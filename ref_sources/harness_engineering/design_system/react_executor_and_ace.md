# ReAct Executor & Agentic Context Engineering (ACE)

**Scope**: Complete architecture of the ReAct execution loop and the ACE memory system - how a single user message is processed through thinking, action, tool execution, system reminders, context compaction, and long-term learning.

**Key Source Files**:
- `swecli/repl/react_executor.py` - ReAct iteration engine, injection queue, compaction, parallel tools
- `swecli/core/agents/main_agent.py` - Agent core, smart nudge, todo gate, LLM callers
- `swecli/core/context_engineering/compaction.py` - Staged compaction (70/80/90/99%)
- `swecli/core/context_engineering/memory/playbook.py` - Bullet store, effectiveness scoring
- `swecli/core/context_engineering/memory/roles.py` - Reflector + Curator (LLM-powered)
- `swecli/core/context_engineering/memory/delta.py` - DeltaOperation (ADD/UPDATE/TAG/REMOVE)
- `swecli/core/context_engineering/memory/selector.py` - BulletSelector, weighted scoring
- `swecli/core/context_engineering/memory/conversation_summarizer.py` - Episodic memory
- `swecli/core/context_engineering/memory/embeddings.py` - Embedding cache, cosine similarity

---

## Master Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         ReactExecutor.execute()                                                │
│                                                                                                                │
│  ┌─── Initialization ─────────────────────────────────────────────────────────────────────────────────────┐     │
│  │  Clear injection queue ─→ Create InterruptToken ─→ Wrap in ValidatedMessageList ─→ IterationContext   │     │
│  └───────────────────────────────────────────────────────────────────────────────────────────────────────┘     │
│                                                    │                                                          │
│                             ┌───────────────── while True ──────────────────┐                                 │
│                             │                                               │                                 │
│  ┌──────────────────────────▼───────────────────────────────────────────────────────────────────────────────┐  │
│  │                            _run_iteration_inner()                                                        │  │
│  │                                                                                                          │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │ PHASE 0 - CONTEXT MANAGEMENT                                                                       │  │  │
│  │  │                                                                                                     │  │  │
│  │  │  _drain_injected_messages()         _maybe_compact()                                                │  │  │
│  │  │  ┌─────────────────────────┐        ┌──────────────────────────────────────────────────────────┐    │  │  │
│  │  │  │ injection_queue (max 10)│        │  ContextCompactor.check_usage(messages, system_prompt)   │    │  │  │
│  │  │  │ Thread-safe queue from  │        │                                                          │    │  │  │
│  │  │  │ UI thread, drained into │        │  Token Usage    OptimizationLevel    Action               │    │  │  │
│  │  │  │ ctx.messages as         │        │  ──────────────────────────────────────────────────────   │    │  │  │
│  │  │  │ role: user messages     │        │  < 70%          NONE                 (nothing)            │    │  │  │
│  │  │  │ (max 3 per drain)       │        │  ≥ 70%          WARNING              log warning          │    │  │  │
│  │  │  └─────────────────────────┘        │  ≥ 80%          MASK                 mask old tool results │    │  │  │
│  │  │                                      │                                      (keep recent 6)      │    │  │  │
│  │  │                                      │  ≥ 90%          AGGRESSIVE           aggressive masking   │    │  │  │
│  │  │                                      │                                      (keep recent 3)      │    │  │  │
│  │  │                                      │  ≥ 99%          COMPACT              LLM summarization    │    │  │  │
│  │  │                                      │                                      head + [SUMMARY] +   │    │  │  │
│  │  │                                      │                                      tail                 │    │  │  │
│  │  │                                      └──────────────────────────────────────────────────────────┘    │  │  │
│  │  └─────────────────────────────────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                    │                                                      │  │
│  │                                     _check_interrupt("pre-thinking")                                      │  │
│  │                                                    │                                                      │  │
│  │  ┌─────────────────────────────────────────────────▼───────────────────────────────────────────────────┐  │  │
│  │  │ PHASE 1 - THINKING (if thinking_visible && !subagent_just_completed)                                │  │  │
│  │  │                                                                                                     │  │  │
│  │  │  _get_thinking_trace()                        _critique_and_refine_thinking()                       │  │  │
│  │  │  ┌──────────────────────────────────┐         ┌──────────────────────────────────┐                  │  │  │
│  │  │  │ Build thinking-specific sys prompt│         │ (if thinking_level == SELF_CRIT) │                  │  │  │
│  │  │  │ Clone messages (no tools)         │────────→│ Critique model evaluates trace   │                  │  │  │
│  │  │  │ Append thinking_analysis_prompt   │         │ Thinking model refines with      │                  │  │  │
│  │  │  │ Call thinking LLM (NO tools)      │         │ critique as additional input      │                  │  │  │
│  │  │  │ Return: thinking trace string     │         └──────────────┬───────────────────┘                  │  │  │
│  │  │  └──────────────────────────────────┘                        │                                      │  │  │
│  │  │                                                              ▼                                      │  │  │
│  │  │                                              💉 thinking_trace_reminder                              │  │  │
│  │  │                                              Inject trace as role: user message                      │  │  │
│  │  └─────────────────────────────────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                    │                                                      │  │
│  │  ┌─────────────────────────────────────────────────▼───────────────────────────────────────────────────┐  │  │
│  │  │ PHASE 1b - POST-SUBAGENT SIGNAL                                                                     │  │  │
│  │  │                                                                                                     │  │  │
│  │  │  if subagent_just_completed && !continue_after_subagent:                                            │  │  │
│  │  │      💉 subagent_complete_signal                                                                     │  │  │
│  │  │      "All subagents completed. Evaluate results and continue."                                      │  │  │
│  │  └─────────────────────────────────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                    │                                                      │  │
│  │                               _drain_injected_messages() + _check_interrupt("pre-action")                 │  │
│  │                                                    │                                                      │  │
│  │  ┌─────────────────────────────────────────────────▼───────────────────────────────────────────────────┐  │  │
│  │  │ PHASE 2 - ACTION (LLM call with tools)                                                              │  │  │
│  │  │                                                                                                     │  │  │
│  │  │  call_llm_with_progress(agent, messages, task_monitor)                                              │  │  │
│  │  │  ┌──────────────────────────────────────────────────────────────────────────────┐                    │  │  │
│  │  │  │ Build action system prompt (PromptComposer, 18 sections)                     │                    │  │  │
│  │  │  │ Include all tool schemas                                                     │                    │  │  │
│  │  │  │ Include playbook.as_context(query, max_strategies=30)  ← ACE bullets         │                    │  │  │
│  │  │  │ Send to LLM API                                                              │                    │  │  │
│  │  │  │ Parse: content, tool_calls[], reasoning_content                              │                    │  │  │
│  │  │  │ Calibrate compactor with API prompt_tokens                                   │                    │  │  │
│  │  │  └──────────────────────────────────────────────────────────────────────────────┘                    │  │  │
│  │  └───────────────────────────┬───────────────────────────────────────────┬─────────────────────────────┘  │  │
│  │                              │                                           │                                │  │
│  │                     tool_calls == []                             tool_calls != []                          │  │
│  │                              │                                           │                                │  │
│  │  ┌───────────────────────────▼──────────────────┐  ┌─────────────────────▼──────────────────────────────┐  │  │
│  │  │ PHASE 3a - NO TOOL CALLS                      │  │ PHASE 3b - TOOL EXECUTION                         │  │  │
│  │  │ _handle_no_tool_calls()                       │  │ _process_tool_calls()                              │  │  │
│  │  │                                               │  │                                                    │  │  │
│  │  │  ┌─ Last tool failed?                         │  │  ┌─ Has task_complete?                             │  │  │
│  │  │  │  YES:                                      │  │  │  YES:                                           │  │  │
│  │  │  │  consecutive_no_tool_calls++               │  │  │  ├─ Check todos (if status=success)             │  │  │
│  │  │  │  ├─ ≥ MAX_NUDGE_ATTEMPTS (3)?             │  │  │  │  └─ 💉 incomplete_todos_nudge → CONTINUE     │  │  │
│  │  │  │  │  └─ BREAK (accept failure)              │  │  │  ├─ Check injection queue                      │  │  │
│  │  │  │  └─ _get_smart_nudge()                     │  │  │  └─ → BREAK                                    │  │  │
│  │  │  │     _classify_error() →                    │  │  │                                                 │  │  │
│  │  │  │     permission | edit_mismatch |           │  │  │  NO:                                            │  │  │
│  │  │  │     file_not_found | syntax |              │  │  │  ┌─ Decide execution strategy ──────────────┐  │  │  │
│  │  │  │     rate_limit | timeout | generic         │  │  │  │ All spawn_subagent?  → parallel agents   │  │  │  │
│  │  │  │     💉 nudge_{type} → CONTINUE             │  │  │  │ All PARALLELIZABLE?  → silent parallel   │  │  │  │
│  │  │  │                                            │  │  │  │ Otherwise?           → sequential         │  │  │  │
│  │  │  │  NO:                                       │  │  │  └──────────────────────────────────────────┘  │  │  │
│  │  │  │  ├─ Incomplete todos?                      │  │  │                                                 │  │  │
│  │  │  │  │  (todo_nudge_count < MAX_TODO_NUDGES=2) │  │  │  Execute tools (parallel or sequential)         │  │  │
│  │  │  │  │  💉 incomplete_todos_nudge → CONTINUE   │  │  │  ┌──────────────────────────────────────────┐  │  │  │
│  │  │  │  │                                         │  │  │  │ For each tool_call:                      │  │  │  │
│  │  │  │  ├─ Injection queue not empty?             │  │  │  │  _check_interrupt("pre-tool")            │  │  │  │
│  │  │  │  │  → CONTINUE                             │  │  │  │  _execute_single_tool()                  │  │  │  │
│  │  │  │  │                                         │  │  │  │  ├─ UI: on_tool_call(name, args)         │  │  │  │
│  │  │  │  ├─ Empty content? (silent finish)         │  │  │  │  ├─ registry.execute_tool()              │  │  │  │
│  │  │  │  │  (!completion_nudge_sent)               │  │  │  │  ├─ UI: on_tool_result(name, result)     │  │  │  │
│  │  │  │  │  💉 completion_summary_nudge → CONTINUE │  │  │  │  └─ Return result dict                   │  │  │  │
│  │  │  │  │                                         │  │  │  └──────────────────────────────────────────┘  │  │  │
│  │  │  │  └─ Has content → BREAK (implicit done)    │  │  │                                                 │  │  │
│  │  │  │                                            │  │  │  Post-tool signals:                              │  │  │
│  │  │  └────────────────────────────────────────────│  │  │  ├─ 💉 plan_approved_signal (once)              │  │  │
│  │  └───────────────────────────────────────────────┘  │  │  ├─ 💉 all_todos_complete_nudge (once)          │  │  │
│  │                                                      │  │  ├─ 💉 tool_denied_nudge (if denied)           │  │  │
│  │                                                      │  │  ├─ 💉 consecutive_reads_nudge (if ≥5 reads)   │  │  │
│  │                                                      │  │  │                                              │  │  │
│  │                                                      │  │  └─ → CONTINUE                                 │  │  │
│  │                                                      │  └────────────────────────────────────────────────┘  │  │
│  │                                                      │                       │                              │  │
│  │  ┌───────────────────────────────────────────────────┴───────────────────────▼──────────────────────────┐  │  │
│  │  │ PHASE 4 - PERSIST & LEARN                                                                            │  │  │
│  │  │                                                                                                      │  │  │
│  │  │  _persist_step()                                                                                     │  │  │
│  │  │  ┌────────────────────────────────────────────────────────────────────────────────────────┐           │  │  │
│  │  │  │ Build ChatMessage(role=ASSISTANT, content, tool_calls,                                  │           │  │  │
│  │  │  │                   thinking_trace, reasoning_content, token_usage)                       │           │  │  │
│  │  │  │ session_manager.add_message(msg)                                                       │           │  │  │
│  │  │  │ record_tool_learnings(query, tool_calls, outcome, agent)  ← ACE learning trigger       │           │  │  │
│  │  │  └────────────────────────────────────────────────────────────────────────────────────────┘           │  │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                    │                                                          │
│                                          LoopAction.BREAK?                                                    │
│                                         ┌──── YES ────┐                                                      │
│                                         │             │                                                      │
│                                         │  injection_queue empty?                                             │
│                                         │  YES → break                                                       │
│                                         │  NO  → continue (process new messages)                              │
│                                         └─────────────┘                                                      │
│                                                                                                                │
│  ┌─── Finally ─────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  Clear InterruptToken · Final drain injection queue · _on_orphan_message() for remaining                │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ACE Memory Pipeline

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                              Agentic Context Engineering (ACE)                                │
│                                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ GENERATOR (Main Agent)                                                                   │ │
│  │                                                                                          │ │
│  │  User query ──→ System prompt + Playbook bullets ──→ LLM ──→ Response + Tool calls       │ │
│  │                       ▲                                            │                      │ │
│  │                       │                                            ▼                      │ │
│  │           ┌───────────┴────────┐                     ┌─────────────────────────┐         │ │
│  │           │ BulletSelector     │                     │ Tool execution results  │         │ │
│  │           │ ┌───────────────┐  │                     └────────────┬────────────┘         │ │
│  │           │ │ Scoring:      │  │                                  │                      │ │
│  │           │ │  effective×0.5│  │                                  │                      │ │
│  │           │ │  recency ×0.3│  │                                  ▼                      │ │
│  │           │ │  semantic×0.2│  │               record_tool_learnings()                   │ │
│  │           │ └───────────────┘  │                                  │                      │ │
│  │           │ Top-K selection    │                                  │                      │ │
│  │           │ (max 30 bullets)   │                                  │                      │ │
│  │           └────────────────────┘                                  │                      │ │
│  └──────────────────────────────────────────────────────────────────┼──────────────────────┘ │
│                                                                     │                        │
│  ┌──────────────────────────────────────────────────────────────────▼──────────────────────┐ │
│  │ REFLECTOR (LLM-powered analysis)                                                        │ │
│  │                                                                                          │ │
│  │  Inputs:                                        Output: ReflectorOutput                  │ │
│  │  ┌──────────────────────────┐                   ┌──────────────────────────────────────┐ │ │
│  │  │ question (user query)    │                   │ reasoning: str                       │ │ │
│  │  │ agent_response (content  │                   │ error_identification: str             │ │ │
│  │  │   + tool_calls)          │──→ LLM call ──→  │ root_cause_analysis: str              │ │ │
│  │  │ playbook (current state) │    (JSON output)  │ correct_approach: str                │ │ │
│  │  │ ground_truth (optional)  │                   │ key_insight: str                     │ │ │
│  │  │ feedback (exec result)   │                   │ bullet_tags: [{id, tag}]             │ │ │
│  │  └──────────────────────────┘                   └───────────────────┬──────────────────┘ │ │
│  │                                                                     │                    │ │
│  │  JSON retry: up to 3 attempts, strips markdown fences               │                    │ │
│  │  💉 json_retry_simple on parse failure                              │                    │ │
│  └─────────────────────────────────────────────────────────────────────┼────────────────────┘ │
│                                                                        │                      │
│  ┌─────────────────────────────────────────────────────────────────────▼────────────────────┐ │
│  │ CURATOR (LLM-powered mutation planning)                                                  │ │
│  │                                                                                          │ │
│  │  Inputs:                                        Output: CuratorOutput                    │ │
│  │  ┌──────────────────────────┐                   ┌──────────────────────────────────────┐ │ │
│  │  │ reflection (from above)  │                   │ delta: DeltaBatch                    │ │ │
│  │  │ playbook (current state) │──→ LLM call ──→  │   reasoning: str                    │ │ │
│  │  │ question_context         │    (JSON output)  │   operations: [DeltaOperation]      │ │ │
│  │  │ progress (task status)   │                   │     ├─ ADD(section, content)         │ │ │
│  │  └──────────────────────────┘                   │     ├─ UPDATE(bullet_id, content)    │ │ │
│  │                                                  │     ├─ TAG(bullet_id, metadata)      │ │ │
│  │  JSON retry: up to 3 attempts                    │     └─ REMOVE(bullet_id)             │ │ │
│  │  💉 json_retry_with_fields on parse failure      └───────────────────┬──────────────────┘ │ │
│  └──────────────────────────────────────────────────────────────────────┼────────────────────┘ │
│                                                                         │                      │
│  ┌──────────────────────────────────────────────────────────────────────▼────────────────────┐ │
│  │ PLAYBOOK (Bullet store)                                                                   │ │
│  │                                                                                           │ │
│  │  playbook.apply_delta(delta)                                                              │ │
│  │                                                                                           │ │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────────┐  │ │
│  │  │ Bullet                                                                              │  │ │
│  │  │ ┌────────────┬──────────────┬──────────────────────────────┬──────────┬──────────┐  │  │ │
│  │  │ │ id         │ section      │ content                      │ helpful  │ harmful  │  │  │ │
│  │  │ ├────────────┼──────────────┼──────────────────────────────┼──────────┼──────────┤  │  │ │
│  │  │ │ fil-00001  │ file_ops     │ List directory before reading│ 5        │ 0        │  │  │ │
│  │  │ │ err-00003  │ error_recov  │ Re-read file after edit fail │ 12       │ 1        │  │  │ │
│  │  │ │ tst-00007  │ testing      │ Run tests after each edit    │ 8        │ 2        │  │  │ │
│  │  │ └────────────┴──────────────┴──────────────────────────────┴──────────┴──────────┘  │  │ │
│  │  └─────────────────────────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                                           │ │
│  │  Persistence: playbook.save_to_file() → JSON                                             │ │
│  │  Survives: compaction, session restart, context overflow                                  │ │
│  │  Selection: BulletSelector scores effectiveness × recency × semantic → top-K for prompt   │ │
│  └───────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                                │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ EPISODIC MEMORY (ConversationSummarizer)                                                  │ │
│  │                                                                                           │ │
│  │  Trigger: every 5 new messages                                                            │ │
│  │  Scope: all messages EXCEPT last 6 (working memory)                                       │ │
│  │  Output: incremental summary for thinking phase context                                   │ │
│  │  Persistence: to_dict() / load_from_dict() in session metadata                           │ │
│  └───────────────────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## IterationContext State Machine

