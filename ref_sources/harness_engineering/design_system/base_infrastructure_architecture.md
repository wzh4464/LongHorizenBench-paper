# Base Infrastructure Architecture

## Overview

The base infrastructure defines the interface contracts, abstract base classes, factory patterns, and core data models that the entire system builds upon. Protocol interfaces provide runtime-checkable contracts that decouple consumers from concrete implementations. Abstract base classes offer shared behavior for agents, tools, and managers. Factory classes wire dependencies at startup. Core data models define the shapes of messages, sessions, operations, and configuration that flow through every layer.

## Layered Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    Protocol Interfaces (Runtime-Checkable)                 │
│                                                                           │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐                │
│  │ Agent       │ │ Tool         │ │ ToolRegistry      │                │
│  │ Interface   │ │ Interface    │ │ Interface         │                │
│  └──────┬──────┘ └──────┬───────┘ └────────┬──────────┘                │
│         │               │                   │                            │
│  ┌──────────────────┐ ┌──────────────────┐ ┌────────────────────┐      │
│  │ ConfigManager   │ │ SessionManager   │ │ ApprovalManager    │      │
│  │ Interface       │ │ Interface        │ │ Interface          │      │
│  └──────┬──────────┘ └──────┬───────────┘ └────────┬───────────┘      │
│         │                    │                       │                   │
└─────────┼────────────────────┼───────────────────────┼───────────────────┘
          │                    │                       │
          ▼                    ▼                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    Abstract Base Classes                                   │
│                                                                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │ BaseAgent    │ │ BaseTool     │ │ BaseManager  │ │ BaseMonitor  │  │
│  │              │ │              │ │              │ │              │  │
│  │ build_       │ │ name         │ │ _log()       │ │ start()      │  │
│  │ system_      │ │ description  │ │              │ │ stop()       │  │
│  │ prompt()     │ │ run()        │ │              │ │ is_running() │  │
│  │ build_tool_  │ │              │ │              │ │              │  │
│  │ schemas()    │ │              │ │              │ │              │  │
│  │ call_llm()   │ │              │ │              │ │              │  │
│  │ run_sync()   │ │              │ │              │ │              │  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘  │
│         │                │                │                │            │
└─────────┼────────────────┼────────────────┼────────────────┼────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    Factory Layer                                          │
│                                                                           │
│  ┌─────────────────────────────┐  ┌──────────────────────────────────┐  │
│  │ AgentFactory                │  │ ToolFactory                      │  │
│  │                              │  │                                  │  │
│  │ create_agents() → AgentSuite │  │ create_registry() → ToolRegistry │  │
│  │   ├── normal: AgentInterface │  │   ├── File handlers              │  │
│  │   ├── subagent_manager       │  │   ├── Process handlers           │  │
│  │   └── skill_loader           │  │   ├── Web handlers               │  │
│  └─────────────────────────────┘  │   ├── MCP handlers                │  │
│                                    │   └── Symbol tool handlers        │  │
│                                    └──────────────────────────────────┘  │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
          │                │
          ▼                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                   Concrete Implementations                                │
│                                                                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │ MainAgent    │ │ ToolRegistry │ │ ConfigManager│ │ SessionManager│  │
│  │ PlanningAgent│ │              │ │              │ │              │  │
│  │ (subagents)  │ │              │ │              │ │              │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘  │
│                                                                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                    │
│  │ Approval     │ │ UndoManager  │ │ ModeManager  │                    │
│  │ Manager      │ │              │ │              │                    │
│  └──────────────┘ └──────────────┘ └──────────────┘                    │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

## Abstract Base Classes

### BaseAgent

Foundation for all agents that orchestrate LLM calls.

