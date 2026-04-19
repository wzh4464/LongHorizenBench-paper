# REPL Command System Architecture

## Overview

The REPL command system handles slash commands (`/mode`, `/clear`, `/mcp`, etc.) that operate at the REPL level, outside the agent's reasoning loop. When user input starts with `/`, it is intercepted before query processing and dispatched to a registered CommandHandler. Commands provide direct control over session management, mode switching, model configuration, MCP server management, and other system operations that do not require LLM involvement.

## End-to-End Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          User Input                                       │
│                                                                           │
│  ┌────────────────────────────┐    ┌─────────────────────────────────┐   │
│  │ "/mode plan"               │    │ "fix the login bug"             │   │
│  │ "/mcp list"                │    │ "@src/auth.py explain this"     │   │
│  │ "/clear"                   │    │ (natural language queries)      │   │
│  └────────────┬───────────────┘    └──────────────┬──────────────────┘   │
│               │                                    │                      │
│          starts with "/"                    does not start with "/"       │
│               │                                    │                      │
└───────────────┼────────────────────────────────────┼──────────────────────┘
                │                                    │
                ▼                                    ▼
┌──────────────────────────────┐    ┌──────────────────────────────────────┐
│  REPL._handle_command()      │    │  QueryProcessor → Agent Loop         │
│                               │    │  (LLM reasoning, tool execution)     │
│  Split: cmd + args            │    └──────────────────────────────────────┘
│  Route to handler             │
│  Return CommandResult         │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       Command Handler Layer                               │
│                                                                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │ Session      │ │ Mode         │ │ MCP          │ │ Config       │   │
│  │ Commands     │ │ Commands     │ │ Commands     │ │ Commands     │   │
│  │ /clear       │ │ /mode        │ │ /mcp         │ │ /models      │   │
│  │ /compact     │ │              │ │ (11 subcmds) │ │              │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
│                                                                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │ Agents       │ │ Skills       │ │ Plugins      │ │ Tool         │   │
│  │ Commands     │ │ Commands     │ │ Commands     │ │ Commands     │   │
│  │ /agents      │ │ /skills      │ │ /plugins     │ │ /init        │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
│                                                                           │
│  ┌──────────────┐                                                        │
│  │ Help         │                                                        │
│  │ Command      │                                                        │
│  │ /help        │                                                        │
│  └──────────────┘                                                        │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

## CommandHandler Base Class

All command handlers extend the abstract CommandHandler base.

```
CommandHandler (ABC)
│
├── __init__(repl: REPL)
│   └── Stores reference to REPL for accessing managers
│
├── handle(args: str) → CommandResult        [abstract]
│   └── Each handler implements its own dispatch logic
│
├── print_command_header(command_name, params)
│   └── Formatted header: "━━━ /command params ━━━"
│
├── print_success(message)
│   └── Green "✓" prefix
│
├── print_error(message)
│   └── Red "✗" prefix
│
├── print_warning(message)
│   └── Yellow "⚠" prefix
│
├── print_info(message)
│   └── Blue "ℹ" prefix
│
├── print_line(message)
│   └── Indented continuation line
│
└── print_continuation(message)
    └── Double-indented continuation
```

### CommandResult

```
CommandResult (Dataclass)
│
├── success: bool           Whether the command completed successfully
├── message: Optional[str]  Human-readable result description
└── data: Optional[Any]     Structured data (for programmatic consumers)
```

## Command Registry

Commands are registered during REPL initialization in `_init_command_handlers()`.

