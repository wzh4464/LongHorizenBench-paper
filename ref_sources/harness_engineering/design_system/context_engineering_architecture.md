# Context Engineering Layer Architecture

> Definitive reference for `swecli/core/context_engineering/` - every subsystem, data flow, and integration point.

---

## 1. Layer Overview

```mermaid
graph TB
    subgraph UserInput["User Input"]
        QP[QueryProcessor]
        QE[QueryEnhancer]
    end

    subgraph Root["Root Components"]
        VML[ValidatedMessageList]
        MPV[MessagePairValidator]
        CC[ContextCompactor]
        CTX[ToolExecutionContext]
    end

    subgraph History["History & Persistence"]
        SM[SessionManager]
        TD[TopicDetector]
        UM[UndoManager]
        FL[file_locks]
    end

    subgraph Memory["Memory / ACE"]
        PB[Playbook]
        DT[Delta / DeltaBatch]
        RF[Reflector]
        CU[Curator]
        BS[BulletSelector]
        EC[EmbeddingCache]
        CS[ConversationSummarizer]
    end

    subgraph MCP["MCP Integration"]
        MCfg[MCPConfig]
        MMgr[MCPManager]
        MHnd[McpToolHandler]
        STH[SearchToolsHandler]
    end

    subgraph Retrieval["Retrieval & Context Assembly"]
        TM[ContextTokenMonitor]
        CI[CodebaseIndexer]
        CR[ContextRetriever]
        CP[ContextPicker]
        CT[ContextTracer]
    end

    subgraph ToolSystem["Tool System"]
        TR[ToolRegistry]
        FH[FileToolHandler]
        PH[ProcessToolHandler]
        WH[WebToolHandler]
        TDH[TodoHandler]
        THH[ThinkingHandler]
        BTM[BackgroundTaskManager]
    end

    subgraph SymbolLSP["Symbol Tools + LSP"]
        SR[SymbolRetriever]
        LSPw[LSPServerWrapper]
        LS[37 Language Servers]
    end

    subgraph Skills["Skills System"]
        SL[SkillLoader]
        SKM[SkillMetadata]
        LSK[LoadedSkill]
    end

    subgraph Hooks["Hooks System"]
        HM[HookManager]
        HE[HookCommandExecutor]
        HC[HookConfig]
        HL[loader]
    end

    QP --> QE
    QE --> CP
    CP --> VML
    CP --> PB
    CP --> SM
    CP --> TM

    VML --> CC
    CC --> TM

    QP --> TR
    TR --> FH & PH & WH & TDH & THH
    TR --> MHnd
    TR --> STH
    MHnd --> MMgr
    STH --> MMgr

    FH --> SR
    SR --> LSPw --> LS

    PH --> BTM

    TR --> CTX
    CTX --> SM & UM

    RF --> CU --> DT --> PB
    BS --> EC

    SM --> FL
    SM --> TD

    TR --> SL
    SL --> SKM & LSK

    HM --> HE
    HL --> HC --> HM
    TR -.->|PreToolUse / PostToolUse| HM
    QP -.->|UserPromptSubmit| HM
    CC -.->|PreCompact| HM
```

**Ten subsystems**, 90+ source files. The flow is: **User input** enters via `QueryProcessor`, gets enhanced with `@file` references, assembled by `ContextPicker` into `AssembledContext`, wrapped in `ValidatedMessageList`, checked by `ContextCompactor`, then fed to the ReAct loop. The `ToolRegistry` dispatches to 13+ handlers, each delegating to specialized implementations. `SessionManager` persists everything; `ACE` learns from outcomes. **Skills** provide on-demand knowledge injection via `invoke_skill`. **Hooks** fire shell commands at lifecycle events (tool use, session start/end, compaction) for user-defined automation.

---

## 2. Message Integrity & Validation

### ValidatedMessageList State Machine

```mermaid
stateDiagram-v2
    [*] --> EXPECT_ANY: init(messages)

    EXPECT_ANY --> EXPECT_ANY: append(user)
    EXPECT_ANY --> EXPECT_ANY: append(system)
    EXPECT_ANY --> EXPECT_TOOL_RESULTS: append(assistant + tool_calls)

    EXPECT_TOOL_RESULTS --> EXPECT_TOOL_RESULTS: append(tool) - discard from pending_ids
    EXPECT_TOOL_RESULTS --> EXPECT_ANY: last pending_id satisfied
    EXPECT_TOOL_RESULTS --> EXPECT_ANY: append(user) - auto-complete pending with synthetic errors

    note right of EXPECT_TOOL_RESULTS
        pending_ids = set of tool_call IDs
        awaiting matching tool results.
        Each tool result discards its ID.
    end note
```

**`ValidatedMessageList`** (`validated_message_list.py`) is a `list` subclass with write-time enforcement:

- **Thread-safe**: `threading.Lock` guards all mutations
- **`_pending_tool_ids: set[str]`**: Tracks tool call IDs awaiting results
- **`_strict: bool`**: `True` raises on violations; `False` auto-repairs with warnings
- **`SYNTHETIC_TOOL_RESULT`**: Error placeholder inserted for missing results

Intercepted mutations: `append`, `extend`, `__setitem__`, `insert`. All reads pass through unmodified.

### MessagePairValidator

