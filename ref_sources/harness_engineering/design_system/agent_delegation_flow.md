# Agent Delegation Flow

**Version**: 1.0
**Last Updated**: 2026-02-25

---

## Overview

The agent delegation flow describes how the main agent decides when to handle tasks directly using its own tools versus delegating work to specialized subagents. This is a critical architectural decision that affects latency, context efficiency, accuracy, and the agent's ability to parallelize independent work streams.

OpenDev implements a **hub-and-spoke subagent architecture**: a single MainAgent acts as the orchestrator, dynamically spawning ephemeral subagents via the `spawn_subagent` tool. Each subagent runs in an isolated context with a restricted tool set and a purpose-built system prompt, then returns a single result to the orchestrator.

---

## Decision Flow

```
User Request
    │
    ▼
┌─────────────────────┐
│     MainAgent       │
│  (Full tool access) │
└─────────┬───────────┘
          │
    ┌─────▼──────┐
    │  Classify  │
    │   Task     │
    └─────┬──────┘
          │
    ┌─────┴──────────────────────────┐
    │                                │
    ▼                                ▼
┌──────────────┐          ┌──────────────────────┐
│ Direct Tool  │          │  spawn_subagent()    │
│ Execution    │          │  (Delegation)         │
│              │          │                       │
│ read_file    │          │  ┌─────────────────┐  │
│ edit_file    │          │  │ Code-Explorer   │  │
│ write_file   │          │  │ Planner         │  │
│ search       │          │  │ Security-Review │  │
│ list_files   │          │  │ PR-Reviewer     │  │
│ run_command  │          │  │ Web-Generator   │  │
│ fetch_url    │          │  │ Web-clone       │  │
│ ...          │          │  │ Project-Init    │  │
│              │          │  │ ask-user        │  │
│              │          │  │ Custom agents   │  │
│              │          │  └─────────────────┘  │
└──────┬───────┘          └──────────┬────────────┘
       │                             │
       ▼                             ▼
┌──────────────┐          ┌──────────────────────┐
│   Response   │          │  Result returned     │
│   to User    │          │  to MainAgent        │
│              │          │  (single message)    │
└──────────────┘          └──────────┬────────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │  MainAgent presents  │
                          │  findings to user    │
                          └──────────────────────┘
```

The MainAgent (the LLM itself) makes this routing decision at each turn based on the task description in its system prompt. There is no hard-coded if/else branching - the model reasons about whether direct tool use or delegation is more appropriate.

---

## When to Use Direct Tools vs. Delegation

### Direct tool use (handle it yourself)

Use direct tools when the task is simple, specific, and can be completed in a few tool calls:

- **Read a specific file**: `read_file` with a known path
- **Search for a specific symbol**: `search` with a targeted pattern
- **Find files by pattern**: `list_files` with a glob
- **Edit a known location**: `edit_file` when you know what to change
- **Run a single command**: `run_command` for a build/test
- **Creative or greenfield tasks**: No existing codebase to explore (game design, brainstorming, writing specs from scratch)
- **Tasks that don't match any subagent**: Don't force-fit - handle directly

### Delegation via `spawn_subagent` (hand it off)

Delegate when the task requires multi-step exploration, focused expertise, or benefits from context isolation:

- **"Where is error handling done?"** → Code-Explorer (requires broad codebase search)
- **"What's the architecture?"** → Code-Explorer (needs systematic exploration)
- **"Plan implementing feature X"** → Planner (requires analysis, file identification, plan writing)
- **"Review this PR for security"** → Security-Reviewer (domain expertise)
- **"Review PR #123"** → PR-Reviewer (structured code review workflow)
- **"Clone this website"** → Web-clone (visual analysis + code generation)
- **"Build a landing page"** → Web-Generator (full-stack web creation)
- **"Set up the project"** → Project-Init (codebase analysis + OPENDEV.md generation)
- **"What approach should we take?"** → ask-user (structured multiple-choice questions)

---

## The `spawn_subagent` Tool

The `spawn_subagent` tool is the single entry point for all delegation. It is registered in the MainAgent's tool schema with a dynamic description that lists all available subagent types.