| Command | Handler Class | Subcommands | Purpose |
|---------|---------------|-------------|---------|
| `/clear` | SessionCommands | - | Save current session and start fresh |
| `/compact` | SessionCommands | - | Manually trigger context compaction |
| `/mode` | ModeCommands | `plan`, `normal` | Switch between normal and plan mode |
| `/models` | ConfigCommands | - | Interactive model selector |
| `/mcp` | MCPCommands | `list`, `connect`, `disconnect`, `add`, `remove`, `enable`, `disable`, `tools`, `status`, `refresh`, `test` | MCP server management (11 subcommands) |
| `/init` | ToolCommands | - | Initialize codebase context |
| `/agents` | AgentsCommands | `list`, `create`, `delete`, `edit` | Custom agent management |
| `/skills` | SkillsCommands | `list`, `load`, `info` | Skills discovery and loading |
| `/plugins` | PluginsCommands | `list`, `install`, `remove`, `info` | Plugin marketplace |
| `/help` | HelpCommand | - | Display available commands |

## Argument Parsing

Commands use simple space-splitting for argument extraction.

```
_handle_command(command_string)
│
├── parts = command_string.split(maxsplit=1)
│   ├── parts[0] = "/mode"       ◄── command name
│   └── parts[1] = "plan"        ◄── remaining args (may be empty)
│
├── cmd = parts[0].lower()
├── args = parts[1] if len(parts) > 1 else ""
│
└── Route based on cmd string
```

For commands with subcommands (e.g., `/mcp`), the handler performs a second split:

```
MCPCommands.handle(args)
│
├── parts = args.split(maxsplit=1)
│   ├── parts[0] = "connect"     ◄── subcommand
│   └── parts[1] = "myserver"    ◄── subcommand args
│
├── subcmd = parts[0].lower()
│
└── Route: {"list": list_servers, "connect": connect, ...}[subcmd]()
```

## Dispatch Flow

```
REPL.start() main loop
│
├── Read user input via prompt_toolkit
│
├── user_input.startswith("/")?
│   │
│   YES ─────────────────────────────┐
│   │                                 │
│   ▼                                 │
│   _handle_command(user_input)       │
│   │                                 │
│   ├── Parse cmd + args              │
│   │                                 │
│   ├── cmd == "/clear"?              │
│   │   └── session_commands.clear()  │
│   │                                 │
│   ├── cmd == "/compact"?            │
│   │   └── session_commands.compact()│
│   │                                 │
│   ├── cmd == "/mode"?               │
│   │   └── mode_commands.handle(args)│
│   │                                 │
│   ├── cmd == "/models"?             │
│   │   └── config_commands.handle()  │
│   │                                 │
│   ├── cmd == "/mcp"?                │
│   │   └── mcp_commands.handle(args) │
│   │                                 │
│   ├── cmd == "/init"?               │
│   │   └── tool_commands.handle()    │
│   │                                 │
│   ├── cmd == "/agents"?             │
│   │   └── agents_commands.handle()  │
│   │                                 │
│   ├── cmd == "/skills"?             │
│   │   └── skills_commands.handle()  │
│   │                                 │
│   ├── cmd == "/plugins"?            │
│   │   └── plugins_commands.handle() │
│   │                                 │
│   ├── cmd == "/help"?               │
│   │   └── help_command.handle()     │
│   │                                 │
│   └── Unknown?                      │
│       └── "Unknown command" message │
│                                     │
│   NO ──────────────────────────────►│
│   │                                 │
│   ▼                                 │
│   _process_query(user_input)        │
│   └── QueryProcessor → Agent loop   │
│                                     │
└─────────────────────────────────────┘
```

## Command Examples

### /clear - Session Reset

```
SessionCommands.clear()
│
├── Get current session from session_manager
├── Save current session to disk
├── Create new session via session_manager.create_session()
├── print_success("Session cleared. Starting fresh.")
└── return CommandResult(success=True)
```

### /compact - Manual Compaction

```
SessionCommands.compact()
│
├── Get messages from current session
├── Validate message_count >= 5 (minimum for compaction)
├── Create ContextCompactor instance
├── compacted = compactor.compact(messages, system_prompt)
├── Store compaction metadata in session
├── print_success("Compacted {before} → {after} messages")
└── return CommandResult(success=True, data={"before": N, "after": M})
```