```
                                        IterationContext
                            ┌────────────────────────────────────┐
                            │ query: str                         │
                            │ messages: ValidatedMessageList     │
                            │ agent, tool_registry               │
                            │ approval_manager, undo_manager     │
                            │ ui_callback                        │
                            ├────────────────────────────────────┤
                            │ Counters:                          │
                            │   iteration_count          = 0     │  ++ each iteration
                            │   consecutive_reads        = 0     │  ++ on all-read batch, reset on write
                            │   consecutive_no_tool_calls= 0     │  ++ on failed nudge, reset on tool batch
                            │   todo_nudge_count         = 0     │  ++ on todo nudge (max 2)
                            ├────────────────────────────────────┤
                            │ One-Shot Guards:                   │
                            │   plan_approved_signal_injected    │  prevents duplicate plan signal
                            │   all_todos_complete_nudged        │  prevents duplicate done signal
                            │   completion_nudge_sent            │  prevents duplicate summary request
                            │   continue_after_subagent          │  skip post-subagent signal
                            └────────────────────────────────────┘

                            Safety Constants:
                            ┌────────────────────────────────────┐
                            │ MAX_REACT_ITERATIONS  = 200        │
                            │ MAX_NUDGE_ATTEMPTS    = 3          │
                            │ MAX_TODO_NUDGES       = 2          │
                            │ MAX_CONCURRENT_TOOLS  = 5          │
                            │ OFFLOAD_THRESHOLD     = 8000 chars │
                            └────────────────────────────────────┘
```