**Source**: `swecli/core/agents/subagents/task_tool.py`

### Schema

```python
{
    "name": "spawn_subagent",
    "parameters": {
        "description":    str,    # Short summary (3-5 words)
        "prompt":         str,    # Full task with all context
        "subagent_type":  enum,   # One of the registered types
        "model":          enum,   # Optional: "haiku", "sonnet", "opus"
        "run_in_background": bool, # Optional: async execution
        "resume":         str,    # Optional: agent_id to continue
    }
}
```

### Key design decisions

1. **Context isolation**: Subagents have **no access to conversation history**. The `prompt` parameter must include all necessary context. This prevents context leakage and keeps the subagent focused.

2. **Single result**: A subagent returns a single message. The MainAgent never sees intermediate reasoning or tool calls - only the final output. This keeps the orchestrator's context clean.

3. **Model selection**: The caller can select a cheaper/faster model (`haiku` for quick tasks) or a more capable model (`opus` for complex reasoning). If unspecified, the subagent inherits the parent's model.

4. **Resumability**: Passing `resume` with a previous `agent_id` continues the subagent's session with full context preserved. This enables multi-turn subagent interactions without re-explaining context.

---

## Subagent Registry

All subagents are defined as `SubAgentSpec` typed dictionaries and collected in `ALL_SUBAGENTS`.

**Source**: `swecli/core/agents/subagents/specs.py`, `swecli/core/agents/subagents/agents/`

### SubAgentSpec type

```python
class SubAgentSpec(TypedDict):
    name: str                              # Unique identifier
    description: str                       # Used in spawn_subagent tool description
    system_prompt: str                     # Loaded from templates/subagents/*.md
    tools: NotRequired[list[str]]          # Restricted tool set (or inherit all)
    model: NotRequired[str]                # Model override
    docker_config: NotRequired[DockerConfig]  # Optional Docker execution
```

### Built-in subagents

| Subagent | Tools | Purpose |
|----------|-------|---------|
| **Code-Explorer** | `read_file`, `search`, `list_files`, `find_symbol`, `find_referencing_symbols` | Read-only codebase exploration. Searches, reads, and analyzes local files. Cannot modify anything. |
| **Planner** | `PLANNING_TOOLS` + `write_file`, `edit_file` | Explores codebase and writes implementation plans. Has write access only for the plan file. |
| **Security-Reviewer** | `read_file`, `search`, `list_files`, `find_symbol`, `find_referencing_symbols`, `run_command` | Security-focused code review. Reports vulnerabilities with severity/confidence scores. |
| **PR-Reviewer** | `read_file`, `search`, `list_files`, `find_symbol`, `find_referencing_symbols`, `run_command` | GitHub PR code review. Analyzes diffs for correctness, style, performance, tests, security. |
| **Project-Init** | `read_file`, `search`, `list_files`, `run_command`, `write_file` | Analyzes codebase and generates OPENDEV.md project instructions. |
| **Web-clone** | `capture_web_screenshot`, `analyze_image`, `write_file`, `read_file`, `run_command`, `list_files` | Visually analyzes websites and generates code to replicate their UI. |
| **Web-Generator** | `write_file`, `edit_file`, `run_command`, `list_files`, `read_file` | Creates responsive web applications from scratch (React + Tailwind). |
| **ask-user** | *(none)* | UI-only interaction. Gathers user input via structured multiple-choice prompts. |

### Tool restriction philosophy

Each subagent gets the **minimum viable tool set** for its purpose:

- **Read-only subagents** (Code-Explorer): No `write_file`, `edit_file`, or `run_command`. Physically cannot modify the codebase.
- **Plan-then-write subagents** (Planner): Write access limited to the plan file path. Read access to everything for exploration.
- **Full-access subagents** (Web-Generator): Need `write_file` + `edit_file` + `run_command` to scaffold projects and install dependencies.
- **Zero-tool subagents** (ask-user): No tools at all. The interaction is handled entirely by the UI layer via a special built-in type detection.

**Excluded from all subagents**: Todo tools (`write_todos`, `update_todo`, etc.) are intentionally excluded. Only the MainAgent manages task tracking - subagents focus purely on execution.

