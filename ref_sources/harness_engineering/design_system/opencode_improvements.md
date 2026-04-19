# OpenCode-Inspired Improvements

**Added**: 2026-03-03
**Origin**: Deep-dive comparison of OpenDev against OpenCode (TypeScript/Bun AI coding assistant)
**Scope**: 15 improvements across 4 phases; Phase 1 fully implemented, Phases 2-4 designed

---

## Table of Contents

1. [Plan Mode Refactoring: Planner as First-Class Subagent](#1-plan-mode-refactoring)
2. [9-Pass Edit Tool Fuzzy Matching](#2-9-pass-edit-tool-fuzzy-matching)
3. [Session Cost Tracking](#3-session-cost-tracking)
4. [Doom-Loop Detection](#4-doom-loop-detection)
5. [Staged Context Compaction](#5-staged-context-compaction)
6. [Tool Output Offloading](#6-tool-output-offloading)
7. [Lifecycle Hooks System](#7-lifecycle-hooks-system)
8. [ESC Interrupt System Fixes](#8-esc-interrupt-system-fixes)
9. [Thinking Level Simplification](#9-thinking-level-simplification)
10. [Provider-Specific Prompt Sections](#10-provider-specific-prompt-sections)
11. [Parallel Subagent Spawning Improvements](#11-parallel-subagent-spawning-improvements)
12. [Subagent Prompt Refinements](#12-subagent-prompt-refinements)
13. [Web Fetch Auto-Browser Install](#13-web-fetch-auto-browser-install)
14. [Files Summary](#14-files-summary)
15. [Phase 2-4 Roadmap (Designed, Not Yet Implemented)](#15-phase-2-4-roadmap)

---

## 1. Plan Mode Refactoring

### Problem

The old plan mode used four dedicated tools (`enter_plan_mode`, `exit_plan_mode`, `create_plan`, `edit_plan`) to switch the agent into a restricted planning state. This created a complex state machine: the agent had to know when to enter plan mode, the mode manager tracked plan existence, and the UI had to handle mode transitions. It was brittle - the agent sometimes failed to exit plan mode, leaving the system stuck.

### Design

Replaced the 4-tool state machine with a single pattern: **spawn a Planner subagent, then call `present_plan`**.

```
OLD FLOW                              NEW FLOW
─────────                             ─────────
Agent calls enter_plan_mode           Agent calls spawn_subagent(type="Planner")
  → ModeManager switches to PLAN        → Planner runs with read-only tools
  → Agent restricted to read-only        → Planner writes plan to file
  → Agent calls create_plan              → Planner returns plan_file_path
  → Agent calls edit_plan (iterate)    Agent calls present_plan(plan_file_path)
  → Agent calls exit_plan_mode           → Plan displayed to user for approval
  → ModeManager switches to NORMAL       → User approves/rejects
  → Plan displayed for approval          → Agent continues in normal mode
```

The Planner subagent was already implemented but was hidden from direct agent access (only reachable through `enter_plan_mode`). Now it's exposed as a first-class subagent type in the `spawn_subagent` tool schema.

### Changes

**Deleted (6 files):**
- `swecli/core/context_engineering/tools/implementations/create_plan_tool.py`
- `swecli/core/context_engineering/tools/implementations/edit_plan_tool.py`
- `swecli/core/context_engineering/tools/implementations/enter_plan_mode_tool.py`
- `swecli/core/context_engineering/tools/implementations/exit_plan_mode_tool.py`
- `swecli/core/agents/prompts/templates/tools/tool-create-plan.md`
- `swecli/core/agents/prompts/templates/tools/tool-edit-plan.md`
- `swecli/core/agents/prompts/templates/tools/tool-enter-plan-mode.md`
- `swecli/core/agents/prompts/templates/tools/tool-exit-plan-mode.md`

**Created:**
- `swecli/core/agents/prompts/templates/tools/tool-present-plan.md` - describes the new `present_plan` tool

**Modified:**
- `swecli/core/agents/components/schemas/definitions.py` - removed 4 plan tool schemas, added `present_plan` schema (takes only `plan_file_path`)
- `swecli/core/agents/prompts/variables.py` - renamed `EXIT_PLAN_MODE_TOOL` → `PRESENT_PLAN_TOOL`
- `swecli/core/agents/prompts/templates/system/main/main-mode-awareness.md` (v2.0 → v3.0) - rewrote "Operation Modes" to describe spawning a Planner subagent + calling `present_plan`
- `swecli/core/agents/prompts/templates/tools/tool-ask-user.md` - updated planning-context note
- `swecli/core/agents/prompts/templates/reminders.md` - renamed `plan_mode_request` → `plan_subagent_request`, updated `plan_file_reference`
- `swecli/core/agents/subagents/agents/planner.py` - updated description (plan file path provided in prompt, not by EnterPlanMode)
- `swecli/core/agents/subagents/task_tool.py` - removed filter that hid Planner from spawn_subagent schema
- `swecli/core/runtime/mode_manager.py` - removed `_plan_exists` flag, `plan_file_exists()`, `update_plan_existence()`
- `swecli/repl/query_processor.py` - changed injected reminder from `plan_mode_request` to `plan_subagent_request`
- `swecli/ui_textual/services/tool_display_service.py` - replaced 4-branch plan tool display with single `present_plan` branch
- `swecli/ui_textual/utils/tool_display.py` - removed 4 old entries, added `present_plan`
- `swecli/ui_textual/runner.py` - simplified `_cycle_mode` (no more active plan mode exit)

### Why This is Better

- **No state machine**: The agent stays in normal mode throughout. No risk of getting stuck in plan mode.
- **Composable**: Planner subagent can be spawned in parallel with other subagents (e.g., spawn Planner + Code Explorer simultaneously).
- **Simpler tool surface**: 1 tool instead of 4. Less for the LLM to learn, fewer edge cases.
- **Consistent pattern**: Uses the same `spawn_subagent` → `present_plan` flow as all other delegation patterns.

---

## 2. 9-Pass Edit Tool Fuzzy Matching

### Problem

The edit tool's `_find_content()` used a 2-pass strategy (exact match, then whitespace-stripped match). This frequently failed when the LLM produced `old_content` with slightly different indentation, trailing whitespace, or escape sequences - especially common when the LLM reconstructs code from memory rather than verbatim copy.

OpenCode's `edit.ts` implements a sophisticated multi-pass replacer chain. Our 2-pass approach was the single largest source of "old_content not found" errors.

### Design

Replaced the 2-pass search with a **9-pass chain-of-responsibility** pattern. Each replacer class inherits from `_Replacer` and implements `find(original, old_content) -> Optional[str]`. The chain short-circuits on first match. The returned value is the *actual substring found in the original file* (not the search query), so the replacement preserves the file's original formatting.

```
old_content from LLM
    │
    ▼
Pass 1: SimpleReplacer ──── exact string match
    │ miss
    ▼
Pass 2: LineTrimmedReplacer ──── strip trailing whitespace per line
    │ miss
    ▼
Pass 3: BlockAnchorReplacer ──── first/last lines as anchors + SequenceMatcher
    │ miss
    ▼
Pass 4: WhitespaceNormalizedReplacer ──── collapse whitespace runs
    │ miss
    ▼
Pass 5: IndentationFlexibleReplacer ──── ignore all leading whitespace
    │ miss
    ▼
Pass 6: EscapeNormalizedReplacer ──── unescape \n, \t, \\, \", \'
    │ miss
    ▼
Pass 7: TrimmedBoundaryReplacer ──── strip leading/trailing context lines
    │ miss
    ▼
Pass 8: ContextAwareReplacer ──── best substring match by similarity score
    │ miss
    ▼
Pass 9: MultiOccurrenceReplacer ──── trimmed exact match across all occurrences
    │ miss
    ▼
Error: old_content not found
```

#### Replacer Details

| Pass | Class | Strategy | Threshold |
|------|-------|----------|-----------|
| 1 | `_SimpleReplacer` | `old_content in original` | Exact |
| 2 | `_LineTrimmedReplacer` | Strip each line's trailing whitespace, match | Exact per-line |
| 3 | `_BlockAnchorReplacer` | First+last N lines match exactly (trimmed); middle scored by `SequenceMatcher` | 0.3 multi-candidate, 0.0 single |
| 4 | `_WhitespaceNormalizedReplacer` | Collapse all whitespace to single space before comparing | Exact normalized |
| 5 | `_IndentationFlexibleReplacer` | Strip all leading whitespace, skip blank lines in original | Exact stripped |
| 6 | `_EscapeNormalizedReplacer` | Unescape `\\n`→`\n`, `\\t`→`\t`, `\\\\`→`\\`, `\\"`→`"`, `\\'`→`'` | Exact unescaped |
| 7 | `_TrimmedBoundaryReplacer` | Try trimmed content; expand to full line boundaries if partial match | Exact trimmed |
| 8 | `_ContextAwareReplacer` | First/last non-empty lines as anchors, score all candidates | 0.5 similarity |
| 9 | `_MultiOccurrenceReplacer` | Trimmed line-by-line exact match as last resort | Exact trimmed |

Debug logging records which pass succeeded (e.g., `"edit_tool fuzzy match: _BlockAnchorReplacer succeeded"`).

### File

`swecli/core/context_engineering/tools/implementations/edit_tool.py`

---

## 3. Session Cost Tracking

### Problem

Token usage was captured per-message (`ChatMessage.token_usage`) and used for context compaction calibration, but never aggregated into a running cost figure. `ModelInfo` already had `pricing_input` and `pricing_output` fields (populated from models.dev cache) but they were unused at runtime.

### Design

```
LLM Response (usage dict)
    │
    ▼
ReactExecutor._run_iteration_inner()
    │  cost_tracker.record_usage(usage, model_info)
    │
    ├──► UI: on_cost_update(total_cost_usd)
    │         → StatusBar.set_session_cost()
    │
    └──► Persistence: session.metadata["cost_tracking"] = {...}
```

#### CostTracker (`swecli/core/runtime/cost_tracker.py`)

```python
class CostTracker:
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    call_count: int

    def record_usage(usage: dict, model_info: ModelInfo | None) -> float
    def format_cost() -> str
    def to_metadata() -> dict
    def restore_from_metadata(metadata: dict) -> None
```

**Cost formula**: `(prompt_tokens / 1M) * pricing_input + (completion_tokens / 1M) * pricing_output`

**Key decisions:**
- Incremental accumulation - no recomputation from message history
- Graceful degradation - if `model_info` is None, tokens tracked but cost stays zero
- Session persistence - `to_metadata()` exports to `session.metadata["cost_tracking"]`; `restore_from_metadata()` restores on `--continue`
- Precision - 6 decimal places in metadata, 4 for display of sub-cent costs

#### Status Bar Display

```
Mode: NORMAL  │  Autonomy: Manual  │  Thinking: Medium  │  ~/codes/swe-cli (main)
                                                        Cost $0.0142  │  Context left 87.3%
```

Cost only appears when `session_cost > 0`.

#### Session Metadata Schema

```json
{
  "cost_tracking": {
    "total_cost_usd": 0.014237,
    "total_input_tokens": 45230,
    "total_output_tokens": 3891,
    "api_call_count": 7
  }
}
```

### Files

- Created: `swecli/core/runtime/cost_tracker.py`
- Modified: `swecli/repl/react_executor.py`, `swecli/repl/query_processor.py`, `swecli/ui_textual/widgets/status_bar.py`, `swecli/ui_textual/ui_callback.py`

---

## 4. Doom-Loop Detection

### Problem

The agent could get stuck calling the same tool with identical arguments repeatedly (e.g., reading a file that doesn't exist, retrying a failed bash command). Existing safeguards were too blunt:

- `MAX_REACT_ITERATIONS` (200) - hard cap, only triggers after 200 turns
- `consecutive_reads` - counts *any* reads, not identical ones
- `consecutive_no_tool_calls` - only catches empty responses

None fingerprint the actual `(tool_name, args)` combination.

### Design

Tool call fingerprinting via MD5 hash of `(tool_name, sorted_args_json)`, tracked in a sliding window.

```python
# In IterationContext:
recent_tool_calls: deque(maxlen=20)  # sliding window of fingerprints
doom_loop_warned: bool = False        # prevents repeated warnings

# In ReactExecutor:
DOOM_LOOP_THRESHOLD = 3  # same fingerprint 3x → doom loop

def _tool_call_fingerprint(tool_name, args_str) -> str:
    return f"{tool_name}:{md5(args)[:12]}"

def _detect_doom_loop(tool_calls, ctx) -> Optional[str]:
    # Append fingerprints, count via Counter, return warning if any >= threshold
```

When detected, a `[SYSTEM WARNING]` user message is injected into the conversation:

```
[SYSTEM WARNING] The agent has called `read_file` with the same arguments
3 times. It may be stuck in a loop. Try a different approach.
```

This leverages the LLM's self-correction ability rather than forcibly terminating. Tool execution is skipped for that turn, and the loop continues with `LoopAction.CONTINUE`.

### File

`swecli/repl/react_executor.py`

---

## 5. Staged Context Compaction

### Problem

The old compaction system was binary: do nothing until 99% of context is used, then run a full LLM-powered compaction. This meant:

- Context pressure built invisibly until a sudden, expensive compaction
- No gradual degradation - full fidelity one moment, aggressive compression the next
- Tool outputs (80%+ of context) grew unchecked until the compaction cliff

### Design

Replaced the binary threshold with a **4-stage progressive pressure system**:

```
Context Usage    Stage              Action
────────────    ──────             ──────
0-70%           NONE               No action
70-80%          WARNING            Log warning, start tracking
80-90%          MASK               Progressive observation masking
90-99%          AGGRESSIVE         More aggressive masking, keep only recent outputs
99%+            COMPACT            Full LLM-powered compaction
```

```python
class OptimizationLevel:
    NONE = 0
    WARNING = 1
    MASK = 2
    AGGRESSIVE = 3
    COMPACT = 4
```

#### Observation Masking (`mask_old_observations`)

At 80%+ usage, old tool result messages are replaced in-place with compact placeholders:

```
Before: {"role": "tool", "content": "<2000 lines of file content>"}
After:  {"role": "tool", "content": "[output offloaded to scratch file]"}
```

The 6 most recent tool outputs are preserved. At 90%+ (AGGRESSIVE), only the 3 most recent are preserved.

#### Artifact Index

New `ArtifactIndex` class tracks file operations during a session:

```python
class ArtifactIndex:
    def record(path: str, operation: str, metadata: dict) -> None
    def to_summary() -> str  # injected into compaction summary
    def serialize() -> dict  # survives compaction
```

Operations tracked: `read`, `created`, `modified`, `deleted`. The index survives compaction by being serialized into the summary message, ensuring the agent remembers what files it has touched even after context is compressed.

#### History Archival

Before full compaction, the entire message history is written to a scratch file:

```
~/.opendev/scratch/<session_id>/history_archive_<timestamp>.txt
```

A reference is injected into the compaction summary: `"Full conversation history archived at <path>. Use read_file to recover details if needed."`

This means compaction is no longer lossy - the agent can recover any detail by reading the archive.

### Files

- Modified: `swecli/core/context_engineering/compaction.py` (major rewrite)
- Modified: `swecli/repl/react_executor.py` (integrated `check_usage`, `mask_old_observations`, `_record_artifact`)
- Tests: `tests/test_staged_compaction.py`

---

## 6. Tool Output Offloading

### Problem

Large tool outputs (file reads, bash command results) consumed disproportionate context. A single `read_file` of a 2000-line file could use 8000+ tokens.

### Design

Tool outputs exceeding a threshold are offloaded to scratch files before being added to message history.

```python
OFFLOAD_THRESHOLD = 8000  # chars (~2000 tokens)

def _maybe_offload_output(tool_name, tool_call_id, output) -> str:
    if len(output) <= OFFLOAD_THRESHOLD:
        return output  # Pass through

    # Write full output to scratch file
    path = f"~/.opendev/scratch/{session_id}/{tool_name}_{call_id[:8]}.txt"
    write(path, output)

    # Return summary
    return f"{output[:500]}\n\n[Output offloaded: {lines} lines, {chars} chars → {path}]\nUse read_file to see full output if needed."
```

The agent sees the first 500 characters (enough to understand the content) plus a reference to the full output. If it needs details, it can `read_file` the scratch path - which is itself subject to the same offloading, creating a natural tiering system.

Subagent completion status messages are excluded from offloading (they're already compact).

### File

`swecli/repl/react_executor.py`

---

## 7. Lifecycle Hooks System

### Problem

There was no way for users to run custom scripts in response to agent lifecycle events - no way to log tool calls to an external system, block dangerous operations with custom policies, run linters after file edits, or integrate with CI/CD pipelines.

OpenCode and Claude Code both support lifecycle hooks.

### Design

A complete hooks system modeled after Claude Code's hook protocol.

```
~/.opendev/settings.json (or .opendev/settings.json per-project)
    │
    │  "hooks": {
    │    "PreToolUse": [
    │      { "matcher": "bash_execute",
    │        "commands": [{"command": "my-validator.sh", "timeout": 10}] }
    │    ]
    │  }
    │
    ▼
HookManager
    │  run_hooks(event, match_value, event_data)
    │
    ├──► HookMatcher.matches(match_value)?
    │      regex match against tool name, agent type, etc.
    │
    └──► HookCommandExecutor.run(command, stdin_json)
           subprocess.run with JSON context on stdin
           Exit 0 = success
           Exit 2 = BLOCK operation (short-circuit)
           Other  = error (logged, continues)
```

#### Hook Events (10 total)

| Event | Trigger | Blocking | Match Value |
|-------|---------|----------|-------------|
| `SessionStart` | Session begins | No | - |
| `UserPromptSubmit` | Before processing user prompt | Yes | - |
| `PreToolUse` | Before each tool call | Yes (can block/mutate) | tool name |
| `PostToolUse` | After successful tool call | No (async) | tool name |
| `PostToolUseFailure` | After failed tool call | No (async) | tool name |
| `SubagentStart` | Before subagent runs | Yes (can block) | agent type |
| `SubagentStop` | After subagent completes | No (async) | agent type |
| `Stop` | Agent loop ends naturally | No | - |
| `PreCompact` | Before context compaction | No | - |
| `SessionEnd` | Session cleanup | No | - |

#### Hook Outcomes

A hook command can:
- **Block** (exit code 2): Prevents the operation. The `block_reason` from stdout is returned to the agent.
- **Mutate input** (stdout JSON with `tool_input` key): Modifies tool arguments before execution.
- **Add context** (stdout JSON with `additional_context` key): Injects extra context into the tool result.
- **Grant/deny permission** (stdout JSON with `permission_decision` key): Override approval for this call.

#### Configuration Merging

Global (`~/.opendev/settings.json`) and project (`.opendev/settings.json`) hooks are merged: project matchers are appended after global matchers per event. This allows global policies (e.g., "log all bash commands") combined with project-specific hooks (e.g., "run eslint after file edits").

### Files

- Created: `swecli/core/hooks/models.py`, `swecli/core/hooks/executor.py`, `swecli/core/hooks/manager.py`, `swecli/core/hooks/loader.py`
- Modified: `swecli/repl/repl.py` (init hooks, fire SessionStart/SessionEnd)
- Modified: `swecli/core/context_engineering/tools/registry.py` (fire PreToolUse/PostToolUse)
- Modified: `swecli/repl/query_processor.py` (fire UserPromptSubmit)
- Modified: `swecli/repl/react_executor.py` (fire Stop hook)
- Modified: `swecli/core/agents/subagents/manager.py` (fire SubagentStart/SubagentStop)
- Modified: `swecli/core/context_engineering/compaction.py` (fire PreCompact)
- Tests: `tests/test_hooks.py`

---

## 8. ESC Interrupt System Fixes

### Problem

The ESC key interrupt had multiple race conditions and UX issues:

1. Pressing ESC during an ask-user dialog would interrupt the agent AND cancel the dialog, leaving orphaned state
2. Pressing ESC during parallel agent execution would show incomplete UI (dangling spinner rows, missing completion indicators)
3. Bash tool `process.terminate()` didn't reliably kill child processes (process groups survived)
4. Multiple rapid ESC presses could produce duplicate interrupt messages
5. Plan approval controller could crash if interrupted and re-invoked (stale future reference)

### Design

Six targeted fixes, each addressing a specific race condition:

#### Fix 1: Modal Controller Priority

```python
# chat_app.py - action_interrupt()
if self._is_processing and (ask_user_active or approval_active):
    # Cancel the controller only - do NOT interrupt the agent
    controller.cancel()
    return
elif self._is_processing:
    # No modal - interrupt the agent
    self._interrupt_agent()
```

#### Fix 2: Immediate Interrupt Feedback

New `_show_interrupt_feedback()` method in `chat_app.py`:
- Immediately clears `_is_processing` flag (prevents further tool display updates)
- Calls `conversation.interrupt_cleanup()` (collapses dangling parallel agent/tool UI)
- Marks `_ui_callback.mark_interrupt_shown()` (guard against duplicate messages)
- Stops all spinners with `immediate=True`

#### Fix 3: Tool Renderer Interrupt Cleanup

`tool_renderer.py` gained `_interrupted: bool` flag and `interrupt_cleanup()`:
- For parallel agent groups: deletes per-agent rows, updates header to red bullet
- For single agents: deletes tool line, updates header to red bullet
- Stops animation timers, clears state
- All rendering methods early-return if `_interrupted` is True

#### Fix 4: Process Group Kill

```python
# bash_tool.py - subprocess creation
process = subprocess.Popen(..., start_new_session=True)  # creates process group

# On interrupt:
os.killpg(os.getpgid(process.pid), signal.SIGKILL)  # kills entire group
```

Previously used `process.terminate()` which only sent SIGTERM to the parent process, leaving child processes running.

#### Fix 5: Duplicate Interrupt Guard

`_interrupt_shown: bool` flag on `TextualUICallback` - set in `mark_interrupt_shown()`, checked in every callback method that could produce output. Reset at the start of each new run in `on_thinking_start()`.

#### Fix 6: Plan Approval Stale Future

`plan_approval_controller.py` - `display_plan()` now cancels a stale `_future` from a previous interrupted call instead of raising `RuntimeError`.

### Files

- Modified: `swecli/ui_textual/chat_app.py`
- Modified: `swecli/ui_textual/widgets/conversation/tool_renderer.py`
- Modified: `swecli/ui_textual/widgets/conversation_log.py`
- Modified: `swecli/ui_textual/managers/spinner_service.py`
- Modified: `swecli/ui_textual/controllers/ask_user_prompt_controller.py`
- Modified: `swecli/ui_textual/controllers/plan_approval_controller.py`
- Modified: `swecli/core/context_engineering/tools/implementations/bash_tool.py`
- Modified: `swecli/core/context_engineering/tools/handlers/process_handlers.py`
- Tests: `tests/test_interrupt_fixes.py`

---

## 9. Thinking Level Simplification

### Problem

The thinking system had 5 levels: `Off → Low → Medium → High → Self-Critique`. The `Self-Critique` level was confusingly similar to `High` - both enabled extended thinking, with the only difference being that Self-Critique also triggered a critique pass. Users didn't understand the distinction.

### Design

Merged `Self-Critique` into `High`. The cycle is now `Off → Low → Medium → High → Off`.

`ThinkingLevel.HIGH.includes_critique` now returns `True` (previously only `SELF_CRITIQUE` did). When thinking is set to High, the critique pass happens automatically.

### Files

- Modified: `swecli/core/context_engineering/tools/handlers/thinking_handler.py` (removed `SELF_CRITIQUE` enum value)
- Modified: `swecli/ui_textual/widgets/status_bar.py` (removed from color map)
- Modified: `swecli/ui_textual/chat_app.py` (4-level cycle)
- Modified: `swecli/ui_textual/ui_callback.py` (comment update)
- Modified: `swecli/web/routes/config.py` (removed from valid levels)
- Modified: `web-ui/src/components/Chat/ThinkingBlock.tsx` (removed from `LEVEL_COLORS`)
- Modified: `web-ui/src/components/Layout/TopBar.tsx` (removed from `THINKING_STYLES`)

---

## 10. Provider-Specific Prompt Sections

### Problem

The system prompt was identical regardless of which LLM provider was active. Different providers have meaningfully different capabilities (Anthropic extended thinking, OpenAI function calling, Fireworks context limits). Without provider-specific guidance, the LLM might reference capabilities it doesn't have.

### Design

Conditional sections in the existing `PromptComposer` system. The `model_provider` and `model` fields from `EnvironmentContext` are threaded into the composer context dict, enabling conditions like `ctx.get("model_provider") == "openai"`.

```
Priority 65-75:  Conditional features (subagent_guide, git_workflow, task_tracking)
Priority 80:     Provider-specific notes  ← NEW (mutually exclusive)
Priority 85-95:  Context awareness (output_awareness, scratchpad, code_references)
```

Three provider sections registered at priority 80:
- `main-provider-openai.md` - function calling, reasoning models, vision, structured output
- `main-provider-anthropic.md` - tool_use blocks, extended thinking, cache control, vision
- `main-provider-fireworks.md` - OpenAI-compatible API, context windows, inference speed

Only one is included per prompt (mutually exclusive by condition). Unknown providers get no section (graceful degradation).

### Files

- Created: 3 template files in `swecli/core/agents/prompts/templates/system/main/`
- Modified: `swecli/core/agents/prompts/composition.py` (3 section registrations)
- Modified: `swecli/core/agents/components/prompts/builders.py` (thread model_provider/model into context)

---

## 11. Parallel Subagent Spawning Improvements

### Problem

The agent could already spawn subagents in parallel (the executor detects multiple `spawn_subagent` calls in the same response), but the system prompt didn't clearly explain this capability. The agent often spawned subagents sequentially, wasting time.

### Design

Enhanced prompt guidance across multiple template files:

**`main-subagent-guide.md`** - added "Parallel Subagent Spawning" section:
- WHEN to parallelize: user asks for multiple agents, large codebase, independent tasks
- HOW: "make multiple spawn_subagent calls in the SAME response"
- Synthesis guidance: "do NOT summarize each agent separately - synthesize all results into a single unified response organized by topic"

**`main-tool-selection.md`** - added bullet points for parallel subagents and parallel read-only tools

**`task_tool.py` description** - updated item 4 to explicitly state: "To run subagents concurrently, make multiple spawn_subagent calls in the SAME response. The system detects this and executes them in parallel automatically."

**`reminders.md`** - updated `subagent_complete_signal`: "All subagents have completed. Evaluate ALL results together... synthesize findings from all agents into one unified answer."

### Files

- Modified: `swecli/core/agents/prompts/templates/system/main/main-subagent-guide.md`
- Modified: `swecli/core/agents/prompts/templates/system/main/main-tool-selection.md`
- Modified: `swecli/core/agents/subagents/task_tool.py`
- Modified: `swecli/core/agents/prompts/templates/reminders.md`
- Tests: `tests/test_parallel_tools.py`

---

## 12. Subagent Prompt Refinements

### Problem

Subagent prompts had vague termination conditions, leading to over-exploration (Code Explorer reading the same files repeatedly) and missing plan file paths in Planner outputs.

### Design

**Code Explorer** (`subagent-code-explorer.md`):
- Added explicit stop conditions: "stop when evidence is clear, stop if progress stalls, prefer depth over breadth"
- Added anti-loop instruction: "re-reading the same file triggers immediate stop"

**Planner** (`subagent-planner.md`):
- Updated `task_complete` call instruction to include `plan_file_path` in the summary, so the main agent knows where to find the plan file for `present_plan`

**Thinking mode** (`system/thinking.md`):
- Added encouragement to spawn Code Explorer for large tasks requiring deep analysis

**Thinking subagent guide** (`thinking-subagent-guide.md`):
- Replaced `enter_plan_mode` references with "Planner subagent" in examples

### Files

- Modified: `swecli/core/agents/prompts/templates/subagents/subagent-code-explorer.md`
- Modified: `swecli/core/agents/prompts/templates/subagents/subagent-planner.md`
- Modified: `swecli/core/agents/prompts/templates/system/thinking.md`
- Modified: `swecli/core/agents/prompts/templates/system/thinking/thinking-subagent-guide.md`

---

## 13. Web Fetch Auto-Browser Install

### Problem

`web_fetch` and `web_screenshot` tools used Playwright for rendering JavaScript-heavy pages, but if Playwright's Chromium wasn't installed, the tools failed with an opaque error.

### Design

Added `_ensure_browsers_installed()` function that auto-installs Playwright Chromium on first use. Both tools now auto-retry after calling this function if the initial failure was a missing Playwright executable.

### Files

- Modified: `swecli/core/context_engineering/tools/implementations/web_fetch_tool.py`
- Modified: `swecli/core/context_engineering/tools/implementations/web_screenshot_tool.py`

---

## 14. Files Summary

### Created

| File | Purpose |
|------|---------|
| `swecli/core/runtime/cost_tracker.py` | Session cost tracking service |
| `swecli/core/hooks/models.py` | Hook event types, matchers, config models |
| `swecli/core/hooks/executor.py` | Shell command executor for hooks |
| `swecli/core/hooks/manager.py` | Hook orchestration and lifecycle management |
| `swecli/core/hooks/loader.py` | Config loading and merging (global + project) |
| `swecli/core/agents/prompts/templates/tools/tool-present-plan.md` | Present plan tool description |
| `swecli/core/agents/prompts/templates/system/main/main-provider-openai.md` | OpenAI provider hints |
| `swecli/core/agents/prompts/templates/system/main/main-provider-anthropic.md` | Anthropic provider hints |
| `swecli/core/agents/prompts/templates/system/main/main-provider-fireworks.md` | Fireworks provider hints |
| `swecli/web/web_ui_callback.py` | Web UI callback with plan approval support |
| `tests/test_hooks.py` | Hooks system tests |
| `tests/test_staged_compaction.py` | Staged compaction tests |
| `tests/test_parallel_tools.py` | Parallel tool execution tests |
| `tests/test_interrupt_fixes.py` | ESC interrupt fix tests |

### Deleted

| File | Reason |
|------|--------|
| `swecli/core/context_engineering/tools/implementations/create_plan_tool.py` | Replaced by Planner subagent |
| `swecli/core/context_engineering/tools/implementations/edit_plan_tool.py` | Replaced by Planner subagent |
| `swecli/core/context_engineering/tools/implementations/enter_plan_mode_tool.py` | Replaced by spawn_subagent |
| `swecli/core/context_engineering/tools/implementations/exit_plan_mode_tool.py` | Replaced by present_plan |
| `swecli/core/agents/prompts/templates/tools/tool-create-plan.md` | Deleted with tool |
| `swecli/core/agents/prompts/templates/tools/tool-edit-plan.md` | Deleted with tool |
| `swecli/core/agents/prompts/templates/tools/tool-enter-plan-mode.md` | Deleted with tool |
| `swecli/core/agents/prompts/templates/tools/tool-exit-plan-mode.md` | Deleted with tool |

### Modified (40+ files)

Core agent: `definitions.py`, `variables.py`, `main-mode-awareness.md`, `tool-ask-user.md`, `reminders.md`, `planner.py`, `task_tool.py`, `manager.py`

Runtime: `mode_manager.py`, `compaction.py`, `registry.py`

ReAct executor: `react_executor.py`, `query_processor.py`, `repl.py`

Edit tool: `edit_tool.py`

UI (TUI): `chat_app.py`, `ui_callback.py`, `status_bar.py`, `tool_renderer.py`, `conversation_log.py`, `spinner_service.py`, `ask_user_prompt_controller.py`, `plan_approval_controller.py`, `runner.py`, `tool_display_service.py`, `tool_display.py`

UI (Web): `config.py`, `state.py`, `websocket.py`, `TopBar.tsx`, `ThinkingBlock.tsx`, `ToolCallMessage.tsx`, `ChatPage.tsx`, `chat.ts`, `types/index.ts`

Tools: `bash_tool.py`, `web_fetch_tool.py`, `web_screenshot_tool.py`, `process_handlers.py`, `thinking_handler.py`

Prompts: `main-subagent-guide.md`, `main-tool-selection.md`, `subagent-code-explorer.md`, `subagent-planner.md`, `thinking.md`, `thinking-subagent-guide.md`

Tests: `test_prompt_variables.py`, `test_tool_descriptions.py`, `test_context_compaction.py`, `test_prompt_rendering.py`, `test_reminders.py`, `test_thinking_mode.py`, `test_modular_composition.py`

---

## 15. Phase 2-4 Roadmap (Designed, Not Yet Implemented)

These improvements were designed during the OpenCode comparison analysis but are deferred to future phases.

### Phase 2 - Core Architecture

- **Event Bus / Pub-Sub**: `EventBus` with typed events (`ToolCallStarted`, `CostUpdated`, `FileModified`, etc.). Replace direct `ui_callback` calls with bus publishes; UI layers become subscribers.
- **Provider Abstraction Layer**: Abstract `ProviderAdapter` with `normalize_messages()`, `apply_prompt_caching()`, `get_reasoning_params()`, `get_temperature()`. Implementations for Anthropic, OpenAI, generic OpenAI-compatible.
- **Snapshot-Based Undo**: `SnapshotManager` using a dedicated git object store at `~/.opendev/snapshots/<project-hash>/`. `track()` → `git write-tree`, `restore(hash)` → `git read-tree` + `git checkout-index`. Hooks into tool execution pipeline for before/after snapshots. `/undo` and `/diff` REPL commands.

### Phase 3 - Platform

- **Structured Message Parts**: `MessagePart` discriminated union (`TextPart`, `ToolPart` with state machine, `ReasoningPart`, `SnapshotPart`, `PatchPart`, etc.). Foundational for per-part UI rendering and streaming.
- **SQLite Sessions**: Replace JSON/JSONL with `sqlite3` tables (`sessions`, `messages`, `session_stats`). Enables cross-session queries, content search, session forking, concurrent access.
- **Wildcard Permission Cascade**: Glob pattern matching for approval rules (`git *`, `npm install *`). Persistent storage in `~/.opendev/permissions.json`.
- **Session Forking**: `fork(session_id, up_to_message_id)` cloning message history. Depends on SQLite sessions.

### Phase 4 - Polish

- **JSONC Config**: JSON5/JSONC support with `{env:VAR_NAME}` and `{file:path}` variable substitution.
- **Enterprise Session Sharing**: Share URLs with HMAC-signed tokens, abstract storage adapter (local → S3/R2).
- **File Watcher with Diagnostics**: `watchdog` for cross-platform file watching, LSP diagnostic refresh at 150ms debounce.
- **TUI Enhancements**: Command palette (Ctrl+K), frecency-ranked sessions, prompt stash, keybind customization.
