# Subagent Orchestration Architecture

## Overview

The subagent system lets the main agent delegate tasks to ephemeral, purpose-built agents. Each subagent runs a full ReAct loop in isolation: it has its own system prompt, filtered tool set, and empty conversation history. It receives a task string, executes until done, and returns a single result to the parent.

## Architecture

```
                 Main Agent (ReactExecutor)
                 │
                 │  LLM response contains tool_calls
                 │
                 ├─────────────────────────────────────────────────────────────────┐
                 │                                                                 │
                 ▼                                                                 ▼
    ┌────────────────────────┐                                  ┌─────────────────────────────┐
    │ Single spawn_subagent  │                                  │ ALL tool_calls are           │
    │ (or mixed batch)       │                                  │ spawn_subagent AND count > 1 │
    └───────────┬────────────┘                                  └──────────────┬──────────────┘
                │                                                              │
                │ _execute_single_tool(tc)                                     │ is_parallel_agents = True
                │                                                              │
                ▼                                                              ▼
    ┌────────────────────────┐                          ┌─────────────────────────────────┐
    │  ToolRegistry.execute  │                          │ Parallel Detection & Dispatch    │
    │  ("spawn_subagent",    │                          │                                  │
    │   args)                │                          │ 1. Parse each tc's args JSON     │
    └───────────┬────────────┘                          │    → {subagent_type, description, │
                │                                       │       tool_call_id}               │
                │                                       │                                  │
                │                                       │ 2. UI: on_parallel_agents_start  │
                │                                       │    (agent_infos list)             │
                │                                       │                                  │
                │                                       │ 3. ThreadPoolExecutor.submit()   │
                │                                       │    per spawn_subagent call        │
                │                                       │                                  │
                │                                       │ 4. as_completed() → track each   │
                │                                       │    on_parallel_agent_complete     │
                │                                       │                                  │
                │                                       │ 5. UI: on_parallel_agents_done   │
                │                                       └────────────┬────────────────────┘
                │                                                    │
                │ (both paths call)                                  │
                ▼                                                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                      │
│                     SubAgentManager.execute_subagent(name, task, deps, ...)           │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │  Gate 1: Hook System                                                            │  │
│  │  ├── HookEvent.SUBAGENT_START (match_value=name)                                │  │
│  │  ├── event_data = {agent_task: task}                                             │  │
│  │  └── If outcome.blocked → return {success: false, error: block_reason}          │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                         │                                                            │
│                         ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │  Gate 2: Three-Way Dispatch                                                     │  │
│  │                                                                                  │  │
│  │  ┌──── name == "ask-user" ─────────────────────────────────────────────────┐     │  │
│  │  │                                                                         │     │  │
│  │  │  _execute_ask_user(task, ui_callback)                                   │     │  │
│  │  │  │                                                                      │     │  │
│  │  │  ├── Parse task as JSON: {questions: [{question, header, options, ...}]} │     │  │
│  │  │  ├── Get app ref from ui_callback chain                                 │     │  │
│  │  │  ├── app.call_from_thread → run_worker(run_panel)                       │     │  │
│  │  │  │   └── answers = await app._ask_user_controller.start(questions)      │     │  │
│  │  │  ├── threading.Event.wait(timeout=600)                                  │     │  │
│  │  │  └── Return {success, content: "Received N/M answers: ...", answers}    │     │  │
│  │  │                                                                         │     │  │
│  │  │  ★ No LLM call. No tools. Pure UI panel interaction.                    │     │  │
│  │  └─────────────────────────────────────────────────────────────────────────┘     │  │
│  │                                                                                  │  │
│  │  ┌──── spec.docker_config AND docker available ────────────────────────────┐     │  │
│  │  │                                                                         │     │  │
│  │  │  _execute_with_docker(name, task, deps, spec, ...)                      │     │  │
│  │  │  │                                                                      │     │  │
│  │  │  │  [see Docker Execution section below]                                │     │  │
│  │  │  │                                                                      │     │  │
│  │  └─────────────────────────────────────────────────────────────────────────┘     │  │
│  │                                                                                  │  │
│  │  ┌──── Default: Local Execution ───────────────────────────────────────────┐     │  │
│  │  │                                                                         │     │  │
│  │  │  [see Local Execution section below]                                    │     │  │
│  │  │                                                                         │     │  │
│  │  └─────────────────────────────────────────────────────────────────────────┘     │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                         │                                                            │
│                         ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │  Post-Execution: Hook System                                                    │  │
│  │  └── HookEvent.SUBAGENT_STOP (match_value=name, async fire-and-forget)          │  │
│  │      event_data = {agent_result: {success: bool}}                               │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  Return {content: str, success: bool, messages: list}                                │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## Local Execution (Default Path)

```
execute_subagent(name, task, deps, ui_callback, tool_call_id, ...)
│
│  ── Step 1: Resolve agent instance ──────────────────────────────────────
│
├── Look up name in _agents dict (pre-registered CompiledSubAgent)
│   └── Not found → return error with list of available types
│
├── agent = compiled["agent"]       ← Pre-built MainAgent
├── allowed_tools = compiled["tool_names"]
│
│   ★ If working_dir or docker_handler overrides are given:
│     └── Create fresh MainAgent instead of using pre-built one:
│         MainAgent(
│             config       = _get_subagent_config(spec)  ← optional model override
│             tool_registry = _tool_registry (or DockerToolRegistry if docker_handler)
│             mode_manager  = shared _mode_manager
│             working_dir   = override or self._working_dir
│             allowed_tools = spec.tools or all tools
│             env_context   = shared _env_context
│         )
│
├── Apply system prompt:
│   ├── agent.system_prompt = spec["system_prompt"]
│   └── If Docker: prepend docker_preamble to system prompt
│
│  ── Step 2: Create NestedUICallback ─────────────────────────────────────
│
├── ui_callback provided?
│   ├── Already a NestedUICallback → use directly (no double-wrapping)
│   └── Raw UICallback → wrap:
│       NestedUICallback(
│           parent_callback = ui_callback
│           parent_context  = tool_call_id or name
│                             ↑ tool_call_id enables per-agent tracking in parallel display
│           depth           = 1
│       )
│
│  ── Step 3: Run isolated ReAct loop ─────────────────────────────────────
│
├── agent.run_sync(
│       message         = task          ← Full task text (all context must be here)
│       deps            = deps          ← mode_manager, approval_manager, undo_manager
│       message_history = None          ← Empty history (no parent conversation access)
│       ui_callback     = nested_callback
│       max_iterations  = None          ← No cap (subagent prompt controls termination)
│       task_monitor    = task_monitor  ← Shared interrupt token propagates ESC
│   )
│   │
│   └── Inside run_sync:
│       ├── Create own ReactExecutor
│       ├── Build system prompt via PromptComposer
│       ├── Iterate: thinking → LLM call → tool execution → repeat
│       ├── Tool calls filtered to allowed_tools only
│       └── Terminate when: task_complete called or LLM stops producing tool calls
│
│  ── Step 4: Return result ───────────────────────────────────────────────
│
└── Return {
        content: str      ← Final text output from subagent
        success: bool     ← Did it complete without error
        messages: list    ← Full message history (for resume)
    }