---

## Loop Termination Paths

```
                          ┌──────────────────┐
                          │ Iteration runs   │
                          └────────┬─────────┘
                                   │
                    ┌──────────────┼──────────────┬──────────────────────┐
                    │              │              │                      │
             ┌──────▼──────┐ ┌────▼────┐  ┌──────▼──────┐  ┌───────────▼───────────┐
             │ EXPLICIT    │ │ IMPLICIT│  │ EXHAUSTED   │  │ SAFETY LIMIT          │
             │             │ │         │  │ NUDGES      │  │                       │
             │ task_complete│ │ Text    │  │             │  │ iteration_count       │
             │ tool called │ │ response│  │ ≥3 failed   │  │ > MAX_REACT_ITERATIONS│
             │ with summary│ │ no tools│  │ tool nudges │  │ (200)                 │
             │             │ │ no error│  │ OR ≥2 todo  │  │                       │
             │ Gated by:   │ │         │  │ nudges      │  │ → force summarize     │
             │ todo check  │ │         │  │             │  │                       │
             └─────────────┘ └─────────┘  └─────────────┘  └───────────────────────┘
```

---

## System Reminders Injection Map

```
     Injection Point                          Reminder Name                    Guard
     ─────────────────────────────────────────────────────────────────────────────────────
     After thinking phase                     thinking_trace_reminder          (always)
     After subagent completion                subagent_complete_signal         continue_after_subagent
     ─── ACTION PHASE LLM CALL ───
     No tools + last failed                   nudge_{error_type}               consecutive_no_tool_calls < 3
     No tools + incomplete todos              incomplete_todos_nudge           todo_nudge_count < 2
     No tools + empty content                 completion_summary_nudge         completion_nudge_sent (once)
     Tools + present_plan approved            plan_approved_signal             plan_approved_signal_injected (once)
     Tools + all todos done                   all_todos_complete_nudge         all_todos_complete_nudged (once)
     Tools + user denied                      tool_denied_nudge                (always)
     Tools + 5+ consecutive reads             consecutive_reads_nudge          (resets after nudge)
     ─── OUTSIDE LOOP ───
     User toggles plan mode                   plan_subagent_request            (QueryProcessor)
     Session resume with plan                 plan_file_reference              (TUI Runner)
     Enhanced query                           thinking_on/off_instruction      (QueryEnhancer)
     @file reference                          file_exists_warning              (FileContentInjector)
     Docker command fails                     docker_command_failed_nudge      (DockerToolHandler)
```

