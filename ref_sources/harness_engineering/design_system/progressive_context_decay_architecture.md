# Progressive Context Decay - Architecture Reference

**Version**: 1.0
**Last Updated**: 2026-02-26

---

## System Position

```
┌─────────────────────────────────────────────────────────────────┐
│                        ReAct Executor                           │
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ Thinking │───>│  Action  │───>│  Tool    │───>│ Persist  │  │
│  │  Phase   │    │  Phase   │    │  Exec    │    │  Step    │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │                                │              │         │
│       │                                │              │         │
│       ▼                                ▼              ▼         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │            Progressive Context Decay Layer              │   │
│  │                                                         │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │   │
│  │  │   Staged    │  │  Observation │  │   Output     │  │   │
│  │  │  Triggers   │  │   Masking    │  │  Offloading  │  │   │
│  │  └─────────────┘  └──────────────┘  └──────────────┘  │   │
│  │  ┌─────────────┐  ┌──────────────┐                    │   │
│  │  │  Artifact   │  │   History    │                    │   │
│  │  │   Index     │  │   Archival   │                    │   │
│  │  └─────────────┘  └──────────────┘                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│                   ┌────────────────┐                            │
│                   │  LLM API Call  │                            │
│                   │  (messages)    │                            │
│                   └────────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

```
                    ContextCompactor
                    ┌──────────────────────────────────────────┐
                    │                                          │
                    │  check_usage()  ──> OptimizationLevel    │
                    │  should_compact()  ──> bool (compat)     │
                    │                                          │
                    │  mask_old_observations()                 │
                    │    ├── MASK: keep recent 6               │
                    │    └── AGGRESSIVE: keep recent 3         │
                    │                                          │
                    │  compact()                               │
                    │    ├── archive_history()                 │
                    │    ├── _summarize() ──> LLM call         │
                    │    ├── artifact_index.as_summary()       │
                    │    └── inject archive path               │
                    │                                          │
                    │  archive_history()                       │
                    │    └── writes to scratch/                │
                    │                                          │
                    │  ┌────────────────┐                      │
                    │  │ ArtifactIndex  │                      │
                    │  │  .record()     │                      │
                    │  │  .as_summary() │                      │
                    │  │  .to_dict()    │                      │
                    │  │  .from_dict()  │                      │
                    │  └────────────────┘                      │
                    │                                          │
                    │  update_from_api_usage()                 │
                    │  usage_pct                               │
                    │  pct_until_compact                       │
                    │                                          │
                    └──────────────────────────────────────────┘
                                       │
                    ┌──────────────────┐│┌──────────────────────┐
                    │ ContextToken     │││ Scratch Filesystem   │
                    │ Monitor          │││                      │
                    │  .count_tokens() ││├ ~/.opendev/scratch/  │
                    └──────────────────┘││  {session_id}/       │
                                        ││   history_archive_*  │
                                        ││   {tool}_{id}.txt    │
                                        │└──────────────────────┘
                                        │
                    ┌───────────────────┘
                    │
              ReactExecutor
              ┌──────────────────────────────────────────────┐
              │                                              │
              │  _maybe_compact(ctx)                         │
              │    ├── check_usage() ──> level               │
              │    ├── mask_old_observations(level)           │
              │    └── compact() if level == COMPACT          │
              │                                              │
              │  _maybe_offload_output(name, id, output)     │
              │    ├── len > 8000? ──> write scratch file     │
              │    └── return preview + path                  │
              │                                              │
              │  _record_artifact(tool_name, tc, result)      │
              │    └── compactor.artifact_index.record()      │
              │                                              │
              │  _add_tool_result_to_history(msgs, tc, res)  │
              │    └── calls _maybe_offload_output()          │
              │                                              │
              │  _persist_step(ctx, tool_calls, results, ..) │
              │    └── calls _record_artifact() per tool      │
              │                                              │
              └──────────────────────────────────────────────┘
```

---

## Staged Trigger Pipeline

```
                         _maybe_compact() called every iteration
                                      │
                                      ▼
                              ┌───────────────┐
                              │ check_usage() │
                              └───────┬───────┘
                                      │
                    ┌─────────────────┼─────────────────────┐
                    │                 │                      │
               < 70%            70-80%              80-90%  │
                    │                 │                      │
                    ▼                 ▼                      ▼
              ┌──────────┐    ┌──────────┐         ┌──────────────┐
              │   NONE   │    │ WARNING  │         │     MASK     │
              │ (no-op)  │    │ (log)    │         │ mask 6+ old  │
              └──────────┘    └──────────┘         └──────────────┘
                                                          │
                    ┌─────────────────────────────────────┘
                    │                              │
               90-99%                           99%+
                    │                              │
                    ▼                              ▼
           ┌───────────────┐            ┌──────────────────┐
           │  AGGRESSIVE   │            │     COMPACT      │
           │ mask 3+ old   │            │ archive + LLM    │
           └───────────────┘            │ summary + inject │
                                        │ artifact index   │
                                        └──────────────────┘
