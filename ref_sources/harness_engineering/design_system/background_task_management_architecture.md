# Background Task Management Architecture

## Overview

The background task management system tracks long-running processes across two execution paths: bash commands running in PTY subprocesses and parallel subagent executions. The BackgroundTaskManager handles process-level tasks with file-based output storage, PTY streaming, and listener notifications. The SubAgentManager handles parallel agent execution via asyncio.gather(). The ReactExecutor coordinates concurrent tool calls with a bounded ThreadPoolExecutor. An InterruptToken provides centralized cancellation across all active tasks.

## End-to-End Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        Agent Decision Layer                               │
│                                                                           │
│  LLM decides to execute tools                                            │
│  │                                                                        │
│  ├── Single tool call                                                    │
│  │   └── Sequential execution                                            │
│  │                                                                        │
│  ├── Multiple independent tool calls                                     │
│  │   └── Parallel execution via ThreadPoolExecutor                       │
│  │                                                                        │
│  ├── run_command(cmd, run_in_background=True)                            │
│  │   └── Background bash via BackgroundTaskManager                       │
│  │                                                                        │
│  └── Multiple spawn_subagent calls in same response                      │
│      └── Parallel subagent execution via asyncio.gather()                │
│                                                                           │
└──────────┬───────────────┬──────────────────┬─────────────────────────────┘
           │               │                  │
           ▼               ▼                  ▼
┌─────────────────┐ ┌──────────────┐ ┌────────────────────┐
│ ReactExecutor   │ │ Background   │ │ SubAgentManager    │
│                 │ │ TaskManager  │ │                    │
│ ThreadPool      │ │              │ │ execute_parallel() │
│ Executor        │ │ PTY streams  │ │ asyncio.gather()   │
│ (5 workers)     │ │ File output  │ │                    │
│                 │ │ Listeners    │ │ Per-agent ReAct    │
│ Parallel tool   │ │              │ │ loop (isolated)    │
│ execution       │ │ Task IDs     │ │                    │
└────────┬────────┘ └──────┬───────┘ └─────────┬──────────┘
         │                 │                    │
         │                 │                    │
         ▼                 ▼                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     Interrupt / Monitoring Layer                          │
│                                                                           │
│  ┌─────────────────┐    ┌──────────────────┐                            │
│  │ InterruptToken   │    │ TaskMonitor       │                            │
│  │                  │    │                   │                            │
│  │ Thread-safe      │    │ Timing            │                            │
│  │ cancellation     │    │ Token tracking    │                            │
│  │ flag             │    │ Elapsed seconds   │                            │
│  │                  │    │ Token delta        │                            │
│  └─────────────────┘    └──────────────────┘                            │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

## BackgroundTaskManager

### Data Structures

```
TaskStatus (Enum)
│  RUNNING
│  COMPLETED
│  FAILED
│  KILLED

BackgroundTask (Dataclass)
│
├── task_id: str              7-char hex ID (uuid4().hex[:7])
├── command: str              Shell command being executed
├── working_dir: Path         Working directory for the process
├── pid: int                  Process ID
├── status: TaskStatus        Current lifecycle state
├── started_at: datetime      When the task started
├── output_file: Path         File storing captured output
├── process: subprocess.Popen The subprocess handle
├── pty_master_fd: Optional[int]  PTY file descriptor for streaming
├── completed_at: Optional[datetime]
├── exit_code: Optional[int]
└── error_message: Optional[str]
```

### Task Lifecycle

```
register_task(command, pid, process, pty_master_fd, initial_output)
│
├── Generate task_id = uuid4().hex[:7]
│
├── Create output file:
│   /tmp/swe-cli/{sanitized-working-dir}/tasks/{task_id}.output
│
├── Write initial_output to file (if any)
│
├── Create BackgroundTask(status=RUNNING)
│
├── Start output streaming daemon thread
│   └── _stream_output(task_id, pty_master_fd, output_file)
│
├── Notify listeners: on_task_started(task_id)
│
└── Return BackgroundTask
        │
        │  (task runs in background)
        │
        ▼
    _update_task_status(task)
    │
    ├── process.poll() → exit_code
    │
    ├── exit_code is None → still RUNNING
    │
    ├── exit_code == 0 → COMPLETED
    │   └── Set completed_at = now
    │
    ├── exit_code in {-SIGTERM, -SIGKILL} → KILLED
    │   └── Set completed_at = now
    │
    └── exit_code != 0 → FAILED
        ├── Set completed_at = now
        └── Set error_message = "Exit code: {code}"
```

### Key Methods

```
BackgroundTaskManager
│
├── register_task(command, pid, process, pty_master_fd, initial_output) → BackgroundTask
├── get_task(task_id) → BackgroundTask | None
├── get_running_tasks() → list[BackgroundTask]
├── get_all_tasks() → list[BackgroundTask]
├── kill_task(task_id, signal=SIGTERM) → bool
├── read_output(task_id, tail_lines=100) → str
├── add_listener(callback) → None
├── remove_listener(callback) → None
└── _stream_output(task_id, pty_master_fd, output_file) → None   [daemon thread]
```