```mermaid
flowchart LR
    subgraph SinglePass["Single Forward Pass"]
        M1[Message i] --> Check{role?}
        Check -->|assistant + tc| Track["Add tc IDs to expected set"]
        Check -->|tool| Verify["Check ID in expected set"]
        Check -->|user| Gap["Flag if expected not empty"]
    end

    subgraph ViolationTypes
        V1["MISSING_TOOL_RESULT"]
        V2["ORPHANED_TOOL_RESULT"]
        V3["CONSECUTIVE_SAME_ROLE"]
    end

    subgraph Repair
        R1["Missing → insert synthetic error"]
        R2["Orphaned → remove message"]
    end

    SinglePass --> ViolationTypes --> Repair
```

**`validate_tool_results_complete()`** is the pre-batch guard called by `ReactExecutor` before adding results to history. Fills missing entries with synthetic errors containing `success: False`.

### ToolExecutionContext

```mermaid
graph LR
    CTX["ToolExecutionContext"]
    CTX --- MM["mode_manager: ModeManager"]
    CTX --- AM["approval_manager: ApprovalManager"]
    CTX --- UMgr["undo_manager: UndoManager"]
    CTX --- TMon["task_monitor: TaskMonitor"]
    CTX --- SMgr["session_manager: SessionManager"]
    CTX --- UI["ui_callback: UICallback"]
    CTX --- IS["is_subagent: bool"]
```

Created per tool call in `ToolRegistry.execute_tool()`. Handlers extract the managers they need.

---

## 3. Context Compaction Pipeline

### Token Counting Strategy

```mermaid
graph TB
    subgraph Estimation["Token Estimation"]
        TK["tiktoken (cl100k_base)"]
        CH["Character estimate: len/4"]
    end

    subgraph Calibration["API Calibration"]
        API["response.usage.prompt_tokens"]
        DC["Delta counting for new messages"]
    end

    subgraph Budget["Token Budget"]
        MW["Model context_length"]
        MC["max_context = 80% of window"]
        TH["Threshold = 99% of max_context"]
    end

    TK -->|"initial estimate"| SC["should_compact()"]
    API -->|"calibrates"| SC
    DC -->|"incremental after calibration"| SC
    SC -->|"total > threshold?"| Trigger["Trigger Compaction"]

    MW --> MC --> TH --> Trigger
```

### Compaction Flow

```mermaid
flowchart LR
    SC["should_compact()"] -->|yes| Sanitize
    Sanitize["_sanitize_for_summarization()
    Replace tool results with summaries
    Truncate to 200 chars"] --> LLM

    LLM["LLM Summarize
    (compaction_prompt template)"] --> Assemble

    Assemble["head[0:1] + [summary_msg] + tail[-N:]
    N = min(5, max(2, len/3))"] --> Invalidate

    Invalidate["Reset API calibration
    _api_prompt_tokens = 0"]
```

**Key constants**:
- `COMPACTION_THRESHOLD = 0.99` - trigger at 99% of max_context
- `max_context = config.max_context_tokens` - defaults to 80% of model window (e.g., 100K for 128K models)
- `keep_recent = min(5, max(2, len(messages) // 3))` - preserve tail
- Sanitization: `result_summary` preferred, else truncate to 200 chars

---

## 4. Session & History Management

### SessionManager Architecture

```mermaid
flowchart TB
    subgraph Storage["Project-Scoped Storage"]
        direction TB
        PD["~/.opendev/projects/{encoded-path}/"]
        IDX["sessions-index.json"]
        SJ["{session_id}.json - metadata"]
        SL["{session_id}.jsonl - transcript"]
        LK["{session_id}.json.lock"]
        OL["operations.jsonl"]
    end

    subgraph Index["Self-Healing Index"]
        RI["_read_index()"]
        WI["_write_index() - atomic temp+rename"]
        RBI["rebuild_index() - glob .json files"]
        RI -->|corrupted/missing| RBI
        RBI --> WI
    end

    subgraph Lifecycle["Session Lifecycle"]
        CR["create_session()"] --> AM["add_message()"]
        AM -->|"turn_count % interval == 0"| SV["save_session()"]
        SV --> UI["_update_index_entry()"]
        LS["list_sessions()"] --> RI
        LO["load_session()"] --> FF["_load_from_file()"]
    end
```

**Key parameters**:
- `_INDEX_VERSION = 1`
- Lock timeout: **10.0 seconds** (fcntl exclusive lock)
- Auto-save interval: **5 turns** (configurable)
- Title length: **50 characters** max
- Session ID: **12-char hex** UUID

### Session Lifecycle Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant QP as QueryProcessor
    participant SM as SessionManager
    participant TD as TopicDetector
    participant FL as file_locks

    U->>QP: Input query
    QP->>SM: create_session(working_dir)
    SM-->>QP: Session(id=8char_hex)

    loop Every message
        QP->>SM: add_message(ChatMessage)
        SM->>SM: turn_count++
        alt turn_count % 5 == 0
            SM->>FL: exclusive_session_lock(timeout=10s)
            FL-->>SM: lock acquired
            SM->>SM: Write .json metadata
            SM->>SM: Rewrite .jsonl transcript
            SM->>SM: _update_index_entry()
            SM->>FL: release lock
        end
    end

    QP->>TD: detect(session_id, messages)
    TD->>TD: Spawn daemon thread
    TD->>TD: _call_llm(last 4 messages)
    Note right of TD: Cheap model (gpt-4o-mini)<br/>max_tokens=100, temp=0.0
    TD->>SM: set_title(session_id, title[:50])
