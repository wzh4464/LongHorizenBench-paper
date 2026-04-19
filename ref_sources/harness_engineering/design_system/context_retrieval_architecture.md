# Context Retrieval Architecture

## Overview

Context retrieval is the system's ability to locate, extract, and assemble relevant information from the codebase and external sources before each LLM call. The quality of every agent response depends primarily on what the model sees in its context window - which files were read, which symbols were resolved, how much history was retained, and how efficiently the token budget was spent.

Two complementary mechanisms drive context retrieval:

- **Agent-driven retrieval.** The Code Explorer subagent orchestrates five specialized tools (file reading, text search, structural search, symbol lookup, reference finding) in a read-only ReAct loop to answer deep codebase questions. The main agent delegates exploration tasks to this subagent, which operates in an isolated context with filtered tool access.

- **Pipeline-driven assembly.** The ContextPicker orchestrates six context sources - system prompt, playbook strategies, @file references, conversation history, image blocks, and the user query - into a single assembled context. Each piece is tracked with provenance metadata (source, relevance score, token estimate) for traceability and budget management.

Both mechanisms feed into the same output: an `AssembledContext` object that the ReAct executor sends to the LLM on each turn.


## End-to-End Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          User Query                                     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    RETRIEVAL TOOLS (Layer 1)                             │
│                                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌───────────┐ ┌─────────┐ │
│  │read_file │ │list_files│ │   search     │ │find_symbol│ │find_ref │ │
│  │          │ │          │ │(text + AST)  │ │  (LSP)    │ │ (LSP)   │ │
│  │ Direct   │ │ Glob     │ │ Ripgrep +    │ │ Symbol    │ │ Usage   │ │
│  │ content  │ │ patterns │ │ ast-grep     │ │ lookup    │ │ finding │ │
│  └──────────┘ └──────────┘ └──────────────┘ └───────────┘ └─────────┘ │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                 CODE EXPLORER SUBAGENT (Layer 2)                         │
│                                                                         │
│  Main Agent ──spawn──▶ SubAgentManager ──create──▶ Isolated Agent       │
│                                                                         │
│  • Read-only mode, 5 tools only                                         │
│  • Anchor-based search strategy                                         │
│  • Parallel tool calls for independent queries                          │
│  • Self-terminating (no hard iteration limit)                           │
│  • Returns summary to parent via separate_response                      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               CONTEXT ASSEMBLY PIPELINE (Layer 3)                       │
│                                                                         │
│  ContextPicker.pick_context()                                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────────┐ │
│  │[1] System    │ │[2] Playbook  │ │[3] @File     │ │[4] Convo      │ │
│  │    Prompt    │ │  Strategies  │ │  References  │ │   History     │ │
│  │ (18 sections │ │ (weighted    │ │ (text, dir,  │ │ (compacted    │ │
│  │  composed)   │ │  selection)  │ │  PDF, image) │ │  if needed)   │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └───────────────┘ │
│  ┌──────────────┐ ┌──────────────┐                                     │
│  │[5] Image     │ │[6] User      │                                     │
│  │    Blocks    │ │    Query     │                                     │
│  └──────────────┘ └──────────────┘                                     │
│                         │                                               │
│                         ▼                                               │
│                  AssembledContext                                        │
│          (system_prompt, messages, pieces,                               │
│           image_blocks, total_tokens_estimate)                          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                CONTEXT OPTIMIZATION (Layer 4)                            │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Staged Compaction                                                │   │
│  │  70% ──▶ Warning   80% ──▶ Mask old     90% ──▶ Aggressive     │   │
│  │                      observations          trimming              │   │
│  │                                    99% ──▶ Full LLM summary     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Observation Lifecycle                                            │   │
│  │  Active ──age──▶ Faded (~15 tokens) ──size──▶ Archived (file)   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Token Calibration: API-reported prompt_tokens as ground truth    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       LLM API Call                                      │
└─────────────────────────────────────────────────────────────────────────┘
```


## Retrieval Tools

The system provides five tools for retrieving codebase context. Each tool is registered in the ToolRegistry and dispatched through typed handlers.

### read_file

Direct file content retrieval. Accepts an optional line offset and maximum line count (default 2000 lines). Returns content with line numbers. The handler (`FileToolHandler.read_file` in `tools/handlers/file_handlers.py:171-184`) sanitizes paths relative to the working directory and detects binary files via null-byte checking and UTF-8 validation.

### list_files

Glob-based file and directory discovery. Accepts a path and an optional glob pattern (e.g., `*.py`, `**/*.tsx`). Returns up to 100 results by default, truncates output at 500 entries. Useful for understanding project structure before targeted reads.

### search (text mode)

Ripgrep-backed regex search across the codebase. Returns matching lines with file path, line number, and surrounding content. Maximum 50 matches returned, output truncated at 30,000 characters. Invoked via `search(pattern, path, type="text")`. Implemented in `file_handlers.py:236-294`.

### search (AST mode)

ast-grep structural pattern matching. Language-aware parsing that matches code by structure rather than text. Uses `$VAR` wildcards for structural queries - for example, `console.log($MSG)` matches all console.log calls regardless of argument content. Requires a language hint or auto-detection from file extension. Invoked via `search(pattern, path, type="ast", lang="python")`.

### find_symbol / find_referencing_symbols

LSP-powered symbol operations supporting 30+ languages (Python, TypeScript, Rust, Go, Java, C++, Ruby, and others). `find_symbol` accepts a name pattern with wildcards (e.g., `My*`, `MyClass.method`) and returns symbol metadata: kind (class, function, variable), file path, line number, and a body preview (up to 5 lines). `find_referencing_symbols` finds all usages of a given symbol, grouped by file with line numbers and code snippets.

Both tools use `SymbolRetriever` backed by the `solidlsp` language server (`tools/lsp/wrapper.py`). Extension-to-language mapping covers 30+ file types.


## Code Explorer Subagent

### Purpose

The Code Explorer is a read-only subagent designed for deep codebase exploration. When the main agent encounters a question that requires systematic code analysis - understanding architecture, finding patterns, tracing data flow - it delegates to the Code Explorer rather than performing the search itself. This keeps the main agent's context clean and allows focused, parallel exploration.

### Tool Access

The Code Explorer has access to exactly five tools:

| Tool | Purpose |
|------|---------|
| `read_file` | Read file content with offset/line-range |
| `search` | Text (ripgrep) and AST (ast-grep) search |
| `list_files` | Glob-based file discovery |
| `find_symbol` | LSP symbol lookup by name pattern |
| `find_referencing_symbols` | LSP reference finding |

All other tools (file writing, command execution, todo management, subagent spawning) are excluded from its schema. The LLM never sees definitions for tools it cannot use.

### Spawn and Execution Flow

```
Main Agent (full tool access)
    │
    ├── spawn_subagent("Code-Explorer", task_description)
    │       │
    │       ▼
    │   ToolRegistry._execute_spawn_subagent()
    │       │
    │       ▼
    │   SubAgentManager.execute_subagent()
    │       │
    │       ├── Retrieve pre-compiled SubAgent (or create fresh instance)
    │       ├── Apply FilteredToolRegistry with 5 allowed tools
    │       ├── Wrap UI callback in NestedUICallback (for nested display)
    │       ├── Fire SUBAGENT_START hooks
    │       │
    │       └── agent.run_sync(
    │               message = task_description,
    │               message_history = None,       ◄── Fresh context, no parent leakage
    │               max_iterations = None          ◄── Self-terminating via prompt
    │           )
    │               │
    │               ▼
    │           Code Explorer ReAct Loop
    │           ├── Anchor-based search (symbol → text → AST → list_files)
    │           ├── Parallel tool calls for independent queries
    │           ├── Depth-first: follow one promising lead, stop when answered
    │           └── Returns summary with file paths and line numbers as evidence
    │
    ◄── Result injected as separate_response into parent conversation
```

**Key properties:**

- **Isolation.** The subagent starts with an empty message history. It cannot see the parent agent's conversation, preventing context pollution in both directions.

- **No iteration limit.** Unlike a fixed budget, the Code Explorer's prompt instructs it to stop as soon as evidence answers the question. If progress stalls, it reports what is known and what remains unknown.

- **Search strategy.** The prompt encodes an anchor-based approach: identify the strongest anchor point in the query, then select the most efficient tool. Symbol names go to `find_symbol`. String patterns (error messages, route paths, config keys) go to `search(type="text")`. Structural patterns (all classes inheriting X, all functions decorated with Y) go to `search(type="ast")`. File name lookups use `list_files` as a last resort.

- **Parallel execution.** When multiple independent searches are needed, the Code Explorer issues them in a single response. The tool registry dispatches read-only tools concurrently via a thread pool (up to 5 workers).

- **Result delivery.** The subagent's final output is returned to the parent agent in the `separate_response` field, displayed as a separate assistant message in the UI. The parent agent then continues its own reasoning with the exploration results available in its conversation.


## Context Assembly Pipeline

Before each LLM call, `ContextPicker.pick_context()` assembles the full context from six sources in a fixed priority order. Each source produces one or more `ContextPiece` objects, each annotated with a `ContextReason` containing the source identifier, a human-readable explanation, a relevance score, and a token estimate.

```
User Query
    │
    ▼
ContextPicker.pick_context(query, agent)
    │
    ├─[1] System Prompt
    │     PromptComposer loads 18 markdown sections, filtered by condition predicates
    │     and sorted by ascending priority. Identity and persona rules appear first,
    │     dynamic context last.
    │
    ├─[2] Playbook Strategies
    │     BulletSelector ranks playbook entries by weighted score:
    │       effectiveness (0.5) + recency (0.3) + semantic similarity (0.2)
    │     Semantic similarity uses cosine distance over cached embeddings.
    │     Top-ranked bullets are injected into the system prompt.
    │
    ├─[3] @File References
    │     FileContentInjector extracts @mentions from the query, resolves paths,
    │     and processes each by type:
    │       Text files    → <file_content> XML tags (full content)
    │       Large files   → <file_truncated> (first 100 + last 50 lines)
    │       Directories   → <directory_listing> (tree with gitignore filtering)
    │       PDFs          → <pdf_content> (extracted text via pypdf)
    │       Images        → multimodal base64 blocks for vision models
    │
    ├─[4] Conversation History
    │     All session messages retrieved from SessionManager.
    │     May be compacted if context pressure is high.
    │
    ├─[5] Image Blocks
    │     Multimodal vision content from @image references, encoded as base64.
    │
    └─[6] User Query
          Current input with any @file content injected inline.
            │
            ▼
    AssembledContext
    ├── system_prompt: str         (final composed prompt)
    ├── messages: list[dict]       (API-ready message list)
    ├── pieces: list[ContextPiece] (traceable breakdown)
    ├── image_blocks: list[dict]   (multimodal content)
    └── total_tokens_estimate: int (budget tracking)
```

The assembled message list is validated by `ValidatedMessageList`, which enforces structural integrity - every assistant message with tool calls must be followed by matching tool results before the next user turn. Violations are auto-repaired with synthetic error placeholders rather than causing a hard failure.

### Playbook Selection Detail

The playbook is a collection of natural-language strategy bullets accumulated across sessions. Each bullet carries effectiveness counters (helpful, harmful, neutral) and timestamps. The `BulletSelector` computes a composite score:

- **Effectiveness (weight 0.5):** `(helpful × 1.0 + neutral × 0.5 + harmful × 0.0) / total`. Untested bullets receive a neutral default of 0.5.
- **Recency (weight 0.3):** `1.0 / (1.0 + days_old × 0.1)`. A bullet created today scores 1.0; one created 7 days ago scores 0.59; 30 days ago scores 0.25.
- **Semantic similarity (weight 0.2):** Cosine similarity between the query embedding and the bullet embedding, using `text-embedding-3-small`. Embeddings are cached to disk for persistence.

Batch embedding generation reduces API calls from N+1 to 1 per selection round.

### @File Reference Processing

The `FileContentInjector` (`repl/file_content_injector.py`) handles inline file references in user queries:

1. **Extract.** Pattern-match `@"quoted path"` and `@unquoted_path` references, excluding email addresses.
2. **Resolve.** Convert to absolute paths relative to the working directory.
3. **Classify.** Determine file type via extension mapping (50+ known extensions), special filenames (Dockerfile, Makefile), and binary detection (null-byte check, UTF-8 validation, printable-character threshold of 85%).
4. **Process.** Dispatch to type-specific processors that produce XML-tagged output with path, size, and language attributes.
5. **Inject.** Insert processed content into the user message before sending to the LLM.


## Token-Efficient MCP Tool Discovery

External tools provided by MCP servers present a token efficiency challenge: loading all schemas upfront can consume thousands of tokens for tools that may never be used in a given session.

The system addresses this through lazy discovery:

```
LLM calls search_tools("database query tools")
    │
    ▼
SearchToolsHandler.search_tools()
    │
    ├── Build vocabulary from all registered MCP tool names and descriptions
    │     Extract keywords from tool names (split on _, -)
    │     Extract keywords from descriptions (3+ character words)
    │
    ├── Score each tool against the query using vocabulary matching
    │
    ├── Return top matches with names and descriptions
    │
    └── For each matched tool: discover_mcp_tool(tool_name)
            │
            ▼
        _discovered_mcp_tools.add(tool_name)
            │
            ▼
        Next LLM call includes this tool's schema
```

Only tools that have been explicitly discovered through `search_tools` get their schemas included in subsequent LLM calls. The `_discovered_mcp_tools` set in the ToolRegistry tracks which tools are active. This reduces the baseline token cost of MCP integration to near zero - paying only for tools the agent actually needs.


## Context Optimization

### Staged Compaction

The compactor monitors token utilization incrementally, using the API-reported `prompt_tokens` count as calibration. Four escalating thresholds trigger progressively aggressive reduction:

| Threshold | Level | Action |
|-----------|-------|--------|
| 70% | WARNING | Log utilization metrics |
| 80% | MASK | Replace old tool results with compact reference pointers (~15 tokens each) |
| 90% | AGGRESSIVE | Aggressive result trimming + observation masking |
| 99% | COMPACT | Full LLM-powered summarization of conversation middle |

### Observation Lifecycle

Tool observations transition through three preservation states:

- **Active.** Recent observations retain full content. Default state for the most recent N tool results.
- **Faded.** Observations past the recency threshold have their content replaced in-place with a reference pointer (e.g., `[ref: call_01 - see history]`), reducing from thousands of tokens to approximately 15. The conversation structure required by the API is preserved.
- **Archived.** Observations that exceed a size threshold at birth are never inserted at full resolution. They are written to the filesystem, and the model receives a short preview (first ~150 tokens) plus the file path for on-demand retrieval.

### Artifact Registry

A structured index of all files touched during the session (create, modify, read, delete) with timestamps and operation counts. This index survives compaction - it is injected as a context reminder after summarization - ensuring the agent retains awareness of workspace state even after aggressive context reduction.


## Key Files Reference

| Component | File Path | Key Elements |
|-----------|-----------|--------------|
| Tool Registry | `core/context_engineering/tools/registry.py` | `ToolRegistry`, `execute_tool()`, `_discovered_mcp_tools` |
| File Handlers | `core/context_engineering/tools/handlers/file_handlers.py` | `FileToolHandler` - read, write, edit, list, search |
| Process Handlers | `core/context_engineering/tools/handlers/process_handlers.py` | `ProcessToolHandler` - run_command, background processes |
| Search Tools Handler | `core/context_engineering/tools/handlers/search_tools_handler.py` | `SearchToolsHandler` - MCP tool discovery |
| Batch Tool | `core/context_engineering/tools/implementations/batch_tool.py` | `BatchTool` - parallel/serial multi-tool execution |
| find_symbol | `core/context_engineering/tools/symbol_tools/find_symbol.py` | `handle_find_symbol()` - LSP symbol lookup |
| find_referencing_symbols | `core/context_engineering/tools/symbol_tools/find_referencing_symbols.py` | `handle_find_referencing_symbols()` - LSP reference finding |
| LSP Wrapper | `core/context_engineering/tools/lsp/wrapper.py` | `LSPServerWrapper` - solidlsp adapter, 30+ language support |
| Context Picker | `core/context_engineering/context_picker/picker.py` | `ContextPicker.pick_context()` - 6-source assembly pipeline |
| Context Models | `core/context_engineering/context_picker/models.py` | `ContextPiece`, `ContextReason`, `AssembledContext` |
| File Content Injector | `repl/file_content_injector.py` | `FileContentInjector` - @file reference expansion |
| Playbook | `core/context_engineering/memory/playbook.py` | `Playbook`, `Bullet` - strategy storage |
| Bullet Selector | `core/context_engineering/memory/selector.py` | `BulletSelector` - weighted hybrid retrieval |
| Embeddings | `core/context_engineering/memory/embeddings.py` | `EmbeddingCache` - persistent embedding storage |
| Compaction | `core/context_engineering/compaction.py` | `ContextCompactor` - staged compaction, artifact registry |
| Code Explorer Spec | `core/agents/subagents/agents/code_explorer.py` | `CODE_EXPLORER_SUBAGENT` - subagent definition |
| Code Explorer Prompt | `core/agents/prompts/templates/subagents/subagent-code-explorer.md` | Search strategy, efficiency rules, completion rules |
| SubAgent Manager | `core/agents/subagents/manager.py` | `SubAgentManager` - spawn, filter tools, execute |
| Schema Builder | `core/agents/components/schemas/normal_builder.py` | `ToolSchemaBuilder` - filtered schema generation |
| Session Manager | `core/context_engineering/history/session_manager.py` | `SessionManager` - conversation persistence |
| MCP Manager | `core/context_engineering/mcp/manager.py` | `MCPManager` - server lifecycle, transport management |
| Skills | `core/skills.py` | `SkillLoader` - lazy-loaded domain knowledge templates |
