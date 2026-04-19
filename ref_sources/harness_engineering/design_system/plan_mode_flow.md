# Plan Mode Flow

How OpenDev enters plan-mode, operates read-only, presents a structured plan for approval, and resumes execution.

---

## State Overview

```
                              👤 User Prompt
                                    │
                              ┌─────▼─────┐
                              │ MainAgent │
                              └─────┬─────┘
                                    │
                    ┌───────────────┴──────────────────┐
                    │                                  │
              /plan /trigger from prompt           Default
                    │                                  │
                    ▼                                  ▼
         PLAN  MODE                              NORMAL  MODE
   (PLANNING_TOOLS only,                   (all tools available,
    writes blocked)                         write / edit / run)
──────────────────────────────────────────────────────────────────
        │                                         │
        │                                         │
        ▼                                         │
 ┌──────────────────────┐                         │
 │  ModeManager = PLAN  │                         │
 │  Schema rebuilt:     │                         │
 │  PLANNING_TOOLS only │                         │
 └──────────┬───────────┘                         │
            │                                     │
            ▼                                     │
 ┌──────────────────────┐                         │
 │  spawn_subagent      │                         │
 │  type = "Planner"    │                         │
 └──────────┬───────────┘                         │
            │                                     │
            ▼                                     │
 ┌──────────────────────┐                         │
 │  Planner: Explore    │                         │
 │  read_file, search,  │                         │
 │  list_files,         │                         │
 │  find_symbol,        │                         │
 │  ± nested            │                         │
 │    Code-Explorers    │                         │
 └──────────┬───────────┘                         │
            │                                     │
            ▼                                     │
 ┌──────────────────────┐                         │
 │  Planner: Analyze    │                         │
 │  patterns, risks,    │                         │
 │  trade-offs, steps   │                         │
 └──────────┬───────────┘                         │
            │                                     │
            ▼                                     │
 ┌──────────────────────┐                         │
 │  Planner: Write plan │                         │
 │  ---BEGIN PLAN---    │                         │
 │  Goal / Context      │                         │
 │  Files / Steps       │                         │
 │  Verification/Risks  │                         │
 │  ---END PLAN---      │                         │
 └──────────┬───────────┘                         │
            │                                     │
            ▼                                     │
 ┌──────────────────────┐                         │
 │  parse_plan()        │                         │
 │  store_plan()        │                         │
 │  Present to user     │                         │
 └──────────┬───────────┘                         │
            │                                     │
    ┌───────┴───────┐                             │
    │               │                             │
 Revise           Approve ──────────────────────▶ │
 (stay, replan)      set_mode(NORMAL)             ▼
    │                todos → task panel   ┌───────────────────┐
    │                                     │  Execute steps    │
    │                                     │  write_file /     │
    │                                     │  edit_file /      │
    │                                     │  run_command      │
    │                                     │  mark todos done  │
    │                                     └────────┬──────────┘
    │                                              │
    │                                     ┌────────┴──────────┐
    │                                     │ Unexpected result? │
    │                                     │ scope change?      │
    │                                     └────────┬──────────┘
    │                                              │
    │◀──────────────────────────────── /plan ──────┘
    │                           set_mode(PLAN)
    ▼
 (back to top - Planner re-runs with
  current codebase as context)
```

---

## Available Tools in Plan Mode (PLANNING_TOOLS)

```
✅ Allowed                         ❌ Blocked
─────────────────────────          ───────────────────
read_file                          write_file
list_files                         edit_file
search (text + AST)                run_command (write)
fetch_url                          delete_file
web_search                         any state-mutating op
list_processes
get_process_output
read_pdf
find_symbol
find_referencing_symbols
search_tools (MCP discovery)
spawn_subagent  ←── Planner only
ask_user        ←── clarification
task_complete
```

Write operations are blocked at schema level - the LLM never sees tool schemas it cannot use.

**Source**: `swecli/core/agents/components/schemas/planning_builder.py`

---

## Plan Structure

The Planner outputs a structured markdown block delimited by sentinel markers:

```
---BEGIN PLAN---

## Goal
One-sentence description of what will be achieved.

## Context
Relevant background from codebase exploration.

## Files to Modify
- path/to/file.py
- path/to/other.py

## New Files to Create
- path/to/new_module.py

## Implementation Steps
1. Step one
2. Step two
3. Step three

## Verification
- [ ] Tests pass
- [ ] Linting clean

## Risks & Considerations
- Potential breaking change in X

---END PLAN---
```

`parse_plan()` extracts each section into a `ParsedPlan` dataclass. Steps are converted to todo items via `get_todo_items()` and surfaced in the UI task panel.

**Source**: `swecli/core/agents/components/response/plan_parser.py`

---

## Key Source Files

| File | Responsibility |
|------|----------------|
| `swecli/core/runtime/mode_manager.py` | `OperationMode` enum, mode switching, plan storage |
| `swecli/core/agents/components/schemas/planning_builder.py` | `PLANNING_TOOLS` constant |
| `swecli/core/agents/subagents/agents/planner.py` | Planner `SubAgentSpec` |
| `swecli/core/agents/components/response/plan_parser.py` | `parse_plan()`, `ParsedPlan` dataclass |
| `swecli/core/agents/prompts/templates/subagents/subagent-planner.md` | Planner system prompt |
