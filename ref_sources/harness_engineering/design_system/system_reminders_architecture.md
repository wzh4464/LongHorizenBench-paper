# System Reminders - Architecture & Design

**Version**: 1.0
**Last Updated**: 2026-02-28

---

## The Problem: Attention Decay in Long Conversations

Large language models process entire conversations but allocate attention unevenly. The most recent messages exert disproportionate influence on the next token prediction. As conversations grow, instructions from the system prompt - no matter how carefully written - lose their practical influence on the model's decisions.

This is not a hallucination problem. The model can still *read* the original instructions. It simply stops *acting* on them when newer, more salient content (tool outputs, error messages, intermediate results) fills the conversation window.

The effect is predictable and measurable:

- After ~20 messages, error-recovery rules stop influencing behavior
- After ~25 messages, checklist-tracking rules lose salience
- After ~30 messages, the model treats the system prompt as background context rather than active guidance

The result: an agent that was given correct instructions at the start, but forgets them precisely when they matter most.

---

## The Solution: Event-Driven Micro-Reminders

System reminders are short messages (1–3 sentences) injected into the conversation as `user`-role messages at specific decision points. They do not introduce new rules - they **restate existing system prompt instructions** at the moment the agent needs to apply them.

Three principles govern the design:

- **Proximity**: A 2-sentence reminder at the decision point outweighs a 2-paragraph rule from 30 messages ago
- **Specificity**: "Re-read the file, then retry your edit" is more effective than "try again"
- **Restraint**: Each reminder fires at most 1–3 times, then stops. Excessive repetition trains the model to ignore the signal

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ReAct Executor Loop                            │
│                                                                         │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────────┐  │
│   │  LLM     │────>│  Parse   │────>│  Tool    │────>│  Append      │  │
│   │  Call     │     │ Response │     │  Exec    │     │  Results     │  │
│   └──────────┘     └──────────┘     └──────────┘     └──────────────┘  │
│        ▲                │                │                  │            │
│        │                ▼                ▼                  ▼            │
│        │         ┌──────────────────────────────────────────────┐       │
│        │         │          Reminder Injection Layer             │       │
│        │         │                                              │       │
│        │         │   Event Detectors:                           │       │
│        │         │   ┌─────────────────────────────────┐       │       │
│        │         │   │ No tool calls + last tool failed │──┐   │       │
│        │         │   │ 5+ consecutive read operations   │──┤   │       │
│        │         │   │ Tool call denied by user         │──┤   │       │
│        │         │   │ Completion with incomplete todos │──┤   │       │
│        │         │   │ All todos now complete           │──┤   │       │
│        │         │   │ Plan just approved               │──┤   │       │
│        │         │   │ Subagent returned results        │──┤   │       │
│        │         │   │ Empty completion message         │──┤   │       │
│        │         │   └─────────────────────────────────┘  │   │       │
│        │         │                                        ▼   │       │
│        │         │   ┌──────────────────────────────────────┐ │       │
│        │         │   │ get_reminder(name, **kwargs)         │ │       │
│        │         │   │ ┌──────────────┐ ┌────────────────┐  │ │       │
│        │         │   │ │ reminders.md │ │ fallback .txt  │  │ │       │
│        │         │   │ │ (sections)   │ │ (long prompts) │  │ │       │
│        │         │   │ └──────────────┘ └────────────────┘  │ │       │
│        │         │   └───────────────┬──────────────────────┘ │       │
│        │         │                   │                        │       │
│        │         │                   ▼                        │       │
│        │         │   ┌──────────────────────────────────────┐ │       │
│        │         │   │ Guardrails:                          │ │       │
│        │         │   │  - todo_nudge_count < MAX (2)        │ │       │
│        │         │   │  - consecutive_no_tool < MAX (3)     │ │       │
│        │         │   │  - all_todos_complete_nudged: once   │ │       │
│        │         │   │  - completion_nudge_sent: once       │ │       │
│        │         │   │  - plan_approved_signal: once        │ │       │
│        │         │   └──────────────────────────────────────┘ │       │
│        │         │                   │                        │       │
│        │         └───────────────────┼────────────────────────┘       │
│        │                             ▼                                 │
│        │                  ┌─────────────────────┐                      │
│        │                  │ messages.append(     │                      │
│        └──────────────────│   role: "user",      │                      │
│           next iteration  │   content: reminder  │                      │
│                           │ )                    │                      │
│                           └─────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────────┘
```

The injection layer sits between tool execution and the next LLM call. When an event detector fires, it retrieves the corresponding reminder text, checks the guardrail counter, and appends a `user`-role message to the conversation. The next LLM call sees this reminder as the most recent context - maximizing its influence on the model's next decision.

---

## Reminder Lifecycle

```
  reminders.md                    IterationContext              messages[]
  ┌──────────┐                    ┌──────────────┐              ┌──────────┐
  │ Template  │     get_reminder  │ Counters &   │   append     │          │
  │ Sections  │─────────────────>│ Flags        │────────────>│ user msg │
  │           │   + .format()     │              │              │ (reminder│
  │ --- name  │                   │ consecutive_ │              │  text)   │
  │ --- name  │                   │   reads: int │              │          │
  │ --- name  │                   │ todo_nudge_  │              └────┬─────┘
  └──────────┘                   │   count: int │                   │
       │                          │ plan_signal: │                   │
       │                          │   bool       │                   ▼
  ┌──────────┐                   │ completion_  │           ┌──────────────┐
  │ .txt     │                   │   sent: bool │           │  Next LLM    │
  │ fallback │                   └──────────────┘           │  Call sees   │
  │ files    │                                              │  reminder as │
  └──────────┘                                              │  most recent │
                                                            │  user input  │
                                                            └──────────────┘