```

## Parallel Subagent Execution

### Detection Logic (ReactExecutor)

```
_execute_tool_calls(tool_calls, ctx):
│
├── spawn_calls = [tc for tc in tool_calls if tc.name == "spawn_subagent"]
│
├── is_parallel = len(spawn_calls) == len(tool_calls) AND len(spawn_calls) > 1
│   │
│   │  ★ ALL-or-nothing rule: if any non-spawn tool in the batch,
│   │    entire batch runs sequentially. No mixing.
│   │
│   │  Examples:
│   │    [spawn, spawn, spawn]           → parallel (3 agents)
│   │    [spawn]                         → sequential (single agent)
│   │    [spawn, spawn, read_file]       → sequential (mixed batch)
│   │    [read_file, read_file]          → parallel via PARALLELIZABLE_TOOLS path
│   │
│   └── ★ This is triggered by the LLM producing multiple spawn_subagent tool
│         calls in a single response. The tool description instructs the LLM:
│         "To run subagents concurrently, make multiple spawn_subagent calls
│          in the SAME response."
│
└── If parallel:

    ── Phase 1: Build UI metadata ──────────────────────────────────────

    For each spawn_call:
    ├── Parse arguments JSON:
    │   args = json.loads(tc["function"]["arguments"])
    │   agent_type = args["subagent_type"]     e.g., "Code-Explorer"
    │   description = args["description"]      e.g., "Analyze auth module"
    │   tool_call_id = tc["id"]                e.g., "call_abc123"
    │
    ├── agent_name_map[tool_call_id] = agent_type
    │
    └── agent_infos.append({
            agent_type: "Code-Explorer",
            description: "Analyze auth module",
            tool_call_id: "call_abc123"
        })

    UI: on_parallel_agents_start(agent_infos)
    └── TUI shows: "Running 3 agents: Code-Explorer, Planner, Security-Reviewer"

    ── Phase 2: Concurrent execution ───────────────────────────────────

    ThreadPoolExecutor (shared, max_workers=5):
    ├── executor.submit(_execute_single_tool, tc1, ctx) → Future 1
    ├── executor.submit(_execute_single_tool, tc2, ctx) → Future 2
    └── executor.submit(_execute_single_tool, tc3, ctx) → Future 3
        │
        │   Each _execute_single_tool:
        │   ├── Parse spawn_subagent args
        │   ├── Call SubAgentManager.execute_subagent(
        │   │       name=subagent_type,
        │   │       task=prompt,
        │   │       tool_call_id=tc["id"]  ← unique ID for per-agent UI tracking
        │   │   )
        │   │   └── Full isolated ReAct loop per agent (own thread)
        │   └── Return result dict
        │
        └── as_completed(futures):
            For each completed future:
            ├── result = future.result()
            ├── tool_results_by_id[tc.id] = result
            │
            └── UI: on_parallel_agent_complete(tool_call_id, success)
                └── TUI shows: "✓ Code-Explorer completed" or "✗ Planner failed"

    ── Phase 3: Completion ─────────────────────────────────────────────

    UI: on_parallel_agents_done()
    └── TUI clears parallel tracking display

    Return tool_results_by_id (keyed by tool_call.id)
