# Persistence Layer Architecture

## Overview

The persistence layer manages all durable state across sessions, configurations, caches, and runtime artifacts. It uses a filesystem-based strategy organized under two root directories: `~/.opendev/` for user-global state and `<project>/.opendev/` for project-scoped state. The layer enforces atomicity through tempfile-rename patterns, concurrency safety through fcntl file locks, and resilience through self-healing indexes and graceful degradation on corruption. No external database is required; all storage uses JSON, JSONL, and plain text files.

## End-to-End Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     Persistence Consumers                                 │
│                                                                           │
│  ┌──────────┐ ┌───────────┐ ┌───────────┐ ┌──────────┐ ┌────────────┐ │
│  │ Session  │ │ Config    │ │ Provider  │ │ MCP      │ │ Undo       │ │
│  │ Manager  │ │ Manager   │ │ Cache     │ │ Config   │ │ Manager    │ │
│  └────┬─────┘ └─────┬─────┘ └─────┬─────┘ └────┬─────┘ └─────┬──────┘ │
│       │              │             │             │             │          │
│  ┌────┴──┐ ┌────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐          │
│  │Playbook│ │Embedding│ │ Topic   │ │ Debug   │ │ Plugins  │          │
│  │Memory │ │ Cache   │ │Detector │ │ Logger  │ │ Manager  │          │
│  └───┬───┘ └───┬────┘ └────┬─────┘ └────┬────┘ └─────┬─────┘          │
│      │          │           │            │            │                   │
└──────┼──────────┼───────────┼────────────┼────────────┼───────────────────┘
       │          │           │            │            │
       ▼          ▼           ▼            ▼            ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        Filesystem Layout                                  │
