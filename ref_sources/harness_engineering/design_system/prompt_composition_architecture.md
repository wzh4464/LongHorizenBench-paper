# Prompt Composition Architecture

A detailed architecture reference showing how OpenDev assembles system prompts from modular sections, variables, tools, and runtime context.

---

## High-Level Assembly Pipeline

```mermaid
graph TD
    subgraph "Entry Points (Prompt Builders)"
        SPB["SystemPromptBuilder<br/><i>mode: system/main</i>"]
        TPB["ThinkingPromptBuilder<br/><i>mode: system/thinking</i>"]
        PPB["PlanningPromptBuilder<br/><i>standalone template</i>"]
    end

    subgraph "BasePromptBuilder.build()"
        B1["_build_modular_prompt()"]
        B2["_build_environment()"]
        B3["_build_project_instructions()"]
        B4["_build_skills_index()"]
        B5["_build_mcp_section()"]
    end

    SPB --> B1
    SPB --> B2
    SPB --> B3
    SPB --> B4
    SPB --> B5

    TPB --> B1
    TPB --> B2

    B1 --> COMP["PromptComposer.compose()"]

    subgraph "Final System Prompt"
        F["Core Identity<br/>+ Modular Sections<br/>+ Environment<br/>+ Project Instructions<br/>+ Skills Index<br/>+ MCP Servers"]
    end

    B1 --> F
    B2 --> F
    B3 --> F
    B4 --> F
    B5 --> F
```

---

## Detailed Component Architecture

```mermaid
graph LR
    subgraph "composition.py"
        CC["create_composer()"]
        CDC["create_default_composer()"]
        CTC["create_thinking_composer()"]
        PC["PromptComposer"]
        PS["PromptSection"]
    end

    subgraph "renderer.py"
        PR["PromptRenderer"]
        RV["replace_var()"]
    end

    subgraph "variables.py"
        PV["PromptVariables"]
        TV["ToolVariable"]
        SRV["SystemReminderVariable"]
    end

    subgraph "loader.py"
        LP["load_prompt()"]
        LTD["load_tool_description()"]
        GPP["get_prompt_path()"]
        SF["_strip_frontmatter()"]
    end

    subgraph "reminders.py"
        GR["get_reminder()"]
        PRS["_parse_sections()"]
    end

    CC --> CDC
    CC --> CTC
    CDC --> PC
    CTC --> PC
    PC --> PS
    PR --> PV
    PR --> RV
    LP --> GPP
    LP --> SF
    LTD --> LP
    GR --> PRS
```

---

## PromptComposer Internals

### Section Registration & Composition Flow

```mermaid
sequenceDiagram
    participant Builder as BasePromptBuilder
    participant Composer as PromptComposer
    participant FS as File System
    participant Output as Final Prompt

    Builder->>Composer: create_composer(templates_dir, mode)
    Note over Composer: Registers all sections<br/>with name, file_path,<br/>condition, priority

    Builder->>Composer: compose(context)
    Composer->>Composer: Filter sections by condition(ctx)
    Composer->>Composer: Sort by priority (ascending)

    loop Each active section
        Composer->>FS: Load .md template file
        FS-->>Composer: Raw markdown content
        Composer->>Composer: Strip <!-- frontmatter -->
    end

    Composer->>Output: Join sections with "\n\n"
    Output-->>Builder: Composed modular prompt string
```

---

## Main Mode: 16 Registered Sections

