# OpenCode-Inspired Improvements - Phase 2

**Added**: 2026-03-03
**Origin**: Deep-dive comparison of OpenDev against OpenCode (TypeScript/Bun AI coding assistant), Phase 2
**Scope**: 11 improvements across 3 implementation phases; all fully implemented
**Predecessor**: [opencode_improvements.md](./opencode_improvements.md) (Phase 1: 13 features)

---

## Table of Contents

1. [Error Prompt Table Removal](#1-error-prompt-table-removal)
2. [Dynamic Truncation Hints](#2-dynamic-truncation-hints)
3. [FileTime Stale-Read Detection](#3-filetime-stale-read-detection)
4. [Doom Loop → Permission-Based Pause](#4-doom-loop--permission-based-pause)
5. [Cost Display: Web UI + Exit Summary](#5-cost-display-web-ui--exit-summary)
6. [Structured Compaction Template (Verified)](#6-structured-compaction-template)
7. [LSP Diagnostics After Edit](#7-lsp-diagnostics-after-edit)
8. [Anthropic Prompt Caching](#8-anthropic-prompt-caching)
9. [Two-Tier Compaction: Fast Pruning](#9-two-tier-compaction-fast-pruning)
10. [Persistent Permission Rules](#10-persistent-permission-rules)
11. [Shadow Git Snapshot System](#11-shadow-git-snapshot-system)
12. [Files Summary](#12-files-summary)
13. [Test Coverage](#13-test-coverage)

---

## 1. Error Prompt Table Removal

### Problem

`CLAUDE.md` specifies: "When crafting system prompts, never use table format. Tables are poorly parsed by LLMs and waste tokens." Two prompt templates violated this constraint:

- `main-error-recovery.md` used a markdown table mapping error patterns to causes and resolutions
- `main-output-awareness.md` used a markdown table mapping tool names to output limits and truncation behavior

Markdown tables consume extra tokens for the pipe/dash formatting and are parsed less reliably than prose by language models.

### Design

Replaced all tables with bullet lists using a consistent structure:

```
Before (table):
| Error Pattern    | Cause         | Resolution              |
|------------------|---------------|-------------------------|
| "File not found" | Incorrect path| Check spelling and path |

After (bullet list):
- **"File not found"** - Path is incorrect. Check spelling, verify the directory
  exists, and try using an absolute path.
```

Each table row becomes a bullet with the key field bolded, a dash separator, and the remaining fields merged into a natural prose sentence.

### Files

- Modified: `swecli/core/agents/prompts/templates/system/main/main-error-recovery.md`
- Modified: `swecli/core/agents/prompts/templates/system/main/main-output-awareness.md`

---

## 2. Dynamic Truncation Hints

### Problem

When tool output exceeds the offloading threshold (8000 chars), the agent receives a static hint: "Use read_file with offset/max_lines to page through the full output." This ignores the agent's actual capabilities. If the agent has access to `spawn_subagent`, it can delegate to an explore subagent for more efficient processing - but the hint doesn't mention this.

OpenCode varies its truncation advice based on whether the agent has the `task` tool (their equivalent of `spawn_subagent`).

### Design

```
Tool output > 8000 chars
    │
    ├── Agent HAS spawn_subagent tool:
    │   "Delegate to an explore subagent to process the full output via
    │    search/read_file, or use read_file with offset/max_lines to page through it."
    │
    └── Agent LACKS spawn_subagent tool:
        "Use read_file with offset/max_lines to page through the full output."
```

Detection is done by checking the tool registry at the point of result processing:

```python
_has_subagent = "spawn_subagent" in getattr(ctx.tool_registry, "_handlers", {})
```

This check happens once per tool call batch (not per individual tool result) and is passed down through `_add_tool_result_to_history()` → `_maybe_offload_output()`.

### Flow

```
_process_tool_calls()
    │
    ├── Execute all tool calls (parallel/sequential)
    ├── Snapshot tracking (if write operations)
    │
    ├── _has_subagent = check registry for "spawn_subagent"
    │
    └── for each tool_call:
        └── _add_tool_result_to_history(has_subagent_tool=_has_subagent)
            └── _maybe_offload_output(has_subagent_tool=_has_subagent)
                └── if output > OFFLOAD_THRESHOLD:
                    └── Build hint using has_subagent_tool flag
```

### File

`swecli/repl/react_executor.py` - modified `_process_tool_calls()` (line ~1430), `_add_tool_result_to_history()` (line ~1788), `_maybe_offload_output()` (line ~1827)

---

## 3. FileTime Stale-Read Detection

### Problem

When the agent reads a file and then later edits it, there is a window where the user (or an external process) might modify the file between the read and the edit. Without stale-read detection, the agent would silently overwrite the user's changes - a data-loss risk.

OpenCode's `FileTime` system records read timestamps per session and asserts `mtime <= read_time + 50ms` before any write operation.

### Design

```
            Agent reads file           User edits file          Agent tries to edit
                │                          │                         │
                ▼                          ▼                         ▼
        record_read(path)           (mtime changes)          assert_fresh(path)
        stores time.time()                                        │
                                                                  ▼
                                                        mtime > read_time + 50ms?
                                                           │              │
                                                          YES             NO
                                                           │              │
                                                           ▼              ▼
                                                     Return error     Return None
                                                     "Re-read the    (safe to edit)
                                                      file first"
```

#### FileTimeTracker (`swecli/core/context_engineering/tools/file_time.py`)

```python
MTIME_TOLERANCE_SECS = 0.05  # 50ms tolerance for filesystem timestamp fuzziness

class FileTimeTracker:
    _read_times: Dict[str, float]  # abs_path -> time.time() of last read
    _lock: threading.Lock          # Thread-safe for parallel tool execution

    def record_read(filepath: str) -> None
    def assert_fresh(filepath: str) -> Optional[str]  # Returns error or None
    def invalidate(filepath: str) -> None              # Remove record after edit
    def clear() -> None                                # Reset on session clear
```

**Key design decisions:**

- **50ms tolerance**: Most filesystems have 1-second mtime resolution. APFS/ext4 can do sub-second. 50ms handles both while still catching real edits.
- **Thread-safe**: Parallel tool execution means multiple tools could read/write concurrently. A `threading.Lock` protects the dict.
- **Invalidate after edit**: After a successful edit, the agent's cached view is stale, so we remove the record to force a re-read before the next edit.
- **Graceful on unknown files**: If the agent hasn't read a file (e.g., it's creating a new file), `assert_fresh()` returns None (allow the edit). The system only blocks edits to files the agent has previously read and that have been modified since.
- **Graceful on deleted files**: If the file no longer exists, returns None and lets the edit tool handle the error.

#### Integration Points

The tracker is instantiated in `ToolRegistry.__init__()` and passed to tool handlers via `ToolExecutionContext`:

```
ToolRegistry.__init__()
    └── self._file_time_tracker = FileTimeTracker()

ToolRegistry.execute_tool()
    └── context = ToolExecutionContext(
            file_time_tracker=self._file_time_tracker, ...)

FileToolHandler.read_file()
    └── context.file_time_tracker.record_read(file_path)

FileToolHandler.edit_file()
    ├── stale_error = context.file_time_tracker.assert_fresh(file_path)
    │   └── if stale_error: return error to agent
    └── (on success) context.file_time_tracker.invalidate(file_path)
```

### Files

- Created: `swecli/core/context_engineering/tools/file_time.py`
- Modified: `swecli/core/context_engineering/tools/context.py` - added `file_time_tracker` field to `ToolExecutionContext`
- Modified: `swecli/core/context_engineering/tools/registry.py` - instantiate `FileTimeTracker`, pass to context, added `"read_file"` to context-receiving tools
- Modified: `swecli/core/context_engineering/tools/handlers/file_handlers.py` - call `record_read()` in `read_file()`, call `assert_fresh()`/`invalidate()` in `edit_file()`
- Tests: `tests/test_file_time.py` (10 tests)

---

## 4. Doom Loop → Permission-Based Pause

### Problem

Phase 1 implemented doom loop detection via MD5 fingerprinting of `(tool_name, sorted_args)`. When detected, a `[SYSTEM WARNING]` message was injected into the conversation, but the agent continued executing immediately. This was an advisory, not a pause. The agent would see the warning on the next LLM call but had already burned one iteration. More importantly, the user had no agency - no way to decide whether to allow the loop to continue (it might be intentional) or break it.

OpenCode triggers `PermissionNext.ask({ permission: "doom_loop" })`, which genuinely halts execution until the user responds.

### Design

Replaced the warning injection with a blocking approval request:

```
_detect_doom_loop() returns warning string
    │
    ▼
_request_doom_loop_approval(ctx, warning)
    │
    ├── Notify UI: "Doom-loop detected: {warning}"
    │
    ├── Create synthetic Operation:
    │   Operation(
    │       id="doom_loop_{timestamp}",
    │       type=OperationType.BASH_EXECUTE,
    │       target="doom_loop_check",
    │       parameters={"warning": warning},
    │   )
    │
    ├── Call approval_manager.request_approval(
    │       operation=operation,
    │       preview=warning,
    │       command="Agent is repeating: {warning}",
    │   )
    │
    └── User sees approval prompt:
        ┌─────────────────────────────────────────────────┐
        │ Agent is repeating: The agent has called         │
        │ `read_file` with the same arguments 3 times.    │
        │ It may be stuck in a loop.                       │
        │                                                  │
        │ [Allow]  [Deny]                                  │
        └─────────────────────────────────────────────────┘

        Allow → return True → set doom_loop_warned = True → agent continues
        Deny  → return False → inject guidance message → agent tries different approach
```

**Key design decisions:**

- **Reuses existing approval infrastructure**: No new UI components needed. The TUI blocking approval dialog and Web UI polling approval both work automatically.
- **Synthetic Operation**: Uses `OperationType.BASH_EXECUTE` with a `"doom_loop_check"` target because the Operation model requires these fields. The approval manager doesn't inspect the operation type - it just presents the prompt.
- **One-shot allowance**: After the user clicks "Allow", `doom_loop_warned` is set to True, preventing further prompts for the same session. This avoids the annoyance of repeated prompts if the user has decided the loop is intentional.
- **Async-safe fallback**: If running in an async context where blocking is impossible, falls back to automatic break (returns False).

### Flow in react_executor

```python
# In _process_tool_calls():
doom_warning = self._detect_doom_loop(tool_calls, ctx)
if doom_warning:
    user_allowed = self._request_doom_loop_approval(ctx, doom_warning)
    if user_allowed:
        ctx.doom_loop_warned = True  # Don't prompt again
    else:
        # Inject guidance and skip this iteration's tool execution
        ctx.messages.append({
            "role": "user",
            "content": f"[SYSTEM] {doom_warning} Try a different approach."
        })
        return LoopAction.CONTINUE
```

### File

`swecli/repl/react_executor.py` - modified `_detect_doom_loop()` (line ~268), added `_request_doom_loop_approval()` (line ~297), modified tool call processing (line ~1288)

---

## 5. Cost Display: Web UI + Exit Summary

### Problem

Phase 1 created `CostTracker` and wired it to the TUI status bar, but:

1. The Web UI had no cost display - `WebUICallback` didn't broadcast cost/context data
2. There was no session cost summary on exit - the user had to mentally track spending

### Design

#### Web UI Callbacks (`swecli/web/web_ui_callback.py`)

Added two WebSocket broadcast methods:

```python
def on_cost_update(self, total_cost_usd: float) -> None:
    self._broadcast({
        "type": "status_update",
        "data": {"session_cost": total_cost_usd},
    })

def on_context_update(self, usage_pct: float) -> None:
    self._broadcast({
        "type": "status_update",
        "data": {"context_usage_pct": usage_pct},
    })
```

The frontend receives these via the existing WebSocket `status_update` handler and can display them in the top bar.

#### Exit Summary (`swecli/repl/repl.py`)

On REPL exit, displays a session cost summary:

```
Session cost: $0.0142 | 49.1K tokens | 7 API calls
Goodbye!
```

Implementation searches for the `CostTracker` instance through the object hierarchy:

```python
cost_tracker = getattr(self, "_cost_tracker", None)
if cost_tracker is None:
    react_exec = getattr(self, "_react_executor", None)
    if react_exec:
        cost_tracker = getattr(react_exec, "_cost_tracker", None)

if cost_tracker and cost_tracker.total_cost_usd > 0:
    cost_str = cost_tracker.format_cost()
    tokens = cost_tracker.total_input_tokens + cost_tracker.total_output_tokens
    token_str = f"{tokens / 1000:.1f}K" if tokens >= 1000 else str(tokens)
    console.print(f"Session cost: {cost_str} | {token_str} tokens | "
                  f"{cost_tracker.call_count} API calls")
```

**Key decisions:**

- Only displays when `total_cost_usd > 0` (hides the line when no costs were tracked, e.g., if `model_info` was unavailable)
- Grey color (`GREY` style token) to keep it unobtrusive
- Searches up to 2 levels deep (`self -> _react_executor -> _cost_tracker`) to find the tracker regardless of where it was instantiated

### Files

- Modified: `swecli/web/web_ui_callback.py` - added `on_cost_update()`, `on_context_update()`
- Modified: `swecli/repl/repl.py` - added exit summary display, added `GREY` import

---

## 6. Structured Compaction Template

### Status: Already Implemented

The compaction prompt in `swecli/core/agents/prompts/templates/system/compaction.md` was reviewed and found to already use a well-structured template with goal/instructions/discoveries/accomplished sections. No changes were needed.

---

## 7. LSP Diagnostics After Edit

### Problem

After the agent edits a file, it has no immediate feedback about whether the edit introduced errors. The agent discovers errors only when it runs tests or when the user reports them. OpenCode automatically calls `LSP.touchFile(filepath, true)` after every edit and appends error diagnostics to the tool output.

### Design

```
Agent calls edit_file("src/main.py", old_content, new_content)
    │
    ├── assert_fresh() - stale-read check
    ├── apply_edit() - write file
    ├── invalidate() - clear stale-read record
    │
    └── _get_lsp_diagnostics("src/main.py")
        │
        ├── get_lsp_wrapper() - singleton LSP manager
        ├── wrapper.get_diagnostics(
        │       file_path,
        │       severity_filter=1,     # Errors only (not warnings)
        │       max_diagnostics=20,    # Cap to avoid context bloat
        │       timeout=3.0,           # Don't block too long
        │   )
        │
        ├── If diagnostics found:
        │   return "\n\nLSP errors detected:\n  Line 42: Expected ';'\n  Line 57: Undefined variable 'x'"
        │
        └── If no diagnostics or no LSP server:
            return ""  (silently skip)
```

#### LSPServerWrapper.get_diagnostics() (`swecli/core/context_engineering/tools/lsp/wrapper.py`)

```python
def get_diagnostics(
    self, file_path: str | Path, *,
    severity_filter: int = 1,      # 1=Error, 2=Warning, 3=Info, 4=Hint
    max_diagnostics: int = 20,
    timeout: float = 3.0,
) -> list[dict[str, Any]]:
```

Returns list of dicts:

```python
[
    {"severity": "Error", "message": "Expected ';'", "line": 42, "character": 10},
    {"severity": "Error", "message": "Undefined 'x'", "line": 57, "character": 5},
]
```

**Key design decisions:**

- **Errors only**: `severity_filter=1` means only Error-level diagnostics are shown. Warnings would be too noisy - the agent might try to "fix" style warnings, derailing the task.
- **20-diagnostic cap**: Prevents a badly broken file from flooding the context with 100+ errors.
- **3-second timeout**: LSP servers can be slow to produce diagnostics after a change. 3 seconds is enough for most language servers but doesn't stall the agent.
- **Graceful skip**: If no LSP server is running for the file type, `get_diagnostics()` returns `[]` and the edit output is unchanged. The feature adds no overhead when LSP is unavailable.
- **Static method**: `_get_lsp_diagnostics()` is a static method on `FileToolHandler` because it doesn't need instance state - it creates its own LSP wrapper.

#### Agent's View

```
Tool result (without LSP):
  File edited: src/main.py (+3/-1)

Tool result (with LSP errors):
  File edited: src/main.py (+3/-1)

  LSP errors detected:
    Line 42: Expected ';' after expression
    Line 57: Cannot find name 'x'
```

The agent sees the errors immediately and can self-correct in the same turn.

### Files

- Modified: `swecli/core/context_engineering/tools/lsp/wrapper.py` - added `get_diagnostics()` method
- Modified: `swecli/core/context_engineering/tools/handlers/file_handlers.py` - added `_get_lsp_diagnostics()` static method, wired into `edit_file()` output

---

## 8. Anthropic Prompt Caching

### Problem

Every LLM call re-sends the full system prompt. For Anthropic models, the system prompt is typically 8,000-15,000 tokens. Over a 50-turn session, that's 400,000-750,000 input tokens just for the system prompt. Anthropic offers a `cache_control` mechanism that caches stable content blocks between turns, giving a ~90% cost discount on cached input tokens.

OpenCode structures its system prompt as exactly 2 content blocks: a stable first block (with `cache_control: {"type": "ephemeral"}`) and a dynamic second block (no caching).

### Design

Three components work together:

#### 1. PromptComposer.compose_two_part() (`swecli/core/agents/prompts/composition.py`)

Each `PromptSection` now has a `cacheable` boolean field (default `True`):

```python
@dataclass
class PromptSection:
    name: str
    file_path: str
    condition: Optional[Callable] = None
    priority: int = 50
    cacheable: bool = True  # New field
```

`compose_two_part()` splits registered sections into two groups:

```
Sections (sorted by priority):
    ├── cacheable=True  → stable_parts
    │   - security_policy (priority 15)
    │   - tone_and_style (priority 20)
    │   - tool_selection (priority 50)
    │   - error_recovery (priority 60)
    │   - output_awareness (priority 85)
    │   - ... (most sections)
    │
    └── cacheable=False → dynamic_parts
        - scratchpad (priority 87)       ← changes per session
        - system_reminders_note (priority 95) ← changes per turn
```

Returns `tuple[str, str]` - `(stable_prompt, dynamic_prompt)`.

#### 2. AnthropicAdapter._build_system_with_cache() (`swecli/core/agents/components/api/anthropic_adapter.py`)

Converts the two-part split into Anthropic's content block format:

```python
@staticmethod
def _build_system_with_cache(stable_content: str, dynamic_content: str = "") -> Any:
    blocks = [{
        "type": "text",
        "text": stable_content,
        "cache_control": {"type": "ephemeral"},  # Cached across turns
    }]
    if dynamic_content:
        blocks.append({
            "type": "text",
            "text": dynamic_content,
            # No cache_control - regenerated each turn
        })
    return blocks
```

#### 3. Cache Metrics in Usage (`swecli/core/agents/components/api/anthropic_adapter.py`)

`_convert_usage()` now preserves Anthropic-specific cache metrics:

```python
def _convert_usage(self, anthropic_usage: Dict) -> Dict:
    result = {
        "prompt_tokens": anthropic_usage.get("input_tokens", 0),
        "completion_tokens": anthropic_usage.get("output_tokens", 0),
    }
    # Preserve cache metrics for cost tracking
    cache_read = anthropic_usage.get("cache_read_input_tokens", 0)
    cache_create = anthropic_usage.get("cache_creation_input_tokens", 0)
    if cache_read or cache_create:
        result["cache_read_input_tokens"] = cache_read
        result["cache_creation_input_tokens"] = cache_create
    return result
```

#### Request Flow

```
PromptComposer.compose_two_part(context)
    │
    ├── stable_prompt = "Security policy... Tone... Tools... Error recovery..."
    └── dynamic_prompt = "Scratchpad: ... System reminders: ..."
           │
           ▼
AnthropicAdapter.convert_request(payload)
    │
    ├── Extract system message from messages array
    ├── Get _system_dynamic from payload metadata
    │
    └── _build_system_with_cache(stable, dynamic)
            │
            ▼
        Anthropic API receives:
        {
          "system": [
            {"type": "text", "text": "<stable>", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "<dynamic>"}
          ],
          "messages": [...]
        }
            │
            ▼
        Turn 1: Cache MISS - full token charge, cache created
        Turn 2: Cache HIT  - ~90% discount on stable tokens
        Turn 3: Cache HIT  - ~90% discount on stable tokens
        ...
```

**Key design decisions:**

- **Only applied to Anthropic**: The `_build_system_with_cache()` call is inside `AnthropicAdapter`. OpenAI and other providers get the standard string format.
- **Default cacheable=True**: Most prompt sections are stable across the session (security policy, tool descriptions, code quality rules). Only explicitly dynamic sections (`scratchpad`, `system_reminders_note`) are marked `cacheable=False`.
- **Ephemeral cache type**: Anthropic's "ephemeral" cache lasts for 5 minutes of inactivity. For interactive sessions where turns happen every 10-60 seconds, this provides near-continuous cache hits.

### Cost Impact

For a typical 50-turn session with a 12,000-token system prompt:

```
Without caching: 50 turns × 12,000 tokens = 600,000 input tokens
With caching:    1 cache miss (12,000) + 49 cache hits (12,000 × 0.1) = 70,800 tokens equivalent
Savings:         ~88% reduction in system prompt input costs
```

### Files

- Modified: `swecli/core/agents/prompts/composition.py` - added `cacheable` field to `PromptSection`, `compose_two_part()` method, marked `scratchpad` and `system_reminders_note` as `cacheable=False`
- Modified: `swecli/core/agents/components/api/anthropic_adapter.py` - added `_build_system_with_cache()`, modified `convert_request()` to use it, updated `_convert_usage()` to preserve cache metrics
- Tests: `tests/test_anthropic_cache.py` (17 tests)

---

## 9. Two-Tier Compaction: Fast Pruning

### Problem

The staged compaction system from Phase 1 goes directly from AGGRESSIVE masking (90%) to full LLM-powered compaction (99%). The gap between 85-99% has no intermediate strategy. Full LLM compaction is expensive (~$0.01-0.05 per invocation) and slow (~3-5 seconds). Many sessions could stay under the limit with a cheaper intermediate step.

OpenCode adds a fast "pruning" pass: walk backwards through tool outputs, protect the last 40K tokens, and strip older outputs entirely. This is much cheaper than LLM summarization and often sufficient.

### Design

Added a new optimization level between MASK and AGGRESSIVE:

```
Context Usage    Stage              Action
────────────    ──────             ──────
0-70%           NONE               No action
70-80%          WARNING            Log warning, start tracking
80-85%          MASK               Progressive observation masking (keep 6 recent)
85-90%          PRUNE (NEW)        Fast pruning of old tool outputs
90-99%          AGGRESSIVE         Aggressive masking (keep 3 recent)
99%+            COMPACT            Full LLM-powered compaction
```

#### prune_old_tool_outputs() (`swecli/core/context_engineering/compaction.py`)

```
PRUNE_PROTECTED_TOKENS = 40_000  # Protect last ~40K tokens of tool output

Messages array (backwards):
    ├── tool_result_20  ← Protected (recent, within 40K budget)
    ├── tool_result_19  ← Protected
    ├── tool_result_18  ← Protected
    ├── ...
    ├── tool_result_5   ← LAST to fit in 40K budget
    ├── tool_result_4   ← PRUNED → "[pruned]"
    ├── tool_result_3   ← PRUNED → "[pruned]"
    ├── tool_result_2   ← PRUNED → "[pruned]"
    └── tool_result_1   ← PRUNED → "[pruned]"
```

Algorithm:

```python
def prune_old_tool_outputs(self, messages: list[dict]) -> list[dict]:
    # 1. Collect all tool result message indices (reverse order)
    tool_indices = [i for i in range(len(messages)-1, -1, -1)
                    if messages[i].get("role") == "tool"]

    # 2. Walk backwards, protecting recent tokens up to budget
    protected_tokens = 0
    protected_indices = set()
    for idx in tool_indices:
        content = messages[idx].get("content", "")
        if content.startswith("[ref:") or content == "[pruned]":
            continue  # Already processed
        token_estimate = len(content) // 4  # ~4 chars per token
        if protected_tokens + token_estimate <= PRUNE_PROTECTED_TOKENS:
            protected_tokens += token_estimate
            protected_indices.add(idx)

    # 3. Replace unprotected tool results with [pruned]
    for idx in tool_indices:
        if idx not in protected_indices:
            if not (content.startswith("[ref:") or content == "[pruned]"):
                messages[idx]["content"] = "[pruned]"
```

**Key design decisions:**

- **40K token budget**: Protects approximately the last 10-15 tool results (depending on size). This is enough for the agent to maintain awareness of recent context while aggressively stripping old results.
- **Backwards walk**: Most recent tool results are most relevant. The walk starts from the end and fills the protection budget, ensuring recent outputs are always preserved.
- **Coexists with masking**: Pruning runs after masking. Already-masked outputs (`[ref: ...]`) are skipped. Already-pruned outputs are also skipped. The two strategies are complementary, not conflicting.
- **Rough token estimate**: Uses `len(content) // 4` instead of a real tokenizer. This is intentionally imprecise - it's a budget heuristic, not a billing calculation. Exact token counting would be slower and provide negligible benefit for this use case.
- **Idempotent**: Multiple calls produce the same result. The method checks for `[pruned]` and `[ref:]` prefixes before modifying.

#### Integration in ReactExecutor

```python
if optimization_level == OptimizationLevel.PRUNE:
    compactor.prune_old_tool_outputs(api_messages)
    compactor.mask_old_observations(api_messages, OptimizationLevel.MASK)
```

When the PRUNE level fires, both pruning and masking are applied. Pruning strips the heaviest old outputs; masking replaces remaining old outputs with compact references.

### Files

- Modified: `swecli/core/context_engineering/compaction.py` - added `STAGE_PRUNE = 0.85`, `PRUNE_PROTECTED_TOKENS = 40_000`, `OptimizationLevel.PRUNE`, `prune_old_tool_outputs()` method, updated `check_usage()` threshold ordering
- Modified: `swecli/repl/react_executor.py` - added PRUNE handling in compaction section
- Tests: `tests/test_prune_compaction.py` (10 tests)

---

## 10. Persistent Permission Rules

### Problem

The `ApprovalRulesManager` from Phase 1 was session-only (ephemeral). When a user chose "Always allow git commands", that preference was lost when the session ended. OpenCode persists "always allow" rules to storage so preferences survive across sessions.

### Design

#### Persistence Paths

```
User-global rules:   ~/.opendev/permissions.json
Project-scoped rules: <project_dir>/.opendev/permissions.json
```

Project-scoped rules take higher priority (loaded after user-global, no deduplication needed since IDs are unique).

#### File Format

```json
{
  "version": 1,
  "rules": [
    {
      "id": "user_rule_git_push",
      "name": "Allow git push",
      "description": "Auto-approve git push commands",
      "rule_type": "prefix",
      "pattern": "git push",
      "action": "auto_approve",
      "enabled": true,
      "priority": 0,
      "created_at": "2026-03-03T10:00:00",
      "modified_at": null
    }
  ]
}
```

#### New Methods on ApprovalRulesManager

```python
class ApprovalRulesManager:
    USER_PERMISSIONS_PATH = Path.home() / ".opendev" / "permissions.json"

    def __init__(self, project_dir: Optional[str] = None):
        self._initialize_default_rules()  # Session-only danger rules
        self._load_persistent_rules()     # Load from disk (new)

    def add_persistent_rule(rule, scope="user") -> None
    def remove_persistent_rule(rule_id) -> bool
    def clear_persistent_rules(scope="all") -> int
    def list_persistent_rules() -> List[Dict]

    def _load_persistent_rules() -> None    # Load user-global + project-scoped
    def _load_rules_from_file(path) -> None # Load from a single file
    def _save_persistent_rules(scope) -> None
    def _delete_permissions_file(path) -> None
```

#### Loading Priority

```
ApprovalRulesManager.__init__()
    │
    ├── 1. _initialize_default_rules()
    │   └── default_danger_rm, default_danger_chmod (session-only, priority 100)
    │
    ├── 2. _load_rules_from_file(~/.opendev/permissions.json)
    │   └── User-global persistent rules
    │
    └── 3. _load_rules_from_file(<project>/.opendev/permissions.json)
        └── Project-scoped persistent rules (loaded last = highest priority for duplicates)
```

Duplicate detection: if a rule ID from a file already exists in memory, it is skipped. This prevents doubles when both user-global and project-scoped files contain the same rule.

#### Slash Commands

Two new slash commands in `CommandRouter`:

**`/permissions`** - Lists all non-default persistent rules:

```
Persistent permission rules:
  [user_rule_1] Allow git push - auto_approve on prefix:git push (enabled)
  [user_rule_2] Allow npm test - auto_approve on prefix:npm test (enabled)

Use /permissions clear to remove all persistent rules.
```

**`/permissions clear`** - Removes all persistent rules (keeps default danger rules):

```
Cleared 2 persistent rules.
```

**`/undo`** - Reverts to the previous snapshot (see section 11):

```
Reverted: Reverted 3 file(s) to previous state: src/main.py, src/utils.py, tests/test_main.py
```

### Files

- Modified: `swecli/core/runtime/approval/rules.py` - added persistence methods, `USER_PERMISSIONS_PATH`, `project_dir` parameter, load/save logic
- Modified: `swecli/ui_textual/controllers/command_router.py` - added `/permissions`, `/permissions clear`, `/undo` commands, updated help text
- Tests: `tests/test_persistent_rules.py` (16 tests)

---

## 11. Shadow Git Snapshot System

### Problem

The existing `UndoManager` tracks file operations (reads, writes, edits) but can't reliably restore arbitrary file states. It stores "before" content for each edit, but:

- It doesn't capture the full workspace state (only files the agent touched)
- Undo is per-operation, not per-step (an agent step may involve multiple file operations)
- Binary files and large files aren't handled well

OpenCode maintains a parallel shadow git repository that captures a tree hash at every agent step. Git's content-addressable storage provides efficient deduplication, binary file support, and atomic restoration.

### Design

#### Architecture

```
User's project directory                Shadow git repository
/home/user/my-project/                 ~/.opendev/snapshot/<project_id>/
    ├── src/                                ├── HEAD
    ├── tests/                              ├── objects/     ← tree/blob storage
    ├── .git/  ← user's real git            ├── refs/
    └── ...                                 └── info/
                                                └── exclude  ← synced from .gitignore
```

The shadow repo is initialized as a bare git repo (`git init --bare`). It uses `--work-tree` to point at the user's project directory for staging operations.

`<project_id>` is a 16-character hex string derived from `sha256(project_path)[:16]`.

#### SnapshotManager (`swecli/core/context_engineering/history/snapshot.py`)

```python
class SnapshotManager:
    _project_dir: str                # Absolute path to user's project
    _project_id: str                 # sha256(project_dir)[:16]
    _shadow_dir: Path                # ~/.opendev/snapshot/<project_id>/
    _snapshots: list[str]            # Stack of tree hashes (session-only)
    _initialized: bool

    def track() -> Optional[str]     # Capture state, return tree hash
    def patch(hash) -> List[str]     # Files changed since hash
    def revert(hash, files) -> List[str]  # Restore specific files
    def restore(hash) -> bool        # Full restoration
    def undo_last() -> Optional[str] # Convenience: revert to previous snapshot
    def cleanup() -> None            # git gc --prune=7.days
```

#### Snapshot Lifecycle

```
ReactExecutor.execute()
    │
    ├── Initialize SnapshotManager(working_dir)
    │   └── git init --bare ~/.opendev/snapshot/<id>/
    │
    ├── Initial snapshot: track()
    │   └── git --work-tree <project> add --all --force
    │       git write-tree → hash_0
    │
    ├── Agent step 1: edit src/main.py, edit tests/test.py
    │   └── (after tool execution) track()
    │       └── git add . && git write-tree → hash_1
    │
    ├── Agent step 2: run_command "pytest"
    │   └── No writes → no snapshot
    │
    ├── Agent step 3: write_file src/new_module.py
    │   └── track() → hash_2
    │
    └── User types /undo
        └── undo_last()
            ├── Pop hash_2
            ├── Target: hash_1
            ├── patch(hash_1) → ["src/new_module.py"]
            └── restore(hash_1) → reverts workspace to step 1 state
```

#### Git Operations

**track()** - Capture current state:

```bash
git --git-dir <shadow> --work-tree <project> add --all --force
git --git-dir <shadow> write-tree
# Returns: 40-char SHA-1 tree hash
```

`--force` bypasses `.gitignore` in the shadow context (we have our own exclude). `write-tree` creates a tree object without creating a commit, which is faster and avoids ref management.

**patch(hash)** - Get changed files:

```bash
git --git-dir <shadow> --work-tree <project> add --all --force
git --git-dir <shadow> write-tree  # current state
git --git-dir <shadow> diff-tree -r --name-only <old_hash> <new_hash>
# Returns: list of changed file paths
```

**restore(hash)** - Full workspace restoration:

```bash
git --git-dir <shadow> read-tree <hash>
git --git-dir <shadow> --work-tree <project> checkout-index --all --force
```

`read-tree` loads the tree into the shadow index; `checkout-index` writes the files to the working directory.

**revert(hash, files)** - Selective file restoration:

```bash
# For each file:
git --git-dir <shadow> --work-tree <project> checkout <hash> -- <file>
```

#### .gitignore Synchronization

On initialization, the shadow repo's `info/exclude` is populated with:

1. Contents of `<project>/.gitignore`
2. Contents of `<project>/.git/info/exclude`
3. Default patterns: `.git`, `node_modules`, `__pycache__`, `*.pyc`, `.venv`, `venv`

This ensures the shadow repo ignores the same files as the user's real git repo, plus common large directories that would slow down snapshot creation.

#### Trigger Points

Snapshots are only taken after **write operations** (file edits, file creates, command execution):

```python
_write_tools = {"write_file", "edit_file", "run_command"}
has_writes = any(tc["function"]["name"] in _write_tools for tc in tool_calls)
if has_writes:
    self._snapshot_manager.track()
```

Read-only operations (read_file, search, etc.) do not trigger snapshots, avoiding unnecessary overhead.

**Key design decisions:**

- **Tree hashes, not commits**: Using `write-tree` instead of `commit-tree` avoids creating commit objects, refs, and parent chains. Tree hashes are sufficient for snapshot/restore and are cheaper to create.
- **Session-only snapshot stack**: The `_snapshots` list is in-memory. Cross-session undo would require persisting the stack, which adds complexity without clear value (users rarely undo across sessions).
- **Bare repo**: `git init --bare` avoids creating a working tree inside the shadow directory. The working tree is always the user's project via `--work-tree`.
- **7-day prune**: `git gc --prune=7.days.ago` runs on cleanup, keeping a week of objects before garbage collection.
- **Graceful failure**: All operations are wrapped in try/except. If git fails (corrupt shadow repo, permissions issue), the feature silently degrades - no crashes, no user-visible errors.

#### Storage Efficiency

Git's content-addressable storage means:

- Identical files across snapshots are stored once (deduplicated by SHA-1)
- A snapshot of a 1000-file project where only 1 file changed adds ~1 blob object (~100 bytes overhead for tree entries)
- Typical session with 20 snapshots of a 500-file project: ~2-5 MB total shadow repo size

### Files

- Created: `swecli/core/context_engineering/history/snapshot.py` - `SnapshotManager` class, `_encode_project_id()`
- Modified: `swecli/repl/react_executor.py` - initialize `SnapshotManager` in `execute()`, snapshot after write operations in `_process_tool_calls()`
- Modified: `swecli/ui_textual/controllers/command_router.py` - `/undo` command
- Tests: `tests/test_snapshot.py` (18 tests)

---

## 12. Files Summary

### Created

| File | Purpose |
|------|---------|
| `swecli/core/context_engineering/tools/file_time.py` | Stale-read detection for file edits |
| `swecli/core/context_engineering/history/snapshot.py` | Shadow git snapshot system for per-step undo |
| `tests/test_file_time.py` | FileTimeTracker tests (10 tests) |
| `tests/test_snapshot.py` | SnapshotManager tests (18 tests) |
| `tests/test_persistent_rules.py` | Persistent permission rules tests (16 tests) |
| `tests/test_prune_compaction.py` | Two-tier compaction pruning tests (10 tests) |
| `tests/test_anthropic_cache.py` | Anthropic prompt caching + compose_two_part tests (17 tests) |

### Modified

| File | Changes |
|------|---------|
| `swecli/repl/react_executor.py` | Doom loop → approval pause, snapshot tracking, dynamic truncation hints, PRUNE compaction level |
| `swecli/repl/repl.py` | Session cost summary on exit |
| `swecli/core/context_engineering/compaction.py` | PRUNE threshold, `prune_old_tool_outputs()`, `OptimizationLevel.PRUNE` |
| `swecli/core/agents/prompts/composition.py` | `cacheable` field, `compose_two_part()` method |
| `swecli/core/agents/components/api/anthropic_adapter.py` | `_build_system_with_cache()`, cache metrics in usage |
| `swecli/core/runtime/approval/rules.py` | Persistent rule save/load, project-scoped rules |
| `swecli/core/context_engineering/tools/context.py` | `file_time_tracker` field on `ToolExecutionContext` |
| `swecli/core/context_engineering/tools/registry.py` | Instantiate `FileTimeTracker`, pass to context |
| `swecli/core/context_engineering/tools/handlers/file_handlers.py` | Stale-read checks, LSP diagnostics after edit |
| `swecli/core/context_engineering/tools/lsp/wrapper.py` | `get_diagnostics()` method |
| `swecli/ui_textual/controllers/command_router.py` | `/permissions`, `/undo` commands |
| `swecli/web/web_ui_callback.py` | `on_cost_update()`, `on_context_update()` broadcasts |
| `swecli/core/agents/prompts/templates/system/main/main-error-recovery.md` | Tables → bullet lists |
| `swecli/core/agents/prompts/templates/system/main/main-output-awareness.md` | Tables → bullet lists |

---

## 13. Test Coverage

### New Test Files

| File | Tests | Duration | Coverage |
|------|-------|----------|----------|
| `tests/test_file_time.py` | 10 | <0.1s | `record_read`, `assert_fresh` (stale detection), `invalidate`, `clear` |
| `tests/test_snapshot.py` | 18 | ~1s | `track`, `patch`, `restore`, `undo_last`, encoding, failure handling |
| `tests/test_persistent_rules.py` | 16 | <0.1s | Save/load, project-scoped, clear, matching (prefix/pattern/command), serialization |
| `tests/test_prune_compaction.py` | 10 | <0.1s | Threshold, protection budget, idempotency, already-masked skipping |
| `tests/test_anthropic_cache.py` | 17 | <0.1s | Cache blocks, two-part compose, usage metrics, conditions |
| **Total** | **71** | **~1.3s** | |

### Key Test Scenarios

- **FileTime stale detection**: Creates real temp files, records read, modifies file with `time.sleep(tolerance + 0.1s)`, asserts `assert_fresh()` returns error
- **Snapshot round-trip**: Creates temp project directory, writes files, tracks state, modifies files, restores to original - verifies file contents match
- **Persistent rules save/load**: Patches `USER_PERMISSIONS_PATH` to temp directory, adds rules, recreates manager from disk, verifies rules survive
- **Pruning budget**: Creates 20 tool results with 10K chars each (~50K tokens total), verifies some are pruned and recent ones protected
- **Anthropic cache blocks**: Verifies `_build_system_with_cache()` produces correct 2-element array with `cache_control` on first block only

### Regression Status

Full test suite: 1488 passed, 25 failed (all pre-existing), 6 errors (all pre-existing). No new failures introduced.

---

## Architecture Impact Summary

```
                    ┌─────────────────────────────────┐
                    │          ReAct Executor           │
                    │                                   │
                    │  ┌─────────┐   ┌──────────────┐  │
                    │  │ Doom    │   │ Snapshot     │  │
                    │  │ Loop    │   │ Manager      │  │
                    │  │ Approval│   │ (shadow git) │  │
                    │  └────┬────┘   └──────┬───────┘  │
                    │       │               │           │
                    │  ┌────▼────┐   ┌──────▼───────┐  │
                    │  │Approval │   │ /undo        │  │
                    │  │Manager  │   │ command      │  │
                    │  └─────────┘   └──────────────┘  │
                    └─────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
            ┌───────▼──────┐ ┌─────▼──────┐ ┌──────▼──────┐
            │ Tool Registry│ │ Compactor  │ │ Anthropic   │
            │              │ │            │ │ Adapter     │
            │ FileTime     │ │ PRUNE      │ │ Cache       │
            │ Tracker      │ │ Stage      │ │ Control     │
            │ (stale-read) │ │ (40K prot.)│ │ (2-part)    │
            └───────┬──────┘ └────────────┘ └─────────────┘
                    │
            ┌───────▼──────┐
            │ File Handler │
            │              │
            │ LSP          │
            │ Diagnostics  │
            │ (after edit) │
            └──────────────┘
```

These 11 improvements strengthen three dimensions of the system:

1. **Safety**: FileTime prevents overwrites, doom loop pause gives user control, snapshot undo enables recovery
2. **Efficiency**: Anthropic caching (~88% input cost reduction), PRUNE stage (defers LLM compaction), dynamic hints (better agent behavior)
3. **Observability**: Cost display in Web UI, exit summary, LSP diagnostics (immediate error feedback), persistent permissions (user preference memory)