│                                                                           │
│  ~/.opendev/                              <project>/.opendev/            │
│  ├── settings.json (global config)        ├── settings.json (proj config)│
│  ├── mcp.json (global MCP)                └── skills/ (project skills)   │
│  ├── OPENDEV.md (global context)                                         │
│  ├── history.txt (command history)        <project>/.mcp.json (proj MCP) │
│  ├── projects/                            <project>/OPENDEV.md (context) │
│  │   └── {encoded-path}/                                                 │
│  │       ├── {session_id}.json (metadata)                                │
│  │       ├── {session_id}.jsonl (messages)                               │
│  │       ├── {session_id}.debug (debug log)                              │
│  │       ├── sessions-index.json (index)                                 │
│  │       └── operations.jsonl (undo log)                                 │
│  ├── cache/                                                               │
│  │   ├── models.dev.json (full catalog)                                  │
│  │   └── providers/*.json (per-provider)                                 │
│  ├── skills/ (user skills)                                               │
│  ├── agents/ (user agent definitions)                                    │
│  ├── plans/ (plan mode files)                                            │
│  ├── repos/ (reserved for future use)                                    │
│  ├── logs/ (application logs)                                            │
│  └── plugins/                                                             │
│      ├── known_marketplaces.json                                         │
│      ├── installed_plugins.json                                          │
│      ├── bundles.json                                                    │
│      ├── marketplaces/ (cloned repos)                                    │
│      ├── cache/ (installed plugins)                                      │
│      └── bundles/ (direct bundles)                                       │
│                                                                           │
│  /tmp/opendev/{safe-path}/tasks/                                         │
│  └── {task_id}.output (background task output)                           │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

## Session Storage

Session storage is the largest and most safety-critical persistence subsystem. It uses a split-file format with separate metadata and message files, an index for fast listing, and project-scoped directories for isolation.

### Storage Structure

```
~/.opendev/projects/{encoded-path}/
│
├── sessions-index.json          O(1) session listing cache
│
├── abc12345def4.json            Session metadata (no messages)
├── abc12345def4.jsonl           Message transcript (append-only)
├── abc12345def4.debug           Debug log (optional, JSONL)
│
├── xyz98765abc1.json
├── xyz98765abc1.jsonl
│
└── operations.jsonl             Undo history log

Path encoding: /Users/nghibui/codes/swe-cli → -Users-nghibui-codes-swe-cli
```

### File Formats

**Session Metadata (.json)**:
```json
{
  "id": "abc12345def4",
  "created_at": "2026-03-02T10:30:45.123456",
  "updated_at": "2026-03-02T11:45:30.654321",
  "messages": [],
  "working_directory": "/Users/user/project",
  "metadata": {
    "title": "Add dark mode",
    "summary": null,
    "tags": []
  },
  "playbook": {},
  "file_changes": [],
  "channel": "cli",
  "chat_type": "direct",
  "channel_user_id": "",
  "thread_id": null,
  "delivery_context": {},
  "last_activity": "2026-03-02T11:45:30.654321",
  "workspace_confirmed": true
}
```

The `messages` field in the JSON file is always empty in JSONL mode. Messages are stored exclusively in the `.jsonl` file.

**Message Transcript (.jsonl)**:
```
{"role":"user","content":"fix the login bug","timestamp":"2026-03-02T10:30:45.123456","metadata":{},"tool_calls":[],"tokens":null}
{"role":"assistant","content":"I'll look into that...","timestamp":"2026-03-02T10:30:47.234567","metadata":{},"tool_calls":[{"id":"tc_1","name":"read_file","parameters":{"path":"src/auth.py"},"result":"..."}],"tokens":1234}
```

One ChatMessage per line, serialized with `model_dump()`. Append-only by design.

**Sessions Index (sessions-index.json)**:
```json
{
  "version": 1,
  "entries": [
    {
      "sessionId": "abc12345def4",
      "created": "2026-03-02T10:30:45.123456",
      "modified": "2026-03-02T11:45:30.654321",
      "messageCount": 12,
      "totalTokens": 2340,
      "title": "Add dark mode",
      "summary": null,
      "tags": [],
      "workingDirectory": "/Users/user/project",
      "channel": "cli",
      "channelUserId": "",
      "threadId": null
    }
  ]
}
```

~200 bytes per entry. Enables O(1) session listing without loading full session files.

### Session Write Flow

```
SessionManager.save_session(session, use_jsonl=True)
│
├── Acquire exclusive lock on {session_id}.json
│   └── exclusive_session_lock(path, timeout=10.0)
│       └── Creates .{filename}.lock file, fcntl.flock(LOCK_EX)
│
├── If no title exists:
│   └── generate_title(messages)    ◄── Heuristic: first user message
│
├── Write metadata to {session_id}.json:
│   ├── open(file, "w") under exclusive lock
│   └── messages field = [] (empty in JSONL mode)
│
├── Acquire exclusive lock on {session_id}.jsonl
│   └── exclusive_session_lock(path, timeout=10.0)
│
├── Write messages to {session_id}.jsonl:
│   └── Full rewrite: one line per ChatMessage
│
├── Update sessions-index.json via _update_index_entry():
│   ├── Acquire exclusive_session_lock on index file
│   ├── Load existing index (or rebuild if missing/corrupted)
│   ├── Find/create entry for this session
│   ├── Atomic write: tempfile.mkstemp() → write → Path.replace()
│   └── Update messageCount, totalTokens, modified, title
│
└── All locks released via context managers
```

### Session Read Flow

```
SessionManager.load_session(session_id)
│
├── Search for {session_id}.json in:
│   ├── Current project dir (primary)
│   └── All project dirs under ~/.opendev/projects/ (fallback scan)
│
├── Load metadata from .json file
│
├── Check for .jsonl file:
│   │
│   ├── .jsonl exists:
│   │   └── load_transcript() → read line by line → ChatMessage list
│   │
│   └── .jsonl does not exist (legacy):
│       ├── Check .json for inline messages
│       └── If found → migrate_json_to_jsonl()
│           ├── Extract messages → write .jsonl
│           ├── Clear messages from .json → save
│           └── Backup original as .json.bak
│
├── Set session.messages = loaded messages
│
└── Return Session object
```

### Index Self-Healing

```
SessionManager.list_sessions()
│
├── Try reading sessions-index.json
│   │
│   ├── Success → return entries
│   │
│   ├── File missing:
│   │   └── rebuild_index()
│   │
│   ├── JSON corrupted:
│   │   └── rebuild_index()
│   │
│   └── Permission error:
│       └── rebuild_index()
│
└── rebuild_index():
    ├── Glob all *.json files in session dir
    ├── For each file:
    │   ├── Load session metadata
    │   ├── Count messages from .jsonl if exists
    │   ├── Skip empty sessions (0 messages) → delete them
    │   └── Create index entry
    ├── Sort by modified date (newest first)
    └── Write sessions-index.json (atomic)
```

### Auto-Save and Append

```
SessionManager.add_message(message, auto_save_interval=5)
│
├── session.messages.append(message)
├── Increment turn_count
│
├── turn_count % auto_save_interval == 0?
│   │
│   ├── YES → save_session()
│   │         └── Full write (metadata + messages + index)
│   │
│   └── NO → skip (in-memory only until next save)
│
└── For multi-channel (append-only):
    └── append_message_to_transcript(session_id, message)
        ├── Open .jsonl in append mode ("a")
        ├── Acquire exclusive lock
        ├── Write single line
        └── Release lock
```

### Concurrency Safety

```
Mechanism                    Purpose                          Scope
─────────                    ───────                          ─────
exclusive_session_lock()     Prevent concurrent writes        Per-file (.json, .jsonl, index)
  └── fcntl.flock(LOCK_EX)   Underlying OS lock               Lock file (.{filename}.lock)
tempfile + Path.replace()    Atomic file replacement          Index writes only (POSIX)
Lock timeout (10s)           Prevent deadlocks                Per-lock acquisition
JSONL append mode            Safe concurrent appends          Message writes
```

## Configuration Persistence

### Hierarchical Loading

```
ConfigManager.load_config()
│
├── Load defaults from AppConfig class definition
│   └── model_provider="fireworks", temperature=0.6, max_tokens=16384, etc.
│
├── Load global: ~/.opendev/settings.json
│   └── Parse JSON → merge with defaults
│   └── Remove legacy api_key if present
│   └── Normalize Fireworks model names (short → full ID)
│
├── Load project: <working_dir>/.opendev/settings.json
│   └── Parse JSON → merge (project overrides global)
│   └── Remove legacy api_key if present
│   └── Normalize Fireworks model names (short → full ID)
│
├── Post-processing:
│   ├── Create AppConfig with merged data
│   └── Auto-set max_context_tokens from model context_length (80%)
│       └── Only if not explicitly set or set to old defaults (100000, 256000)
│
└── Return AppConfig (cached in _config)

Priority: project settings > global settings > defaults
API keys: ALWAYS from environment (never persisted in config files)
```

### settings.json Format

```json
{
  "model_provider": "fireworks",
  "model": "accounts/fireworks/models/kimi-k2-instruct-0905",
  "model_thinking_provider": "anthropic",
  "model_thinking": "claude-3-7-sonnet-20250219",
  "temperature": 0.6,
  "max_tokens": 16384,
  "debug_logging": false
}
```

Only user-facing fields are persisted by `save_config()`: model providers, model IDs, API base URL, and debug logging. API keys are never saved to config files; they must come from environment variables.

Full defaults are defined in `AppConfig` (Pydantic model): `auto_save_interval=5`, `verbose=false`, `enable_sound=true`, `topic_detection=true`, `max_undo_history=50`, etc.

### Directory Initialization

```
ConfigManager.ensure_directories()
│
├── Create ~/.opendev/           (from config.opendev_dir)
├── Create ~/.opendev/logs/      (from config.log_dir)
├── Create ~/.opendev/projects/  (project-scoped sessions)
├── Create ~/.opendev/skills/    (user global skills)
│
├── Clean up legacy flat sessions dir:
│   └── If ~/.opendev/sessions/ has *.json files:
│       └── shutil.rmtree() (delete old flat format)
│   └── Recreate ~/.opendev/sessions/ (backward compat)
│
└── If .git exists in working_dir:
    └── Create <project>/.opendev/commands/
```

Note: Additional directories (`cache/`, `agents/`, `plugins/`, etc.) are created lazily by `Paths.ensure_global_dirs()` when needed.

## Provider Cache (models.dev)

The provider cache stores model and provider information fetched from the models.dev API, enabling the system to know model capabilities (context length, vision support, pricing) without bundling a static fallback.

### Cache Architecture

```
~/.opendev/cache/
├── models.dev.json              Full API response (raw catalog)
├── providers/
│   ├── openai.json              Per-provider model info
│   ├── anthropic.json
│   ├── fireworks.json
│   └── .last_sync               Timestamp marker for TTL
```

### Sync Flow

```
sync_provider_cache(cache_dir, cache_ttl=86400)
│
├── is_cache_stale()?
│   └── Check .last_sync mtime vs now > 24 hours
│
├── If fresh (< 24h):
│   └── Return cached data
│
├── If stale or missing:
│   ├── Fetch from models.dev API
│   │   └── _fetch_models_dev() → HTTP GET
│   │
│   ├── Transform per-provider:
│   │   └── _convert_provider_to_internal(raw_data)
│   │       ├── Extract: id, name, api_base_url, api_key_env
│   │       └── Per model: context_length, capabilities, pricing
│   │
│   ├── Write models.dev.json (full catalog)
│   ├── Write providers/{id}.json (per-provider)
│   ├── Touch .last_sync marker
│   │
│   └── On network failure:
│       ├── Return stale cache if exists
│       └── Return None if no cache at all
│
└── Environment overrides:
    ├── OPENDEV_MODELS_DEV_PATH → Use local file instead of API
    └── OPENDEV_DISABLE_REMOTE_MODELS → Skip network entirely
```

### Per-Provider Format

```json
{
  "id": "openai",
  "name": "OpenAI",
  "api_key_env": "OPENAI_API_KEY",
  "api_base_url": "https://api.openai.com/v1",
  "models": {
    "gpt-4o": {
      "id": "gpt-4o",
      "name": "GPT-4o",
      "context_length": 128000,
      "capabilities": ["text", "vision"],
      "pricing": {"input": 2.50, "output": 10.00, "unit": "per 1M tokens"},
      "max_tokens": 4096,
      "supports_temperature": true
    }
  }
}
```

## MCP Server Configuration

### Storage and Merge

```
MCP Config Sources:
│
├── Global: ~/.opendev/mcp.json
│
├── Project: <working_dir>/.mcp.json
│   └── Note: at project root, NOT in .opendev/
│
└── merge_configs(global, project)
    └── Project servers override global servers with same name


Format:
{
  "mcpServers": {
    "server-name": {
      "command": "uvx",
      "args": ["mcp-server-sqlite", "${DB_PATH}"],
      "env": {"API_KEY": "${MY_API_KEY}"},
      "enabled": true,
      "autoStart": true,
      "transport": "stdio"
    }
  }
}
```

Environment variables in `args`, `env`, `url`, and `headers` are expanded via `${VAR_NAME}` syntax using `expand_env_vars()`. Unexpanded variables are left as literal strings.

## Undo History

### Operations Log

```
{session_dir}/operations.jsonl

Format (one entry per line):
{"timestamp":"2026-03-02T10:30:45","type":"FILE_WRITE","path":"/src/auth.py","status":"SUCCESS","id":"op-001"}
{"timestamp":"2026-03-02T10:31:12","type":"FILE_EDIT","path":"/src/auth.py","status":"SUCCESS","id":"op-002"}
```

### Write Pattern

```
UndoManager.record_operation(operation)
│
├── Append to in-memory history list
│
├── If len(history) > max_history (50):
│   └── Trim oldest entries (FIFO)
│
└── _append_to_log(operation)
    ├── Open operations.jsonl in append mode
    ├── Write single JSON line
    └── On failure: log warning, continue (best-effort persistence)
```

The undo log is best-effort. Write failures are logged but do not affect agent operation. The in-memory history is the primary data source; the JSONL log serves as a durable backup for post-session analysis.

## Playbook Memory

The ACE Playbook persists learned strategies within the session.

```
Session.playbook (dict)
│
├── Serialized Playbook:
│   ├── bullets: dict[str, Bullet]
│   │   └── Each bullet: id, section, content, helpful/harmful/neutral counts
│   ├── sections: dict[str, list[str]]
│   │   └── Section name → list of bullet IDs
│   └── next_id: int
│
├── Persistence:
│   ├── Saved as part of session .json file
│   ├── playbook.save_to_file(path) → standalone JSON
│   └── Playbook.load_from_file(path) → deserialize
│
└── Selection for context:
    └── BulletSelector scores bullets by:
        ├── Effectiveness: (helpful - harmful) / total    weight: 0.5
        ├── Recency: normalized updated_at                weight: 0.3
        └── Semantic similarity: cosine(query, bullet)    weight: 0.2
```

## Embedding Cache

```
EmbeddingCache
│
├── Storage: User-configurable JSON file path
│
├── Cache key: SHA256[:16] of "model:text"
│
├── Entry:
│   ├── text: str (original text)
│   ├── model: str (embedding model name)
│   ├── hash: str (cache key)
│   └── embedding: list[float] (vector)
│
├── Operations:
│   ├── get(text, model) → vector or None
│   ├── set(text, embedding, model) → void
│   ├── get_or_generate(text, generator_fn) → vector
│   ├── batch_get_or_generate(texts, generator_fn) → vectors
│   ├── save_to_file(path) → JSON
│   └── load_from_file(path) → EmbeddingCache or None
│
└── Corruption handling:
    └── load_from_file returns None on parse error
        └── Cache rebuilt transparently on next use
```

## Background Task Output

```
/tmp/opendev/{safe-path}/tasks/
│
├── a1b2c3d.output       Plain text, append-only (PTY stream)
├── e5f6g7h.output
└── ...

Path construction:
├── safe-path = working_dir.resolve() with / replaced by -
└── e.g. /Users/nghibui/codes/project → -Users-nghibui-codes-project

Write pattern:
├── Initial write at task registration
├── Background daemon thread streams PTY output → file (append mode)
├── select() with 0.5s timeout for non-blocking reads
└── Thread-safe via RLock on task metadata

Read pattern:
├── read_output(task_id, tail_lines=100)
└── Reads entire file, returns last N lines

Cleanup:
├── No automatic garbage collection
├── Output files persist in /tmp/ (OS cleanup responsibility)
└── Explicit cleanup via manager.cleanup() kills all running tasks
```

## Debug Logging

```
{session_dir}/{session_id}.debug

Format (JSONL):
{"ts":"2026-03-02T10:30:45.123456","elapsed_ms":0,"event":"llm_call_start","component":"react","data":{"model":"gpt-4o","tokens":500}}
{"ts":"2026-03-02T10:30:47.234567","elapsed_ms":2234,"event":"llm_call_end","component":"react","data":{"status":"success","response_tokens":150}}

Enabled: --debug or --verbose flag (AppConfig.debug_logging)
Thread safety: threading.Lock for JSONL appends
Data truncation: String values capped at 200 chars
Disabled: Returns noop logger (zero overhead)
```

## Plugin and Skill Storage

### Skills Discovery Hierarchy

```
Priority (highest → lowest):

1. <project>/.opendev/skills/           Project-specific skills
2. ~/.opendev/skills/                   User global skills
3. swecli/skills/builtin/              Built-in skills (shipped with package)

Bundle skills (~/.opendev/plugins/bundles/*/skills/) are discovered
separately by PluginManager.get_plugin_skills() with source attribution.