### PLANNING_TOOLS set

The Planner subagent uses a curated set of read-only tools:

```python
PLANNING_TOOLS = {
    "read_file", "list_files", "search",
    "fetch_url", "web_search",
    "list_processes", "get_process_output",
    "read_pdf",
    "find_symbol", "find_referencing_symbols",
    "search_tools",       # MCP tool discovery
    "spawn_subagent",     # Can spawn nested subagents
    "ask_user",           # Can ask clarifying questions
    "task_complete",      # Must be able to signal completion
}
```

Note: `spawn_subagent` is included, meaning the Planner can spawn nested Code-Explorers to parallelize its own exploration.

---

## Subagent Lifecycle

### 1. Registration

At startup, `SubAgentManager.register_defaults()` iterates over `ALL_SUBAGENTS` and creates a `CompiledSubAgent` for each:

```
SubAgentSpec → register_subagent() → MainAgent(allowed_tools=...) → CompiledSubAgent
```

Each `CompiledSubAgent` is a fully instantiated `MainAgent` with:
- A restricted `allowed_tools` list (filters the tool schema)
- An overridden `_subagent_system_prompt` (replaces the main system prompt)
- The same `tool_registry` (shared, but tool calls are filtered at schema level)
- The same `mode_manager` and `working_dir`

**Source**: `swecli/core/agents/subagents/manager.py:131-160`

### 2. Spawning

When the MainAgent calls `spawn_subagent`, the `SubAgentManager` looks up the `CompiledSubAgent` by name and executes its `run_sync()` method with the provided prompt:

```
MainAgent tool call → ToolRegistry → SubAgentManager.execute()
    → CompiledSubAgent.agent.run_sync(prompt, deps, ...)
    → Result string returned to MainAgent
```

The subagent runs the same ReAct loop as the MainAgent - it reasons, calls tools, observes results, and loops until completion. The only differences are the restricted tool set and specialized system prompt.

### 3. Result handling

The subagent's result is formatted by `format_task_result()` and injected as a tool result message in the MainAgent's conversation:

```python
# In MainAgent.run_sync(), after tool execution:
tool_result = separate_response if separate_response else result.get("output", "")
# Prepend completion status
if completion_status:
    tool_result = f"[completion_status={completion_status}]\n{tool_result}"
```

The MainAgent then synthesizes the subagent's findings into its response to the user. **Subagent results are not directly visible to the user** - the MainAgent must present them.

### 4. Cleanup

Subagents are ephemeral. After returning their result, no state is retained unless the caller saves the `agent_id` for later `resume`.

---

## Parallel Execution

### Detection

The `ReactExecutor` detects parallel subagent spawning at the tool-call level:

```python
# swecli/repl/react_executor.py
spawn_calls = [tc for tc in tool_calls if tc["function"]["name"] == "spawn_subagent"]
is_parallel_agents = len(spawn_calls) == len(tool_calls) and len(spawn_calls) > 1
```

Parallel execution is triggered when the LLM emits **multiple `spawn_subagent` calls in a single response**. This is the only way to get parallelism - sequential responses always execute sequentially.

### Execution

Parallel subagents run concurrently via `ThreadPoolExecutor`:

```
MainAgent response with N spawn_subagent calls
    │
    ├──→ Thread 1: Code-Explorer (search for auth patterns)
    ├──→ Thread 2: Code-Explorer (search for database patterns)
    └──→ Thread 3: Code-Explorer (search for API patterns)
         │
         ▼ (all complete via as_completed)
    Results collected by tool_call_id
    │
    ▼
MainAgent synthesizes all results into unified response
```

**Source**: `swecli/repl/react_executor.py:1487-1529`

### UI integration for parallel agents

The UI receives lifecycle callbacks for parallel agent tracking:

1. `on_parallel_agents_start(agent_infos)` - Called with list of `{agent_type, description, tool_call_id}` before execution begins
2. `on_parallel_agent_complete(tool_call_id, success)` - Called as each individual agent finishes
3. `on_parallel_agents_done()` - Called when all agents have completed

This enables the TUI to display a multi-agent progress panel showing which agents are running, which have completed, and their success/failure status.

