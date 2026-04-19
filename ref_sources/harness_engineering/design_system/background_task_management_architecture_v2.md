# Background Task Management Architecture (v2)

## Overview

The background task management system coordinates all concurrent and long-running work across the agent: shell commands spawned in pseudo-terminals, parallel subagent executions, concurrent tool calls, user-driven interruption, and UI status updates. Five subsystems collaborate:

1. **BackgroundTaskManager** - tracks PTY-based shell processes with file-based output storage and listener notifications.
2. **ReactExecutor** - orchestrates parallel tool execution via a bounded thread pool.
3. **SubAgentManager** - runs multiple subagents concurrently via `asyncio.gather()`.
4. **InterruptToken** - provides per-query, thread-safe cancellation shared across all components.
5. **TaskMonitor** - tracks wall-clock timing and token consumption for individual LLM/tool calls.

## End-to-End Architecture

```
                        ┌─────────────────┐
                        │   User Input     │
                        └────────┬────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │       ReactExecutor           │
                  │                               │
                  │  Creates InterruptToken       │
                  │  (one per query, shared)       │
                  │                               │
                  │  ┌─ LLM produces tool calls ──┤
                  │  │                             │
                  └──┼─────────────────────────────┘
                     │
        ┌────────────┼──────────────┬──────────────────────┐
        │            │              │                      │
        ▼            ▼              ▼                      ▼
┌──────────────┐ ┌────────────┐ ┌────────────────┐ ┌──────────────────┐
│  Sequential  │ │  Parallel  │ │  Background    │ │  Parallel        │
│  Tool Exec   │ │  Tool Exec │ │  Command       │ │  Subagent Exec   │
│              │ │            │ │                │ │                  │
│  Any tool    │ │ThreadPool  │ │ PTY subprocess │ │ asyncio.gather() │
│  one at a    │ │(5 workers) │ │ + daemon       │ │ + per-agent      │
│  time        │ │read-only   │ │   stream       │ │   ReAct loop     │
│              │ │tools only  │ │   thread       │ │                  │
└──────┬───────┘ └─────┬──────┘ └───────┬────────┘ └────────┬─────────┘
       │               │                │                    │
       │               │                │                    │
       ▼               ▼                ▼                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Shared Infrastructure                           │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────┐ │
│  │  InterruptToken   │  │  TaskMonitor      │  │  BackgroundTask   │ │
│  │                   │  │                   │  │  Manager          │ │
│  │  request()        │  │  start/stop       │  │                  │ │
│  │  is_requested()   │  │  elapsed time     │  │  register_task() │ │
│  │  throw_if_        │  │  token delta      │  │  kill_task()     │ │
│  │    requested()    │  │  ↑/↓/· display    │  │  read_output()   │ │
│  │                   │  │                   │  │  listener notify  │ │
│  └────────┬──────────┘  └──────────────────┘  └────────┬──────────┘ │
│           │                                            │            │
└───────────┼────────────────────────────────────────────┼────────────┘
            │                                            │
            ▼                                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        UI Integration                               │
│                                                                     │
│  ┌──────────────────────────┐  ┌─────────────────────────────────┐ │
│  │  InterruptManager        │  │  BackgroundTaskStatusProvider    │ │
│  │                          │  │                                  │ │
│  │  ESC key → token.request │  │  Listener on task_mgr            │ │
│  │  Wired per-query by      │  │  → call_from_thread()            │ │
│  │  ReactExecutor           │  │  → footer.set_bg_task_count()    │ │
│  └──────────────────────────┘  └─────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## BackgroundTaskManager

Manages shell processes running in PTY subprocesses. Thread-safe via `RLock`.

### Data Structures

```
TaskStatus (Enum)
    RUNNING
    COMPLETED
    FAILED
    KILLED