```

### Thread / Isolation Model

```
Main Agent Thread (ReactExecutor)
│
├── ThreadPoolExecutor.submit() per parallel spawn
│   │
│   ├── Thread 1: execute_subagent("Code-Explorer", task1)
│   │   ├── Own MainAgent instance
│   │   ├── Own ReactExecutor (created inside run_sync)
│   │   ├── Own conversation history (starts empty)
│   │   ├── Filtered tool registry (read-only tools only)
│   │   ├── NestedUICallback(parent_context=tool_call_id_1)
│   │   └── Shared: interrupt_token, working_dir, mode_manager
│   │
│   ├── Thread 2: execute_subagent("Planner", task2)
│   │   ├── Own MainAgent instance
│   │   ├── Filtered tool registry (planning_tools + write_file + edit_file)
│   │   ├── NestedUICallback(parent_context=tool_call_id_2)
│   │   └── Shared: interrupt_token, working_dir, mode_manager
│   │
│   └── Thread 3: execute_subagent("Security-Reviewer", task3)
│       ├── Own MainAgent instance
│       ├── Filtered tool registry (read + run_command)
│       ├── NestedUICallback(parent_context=tool_call_id_3)
│       └── Shared: interrupt_token, working_dir, mode_manager
│
└── Main thread waits at as_completed() for all futures

