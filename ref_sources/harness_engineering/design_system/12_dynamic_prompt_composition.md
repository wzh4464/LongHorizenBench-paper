# Dynamic System Prompt Loading Architecture

How the system prompt is assembled at runtime from modular markdown sections, filtered by conditions, ordered by priority, and enriched with live environment data.

---

## Component Map

```
composition.py          loader.py            renderer.py          variables.py
PromptComposer          load_prompt()        PromptRenderer       PromptVariables
  register_section()    get_prompt_path()      render()             to_dict()
  compose()             _strip_frontmatter()                        ToolVariable
  _load_section()       load_tool_description()                     SystemReminderVariable

          ↕                     ↕                    ↕                    ↕

builders.py                                    environment.py
BasePromptBuilder                              EnvironmentCollector
  SystemPromptBuilder                            collect() → EnvironmentContext
  ThinkingPromptBuilder                        build_env_block()
  PlanningPromptBuilder                        build_git_status_block()
                                               build_project_structure_block()
                                               build_project_instructions_block()
```

---

## 1. PromptComposer - Core Assembly Engine

**File:** `swecli/core/agents/prompts/composition.py`

### Data Model

```python
@dataclass
class PromptSection:
    name: str                                          # "security_policy"
    file_path: str                                     # "system/main/main-security-policy.md"
    condition: Optional[Callable[[Dict], bool]] = None # None = always included
    priority: int = 50                                 # Lower = earlier in output
```

### Algorithm

```
compose(context) → str
  1. FILTER  - keep section if condition is None or condition(context) returns True
  2. SORT    - ascending by priority (10 before 90)
  3. LOAD    - read each .md file from disk, strip HTML-comment frontmatter
  4. JOIN    - concatenate with "\n\n"
```

Frontmatter stripping regex: `^\s*<!--.*?-->\s*` (DOTALL) - removes `<!-- ... -->` block at file start.

### Factory Functions

```python
create_default_composer(templates_dir)   # 18 sections for normal mode
create_thinking_composer(templates_dir)  # 4 sections for thinking mode
create_composer(templates_dir, mode)     # Dispatches by mode string
```

---

## 2. Section Registry - Normal Mode (18 sections)

```
PRIORITY  NAME                 FILE                              CONDITION
────────  ───────────────────  ──────────────────────────────    ──────────────────
  12      mode_awareness       main-mode-awareness.md            Always
  15      security_policy      main-security-policy.md           Always
  20      tone_and_style       main-tone-and-style.md            Always
  25      no_time_estimates    main-no-time-estimates.md         Always
  40      interaction_pattern  main-interaction-pattern.md       Always
  45      available_tools      main-available-tools.md           Always
  50      tool_selection       main-tool-selection.md            Always
  55      code_quality         main-code-quality.md              Always
  56      action_safety        main-action-safety.md             Always
  58      read_before_edit     main-read-before-edit.md          Always
  60      error_recovery       main-error-recovery.md            Always
  65      subagent_guide       main-subagent-guide.md            has_subagents
  70      git_workflow         main-git-workflow.md              in_git_repo
  75      task_tracking        main-task-tracking.md             todo_tracking_enabled
  85      output_awareness     main-output-awareness.md          Always
  87      scratchpad           main-scratchpad.md                session_id != None
  90      code_references      main-code-references.md           Always
  95      system_reminders     main-reminders-note.md            Always
```

### Thinking Mode (4 sections)

```
PRIORITY  NAME              FILE
────────  ────────────────  ─────────────────────────────────
  45      available_tools   thinking-available-tools.md
  50      subagent_guide    thinking-subagent-guide.md
  85      code_references   thinking-code-references.md
  90      output_rules      thinking-output-rules.md
```

---

## 3. Prompt Builders - Full Prompt Orchestration

**File:** `swecli/core/agents/components/prompts/builders.py`

### Builder Hierarchy

```
BasePromptBuilder
├── SystemPromptBuilder    _core_template = "system/main"
├── ThinkingPromptBuilder  _core_template = "system/thinking"
└── PlanningPromptBuilder  (standalone, no modular sections)
```

### Build Flow

```
BasePromptBuilder.build()
  │
  ├─ TRY: _build_modular_prompt()
  │       │
  │       ├─ load_prompt(_core_template)          → core role text from system/main.md
  │       ├─ create_composer(templates_dir, mode)  → PromptComposer with registered sections
  │       ├─ Build context dict:
  │       │    { in_git_repo, has_subagents, todo_tracking_enabled }
  │       ├─ composer.compose(context)             → filtered + sorted + joined sections
  │       └─ Return: core_text + "\n\n" + modular_sections
  │
  ├─ CATCH: _build_core_identity()                → monolithic fallback
  │
  ├─ + _build_environment()                       → EnvironmentContext formatted blocks
  ├─ + _build_project_instructions()              → CLAUDE.md / OPENDEV.md content
  ├─ + _build_skills_index()                      → SkillLoader.build_skills_index()
  └─ + _build_mcp_section()                       → connected MCP server list
      │
      └─ OR _build_mcp_config_section()           → setup instructions if none connected
```