BackgroundTask (Dataclass)
├── task_id: str              7-char hex (uuid4().hex[:7]), ~268M unique values
├── command: str              Shell command
├── working_dir: Path         Execution directory
├── pid: int                  Process ID
├── status: TaskStatus        Lifecycle state
├── started_at: datetime
├── output_file: Path         /tmp/swe-cli/{sanitized-dir}/tasks/{id}.output
├── process: Any              subprocess.Popen handle
├── pty_master_fd: int|None   PTY file descriptor for streaming
├── completed_at: datetime|None
├── exit_code: int|None
├── error_message: str|None
│
├── runtime_seconds → float   Computed: now - started_at (or completed_at - started_at)
└── is_running → bool         Computed: status == RUNNING
```

### Task Lifecycle

```
BashTool.execute(command, background=True)
│
├── Open PTY pair: master_fd, slave_fd = pty.openpty()
│
├── Spawn subprocess attached to PTY:
│   Popen(command, shell=True, stdin/stdout/stderr=slave_fd, close_fds=True)
│   os.close(slave_fd)  ← close slave in parent
│
├── Capture initial startup output (up to 20s, 3s idle timeout):
│   └── select.select([master_fd], ..., timeout=0.1) loop
│       ├── Read chunks → stdout_lines[]
│       ├── Stream via output_callback if provided
│       └── Break on: process exit, idle timeout, max capture time
│
├── Check process state:
│   ├── exit_code != 0 → return BashResult(success=False)   [startup crash]
│   ├── exit_code == 0 → return BashResult(success=True)    [fast command]
│   └── exit_code is None → process still running:
│
├── Store in BashTool._background_processes[pid]
│
└── Register with BackgroundTaskManager:
    │
    BackgroundTaskManager.register_task(command, pid, process, master_fd, initial_output)
    │
    ├── Generate task_id = uuid4().hex[:7]
    ├── Create output file: /tmp/swe-cli/{sanitized-dir}/tasks/{id}.output
    ├── Write initial_output to file
    ├── Create BackgroundTask(status=RUNNING)
    │
    ├── Start PTY streaming daemon thread:
    │   └── _start_output_streaming(task)
    │       └── stream_output() [inner function, daemon thread]
    │           ├── select.select([master_fd], ..., timeout=0.1) loop
    │           ├── os.read(master_fd, 4096) → append to output_file
    │           ├── stop_event check each iteration
    │           ├── On EOF or OSError → break
    │           └── Close master_fd on exit
    │
    ├── _notify_listeners(task_id, RUNNING)
    │
    └── Return BackgroundTask
```

### Status Transitions

```
                    register_task()
                         │
                         ▼
                    ┌─────────┐
                    │ RUNNING  │
                    └────┬────┘
                         │
               process.poll() → exit_code
                    ┌────┼────┐
                    │    │    │
                    ▼    │    ▼
            ┌───────────┐│ ┌──────┐
            │ COMPLETED  ││ │FAILED│
            │ (exit=0)   ││ │(≠0)  │
            └───────────┘│ └──────┘
                         │
                 {-SIGTERM, -SIGKILL}
                         │
                         ▼
                    ┌──────┐
                    │KILLED│
                    └──────┘
```

### Server Auto-Detection

The bash tool automatically detects server/daemon commands and forces background mode:

```
_SERVER_PATTERNS (regex):
    flask run             python manage.py runserver     uvicorn
    gunicorn              python -m http.server          npm start/dev/serve
    yarn start/dev/serve  node.*server                   nodemon
    next dev/start        rails server                   php artisan serve
    hugo server           jekyll serve
```

When `_is_server_command(command)` matches, `background` is forced to `True` regardless of the caller's setting. This ensures proper PTY-based output capture for long-running servers.

### Output Storage

```
/tmp/swe-cli/
└── {sanitized-working-dir}/          e.g., -Users-nghibui-codes-project
    └── tasks/
        ├── a1b2c3d.output            Append-only output file
        ├── e5f6g7h.output
        └── ...

Sanitization: working_dir path separators → dashes, spaces → underscores

read_output(task_id, tail_lines=100):
    Read entire file → return last N lines
    Return "" if file not found
```

### Kill Flow

```
kill_task(task_id, sig=SIGTERM)
│
├── Acquire _lock
├── Look up task in _tasks dict
│
├── Signal stop_event → daemon thread exits loop
│
├── Send signal to process:
│   os.killpg(os.getpgid(pid), sig)    ← kill entire process group
│   Fallback: process.terminate() or process.kill()
│
├── Wait for process exit (timeout=5s):
│   └── On timeout: process.kill() (SIGKILL escalation)
│
├── Close pty_master_fd
├── Update status → KILLED, set completed_at
│
├── _notify_listeners(task_id, KILLED)
│
└── Return True
```

### Listener Notification

```
BackgroundTaskManager
│
├── _listeners: list[Callable[[str, TaskStatus], None]]
│
├── add_listener(callback)     → _listeners.append(callback)
├── remove_listener(callback)  → _listeners.remove(callback)
│
└── _notify_listeners(task_id, status)
    └── for callback in _listeners:
            try: callback(task_id, status)
            except: log and continue   ← listener errors don't crash manager