```

### UndoManager

```mermaid
flowchart LR
    subgraph Operations["Operation Types"]
        FW["FILE_WRITE"]
        FE["FILE_EDIT"]
        FD["FILE_DELETE"]
        BE["BASH_EXECUTE"]
    end

    subgraph Stack["In-Memory Stack"]
        RO["record_operation()"]
        UL["undo_last()"]
        RO -->|"trim if > 50"| Stack2["history: list"]
        UL -->|"pop"| Stack2
    end

    subgraph Undo["Undo Actions"]
        UW["_undo_file_write: delete file"]
        UE["_undo_file_edit: restore backup"]
        UD["_undo_file_delete: restore backup"]
    end

    subgraph Persist["JSONL Persistence"]
        AP["_append_to_log()"]
        AP --> OJ["operations.jsonl"]
    end

    Operations --> RO --> AP
    UL --> Undo
```

**Capacity**: `max_history = 50` operations. JSONL append-only log (no locks needed).

---

## 5. Memory & Learning (ACE)

### ACE Learning Loop

```mermaid
flowchart TB
    TE["Tool Execution + Feedback"]
    TE --> REF["Reflector.reflect()"]

    REF --> RO["ReflectorOutput
    reasoning, error_id, root_cause,
    correct_approach, key_insight,
    bullet_tags: list of BulletTag"]

    RO --> BT["Apply BulletTags
    Tag each bullet: helpful / harmful / neutral"]

    BT --> CUR["Curator.curate()"]

    CUR --> CO["CuratorOutput
    DeltaBatch: reasoning + operations"]

    CO --> APD["Apply DeltaBatch"]

    subgraph DeltaOps["Delta Operations"]
        ADD["ADD: new bullet"]
        UPD["UPDATE: modify content"]
        TAG["TAG: mark effectiveness"]
        REM["REMOVE: delete bullet"]
    end

    APD --> DeltaOps --> PB["Playbook Mutation"]
    PB --> PERS["Persist in Session"]
    PERS -.->|"next query"| SP["Injected into System Prompt"]
```

### Playbook Data Model

```mermaid
graph LR
    subgraph Playbook
        B["Bullet"]
        B --- id["id: str (uuid4)"]
        B --- sec["section: str"]
        B --- con["content: str"]
        B --- eff["effectiveness: helpful/harmful/neutral"]
        B --- ca["created_at: ISO datetime"]
        B --- ua["updated_at: ISO datetime"]
    end

    subgraph Selection["BulletSelector Hybrid Scoring"]
        EF["effectiveness_score: 0.5 weight
        (helpful*1.0 + neutral*0.5 + harmful*0.0) / total"]
        RC["recency_score: 0.3 weight
        1.0 / (1.0 + days_old * 0.1)"]
        SE["semantic_score: 0.2 weight
        cosine_similarity normalized to 0-1"]

        EF --> FS["Final Score = weighted sum"]
        RC --> FS
        SE --> FS
    end
```

### Scoring Examples

| Age | Recency Score | Effectiveness (all helpful) | Semantic (0.8 cosine) | Final Score |
|-----|--------------|---------------------------|----------------------|-------------|
| 0 days | 1.00 | 1.00 | 0.90 | 0.98 |
| 7 days | 0.59 | 1.00 | 0.90 | 0.86 |
| 30 days | 0.25 | 0.50 | 0.70 | 0.57 |

### ConversationSummarizer

- **Incremental**: Only new messages since `last_summarized_index` are sent to LLM
- **Merge**: New summary merged with previous via prompt template
- **Trigger**: `regenerate_threshold = 5` new messages
- **Exclusion**: Last 6 messages always excluded (`exclude_last_n = 6`)
- **Max length**: 500 characters

### EmbeddingCache

- **Model**: `text-embedding-3-small` (default)
- **Cache key**: SHA256 of `"{model}:{text}"` (first 16 chars)
- **Persistence**: JSON file (in-memory + disk)
- **Batch optimization**: Single API call for all missing embeddings
- **Similarity**: `cosine_similarity()` with numpy vectorization

---

## 6. MCP Integration

### Connection Lifecycle

```mermaid
sequenceDiagram
    participant CLI as CLI Startup
    participant MGR as MCPManager
    participant EL as Background Event Loop
    participant LS as Language Server Process

    CLI->>MGR: MCPManager(working_dir)
    CLI->>MGR: connect_enabled_servers_background(callback)
    MGR->>EL: _ensure_event_loop()
    EL->>EL: Start daemon thread with asyncio loop

    par For each enabled server
        MGR->>EL: _connect_internal(server_name)
        EL->>EL: prepare_server_config (expand env vars)
        EL->>EL: _create_transport_from_config()
        EL->>LS: Client.__aenter__()
        LS-->>EL: Connected
        EL->>LS: client.list_tools()
        LS-->>EL: Tool schemas
        EL->>EL: Store in server_tools as mcp__{server}__{tool}
    end

    MGR-->>CLI: callback(results_dict)

    Note over CLI,LS: Tool Execution
    CLI->>MGR: call_tool_sync(server, tool, args)
    MGR->>EL: _call_tool_internal()

    loop Poll every 100ms
        MGR->>MGR: Check task_monitor.should_interrupt()
        MGR->>EL: Check future.done()
    end

    EL->>LS: client.call_tool(tool_name, args)
    LS-->>EL: Result
    EL-->>MGR: {success, output}
```

### MCP Architecture

```mermaid
graph TB
    subgraph Config["Configuration (Merge Strategy)"]
        GC["~/.opendev/mcp.json (global)"]
        PC[".mcp.json (project)"]
        GC -->|"merge"| MC["MCPConfig"]
        PC -->|"project wins"| MC
    end

    subgraph Transport["Transport Types"]
        NPX["NpxStdioTransport"]
        NODE["NodeStdioTransport"]
        PY["PythonStdioTransport"]
        UVX["UvxStdioTransport"]
        STDIO["StdioTransport (generic)"]
        HTTP["StreamableHttpTransport"]
        SSE["SSETransport"]
    end

    subgraph Manager["MCPManager Threading"]
        EL["Background Event Loop (daemon)"]
        SL["Per-Server Locks"]
        CL["clients: dict[name, Client]"]
        ST["server_tools: dict[name, list[schema]]"]
    end

    subgraph Discovery["Token-Efficient Discovery"]
        STH["SearchToolsHandler"]
        DIS["_discovered_mcp_tools: set"]
        STH -->|"vocabulary scoring"| DIS
        DIS -->|"only discovered in LLM context"| TR["ToolRegistry"]
    end

    MC --> Manager
    Manager --> Transport
    TR --> MHnd["McpToolHandler"]
    MHnd -->|"parse mcp__server__tool"| Manager
```

**Key constants**:
- Tool call timeout: **30 seconds**
- Poll interval: **100ms** (interrupt-responsive)
- Connection timeout: **60 seconds**
- Name format: `mcp__{server_name}__{tool_name}`

---

## 7. Retrieval & Context Assembly

### Context Assembly Pipeline

```mermaid
flowchart LR
    subgraph Input
        Q["User Query"]
        AT["@file references"]
    end

    subgraph Picker["ContextPicker.pick_context()"]
        direction TB
        P1["1. _pick_file_references()
        FileContentInjector parses @refs
        text + images"]

        P2["2. _pick_playbook_strategies()
        session.get_playbook()
        BulletSelector.select(max=30)"]

        P3["3. _assemble_system_prompt()
        agent.system_prompt + strategies"]

        P4["4. _pick_conversation_history()
        session.to_api_messages()"]

        P5["5. _create_query_piece()
        Enhanced query + metadata"]

        P6["6. _build_messages()
        Final API message list"]

        P1 --> P2 --> P3 --> P4 --> P5 --> P6
    end

    subgraph Output
        AC["AssembledContext
        system_prompt: str
        messages: list[dict]
        pieces: list[ContextPiece]
        image_blocks: list[dict]
        total_tokens_estimate: int"]
    end

    Q --> Picker
    AT --> Picker
    Picker --> AC
```

### ContextPiece Order & Categories

| Order | Category | Source |
|-------|----------|--------|
| 0 | `SYSTEM_PROMPT` | Agent system prompt + strategies |
| 5 | `PLAYBOOK_STRATEGY` | Selected playbook bullets |
| 10 | `FILE_REFERENCE` | @file text content |
| 15 | `IMAGE_CONTENT` | @file image blocks |
| 50 | `CONVERSATION_HISTORY` | Session messages |
| 100 | `USER_QUERY` | Current query |

### Supporting Components

**ContextTokenMonitor** - tiktoken-based counting with `cl100k_base` fallback. Methods: `count_tokens(text)`, `count_message_tokens(ChatMessage)`, `count_messages_total(list)`.

**CodebaseIndexer** - Generates OPENDEV.md summaries. Target: 3000 tokens. Sections: overview, structure (`tree -L 2`), key files, dependencies. Auto-compresses if over budget.

**EntityExtractor** - Regex patterns for 50+ file extensions. Extracts: `file_path`, `function`, `class`, `variable`, `action` entities from user input.

**ContextRetriever** - JIT context loading. Resolves file paths (direct then rglob), searches with ripgrep (fallback to grep). Returns up to 10 files with reasons.

**ContextTracer** - Logs all decisions. `export_trace()` writes JSON with timestamp, piece counts, and category breakdown.

---

## 8. Tool System Architecture

### Registry & Handler Wiring

```mermaid
graph TB
    subgraph Registry["ToolRegistry (Central Dispatcher)"]
        EX["execute_tool(name, args, **context)"]
    end

    subgraph Handlers["13 Handlers"]
        FTH["FileToolHandler"]
        PTH["ProcessToolHandler"]
        WTH["WebToolHandler"]
        WSH["WebSearchHandler"]
        NEH["NotebookEditHandler"]
        AUH["AskUserHandler"]
        SSH["ScreenshotToolHandler"]
        TDH2["TodoHandler"]
        THH2["ThinkingHandler"]
        CRH["CritiqueHandler"]
        BTH["BatchToolHandler"]
        MCH["McpToolHandler"]
        STSH["SearchToolsHandler"]
    end

    subgraph Implementations["18 Implementations"]
        FO["FileOperations"]
        WT["WriteTool"]
        ET["EditTool"]
        BT["BashTool"]
        WFT["WebFetchTool"]
        WST["WebSearchTool"]
        WSSr["WebScreenshotTool"]
        AUT["AskUserTool"]
        NET["NotebookEditTool"]
        OBT["OpenBrowserTool"]
        PDT["PDFTool"]
        VLT["VLMTool"]
        DPR["DiffPreview"]
        TCT["TaskCompleteTool"]
        PPT["PresentPlanTool"]
        BAT["BatchTool"]
        BASE["BaseTool (ABC)"]
        BGM["BackgroundTaskManager"]
    end

    EX --> FTH & PTH & WTH & WSH & NEH & AUH & SSH
    EX --> TDH2 & THH2 & CRH & BTH & MCH & STSH

    FTH --> FO & WT & ET
    PTH --> BT --> BGM
    WTH --> WFT
    WSH --> WST
    NEH --> NET
    AUH --> AUT
    BTH --> BAT
```

### Handler-to-Tool Mapping

| Tool Name | Handler | Implementation |
|-----------|---------|----------------|
| `read_file` | FileToolHandler | FileOperations.read_file |
| `write_file` | FileToolHandler | WriteTool.write_file |
| `edit_file` | FileToolHandler | EditTool.edit_file |
| `list_files` | FileToolHandler | FileOperations.list_directory |
| `search` | FileToolHandler | FileOperations.grep_files / ast_grep |
| `run_command` | ProcessToolHandler | BashTool.execute |
| `list_processes` | ProcessToolHandler | BashTool.list_processes |
| `get_process_output` | ProcessToolHandler | BashTool.get_process_output |
| `kill_process` | ProcessToolHandler | BashTool.kill_process |
| `fetch_url` | WebToolHandler | WebFetchTool.fetch_url |
| `web_search` | WebSearchHandler | WebSearchTool.search |
| `capture_web_screenshot` | (direct) | WebScreenshotTool |
| `capture_screenshot` | ScreenshotToolHandler | mss library |
| `ask_user` | AskUserHandler | AskUserTool.ask |
| `notebook_edit` | NotebookEditHandler | NotebookEditTool.edit_cell |
| `read_pdf` | (direct) | PDFTool.extract_text |
| `analyze_image` | (direct) | VLMTool.analyze_image |
| `open_browser` | (direct) | OpenBrowserTool |
| `write_todos` / `update_todo` / `complete_todo` | TodoHandler | (in-memory) |
| `think` | ThinkingHandler | 5 levels: OFF/LOW/MED/HIGH/SELF_CRITIQUE |
| `task_complete` | (direct) | TaskCompleteTool |
| `present_plan` | (direct) | PresentPlanTool |
| `batch_tool` | BatchToolHandler | BatchTool (parallel/serial) |
| `search_tools` | SearchToolsHandler | vocabulary scoring + discovery |
| `invoke_skill` | (direct) | SkillLoader.load_skill (dedup per session) |
| `spawn_subagent` | (direct) | SubAgentDeps injection |
| `mcp__*` | McpToolHandler | MCPManager.call_tool_sync |
| `find_symbol` / `rename_symbol` / ... | (lambda) | SymbolRetriever → LSP |

### Key Tool Patterns

**BashTool safety**: SAFE_COMMANDS whitelist, DANGEROUS_PATTERNS regex, server detection (15+ frameworks auto-backgrounded), output cap at 30K chars (10K head + 10K tail).

**FileToolHandler approval flow**: Check `mode_manager.needs_approval()` → `approval_manager.request_approval()` → if denied, return `{denied: True}`. Record operation for undo via `UndoManager`.

**BatchTool**: `MAX_PARALLEL_WORKERS = 5`. Two modes: parallel (ThreadPoolExecutor) or serial.

**Hook interception**: Every `execute_tool()` call passes through `HookManager` if configured. PreToolUse fires before handler dispatch (can block or modify arguments); PostToolUse/PostToolUseFailure fires asynchronously after handler returns.

**TodoHandler**: In-memory state. Only one todo in "doing" at a time. Flexible ID matching: numeric, slug, partial, fuzzy.

**BackgroundTaskManager**: PTY-based streaming to `/tmp/swe-cli/{hash}/tasks/{id}.output`. Non-blocking `select()` with 0.5s poll. Listener callbacks for status changes.

---

## 9. Symbol Tools & LSP

### Symbol Operations Flow

```mermaid
graph LR
    subgraph SymbolOps["6 Symbol Operations"]
        FS["find_symbol"]
        FRS["find_referencing_symbols"]
        IBS["insert_before_symbol"]
        IAS["insert_after_symbol"]
        RSB["replace_symbol_body"]
        RNS["rename_symbol"]
    end

    subgraph Core["Core Classes"]
        SR2["SymbolRetriever"]
        SYM["Symbol (dataclass)
        name, kind, file_path,
        start/end line/char,
        children, parent"]
        NPM["NamePathMatcher
        exact, partial, wildcard, glob"]
    end

    subgraph LSP2["LSP Layer"]
        LSPW["LSPServerWrapper (singleton)"]
        SLS["SolidLanguageServer (ABC)"]
        SLSH["SolidLanguageServerHandler
        JSON-RPC 2.0 over stdin/stdout"]
    end

    subgraph Servers["37 Language Servers"]
        PYR["Pyright (Python)"]
        TSS["typescript-language-server"]
        RA["rust-analyzer"]
        GPL["gopls (Go)"]
        JDT["eclipse-jdtls (Java)"]
        CLG["clangd (C/C++)"]
        MORE["... 31 more"]
    end

    SymbolOps --> SR2
    SR2 --> LSPW
    SR2 --> NPM
    LSPW --> SLS --> SLSH --> Servers
    SLS --> SYM
```

### Supported Languages

35+ languages via `Language` enum: Python, TypeScript, Rust, Go, Java, Kotlin, C#, PHP, Ruby, Dart, C/C++, Bash, Swift, Scala, Clojure, Elixir, Elm, Erlang, Haskell, Julia, Fortran, R, Perl, Lua, Nix, Zig, Terraform, YAML, Markdown, AL, Rego, and experimental variants.

Each server extends `SolidLanguageServer`:
- Auto-installs runtime dependencies (rustup, npm packages, etc.)
- Custom log level classification to suppress false-positive errors
- Language-specific ignore patterns (node_modules, vendor, __pycache__)
- Two-level caching: raw LSP responses + processed DocumentSymbols, content-hash invalidation

**SymbolKind**: 26 values matching LSP spec (FILE=1 through TYPEPARAMETER=26).

---

## 10. Integration & Data Flow

### End-to-End Query Lifecycle

```mermaid
sequenceDiagram
    participant U as User
    participant HM as HookManager
    participant QP as QueryProcessor
    participant QE as QueryEnhancer
    participant CP as ContextPicker
    participant VML as ValidatedMessageList
    participant CC as ContextCompactor
    participant RE as ReactExecutor
    participant AG as MainAgent
    participant TR as ToolRegistry
    participant SM as SessionManager
    participant ACE as Reflector + Curator
    participant TD as TopicDetector

    U->>QP: Input query

    rect rgb(255, 245, 245)
        Note over QP,HM: 1. Hook: UserPromptSubmit
        QP->>HM: run_hooks(UserPromptSubmit)
        alt Hook blocks
            HM-->>QP: blocked=True, reason
            QP-->>U: Query blocked
        end
    end

    rect rgb(240, 248, 255)
        Note over QP,QE: 2. Query Enhancement
        QP->>QE: enhance_query(query)
        QE->>QE: Parse @file references
        QE->>QE: FileContentInjector → text + images
        QE-->>QP: (enhanced_query, image_blocks)
    end

    rect rgb(255, 248, 240)
        Note over QP,CP: 3. Context Assembly
        QP->>CP: pick_context(query, agent)
        CP->>CP: _pick_file_references()
        CP->>CP: _pick_playbook_strategies(query, max=30)
        CP->>CP: _assemble_system_prompt() [includes skills index]
        CP->>CP: _build_messages()
        CP-->>QP: AssembledContext
    end

    rect rgb(240, 255, 240)
        Note over QP,VML: 4. Message Wrapping
        QP->>VML: ValidatedMessageList(messages)
        VML->>VML: Enforce pair invariants
    end

    rect rgb(255, 240, 255)
        Note over RE,CC: 5. Compaction Check
        RE->>CC: should_compact(messages, system_prompt)
        alt Exceeds 99% threshold
            CC->>HM: run_hooks(PreCompact, "auto")
            CC->>CC: compact() → head + summary + tail
            CC->>CC: Invalidate API calibration
        end
    end

    rect rgb(248, 248, 248)
        Note over RE,TR: 6. ReAct Loop (max 200 iterations)
        loop Each iteration
            RE->>AG: call_thinking_llm() [if thinking ON]
            AG-->>RE: thinking_trace

            RE->>AG: call_critique_llm() [if self-critique ON]
            AG-->>RE: critique

            RE->>AG: call_llm(messages, tools)
            AG-->>RE: {content, tool_calls, usage}

            RE->>CC: update_from_api_usage(prompt_tokens)

            alt Has tool_calls
                TR->>HM: run_hooks(PreToolUse, tool_name)
                alt Hook blocks
                    HM-->>TR: blocked=True
                    TR-->>RE: {success: false, denied: true}
                else Hook allows (may modify input)
                    RE->>TR: execute_tool(name, args, context)
                    TR-->>RE: {success, output}
                    TR->>HM: run_hooks_async(PostToolUse)
                end
                RE->>VML: append tool results
            else task_complete
                RE->>RE: Check incomplete todos
                RE->>HM: run_hooks(Stop)
                RE-->>U: Break loop
            end
        end
    end

    rect rgb(255, 255, 240)
        Note over RE,ACE: 7. Learning & Persistence
        RE->>SM: add_message(assistant_msg)
        RE->>ACE: record_tool_learnings()
        ACE->>ACE: Reflector → Curator → Playbook mutation
    end

    rect rgb(240, 255, 255)
        Note over RE,TD: 8. Background Title Update
        RE->>TD: detect(session_id, messages)
        TD->>TD: Daemon thread → cheap LLM → set_title()
    end
```

---

## 11. Skills System

### Skill Discovery & Loading

```mermaid
flowchart TB
    subgraph Discovery["Discovery (Priority Order)"]
        P1["1. Project: .opendev/skills/"]
        P2["2. User global: ~/.opendev/skills/"]
        P3["3. Project bundles: .opendev/plugins/bundles/*/skills/"]
        P4["4. User bundles: ~/.opendev/plugins/bundles/*/skills/"]
        P5["5. Built-in: swecli/skills/builtin/"]
        P1 --> P2 --> P3 --> P4 --> P5
    end

    subgraph Loading["SkillLoader"]
        DS["discover_skills()"]
        LS["load_skill(name)"]
        BI["build_skills_index()"]
        MC["_metadata_cache: dict"]
        SC["_cache: dict"]
    end

    subgraph Integration["System Integration"]
        TR["ToolRegistry._handle_invoke_skill()"]
        SP["SystemPromptBuilder._build_skills_index()"]
        DD["_invoked_skills: set (dedup)"]
    end

    Discovery -->|"directories"| DS
    DS -->|"populate"| MC
    LS -->|"lazy load"| SC
    TR --> LS
    TR --> DD
    SP --> BI
    BI --> MC
```

Skills are markdown files with YAML frontmatter providing on-demand knowledge injection into the agent's context.

### Skill File Format

```markdown
---
name: commit
description: Git commit best practices
namespace: default
---

# Skill content here (markdown)
```

**Frontmatter fields**: `name` (required, falls back to filename), `description` (required, defaults to "Skill: {name}"), `namespace` (optional, defaults to "default", used as prefix: `namespace:name`).

### Invoke Flow

1. **System prompt** includes an "Available Skills" index generated by `SkillLoader.build_skills_index()`, listing all discovered skills with names and descriptions
2. Agent calls `invoke_skill` tool with `skill_name`
3. `ToolRegistry._handle_invoke_skill()` checks `_invoked_skills` set for dedup
4. First invocation: loads full skill content via `SkillLoader.load_skill()`, adds to `_invoked_skills`, returns content
5. Second invocation of same skill: returns short reminder ("already loaded") to prevent context bloat
6. Agent follows skill instructions for the remainder of the conversation

### Initialization

`AgentFactory._initialize_skills()` runs at startup:
1. `ConfigManager.get_skill_dirs()` returns directories in priority order
2. Creates `SkillLoader(skill_dirs)`
3. `discover_skills()` populates the metadata cache (reads frontmatter only)
4. `tool_registry.set_skill_loader(loader)` wires the loader in

**Key classes**: `SkillMetadata` (name, description, namespace, path, source), `LoadedSkill` (metadata + stripped content), `SkillLoader` (discovery, loading, indexing, caching).

---

## 12. Hooks System

### Architecture

```mermaid
flowchart TB
    subgraph Config["Configuration (settings.json)"]
        GS["~/.opendev/settings.json (global)"]
        PS[".opendev/settings.json (project)"]
        GS -->|"merge"| LDR["loader.load_hooks_config()"]
        PS -->|"project appended"| LDR
        LDR --> HC["HookConfig (snapshot)"]
    end

    subgraph Models["Data Models"]
        HEV["HookEvent (10 events)"]
        HMT["HookMatcher (regex + commands)"]
        HCD["HookCommand (type, command, timeout)"]
        HC --> HMT --> HCD
    end

    subgraph Manager["HookManager (Orchestrator)"]
        RH["run_hooks(event, match_value, data)"]
        RHA["run_hooks_async(event, ...)"]
        BS["_build_stdin(event, ...)"]
        HF["has_hooks_for(event)"]
        TP["ThreadPoolExecutor(max_workers=2)"]
        RH --> BS
        RHA --> TP
    end

    subgraph Executor["HookCommandExecutor"]
        EX["execute(command, stdin_data)"]
        SP["subprocess.run(shell=True, input=json)"]
        EX --> SP
        SP --> HR["HookResult"]
    end

    subgraph Events["10 Hook Events"]
        E1["SessionStart (startup/resume/clear)"]
        E2["UserPromptSubmit"]
        E3["PreToolUse (tool name regex)"]
        E4["PostToolUse (tool name)"]
        E5["PostToolUseFailure (tool name)"]
        E6["SubagentStart (agent type)"]
        E7["SubagentStop (agent type)"]
        E8["Stop"]
        E9["PreCompact (manual/auto)"]
        E10["SessionEnd"]
    end

    HC --> Manager
    RH --> EX
    Events -.-> RH
```

Hooks let users define shell commands that fire at lifecycle events. Configured in `settings.json`, they receive JSON on stdin and communicate via exit codes (0=proceed, 2=block) and JSON on stdout.

### Config Format

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "run_command",
        "hooks": [
          { "type": "command", "command": ".opendev/hooks/block-rm.sh", "timeout": 60 }
        ]
      }
    ]
  }
}
```

**Merge strategy**: Project matchers are appended after global matchers for the same event. Global hooks fire first, then project hooks.

### Hook Protocol

The hook command receives JSON on stdin:

```json
{
  "session_id": "abc123",
  "cwd": "/path/to/project",
  "hook_event_name": "PreToolUse",
  "tool_name": "run_command",
  "tool_input": {"command": "rm -rf /tmp/test"}
}
```

The command communicates back via:
- **Exit code 0**: Proceed normally
- **Exit code 2**: Block the operation
- **JSON stdout** (optional): `permissionDecision`, `updatedInput`, `additionalContext`, `decision`, `reason`

### Integration Points

```mermaid
sequenceDiagram
    participant REPL as REPL
    participant QP as QueryProcessor
    participant RE as ReactExecutor
    participant TR as ToolRegistry
    participant SAM as SubAgentManager
    participant CC as ContextCompactor
    participant HM as HookManager

    Note over REPL,HM: Session Lifecycle
    REPL->>HM: SessionStart (startup/resume)
    REPL->>HM: SessionEnd (cleanup)

    Note over QP,HM: User Input
    QP->>HM: UserPromptSubmit (can block)

    Note over TR,HM: Tool Execution
    TR->>HM: PreToolUse (can block/modify input)
    TR->>HM: PostToolUse (async, fire-and-forget)
    TR->>HM: PostToolUseFailure (async)

    Note over RE,HM: Agent Lifecycle
    RE->>HM: Stop (after loop ends)

    Note over SAM,HM: Subagent Lifecycle
    SAM->>HM: SubagentStart (can block)
    SAM->>HM: SubagentStop (async)

    Note over CC,HM: Compaction
    CC->>HM: PreCompact (manual/auto)
```

### Key Design Decisions

- **Snapshot at startup**: `HookConfig` is loaded once when `HookManager` is created. Mid-session changes to settings.json are not reflected (prevents TOCTOU security issues)
- **Setter injection**: `set_hook_manager()` on ToolRegistry, QueryProcessor, ReactExecutor, SubAgentManager, ContextCompactor. If None, hooks are a no-op (zero overhead)
- **Short-circuit on block**: If any hook returns exit code 2, remaining hooks are skipped and the operation is denied immediately
- **Async for post-events**: PostToolUse, PostToolUseFailure, SubagentStop use fire-and-forget via `ThreadPoolExecutor(max_workers=2)` to avoid blocking the agent
- **Tool names use OpenDev names**: Matchers match against `run_command`, `write_file`, `edit_file`, etc. (not Claude Code names)

### Wiring Flow

`REPL._init_hooks()` runs at startup:
1. `load_hooks_config(working_dir)` reads and merges global + project settings
2. Creates `HookManager(config, session_id, cwd)`
3. Wires into: `tool_registry.set_hook_manager()`, `query_processor.set_hook_manager()`, `subagent_manager.set_hook_manager()`, `compactor.set_hook_manager()`

---

## Key Files Reference

| Subsystem | Source Files |
|-----------|-------------|
| **Root** | `compaction.py`, `validated_message_list.py`, `message_pair_validator.py`, `context.py` |
| **History** | `history/session_manager.py`, `history/topic_detector.py`, `history/undo_manager.py`, `history/file_locks.py` |
| **Memory / ACE** | `memory/playbook.py`, `memory/delta.py`, `memory/roles.py`, `memory/conversation_summarizer.py`, `memory/selector.py`, `memory/embeddings.py`, `memory/reflection/reflector.py` |
| **MCP** | `mcp/config.py`, `mcp/models.py`, `mcp/manager.py`, `mcp/handler.py` |
| **Retrieval** | `retrieval/token_monitor.py`, `retrieval/indexer.py`, `retrieval/retriever.py` |
| **Context Picker** | `context_picker/picker.py`, `context_picker/models.py`, `context_picker/tracer.py` |
| **Tool System** | `tools/registry.py`, `tools/context.py`, `tools/path_utils.py`, `tools/background_task_manager.py`, `tools/handlers/*` (13 files), `tools/implementations/*` (18 files) |
| **Symbol / LSP** | `tools/symbol_tools/*` (6 files), `tools/lsp/*` (10+ core files), `tools/lsp/language_servers/*` (37 files) |
| **Skills** | `../../core/skills.py` (SkillLoader, SkillMetadata, LoadedSkill), `../../skills/builtin/` |
| **Hooks** | `../../core/hooks/models.py`, `../../core/hooks/executor.py`, `../../core/hooks/manager.py`, `../../core/hooks/loader.py` |
| **Integration** | `../../repl/repl.py`, `../../repl/query_processor.py`, `../../repl/react_executor.py`, `../../repl/query_enhancer.py`, `../../repl/tool_executor.py` |

## Constants & Thresholds Summary

| Component | Constant | Value |
|-----------|----------|-------|
| ContextCompactor | COMPACTION_THRESHOLD | 0.99 (99%) |
| ContextCompactor | max_context default | 100,000 tokens |
| SessionManager | _INDEX_VERSION | 1 |
| SessionManager | Lock timeout | 10.0 seconds |
| SessionManager | Auto-save interval | 5 turns |
| SessionManager | Title max length | 50 chars |
| TopicDetector | _MAX_RECENT_MESSAGES | 4 |
| TopicDetector | LLM max_tokens | 100 |
| TopicDetector | LLM temperature | 0.0 |
| UndoManager | max_history | 50 operations |
| file_locks | Poll interval | 0.05 seconds |
| BulletSelector | effectiveness weight | 0.5 |
| BulletSelector | recency weight | 0.3 |
| BulletSelector | semantic weight | 0.2 |
| BulletSelector | Recency decay rate | 0.1 per day |
| ConversationSummarizer | regenerate_threshold | 5 messages |
| ConversationSummarizer | exclude_last_n | 6 messages |
| ConversationSummarizer | max_summary_length | 500 chars |
| ExecutionReflector | min_tool_calls | 2 |
| ExecutionReflector | min_confidence | 0.6 |
| MCPManager | Tool call timeout | 30 seconds |
| MCPManager | Poll interval | 100ms |
| MCPManager | Connection timeout | 60 seconds |
| CodebaseIndexer | target_tokens | 3,000 |
| ContextPicker | DEFAULT_MAX_STRATEGIES | 30 |
| ContextRetriever | max_files | 10 |
| BashTool | MAX_OUTPUT_CHARS | 30,000 |
| BashTool | IDLE_TIMEOUT | 60 seconds |
| BashTool | MAX_TIMEOUT | 600 seconds |
| BatchTool | MAX_PARALLEL_WORKERS | 5 |
| ReactExecutor | MAX_REACT_ITERATIONS | 200 |
| ValidatedMessageList | SYNTHETIC_TOOL_RESULT | Error placeholder |
| EmbeddingCache | Model | text-embedding-3-small |
| EmbeddingCache | Hash | SHA256[:16] |
| SkillLoader | Default namespace | "default" |
| SkillLoader | Namespace separator | `:` |
| SkillLoader | Dedup scope | Per session |
| HookCommand | Default timeout | 60 seconds |
| HookCommand | Max timeout | 600 seconds |
| HookManager | Async pool workers | 2 |
| HookManager | Block exit code | 2 |
| HookConfig | Config snapshot | At startup (immutable) |