```
BaseAgent (ABC)
│
├── __init__(config: AppConfig, tool_registry: ToolRegistryInterface | None,
│            mode_manager: ModeManager)
│
├── Properties:
│   ├── config: AppConfig
│   ├── tool_registry: ToolRegistryInterface | None
│   ├── mode_manager: ModeManager
│   ├── system_prompt: str            (cached from build_system_prompt)
│   └── tool_schemas: Sequence[dict]  (cached from build_tool_schemas)
│
├── @abstractmethod build_system_prompt() → str
│   └── Assemble system prompt from template sections
│
├── @abstractmethod build_tool_schemas() → Sequence[dict]
│   └── Collect tool definitions for LLM function calling
│
├── refresh_tools() → None
│   └── Rebuilds tool_schemas and system_prompt caches
│
├── @abstractmethod call_llm(messages, task_monitor) → Response
│   └── Make HTTP call to LLM provider
│
└── @abstractmethod run_sync(message, deps, ui_callback) → Response
    └── Run full ReAct loop synchronously
```

### BaseTool

Minimal contract for executable tools.

```
BaseTool (ABC)
│
├── name: str           Tool identifier
├── description: str    Human-readable description
│
└── @abstractmethod run(**kwargs) → dict[str, Any]
    └── Execute tool with given arguments, return structured result
```

### BaseManager

Shared foundation for managers with console-aware logging.

```
BaseManager (ABC)
│
├── __init__(console: Any | None = None)
│
└── _log(message: str) → None
    └── Emit to Rich Console if available, otherwise no-op
```

### BaseMonitor

Interface for monitoring utilities.

```
BaseMonitor (ABC)
│
├── @abstractmethod start(description, **kwargs) → None
├── @abstractmethod stop() → dict[str, Any]
└── @abstractmethod is_running() → bool
```

## Protocol Interfaces

All protocols use `@runtime_checkable` for isinstance() checks at runtime.

### AgentInterface

```
AgentInterface (Protocol)
│
├── system_prompt: str
├── tool_schemas: Sequence[dict]
│
├── refresh_tools() → None
├── call_llm(messages, task_monitor) → Response
└── run_sync(message, deps) → Response
```

### ToolInterface and ToolRegistryInterface

```
ToolInterface (Protocol)
│
├── name: str
├── description: str
└── run(**kwargs) → dict[str, Any]


ToolRegistryInterface (Protocol)
│
├── get_schemas() → Sequence[dict]
│
└── execute_tool(tool_name, arguments,
│                mode_manager, approval_manager,
│                undo_manager) → dict[str, Any]
```

### Manager Interfaces

```
ConfigManagerInterface (Protocol)
│
├── working_dir: Path
├── load_config() → AppConfig
├── get_config() → AppConfig
├── save_config(config, global_config) → None
├── ensure_directories() → None
└── load_context_files() → list[str]


SessionManagerInterface (Protocol)
│
├── session_dir: Path
├── create_session(working_directory) → Session
├── load_session(session_id) → Session
├── save_session(session) → None
├── add_message(message, auto_save_interval) → None
├── list_sessions() → Sequence[SessionMetadata]
├── delete_session(session_id) → None
└── get_current_session() → Session | None


ApprovalManagerInterface (Protocol)
│
├── auto_approve_remaining: bool
├── request_approval(operation, preview, command, working_dir) → ApprovalResult
└── reset_auto_approve() → None
```

## Factory Patterns

### AgentFactory

Creates a complete agent suite from configuration and shared dependencies.

```
AgentFactory
│
├── __init__(config, tool_registry, mode_manager, working_dir,
│            enable_subagents, config_manager, env_context)
│
├── create_agents() → AgentSuite
│   │
│   ├── Create MainAgent(config, tool_registry, mode_manager)
│   │   └── Full tool access, ReAct loop with max iterations
│   │
│   ├── If enable_subagents:
│   │   ├── Create SubAgentManager(config, mode_manager)
│   │   │   └── Manages subagent specs, tool filtering, execution
│   │   │
│   │   └── Register custom agents from .opendev/agents/
│   │       └── _register_custom_agents()
│   │
│   ├── _initialize_skills()
│   │   └── SkillLoader(built-in + user + project skill dirs)
│   │
│   └── Return AgentSuite(
│         normal=main_agent,
│         subagent_manager=subagent_manager,
│         skill_loader=skill_loader
│       )
│
└── refresh_tools(suite) → None
    └── suite.normal.refresh_tools()


AgentSuite (Dataclass)
│
├── normal: AgentInterface          Main conversation agent
├── subagent_manager: SubAgentManager | None
└── skill_loader: SkillLoader | None
```