All sections live in `swecli/core/agents/prompts/templates/system/main/`.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    COMPOSED SYSTEM PROMPT                           │
│                  (Priority: lower = earlier)                        │
├──────┬──────────────────────────┬──────────┬────────────────────────┤
│ Pri  │ Section                  │ Cond.    │ File                   │
├──────┼──────────────────────────┼──────────┼────────────────────────┤
│      │ *** CORE IDENTITY ***    │          │                        │
│  12  │ Mode Awareness           │ Always   │ main-mode-awareness    │
│  15  │ Security Policy          │ Always   │ main-security-policy   │
│  20  │ Tone and Style           │ Always   │ main-tone-and-style    │
│  25  │ No Time Estimates        │ Always   │ main-no-time-estimates │
├──────┼──────────────────────────┼──────────┼────────────────────────┤
│      │ *** INTERACTION ***      │          │                        │
│  40  │ Interaction Pattern      │ Always   │ main-interaction-pat.  │
│  45  │ Available Tools          │ Always   │ main-available-tools   │
│  50  │ Tool Selection           │ Always   │ main-tool-selection    │
├──────┼──────────────────────────┼──────────┼────────────────────────┤
│      │ *** CODE & SAFETY ***    │          │                        │
│  55  │ Code Quality             │ Always   │ main-code-quality      │
│  56  │ Action Safety            │ Always   │ main-action-safety     │
│  58  │ Read Before Edit         │ Always   │ main-read-before-edit  │
│  60  │ Error Recovery           │ Always   │ main-error-recovery    │
├──────┼──────────────────────────┼──────────┼────────────────────────┤
│      │ *** CONDITIONAL ***      │          │                        │
│  65  │ Subagent Guide           │ has_sub  │ main-subagent-guide    │
│  70  │ Git Workflow             │ git_repo │ main-git-workflow      │
│  75  │ Task Tracking            │ todo_on  │ main-task-tracking     │
├──────┼──────────────────────────┼──────────┼────────────────────────┤
│      │ *** CONTEXT ***          │          │                        │
│  85  │ Output Awareness         │ Always   │ main-output-awareness  │
│  87  │ Scratchpad               │ session  │ main-scratchpad        │
│  90  │ Code References          │ Always   │ main-code-references   │
│  95  │ Reminders Note           │ Always   │ main-reminders-note    │
└──────┴──────────────────────────┴──────────┴────────────────────────┘
```

### Conditional Evaluation Logic

```python
context = {
    "in_git_repo":          env_context.is_git_repo,     # Git Workflow
    "has_subagents":        True,                         # Subagent Guide
    "todo_tracking_enabled": True,                        # Task Tracking
    "session_id":           session_id or None,           # Scratchpad
}
```

---

## Thinking Mode: 4 Registered Sections

Thinking mode is a reasoning pre-phase with **no tool execution**. It uses purpose-built sections from `system/thinking/`.

```
┌──────┬──────────────────────────┬────────────────────────────────────┐
│ Pri  │ Section                  │ File                               │
├──────┼──────────────────────────┼────────────────────────────────────┤
│  45  │ Available Tools          │ thinking-available-tools.md        │
│  50  │ Subagent Guide           │ thinking-subagent-guide.md         │
│  85  │ Code References          │ thinking-code-references.md        │
│  90  │ Output Rules             │ thinking-output-rules.md           │
└──────┴──────────────────────────┴────────────────────────────────────┘
```

---

## Dynamic Sections (Appended by Builder)

After the modular sections are composed, `BasePromptBuilder.build()` appends four dynamic sections:

```mermaid
graph TD
    subgraph "Dynamic Section Assembly"
        ENV["_build_environment()<br/>─────────────────<br/>• Working directory<br/>• OS / platform<br/>• Git branch / status<br/>• Shell info"]

        PROJ["_build_project_instructions()<br/>─────────────────<br/>• Loads SWECLI.md from project root<br/>• Custom per-project rules"]

        SKILLS["_build_skills_index()<br/>─────────────────<br/>• Queries SkillLoader<br/>• Lists available skills<br/>• Names + descriptions"]

        MCP["_build_mcp_section()<br/>─────────────────<br/>• Connected MCP servers<br/>• Server names (not tool schemas)<br/>• Lazy discovery via search_tools()"]
    end

    ENV --> FINAL["Final Prompt"]
    PROJ --> FINAL
    SKILLS --> FINAL
    MCP --> FINAL