```

**Step-by-step:**

1. An event occurs (e.g., the agent emits text with no tool calls after a tool failure)
2. The executor checks the corresponding guardrail counter in `IterationContext`
3. If the counter is below its maximum, `get_reminder("failed_tool_nudge")` is called
4. The reminder text is loaded from `reminders.md`, with placeholders filled via `.format()`
5. The text is appended to `messages[]` as `{"role": "user", "content": "..."}`
6. The guardrail counter is incremented
7. The loop returns `LoopAction.CONTINUE` - forcing another LLM call
8. The LLM sees the reminder as the latest user message and adjusts its behavior

---

## Reminder Categories

The system defines reminders across five functional categories:

### Continuation Signals

Fire after an external event completes, to prevent the agent from treating intermediate results as final output.

- `subagent_complete_signal` - After a subagent returns, tell the agent to evaluate and continue
- `plan_approved_signal` - After plan approval, list the todos and tell the agent to start item 1

### Error Recovery Nudges

Fire when a tool fails and the agent produces text without retrying. The system classifies the error type and delivers a specific recovery instruction.

- `failed_tool_nudge` - Generic: "fix the issue and try again"
- `nudge_edit_mismatch` - "The file changed. Re-read it, then retry your edit"
- `nudge_file_not_found` - "Use list_files or search to locate the correct path"
- `nudge_syntax_error` - "Read the file again to see current state, then retry"
- `nudge_permission_error` - "Check permissions, try a different path"
- `nudge_timeout` - "Try a more targeted approach"
- `nudge_rate_limit` - "Wait before retrying"

### Behavioral Corrections

Fire when the agent falls into an unproductive pattern.

- `consecutive_reads_nudge` - After 5+ read-only operations: "Start building or ask the user"
- `tool_denied_nudge` - After a user denies a tool call: "Don't retry. Ask why or try differently"

### Completion Guards

Ensure the agent finishes all work before exiting and exits cleanly when done.

- `incomplete_todos_nudge` - "You have N incomplete todos. Complete them first" (max 2 nudges)
- `all_todos_complete_nudge` - "All items done. Wrap up and report" (fires once)
- `completion_summary_nudge` - "Briefly state the outcome" (fires once on empty completion)

### Mode & Thinking Instructions

Injected during query preparation to configure the agent's reasoning behavior.

- `thinking_on_instruction` - "Call the think tool FIRST before any other tool"
- `thinking_off_instruction` - "For complex tasks, briefly explain reasoning"

---

## Injection Points in the ReAct Loop

The following diagram shows where each reminder category fires within a single iteration of the ReAct loop:

```
                    ┌──────────────────┐
                    │  LLM Response    │
                    │  (text + tools)  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ Has tool calls?  │
                    └──┬───────────┬───┘
                       │           │
                      YES          NO
                       │           │
              ┌────────▼────┐  ┌──▼──────────────────────┐
              │ Execute     │  │ Last tool failed?        │
              │ tool calls  │  └──┬──────────────────┬───┘
              └────────┬────┘     │                  │
                       │         YES                 NO
                       │          │                  │
                       │  ┌───────▼──────────┐  ┌───▼─────────────────┐
                       │  │ Inject:          │  │ Has incomplete      │
                       │  │ failed_tool_nudge│  │ todos?              │
                       │  │ or smart nudge   │  └──┬──────────────┬──┘
                       │  └──────────────────┘     │              │
                       │                          YES             NO
                       │                           │              │
                       │                   ┌───────▼───────┐  ┌──▼────────────┐
                       │                   │ Inject:       │  │ Empty         │
                       │                   │ incomplete_   │  │ completion?   │
                       │                   │ todos_nudge   │  │               │
                       │                   │ (max 2x)      │  │ If yes:       │
                       │                   └───────────────┘  │ completion_   │
                       │                                      │ summary_nudge │
                       │                                      └───────────────┘
                       │
              ┌────────▼────────────────┐
              │ All read-only tools?    │
              └──┬──────────────────┬──┘
                 │                  │
                YES                NO
                 │                  │
        ┌────────▼────────┐   ┌────▼───────────────┐
        │ consecutive_    │   │ Reset read counter │
        │ reads >= 5?     │   │ consecutive_reads=0│
        │                 │   └────────────────────┘
        │ If yes:         │
        │ consecutive_    │
        │ reads_nudge     │
        └─────────────────┘
                                         ┌────────────────────────┐
              After tool denial ────────>│ Inject:                │
              (approval rejected)        │ tool_denied_nudge      │
                                         └────────────────────────┘

              After plan approval ──────>┌────────────────────────┐
              (present_plan success)     │ Inject:                │
                                         │ plan_approved_signal   │
                                         │ (once)                 │
                                         └────────────────────────┘

              After subagent returns ───>┌────────────────────────┐
                                         │ Inject:                │
                                         │ subagent_complete_     │
                                         │ signal                 │
                                         └────────────────────────┘

              After all todos done ─────>┌────────────────────────┐
                                         │ Inject:                │
                                         │ all_todos_complete_    │
                                         │ nudge (once)           │
                                         └────────────────────────┘