### ToolFactory

Creates a ToolRegistry wired with all handler dependencies.

```
ToolFactory
│
├── __init__(dependencies: ToolDependencies)
│
└── create_registry(mcp_manager) → ToolRegistry


ToolDependencies (Dataclass)
│
├── file_ops: Any            File operations handler
├── write_tool: Any          Write file implementation
├── edit_tool: Any           Edit file implementation
├── bash_tool: Any           Bash execution implementation
├── web_fetch_tool: Any      Web fetch implementation
├── web_search_tool: Any | None
├── notebook_edit_tool: Any | None
├── ask_user_tool: Any | None
├── open_browser_tool: Any | None
├── vlm_tool: Any | None
└── web_screenshot_tool: Any | None
```

## Dependency Injection

### AgentDependencies

The central bundle of runtime services injected into tools via RunContext.

```
AgentDependencies (Pydantic BaseModel)
│
├── mode_manager: Any          ModeManager instance
├── approval_manager: Any      ApprovalManager instance
├── undo_manager: Any          UndoManager instance
├── session_manager: Any       SessionManager instance
├── working_dir: Path          Current project directory
├── console: Any               Rich Console for output
└── config: Any                AppConfig instance


Injection Flow:

REPL / WebExecutor
│
├── Create AgentDependencies(
│     mode_manager=mode_manager,
│     approval_manager=approval_manager,
│     undo_manager=undo_manager,
│     session_manager=session_manager,
│     working_dir=working_dir,
│     console=console,
│     config=config
│   )
│
├── agent.run_sync(message, deps=agent_deps)
│   │
│   └── Internally: RunContext[AgentDependencies]
│       │
│       └── Passed to every tool call:
│
│           @tool
│           async def bash_tool(ctx: RunContext[AgentDependencies]):
│               deps = ctx.deps
│               approval = deps.approval_manager.request_approval(...)
│               deps.undo_manager.record_operation(...)
│               deps.session_manager.add_message(...)
```

All dependency fields use `Any` type to avoid circular imports between the models and runtime packages.

## Core Data Models

### ChatMessage

```
ChatMessage (Pydantic BaseModel)
│
├── role: Role                        "user" | "assistant" | "system"
├── content: str                      Message text
├── timestamp: datetime               When created
├── metadata: dict[str, Any]          Arbitrary metadata
├── tool_calls: list[ToolCall]        Tool invocations in this message
├── tokens: Optional[int]             Token count
│
├── thinking_trace: Optional[str]     Extended thinking content
├── reasoning_content: Optional[str]  Native model reasoning (o1/o3)
├── token_usage: Optional[dict]       Detailed token statistics
│
├── provenance: Optional[InputProvenance]   Message origin tracking
│
└── token_estimate() → int            Rough estimate based on content length
```

### ToolCall

```
ToolCall (Pydantic BaseModel)
│
├── id: str                           Unique tool call ID
├── name: str                         Tool name (e.g., "read_file")
├── parameters: dict[str, Any]        Tool arguments
├── result: Optional[Any]             Tool output
├── result_summary: Optional[str]     Concise 1-2 line summary
├── timestamp: datetime
├── approved: bool                    Whether user approved
├── error: Optional[str]
└── nested_tool_calls: list[ToolCall] Tool calls made by subagents
```

### Session

```
Session (Pydantic BaseModel)
│
├── id: str                           12-char hex ID
├── created_at: datetime
├── updated_at: datetime
├── messages: list[ChatMessage]
├── context_files: list[str]          Files referenced via @mention
├── working_directory: Optional[str]
├── metadata: dict[str, Any]          Holds "title", "summary", "tags"
├── playbook: Optional[dict]          ACE Playbook state
├── file_changes: list[FileChange]    File operations this session
│
├── Multi-channel fields:
│   ├── channel: str = "cli"
│   ├── chat_type: str = "direct"
│   ├── channel_user_id: str = ""
│   ├── thread_id: Optional[str]
│   ├── delivery_context: dict
│   ├── last_activity: Optional[datetime]
│   └── workspace_confirmed: bool = False
│
├── get_playbook() → Playbook
├── update_playbook(playbook) → None
├── add_message(message) → None
├── add_file_change(file_change) → None
├── get_file_changes_summary() → dict
├── total_tokens() → int
├── get_metadata() → SessionMetadata
└── to_api_messages(window_size) → list[dict]
```