### Result synthesis

When multiple subagents return results, the MainAgent is instructed (via system prompt) to:
- **Synthesize** all results into a single unified response organized by topic
- **Merge** overlapping findings and eliminate redundancy
- **Present** combined knowledge as if it came from one source
- **Never** summarize each agent separately

---

## Custom Agents

Beyond the 8 built-in subagents, users can define custom agents from two sources:

### JSON format

File: `~/.opendev/agents.json` or `<project>/.opendev/agents.json`

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

### Markdown format

File: `~/.opendev/agents/*.md` or `<project>/.opendev/agents/*.md`

The markdown file content becomes the system prompt directly. Frontmatter can specify tools and model.

### Three-tier precedence

1. **Built-in agents**: Lowest priority. Always available. Cannot be overridden by custom agents with the same name (builtin takes priority).
2. **User-global agents**: Defined in `~/.opendev/agents/`. Available across all projects.
3. **Project-local agents**: Defined in `<project>/.opendev/agents/`. Available only in that project.

### Tool specification flexibility

Custom agents support three tool specification modes:

```python
tools: list[str] | str | dict[str, list[str]]
```

- **Explicit list**: `["read_file", "search"]` - only these tools
- **Wildcard**: `"*"` - all available tools
- **Exclude pattern**: `{"exclude": ["write_file", "edit_file"]}` - all tools except excluded ones

**Source**: `swecli/core/agents/subagents/manager.py:263-326`

---

## Docker Execution (Optional)

Subagents can optionally execute inside Docker containers for sandboxed execution:

```python
SubAgentSpec(
    name="Sandboxed-Agent",
    docker_config=DockerConfig(...),
    copy_back_recursive=True,   # Copy workspace back after completion
)
```

When `docker_config` is specified:
1. A Docker container is started with the workspace mounted
2. Input files referenced in the task (PDFs, docs) are copied in via `docker cp`
3. The subagent runs inside the container
4. Results (and optionally the full workspace) are copied back to the host

This provides filesystem isolation - the subagent cannot modify the host filesystem directly.

**Fallback**: If Docker is unavailable (`shutil.which("docker") is None`), execution falls back to local mode transparently.

---

## Background Execution

Subagents can run in the background using `run_in_background: true`:

```
MainAgent: spawn_subagent(type="Code-Explorer", prompt="...", run_in_background=true)
    │
    ▼
Immediate response: { task_id: "abc123" }
    │
    ▼
MainAgent continues working on other tasks
    │
    ▼ (later)
MainAgent: get_subagent_output(task_id="abc123")
    │
    ▼
Result from completed subagent
```

This enables the MainAgent to fire off long-running tasks and check on them later, rather than blocking on the result.

---

## Relationship to Agent Modes

The delegation system interacts with the agent's mode:

- **Normal mode**: MainAgent has full tool access and can delegate to any subagent.
- **Plan mode**: MainAgent is restricted to read-only tools (PLANNING_TOOLS). The Planner subagent is the primary delegation target. Write operations are blocked at the registry level.
- **Thinking mode**: No tool access at all. Pure reasoning. No delegation possible.

The mode affects which tools appear in the MainAgent's schema, which in turn affects what the LLM can call - including `spawn_subagent` itself.

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          MainAgent                                  │
│                                                                     │
│  System Prompt ─────┐                                               │
│  (18 sections)      │                                               │
│                     ▼                                               │
│  ┌──────────────────────────────┐                                   │
│  │       LLM API Call          │                                    │
│  │  (model, messages, tools)   │                                    │
│  └──────────────┬───────────────┘                                   │
│                 │                                                    │
│     ┌───────────┴──────────────────────┐                            │
│     │                                  │                            │
│     ▼                                  ▼                            │
│  Direct tool call               spawn_subagent call                 │
│  ┌─────────────┐               ┌─────────────────────┐             │
│  │ ToolRegistry│               │ SubAgentManager     │             │
│  │  .execute() │               │  .execute()         │             │
│  └──────┬──────┘               └─────────┬───────────┘             │
│         │                                │                          │
│         ▼                                ▼                          │
│  ┌─────────────┐               ┌─────────────────────┐             │
│  │  Handler    │               │ CompiledSubAgent    │             │
│  │ (file/proc/ │               │ ┌─────────────────┐ │             │
│  │  web/mcp)   │               │ │ MainAgent       │ │             │
│  └──────┬──────┘               │ │ (restricted)    │ │             │
│         │                      │ │ ┌─────────────┐ │ │             │
│         │                      │ │ │ ReAct Loop  │ │ │             │
│         │                      │ │ │ (own tools) │ │ │             │
│         │                      │ │ └──────┬──────┘ │ │             │
│         │                      │ └────────┼────────┘ │             │
│         │                      └──────────┼──────────┘             │
│         │                                 │                         │
│         ▼                                 ▼                         │
│  Tool result message              Formatted result string           │
│  (appended to messages)           (appended as tool result)         │
│                                                                     │
│  ┌──────────────────────────────┐                                   │
│  │    Next LLM API Call         │◄──────── Loop continues           │
│  └──────────────────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Source Files

