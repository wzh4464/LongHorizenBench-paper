# Agent Delegation Flow

How the MainAgent decides when to act directly versus spawning a specialized subagent, and how those subagents are defined, compiled, executed, and returned.

---

## Overview

```
User Request
     │
     ▼
┌─────────────────────┐
│     MainAgent       │  ← Full tool access + spawn_subagent
│   (18-section       │
│   system prompt)    │
└─────────┬───────────┘
          │
    ┌─────▼──────┐
    │  Classify  │  ← LLM, not code: no hard-coded branching
    │   Task     │
    └─────┬──────┘
          │
    ┌─────┴──────────────────────────────┐
    │                                    │
    ▼                                    ▼
┌──────────────┐          ┌──────────────────────────┐
│ Direct Tool  │          │    spawn_subagent()       │
│ Execution    │          │                           │
│              │          │  Code-Explorer            │
│ read_file    │          │  Planner                  │
│ edit_file    │          │  Project-Init             │
│ write_file   │          │  ask-user                 │
│ search       │          │  + custom agents          │
│ run_command  │          │                           │
│ fetch_url    │          │                           │
│ …            │          │                           │
│              │          │                           │
└──────┬───────┘          └──────────┬────────────────┘
       │                             │
       ▼                             ▼
┌──────────────┐          ┌──────────────────────────┐
│  Response    │          │ Result returned to        │
│  to User     │          │ MainAgent (single string) │
└──────────────┘          └──────────┬────────────────┘
                                     │
                                     ▼
                          ┌──────────────────────────┐
                          │  MainAgent synthesizes   │
                          │  and responds to user    │
                          └──────────────────────────┘
```

No code branch controls this routing - the MainAgent's system prompt describes when to delegate. The LLM reasons about whether direct tool use or delegation is more appropriate for each turn.

---

## Direct Tool Use vs. Delegation

| Scenario | Approach | Reason |
|----------|----------|--------|
| Read a specific file | **Direct** (`read_file`) | Known path, one tool call |
| Search for a symbol | **Direct** (`search`) | Targeted needle query |
| Edit a known location | **Direct** (`edit_file`) | One-shot write |
| Run a single command | **Direct** (`run_command`) | Single step |
| Green-field creative task | **Direct** | No codebase to explore |
| "Where is error handling?" | **Delegation** (`Code-Explorer`) | Requires broad search |
| "What's the architecture?" | **Delegation** (`Code-Explorer`) | Needs systematic exploration |
| Plan implementing feature X | **Delegation** (`Planner`) | Multi-step analysis + plan doc |
| "What approach should we take?" | **Delegation** (`ask-user`) | Structured clarification needed |

---

## The `spawn_subagent` Tool

The single entry point for all delegation. Its schema is built dynamically from the registered subagent list so the LLM always sees exactly which types are available.

**Source**: `swecli/core/agents/subagents/task_tool.py`

```python
spawn_subagent(
    description:      str,   # 3–5 word summary (required)
    prompt:           str,   # Full task with all context (required)
    subagent_type:    enum,  # One of the registered names (required)
    model:            enum,  # Optional: "haiku" | "sonnet" | "opus"
    run_in_background: bool, # Optional: fire-and-forget (default: False)
    resume:           str,   # Optional: agent_id to continue a session
)
```

### Four design constants

1. **Context isolation.** Subagents have no access to conversation history. Every fact they need must be in the `prompt` argument. This keeps subagents focused and prevents context leakage between concerns.

2. **Single opaque result.** The MainAgent sees only the subagent's final output string - never intermediate tool calls or reasoning traces. This keeps the orchestrator's context window clean when combining multiple subagent results.

3. **Model selection.** Callers can select a cheaper/faster model (`haiku` for quick lookups) or a more capable one (`opus` for complex reasoning). If unspecified, the subagent inherits the parent's model.

4. **Resumability.** Passing `resume` with a prior `agent_id` continues that subagent's session with full history intact, enabling multi-turn delegation without re-explaining context.

---

## Subagent Registry

