# Hooks System Architecture

## Overview

The hooks system provides lifecycle event interception through shell command execution. Users configure hook commands in `settings.json` that run as subprocesses in response to agent events such as tool execution, session start, context compaction, and subagent spawning. Hooks receive structured JSON on stdin and communicate decisions back via exit codes and optional JSON on stdout. This enables external scripts to block dangerous operations, inject additional context, modify tool inputs, or log activity without modifying the core agent codebase.

## End-to-End Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Event Source Layer                               │
│                                                                         │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌────────────┐            │
│  │Tool      │  │Session    │  │Subagent  │  │Compaction  │            │
│  │Registry  │  │Lifecycle  │  │Manager   │  │Engine      │            │
│  └────┬─────┘  └─────┬─────┘  └────┬─────┘  └─────┬──────┘            │
│       │               │             │              │                    │
│       │  PreToolUse   │ SessionStart│ SubagentStart│ PreCompact         │
│       │  PostToolUse  │ SessionEnd  │ SubagentStop │                    │
│       │  PostToolUse  │ Stop        │              │                    │
│       │  Failure      │             │              │                    │
└───────┼───────────────┼─────────────┼──────────────┼────────────────────┘
        │               │             │              │
        ▼               ▼             ▼              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         HookManager                                     │
│                                                                         │
│  ┌──────────────────────────────────────────────┐                      │
│  │ HookConfig (frozen at session start)          │                      │
│  │                                                │                      │
│  │  hooks: {                                      │                      │
│  │    "PreToolUse":  [HookMatcher, ...]           │                      │
│  │    "PostToolUse": [HookMatcher, ...]           │                      │
│  │    "SessionStart": [HookMatcher, ...]          │                      │
│  │    ...                                         │                      │
│  │  }                                             │                      │
│  └──────────────────────────────────────────────┘                      │
│                          │                                              │
│  run_hooks(event, match_value, event_data)                             │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────┐                           │
│  │ For each HookMatcher:                    │                           │
│  │   if matcher.matches(match_value):       │                           │
│  │     for each HookCommand:                │                           │
│  │       execute(command, stdin_data)        │──── short-circuit ────┐  │
│  │       if exit_code == 2: BLOCK           │◄──────────────────────┘  │
│  └─────────────────────────────────────────┘                           │
│                          │                                              │
│                          ▼                                              │
│                    HookOutcome                                          │
│                    (blocked, results, additional_context, ...)          │
└─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     HookCommandExecutor                                 │
│                                                                         │
│  subprocess.run(command, shell=True, stdin=JSON, timeout=N)            │
│                                                                         │
│  ┌──────────────────────────────────────────────┐                      │
│  │ stdin:  JSON payload (session_id, cwd, ...)   │                      │
│  │ stdout: Optional JSON (context, decisions)    │                      │
│  │ exit code:                                     │                      │
│  │   0 = success (proceed)                        │                      │
│  │   2 = block (deny operation)                   │                      │
│  │   other = error (log, proceed anyway)          │                      │
│  └──────────────────────────────────────────────┘                      │
│                                                                         │
│  Returns: HookResult(exit_code, stdout, stderr, timed_out, error)      │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Model Hierarchy

```
HookEvent (Enum)
│
│  SESSION_START           Session initialization
│  USER_PROMPT_SUBMIT      User submits prompt
│  PRE_TOOL_USE            Before tool execution
│  POST_TOOL_USE           After successful tool execution
│  POST_TOOL_USE_FAILURE   After failed tool execution
│  SUBAGENT_START          Subagent spawning
│  SUBAGENT_STOP           Subagent completion
│  STOP                    Session stop
│  PRE_COMPACT             Before context compaction
│  SESSION_END             Session termination
│
HookCommand (Pydantic Model)
│  type: str = "command"
│  command: str                  Shell command to execute
│  timeout: int = 60             Clamped to 1–600 seconds
│
HookMatcher (Pydantic Model)
│  matcher: Optional[str]        Regex pattern (None matches all)
│  hooks: list[HookCommand]      Commands to execute on match
│  _compiled_regex: Pattern       Compiled at construction time
│
│  matches(value) → bool          regex.search() semantics
│                                  None matcher → matches everything
│                                  Invalid regex → fallback to equality
│
HookConfig (Pydantic Model)
│  hooks: dict[str, list[HookMatcher]]
│
│  validate_event_names()         Silently drops unknown events
│  get_matchers(event) → list     Returns matchers for event
│  has_hooks_for(event) → bool    Fast existence check
│
HookResult (Dataclass)
│  exit_code: int
│  stdout: str
│  stderr: str
│  timed_out: bool
│  error: Optional[str]
│
│  success → exit_code == 0 and not timed_out and no error
│  should_block → exit_code == 2
│  parse_json_output() → dict     Parses stdout as JSON
│
HookOutcome (Dataclass)
   blocked: bool
   block_reason: str
   results: list[HookResult]
   additional_context: Optional[str]
   updated_input: Optional[dict]
   permission_decision: Optional[str]
   decision: Optional[str]
```