### Operation

```
OperationType (Enum)
│  FILE_WRITE, FILE_EDIT, FILE_DELETE, BASH_EXECUTE

OperationStatus (Enum)
│  PENDING, APPROVED, EXECUTING, SUCCESS, FAILED, CANCELLED

Operation (Pydantic BaseModel)
│
├── id: str                           Timestamp-based ID
├── type: OperationType
├── status: OperationStatus = PENDING
├── target: str                       File path or command
├── parameters: dict[str, Any]        Operation-specific params
├── created_at: datetime
├── started_at: Optional[datetime]
├── completed_at: Optional[datetime]
├── approved: bool = False
├── error: Optional[str]
│
├── mark_executing() → None           Set status + started_at
├── mark_success() → None             Set status + completed_at
└── mark_failed(error) → None         Set status + error + completed_at
```

### FileChange

```
FileChangeType (Enum)
│  CREATED, MODIFIED, DELETED, RENAMED

FileChange (Pydantic BaseModel)
│
├── id: str                           8-char hex ID
├── type: FileChangeType
├── file_path: str
├── old_path: Optional[str]           For renames
├── timestamp: datetime
├── lines_added: int = 0
├── lines_removed: int = 0
├── tool_call_id: Optional[str]       Linked tool call
├── session_id: Optional[str]
├── description: Optional[str]
│
├── from_tool_result(tool_name, tool_args, tool_result, session_id) → FileChange
├── get_file_icon() → str
├── get_status_color() → str
└── get_change_summary() → str
```

### InputProvenance

```
InputProvenance (Pydantic BaseModel)
│
├── kind: str              "external_user" | "forwarded" | "system"
├── source_channel: str    Channel the message arrived from
└── source_session_id: Optional[str]   If forwarded from another session
```

## Configuration Hierarchy

```
Priority (highest to lowest):

┌──────────────────────────────────────┐
│ Environment Variables                 │  OPENAI_API_KEY, ANTHROPIC_API_KEY,
│ (override everything)                 │  FIREWORKS_API_KEY, etc.
└──────────────────┬───────────────────┘
                   │
┌──────────────────┴───────────────────┐
│ Local Project Config                  │  .opendev/settings.json
│ (project-specific overrides)          │  (in working directory)
└──────────────────┬───────────────────┘
                   │
┌──────────────────┴───────────────────┐
│ Global User Config                    │  ~/.opendev/settings.json
│ (user-wide defaults)                  │  (in home directory)
└──────────────────┬───────────────────┘
                   │
┌──────────────────┴───────────────────┐
│ AppConfig Defaults                    │  Hard-coded in AppConfig class
│ (last resort fallbacks)               │  definition (config.py)
└──────────────────────────────────────┘


ConfigManager.load_config():
│
├── Load global: ~/.opendev/settings.json → global_data
├── Load local: .opendev/settings.json → local_data
├── Merge: {**defaults, **global_data, **local_data}
├── Normalize fireworks model names (if applicable)
└── Return AppConfig(**merged_data)
```

## Multi-Model System

The system supports multiple specialized models, each with an independent provider.

```
AppConfig Model Fields:

┌────────────────────┬──────────────────────┬──────────────────────────────┐
│ Model Field        │ Provider Field        │ Purpose                      │
├────────────────────┼──────────────────────┼──────────────────────────────┤
│ model              │ model_provider        │ General-purpose (main agent) │
│ model_thinking     │ model_thinking_       │ Extended reasoning (optional)│
│                    │ provider              │                              │
│ model_vlm          │ model_vlm_provider    │ Vision/multimodal (optional) │
│ model_critique     │ model_critique_       │ Self-critique (optional)     │
│                    │ provider              │                              │
│ model_compact      │ model_compact_        │ Context compression          │
│                    │ provider              │ (optional)                   │
└────────────────────┴──────────────────────┴──────────────────────────────┘

Resolution Methods:
├── get_model_info()           → ModelInfo for main model
├── get_thinking_model_info()  → (provider, model, info) or falls back to main
├── get_vlm_model_info()       → (provider, model, info) or None
├── get_critique_model_info()  → (provider, model, info) or None
└── get_compact_model_info()   → (provider, model, info) or None
```