All subagents are `SubAgentSpec` typed dictionaries collected in `ALL_SUBAGENTS`.

**Sources**: `swecli/core/agents/subagents/specs.py`, `swecli/core/agents/subagents/agents/`

### SubAgentSpec

```python
class SubAgentSpec(TypedDict):
    name:               str                         # Unique identifier
    description:        str                         # Used in spawn_subagent enum description
    system_prompt:      str                         # Loaded from templates/subagents/*.md
    tools:              NotRequired[list[str]]       # Restricted tool set; inherits all if absent
    model:              NotRequired[str]             # Model override
    docker_config:      NotRequired[DockerConfig]   # Optional sandboxed execution
    copy_back_recursive: NotRequired[bool]          # Copy workspace from Docker on completion
```

### Built-in subagents

| Name | Tools | Purpose |
|------|-------|---------|
| **Code-Explorer** | `read_file`, `search`, `list_files`, `find_symbol`, `find_referencing_symbols` | Read-only local codebase exploration. Cannot modify anything. |
| **Planner** | `PLANNING_TOOLS` + `write_file`, `edit_file` | Explores codebase and writes an implementation plan to a file. |
| **Project-Init** | `read_file`, `search`, `list_files`, `run_command`, `write_file` | Analyzes codebase and generates the `OPENDEV.md` project instruction file. |
| **ask-user** | *(none)* | Gathers user input via structured multiple-choice prompts. Zero tools - the manager detects `_builtin_type: "ask-user"` and routes execution to the UI layer instead of the ReAct loop. The `prompt` must be a JSON string with `questions` / `options` structure. |

### Tool restriction philosophy

Each subagent receives the **minimum viable tool set** for its job:

- **Read-only subagents** (`Code-Explorer`): no `write_file`, `edit_file`, or `run_command`. Cannot modify the codebase by construction.
- **Plan-then-write subagents** (`Planner`): write access is limited to the plan file. Unrestricted read access for exploration.
- **Zero-tool subagents** (`ask-user`): no tools. Rather than running the ReAct loop, the `SubAgentManager` detects the `_builtin_type: "ask-user"` marker and hands off to the UI layer directly. Note the distinction: `ask-user` is a *subagent* (spawned via `spawn_subagent`). There is a *separate* `ask_user` *tool* that some subagents (e.g., `Planner`) include in their tool set, which lets them pause mid-task and ask the user a question.

**Excluded from all subagents**: Todo tools (`write_todos`, `update_todo`, `complete_todo`). Only the MainAgent coordinates task tracking. Subagents focus purely on execution.

### Filtering is at schema level

The `allowed_tools` list is passed to `ToolSchemaBuilder` at compile time. The LLM never sees tool schemas it cannot use - so it cannot attempt to call a tool that was filtered out. This is stricter and more token-efficient than runtime permission checks.

### PLANNING_TOOLS

```python
PLANNING_TOOLS = {
    "read_file", "list_files", "search",
    "fetch_url", "web_search",
    "list_processes", "get_process_output",
    "read_pdf",
    "find_symbol", "find_referencing_symbols",
    "search_tools",    # MCP tool discovery
    "spawn_subagent",  # Planner can nest Code-Explorer calls
    "ask_user",        # Can solicit clarification
    "task_complete",   # Must be able to signal done
}
```

`spawn_subagent` is included: the Planner can spawn Code-Explorer subagents to parallelize its own exploration.

---

## Subagent Lifecycle

### 1. Registration (startup)

```
ALL_SUBAGENTS
    │  (SubAgentSpec list)
    ▼
SubAgentManager.register_defaults()
    │  for each spec:
    ▼
SubAgentManager.register_subagent(spec)
    │
    ├─ MainAgent(allowed_tools=spec["tools"], ...)
    │     └─ agent._subagent_system_prompt = spec["system_prompt"]
    │
    └─ CompiledSubAgent(name, description, agent, tool_names)
         stored in _agents dict
```

Subagents are `MainAgent` instances with a restricted `allowed_tools` list and an overridden system prompt. There is no separate agent class - one ReAct loop implementation covers both orchestrator and delegates.