```

---

## Observation Masking - Message Transformation

```
Messages array (API format):

Index  Role        Content                          State at MASK level
─────  ────        ───────                          ───────────────────
  0    system      "You are a helpful..."           preserved
  1    user        "Fix the auth bug"               preserved
  2    assistant   "" + tool_calls:[read_file]       preserved
  3    tool        "1  import os\n2  import..."     ──> "[ref: call_0 - see history]"
  4    assistant   "" + tool_calls:[edit_file]       preserved
  5    tool        "✓ File edited +10/-5"           ──> "[ref: call_1 - see history]"
  6    assistant   "" + tool_calls:[bash]            preserved
  7    tool        "All 12 tests passed"            ──> "[ref: call_2 - see history]"
  8    assistant   "" + tool_calls:[read_file]       preserved
  9    tool        "def main():\n  ..."             ──> "[ref: call_3 - see history]"
  ·    ·           ·                                 ·
  ·    ·           ·                                 ·
 28    assistant   "" + tool_calls:[search]          preserved
 29    tool        "src/auth.py:42 - ..."           preserved  ← recent 6
 30    assistant   "" + tool_calls:[edit_file]       preserved      │
 31    tool        "✓ File edited +3/-1"            preserved      │
 32    assistant   "" + tool_calls:[bash]            preserved      │
 33    tool        "FAIL: test_login ..."           preserved      │
 34    assistant   "" + tool_calls:[edit_file]       preserved      │
 35    tool        "✓ File edited +1/-1"            preserved      │
 36    assistant   "" + tool_calls:[bash]            preserved      │
 37    tool        "All 13 tests passed"            preserved  ← most recent
```

---

## Output Offloading - Interception Point

```
  Tool Execution
       │
       ▼
  ┌──────────────────────────────────────┐
  │ _add_tool_result_to_history()        │
  │                                      │
  │   output = result.get("output")      │
  │              │                       │
  │              ▼                       │
  │   ┌─────────────────────┐           │
  │   │ len(output) > 8000? │           │
  │   └──────────┬──────────┘           │
  │         no   │   yes                │
  │              │    │                  │
  │              │    ▼                  │
  │              │  ┌──────────────────┐ │
  │              │  │ Write to file:   │ │
  │              │  │ scratch/{sid}/   │ │
  │              │  │  {tool}_{id}.txt │ │
  │              │  └────────┬─────────┘ │
  │              │           │           │
  │              │           ▼           │
  │              │  ┌──────────────────┐ │
  │              │  │ Replace output:  │ │
  │              │  │ 500-char preview │ │
  │              │  │ + file path ref  │ │
  │              │  └────────┬─────────┘ │
  │              │           │           │
  │              ▼           ▼           │
  │         ┌─────────────────────┐     │
  │         │ messages.append({   │     │
  │         │   role: "tool",     │     │
  │         │   content: output   │     │
  │         │ })                  │     │
  │         └─────────────────────┘     │
  └──────────────────────────────────────┘
```

---

## Artifact Index - Lifecycle

```
  Tool Execution              Compaction                  Post-Compaction
  ─────────────              ──────────                  ────────────────

  read_file(a.py)                                        [CONVERSATION SUMMARY]
       │                                                  ...
       ▼                                                  ## Artifact Index
  ArtifactIndex              artifact_index               - `a.py` [read, modified]
  .record(a.py,              .as_summary()                - `b.py` [created] - 50 lines
    "read",            ────>      │                       - `c.py` [read] - 200 lines
    "150 lines")                  │
                                  ▼                       Agent retains file awareness
  edit_file(a.py)            "## Artifact Index           even though original messages
       │                      - `a.py` [read, modified]   were summarized away.
       ▼                      - `b.py` [created]..."
  .record(a.py,                   │
    "modified",                   │
    "+10/-5")                     ▼
                             Injected into
  write_file(b.py)           compact() summary
       │
       ▼
  .record(b.py,
    "created",
    "50 lines")
