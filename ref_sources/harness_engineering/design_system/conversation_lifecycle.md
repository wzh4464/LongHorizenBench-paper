# Conversation Lifecycle

**Scope**: End-to-end trace of a single user message through the system - from input ingestion to final response delivery and session persistence.

**Key Source Files**:
- `swecli/cli.py` - CLI entry point, non-interactive path
- `swecli/repl/repl.py` - Interactive REPL loop
- `swecli/repl/query_processor.py` - Query enhancement and hook firing
- `swecli/repl/react_executor.py` - ReAct iteration engine (TUI path)
- `swecli/core/agents/main_agent.py` - Agent core with dual execution loop
- `swecli/core/context_engineering/tools/registry.py` - Tool dispatch
- `swecli/core/agents/subagents/manager.py` - Subagent spawning
- `swecli/core/context_engineering/compaction.py` - Staged context optimization
- `swecli/core/context_engineering/history/session_manager.py` - Session persistence
- `swecli/web/websocket.py` - WebSocket message routing
- `swecli/web/agent_executor.py` - Web agent execution bridge

---

## 1. High-Level Flow

A user message passes through twelve distinct phases before the conversation turn is complete:

```
 User Input
    │
    ▼
┌─────────────────────┐
│ 1. Input Ingestion   │  TUI / Web - two entry paths
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 2. Query Processing  │  Enhancement, hooks, message preparation
└─────────┬───────────┘
          ▼
┌─────────────────────────────────────────────────┐
│ 3. ReAct Loop                                    │
│ ┌──────────────────┐  ┌──────────────────────┐  │
│ │ 4. Thinking Phase │→│ 5. Action Phase (LLM) │  │
│ └──────────────────┘  └──────────┬───────────┘  │
│                                  │               │
│          ┌───────────────────────┼─────────┐    │
│          │                       │         │    │
│  ┌───────▼──────┐  ┌────────────▼───┐     │    │
│  │ 6. Tool Exec │  │ 8. Completion  │     │    │
│  └───────┬──────┘  └────────────────┘     │    │
│          │                                 │    │
│  ┌───────▼──────────┐                     │    │
│  │ 7. Subagent Deleg │ (recursive)        │    │
│  └──────────────────┘                     │    │
│                                           │    │
│  ┌──────────────────┐                     │    │
│  │ 9. Compaction     │  (per-iteration)   │    │
│  └──────────────────┘                     │    │
└───────────────────────────────────────────┼────┘
                                            │
┌───────────────────────────────────────────▼────┐
│ 10. Session Persistence                         │
│ 11. Interrupt & Cancellation  (cross-cutting)   │
│ 12. Message Injection         (cross-cutting)   │
└─────────────────────────────────────────────────┘
```

---

## 2. Input Ingestion - Three Entry Paths

The system accepts user input through three distinct interfaces that converge on the same execution core.

### 2a. CLI Non-Interactive (`opendev -p "prompt"`)

```
cli.py:main()
  → _run_non_interactive()
    → Create session, build tool suite
    → agent.run_sync(prompt, deps, message_history)
    → Persist messages to session
```

The simplest path. Creates a one-shot session, runs the agent to completion, persists the result. No REPL loop, no UI callbacks.

**Entry**: `cli.py:_run_non_interactive()`

### 2b. TUI Interactive (`opendev`)

```
cli.py:main()
  → launch_textual_cli()
    → TextualRunner.__init__()
      → _setup_runtime()  → REPL, Config, SessionManager
      → _setup_app()      → SWECLIChatApp (Textual)
    → User types message in ChatTextArea
    → REPL.start() loop:
      → user_input = prompt_session.prompt()
      → if "/command": _handle_command()
      → else: _process_query(user_input)
```

The TUI path wraps a `REPL` instance inside a `TextualRunner`. User input arrives from the Textual `ChatTextArea` widget, gets routed through the REPL's `_process_query()` method, then into QueryProcessor.

**Entry**: `ui_textual/runner.py:TextualRunner`, `repl/repl.py:REPL.start()`

### 2c. Web UI (`opendev run ui`)

```
cli.py:main()
  → _handle_run_command("ui")
    → start_server()  → FastAPI + WebSocket

User sends message via WebSocket:
  → WebSocketManager._handle_query()
    → If agent already running:
        inject_user_message(text)  → message injection queue
    → If idle:
        Add user message to session
        Broadcast to all WS clients
        AgentExecutor.execute_query() in ThreadPoolExecutor
          → _run_agent_sync()
            → agent.run_sync(message, deps, message_history)
```