```

### Cleanup

```
cleanup()
│
├── Copy running task IDs (avoid dict mutation during iteration)
│
├── For each running task:
│   ├── Signal stop_event → daemon thread exits
│   ├── process.terminate()
│   ├── process.wait(timeout=3)
│   ├── On timeout: process.kill()
│   └── Close pty_master_fd
│
└── Clear all internal dicts (_tasks, _stop_events, _output_threads)
```

## Parallel Tool Execution (ReactExecutor)

### Parallelizable Tools

```python
PARALLELIZABLE_TOOLS = frozenset({
    "read_file", "list_files", "search",           # File system reads
    "fetch_url", "web_search",                      # Network reads
    "capture_web_screenshot", "analyze_image",      # Media processing
    "list_processes", "get_process_output",          # Process queries
    "list_todos", "search_tools",                    # State queries
    "find_symbol", "find_referencing_symbols",       # Code navigation
})
```

All are read-only, require no user approval, and have no side effects.

### Execution Strategy

```
execute_tools(tool_calls)
│
├── Check: ALL calls in PARALLELIZABLE_TOOLS?
│
├── YES → Parallel execution:
│   ├── ThreadPoolExecutor(max_workers=5, thread_name_prefix="tool-worker")
│   │   (persistent pool, created once, reused across iterations)
│   │
│   ├── Submit all calls → futures
│   ├── Collect via as_completed()
│   └── Return results in original call order
│
└── NO (any non-parallelizable tool) → Sequential execution:
    ├── Execute each tool in order
    └── Return results
```

The executor uses ALL-or-nothing parallelization: if any single tool call in the batch is not in `PARALLELIZABLE_TOOLS`, the entire batch runs sequentially. This avoids partial ordering issues (e.g., a file write followed by a file read must run in order).

## Parallel Subagent Execution (SubAgentManager)

```
SubAgentManager.execute_parallel(tasks, deps, ui_callback)
│
├── tasks = [(name1, task1), (name2, task2), ...]
│
├── Notify UI: on_parallel_agents_start([name1, name2, ...])
│
├── Create coroutine for each task:
│   └── execute_with_tracking(name, task)
│       ├── result = await execute_subagent_async(name, task, deps, ui_callback)
│       │   └── Each subagent runs a full isolated ReAct loop
│       │       with filtered tool registry and own iteration budget
│       └── Notify UI: on_parallel_agent_complete(name, success)
│
├── results = await asyncio.gather(*coroutines)
│   └── Each coroutine runs in separate thread (via asyncio.to_thread)
│
├── Notify UI: on_parallel_agents_done()
│
└── Return list of results (order matches input task order)
```

Each parallel subagent gets a `NestedUICallback` with a unique `tool_call_id` as `parent_context`, enabling per-agent tracking in the parallel display.

## Interrupt System

### InterruptToken

One token is created per user query execution. All components share the same token instance.

```
InterruptToken
│
├── _event: threading.Event      ← Thread-safe by design
│
├── request()                    → _event.set()         [signal cancellation]
├── is_requested()               → _event.is_set()      [poll for cancellation]
├── throw_if_requested()         → raise InterruptedError if set
├── reset()                      → _event.clear()        [reuse; use with care]
│
│   Duck-typing aliases (TaskMonitor compatibility):
├── should_interrupt()           → is_requested()
└── request_interrupt()          → request()
```

### Token Wiring

```
ReactExecutor.execute(query, ...)
│
├── Create InterruptToken()
│   self._active_interrupt_token = InterruptToken()
│
├── Wire to UI:
│   app._interrupt_manager.set_interrupt_token(token)
│   └── ESC key press → interrupt_manager → token.request()
│
├── Wire to each TaskMonitor:
│   task_monitor.set_interrupt_token(token)
│   └── Monitor delegates interrupt queries to shared token
│
├── Check at phase boundaries:
│   _check_interrupt("pre_llm_call")
│   _check_interrupt("post_llm_call")
│   _check_interrupt("post_tool_execution")
│   └── If token.is_requested() → raise InterruptedError
│
├── Check at iteration boundary:
│   if _active_interrupt_token.is_requested():
│       ui_callback.on_interrupt()
│       break
│
└── Finally:
    ├── Clear token from InterruptManager
    └── self._active_interrupt_token = None