```

---

## Full Compaction Sequence

```
  compact(messages, system_prompt)
       │
       ├──1── archive_history(messages)
       │         │
       │         └── Write full conversation to:
       │             ~/.opendev/scratch/{sid}/history_archive_{ts}.md
       │             Return: archive_path
       │
       ├──2── Split messages
       │         │
       │         ├── head = messages[:1]          (system prompt)
       │         ├── middle = messages[1:-N]      (to summarize)
       │         └── tail = messages[-N:]         (keep recent)
       │
       ├──3── _summarize(middle)
       │         │
       │         ├── _sanitize_for_summarization()
       │         │     └── Replace tool results with summaries
       │         │
       │         └── LLM call with compaction prompt
       │               │
       │               ├── success ──> structured summary
       │               └── failure ──> _fallback_summary()
       │
       ├──4── Append artifact_index.as_summary()
       │
       ├──5── Append archive path reference
       │
       ├──6── Assemble: head + [summary_msg] + tail
       │
       ├──7── Reset API calibration
       │
       └──8── Reset stage warnings
```

---

## Filesystem Layout

```
~/.opendev/
  └── scratch/
       └── {session_id}/
            ├── history_archive_20260226_143052.md     ← pre-compaction archive
            ├── history_archive_20260226_152130.md     ← second compaction
            ├── read_file_call0a1b.txt                 ← offloaded tool output
            ├── run_command_call2c3d.txt                ← offloaded bash output
            └── search_call4e5f.txt                    ← offloaded search results
```

---

## Token Budget - Before vs After

```
Typical 40-step session, 30 tool calls, ~1500 tokens avg output

BEFORE (binary compaction at 99%):

  ┌──────────────────────────────────────────────┐
  │ System prompt        ███                3K   │
  │ User messages        ██                 2K   │
  │ Assistant text       █████              5K   │
  │ Tool call args       ██████████        10K   │
  │ Tool outputs (ALL)   ████████████████  45K   │ ← 80% of budget
  │                      ██████████████████      │
  │                      ████████████████        │
  │                                              │
  │ Total: ~65K tokens         Headroom: ~35K    │
  │ Compaction fires at: ~99K                    │
  └──────────────────────────────────────────────┘


AFTER (progressive decay):

  ┌──────────────────────────────────────────────┐
  │ System prompt        ███                3K   │
  │ User messages        ██                 2K   │
  │ Assistant text       █████              5K   │
  │ Tool call args       ██████████        10K   │
  │ Tool outputs:                                │
  │   Recent 6 (full)    ██████             9K   │
  │   Masked 19 (refs)   ██                 1K   │ ← was 28K
  │   Offloaded 5        █                  1K   │ ← was 15K
  │                                              │
  │ Total: ~31K tokens         Headroom: ~69K    │
  │ Compaction: probably never needed            │
  └──────────────────────────────────────────────┘

  Saved: ~34K tokens (52% reduction)
```

---

## Constants

```python
# Staged thresholds (fraction of max_context)
STAGE_WARNING    = 0.70
STAGE_MASK       = 0.80
STAGE_AGGRESSIVE = 0.90
STAGE_COMPACT    = 0.99

# Observation masking - tool results kept intact
MASK_KEEP_RECENT       = 6   # at MASK level
AGGRESSIVE_KEEP_RECENT = 3   # at AGGRESSIVE level

# Output offloading
OFFLOAD_THRESHOLD = 8000     # chars (~2000 tokens)
OFFLOAD_PREVIEW   = 500      # chars kept in context
```

---

## Integration Points

```
┌─────────────────────────────┐     ┌──────────────────────────┐
│ ReactExecutor               │     │ ContextCompactor         │
│                             │     │                          │
│ _maybe_compact() ──────────────> check_usage()              │
│                             │     │ mask_old_observations()  │
│                             │     │ compact()                │
│                             │     │   archive_history()      │
│                             │     │   _summarize()           │
│ _add_tool_result_to_history │     │                          │
│   └─ _maybe_offload_output ───>  scratch filesystem         │
│                             │     │                          │
│ _persist_step()             │     │                          │
│   └─ _record_artifact() ──────> artifact_index.record()     │
│                             │     │                          │
│ _push_context_usage() ─────────> usage_pct                  │
│                             │     │                          │
└─────────────────────────────┘     └──────────────────────────┘
         │                                    │
         ▼                                    ▼
┌─────────────────┐              ┌─────────────────────┐
│ UI Layer        │              │ Session Manager      │
│ on_context_usage│              │ save_session()       │
│ on_message()    │              │ (artifact_index      │
└─────────────────┘              │  persisted via       │
                                 │  session.metadata)   │
                                 └─────────────────────┘
```