The Web path runs the agent in a `ThreadPoolExecutor` thread, broadcasting events back to WebSocket clients via `asyncio.run_coroutine_threadsafe`. If the agent is already running when a new message arrives, the message is injected into the live execution via a thread-safe queue.

**Entry**: `web/websocket.py:WebSocketManager._handle_query()`, `web/agent_executor.py:AgentExecutor`

### Convergence Point

All three paths converge at either:
- **TUI path**: `ReactExecutor.execute()` (orchestrated by QueryProcessor)
- **Web/CLI path**: `MainAgent.run_sync()` (direct agent invocation)

Both implementations contain the same ReAct loop structure - the dual implementation exists because the TUI path has richer UI callback integration, while the Web/CLI path is self-contained in MainAgent.

---

## 3. Query Processing

Before entering the ReAct loop, the TUI path applies several pre-processing steps via `QueryProcessor.process_query()`:

```
QueryProcessor.process_query()
  │
  ├─ 1. Persist user message to session
  │     session_manager.add_message(user_msg)
  │
  ├─ 2. Fire topic detection
  │     TopicDetector extracts title from first message
  │
  ├─ 3. Fire UserPromptSubmit hook
  │     External hooks can inspect/modify the query
  │     If hook blocks → abort query processing
  │
  ├─ 4. Enhance query
  │     QueryEnhancer: expand @file references → inline file contents
  │
  ├─ 5. Prepare messages for API
  │     QueryEnhancer.prepare_messages() → OpenAI-format message list
  │
  ├─ 6. Inject plan mode signal (if Shift+Tab was pressed)
  │     Append special reminder message for plan subagent
  │
  └─ 7. Delegate to ReactExecutor.execute()
```

The Web/CLI paths skip this processing - the agent's `run_sync()` receives raw messages directly.

**Source**: `repl/query_processor.py:QueryProcessor.process_query()`

---

## 4. The ReAct Loop

The core execution engine follows the Reason-Act-Observe pattern. Each iteration of the loop is one complete cycle of LLM reasoning + tool execution.

```
ReactExecutor.execute() / MainAgent.run_sync()
  │
  ├─ Create InterruptToken for this run
  ├─ Wrap messages in ValidatedMessageList
  ├─ Insert system prompt as messages[0]
  ├─ Append user message
  │
  └─ while True:
       │
       ├─ Drain injected messages from queue
       ├─ Check interrupt token / task monitor
       ├─ Check safety limit (MAX_REACT_ITERATIONS = 200)
       │
       ├─ _run_iteration() / inline iteration logic:
       │   ├─ Auto-compact (Phase 9)
       │   ├─ Check interrupt ("pre-thinking")
       │   ├─ Thinking phase (Phase 4, optional)
       │   ├─ Check interrupt ("post-thinking")
       │   ├─ Drain injected messages (arrived during thinking)
       │   ├─ Check interrupt ("pre-action")
       │   ├─ Action phase - call LLM with tools (Phase 5)
       │   ├─ Calibrate compactor with API token count
       │   │
       │   ├─ If NO tool calls → completion logic (Phase 8)
       │   └─ If tool calls → tool execution (Phase 6)
       │
       ├─ If LoopAction.BREAK and injection queue empty → exit
       └─ If LoopAction.BREAK but queue has messages → continue
```

The loop exits when:
- The agent produces a response with no tool calls (implicit completion)
- The agent calls `task_complete` (explicit completion)
- Interrupt is signaled (user cancellation)
- Max iterations reached (safety cap)
- An unrecoverable error occurs

**Source**: `repl/react_executor.py:ReactExecutor.execute()`, `core/agents/main_agent.py:MainAgent.run_sync()`

---

## 5. Thinking Phase (Optional)

When thinking mode is enabled, a separate LLM call generates a reasoning trace *before* the action phase. This separates deliberation from tool selection.