### Final Prompt Structure

```
┌─────────────────────────────────────────────────┐
│  Core Role (system/main.md)                     │  ← Identity, capabilities
├─────────────────────────────────────────────────┤
│  Modular Sections (18 files, priority-ordered)  │  ← Behavioral guidelines
│    mode_awareness → security → tone → ...       │
│    ... → code_references → system_reminders     │
├─────────────────────────────────────────────────┤
│  Environment Block                              │  ← <env> tag with runtime data
├─────────────────────────────────────────────────┤
│  Git Status Block                               │  ← Branch, status, recent commits
├─────────────────────────────────────────────────┤
│  Project Structure Block                        │  ← Config files, tech stack, tree
├─────────────────────────────────────────────────┤
│  Project Instructions                           │  ← CLAUDE.md / OPENDEV.md content
├─────────────────────────────────────────────────┤
│  Skills Index                                   │  ← Available slash commands
├─────────────────────────────────────────────────┤
│  MCP Servers                                    │  ← Connected server list
└─────────────────────────────────────────────────┘
```

---

## 4. Template Variable Substitution

**Files:** `renderer.py`, `variables.py`

Templates use `${VAR}` syntax. The `PromptRenderer` resolves them via regex:

```
${EDIT_TOOL}       → ToolVariable("edit_file")     → "edit_file"
${EDIT_TOOL.name}  → attr access                   → "edit_file"
${BOOL_VAR}        → False becomes ""
${UNKNOWN}         → left as-is (no crash)
```

### Variable Registry

```python
PromptVariables
├── Tool References
│   ├── EDIT_TOOL          = ToolVariable("edit_file")
│   ├── WRITE_TOOL         = ToolVariable("write_file")
│   ├── READ_TOOL          = ToolVariable("read_file")
│   ├── BASH_TOOL          = ToolVariable("run_command")
│   ├── GLOB_TOOL          = ToolVariable("list_files")
│   ├── GREP_TOOL          = ToolVariable("search")
│   └── EXIT_PLAN_MODE_TOOL = ToolVariable("exit_plan_mode")
│
├── Name Shortcuts (for reminder templates)
│   ├── GLOB_TOOL_NAME     = "list_files"
│   ├── GREP_TOOL_NAME     = "search"
│   └── READ_TOOL_NAME     = "read_file"
│
├── Agent Configuration
│   ├── EXPLORE_AGENT_COUNT   = 3
│   ├── PLAN_AGENT_COUNT      = 1
│   └── EXPLORE_AGENT_VARIANT = "enabled"
│
└── Subagent References
    ├── EXPLORE_SUBAGENT = ToolVariable("Explore")
    └── PLAN_SUBAGENT    = ToolVariable("Plan")
```

This indirection means tool names can change in one place (`variables.py`) and all templates automatically pick up the new name.

---

## 5. Environment Context Collection

**File:** `swecli/core/agents/components/prompts/environment.py`

`EnvironmentCollector.collect()` runs once at startup and produces a frozen `EnvironmentContext` dataclass.

### Collection Steps

```
EnvironmentCollector.collect()
  │
  ├─ Git detection: (.git/ exists?)
  │   ├─ git rev-parse --abbrev-ref HEAD           → branch
  │   ├─ git symbolic-ref refs/remotes/origin/HEAD → default branch
  │   ├─ git status --porcelain                    → working tree status
  │   ├─ git log --oneline -5                      → recent commits
  │   └─ git config --get remote.origin.url        → remote URL
  │
  ├─ Shell & runtime
  │   ├─ $SHELL env var                            → shell path
  │   ├─ platform.python_version()                 → python version
  │   ├─ $VIRTUAL_ENV env var                      → venv name
  │   ├─ node --version                            → node version
  │   └─ shutil.which() for each package manager   → available managers
  │
  ├─ Project structure
  │   ├─ Scan for config files (pyproject.toml, package.json, Cargo.toml, ...)
  │   ├─ _infer_tech_stack()                       → "Python", "TypeScript/React", etc.
  │   └─ _build_directory_tree()                   → ASCII tree, depth=2
  │
  └─ Project instructions
      └─ config_manager.load_context_files()       → CLAUDE.md / OPENDEV.md content
```

### Tech Stack Inference Chain

```
Cargo.toml      → "Rust"
go.mod          → "Go"
pom.xml         → "Java"
Gemfile         → "Ruby"
composer.json   → "PHP"
CMakeLists.txt  → "C/C++"
package.json    → _detect_js_framework()
                    ├─ "next" in deps       → "TypeScript / Next.js"
                    ├─ "react" in deps      → "TypeScript / React" or "JavaScript / React"
                    ├─ "vue" in deps        → "JavaScript / Vue"
                    ├─ "@angular/core"      → "TypeScript / Angular"
                    ├─ "svelte" in deps     → "JavaScript / Svelte"
                    ├─ "typescript" in deps → "TypeScript"
                    └─ fallback             → "JavaScript / Node.js"
pyproject.toml  → "Python"
setup.py        → "Python"
requirements.txt → "Python"
```