---

## Parallel Tool Execution

```
     _process_tool_calls() receives tool_calls[]
                    │
                    ▼
     ┌─── Decision ─────────────────────────────────────────────────────┐
     │                                                                   │
     │  All spawn_subagent calls (>1)?                                  │
     │  ├─ YES → PARALLEL AGENTS                                        │
     │  │        ┌──────────────────────────────────────────────────┐   │
     │  │        │ ThreadPoolExecutor(max_workers=5)                │   │
     │  │        │ UI tracks per-agent: on_parallel_agent_complete()│   │
     │  │        │ All complete → on_parallel_agents_done()         │   │
     │  │        └──────────────────────────────────────────────────┘   │
     │  │                                                               │
     │  All in PARALLELIZABLE_TOOLS (>1)?                               │
     │  ├─ YES → SILENT PARALLEL                                        │
     │  │        ┌──────────────────────────────────────────────────┐   │
     │  │        │ ThreadPoolExecutor (concurrent execution)        │   │
     │  │        │ Skip on_tool_call/on_tool_result during exec     │   │
     │  │        │ Replay display in original order after all done  │   │
     │  │        │ (user sees sequential output, gets parallel speed)│   │
     │  │        └──────────────────────────────────────────────────┘   │
     │  │                                                               │
     │  └─ NO → SEQUENTIAL                                              │
     │           ┌──────────────────────────────────────────────────┐   │
     │           │ Loop: _check_interrupt → _execute_single_tool()  │   │
     │           │ Break on interrupt or denial                     │   │
     │           └──────────────────────────────────────────────────┘   │
     └───────────────────────────────────────────────────────────────────┘

     PARALLELIZABLE_TOOLS = {
         read_file, list_files, search,
         fetch_url, web_search, capture_web_screenshot, analyze_image,
         list_processes, get_process_output,
         list_todos, search_tools,
         find_symbol, find_referencing_symbols
     }
```