```
Thinking phase (ReactExecutor._get_thinking_trace):
  │
  ├─ Build thinking-specific system prompt
  │   agent.build_system_prompt(thinking_visible=True)
  │
  ├─ Clone messages with swapped system prompt
  │   _build_messages_with_system_prompt(messages, thinking_prompt)
  │
  ├─ Append analysis prompt as final user message
  │   get_reminder("thinking_analysis_prompt")
  │
  ├─ Call LLM WITHOUT tools (pure reasoning)
  │   agent.call_thinking_llm(thinking_messages, task_monitor)
  │
  ├─ Display trace in UI
  │   ui_callback.on_thinking(thinking_trace)
  │
  └─ [Optional] Self-critique phase (when thinking level = High):
      ├─ Critique: agent.call_critique_llm(thinking_trace)
      ├─ Refine: agent.call_thinking_llm(refinement_messages)
      └─ Return refined trace

After thinking completes:
  └─ Inject trace as user message for the action phase:
      messages.append({"role": "user", "content": f"<thinking_trace>{trace}</thinking_trace>"})
```

The thinking phase is skipped when:
- Thinking mode is OFF (`thinking_handler.is_visible == False`)
- A subagent just completed (the main agent should decide directly)

**Models involved**:
- `call_thinking_llm()` - may use a different model/provider (`model_thinking` config)
- `call_critique_llm()` - may use yet another model (`model_critique` config)

**Source**: `repl/react_executor.py:ReactExecutor._get_thinking_trace()`, `core/agents/main_agent.py:MainAgent.call_thinking_llm()`

---

## 6. Action Phase (LLM Call with Tools)

The action phase calls the LLM with the full tool schema, allowing it to select zero or more tools to invoke.

```
Action phase:
  │
  ├─ Resolve model and HTTP client
  │   _resolve_vlm_model_and_client(messages)
  │   Routes to VLM model if images are present in messages
  │
  ├─ Build tool schemas
  │   _schema_builder.build(thinking_visible=False)
  │   Filtered by allowed_tools for subagents
  │
  ├─ POST to LLM API:
  │   {
  │     "model": model_id,
  │     "messages": messages,
  │     "tools": tool_schemas,
  │     "tool_choice": "auto",
  │     "temperature": ...,
  │     "max_tokens": ...
  │   }
  │
  └─ Parse response:
      ├─ content: assistant's text response
      ├─ tool_calls: list of tool invocations (may be empty)
      ├─ reasoning_content: native thinking from o1/o3 models
      └─ usage: token counts for compactor calibration
```

**HTTP Clients** are lazily initialized per provider:
- `_http_client` - primary model
- `_thinking_http_client` - thinking model (if different provider)
- `_critique_http_client` - critique model (if different provider)
- `_vlm_http_client` - vision/language model (if different provider)

**Source**: `core/agents/main_agent.py:MainAgent.call_llm()`

---

## 7. Tool Dispatch & Execution

When the LLM returns tool calls, each is dispatched through the ToolRegistry.

```
For each tool_call in response.tool_calls:
  │
  ├─ Parse: tool_name, arguments (JSON)
  │
  ├─ Special: task_complete
  │   → Check todo completion
  │   → Check injection queue
  │   → Return with completion status
  │
  ├─ Notify UI: ui_callback.on_tool_call(tool_name, args)
  │
  ├─ ToolRegistry.execute_tool(tool_name, args, managers...):
  │   │
  │   ├─ Auto-discover MCP tools if "mcp__" prefix
  │   │
  │   ├─ Build ToolExecutionContext:
  │   │   mode_manager, approval_manager, undo_manager,
  │   │   task_monitor, session_manager, ui_callback, is_subagent
  │   │
  │   ├─ Run PreToolUse hooks:
  │   │   Can BLOCK execution or MODIFY arguments
  │   │
  │   ├─ Route to handler:
  │   │   FileToolHandler, ProcessToolHandler, WebToolHandler,
  │   │   McpToolHandler, ThinkingHandler, TodoHandler, etc.
  │   │
  │   ├─ Run PostToolUse / PostToolUseFailure hooks (async)
  │   │
  │   └─ Return: {success, output, error, interrupted, ...}
  │
  ├─ Check for interruption
  │
  ├─ Notify UI: ui_callback.on_tool_result(tool_name, args, result)
  │
  └─ Append tool result message:
      {
        "role": "tool",
        "tool_call_id": "call_xyz",
        "content": "tool output" or "Error: message"
      }
```

**Parallel Execution**: Read-only tools can run in parallel (up to `MAX_CONCURRENT_TOOLS = 5`) using a persistent `ThreadPoolExecutor`. Tools eligible for parallelization are listed in `PARALLELIZABLE_TOOLS`:
- `read_file`, `list_files`, `search`, `fetch_url`, `web_search`, `capture_web_screenshot`, `analyze_image`, `list_processes`, `get_process_output`, `list_todos`, `search_tools`, `find_symbol`, `find_referencing_symbols`