File format: Markdown with YAML frontmatter
---
name: commit
description: "Git commit best practices"
model: sonnet
tools: "*"
---

System prompt content here...
```

### Plugin Registry

```
~/.opendev/plugins/
├── known_marketplaces.json       Registered marketplace repos
├── installed_plugins.json        Installed from marketplaces (user)
├── bundles.json                  Direct plugin bundles (user)
├── marketplaces/                 Cloned marketplace git repos
├── cache/                        Installed plugin files
└── bundles/                      Direct bundle directories

<project>/.opendev/plugins/
├── installed_plugins.json        Project-scoped overrides
└── bundles.json                  Project-scoped overrides

Merge: project registries override user registries
```

## Concurrency and Safety Summary

```
Subsystem            Mechanism                          Pattern
─────────            ─────────                          ───────
Session writes       exclusive_session_lock (fcntl)      Lock file + 10s timeout
Session index        exclusive_session_lock + tempfile   Atomic replacement (POSIX)
Message appends      exclusive_session_lock + append     Concurrent-safe JSONL appends
Config reads         In-memory cache                     Single load, cached thereafter
Provider cache       .last_sync mtime check              TTL-based invalidation (24h)
Undo log             Best-effort append                  Silent fail on write error
Debug log            threading.Lock                      Thread-safe JSONL appends
Background output    RLock + daemon threads              Per-task streaming isolation
Plugin registry      No locking                          Single-writer assumed
```

## Error Recovery

```
Failure                         Recovery
───────                         ────────
sessions-index.json missing     rebuild_index() scans *.json files
sessions-index.json corrupted   rebuild_index() recreates from scratch
.jsonl missing (legacy)         migrate_json_to_jsonl() one-time migration
Provider cache stale            Stale-while-revalidate from disk
Provider cache missing          Blocking sync from models.dev API
API key missing                 Graceful no-op (topic detector, etc.)
Undo log write failure          In-memory history unaffected
Debug log write failure         Noop logger, zero overhead
Embedding cache corrupted       Returns None, rebuilt transparently
Empty sessions in index         Cleaned up during rebuild
Lock acquisition timeout        Exception raised after 10s
```

## Key Files Reference

| Component | File | Key Elements |
|-----------|------|--------------|
| Session manager | `swecli/core/context_engineering/history/session_manager.py` | SessionManager, save/load/list, index, migration |
| Config manager | `swecli/core/runtime/config.py` | ConfigManager, load_config(), ensure_directories() |
| Provider cache | `swecli/config/models_dev_loader.py` | load_models_dev_catalog(), sync_provider_cache() |
| MCP config | `swecli/core/context_engineering/mcp/config.py` | MCPConfig, merge_configs(), expand_env_vars() |
| Undo manager | `swecli/core/context_engineering/history/undo_manager.py` | UndoManager, record_operation(), undo_last() |
| Playbook memory | `swecli/core/context_engineering/memory/playbook.py` | Playbook, Bullet, save_to_file() |
| Embedding cache | `swecli/core/context_engineering/memory/embeddings.py` | EmbeddingCache, get_or_generate() |
| Background tasks | `swecli/core/context_engineering/tools/background_task_manager.py` | BackgroundTaskManager, register_task() |
| Debug logger | `swecli/core/debug/session_debug_logger.py` | SessionDebugLogger, log() |
| Path management | `swecli/core/paths.py` | Paths class, encode_project_path() |
| Plugin config | `swecli/core/plugins/config.py` | load_installed_plugins(), save_installed_plugins() |
| Session model | `swecli/models/session.py` | Session, SessionMetadata |
| File change model | `swecli/models/file_change.py` | FileChange, FileChangeType |