```

---

## Variable Substitution Pipeline

Templates use `${VAR}` syntax. The `PromptRenderer` resolves variables from `PromptVariables` + runtime overrides.

```mermaid
graph LR
    subgraph "PromptVariables Registry"
        T1["EDIT_TOOL → edit_file"]
        T2["WRITE_TOOL → write_file"]
        T3["READ_TOOL → read_file"]
        T4["BASH_TOOL → run_command"]
        T5["GLOB_TOOL → list_files"]
        T6["GREP_TOOL → search"]
        T7["EXIT_PLAN_MODE_TOOL"]
        T8["ASK_USER_QUESTION_TOOL_NAME"]
        T9["EXPLORE_SUBAGENT"]
        T10["PLAN_SUBAGENT"]
    end

    subgraph "Runtime Overrides"
        R1["SYSTEM_REMINDER"]
        R2["Custom kwargs"]
    end

    subgraph "PromptRenderer.render()"
        LOAD["Load .md template"]
        STRIP["Strip <!-- frontmatter -->"]
        SUB["Regex: replace ${VAR}<br/>including ${TOOL.name}"]
    end

    T1 --> SUB
    R1 --> SUB
    LOAD --> STRIP --> SUB --> OUT["Rendered text"]
```

### Substitution Examples

| Template Syntax | Resolved Value |
|---|---|
| `${EDIT_TOOL.name}` | `edit_file` |
| `${BASH_TOOL.name}` | `run_command` |
| `${GREP_TOOL.name}` | `search` |
| `${ASK_USER_QUESTION_TOOL_NAME}` | `ask_user` |
| `${SYSTEM_REMINDER.planFilePath}` | `/path/to/plan.md` |
| `${SYSTEM_REMINDER.planExists}` | `True` / *(empty if False)* |

---

## Tool Description Loading

Each of the 37 tools has its own markdown description file loaded lazily by the tool registry.

```mermaid
graph TD
    TR["Tool Registry"] -->|"tool_name = 'write_file'"| LTD["load_tool_description()"]
    LTD -->|"kebab: 'write-file'"| LP["load_prompt('tools/tool-write-file')"]
    LP --> GPP["get_prompt_path()"]
    GPP -->|"Try .md first"| MD["templates/tools/tool-write-file.md"]
    GPP -->|"Fallback .txt"| TXT["templates/tools/tool-write-file.txt"]
    MD --> SF["_strip_frontmatter()"]
    SF --> DESC["Tool description string"]
```

### Tool Templates (37 files)

```
templates/tools/
├── tool-analyze-image.md        ├── tool-list-files.md
├── tool-ask-user.md             ├── tool-list-processes.md
├── tool-batch-tool.md           ├── tool-list-todos.md
├── tool-capture-screenshot.md   ├── tool-notebook-edit.md
├── tool-capture-web-screenshot  ├── tool-open-browser.md
├── tool-complete-todo.md        ├── tool-read-file.md
├── tool-create-plan.md          ├── tool-read-pdf.md
├── tool-edit-file.md            ├── tool-rename-symbol.md
├── tool-edit-plan.md            ├── tool-replace-symbol-body.md
├── tool-enter-plan-mode.md      ├── tool-run-command.md
├── tool-exit-plan-mode.md       ├── tool-search-tools.md
├── tool-fetch-url.md            ├── tool-search.md
├── tool-find-referencing-sym.md ├── tool-task-complete.md
├── tool-find-symbol.md          ├── tool-update-todo.md
├── tool-get-process-output.md   ├── tool-web-search.md
├── tool-get-subagent-output.md  ├── tool-write-file.md
├── tool-insert-after-symbol.md  ├── tool-write-todos.md
├── tool-insert-before-symbol.md └── tool-invoke-skill.md
└── tool-kill-process.md
```

---

## Subagent Prompt Templates (8 files)

Each subagent gets its own system prompt template, loaded when the subagent is spawned.

```
templates/subagents/
├── subagent-ask-user.md           ├── subagent-pr-reviewer.md
├── subagent-code-explorer.md      ├── subagent-project-init.md
├── subagent-planner.md            ├── subagent-security-reviewer.md
├── subagent-web-clone.md          └── subagent-web-generator.md
```

---

## Reminder System

Short runtime nudges and signals are stored in `templates/reminders.md` as named sections, parsed by `reminders.py`.

```mermaid
graph LR
    subgraph "reminders.md"
        S1["--- SECTION_A ---<br/>content..."]
        S2["--- SECTION_B ---<br/>content..."]
        S3["--- SECTION_C ---<br/>content..."]
    end

    PS["_parse_sections()"] --> CACHE["Module-level cache<br/>Dict[name → content]"]
    CACHE --> GR["get_reminder(name, **kwargs)"]
    GR -->|"str.format()"| OUT["Formatted reminder string"]

    subgraph "Fallback"
        TF["Individual .txt files<br/>e.g. docker_preamble.txt"]
    end

    GR -->|"Not in sections"| TF