**Source**: `core/context_engineering/tools/registry.py:ToolRegistry.execute_tool()`

---

## 8. Subagent Delegation

When the agent calls `spawn_subagent`, the SubAgentManager creates an isolated child execution.

```
SubAgentManager.execute_subagent(name, task, deps, ...):
  │
  ├─ Fire SubagentStart hook (can block)
  │
  ├─ Create NestedUICallback:
  │   Wraps parent ui_callback with depth tracking
  │   Nested tool calls attributed to parent tool_call_id
  │
  ├─ Execute child agent:
  │   agent.run_sync(
  │     message=task,
  │     deps=deps,
  │     message_history=None,     ← Fresh context (no parent history)
  │     ui_callback=nested_cb,
  │     max_iterations=None,      ← Unlimited iterations
  │     task_monitor=task_monitor  ← Interrupt propagation
  │   )
  │
  ├─ Fire SubagentStop hook
  │
  └─ Return to parent:
      {
        success: bool,
        output: "brief summary",
        separate_response: "full response shown as assistant message",
        completion_status: "success" or "failed",
        subagent_type: "code_explorer" | "planner" | ...
      }
```

**Isolation model**:
- Subagents receive NO parent conversation history (`message_history=None`)
- Tool access is filtered by `allowed_tools` in the subagent spec
- Interrupt tokens propagate from parent to child
- Results flow back as tool messages in the parent conversation

**After subagent completion**:
- Thinking phase is skipped for the next iteration (agent decides directly)
- A continuation signal is injected: `get_reminder("subagent_complete_signal")`

**Source**: `core/agents/subagents/manager.py:SubAgentManager.execute_subagent()`

---

## 9. Completion & Nudging

The loop supports two completion paths, both guarded by validation.

### Implicit Completion (no tool calls)

When the LLM returns text without tool calls, the system checks:

```
No tool calls detected:
  │
  ├─ Was the last tool execution a failure?
  │   YES → Smart nudge (error-type-specific):
  │         _classify_error() → "permission_error" | "edit_mismatch" | "file_not_found" | ...
  │         _get_smart_nudge() → inject nudge message, continue loop
  │         After MAX_NUDGE_ATTEMPTS (3) → fall through to completion
  │
  ├─ Are there incomplete todos?
  │   YES → Todo nudge (up to MAX_TODO_NUDGES = 2):
  │         "You have N incomplete tasks: • task1 • task2"
  │         After 2 nudges → allow completion anyway
  │
  ├─ Are there injected messages in the queue?
  │   YES → Drain messages, reset counters, continue loop
  │
  ├─ Is the completion content empty?
  │   YES → Send completion_summary_nudge once, continue
  │
  └─ Accept completion → return {success: True, content: cleaned_content}
```

### Explicit Completion (`task_complete` tool)

```
task_complete called:
  │
  ├─ If status == "success":
  │   Check todo completion → nudge if incomplete
  │
  ├─ Check injection queue:
  │   If messages pending → defer completion, add "Completion deferred" tool result
  │
  └─ Return {success: status != "failed", content: summary}
```

**Source**: `repl/react_executor.py:_handle_no_tool_calls()`, `core/agents/main_agent.py` (inline completion logic)

---

## 10. Staged Context Compaction

Context compaction runs at the start of each iteration, before the thinking phase. It applies progressively aggressive optimization as the context window fills.

```
Thresholds (fraction of context window):
  70% → WARNING   (log only)
  80% → MASK      (replace old tool results with compact refs)
  90% → AGGRESSIVE (keep only recent 3 tool results intact)
  99% → COMPACT   (full LLM-powered summarization)
```

### Observation Masking (80–90%)

In-place mutation of old tool result messages:

```
Before: {"role": "tool", "content": "... 5000 chars of file contents ..."}
After:  {"role": "tool", "content": "[ref: tool result call_abc - see history]"}

MASK level:      Keep recent 6 tool results intact
AGGRESSIVE level: Keep recent 3 tool results intact
```

### Full Compaction (99%)