| File | Responsibility |
|------|---------------|
| `swecli/core/agents/subagents/task_tool.py` | `spawn_subagent` tool schema and result formatting |
| `swecli/core/agents/subagents/manager.py` | SubAgentManager: registration, compilation, execution, custom agents |
| `swecli/core/agents/subagents/specs.py` | SubAgentSpec and CompiledSubAgent type definitions |
| `swecli/core/agents/subagents/agents/__init__.py` | ALL_SUBAGENTS registry |
| `swecli/core/agents/subagents/agents/*.py` | Individual subagent specs (tools, prompts, descriptions) |
| `swecli/core/agents/subagents/tool_metadata.py` | Tool display names and metadata for agent creation wizard |
| `swecli/core/agents/components/schemas/planning_builder.py` | PLANNING_TOOLS set |
| `swecli/core/agents/prompts/templates/system/main/main-subagent-guide.md` | System prompt section guiding delegation decisions |
| `swecli/core/agents/prompts/templates/subagents/*.md` | Subagent-specific system prompts |
| `swecli/repl/react_executor.py` | Parallel subagent detection and ThreadPoolExecutor dispatch |
| `swecli/core/agents/main_agent.py` | MainAgent.run_sync() - the ReAct loop that processes tool calls and subagent results |

---

## Design Decisions and Trade-offs

### Why subagents reuse MainAgent

Subagents are instances of `MainAgent` with restricted `allowed_tools` and overridden system prompts - not a separate agent class. This means:

- **Pro**: One ReAct loop implementation to maintain. Bug fixes and improvements apply everywhere.
- **Pro**: Subagents can use the same tool registry, approval system, and context compaction.
- **Con**: A subagent carries the full `MainAgent` class weight even if it only needs 3 tools.
- **Decision**: Code reuse wins. The overhead of carrying unused methods is negligible compared to the maintenance cost of a parallel agent hierarchy.

### Why tool filtering is at schema level

Tools are filtered via `allowed_tools` in `ToolSchemaBuilder` - the LLM never sees tool schemas it cannot use. This is safer than filtering at execution time because:

- The LLM cannot call tools it doesn't know exist (no hallucinated tool calls to reject)
- Fewer tokens consumed by tool schemas (only relevant tools are serialized)
- No error handling needed for "tool not available" at runtime

### Why subagent results are opaque

The MainAgent receives only the final text output from a subagent, not the intermediate tool calls or reasoning. This:

- Keeps the orchestrator's context window clean
- Prevents context pollution from subagent exploration paths
- Allows the MainAgent to synthesize multiple subagent results without navigating nested tool-call trees
- Trade-off: The MainAgent cannot course-correct a subagent mid-execution. If the subagent goes off-track, the MainAgent must re-spawn or handle the incomplete result.

### Why parallel execution requires same-response batching

Parallel subagents only execute concurrently when emitted in the same LLM response. This is an inherent constraint of the ReAct loop: the agent generates a response, tools execute, results are appended, and the next response is generated. There is no mechanism for the LLM to "queue" work across responses.

The system prompt explicitly instructs the LLM: *"To run subagents concurrently, make multiple spawn_subagent calls in the SAME response."*