## Execution Flow

```
run_hooks(event, match_value, event_data)
│
├── get_matchers(event) from frozen HookConfig
│
├── For each HookMatcher in matchers list:
│   │
│   ├── matcher.matches(match_value)?
│   │   │
│   │   NO ──► skip to next matcher
│   │   │
│   │   YES
│   │   │
│   │   ▼
│   ├── For each HookCommand in matcher.hooks:
│   │   │
│   │   ├── _build_stdin(event, match_value, event_data)
│   │   │   └── Constructs JSON payload with session context
│   │   │
│   │   ├── executor.execute(command, stdin_data, timeout)
│   │   │   └── subprocess.run(shell=True, input=JSON, timeout=N)
│   │   │
│   │   ├── result = HookResult(exit_code, stdout, stderr, ...)
│   │   │
│   │   ├── if result.success:
│   │   │   └── Parse JSON output → merge additional_context,
│   │   │       updated_input, permission_decision, decision
│   │   │
│   │   ├── if result.should_block (exit_code == 2):
│   │   │   ├── Set outcome.blocked = True
│   │   │   ├── Extract block_reason from JSON or stderr
│   │   │   └── SHORT-CIRCUIT: return immediately
│   │   │
│   │   └── Append result to outcome.results
│   │
│   └── Continue to next matcher
│
└── Return HookOutcome
```

## stdin/stdout JSON Protocol

### Base Payload (all events)

```json
{
  "session_id": "abc12345",
  "cwd": "/Users/user/project",
  "hook_event_name": "PreToolUse"
}
```

### Per-Event Enrichment

**Tool events** (PRE_TOOL_USE, POST_TOOL_USE, POST_TOOL_USE_FAILURE):
- `tool_name` - Tool being executed (e.g., "run_command", "edit_file")
- `tool_input` - Tool arguments dict
- `tool_response` - Tool result (POST events only)

**Subagent events** (SUBAGENT_START, SUBAGENT_STOP):
- `agent_type` - Subagent type (e.g., "code-explorer")
- All fields from event_data merged (agent_task, agent_result, etc.)

**Session events** (SESSION_START):
- `startup_type` - How session started ("startup", "resume")

**Compaction events** (PRE_COMPACT):
- `trigger` - What triggered compaction ("auto", "manual")

Any additional fields in event_data are merged into the payload as passthrough.

### stdout Response Fields (optional JSON)

```json
{
  "additionalContext": "Extra context to inject into agent prompt",
  "updatedInput": {"command": "modified-command"},
  "permissionDecision": "allow",
  "decision": "proceed",
  "reason": "Blocked: dangerous command detected"
}
```

## Exit Code Semantics

```
Exit Code    Meaning              Agent Behavior
─────────    ───────              ──────────────
    0        Success              Operation proceeds normally
    2        Block                Operation denied, error returned to agent
  other      Error                Logged as warning, operation proceeds
  timeout    Timed out            Logged as warning, operation proceeds
```

Exit code 2 is the only code that blocks an operation. All other non-zero codes are treated as hook script errors and do not prevent the operation from proceeding. This ensures a buggy hook script cannot silently disable the agent.

## Configuration Format