```
compact(messages, system_prompt):
  │
  ├─ Archive full history to ~/.opendev/scratch/{session_id}/
  │
  ├─ Split messages:
  │   head = messages[:1]                    (system prompt)
  │   middle = messages[1:-keep_recent]      (to summarize)
  │   tail = messages[-keep_recent:]         (keep intact)
  │   keep_recent = min(5, max(2, len(messages) / 3))
  │
  ├─ Summarize middle via LLM:
  │   Model: compact_model (gpt-4o-mini or configured)
  │   Temperature: 0.2
  │   Max tokens: 1024
  │   Tool results sanitized (limited to 200 chars)
  │
  ├─ Inject artifact index (files touched this session)
  │
  └─ Return: head + [summary_msg] + tail
      (e.g., 50+ messages → 7-10 messages)
```

### Token Calibration

The compactor calibrates itself using real API token counts:

```
After each LLM response:
  if response.usage.prompt_tokens > 0:
    compactor.update_from_api_usage(prompt_tokens, message_count)
    → Adjusts internal token estimate for more accurate threshold checks
```

**Source**: `core/context_engineering/compaction.py:ContextCompactor`

---

## 11. Session Persistence

### Storage Format

```
~/.opendev/projects/{encoded-project-path}/
  ├─ sessions-index.json        (lightweight metadata for all sessions)
  ├─ {session_id}.json          (session metadata: id, timestamps, channel)
  └─ {session_id}.jsonl         (message transcript, one JSON object per line)
```

### Write Points

Messages are persisted at the following points:

| When | What | Who |
|------|------|-----|
| User submits query | User message | QueryProcessor / WebSocketManager |
| Agent responds | Assistant message (text + tool_calls) | ReactExecutor / MainAgent |
| Tool executes | Tool result message | ReactExecutor / MainAgent |
| Injected message consumed | User message | `_drain_injected_messages()` |
| Loop exits | Final session save | `execute()` finally block |
| Compaction occurs | Compaction metadata | `_maybe_compact()` |

### Session Index

The `sessions-index.json` file is a lightweight cache for the session browser:
```json
[{
  "sessionId": "a1b2c3d4",
  "created": "2026-02-27T10:00:00",
  "modified": "2026-02-27T10:30:00",
  "messageCount": 42,
  "totalTokens": 15000,
  "title": "Refactor login module",
  "summary": "..."
}]
```

Self-healing: if the index is missing or corrupted, it is automatically rebuilt by scanning `.json` and `.jsonl` files on disk.

**Source**: `core/context_engineering/history/session_manager.py:SessionManager`

---

## 12. Interrupt & Cancellation

Interrupts are thread-safe and checked at every phase boundary in the ReAct loop.

### InterruptToken

Created fresh for each `execute()` / `run_sync()` call:

```python
class InterruptToken:
    def request(self) -> None:     # Signal interrupt
    def is_requested(self) -> bool # Poll status
```

### Signal Sources

```
TUI: ESC key
  → InterruptManager.request_interrupt()
    → _active_interrupt_token.request()
    → _current_task_monitor.request_interrupt()

Web: Interrupt button
  → web_state.request_interrupt()
  → task_monitor.should_interrupt() returns True
```

### Check Points

The token is polled at six phase boundaries within each iteration:

```
1. Iteration boundary    (top of while loop)
2. Pre-thinking          (before thinking LLM call)
3. During thinking       (HTTP client checks mid-request)
4. Post-thinking         (after thinking returns)
5. Pre-action            (before action LLM call)
6. During tool execution (tool result can set interrupted=True)
```

### Cleanup

```
finally:
  ├─ Call ui_callback.on_interrupt() if not already called
  ├─ Clear token from InterruptManager
  ├─ Set _active_interrupt_token = None
  ├─ Drain orphan messages from injection queue
  ├─ Save session metadata
  ├─ Fire Stop hook (can log but cannot re-enter loop)
  └─ Play finish sound (unless interrupted)
```

**Source**: `repl/react_executor.py` (finally block), `core/runtime/interrupt_token.py`

---

## 13. Live Message Injection

Users can send new messages while the agent is executing. These are delivered via a thread-safe queue and consumed at iteration boundaries.

```
Injection flow:
  │
  ├─ Producer (UI thread):
  │   inject_user_message(text)
  │     → _injection_queue.put_nowait(text)
  │     Queue capacity: 10 (excess messages dropped with warning)
  │
  └─ Consumer (agent thread):
      _drain_injected_messages(ctx, max_per_drain=3):
        for each message in queue (up to 3):
          ├─ Persist to session
          ├─ Append to messages list
          └─ Fire _on_message_consumed callback

Drain points:
  1. Top of each iteration (before any LLM call)
  2. Between thinking and action phases
  3. Before accepting completion (prevents premature exit)

Orphan handling (loop already exited):
  Final drain in finally block:
    → _on_orphan_message callback (re-queue for next execution)
    → Fallback: persist directly to session
```

