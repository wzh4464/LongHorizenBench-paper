# Agent Scaffolding Architecture

**Version**: 1.0
**Last Updated**: 2026-03-04

How agents are constructed, wired, and composed at startup - the build-time architecture that precedes the runtime ReAct loop documented in `02_agent_system.md`.

---

## Construction Pipeline

```
                         ┌─────────────────────────────────────────────────────────┐
                         │                    AgentFactory                         │
                         │  (config, tool_registry, mode_manager, env_context)     │
                         └──────────────────────┬──────────────────────────────────┘
                                                │
                      ┌─────────────────────────┼────────────────────────┐
                      │                         │                        │
                      ▼                         ▼                        ▼
              SkillLoader              SubAgentManager              MainAgent
          (discover skills          (register_defaults()       (config, registry,
           from 3 dirs)              + custom agents)          mode_mgr, env_ctx)
                      │                         │                        │
                      │                    ┌────┴────┐                   │
                      │                    │ for each │                   │
                      │                    │   spec   │                   │
                      │                    └────┬────┘                   │
                      │                         │                        │
                      │                         ▼                        │
                      │               MainAgent(allowed_tools)           │
                      │               + _subagent_system_prompt          │
                      │                         │                        │
                      └─────────────────────────┼────────────────────────┘
                                                │
                                                ▼
                                           AgentSuite
                                     (normal, subagent_manager,
                                          skill_loader)

     ╔══════════════════════════════════════════════════════════════════════╗
     ║  BaseAgent.__init__() eager-builds on construction:                 ║
     ║    self.system_prompt = self.build_system_prompt()                  ║
     ║    self.tool_schemas  = self.build_tool_schemas()                   ║
     ║                                                                    ║
     ║  MainAgent.build_system_prompt() delegates to:                     ║
     ║    SystemPromptBuilder → PromptComposer (priority-sorted sections) ║
     ║      + environment context + project instructions + MCP + skills   ║
     ║                                                                    ║
     ║  MainAgent.build_tool_schemas() delegates to:                      ║
     ║    ToolSchemaBuilder(registry, allowed_tools)                       ║
     ║      → _BUILTIN_TOOL_SCHEMAS (filtered) + MCP schemas + task tool  ║
     ╚══════════════════════════════════════════════════════════════════════╝
```

---

## 1. Foundation

### BaseAgent ABC

`swecli/core/base/abstract/base_agent.py`

The abstract base class that every agent inherits from. It accepts three constructor arguments - `config`, `tool_registry`, `mode_manager` - and eagerly calls two abstract methods during `__init__`:

- `build_system_prompt() → str` - assemble the system prompt
- `build_tool_schemas() → Sequence[Mapping]` - return OpenAI-format tool schemas

Two additional abstract methods define runtime behavior:

- `call_llm(messages, task_monitor) → Response` - execute a single LLM call
- `run_sync(message, deps, ui_callback) → Response` - run a full ReAct loop

A concrete `refresh_tools()` method re-invokes both build methods when the tool registry changes (e.g., after MCP discovery or skill loading).

The eager-build pattern means that by the time `__init__` returns, the agent is fully ready to serve requests - no lazy prompt assembly.

### AgentInterface Protocol

`swecli/core/base/interfaces/agent_interface.py`

A `@runtime_checkable` Protocol requiring:

- `system_prompt: str`
- `tool_schemas: Sequence[Mapping]`
- `refresh_tools() → None`
- `call_llm(messages, task_monitor) → Response`
- `run_sync(message, deps) → Response`

This protocol is what `AgentSuite.normal` is typed against, decoupling the factory from the concrete `MainAgent` class.

### Single Concrete Agent

There is no separate `PlanningAgent` class. Plan mode is implemented as a Planner subagent (a `MainAgent` instance with restricted tools and a planning-specific system prompt). The main agent and every subagent are instances of the same `MainAgent` class - differentiated only by:

- `allowed_tools` - which tools appear in their schemas
- `_subagent_system_prompt` - an override prompt set after construction
- `is_subagent` - a boolean flag derived from `allowed_tools is not None`

---

## 2. Construction Pipeline

### AgentFactory

`swecli/core/base/factories/agent_factory.py`

The factory is the single entry point for agent construction. It accepts:

- `config: AppConfig` - model, API keys, temperature, max_tokens
- `tool_registry: ToolRegistryInterface` - shared tool dispatch layer
- `mode_manager: ModeManager` - normal/plan mode state
- `working_dir` - filesystem root for file tools
- `enable_subagents: bool` - whether to create the SubAgentManager
- `config_manager: ConfigManager` - for skill dirs and custom agent config files
- `env_context: EnvironmentContext` - git status, OS, shell info for prompt

`create_agents()` executes three steps in order:

1. **Skills** - `_initialize_skills()` discovers skills from three directories (builtin `swecli/skills/builtin/`, user `~/.opendev/skills/`, project `.opendev/skills/`) and registers the `SkillLoader` with the tool registry
2. **Subagents** - creates `SubAgentManager`, calls `register_defaults()` (8 builtin specs), calls `_register_custom_agents()` (from config files), and registers the manager with the tool registry via `set_subagent_manager()`
3. **Main agent** - constructs a `MainAgent` with no tool filtering (full access)

Returns an `AgentSuite` dataclass bundling `normal`, `subagent_manager`, and `skill_loader`.

### MainAgent Construction

`swecli/core/agents/main_agent.py:131-167`

MainAgent's `__init__` does the following before calling `super().__init__()`:

- Sets 4 HTTP client slots to `None` (lazy initialization for normal, thinking, critique, VLM providers)
- Creates a `ResponseCleaner` for stripping markdown artifacts from LLM output
- Creates a `ToolSchemaBuilder(tool_registry, allowed_tools)` for schema generation
- Sets `is_subagent = allowed_tools is not None`
- Creates a bounded `Queue(maxsize=10)` for live message injection (Web UI follow-ups)

HTTP clients are properties with lazy initialization - the API key is not validated until the first LLM call. This allows construction to succeed even when credentials are not yet configured.

### Prompt Assembly

`swecli/core/agents/components/prompts/builders.py`

`SystemPromptBuilder.build()` composes the system prompt in two layers:

**Modular layer** - delegates to `PromptComposer`:
- Each section is a markdown file in `templates/system/main/`
- Sections are registered with a name, file path, priority (lower = earlier), and an optional condition function
- At compose time, sections are filtered by condition, sorted by priority, loaded, and concatenated
- Sections marked `cacheable=False` (scratchpad, reminders) go into a separate dynamic part for Anthropic prompt caching

**Dynamic layer** - appended after the modular prompt:
- Environment context (OS, shell, git branch, working directory)
- Project instructions (CLAUDE.md, .opendev/AGENTS.md)
- Skills index (discovered skill names and descriptions)
- MCP tool descriptions (from connected MCP servers)

Priority bands for the 16+ default sections:

- **10–30**: Core identity - mode awareness (12), security policy (15), tone/style (20), no-time-estimates (25)
- **40–50**: Interaction - interaction pattern (40), available tools (45), tool selection (50)
- **55–65**: Code quality - code quality (55), action safety (56), read-before-edit (58), error recovery (60), subagent guide (65)
- **70–80**: Conditional - git workflow (70, requires `in_git_repo`), task tracking (75, requires `todo_tracking_enabled`), provider-specific (80, keyed on `model_provider`)
- **85–95**: Context - output awareness (85), scratchpad (87, dynamic), code references (90), reminders note (95, dynamic)

### Tool Schema Assembly

`swecli/core/agents/components/schemas/normal_builder.py`

`ToolSchemaBuilder.build()`:

1. Deep-copies `_BUILTIN_TOOL_SCHEMAS` (the static schema definitions)
2. If `allowed_tools` is set, filters to only those names
3. Appends the `spawn_subagent` tool schema (built dynamically from registered agent descriptions) if not filtered out
4. Appends MCP tool schemas from the registry

This is why subagents see a restricted tool palette - the same `ToolSchemaBuilder` with a non-None `allowed_tools` list excludes schemas for tools the subagent should not use.

---

## 3. Subagent Scaffolding

### SubAgentSpec

`swecli/core/agents/subagents/specs.py`

A `TypedDict` defining a subagent blueprint:

- `name: str` - unique identifier (e.g., "code-explorer")
- `description: str` - shown in the `spawn_subagent` tool description
- `system_prompt: str` - the full system prompt override
- `tools: NotRequired[list[str]]` - tool allowlist; omit for all tools
- `model: NotRequired[str]` - model override (e.g., cheaper model for simple tasks)
- `docker_config: NotRequired[DockerConfig]` - optional containerized execution
- `copy_back_recursive: NotRequired[bool]` - copy workspace from Docker after completion

### Registration Flow

`SubAgentManager.register_subagent(spec)` at `manager.py:140-169`:

1. Resolves the tool list - `spec.get("tools", self._all_tool_names)` where `_all_tool_names` is a hardcoded list of 15 safe tools (excludes todo tools)
2. Creates an `AppConfig` copy with model override if `spec["model"]` is set
3. Constructs a `MainAgent(config, registry, mode_manager, working_dir, allowed_tools=tool_names, env_context)`
4. Sets `agent._subagent_system_prompt = spec["system_prompt"]` - this override is checked during `run_sync` to mark the agent as a subagent for approval purposes
5. Stores a `CompiledSubAgent(name, description, agent, tool_names)` in `self._agents`

### 8 Builtin Subagents