## Task ID Generation and Output Storage

```
Output Directory Structure:

/tmp/swe-cli/
└── {sanitized-working-dir}/          e.g., -Users-nghibui-codes-project
    └── tasks/
        ├── a1b2c3d.output            Task output file (append-only)
        ├── e5f6g7h.output
        └── ...

Sanitization: working_dir.replace("/", "-").replace(" ", "_")
```

Task IDs are 7 hex characters from uuid4, providing ~268 million unique values. Collision probability is negligible within a single session.

## PTY Streaming

Each background task gets a dedicated daemon thread that streams output from the PTY file descriptor to the output file.

```
_stream_output(task_id, pty_master_fd, output_file)
│
│  [Runs on daemon thread]
│
├── Create stop_event (threading.Event)
│
├── Loop:
│   │
│   ├── select.select([pty_master_fd], [], [], timeout=0.1)
│   │   │
│   │   ├── fd ready → os.read(pty_master_fd, 4096)
│   │   │   ├── Data received → append to output_file
│   │   │   └── Empty read (EOF) → break loop
│   │   │
│   │   └── timeout → check stop_event
│   │
│   ├── stop_event.is_set()? → break loop
│   │
│   └── Exception (OSError, etc.) → break loop
│
├── Close pty_master_fd
│
└── Thread exits (daemon, dies with process)
```

The select.select() call with 0.1s timeout provides non-blocking reads while remaining responsive to stop signals. The daemon thread flag ensures the thread does not prevent process exit.

## Listener Notification System

External components (UI layers) register callbacks to receive task status change notifications.

```
BackgroundTaskManager
│
├── _listeners: list[Callable[[str, TaskStatus], None]]
│
├── add_listener(callback)
│   └── _listeners.append(callback)
│
├── remove_listener(callback)
│   └── _listeners.remove(callback)
│
└── _notify_listeners(task_id, new_status)
    └── for callback in _listeners:
        └── callback(task_id, new_status)

Example usage:
    TUI status bar registers listener to update task progress indicators
    Web UI registers listener to broadcast WebSocket status updates
```

## Parallel Subagent Execution

When the LLM issues multiple spawn_subagent calls in the same response, the system detects this and executes them concurrently.

```
SubAgentManager.execute_parallel(tasks, deps, ui_callback)
│
├── tasks: list[(agent_name, task_prompt)]
│   e.g., [("code-explorer", "Find auth..."), ("code-explorer", "Find DB...")]
│
├── Create async coroutines:
│   ├── execute_subagent_async("code-explorer", "Find auth...", deps)
│   ├── execute_subagent_async("code-explorer", "Find DB...", deps)
│   └── ...
│
├── results = await asyncio.gather(*coroutines)
│   │
│   │  Each coroutine internally:
│   │  ├── Creates isolated MainAgent with filtered ToolRegistry
│   │  ├── Wraps UI callback in NestedUICallback
│   │  └── agent.run_sync(message=task, history=None)
│   │       └── Full ReAct loop (read-only tools for code-explorer)
│   │
│   └── All agents run concurrently in separate threads
│       (via asyncio.to_thread under the hood)
│
└── Return list of results in original order
```

## Parallel Tool Execution in ReactExecutor

The ReactExecutor manages concurrent tool execution for non-subagent tools.

```
ReactExecutor
│
├── PARALLELIZABLE_TOOLS: set
│   └── Read-only tools safe for concurrent execution
│       (read_file, list_files, search, find_symbol, etc.)
│
├── MAX_CONCURRENT_TOOLS = 5
│
├── ThreadPoolExecutor(max_workers=5)
│
└── execute_tools(tool_calls)
    │
    ├── If all tool_calls are in PARALLELIZABLE_TOOLS:
    │   │
    │   ├── Submit all to ThreadPoolExecutor
    │   │   ├── future_1 = executor.submit(execute_tool, call_1)
    │   │   ├── future_2 = executor.submit(execute_tool, call_2)
    │   │   └── ...
    │   │
    │   ├── Collect results via as_completed()
    │   │
    │   └── Return results in original call order
    │
    └── If any tool_call is NOT parallelizable:
        │
        └── Execute all sequentially
            ├── result_1 = execute_tool(call_1)
            ├── result_2 = execute_tool(call_2)
            └── ...
```

## TaskMonitor

The TaskMonitor tracks timing and token consumption for individual LLM calls and tool executions.