**Key invariant**: Completion is always deferred if the injection queue is non-empty. This ensures no user message is silently dropped.

**Source**: `repl/react_executor.py:_drain_injected_messages()`, `core/agents/main_agent.py:_drain_injected_messages()`

---

## 14. Message Format

All messages flowing through the system use the OpenAI chat format:

```
System message:
  {"role": "system", "content": "...assembled system prompt..."}

User message:
  {"role": "user", "content": "user query or injected content"}

Assistant message:
  {"role": "assistant", "content": "text response", "tool_calls": [...]}

Tool result:
  {"role": "tool", "tool_call_id": "call_xyz", "content": "output or Error: msg"}
```

### ValidatedMessageList

Messages are wrapped in `ValidatedMessageList` which enforces invariants on every write:
- Every `tool_call` in an assistant message must have a matching `tool` result message
- System message (if present) must be at index 0
- No orphaned tool results without preceding assistant tool_calls

### Special Message Content

- **Thinking trace injection**: `<thinking_trace>...</thinking_trace>` appended as user message
- **Subagent completion signal**: `[completion_status=success]` or `[completion_status=failed]` prepended to tool result
- **LLM-only suffix**: `result["_llm_suffix"]` appended to tool content - visible to LLM but not displayed in UI
- **Compaction summary**: `[CONVERSATION SUMMARY] ...` replaces middle messages after full compaction
- **Observation mask**: `[ref: tool result {id} - see history]` replaces old tool outputs

---

## 15. Execution Path Comparison

| Aspect | TUI (ReactExecutor) | Web/CLI (MainAgent.run_sync) |
|--------|---------------------|------------------------------|
| Entry | `ReactExecutor.execute()` | `MainAgent.run_sync()` |
| Iteration | `_run_iteration()` method | Inline while loop |
| Thinking | Separate `_get_thinking_trace()` | Not available |
| Critique | `_critique_and_refine_thinking()` | Not available |
| Tool execution | Via `ToolExecutor` | Via `tool_registry.execute_tool()` |
| Parallel tools | `ThreadPoolExecutor` | Sequential |
| UI callbacks | `TextualUICallback` | Optional `ui_callback` |
| Compaction | Staged (70/80/90/99%) | Binary (99% only) |
| Interrupt | `InterruptToken` + `TaskMonitor` | `TaskMonitor` or `WebInterruptMonitor` |
| Hooks | Full lifecycle hooks | Limited hook support |
| Context usage | Pushed to UI | Stored in session metadata |
| Sound | Play on non-interrupted completion | Play on non-interrupted completion |

---

## Appendix: Complete Sequence Diagram

```
User          UI Layer         QueryProcessor    ReactExecutor       MainAgent         ToolRegistry
  │               │                  │                │                  │                  │
  │─ input ──────▶│                  │                │                  │                  │
  │               │─ process_query ─▶│                │                  │                  │
  │               │                  │─ add_message() │                  │                  │
  │               │                  │─ fire hooks ───│                  │                  │
  │               │                  │─ enhance query │                  │                  │
  │               │                  │─ execute() ───▶│                  │                  │
  │               │                  │                │                  │                  │
  │               │                  │                │── drain queue ──│                  │
  │               │                  │                │── compact ──────│                  │
  │               │                  │                │── thinking ─────▶│ call_thinking    │
  │               │                  │                │◀─ trace ────────│                  │
  │               │                  │                │── action ───────▶│ call_llm         │
  │               │                  │                │◀─ tool_calls ───│                  │
  │               │                  │                │                  │                  │
  │               │                  │                │─── for each tool_call ────────────▶│
  │               │◀─ on_tool_call ──│                │                  │  execute_tool()  │
  │               │                  │                │◀─── result ──────────────────────── │
  │               │◀─ on_tool_result │                │                  │                  │
  │               │                  │                │                  │                  │
  │               │                  │                │── (loop continues until completion) │
  │               │                  │                │                  │                  │
  │               │                  │                │── save session ──│                  │
  │               │                  │◀─ result ──────│                  │                  │
  │               │◀─ display ───────│                │                  │                  │
  │◀── response ──│                  │                │                  │                  │
```