**Source**: `swecli/core/agents/subagents/manager.py`

### 2. Spawning

```
MainAgent calls spawn_subagent(type, prompt, …)
    │
    ▼
ToolRegistry.execute_tool("spawn_subagent", args)
    │
    ▼
SubAgentManager.execute(name, task, deps, …)
    │
    ├─ Look up CompiledSubAgent by name
    ├─ CompiledSubAgent.agent.run_sync(prompt, deps)
    │       └─ Same ReAct loop: think → tool calls → observe → repeat
    └─ format_task_result(result, subagent_type) → str
```

### 3. Result injection

The formatted result string is injected as a tool-result message in the MainAgent's conversation. The MainAgent then synthesizes subagent findings into its response to the user. Subagent results are not presented to the user directly - the orchestrator always mediates.

```python
# Completion status prepended to keep the MainAgent informed
if completion_status:
    tool_result = f"[completion_status={completion_status}]\n{tool_result}"
```

### 4. Cleanup

Subagents are ephemeral. No state is retained after a result is returned unless the caller saves the returned `agent_id` for a future `resume` call.

---

## Parallel Execution

### Detection

The `ReactExecutor` inspects each LLM response for multiple `spawn_subagent` calls:

```python
# swecli/repl/react_executor.py
spawn_calls = [tc for tc in tool_calls if tc["function"]["name"] == "spawn_subagent"]
is_parallel_agents = len(spawn_calls) == len(tool_calls) and len(spawn_calls) > 1
```

Parallelism requires all `spawn_subagent` calls to appear **in the same LLM response**. Sequential responses always execute sequentially - this is an inherent constraint of the ReAct loop.

### Execution

```
MainAgent response: N spawn_subagent calls in one response
    │
    ├──→ Thread 1: Code-Explorer ("find auth patterns")
    ├──→ Thread 2: Code-Explorer ("find database patterns")
    └──→ Thread 3: Code-Explorer ("find API patterns")
         │
         ▼ (as_completed - all required)
    Results collected by tool_call_id
         │
         ▼
    MainAgent synthesizes all results into one unified response
```

**Source**: `swecli/repl/react_executor.py:1487–1529`

### UI callbacks for parallel tracking

```
on_parallel_agents_start(agent_infos)       ← list of {agent_type, description, tool_call_id}
on_parallel_agent_complete(tool_call_id, success)
on_parallel_agents_done()
```

The TUI uses these to render a live multi-agent progress panel.

### Result synthesis instructions

The system prompt instructs the MainAgent to:
- **Merge** overlapping findings, eliminate redundancy
- **Synthesize** all results into a single response organized by topic
- **Never** summarize agents separately (e.g., "Agent 1 found…, Agent 2 found…")

---

## Custom Agents

Beyond the built-ins, users can define custom agents at two scopes.

### Definition formats

**JSON** (`~/.opendev/agents.json` or `<project>/.opendev/agents.json`):

```json
[
  {
    "name": "MyAgent",
    "description": "Does specialized work",
    "tools": ["read_file", "search", "run_command"],
    "skillPath": "~/.opendev/skills/my-agent-prompt.md",
    "model": "haiku"
  }
]
```

**Markdown** (`~/.opendev/agents/*.md` or `<project>/.opendev/agents/*.md`):  
File content becomes the system prompt directly. YAML frontmatter can specify `tools` and `model`.

### Three-tier precedence

| Priority | Source | Location |
|----------|--------|----------|
| 1 (highest) | Built-in | Hardcoded in `ALL_SUBAGENTS` |
| 2 | User-global | `~/.opendev/agents/` |
| 3 | Project-local | `<project>/.opendev/agents/` |

A custom agent with the same name as a built-in is silently skipped - built-ins take priority.

### Tool specification

```python
tools: list[str]             # Explicit: only these tools
tools: "*"                   # Wildcard: all available tools
tools: {"exclude": [...]}    # All tools except excluded ones
```