```

### Interrupt Propagation to Shell Commands

```
BashTool.execute() polling loop:
│
├── While process.poll() is None:
│   ├── Read output via select.select()
│   │
│   ├── Check task_monitor.should_interrupt():
│   │   └── If True:
│   │       ├── os.killpg(os.getpgid(pid), SIGKILL)  ← kill process group
│   │       ├── Fallback: process.kill()
│   │       ├── process.wait(timeout=1)
│   │       └── Return BashResult(success=False, error="interrupted")
│   │
│   └── Check timeouts:
│       ├── Idle timeout: 60s of no output → process.kill()
│       └── Absolute max: 600s → process.kill()
```

## TaskMonitor

Tracks timing and tokens for a single LLM call or tool execution within the ReAct loop.

```
TaskMonitor
│
├── State (all protected by threading.Lock):
│   ├── _start_time, _end_time
│   ├── _task_description: str
│   ├── _initial_tokens, _current_tokens, _token_delta
│   ├── _interrupt_token: InterruptToken|None
│   ├── _interrupt_requested: bool  ← local fallback if no token
│   └── _is_running: bool
│
├── Lifecycle:
│   ├── start(description, initial_tokens) → reset state, begin timing
│   └── stop() → returns {elapsed_seconds, token_delta, token_arrow, interrupted, ...}
│
├── Token tracking:
│   ├── update_tokens(current)     → thread-safe delta recalculation
│   ├── get_token_delta() → int
│   ├── get_token_arrow() → "↑"/"↓"/"·"
│   ├── format_tokens(3700) → "3.7k"
│   └── get_formatted_token_display() → "↑ 3.7k tokens" or ""
│
├── Interrupt support:
│   ├── request_interrupt()   → delegates to token or sets local flag
│   ├── should_interrupt()    → delegates to token or reads local flag
│   └── set_interrupt_token() → attach shared token after construction
│
└── Queries: is_running(), get_elapsed_seconds(), get_task_description()
```

## UI Integration

### BackgroundTaskStatusProvider

Bridges BackgroundTaskManager → TUI footer for running task count display.

```
BackgroundTaskStatusProvider
│
├── __init__(app, task_manager):
│   ├── Register as listener: task_manager.add_listener(_on_task_status_change)
│   └── Initial update: _update_footer()
│
├── _on_task_status_change(task_id, status):
│   └── _update_footer()
│
├── _update_footer():
│   ├── running_count = len(task_manager.get_running_tasks())
│   └── Thread-safe UI update:
│       ├── app.call_from_thread(_do_update)
│       │   └── Find ModelFooter → footer.set_background_task_count(running_count)
│       └── Fallback (not in worker thread): call directly
│
└── cleanup():
    └── task_manager.remove_listener(...)
```

## Concurrency Model

### Thread Architecture

```
Main Thread (TUI event loop / REPL)
│
├── ReactExecutor Thread (agent loop)
│   │
│   ├── ThreadPoolExecutor (max 5 workers, prefix="tool-worker")
│   │   ├── Tool worker 1 (e.g., read_file)
│   │   ├── Tool worker 2 (e.g., search)
│   │   └── ... up to 5 concurrent tool executions
│   │
│   └── asyncio event loop (for parallel subagents)
│       ├── Subagent thread 1 (via asyncio.to_thread)
│       │   └── Full ReAct loop (own ThreadPoolExecutor for tools)
│       ├── Subagent thread 2
│       └── ...
│
├── Background Task Daemon Threads (one per PTY process)
│   ├── stream_output for task a1b2c3d [daemon=True]
│   ├── stream_output for task e5f6g7h [daemon=True]
│   └── ... (die automatically when main process exits)
│
└── Async Hook Threads
    └── ThreadPoolExecutor (max 2 workers, prefix="hook-async")
```

### Thread Safety

```
Component                 Mechanism                   Scope
─────────                 ─────────                   ─────
BackgroundTaskManager     RLock (reentrant)            _tasks, _stop_events, _output_threads
TaskMonitor               threading.Lock               All state fields
InterruptToken            threading.Event              Atomic set/is_set operations
ReactExecutor             Queue(maxsize=10)            Message injection (thread-safe)
SubAgentManager           asyncio.gather               Isolation via separate event loops
```

### Safety Constants

```
MAX_CONCURRENT_TOOLS = 5       Tool worker pool size
IDLE_TIMEOUT = 60              Kill command after 60s of no output
MAX_TIMEOUT = 600              Absolute max runtime: 10 minutes
MAX_OUTPUT_CHARS = 30000       Truncate output beyond 30k chars
KEEP_HEAD_CHARS = 10000        Head preserved on truncation
KEEP_TAIL_CHARS = 10000        Tail preserved on truncation
```

## Key Files Reference

| Component | File | Key Elements |
|-----------|------|--------------|
| Task manager | `swecli/core/context_engineering/tools/background_task_manager.py` | BackgroundTaskManager, BackgroundTask, TaskStatus |
| Task monitor | `swecli/core/runtime/monitoring/task_monitor.py` | TaskMonitor, timing/token tracking |
| Interrupt token | `swecli/core/runtime/interrupt_token.py` | InterruptToken, per-query cancellation |
| Subagent manager | `swecli/core/agents/subagents/manager.py` | execute_parallel(), execute_subagent() |
| Bash tool | `swecli/core/context_engineering/tools/implementations/bash_tool.py` | Background PTY, server auto-detect, safety gates |
| React executor | `swecli/repl/react_executor.py` | Parallel tool execution, interrupt checking |
| UI status provider | `swecli/ui_textual/managers/background_task_status.py` | BackgroundTaskStatusProvider, footer bridge |
