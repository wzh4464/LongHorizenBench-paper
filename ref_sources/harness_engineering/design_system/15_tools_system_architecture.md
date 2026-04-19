# Tools System Architecture

## Architecture Diagram

```mermaid
graph TD
    subgraph Agent Runtime
        LLM[LLM Engine]
        SchemaBldr[ToolSchemaBuilder]
    end

    subgraph Tool Registry & Dispatch
        Registry[ToolRegistry]
        Context[ToolExecutionContext]
    end

    subgraph Tool Handlers
        FileH[FileToolHandler]
        ProcH[ProcessToolHandler]
        WebH[WebToolHandler]
        TaskH[Task Complete/Subagents]
        MCPH[McpToolHandler]
        MoreH[Additional Handlers...]
    end

    subgraph External Dependencies
        FileOps[FileOperations]
        Bash[BashRunner]
        WebClient[WebClient]
        MCPManager[MCP Manager]
        SubAgentMgr[SubAgentManager]
    end

    %% Schema Building
    Defs[_BUILTIN_TOOL_SCHEMAS] -.->|Provides static schemas| SchemaBldr
    MCPManager -.->|Provides discovered MCP schemas| SchemaBldr
    SubAgentMgr -.->|Provides task schemas| SchemaBldr
    SchemaBldr -->|Injects schemas into prompt| LLM

    %% Execution Flow
    LLM -->|Tool Call (e.g., edit_file)| Registry
    Registry -.->|Validates pre-hooks| Context
    Registry -->|Dispatches by name| FileH
    Registry -->|Dispatches by name| ProcH
    Registry -->|Dispatches by name| MCPH
    
    FileH -->|Executes logic| FileOps
    ProcH -->|Executes logic| Bash
    MCPH -->|Executes logic| MCPManager
    
    FileH -.->|Records Undo / Plan Approvals| Context
    
    FileOps -->|Returns Result| FileH
    FileH -->|Returns Dict| Registry
    Registry -->|Returns Tool Result| LLM
```

## Overview
The SWE-CLI Tools System provides the agent with its interactive capabilities while maintaining strict separation of concerns between definition, registration, validation, and execution. The system dynamically loads schemas so the LLM is aware of available tools, and safely delegates execution to specific modular handlers.

## Core Abstractions

### 1. ToolSchemaBuilder (`swecli/core/agents/components/schemas/`)
Responsible for dynamically assembling the JSON schemas injected into the LLM prompt.
- Loads fixed built-in tool definitions (like `write_file`, `search`) from `_BUILTIN_TOOL_SCHEMAS`.
- Loads markdown-based tool descriptions via `load_tool_description()`.
- Dynamically injects **discovered MCP tool schemas**. To save context tokens, MCP tools are only listed if the agent actively "discovers" them via the `search_tools` utility.
- Appends task schemas (like `spawn_subagent`) if the `SubAgentManager` is present.

### 2. ToolRegistry (`swecli/core/context_engineering/tools/registry.py`)
Acts as the main dispatcher for tool executions.
- Initializes all modular **Tool Handlers** upon startup.
- Maintains a mapping `_handlers` of tool names (e.g., `"write_file"`) to specific handler functions (e.g., `_file_handler.write_file`).
- Wraps execution in safety checks, including triggering `PreToolUse` and `PostToolUse` lifecycle hooks to intercept, modify, or block actions.

### 3. Tool Handlers (`swecli/core/context_engineering/tools/handlers/`)
Modular classes that encapsulate the business logic of grouping tools together.
- **`FileToolHandler`**: Groups `write_file`, `edit_file`, `read_file`, `list_files`, and `search`. Depends on the `FileOperations` dependency.
- **`ProcessToolHandler`**: Groups `run_command`, `list_processes`, formatting outputs via the `bash_tool` dependency.
- **`McpToolHandler`**: Routes `mcp__*` tools to the standalone `MCPManager`.
- **`WebToolHandler`, `TodoHandler`, `ThinkingHandler`**, etc. each handle their specific subsets of actions.

### 4. ToolExecutionContext
During execution, handlers receive a `ToolExecutionContext` object which wraps system dependencies such as:
- `mode_manager`: Needed to verify if the tool requires plan approval before running.
- `approval_manager`: Manages synchronous and asynchronous safety popups to the user.
- `undo_manager`: Tracks modifications so destructive file actions can be reverted via the timeline.
- `session_manager`: Records tool actions natively into the active session ledger (e.g., `FileChange` structures).

## Integration Flow
1. **Startup**: The CLI initializes the dependencies (FileOps, Managers) and creates the `ToolRegistry`.
2. **Schema Generation**: `ToolSchemaBuilder` is called to bake tool capabilities into the LLM context limits based on the current context constraints.
3. **LLM Output Generation**: The LLM chooses to execute a tool and emits the structured JSON call.
4. **Execution Delegation**: The Agent runtime forwards the JSON call to `ToolRegistry.execute_tool()`.
5. **Business Logic & Safety**: The assigned `ToolHandler` runs safety checks via the `approval_manager` context. If approved, it calls the underlying file/web/process API and passes back a `dict` result representing the success or failure of the action.