**Source**: `swecli/core/agents/subagents/manager.py:263–326`

---

## Optional: Docker Sandboxing

Subagents can execute inside Docker containers when their `SubAgentSpec` includes a `docker_config`:

```
spawn_subagent(type="Sandboxed-Agent", …)
    │
    ├─ Docker container started; workspace mounted
    ├─ Input files (PDFs, docs referenced in task) copied via docker cp
    ├─ Subagent runs inside container
    └─ Results (+ optionally full workspace) copied back to host
```

This gives filesystem isolation: the subagent cannot modify the host filesystem directly. If Docker is unavailable (`shutil.which("docker") is None`), execution falls back to local mode transparently.

---

## Optional: Background Execution

```
spawn_subagent(type="Code-Explorer", prompt="…", run_in_background=true)
    │
    ▼   immediate response
{ task_id: "abc123" }
    │
    ▼   MainAgent continues other work
…
    │
    ▼   later
get_subagent_output(task_id="abc123")
    │
    ▼
Result from completed subagent
```

Enables the MainAgent to fire off long-running tasks and poll for results rather than blocking.

---

## Relationship to Agent Modes

| Mode | MainAgent tool access | Delegation |
|------|----------------------|------------|
| **Normal** | All tools + `spawn_subagent` | Any subagent |
| **Plan** | `PLANNING_TOOLS` only | `Planner` is the primary target; write tools blocked at registry |
| **Thinking** | No tools | No delegation possible |

Mode controls which tools appear in the MainAgent's schema, which directly controls what the LLM can call - including `spawn_subagent` itself.

---

## Key Source Files

| File | Responsibility |
|------|----------------|
| `swecli/core/agents/subagents/task_tool.py` | `spawn_subagent` schema + result formatting |
| `swecli/core/agents/subagents/manager.py` | Registration, compilation, execution, custom agents, Docker |
| `swecli/core/agents/subagents/specs.py` | `SubAgentSpec` and `CompiledSubAgent` type definitions |
| `swecli/core/agents/subagents/agents/__init__.py` | `ALL_SUBAGENTS` registry |
| `swecli/core/agents/subagents/agents/*.py` | Individual subagent specs |
| `swecli/core/agents/components/schemas/planning_builder.py` | `PLANNING_TOOLS` set |
| `swecli/core/agents/prompts/templates/subagents/*.md` | Subagent system prompts |
| `swecli/core/agents/prompts/templates/system/main/main-subagent-guide.md` | Delegation guidance in MainAgent's system prompt |
| `swecli/repl/react_executor.py` | Parallel subagent detection + `ThreadPoolExecutor` dispatch |
| `swecli/core/agents/main_agent.py` | `MainAgent.run_sync()` - the ReAct loop |

---

## Design Decisions

### Why subagents reuse MainAgent

Subagents are `MainAgent` instances with `allowed_tools` + overridden system prompt - not a separate class. One ReAct loop to maintain; bug fixes apply everywhere. Subagents can also use the same approval system, UndoManager, and context compaction code. The cost (carrying unused MainAgent methods) is negligible compared to maintaining a parallel class hierarchy.

### Why filtering is at schema level - not execution time

The LLM cannot attempt to call a tool it doesn't see in its schema. No hallucinated tool calls to reject, no error handling for "tool not available", and fewer tokens spent serializing irrelevant schemas.

### Why subagent results are opaque

The MainAgent receives only the final text output, not intermediate tool calls or reasoning traces. This keeps the orchestrator's context window uncluttered when synthesizing multiple subagent results, and prevents the MainAgent from drowning in subagent exploration paths it cannot steer. Trade-off: the MainAgent cannot course-correct a subagent mid-execution. If the result is incomplete, it must re-spawn.

### Why parallel execution requires same-response batching

The ReAct loop generates a response, executes tools, appends results, then generates the next response. There is no mechanism for the LLM to queue work across responses. Same-response batching is therefore the only parallelism primitive. The system prompt makes this explicit: *"To run subagents concurrently, make multiple spawn_subagent calls in the SAME response."*