Each model type can use a different provider. The main model might use Fireworks while the thinking model uses Anthropic and the VLM uses OpenAI. If a specialized model is not configured, the system falls back to the main model where applicable.

## Runtime Service Contracts

### ModeManager

```
ModeManager
│
├── OperationMode (Enum): NORMAL | PLAN
│
├── current_mode: OperationMode
├── is_plan_mode: bool
│
├── set_mode(mode) → None
├── is_approval_required(operation_type, is_dangerous) → bool
├── needs_approval(operation) → bool
├── record_operation() → None
├── get_operation_count() → int
├── get_mode_indicator() → str       "[NORMAL]" or "[PLAN]"
├── get_mode_description() → str
│
└── Internal state:
    ├── _pending_plan: Optional[str]
    ├── _plan_steps: list[str]
    ├── _plan_goal: Optional[str]
    └── _operation_count: int
```

### ApprovalManager

```
ApprovalManager
│
├── auto_approve_remaining: bool
├── approved_patterns: set[str]
│
├── request_approval(operation, preview, command, working_dir) → ApprovalResult
│   │
│   ├── If auto_approve_remaining → return approved
│   ├── If pattern matches approved_patterns → return approved
│   └── Show interactive menu → return user choice
│
└── reset_auto_approve() → None


ApprovalResult (Dataclass)
│
├── approved: bool
├── choice: ApprovalChoice    APPROVE | APPROVE_ALL | DENY | EDIT | QUIT
├── edited_content: Optional[str]
├── apply_to_all: bool
└── cancelled: bool
```

### UndoManager

```
UndoManager
│
├── max_history: int = 50
├── history: list[Operation]
│
├── record_operation(operation) → None
│   ├── Append to in-memory history
│   ├── Trim to max_history
│   └── Append to JSONL log on disk
│
├── undo_last() → UndoResult
│   └── Pop last operation, reverse it
│
├── undo_operation(operation) → UndoResult
│   ├── FILE_WRITE → delete created file
│   ├── FILE_EDIT → restore from backup_path
│   └── FILE_DELETE → restore from backup_path
│
└── load_operations(session_dir) → list[dict]
    └── Read persistent JSONL log


UndoResult (Dataclass)
│
├── success: bool
├── operation_id: str
└── error: Optional[str]
```

## Key Files Reference

| Component | File | Key Elements |
|-----------|------|--------------|
| Abstract bases | `swecli/core/base/abstract/` | BaseAgent, BaseTool, BaseManager, BaseMonitor |
| Interfaces | `swecli/core/base/interfaces/` | AgentInterface, ToolInterface, ToolRegistryInterface, ConfigManagerInterface, SessionManagerInterface, ApprovalManagerInterface |
| Agent factory | `swecli/core/base/factories/agent_factory.py` | AgentFactory, AgentSuite |
| Tool factory | `swecli/core/base/factories/tool_factory.py` | ToolFactory, ToolDependencies |
| Dependencies | `swecli/models/agent_deps.py` | AgentDependencies |
| Config model | `swecli/models/config.py` | AppConfig (multi-model fields) |
| Session model | `swecli/models/session.py` | Session, SessionMetadata |
| Message model | `swecli/models/message.py` | ChatMessage, ToolCall, InputProvenance |
| Operation model | `swecli/models/operation.py` | Operation, OperationType, OperationStatus |
| File change model | `swecli/models/file_change.py` | FileChange, FileChangeType |
| Mode manager | `swecli/core/runtime/mode_manager.py` | ModeManager, OperationMode |
| Config manager | `swecli/core/runtime/config.py` | ConfigManager, load/merge/save |
| Approval manager | `swecli/core/runtime/approval/manager.py` | ApprovalManager, ApprovalResult |
| Undo manager | `swecli/core/context_engineering/history/undo_manager.py` | UndoManager, UndoResult |