---

## Context Compaction Pipeline

```
     ContextCompactor.compact(messages, system_prompt)
                    │
                    ▼
     ┌─ Determine tail size ──────────────────────────────────────┐
     │  tail_count = min(5, max(2, len(messages) / 3))            │
     └──────────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
     ┌─ Split ──────────────────────────────────────────────────────┐
     │  head   = messages[:1]          (system prompt - never drop) │
     │  middle = messages[1:-tail]     (to be summarized)           │
     │  tail   = messages[-tail:]      (preserved verbatim)         │
     └──────────────────────────────┬───────────────────────────────┘
                                    │
                                    ▼
     ┌─ Sanitize middle ────────────────────────────────────────────┐
     │  For each tool_result in middle:                             │
     │    if len(content) > 200: truncate to 200 chars              │
     │  Artifact references survive via ArtifactIndex               │
     └──────────────────────────────┬───────────────────────────────┘
                                    │
                                    ▼
     ┌─ LLM Summarization ─────────────────────────────────────────┐
     │  Call compact_model (or fallback to action_model)            │
     │  Prompt: "Summarize preserving: file paths, function names,  │
     │           decisions, error messages, todos"                  │
     │  Output: [CONVERSATION SUMMARY] block                       │
     └──────────────────────────────┬───────────────────────────────┘
                                    │
                                    ▼
     ┌─ Reassemble ────────────────────────────────────────────────┐
     │  Result = [head] + [{role: user, content: SUMMARY}] + [tail]│
     │  Invalidate API calibration (_api_prompt_tokens = 0)         │
     │  Archive full conversation to scratch file                   │
     └─────────────────────────────────────────────────────────────┘
```

---

## BulletSelector Scoring

```
     For each bullet in Playbook:

     effectiveness_score = (helpful × 1.0 + neutral × 0.5) / (helpful + harmful + neutral)
                           Range: 0.0 (all harmful) → 0.5 (untested) → 1.0 (all helpful)

     recency_score = 1.0 / (1.0 + days_old × 0.1)
                     Day 0 → 1.0    Day 7 → 0.59    Day 30 → 0.25

     semantic_score = (cosine_similarity(query_embedding, bullet_embedding) + 1.0) / 2.0
                      Range: 0.0 (opposite) → 0.5 (orthogonal) → 1.0 (identical)

     final_score = effectiveness × 0.5 + recency × 0.3 + semantic × 0.2

     Select top-K bullets (default K=30) → format as Markdown → inject into system prompt
```