Isolation:     Conversation history, system prompt, tool set, UI context
Shared:        Working directory, interrupt token, tool registry (read-through)
No coordination: Agents cannot communicate or share intermediate results
Failure:       If one agent fails, others continue; all results returned
```

## Docker Execution

```
_execute_with_docker(name, task, deps, spec, ...)
│
│  ── Step 1: Container Lifecycle ─────────────────────────────────────────
│
├── Create DockerDeployment(config=spec.docker_config)
│   └── Container name format: "swecli-runtime-{8_hex_chars}"
│
├── Extract container_id = container_name.split("-")[-1]  → e.g., "a1b2c3d4"
│
├── Create NestedUICallback with Docker path sanitizer:
│   │   All paths displayed as: [image_short:container_id]:/workspace/...
│   │   Example: [uv:a1b2c3d4]:/workspace/src/model.py
│   │
│   └── Path sanitization rules:
│       ├── /Users/.../project/src/file.py → [uv:a1b2c3d4]:/workspace/src/file.py
│       ├── /workspace/src/file.py         → [uv:a1b2c3d4]:/workspace/src/file.py
│       ├── src/file.py (relative)         → [uv:a1b2c3d4]:/workspace/src/file.py
│       └── /tmp/.../file.py (other abs)   → [uv:a1b2c3d4]:/workspace/file.py
│
├── UI: docker_start spinner (via nested callback)
├── await deployment.start()    ← async, runs in dedicated event loop
├── mkdir -p /workspace
├── UI: docker_start complete
│
│  ── Step 2: File Transfer In ────────────────────────────────────────────
│
├── Extract input files from task text:
│   ├── @filename.pdf              regex: @[\w\-\.]+\.(pdf|docx?)
│   ├── "quoted/path.pdf"          regex: ["'`]...(pdf|docx?)["'`]
│   ├── unquoted paper.pdf         regex: whitespace-delimited .(pdf|docx?)
│   └── ArXiv IDs (2303.11366v4)   regex: \d[\w\.\-]+v\d+ → try .pdf/.docx
│
├── For each file found:
│   ├── docker cp local_file container:/workspace/filename
│   ├── path_mapping["/workspace/filename"] = "/local/path/filename"
│   └── UI: docker_copy progress per file
│
├── Rewrite task text:
│   ├── Replace @filename → /workspace/filename
│   ├── Replace local absolute paths → /workspace/...
│   ├── Replace "in this repo" → "in /workspace"
│   └── Prepend Docker context reminder to task
│
│  ── Step 3: Tool Routing ────────────────────────────────────────────────
│
├── Create DockerToolHandler(runtime, workspace_dir="/workspace", shell_init=...)
│
├── Create DockerToolRegistry(
│       docker_handler   = handler
│       local_registry   = _tool_registry   ← fallback for unsupported tools
│       path_mapping     = path_mapping     ← remap Docker → local for local-only tools
│   )
│   │
│   └── Tool routing:
│       ├── run_command  → docker exec container bash -c "command"
│       ├── write_file   → docker exec container write to /workspace/...
│       ├── read_file    → docker exec container cat /workspace/...
│       ├── read_pdf     → fallback to local_registry (PDF library not in container)
│       │                  path remapped: /workspace/file.pdf → /local/path/file.pdf
│       └── (etc.)
│
│  ── Step 4: Subagent Execution ──────────────────────────────────────────
│
├── execute_subagent(
│       name            = name
│       task            = docker_task (rewritten)
│       docker_handler  = handler
│       path_mapping    = path_mapping
│       ui_callback     = nested_callback (Docker path sanitizer attached)
│       working_dir     = "/workspace"
│   )
│   │
│   └── Creates MainAgent with:
│       ├── DockerToolRegistry (routes tools through container)
│       ├── system_prompt = docker_preamble + "\n\n" + spec.system_prompt
│       │   └── docker_preamble: "You are running inside a Docker container.
│       │       All file operations happen in /workspace/... Do NOT reference
│       │       any paths outside the container."
│       └── working_dir = "/workspace"
│
│  ── Step 5: File Transfer Out ───────────────────────────────────────────
│
├── If success:
│   └── docker cp container:/workspace/. local_dir/
│       ├── Recursive copy of entire workspace
│       ├── Timeout: 120 seconds
│       └── UI: docker_copy_back progress
│
│  ── Step 6: Cleanup (finally block) ─────────────────────────────────────
│
├── UI: docker_stop
├── await deployment.stop()
├── UI: docker_stop complete
└── Close async event loop
```

## Agent Registration System

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Agent Sources                                    │
│                                                                         │
│  Priority: BUILTIN > USER_GLOBAL > PROJECT                             │
│  (Same name → higher priority wins, lower is skipped)                   │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  BUILTIN (agents/__init__.py → ALL_SUBAGENTS)                    │  │
│  │                                                                   │  │
│  │  Agent             Tools                          Capabilities    │  │
│  │  ─────             ─────                          ────────────    │  │
│  │  Code-Explorer     read_file, search, list_files  Read-only       │  │
│  │                    find_symbol, find_refs          codebase nav    │  │
│  │                                                                   │  │
│  │  Planner           PLANNING_TOOLS + write_file    Read + write    │  │
│  │                    + edit_file                     plan files      │  │
│  │                                                                   │  │
│  │  PR-Reviewer       read_file, search, list_files  Read + git      │  │
│  │                    find_symbol, find_refs          commands        │  │
│  │                    run_command                                     │  │
│  │                                                                   │  │
│  │  Security-Reviewer read_file, search, list_files  Read + security │  │
│  │                    find_symbol, find_refs          checks          │  │
│  │                    run_command                                     │  │
│  │                                                                   │  │
│  │  Project-Init      read_file, search, list_files  Read + write    │  │
│  │                    run_command, write_file         OPENDEV.md      │  │
│  │                                                                   │  │
│  │  Web-Generator     write_file, edit_file          Full write for  │  │
│  │                    run_command, list_files         web app         │  │
│  │                    read_file                       creation        │  │
│  │                                                                   │  │
│  │  Web-clone         capture_web_screenshot          Visual clone   │  │
│  │                    analyze_image, write_file       with screenshot │  │
│  │                    read_file, run_command          analysis        │  │
│  │                    list_files                                      │  │
│  │                                                                   │  │
│  │  ask-user          (none)                          UI panel only   │  │
│  │                                                    No LLM          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  USER_GLOBAL (~/.opendev/agents.json or ~/.opendev/agents/*.md)  │  │
│  │  PROJECT     (<project>/.opendev/agents.json or agents/*.md)     │  │
│  │                                                                   │  │
│  │  register_custom_agents(definitions):                             │  │
│  │  │                                                                │  │
│  │  ├── For each definition:                                         │  │
│  │  │   ├── Skip if name matches builtin (builtin takes priority)   │  │
│  │  │   │                                                            │  │
│  │  │   ├── Resolve tools:                                           │  │
│  │  │   │   ├── "*"              → all available tools               │  │
│  │  │   │   ├── ["read_file"...] → explicit list                    │  │
│  │  │   │   ├── {exclude: [...]} → all minus excluded               │  │
│  │  │   │   └── (missing)        → all available tools               │  │
│  │  │   │                                                            │  │
│  │  │   ├── Resolve system prompt:                                   │  │
│  │  │   │   ├── Markdown format: _system_prompt field (inline)      │  │
│  │  │   │   ├── JSON format: skillPath → load file, strip YAML      │  │
│  │  │   │   └── Neither: default template with name/description     │  │
│  │  │   │                                                            │  │
│  │  │   └── register_subagent(spec) → create MainAgent → _agents    │  │
│  │  │                                                                │  │
│  │  └── Custom agents appear in spawn_subagent's enum automatically │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### SubAgentSpec → CompiledSubAgent → MainAgent

```
SubAgentSpec (TypedDict, static config)
│
├── name: str                         Unique identifier (e.g., "Code-Explorer")
├── description: str                  Used in spawn_subagent tool description
├── system_prompt: str                Loaded via load_prompt("subagents/...")
├── tools: list[str]                  Explicit allowed tool names
├── model: str|None                   Override (e.g., "haiku" for cheap tasks)
├── docker_config: DockerConfig|None  If set, triggers Docker execution path
└── copy_back_recursive: bool         Whether to copy files back from Docker
        │
        │ register_subagent(spec)
        ▼
CompiledSubAgent (TypedDict, runtime)
│
├── name: str
├── description: str
├── agent: MainAgent                  Pre-built agent instance
│   ├── config = AppConfig (with optional model override)
│   ├── tool_registry = shared (but filtered via allowed_tools)
│   ├── _subagent_system_prompt = spec["system_prompt"]
│   └── allowed_tools = spec["tools"]
│
└── tool_names: list[str]             Resolved tool list
```

## Tool Filtering

Each subagent sees only its allowed tools. The filtering happens at two levels:

```
                             Main Agent Tool Registry
                             (all ~30 tools registered)
                                        │
                            ┌───────────┼───────────┐
                            │           │           │
                            ▼           ▼           ▼
                    Code-Explorer    Planner     Web-clone
                    5 tools          ~12 tools    6 tools
                    ┌──────────┐   ┌──────────┐  ┌──────────┐
                    │read_file │   │read_file │  │capture_  │
                    │search    │   │search    │  │ web_     │
                    │list_files│   │list_files│  │ screenshot│
                    │find_     │   │write_file│  │analyze_  │
                    │ symbol   │   │edit_file │  │ image    │
                    │find_     │   │find_     │  │write_file│
                    │ refs     │   │ symbol   │  │read_file │
                    └──────────┘   │...       │  │run_cmd   │
                                   └──────────┘  │list_files│
                                                  └──────────┘

filtering mechanism:
  MainAgent(allowed_tools=["read_file", "search", ...])
  └── Tool schemas passed to LLM include only allowed tools
  └── Tool execution validates against allowed list

★ Todo tools (write_todos, update_todo, complete_todo, list_todos) are
  intentionally excluded from ALL subagents. Only the parent agent
  manages task tracking.
```

## Nested Tool Call Persistence

When a subagent completes, its internal tool calls are captured and persisted as nested calls within the parent's spawn_subagent tool call:

```
_persist_tool_results_step(tool_calls, results, ctx):
│
├── For each spawn_subagent tool_call:
│   ├── Get nested calls from UI callback:
│   │   nested_calls = ctx.ui_callback.get_and_clear_nested_calls()
│   │
│   └── Create ToolCallModel(
│           id        = tc["id"]
│           name      = "spawn_subagent"
│           parameters = {subagent_type, prompt, ...}
│           result     = {content, success}
│           nested_tool_calls = [    ← Subagent's internal tool calls
│               ToolCall(name="read_file", params={path: "..."}, result=...),
│               ToolCall(name="search", params={query: "..."}, result=...),
│               ...
│           ]
│       )
│
└── Stored in session for conversation history display
```

## Key Files

| Component | File |
|-----------|------|
| Manager (1610 lines) | `swecli/core/agents/subagents/manager.py` |
| Specs (TypedDicts) | `swecli/core/agents/subagents/specs.py` |
| spawn_subagent schema | `swecli/core/agents/subagents/task_tool.py` |
| Built-in agents (8) | `swecli/core/agents/subagents/agents/*.py` |
| Parallel detection | `swecli/repl/react_executor.py` (_execute_tool_calls) |
| Nested UI callback | `swecli/ui_textual/nested_callback.py` |
| Docker tool routing | `swecli/core/docker/tool_handler.py` |