```

---

## The Guardrail Counter System

Uncontrolled reminders become noise. If the agent receives the same nudge every iteration, it learns to ignore it - or worse, enters a loop where the nudge and the undesired behavior reinforce each other.

The `IterationContext` dataclass tracks per-session counters and flags:

```
IterationContext
├── consecutive_reads: int          Reset to 0 when a non-read tool fires
├── consecutive_no_tool_calls: int  Reset to 0 when any tool call is made
├── todo_nudge_count: int           Incremented per nudge, capped at 2
├── plan_approved_signal_injected: bool   Set once, never re-fires
├── all_todos_complete_nudged: bool       Set once, never re-fires
├── completion_nudge_sent: bool           Set once, never re-fires
└── continue_after_subagent: bool         Controls subagent signal injection
```

The constants that enforce limits:

```
MAX_NUDGE_ATTEMPTS = 3     After 3 failed-tool nudges, accept failure
MAX_TODO_NUDGES    = 2     After 2 incomplete-todo nudges, allow completion
```

This design ensures that reminders are delivered at most a handful of times. If the agent does not respond to the nudge, the system accepts the agent's judgment and moves on.

---

## Template Storage and Resolution

All reminder text lives outside Python source code, in the prompt templates directory:

```
swecli/core/agents/prompts/templates/
├── reminders.md              Short/medium reminders (section-delimited)
├── docker/
│   ├── docker_preamble.txt   Long-form prompts (filename fallback)
│   └── docker_context.txt
└── ...
```

`reminders.md` uses a simple section delimiter format:

```markdown
--- failed_tool_nudge ---
The previous operation failed. Please fix the issue and try again,
or call task_complete with status='failed' if you cannot proceed.

--- nudge_edit_mismatch ---
The edit_file old_content did not match. The file may have changed.
Read the file again to get the exact current content, then retry.

--- incomplete_todos_nudge ---
You have {count} incomplete todo(s):
{todo_list}

Please complete these tasks or mark them done before finishing.
```

The `get_reminder()` function resolves a name through two stages:

```
get_reminder("incomplete_todos_nudge", count="2", todo_list="  - Write tests\n  - Add docs")
       │
       ├──(1) Check _sections cache (parsed from reminders.md)
       │       Found? → Apply .format(**kwargs) → Return
       │
       └──(2) Check templates/{name}.txt file
               Found? → Read, apply .format(**kwargs) → Return
               Not found? → Raise KeyError