```

---

## Specialized Prompt Templates

```
templates/
├── system/
│   ├── main.md              ← Core identity template (monolithic fallback)
│   ├── main/                ← 16 modular section files
│   ├── thinking.md          ← Thinking core identity
│   ├── thinking/            ← 4 thinking section files
│   ├── compaction.md        ← Context compaction prompt
│   ├── critique.md          ← Self-critique prompt
│   └── init.md              ← Initialization prompt
├── tools/                   ← 37 tool description files
├── subagents/               ← 8 subagent system prompts
├── generators/              ← 2 generator prompts
│   ├── generator-agent.md
│   └── generator-skill.md
├── memory/                  ← 3 memory analysis prompts
│   ├── memory-sentiment-analysis.md
│   ├── memory-topic-detection.md
│   └── memory-update-instructions.md
└── reminders.md             ← Named reminder sections
```

---

## End-to-End Assembly: SystemPromptBuilder

```mermaid
sequenceDiagram
    participant Agent as ReactExecutor
    participant SPB as SystemPromptBuilder
    participant Base as BasePromptBuilder
    participant Comp as PromptComposer
    participant Load as loader.py
    participant Rend as PromptRenderer
    participant FS as Templates Dir

    Agent->>SPB: build()
    SPB->>Base: _build_modular_prompt()

    Base->>Load: load_prompt("system/main")
    Load->>FS: Read system/main.md
    FS-->>Load: Core identity text
    Load-->>Base: core_prompt

    Base->>Comp: create_composer(dir, "system/main")
    Note over Comp: Registers 16 sections<br/>with priorities 12–95

    Base->>Comp: compose(context)
    Comp->>Comp: Filter by conditions
    Comp->>Comp: Sort by priority (asc)

    loop 16 active sections
        Comp->>FS: Read main-*.md
        FS-->>Comp: Section content
        Comp->>Comp: Strip frontmatter
    end

    Comp-->>Base: Joined modular sections

    Base->>Base: _build_environment()
    Note over Base: OS, cwd, git branch, shell

    Base->>Base: _build_project_instructions()
    Note over Base: Load SWECLI.md from project root

    Base->>Base: _build_skills_index()
    Note over Base: Query SkillLoader for available skills

    Base->>Base: _build_mcp_section()
    Note over Base: List connected MCP server names

    Base-->>Agent: Complete system prompt string

    Note over Agent: Prompt sent as system<br/>message to LLM API
```

---

## File Reference

| File | Purpose |
|---|---|
| [composition.py](file:///Users/nghibui/codes/swe-cli/swecli/core/agents/prompts/composition.py) | `PromptComposer`, section registration, `create_default_composer()`, `create_thinking_composer()` |
| [renderer.py](file:///Users/nghibui/codes/swe-cli/swecli/core/agents/prompts/renderer.py) | `PromptRenderer` with `${VAR}` substitution |
| [variables.py](file:///Users/nghibui/codes/swe-cli/swecli/core/agents/prompts/variables.py) | `PromptVariables` registry (tool refs, agent refs) |
| [loader.py](file:///Users/nghibui/codes/swe-cli/swecli/core/agents/prompts/loader.py) | `load_prompt()`, `load_tool_description()`, frontmatter stripping |
| [reminders.py](file:///Users/nghibui/codes/swe-cli/swecli/core/agents/prompts/reminders.py) | `get_reminder()` for runtime nudge strings |
| [builders.py](file:///Users/nghibui/codes/swe-cli/swecli/core/agents/components/prompts/builders.py) | `SystemPromptBuilder`, `ThinkingPromptBuilder`, `PlanningPromptBuilder` |