Defined in `swecli/core/agents/subagents/agents/`:

- **ask-user** - special: bypasses LLM entirely, shows interactive UI panel for user questions
- **code-explorer** - read-only tools (`read_file`, `search`, `list_files`), codebase investigation
- **planner** - read-only tools + `present_plan`, implements Plan mode as a subagent
- **pr-reviewer** - PR review with read + search + `run_command` (for git diff)
- **project-init** - full tool access for scaffolding new projects
- **security-reviewer** - security audit with read + search tools
- **web-clone** - full tools + Docker config for cloning web pages
- **web-generator** - full tools + Docker config for generating web apps

Each is a Python file exporting a `SubAgentSpec` dict. `ALL_SUBAGENTS` in `__init__.py` collects them for `register_defaults()`.

### Custom Agents

Custom agents are loaded from config files by `AgentFactory._register_custom_agents()` → `ConfigManager.load_custom_agents()` → `SubAgentManager.register_custom_agents()`. They follow the same `SubAgentSpec` schema and go through the same `register_subagent()` path.

Agent sources are tracked via `AgentSource` enum: `BUILTIN`, `USER_GLOBAL`, `PROJECT`.

### spawn_subagent Tool

The main agent delegates to subagents via the `spawn_subagent` tool. The tool description is dynamically built from all registered agent configs (`SubAgentManager.build_task_tool_description()`), listing each agent's name and description.

Execution flow:

1. Tool registry receives `spawn_subagent` call with `agent_type` and `task`
2. Registry calls `SubAgentManager.execute_subagent(name, task, deps)`
3. Manager retrieves the pre-compiled agent, creates `SubAgentDeps` (lightweight variant)
4. Calls `agent.run_sync(task, deps, message_history=None)` - fresh context, no conversation history
5. Returns the result to the main agent's ReAct loop as a tool result

Subagent isolation: each execution gets `message_history=None`, so subagents have no knowledge of the parent conversation. They operate on their task description alone.

---

## 4. Dependency Injection

### AgentDependencies

`swecli/models/agent_deps.py`

A Pydantic `BaseModel` carrying the runtime services that tools need:

- `mode_manager: ModeManager` - current operation mode (normal/plan)
- `approval_manager: ApprovalManager` - handles tool approval prompts
- `undo_manager: UndoManager` - tracks operations for undo/rollback
- `session_manager: SessionManager` - conversation persistence
- `working_dir: Path` - filesystem root
- `console: Console` - Rich console for TUI output
- `config: AppConfig` - runtime configuration

### Flow

```
REPL / Web UI
     │
     │  constructs AgentDependencies with all managers
     │
     ▼
agent.run_sync(message, deps=agent_deps)
     │
     │  ReAct loop executes tool calls:
     │
     ▼
tool_registry.execute_tool(
    tool_name, tool_args,
    mode_manager=deps.mode_manager,
    approval_manager=deps.approval_manager,
    undo_manager=deps.undo_manager,
    task_monitor=task_monitor,
    is_subagent=is_subagent,
    ui_callback=ui_callback,
)
```

Individual managers are unpacked from `deps` and passed as keyword arguments to `execute_tool`. This keeps the tool registry interface flat - it does not depend on the `AgentDependencies` model directly.

### SubAgentDeps

`swecli/core/agents/subagents/manager.py:65-70`

A lightweight `@dataclass` with only three fields:

- `mode_manager`
- `approval_manager`
- `undo_manager`

Subagents do not get `session_manager` (their messages are not persisted), `console` (output goes through `ui_callback`), or `config` (they have their own config from construction).

---

## Key Design Decisions

- **Single agent class**: MainAgent is the only concrete agent. Behavioral variation comes from construction parameters (allowed_tools, system_prompt override), not class hierarchies. This avoids the diamond problem and keeps the codebase simple.

- **Eager prompt build**: System prompts and tool schemas are built in `BaseAgent.__init__`. This means construction is slightly heavier, but every agent is immediately ready to serve - no "first call" latency or initialization races.

- **Lazy HTTP clients**: In contrast to eager prompts, HTTP clients are lazily initialized on first LLM call. This allows agents to be constructed before API keys are validated, supporting offline config flows and test environments.

- **Composition over inheritance for prompts**: PromptComposer assembles prompts from independent markdown sections rather than string interpolation in code. Adding a new section means adding a file and a `register_section()` call - no modification to the builder.

- **Subagents are cheap**: A subagent is just a MainAgent with filtered tools and an overridden prompt. Construction is fast because it reuses the same tool registry (no cloning). Isolation comes from `message_history=None` at execution time.

- **Factory as coordination point**: AgentFactory is the single place where skills, subagents, and the main agent are wired together. The REPL and Web UI both go through `AgentFactory.create_agents()`, ensuring consistent setup.