### Formatting into Prompt Blocks

```
build_env_block()                  → "<env>Working directory: ... Platform: ...</env>"
build_git_status_block()           → "gitStatus: ... Current branch: ... Status: ..."
build_project_structure_block()    → "Detected config files: ... Tech stack: ... Directory tree: ..."
build_project_instructions_block() → "# Project Instructions\n<opendev-md>...</opendev-md>"
```

---

## 6. Template File Format

All `.md` templates follow this convention:

```markdown
<!--
name: 'System Prompt: Section Name'
description: What this section covers
version: 2.0.0
-->

# Section Header

Actual prompt content here...
Use ${TOOL_NAME} for variable substitution.
```

The `<!-- ... -->` frontmatter is metadata for humans - it is stripped by both `loader._strip_frontmatter()` and `composition._load_section()` before reaching the LLM.

---

## 7. Loader - File Resolution

**File:** `swecli/core/agents/prompts/loader.py`

```
load_prompt("system/main")
  │
  ├─ Try: templates/system/main.md    ← preferred (.md)
  ├─ Fallback: templates/system/main.txt   ← legacy (.txt)
  │
  ├─ Read file content
  ├─ Strip frontmatter if .md
  └─ Return stripped text

load_tool_description("write_file")
  └─ load_prompt("tools/tool-write-file")   ← underscore → kebab conversion
```

---

## 8. Prompt Lifecycle

### Initialization

```
MainAgent.__init__()
  └─ BaseAgent.__init__()
       ├─ self.system_prompt = self.build_system_prompt()   ← Full assembly
       └─ self.tool_schemas  = self.build_tool_schemas()
```

### Hot Refresh (MCP tools connect/disconnect)

```
BaseAgent.refresh_tools()
  ├─ self.tool_schemas  = self.build_tool_schemas()   ← Rebuild schemas
  └─ self.system_prompt = self.build_system_prompt()  ← Rebuild entire prompt
```

### Injection into LLM Call

```
run_sync(message, message_history)
  ├─ messages.insert(0, {"role": "system", "content": self.system_prompt})
  ├─ messages.append({"role": "user", "content": message})
  └─ call_llm(messages, tools=self.tool_schemas)
```

### Mode Switching

```
build_system_prompt(thinking_visible=False)  → SystemPromptBuilder   (18 sections)
build_system_prompt(thinking_visible=True)   → ThinkingPromptBuilder (4 sections)
PlanningPromptBuilder                        → Monolithic planner.md (no composer)
```

---

## 9. Two-Tier Fallback Strategy

```
build()
  │
  ├─ Tier 1: MODULAR
  │   ├─ Requires: templates/system/main/ directory exists
  │   ├─ Requires: system/main.md core template loadable
  │   ├─ Uses: PromptComposer with 18 registered sections
  │   └─ Result: core + filtered sections + env + project + skills + mcp
  │
  └─ Tier 2: MONOLITHIC (on any Tier 1 exception)
      ├─ Loads: single core template via load_prompt()
      └─ Result: core + env + project + skills + mcp
```

This ensures the agent can always start even if individual section files are missing or corrupt.

---

## 10. Conditional Context Dict

The context dict passed to `compose()` is built by the builder from the `EnvironmentContext` snapshot:

```python
context = {
    "in_git_repo": env_context.is_git_repo,     # gates: main-git-workflow.md
    "has_subagents": True,                        # gates: main-subagent-guide.md
    "todo_tracking_enabled": True,                # gates: main-task-tracking.md
    "session_id": ...,                            # gates: main-scratchpad.md
}
```

Currently `has_subagents` and `todo_tracking_enabled` are hardcoded `True`. The condition lambdas exist so these features can be toggled without changing the composer code - just pass a different context dict.

---

## Implementation References

| Component | File |
|---|---|
| PromptComposer | `swecli/core/agents/prompts/composition.py` |
| Prompt Builders | `swecli/core/agents/components/prompts/builders.py` |
| Template Loader | `swecli/core/agents/prompts/loader.py` |
| Template Renderer | `swecli/core/agents/prompts/renderer.py` |
| Template Variables | `swecli/core/agents/prompts/variables.py` |
| Environment Context | `swecli/core/agents/components/prompts/environment.py` |
| Base Agent (lifecycle) | `swecli/core/base/abstract/base_agent.py` |
| MainAgent (build_system_prompt) | `swecli/core/agents/main_agent.py:251` |
| Section templates | `swecli/core/agents/prompts/templates/system/main/` |
| Thinking templates | `swecli/core/agents/prompts/templates/system/thinking/` |