### /mode plan - Mode Switch

```
ModeCommands.switch_mode("plan")
│
├── Check mode_manager.current_mode
├── If already in PLAN mode:
│   └── print_warning("Already in plan mode")
├── Else:
│   ├── Set repl._pending_plan_request = True
│   └── print_success("Plan mode will activate on next query")
│
│   Next user query:
│   └── QueryProcessor detects plan_requested flag
│       └── Prepends plan mode context to messages
│       └── Agent enters planning loop
```

### /mcp connect - MCP Server Connection

```
MCPCommands.connect(server_name)
│
├── Check if server exists in MCP config
├── Check if already connected
├── mcp_manager.connect(server_name)
│   ├── Create transport (stdio/http/sse)
│   ├── Initialize FastMCP client
│   ├── Discover tools → server_tools[server_name]
│   └── Return tool count
├── Refresh runtime tooling (_refresh_runtime_tooling)
│   └── Update tool registry with new MCP tool schemas
├── print_success("Connected to {server_name} ({N} tools)")
└── return CommandResult(success=True)
```

## Integration Points

Commands interact with the agent system through several side-effect channels.

```
Command                     Side Effect
───────                     ───────────
/models                     Triggers repl.rebuild_agents()
                            → Recreates AgentFactory with new model config
                            → Rebuilds tool registry and system prompts

/mcp connect/disconnect     Triggers _refresh_runtime_tooling()
                            → Updates tool schemas available to agent
                            → Adds/removes MCP tools from registry

/mode plan/normal           Sets _pending_plan_request flag
                            → QueryProcessor reads flag on next query
                            → Agent switches reasoning mode

/clear                      Creates new session
                            → Agent starts with empty conversation history
                            → Old session preserved on disk

/compact                    Compresses conversation history
                            → Reduces token count for subsequent LLM calls
                            → Artifact index injected to preserve awareness

/agents create              Registers custom agent definition
                            → Available for spawn_subagent calls
```

## Command vs Agent Tool Distinction

Commands and agent tools serve different purposes and execute in different contexts.

```
                        Slash Commands              Agent Tools
                        ──────────────              ───────────
Trigger                 User types "/cmd"           LLM decides to call tool
Executor                REPL._handle_command()      ToolRegistry.execute_tool()
LLM involved?           No                          Yes (LLM chose the tool)
Hooks fired?            No                          Yes (PreToolUse, PostToolUse)
Approval required?      No                          Yes (based on autonomy level)
Undo tracked?           No                          Yes (UndoManager records ops)
Context                 REPL instance               RunContext with AgentDeps
Output                  CommandResult               Tool result dict → LLM
```

Commands are handled before the input reaches the query processor. If input starts with `/`, the agent loop is never entered for that input.

## Key Files Reference

| Component | File | Key Elements |
|-----------|------|--------------|
| Base class | `swecli/repl/commands/base.py` | CommandHandler, CommandResult |
| Session commands | `swecli/repl/commands/session_commands.py` | clear(), compact() |
| Mode commands | `swecli/repl/commands/mode_commands.py` | switch_mode() |
| MCP commands | `swecli/repl/commands/mcp_commands.py` | 11 subcommand methods |
| Config commands | `swecli/repl/commands/config_commands.py` | show_model_selector() |
| Agents commands | `swecli/repl/commands/agents_commands.py` | _create_agent(), _list_agents() |
| Skills commands | `swecli/repl/commands/skills_commands.py` | Skills management |
| Plugins commands | `swecli/repl/commands/plugins_commands.py` | Plugin marketplace |
| Tool commands | `swecli/repl/commands/tool_commands.py` | init_codebase() |
| Help command | `swecli/repl/commands/help_command.py` | Command listing |
| REPL dispatch | `swecli/repl/repl.py` | _handle_command(), _init_command_handlers() |