```

The module-level `_sections` cache is parsed once on first call and reused for the process lifetime. This ensures zero I/O overhead on subsequent calls.

---

## Example: A Reminder in Action

Consider this scenario. The agent tries to edit a file, but the content it quotes no longer matches:

```
messages = [
    {"role": "user",    "content": "Add rate limiting to the API"},
    {"role": "assistant", "content": null, "tool_calls": [edit_file(old_content="...")]},
    {"role": "tool",    "content": "Error: old_content not found in file"},
    {"role": "assistant", "content": "I wasn't able to modify the file..."},
    ──── WITHOUT REMINDER: conversation ends, user must intervene ────
    ──── WITH REMINDER: injection happens here ────
    {"role": "user",    "content": "The edit_file old_content did not match.
                                    The file may have changed. Read the file
                                    again to get the exact current content,
                                    then retry."},
    {"role": "assistant", "content": null, "tool_calls": [read_file("api.py")]},
    {"role": "tool",    "content": "... current file content ..."},
    {"role": "assistant", "content": null, "tool_calls": [edit_file(old_content="...")]},
    {"role": "tool",    "content": "File edited successfully"},
]
```

The reminder adds 28 words. It changes the outcome from "agent gives up" to "agent recovers and completes the task." The cost is negligible; the impact is not.

---

## Relationship to Context Compaction

System reminders are **ephemeral by design**. They are not preserved across context compaction. When the context window fills and the compaction system summarizes the conversation history, reminder messages are compressed along with everything else.

This is intentional:

- Reminders are event-specific - a "re-read the file" nudge from 30 messages ago has no future value
- The conditions that triggered them are no longer active after compaction
- The guardrail counters in `IterationContext` are session-scoped and reset naturally

If the same condition arises again after compaction (e.g., another edit mismatch), the detector fires again and injects a fresh reminder. The system is stateless in this regard - each reminder is generated on demand, triggered by the current state of the conversation.

---

## Why User-Role Messages

Reminders are injected as `user`-role messages rather than `system`-role messages or special tags. This is a deliberate design choice:

- **Attention weight**: User messages receive higher attention weight in the model's next-token prediction than system messages, especially in long conversations
- **API compatibility**: All LLM providers support user messages. Some providers handle system messages differently or with lower priority
- **Conversation flow**: The model treats user messages as direct input requiring a response, creating natural pressure to act on the reminder content
- **Simplicity**: No special parsing or tag handling needed - the reminder is plain text that the model reads and acts on like any other user input

Some reminders wrap their content in semantic XML tags (e.g., `<plan_approved>`, `<subagent_complete>`) to give the model structural cues about the nature of the message. The system prompt includes a note telling the model to expect `<system-reminder>` tags in user messages and tool results.

---

## Design Tradeoffs

**Chosen: Event-driven injection** vs. periodic injection (every N messages)

Periodic injection wastes tokens when no correction is needed and misses critical moments between intervals. Event-driven injection fires only when a specific condition is detected, ensuring every reminder is relevant.

**Chosen: Capped repetition** vs. unlimited repetition

Unlimited repetition creates noise and can cause loops where the agent and the reminder system fight each other. Capped repetition (1–3 times per event type) provides correction opportunity while accepting the agent's judgment after that.

**Chosen: Plain text** vs. structured metadata

Structured metadata (JSON flags, priority scores) adds complexity without clear benefit. The model responds to natural language instruction. A well-written sentence is more effective than a metadata field.

**Chosen: Centralized template file** vs. inline strings

Keeping reminder text in `reminders.md` rather than scattered across Python source files makes prompts auditable, testable, and editable by non-engineers. The `get_reminder()` function provides a clean API boundary.

---

## Summary

System reminders address the fundamental limitation of instruction-following in long conversations: **attention decays with distance**. Rather than trying to write a more comprehensive system prompt (which makes the problem worse by adding more text the model must attend to), the system delivers targeted, event-driven micro-corrections at decision points.

The architecture is minimal:

- A template file holds all reminder text
- Event detectors in the ReAct loop identify moments where guidance is needed
- Guardrail counters prevent over-correction
- Reminders are injected as user-role messages for maximum attention weight
- The entire system adds ~200 lines of code and changes the task completion rate from "requires human intervention" to "runs autonomously"

A long system prompt tells the agent what to do. A well-timed reminder makes sure it does it.