```
TaskMonitor
│
├── __init__(interrupt_token: Optional[InterruptToken] = None)
│
├── State:
│   ├── _description: str
│   ├── _start_time: float
│   ├── _stop_time: Optional[float]
│   ├── _initial_tokens: int
│   ├── _current_tokens: int
│   ├── _interrupt_token: Optional[InterruptToken]
│   └── _lock: threading.Lock
│
├── start(description, initial_tokens) → None
│   └── Record start time and initial token count
│
├── stop() → dict
│   └── Returns {"elapsed_seconds": N, "token_delta": M, "description": "..."}
│
├── update_tokens(current_tokens) → None
│   └── Thread-safe token count update
│
├── request_interrupt() → None
│   └── Delegates to InterruptToken.set()
│
├── should_interrupt() → bool
│   └── Checks InterruptToken.is_set()
│
├── get_elapsed_seconds() → int
│
├── get_token_delta() → int
│   └── current_tokens - initial_tokens
│
└── get_token_arrow() → str
    ├── delta > 0 → "↑"
    ├── delta < 0 → "↓"
    └── delta == 0 → "·"
```

## Interrupt System

The InterruptToken provides centralized, thread-safe cancellation across all active tasks.

```
InterruptToken
│
├── _event: threading.Event
│
├── set() → None
│   └── Signal cancellation to all consumers
│
├── is_set() → bool
│   └── Check if cancellation requested
│
└── clear() → None
    └── Reset for reuse


Usage in ReactExecutor:

ReactExecutor
│
├── _active_interrupt_token: InterruptToken
├── _current_task_monitor: TaskMonitor
│
├── request_interrupt()
│   └── _active_interrupt_token.set()
│       └── All running tools check token on next iteration
│
├── _check_interrupt(phase: str)
│   ├── if _active_interrupt_token.is_set():
│   │   └── raise InterruptError(phase)
│   └── else: continue
│
└── execute() main loop:
    ├── _check_interrupt("pre_llm_call")
    ├── call_llm(messages)
    ├── _check_interrupt("post_llm_call")
    ├── execute_tools(tool_calls)
    ├── _check_interrupt("post_tool_execution")
    └── loop
```

## Concurrency Model

```
Thread Architecture:

Main Thread (REPL / Web Server)
│
├── ReactExecutor Thread (agent loop)
│   │
│   ├── ThreadPoolExecutor (max 5 workers)
│   │   ├── Tool execution worker 1
│   │   ├── Tool execution worker 2
│   │   └── ... up to 5
│   │
│   └── asyncio event loop (for parallel subagents)
│       ├── Subagent thread 1 (via to_thread)
│       ├── Subagent thread 2
│       └── ...
│
├── Background Task Daemon Threads
│   ├── PTY stream thread for task a1b2c3d
│   ├── PTY stream thread for task e5f6g7h
│   └── ...
│
└── Async Hook Threads
    └── ThreadPoolExecutor (max 2 workers, "hook-async" prefix)


Thread Safety Mechanisms:

BackgroundTaskManager:
├── _lock: RLock (reentrant)
│   └── Protects: _tasks dict, _stop_events dict, _output_threads dict
│
TaskMonitor:
├── _lock: Lock
│   └── Protects: token tracking, interrupt state
│
InterruptToken:
├── threading.Event
│   └── Thread-safe by design (Event.set/is_set are atomic)
```

## Bash Tool Background Integration

```
BashTool.run_command(command, run_in_background, ...)
│
├── run_in_background == False:
│   └── Execute synchronously via subprocess.run()
│       └── Return output directly
│
└── run_in_background == True:
    │
    ├── Open PTY pair: master_fd, slave_fd = pty.openpty()
    │
    ├── Start subprocess with PTY:
    │   process = subprocess.Popen(
    │     command, shell=True,
    │     stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
    │     preexec_fn=os.setsid
    │   )
    │
    ├── Register with BackgroundTaskManager:
    │   task = task_manager.register_task(
    │     command=command,
    │     pid=process.pid,
    │     process=process,
    │     pty_master_fd=master_fd,
    │     initial_output=""
    │   )
    │
    └── Return to LLM:
        {"success": True, "task_id": task.task_id,
         "output": "Process started in background..."}
```

## Key Files Reference

| Component | File | Key Elements |
|-----------|------|--------------|
| Task manager | `swecli/core/context_engineering/tools/background_task_manager.py` | BackgroundTaskManager, TaskStatus, BackgroundTask |
| Task monitor | `swecli/core/runtime/monitoring/task_monitor.py` | TaskMonitor, timing/token tracking |
| Subagent manager | `swecli/core/agents/subagents/manager.py` | execute_parallel(), execute_subagent_async() |
| Spawn tool | `swecli/core/agents/subagents/task_tool.py` | spawn_subagent schema, parallel detection |
| Bash tool | `swecli/core/context_engineering/tools/implementations/bash_tool.py` | run_in_background integration |
| React executor | `swecli/repl/react_executor.py` | Parallel tool execution, interrupt support |