### settings.json Structure

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "^(run_command|edit_file)$",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/safety-check.sh",
            "timeout": 30
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": null,
        "hooks": [
          {
            "type": "command",
            "command": "logger 'tool executed'",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

### Configuration Loading and Merging

```
load_hooks_config(working_dir)
│
├── Load ~/.opendev/settings.json (global)
│   └── Extract "hooks" key → global_hooks
│
├── Load .opendev/settings.json (project)
│   └── Extract "hooks" key → project_hooks
│
├── Merge: for each event name:
│   └── global_matchers + project_matchers (project appended)
│
├── Validate event names:
│   └── Silently drop unknown events (forward-compatible)
│
├── Parse into HookConfig:
│   └── Compile all matcher regexes at construction time
│
└── Return frozen HookConfig
```

Invalid JSON in either file is logged as a warning and skipped. The system continues with whatever valid configuration was loaded.

## Async Execution Path

For events where the hook result is not needed to decide whether to proceed (logging, telemetry), the hooks system offers fire-and-forget execution.

```
run_hooks_async(event, match_value, event_data)
│
├── has_hooks_for(event)? → NO: return immediately
│
├── Submit run_hooks() to ThreadPoolExecutor
│   └── max_workers=2, thread_name_prefix="hook-async"
│
└── Return immediately (do not wait for result)
```

Used by PostToolUse and PostToolUseFailure events in the tool registry. The main agent loop does not block waiting for logging hooks to complete.

## Tool Registry Integration

```
ToolRegistry.execute_tool(tool_name, arguments)
│
├──── PreToolUse Phase ────────────────────────────────────────────────┐
│                                                                       │
│  if hook_manager and hook_manager.has_hooks_for(PRE_TOOL_USE):       │
│    outcome = hook_manager.run_hooks(                                  │
│      event=PRE_TOOL_USE,                                              │
│      match_value=tool_name,       ◄── regex matched against this     │
│      event_data={"tool_input": arguments}                             │
│    )                                                                  │
│                                                                       │
│    if outcome.blocked:                                                │
│      return {"error": block_reason, "denied": True}  ◄── STOP       │
│                                                                       │
│    if outcome.updated_input:                                          │
│      arguments = {**arguments, **outcome.updated_input}  ◄── MODIFY │
│                                                                       │
├──── Tool Execution ──────────────────────────────────────────────────┤
│                                                                       │
│  result = handler.execute(tool_name, arguments)                      │
│                                                                       │
├──── PostToolUse Phase ───────────────────────────────────────────────┤
│                                                                       │
│  event = POST_TOOL_USE if result.success else POST_TOOL_USE_FAILURE  │
│                                                                       │
│  if hook_manager and hook_manager.has_hooks_for(event):              │
│    hook_manager.run_hooks_async(                  ◄── fire-and-forget│
│      event=event,                                                     │
│      match_value=tool_name,                                           │
│      event_data={"tool_input": arguments, "tool_response": result}   │
│    )                                                                  │
│                                                                       │
└──── Return result ───────────────────────────────────────────────────┘
```

## Hook Initialization and Wiring

At session startup, the REPL initializes the hook system and wires it into all event-producing components.

```
REPL._init_hooks()
│
├── load_hooks_config(working_dir)
│   └── Returns merged, frozen HookConfig
│
├── Create HookManager(config, session_id, cwd)
│
├── Wire into components:
│   ├── tool_registry.set_hook_manager(hook_manager)
│   ├── query_processor.set_hook_manager(hook_manager)
│   ├── subagent_manager.set_hook_manager(hook_manager)
│   └── compactor.set_hook_manager(hook_manager)
│
└── On exception: log warning, _hook_manager = None
    └── System continues without hooks
```

## Security Guarantees

- **TOCTOU protection**: HookConfig is frozen at HookManager initialization. Changes to settings.json during a session are not reflected until the next session. This prevents a malicious process from altering hook policies after the user has reviewed them.

- **Timeout capping**: HookCommand.timeout is clamped to 1–600 seconds via Pydantic validation. subprocess.TimeoutExpired is caught and reported, preventing runaway processes from blocking the agent indefinitely.

- **Error isolation**: Hook script failures (non-zero exit codes other than 2, OSError from missing commands, JSON parse errors in stdout) are logged but never crash the agent. Only exit code 2 blocks operations.

- **Sequential execution**: Hooks within a matcher run sequentially, eliminating race conditions between hook commands that might share state.

- **Forward compatibility**: Unknown event names in settings.json are silently dropped during validation. Adding new events in future versions does not break existing configurations.

## Key Files Reference

| Component | File | Key Elements |
|-----------|------|--------------|
| Event enum, models | `swecli/core/hooks/models.py` | HookEvent, HookCommand, HookMatcher, HookConfig |
| Command executor | `swecli/core/hooks/executor.py` | HookCommandExecutor, HookResult |
| Manager | `swecli/core/hooks/manager.py` | HookManager, HookOutcome, _build_stdin() |
| Config loader | `swecli/core/hooks/loader.py` | load_hooks_config(), merge logic |
| Tool integration | `swecli/core/context_engineering/tools/registry.py` | PreToolUse (L395–413), PostToolUse (L449–463) |
| Initialization | `swecli/repl/repl.py` | _init_hooks() (L319–350) |
