# SWE-CLI System Architecture (Enhanced)

**Enhanced System Architecture with Model Providers, Thinking/Critique, Skills, and Reminders**

This document extends the base system architecture with four key components that enable advanced agent capabilities: multi-model provider selection, extended thinking with self-critique, comprehensive skills management, and context-aware system reminders.

---

## How to Read This Diagram

- **Top-to-bottom flow**: System layers from entry point → UI → agent → tools → context → persistence
- **Left-to-right alternatives**: Parallel paths (TUI vs Web, Normal vs Plan mode)
- **Boxes**: Components, handlers, or logical groupings
- **Arrows**: Data flow and control flow
- **Annotations**: Side notes explaining data structures, decision logic, or patterns

---

## Enhanced System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         CLI ENTRY POINT (cli.py)                             │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ Parse Arguments:                                                       │  │
│  │  • --working-dir, -d      (set working directory)                      │  │
│  │  • --prompt, -p           (non-interactive single prompt)              │  │
│  │  • --continue, -c         (resume recent session)                      │  │
│  │  • --resume SESSION_ID    (resume specific session)                    │  │
│  │  • --verbose, -v          (enable detailed logging)                    │  │
│  │                                                                          │  │
│  │ Subcommands:                                                            │  │
│  │  • config (setup, show)                                                 │  │
│  │  • mcp (list, add, remove, enable, disable)                            │  │
│  │  • run ui (start web UI)                                                │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  Initialize Core Managers:                                                    │
│   • ConfigManager (hierarchical config loading)                               │
│   • SessionManager (project-scoped)                                           │
│   • ModeManager (Normal/Plan mode control)                                    │
│   • ApprovalManager (operation approval)                                      │
│   • UndoManager (history tracking)                                            │
│   • MCPManager (MCP server management)                                        │
└──────────────────────┬─────────────────────────────────────────────────────────┘
                       ↓
            ┌──────────┴──────────┐
            ↓ UI Selection        ↓
   ┌────────────────┐     ┌───────────────────┐
   │ TUI PATH       │     │  WEB UI PATH      │
   │ (default)      │     │  (run ui)         │
   └────────┬───────┘     └─────────┬─────────┘
            ↓                       ↓

┌───────────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE LAYER                                │
├─────────────────────────────────────────┬─────────────────────────────────────┤
│  TUI (Textual-based)                    │  WEB UI (FastAPI + React/Vite)      │
│  ════════════════════                   │  ════════════════════════════       │
│  swecli/ui_textual/                     │  swecli/web/ + web-ui/              │
│                                         │                                     │
│  ┌───────────────────────────────────┐ │  ┌──────────────────────────────┐   │
│  │ ChatApp (main.py)                 │ │  │ BACKEND (server.py)          │   │
│  │  • Main application container     │ │  │  • FastAPI server            │   │
│  │  • Manages widgets and screens    │ │  │  • REST API endpoints        │   │
│  │  • Runs in Textual event loop     │ │  │  • WebSocket connection      │   │
│  │                                   │ │  │  • State dict (state.py)     │   │
│  │ Components:                       │ │  │                              │   │
│  │  • ChatWidget (message display)   │ │  │ Endpoints:                   │   │
│  │  • InputWidget (user input)       │ │  │  /api/messages               │   │
│  │  • StatusBar (mode, autonomy)     │ │  │  /api/sessions               │   │
│  │  • Sidebar (session list)         │ │  │  /api/config                 │   │
│  │  • Modal dialogs                  │ │  │  /api/mcp                    │   │
│  └───────────────┬───────────────────┘ │  │  /ws (WebSocket)             │   │
│                  │                     │  └──────────┬───────────────────┘   │
│  ┌───────────────▼───────────────────┐ │             ↓                       │
│  │ UICallback (ui_callback.py)      │ │  ┌──────────────────────────────┐   │
│  │  • Agent → UI communication       │ │  │ FRONTEND (React/Zustand)     │   │
│  │  • Display tool calls/results     │ │  │  • web-ui/src/               │   │
│  │  • Show thinking blocks           │ │  │  • Built to swecli/web/static│   │
│  │  • Trigger approval modals        │ │  │                              │   │
│  │  • Nested tool call tracking      │ │  │ Components:                  │   │
│  │                                   │ │  │  • ChatView (messages)       │   │
│  │ Controllers:                      │ │  │  • Sidebar (sessions)        │   │
│  │  • ApprovalController (blocking)  │ │  │  • StatusBar (mode/autonomy) │   │
│  │  • AskUserPromptController        │ │  │  • ApprovalDialog (polling)  │   │
│  │  • PlanApprovalController         │ │  │  • AskUserDialog (polling)   │   │
│  └───────────────────────────────────┘ │  └──────────────────────────────┘   │
│                                         │                                     │
│  Approval Pattern: BLOCKING             │  Approval Pattern: POLLING          │
│   1. Show modal dialog                  │   1. Broadcast via WebSocket        │
│   2. Block thread until response        │   2. Poll state._pending_approvals  │
│   3. Return approval decision           │   3. User responds via API          │
│                                         │   4. Resolve and continue           │
└─────────────────────────────────────────┴─────────────────────────────────────┘
                       ↓                                   ↓
                       └───────────────┬───────────────────┘
                                       ↓
┌──────────────────────────────────────────────────────────────────────────────┐
│                              AGENT LAYER                                     │
│  ════════════════════════════════════════════════════════════════════       │
│  swecli/core/agents/                                                         │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ AgentDependencies (models/agent_deps.py)                             │   │
│  │  Dependency Injection Container                                      │   │
│  │  ───────────────────────────────                                     │   │
│  │  • mode_manager       (ModeManager - Normal/Plan mode)               │   │
│  │  • approval_manager   (ApprovalManager - operation approval)         │   │
│  │  • undo_manager       (UndoManager - history tracking)               │   │
│  │  • session_manager    (SessionManager - conversation persistence)    │   │
│  │  • working_dir        (Path - current working directory)             │   │
│  │  • console            (Rich Console - output)                        │   │
│  │  • config             (AppConfig - runtime configuration)            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ MODEL PROVIDER SELECTION (config/models.py)                          │   │
│  │  Multi-Model Architecture for Different Workloads                    │   │
│  │  ─────────────────────────────────────────────────                   │   │
│  │                                                                       │   │
│  │  Five Model Types (configured in AppConfig):                         │   │
│  │   • Normal Model       (main execution model for action phase)       │   │
│  │   • Thinking Model     (extended reasoning, fallback to normal)      │   │
│  │   • Critique Model     (self-critique, fallback chain)               │   │
│  │   • VLM Model          (image processing, fallback to normal)        │   │
│  │   • Compact Model      (summarization, fallback to normal)           │   │
│  │                                                                       │   │
│  │  Model Selection Flow:                                               │   │
│  │   config.model_provider (e.g., "anthropic", "openai", "fireworks")   │   │
│  │   config.model (e.g., "claude-sonnet-4", "gpt-4")                    │   │
│  │   → create_http_client_for_provider()                                │   │
│  │   → Route to provider-specific client (lazy initialization)          │   │
│  │                                                                       │   │
│  │  Provider Cache (24-hour TTL):                                       │   │
│  │   ~/.opendev/cache/providers/*.json                                  │   │
│  │   • Model capabilities (context_length, vision, reasoning)           │   │
│  │   • Parameter support (temperature, max_tokens)                      │   │
│  │   • Pricing information                                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  Mode Selection (mode_manager.current_mode):                                 │
│  ┌─────────────────────────┬──────────────────────────┐                     │
│  │ NORMAL MODE             │  PLAN MODE               │                     │
│  │ ═══════════             │  ═════════                │                     │
│  │ main_agent.py         │  planning_agent.py       │                     │
│  │                         │                          │                     │
│  │ MainAgent             │  PlanningAgent           │                     │
│  │  • Full tool access     │   • Read-only tools      │                     │
│  │  • Write/Edit/Bash      │   • No Write/Edit/Bash   │                     │
│  │  • Task spawning        │   • No task spawning     │                     │
│  │  • Implementation mode  │   • Planning mode        │                     │
│  │  • Max 10 iterations    │   • Max 10 iterations    │                     │
│  └─────────────────────────┴──────────────────────────┘                     │
│                       ↓                                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ EXTENDED REACT LOOP (Three-Phase Architecture)                       │   │
│  │  ════════════════════════════════════════════                        │   │
│  │                                                                       │   │
│  │  PHASE 0: Auto-Compaction (if token_count > 90% threshold)           │   │
│  │   • Summarize older messages                                         │   │
│  │   • Keep recent N interactions intact                                │   │
│  │                                                                       │   │
│  │                         ↓                                             │   │
│  │                 [Interrupt Check #1]                                 │   │
│  │                         ↓                                             │   │
│  │                                                                       │   │
│  │  PHASE 1: THINKING (if enabled)                                      │   │
│  │  ┌────────────────────────────────────────────────────────────┐     │   │
│  │  │ ThinkingHandler + ThinkingLevel Enum:                      │     │   │
│  │  │  • OFF (0)           - No thinking phase                   │     │   │
│  │  │  • QUICK (1)         - 50 words, brief reasoning           │     │   │
│  │  │  • NORMAL (2)        - 100 words [DEFAULT]                 │     │   │
│  │  │  • EXTENDED (3)      - 150 words, deeper analysis          │     │   │
│  │  │  • DEEP (4)          - 200 words, comprehensive reasoning  │     │   │
│  │  │  • SELF_CRITIQUE (5) - 100 words + critique phase          │     │   │
│  │  │                                                             │     │   │
│  │  │ Model: model_thinking (fallback to normal)                 │     │   │
│  │  │ LLM Call: call_thinking_llm(messages)                      │     │   │
│  │  │  • NO tool schemas (pure reasoning)                        │     │   │
│  │  │  • Word limit enforced by level                            │     │   │
│  │  │  • Returns thinking_trace string                           │     │   │
│  │  │                                                             │     │   │
│  │  │ UI Display: ui_callback.on_thinking(content)               │     │   │
│  │  │  • Dark gray styled blocks                                 │     │   │
│  │  │  • Collapsible in TUI                                      │     │   │
│  │  │                                                             │     │   │
│  │  │ Injection: thinking_trace appended as user message         │     │   │
│  │  └────────────────────────────────────────────────────────────┘     │   │
│  │                         ↓                                             │   │
│  │                 [Interrupt Check #2]                                 │   │
│  │                         ↓                                             │   │
│  │                                                                       │   │
│  │  PHASE 2: CRITIQUE (if level == SELF_CRITIQUE)                       │   │
│  │  ┌────────────────────────────────────────────────────────────┐     │   │
│  │  │ CritiqueHandler:                                            │     │   │
│  │  │  Model: Fallback chain (critique → thinking → normal)      │     │   │
│  │  │                                                             │     │   │
│  │  │  Step 1: Generate Critique                                 │     │   │
│  │  │   call_critique_llm(thinking_trace)                        │     │   │
│  │  │   • Evaluates logic soundness                              │     │   │
│  │  │   • Identifies risks and gaps                              │     │   │
│  │  │   • Returns critique string (<100 words)                   │     │   │
│  │  │                                                             │     │   │
│  │  │  Step 2: Refine Thinking                                   │     │   │
│  │  │   _refine_thinking_with_critique()                         │     │   │
│  │  │   • Append critique as user message                        │     │   │
│  │  │   • Call thinking LLM again                                │     │   │
│  │  │   • Returns improved thinking_trace                        │     │   │
│  │  │                                                             │     │   │
│  │  │  UI Display: ui_callback.on_critique(content)              │     │   │
│  │  │   • [Critique] prefix                                      │     │   │
│  │  │   • Only shown if thinking visible                         │     │   │
│  │  └────────────────────────────────────────────────────────────┘     │   │
│  │                         ↓                                             │   │
│  │                 [Interrupt Check #3]                                 │   │
│  │                         ↓                                             │   │
│  │                                                                       │   │
│  │  PHASE 3: ACTION (Standard ReAct Loop)                               │   │
│  │  ┌────────────────────────────────────────────────────────────┐     │   │
│  │  │ Model: Normal model + provider                             │     │   │
│  │  │ LLM Call: call_llm(messages, tools)                        │     │   │
│  │  │  • WITH tool schemas                                       │     │   │
│  │  │  • tool_choice="auto"                                      │     │   │
│  │  │  • Includes thinking trace (if available)                  │     │   │
│  │  │                                                             │     │   │
│  │  │ Loop (max 10 iterations):                                  │     │   │
│  │  │  1. Reason      (LLM analyzes situation)                   │     │   │
│  │  │  2. Act         (LLM selects tools to call)                │     │   │
│  │  │  3. Execute     (ToolRegistry.execute_tool)                │     │   │
│  │  │  4. Observe     (LLM sees tool results)                    │     │   │
│  │  │  5. Loop        (repeat until completion)                  │     │   │
│  │  │                                                             │     │   │
│  │  │ Termination:                                                │     │   │
│  │  │  • LLM outputs text only (no tool calls)                   │     │   │
│  │  │  • task_complete tool called                               │     │   │
│  │  │  • Max iterations reached                                  │     │   │
│  │  │  • Error or interrupt                                      │     │   │
│  │  └────────────────────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Subagent System (core/agents/subagents/)                            │   │
│  │  ════════════════════════════════════════                           │   │
│  │  • SubAgentManager (manager.py)                                     │   │
│  │  • Subagent Registry (subagents/agents/*.py)                        │   │
│  │                                                                      │   │
│  │  Available Subagents:                                               │   │
│  │   • general-purpose  (full tool access, multi-step tasks)           │   │
│  │   • code-explorer    (codebase navigation, search, analysis)        │   │
│  │   • planner          (implementation planning)                      │   │
│  │   • web-clone        (web scraping, page cloning)                   │   │
│  │   • web-generator    (web page generation)                          │   │
│  │   • ask-user         (user interaction, clarification)              │   │
│  │                                                                      │   │
│  │  Spawned via: spawn_subagent tool                                   │   │
│  │  Output via: get_subagent_output tool (background tasks)            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┬────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────────┐
│                         TOOL EXECUTION LAYER                                 │
│  ════════════════════════════════════════════════════════════════════       │
│  swecli/core/context_engineering/tools/                                      │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ ToolRegistry (registry.py)                                           │   │
│  │  Central tool dispatcher and coordinator                            │   │
│  │  ──────────────────────────────────────────                         │   │
│  │  • Tool name → Handler mapping                                      │   │
│  │  • MCP tool discovery (token-efficient)                             │   │
│  │  • SubAgent manager integration                                     │   │
│  │  • Skills system integration                                        │   │
│  │  • Batch tool support (parallel/serial execution)                   │   │
│  │                                                                      │   │
│  │  execute_tool(name, args, context) → result                         │   │
│  └──────────────────────────────┬───────────────────────────────────────┘   │
│                                 ↓                                             │
│        Handler Dispatch (based on tool_name)                                 │
│        ════════════════════════════════════                                  │
│                                                                               │
│  ┌─────────────────┬─────────────────┬─────────────────┬────────────────┐   │
│  ↓ FileToolHandler ↓ ProcessHandler  ↓ WebToolHandler  ↓ MCPHandler     ↓   │
│                                                                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ SKILLS SYSTEM (core/skills.py)                                       │   │
│  │  Reusable prompt templates and domain expertise                     │   │
│  │  ──────────────────────────────────────────────                     │   │
│  │                                                                       │   │
│  │  SkillLoader:                                                         │   │
│  │   • Discovers skills from three directories (priority order):        │   │
│  │     1. swecli/skills/builtin/        (lowest priority)               │   │
│  │     2. .opendev/skills/              (project-local)                 │   │
│  │     3. ~/.opendev/skills/            (user global, highest priority) │   │
│  │                                                                       │   │
│  │  Skill File Format (Markdown with YAML frontmatter):                 │   │
│  │   ---                                                                 │   │
│  │   name: commit                                                        │   │
│  │   description: Git commit best practices                             │   │
│  │   namespace: default                                                 │   │
│  │   ---                                                                 │   │
│  │   [Skill content: instructions, examples, guidelines...]             │   │
│  │                                                                       │   │
│  │  Discovery Flow:                                                      │   │
│  │   discover_skills() → Scan *.md files → Parse frontmatter            │   │
│  │   → Build _skills_metadata dict → Index by namespace:name            │   │
│  │                                                                       │   │
│  │  Lazy Loading:                                                        │   │
│  │   load_skill(name)                                                    │   │
│  │   → Check _skills_cache → Read file if not cached                    │   │
│  │   → Strip frontmatter → Create LoadedSkill → Cache result            │   │
│  │                                                                       │   │
│  │  Invocation (via invoke_skill tool):                                 │   │
│  │   1. Load skill content                                               │   │
│  │   2. Check deduplication (session._invoked_skills)                   │   │
│  │   3. Track invocation                                                 │   │
│  │   4. Return skill content → Injected into LLM context                │   │
│  │                                                                       │   │
│  │  System Prompt Integration:                                           │   │
│  │   build_skills_index() → Generate markdown list of available skills  │   │
│  │   → Injected into system prompt as <skills-index> section            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  HANDLER 1: FileToolHandler (handlers/file_handlers.py)                      │
│  ═══════════════════════════════════════════════════════                     │
│  Handles all file operations                                                 │
│                                                                               │
│  Tools:                                                                       │
│   • read_file      → FileOperations.read(path, offset, limit)                │
│   • write_file     → WriteTool.write(path, content) + approval check         │
│   • edit_file      → EditTool.edit(path, old_str, new_str) + approval        │
│   • list_files     → FileOperations.glob(pattern, path)                      │
│   • search         → FileOperations.grep(pattern, path, type, glob)          │
│                                                                               │
│  Implementations:                                                             │
│   • implementations/file_ops.py (FileOperations)                             │
│   • implementations/write_tool.py (WriteTool)                                │
│   • implementations/edit_tool.py (EditTool)                                  │
├───────────────────────────────────────────────────────────────────────────────┤
│  HANDLER 2: ProcessToolHandler (handlers/process_handlers.py)                │
│  ═══════════════════════════════════════════════════════════════════════     │
│  Handles process execution and management                                    │
│                                                                               │
│  Tools:                                                                       │
│   • run_command          → BashTool.execute(command, timeout, background)    │
│   • list_processes       → ProcessHandler.list_processes()                   │
│   • get_process_output   → ProcessHandler.get_output(task_id)                │
│   • kill_process         → ProcessHandler.kill(task_id)                      │
│   • spawn_subagent       → SubAgentManager.execute_subagent(type, task)      │
│   • get_subagent_output  → SubAgentManager.get_background_task_output()      │
│                                                                               │
│  Background Task Management:                                                 │
│   • ThreadPoolExecutor for background commands                               │
│   • Task ID tracking for output retrieval                                    │
│   • Interrupt token support (InterruptToken)                                 │
│                                                                               │
│  Implementations:                                                             │
│   • implementations/bash_tool.py (BashTool)                                  │
│   • subagents/manager.py (SubAgentManager)                                   │
├───────────────────────────────────────────────────────────────────────────────┤
│  HANDLER 3: WebToolHandler (handlers/web_handlers.py)                        │
│  ══════════════════════════════════════════════════════                      │
│  Handles web content fetching                                                │
│                                                                               │
│  Tools:                                                                       │
│   • fetch_url  → WebFetchTool.fetch(url, prompt)                             │
│                                                                               │
│  Implementations:                                                             │
│   • implementations/web_fetch_tool.py (WebFetchTool)                         │
├───────────────────────────────────────────────────────────────────────────────┤
│  HANDLER 4: WebSearchHandler (handlers/web_search_handler.py)                │
│  ═══════════════════════════════════════════════════════════                 │
│  Handles web search operations                                               │
│                                                                               │
│  Tools:                                                                       │
│   • web_search  → WebSearchTool.search(query, domains, max_results)          │
│                                                                               │
│  Implementations:                                                             │
│   • implementations/web_search_tool.py (WebSearchTool)                       │
├───────────────────────────────────────────────────────────────────────────────┤
│  HANDLER 5: MCPHandler (mcp/handler.py)                                      │
│  ═══════════════════════════════════                                         │
│  Handles MCP (Model Context Protocol) tool execution                         │
│                                                                               │
│  Tools: Dynamic (loaded from MCP servers)                                    │
│   • Format: mcp__<server>__<tool_name>                                       │
│   • Example: mcp__github__create_issue, mcp__sqlite__query                   │
│                                                                               │
│  Token-Efficient Discovery:                                                  │
│   • search_tools tool → Discover MCP tools by keyword                        │
│   • Auto-discovery on first use                                              │
│   • Only discovered tools included in LLM context                            │
│                                                                               │
│  MCP Manager:                                                                 │
│   • Server lifecycle management                                              │
│   • Tool schema caching                                                      │
│   • Server auto-start configuration                                          │
│                                                                               │
│  Implementations:                                                             │
│   • mcp/manager.py (MCPManager)                                              │
│   • mcp/handler.py (McpToolHandler)                                          │
├───────────────────────────────────────────────────────────────────────────────┤
│  ADDITIONAL HANDLERS (6-12):                                                 │
│  ════════════════════════════════                                            │
│   • AskUserHandler          (user interaction prompts)                       │
│   • NotebookEditHandler     (Jupyter notebook editing)                       │
│   • ScreenshotToolHandler   (screenshot capture/analysis)                    │
│   • TodoHandler             (task/todo management)                           │
│   • ThinkingHandler         (thinking mode control)                          │
│   • SearchToolsHandler      (MCP tool discovery)                             │
│   • BatchToolHandler        (parallel/serial multi-tool execution)           │
│                                                                               │
│  ADDITIONAL TOOL IMPLEMENTATIONS:                                            │
│  ════════════════════════════════                                            │
│  Symbol Tools (LSP-based code navigation):                                   │
│   • find_symbol, find_referencing_symbols                                    │
│   • insert_before_symbol, insert_after_symbol                                │
│   • replace_symbol_body, rename_symbol                                       │
│                                                                               │
│  Plan Mode Tools:                                                             │
│   • enter_plan_mode, exit_plan_mode                                          │
│   • create_plan, edit_plan                                                   │
│                                                                               │
│  Other:                                                                       │
│   • task_complete, read_pdf                                                  │
└───────────────────────────────────────────────────────────────────────────────┘
                                    ↓
                          Tool Results + Metadata
                                    ↓
┌──────────────────────────────────────────────────────────────────────────────┐
│                      CONTEXT ENGINEERING LAYER                               │
│  ════════════════════════════════════════════════════════════════════       │
│  swecli/core/context_engineering/                                            │
│                                                                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ SYSTEM REMINDERS (prompts/reminders.py)                              │   │
│  │  Context-aware error nudges and guidance                            │   │
│  │  ──────────────────────────────────────                             │   │
│  │                                                                       │   │
│  │  Reminder Storage (templates/reminders.md):                          │   │
│  │   Section-based markdown file with 20+ reminder templates:           │   │
│  │   • nudge_permission_error     (permission denied guidance)          │   │
│  │   • nudge_edit_mismatch        (edit string not found)               │   │
│  │   • nudge_file_not_found       (file path errors)                    │   │
│  │   • nudge_syntax_error         (Python/JS syntax issues)             │   │
│  │   • nudge_rate_limit           (API rate limiting)                   │   │
│  │   • nudge_timeout              (timeout errors)                      │   │
│  │   • thinking_trace_reminder    (inject thinking trace)               │   │
│  │   • incomplete_todos_nudge     (unfinished tasks)                    │   │
│  │   • failed_tool_nudge          (generic tool failure)                │   │
│  │                                                                       │   │
│  │  get_reminder(reminder_name, **kwargs):                              │   │
│  │   1. Parse reminders.md into sections dict (first call only)         │   │
│  │   2. Lookup section by name                                          │   │
│  │   3. Format placeholders (e.g., {count}, {todo_list})                │   │
│  │   4. Return formatted reminder text                                  │   │
│  │                                                                       │   │
│  │  Error Classification (_get_smart_nudge):                            │   │
│  │   Pattern matching on error messages:                                │   │
│  │   • "Permission denied"    → nudge_permission_error                  │   │
│  │   • "not found"/"No such"  → nudge_file_not_found                    │   │
│  │   • "SyntaxError"          → nudge_syntax_error                      │   │
│  │   • "rate limit"/"429"     → nudge_rate_limit                        │   │
│  │   • "timeout"/"timed out"  → nudge_timeout                           │   │
│  │   • "old_string"           → nudge_edit_mismatch                     │   │
│  │   • Default                → failed_tool_nudge                       │   │
│  │                                                                       │   │
│  │  Injection Points:                                                    │   │
│  │   1. Post-Tool-Failure (after N failures)                            │   │
│  │      IF error_count > threshold:                                     │   │
│  │        reminder = get_reminder(nudge_name)                           │   │
│  │        messages.append(system_message(reminder))                     │   │
│  │                                                                       │   │
│  │   2. Pre-Action-Phase (thinking trace)                               │   │
│  │      IF thinking_trace exists:                                       │   │
│  │        reminder = get_reminder("thinking_trace_reminder",            │   │
│  │                                trace=thinking_trace)                 │   │
│  │        messages.append(user_message(reminder))                       │   │
│  │                                                                       │   │
│  │   3. Pre-Action-Phase (incomplete todos)                             │   │
│  │      IF todos_incomplete AND task_completed:                         │   │
│  │        reminder = get_reminder("incomplete_todos_nudge",             │   │
│  │                                count=len(incomplete),                │   │
│  │                                todo_list=format_todos(incomplete))   │   │
│  │        messages.append(system_message(reminder))                     │   │
│  │                                                                       │   │
│  │   4. Plan Mode Entry                                                 │   │
│  │      IF mode_switch_to_plan:                                         │   │
│  │        reminder = get_reminder("plan_mode_nudge")                    │   │
│  │        messages.append(system_message(reminder))                     │   │
│  │                                                                       │   │
│  │   5. Skill System (deduplication)                                    │   │
│  │      IF skill already invoked:                                       │   │
│  │        reminder = get_reminder("skill_already_loaded")               │   │
│  │        return as tool result                                         │   │
│  │                                                                       │   │
│  │  Format: Wrapped in <system-reminder> XML tags for clarity           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  COMPONENT 1: Prompt System (core/agents/prompts/)                           │
│  ═══════════════════════════════════════════════════                         │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ PromptComposer (composition.py)                                      │   │
│  │  Modular section-based prompt assembly                              │   │
│  │  ───────────────────────────────────────                            │   │
│  │                                                                      │   │
│  │  Flow:                                                               │   │
│  │   1. Register sections with priorities and conditions               │   │
│  │   2. Filter sections based on current context                       │   │
│  │   3. Sort by priority (lower = higher priority)                     │   │
│  │   4. Render templates with variable substitution                    │   │
│  │   5. Compose final system prompt                                    │   │
│  │                                                                      │   │
│  │  Prompt Sections (templates/system/main/):                          │   │
│  │   • main-header.md              (priority: 0)                       │   │
│  │   • security-policy.md          (priority: 10)                      │   │
│  │   • main-tool-selection.md      (priority: 20)                      │   │
│  │   • main-subagent-guide.md      (priority: 30)                      │   │
│  │   • git-workflow.md             (priority: 40)                      │   │
│  │   • file-operations.md          (priority: 50)                      │   │
│  │   • approval-system.md          (priority: 60)                      │   │
│  │   • plan-mode.md                (conditional: plan mode)            │   │
│  │   • main-tone-style.md          (priority: 100)                     │   │
│  │                                                                      │   │
│  │  Template Rendering (renderer.py + loader.py):                      │   │
│  │   • Variable substitution ({{variable}})                            │   │
│  │   • Conditional blocks                                              │   │
│  │   • File system template loading                                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  COMPONENT 2: Context Compaction (compaction.py)                             │
│  ════════════════════════════════════════════════                            │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Compactor                                                            │   │
│  │  Automatic context compression when token limit approached          │   │
│  │  ──────────────────────────────────────────────────────────         │   │
│  │                                                                      │   │
│  │  Flow:                                                               │   │
│  │   1. Check token count vs max context                               │   │
│  │   2. If > 90% threshold → Trigger compaction                        │   │
│  │   3. Summarize older messages                                       │   │
│  │   4. Keep recent messages intact                                    │   │
│  │   5. Update session with compacted history                          │   │
│  │                                                                      │   │
│  │  Trigger Conditions:                                                │   │
│  │   • Before LLM call if token_count > 0.9 * max_tokens               │   │
│  │   • Preserves last N interactions                                   │   │
│  │   • Compacts older conversation history                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  COMPONENT 3: Memory System (memory/)                                        │
│  ═══════════════════════════════════                                         │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Auto-Memory (memory/auto_memory.py)                                 │   │
│  │  Persistent memory files across sessions                            │   │
│  │  ─────────────────────────────────────────                          │   │
│  │                                                                      │   │
│  │  Storage:                                                            │   │
│  │   • ~/.claude/projects/{encoded-path}/memory/                       │   │
│  │   • MEMORY.md (main memory, always loaded, max 200 lines)           │   │
│  │   • Topic files (detailed notes, linked from MEMORY.md)             │   │
│  │                                                                      │   │
│  │  Usage:                                                              │   │
│  │   • Record patterns, conventions, user preferences                  │   │
│  │   • Store architectural decisions                                   │   │
│  │   • Save solutions to recurring problems                            │   │
│  │   • Update/remove outdated or wrong information                     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  COMPONENT 4: MCP Integration (mcp/)                                         │
│  ═══════════════════════════════════                                         │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ MCPManager (mcp/manager.py)                                          │   │
│  │  Model Context Protocol server and tool management                  │   │
│  │  ──────────────────────────────────────────────────                 │   │
│  │                                                                      │   │
│  │  Responsibilities:                                                   │   │
│  │   • Server lifecycle (start, stop, restart)                         │   │
│  │   • Tool discovery and caching                                      │   │
│  │   • Server configuration (enable, disable, auto-start)              │   │
│  │   • Tool schema extraction                                          │   │
│  │                                                                      │   │
│  │  Configuration:                                                      │   │
│  │   • .opendev/mcp.json (project-scoped)                              │   │
│  │   • ~/.opendev/mcp.json (global)                                    │   │
│  │                                                                      │   │
│  │  Tool Format: mcp__<server>__<tool_name>                            │   │
│  │  Example: mcp__github__create_issue                                 │   │
│  │                                                                      │   │
│  │  Token Efficiency:                                                   │   │
│  │   • Only discovered tools included in LLM context                   │   │
│  │   • Use search_tools to discover before first use                   │   │
│  │   • Auto-discovery on direct tool call                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  COMPONENT 5: Symbol Tools (symbol_tools/)                                   │
│  ════════════════════════════════════════════                                │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ AST-based Code Navigation                                           │   │
│  │  Parse and manipulate code using abstract syntax trees              │   │
│  │  ───────────────────────────────────────────────────────            │   │
│  │                                                                      │   │
│  │  Capabilities:                                                       │   │
│  │   • Find function/class definitions                                 │   │
│  │   • Find all references to symbols                                  │   │
│  │   • Insert code before/after symbols                                │   │
│  │   • Replace function/class bodies                                   │   │
│  │   • Rename symbols with refactoring                                 │   │
│  │                                                                      │   │
│  │  Implementation:                                                     │   │
│  │   • Python: ast module                                              │   │
│  │   • JavaScript/TypeScript: tree-sitter (if available)               │   │
│  │   • Fallback: regex-based search                                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────────┐
│                         PERSISTENCE LAYER                                    │
│  ════════════════════════════════════════════════════════════════════       │
│  swecli/core/context_engineering/history/                                    │
│                                                                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  COMPONENT 1: Session Management (session_manager.py)                        │
│  ═════════════════════════════════════════════════                           │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ SessionManager                                                       │   │
│  │  Conversation persistence and CRUD operations                       │   │
│  │  ─────────────────────────────────────────────                      │   │
│  │                                                                      │   │
│  │  Storage Structure:                                                  │   │
│  │   • ~/.opendev/projects/{encoded-path}/                             │   │
│  │     ├── sessions/{session-id}.json                                  │   │
│  │     ├── sessions-index.json                                         │   │
│  │     └── .current-session                                            │   │
│  │                                                                      │   │
│  │  Operations:                                                         │   │
│  │   • create_session(working_directory) → Session                     │   │
│  │   • save_session() → Persist to disk                                │   │
│  │   • load_session(session_id) → Session                              │   │
│  │   • list_sessions() → List[SessionMetadata]                         │   │
│  │   • delete_session(session_id) → bool                               │   │
│  │   • add_message(message, auto_save_interval) → void                 │   │
│  │                                                                      │   │
│  │  Session Indexing:                                                   │   │
│  │   • sessions-index.json maintains metadata                          │   │
│  │   • Enables fast listing without loading full sessions              │   │
│  │   • Includes title from TopicDetector                               │   │
│  │                                                                      │   │
│  │  Auto-Save:                                                          │   │
│  │   • Configurable interval (default: every message)                  │   │
│  │   • Atomic writes (temp file + rename)                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Data Structures                                                      │   │
│  │  ═══════════════                                                     │   │
│  │                                                                      │   │
│  │  ChatSession (models/session.py):                                   │   │
│  │   • id: str (8-character hex)                                       │   │
│  │   • created_at: datetime                                            │   │
│  │   • updated_at: datetime                                            │   │
│  │   • messages: ValidatedMessageList[ChatMessage]                     │   │
│  │   • context_files: list[str]                                        │   │
│  │   • working_directory: Optional[str]                                │   │
│  │   • metadata: dict[str, Any]                                        │   │
│  │   • playbook: Optional[dict] (ACE Playbook)                         │   │
│  │   • file_changes: list[FileChange]                                  │   │
│  │                                                                      │   │
│  │  ChatMessage (models/message.py):                                   │   │
│  │   • role: Role (user, assistant, system, tool)                      │   │
│  │   • content: str                                                    │   │
│  │   • tool_calls: list[ToolCall]                                      │   │
│  │   • metadata: dict[str, Any]                                        │   │
│  │   • thinking_trace: Optional[str]                                   │   │
│  │   • reasoning_content: Optional[str]                                │   │
│  │   • token_usage: Optional[dict]                                     │   │
│  │                                                                      │   │
│  │  ToolCall:                                                           │   │
│  │   • id: str                                                          │   │
│  │   • name: str                                                        │   │
│  │   • parameters: dict[str, Any]                                      │   │
│  │   • result: Optional[Any]                                           │   │
│  │   • result_summary: Optional[str] (concise summary)                 │   │
│  │   • error: Optional[str]                                            │   │
│  │                                                                      │   │
│  │  ValidatedMessageList:                                              │   │
│  │   • Enforces tool_use ↔ tool_result pairing invariants             │   │
│  │   • Validates on append                                             │   │
│  │   • Prevents corrupted message sequences                            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  COMPONENT 2: Configuration Management (core/runtime/config.py)              │
│  ══════════════════════════════════════════════════════════════              │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ ConfigManager                                                        │   │
│  │  Hierarchical configuration loading                                 │   │
│  │  ──────────────────────────────────                                 │   │
│  │                                                                      │   │
│  │  Priority Order (highest to lowest):                                │   │
│  │   1. .opendev/settings.json (project-scoped)                        │   │
│  │   2. ~/.opendev/settings.json (user global)                         │   │
│  │   3. Environment variables (OPENDEV_*)                              │   │
│  │   4. Default values                                                  │   │
│  │                                                                      │   │
│  │  Configuration Fields:                                              │   │
│  │   • model: str (e.g., "gpt-4", "claude-3-opus")                     │   │
│  │   • provider: str (e.g., "openai", "anthropic")                     │   │
│  │   • api_key: str                                                     │   │
│  │   • base_url: Optional[str]                                         │   │
│  │   • max_tokens: int                                                  │   │
│  │   • temperature: float                                              │   │
│  │   • auto_save_interval: int                                         │   │
│  │   • max_undo_history: int                                           │   │
│  │   • verbose: bool                                                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  COMPONENT 3: Provider Cache (core/runtime/provider_cache.py)                │
│  ═══════════════════════════════════════════════════════                     │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Provider Cache System                                                │   │
│  │  Model/provider configuration caching                               │   │
│  │  ──────────────────────────────────                                 │   │
│  │                                                                      │   │
│  │  Storage:                                                            │   │
│  │   • ~/.opendev/cache/providers/*.json                               │   │
│  │   • 24-hour TTL                                                      │   │
│  │                                                                      │   │
│  │  Data Source:                                                        │   │
│  │   • models.dev API (fetch on cache miss)                            │   │
│  │   • No bundled fallback                                             │   │
│  │   • Blocking sync on first startup if cache empty                   │   │
│  │                                                                      │   │
│  │  Content:                                                            │   │
│  │   • Available models per provider                                   │   │
│  │   • Model capabilities (context window, vision, etc.)               │   │
│  │   • Pricing information                                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Enhancements in This Architecture

### 1. Multi-Model Provider System

**Purpose**: Optimize different workloads with specialized models

**Architecture**:
- **Five Model Types**: Normal (main execution), Thinking (extended reasoning), Critique (self-evaluation), VLM (vision), Compact (summarization)
- **Lazy HTTP Client Initialization**: Separate clients only created when needed
- **Fallback Chains**: Critique → Thinking → Normal ensures graceful degradation
- **Provider Cache**: 24-hour TTL cache for model capabilities and pricing

**Benefits**:
- Cost optimization (use cheaper models for thinking)
- Performance optimization (use faster models for actions)
- Quality optimization (use specialized models for vision/reasoning)

### 2. Extended ReAct Loop with Thinking & Critique

**Purpose**: Enable deeper reasoning before action

**Three-Phase Architecture**:

**Phase 0 - Auto-Compaction**:
- Triggers when token count > 90% of max
- Summarizes older messages
- Keeps recent N interactions intact

**Phase 1 - Thinking**:
- Five thinking levels (OFF, QUICK, NORMAL, EXTENDED, DEEP, SELF_CRITIQUE)
- Uses dedicated thinking model (or fallback to normal)
- Pure reasoning without tools
- Word limits enforced by level (50-200 words)
- Thinking trace injected into next phase

**Phase 2 - Critique** (only for SELF_CRITIQUE level):
- Evaluates thinking for logic soundness, completeness, risks
- Uses critique model (fallback chain: critique → thinking → normal)
- Generates critique (<100 words)
- Refines thinking based on critique
- Both critique and improved thinking injected into action phase

**Phase 3 - Action**:
- Standard ReAct loop with tools
- Uses normal model
- Includes thinking trace (if available) in context
- Max 10 iterations with standard termination conditions

**Benefits**:
- Reduces impulsive tool calls
- Improves decision quality through self-reflection
- Catches logical errors before execution
- Transparent reasoning visible to users

### 3. Comprehensive Skills System

**Purpose**: Reusable domain expertise and prompt templates

**Architecture**:
- **Three-Tier Discovery**: Builtin → Project → User Global (priority order)
- **Markdown Format**: YAML frontmatter + content
- **Lazy Loading**: Skills cached on first access
- **Deduplication**: Track invoked skills per session
- **System Prompt Integration**: Available skills listed in system prompt

**Skill Lifecycle**:
1. **Discovery**: Scan `.md` files from three directories
2. **Indexing**: Parse frontmatter, build metadata index by namespace:name
3. **Lazy Load**: Read file content only when invoked
4. **Invocation**: Check dedup, load content, inject into LLM context
5. **Caching**: Store LoadedSkill in memory for reuse

**Benefits**:
- Consistent guidance across sessions
- Project-specific expertise (commit conventions, code style)
- Reduced token waste (only loaded when needed)
- Community sharing via skills marketplace

### 4. Context-Aware System Reminders

**Purpose**: Smart error recovery and contextual guidance

**Architecture**:
- **Template Storage**: 20+ reminder templates in reminders.md
- **Error Classification**: Pattern matching on error messages
- **Placeholder Formatting**: Dynamic content injection (e.g., {count}, {todo_list})
- **Five Injection Points**: Post-tool-failure, thinking trace, incomplete todos, plan mode entry, skill deduplication

**Reminder Flow**:
1. **Error Occurs**: Tool execution fails
2. **Classify Error**: Pattern match error message to nudge name
3. **Retrieve Reminder**: get_reminder(nudge_name, **kwargs)
4. **Format Placeholders**: Inject dynamic values
5. **Inject as System Message**: Wrapped in `<system-reminder>` tags

**Common Reminders**:
- `nudge_permission_error`: File permission guidance
- `nudge_edit_mismatch`: String matching tips
- `nudge_file_not_found`: Path validation
- `thinking_trace_reminder`: Inject thinking trace
- `incomplete_todos_nudge`: Warn about unfinished tasks

**Benefits**:
- Faster error recovery (contextual hints)
- Reduced retry loops (specific guidance)
- Better user experience (transparent debugging)
- Learning over time (agent sees patterns)

---

## Component Interaction Flow

### Thinking → Critique → Action Flow

```
User Query
  ↓
[Auto-Compaction if needed]
  ↓
PHASE 1: THINKING
  • Model: model_thinking (fallback to normal)
  • LLM Call: call_thinking_llm(messages) [NO tools]
  • Output: thinking_trace (50-200 words)
  • UI: ui_callback.on_thinking(content)
  ↓
[Interrupt Check]
  ↓
PHASE 2: CRITIQUE (if level == SELF_CRITIQUE)
  • Model: Fallback chain (critique → thinking → normal)
  • Step 1: call_critique_llm(thinking_trace) → critique
  • Step 2: _refine_thinking_with_critique() → improved_trace
  • UI: ui_callback.on_critique(content)
  ↓
[Interrupt Check]
  ↓
PHASE 3: ACTION
  • Model: Normal model + provider
  • Inject: thinking_trace_reminder + trace → user message
  • LLM Call: call_llm(messages, tools) [WITH tool schemas]
  • ReAct Loop: Reason → Act → Execute → Observe → Repeat
  • Termination: text-only response | task_complete | max iterations
  ↓
Session Save & UI Response
```

### Skills Invocation Flow

```
User types /commit (or LLM calls invoke_skill tool)
  ↓
ToolRegistry.invoke_skill(skill_name="commit")
  ↓
SkillLoader.load_skill("commit")
  ↓
Check _skills_cache
  • Hit: Return cached LoadedSkill
  • Miss: Continue to load
  ↓
Read skill file: .opendev/skills/commit.md
  ↓
Strip frontmatter (YAML header)
  ↓
Create LoadedSkill(metadata, content)
  ↓
Cache in _skills_cache
  ↓
Check deduplication: session._invoked_skills
  • Already invoked: Return reminder
  • Not invoked: Continue
  ↓
Track invocation: session._invoked_skills.add("commit")
  ↓
Return {success: true, output: skill_content}
  ↓
LLM receives skill instructions in context
```

### System Reminder Injection Flow

```
Tool Execution Fails
  ↓
tool_result["success"] == false
  ↓
error_count++
  ↓
IF error_count > threshold (e.g., 2):
  ↓
  Classify Error: _get_smart_nudge(error_message)
    • Pattern match error text
    • Return nudge_name (e.g., "nudge_edit_mismatch")
  ↓
  Retrieve Reminder: get_reminder(nudge_name)
    • Parse reminders.md (if not cached)
    • Lookup section by name
    • Format placeholders
    • Return reminder text
  ↓
  Inject as System Message:
    messages.append({
      "role": "system",
      "content": "<system-reminder>\n{reminder_text}\n</system-reminder>"
    })
  ↓
Next LLM call includes contextual guidance
```

### Model Provider Selection Flow

```
Agent Initialization
  ↓
Read AppConfig:
  • model_provider: "anthropic"
  • model: "claude-sonnet-4"
  • model_thinking_provider: "openai"
  • model_thinking: "o1-preview"
  ↓
Lazy HTTP Client Properties (@property decorators):
  ↓
First call to agent.call_llm():
  ↓
  Access @property _http_client
    • Check if initialized: No
    • create_http_client_for_provider("anthropic", "claude-sonnet-4")
      → Route to AnthropicAdapter
      → Cache client
    • Return cached client
  ↓
First call to agent.call_thinking_llm():
  ↓
  Access @property _thinking_http_client
    • Check if thinking_provider != normal_provider: Yes
    • create_http_client_for_provider("openai", "o1-preview")
      → Route to OpenAIResponsesAdapter
      → Cache client
    • Return cached client
  ↓
Subsequent calls reuse cached clients (lazy initialization)
```

---

## Architectural Patterns

### 1. Dependency Injection
All agents receive `AgentDependencies` containing core managers. Tools receive `ToolExecutionContext` during execution. This enables loose coupling and testability.

### 2. Handler Pattern
`ToolRegistry` dispatches tool calls to specialized handlers based on tool name. Each handler encapsulates logic for a category of tools (files, processes, web, MCP, etc.).

### 3. Modular Prompt Composition
System prompts are assembled from individual markdown sections with priorities and conditions. Enables easy addition/removal of prompt guidance without editing monolithic templates.

### 4. Multi-Model Optimization
Different models for different phases (thinking, critique, action, vision, compaction). Lazy HTTP client initialization minimizes overhead. Fallback chains ensure graceful degradation.

### 5. Token-Efficient Tool Discovery
Only tools explicitly discovered (via `search_tools` or first use) have their schemas included in LLM context. Prevents context bloat from hundreds of MCP tools.

### 6. Skills as Reusable Prompts
Skills are markdown files with frontmatter. Lazy loading, deduplication, and three-tier priority enable flexible, efficient prompt reuse.

### 7. Context-Aware Error Recovery
Pattern-matched error classification routes to specific reminder templates. Placeholders enable dynamic content. Five injection points cover common failure scenarios.

### 8. Validated Message Lists
`ValidatedMessageList` enforces tool_use ↔ tool_result pairing invariants at write time, preventing corrupted message sequences from ever being persisted.

### 9. Hierarchical Configuration
Config priority: project `.opendev/settings.json` > user `~/.opendev/settings.json` > env vars > defaults. Enables per-project customization while maintaining global defaults.

---

## File System Structure

```
~/.opendev/
├── settings.json                    # User global config
├── mcp.json                         # Global MCP servers
├── skills/                          # User global skills
│   └── {skill-name}.md
├── cache/
│   └── providers/*.json             # Model/provider cache (24h TTL)
└── projects/{encoded-path}/
    ├── .opendev/
    │   ├── settings.json            # Project-scoped config
    │   ├── mcp.json                 # Project-scoped MCP servers
    │   └── skills/                  # Project-specific skills
    │       └── {skill-name}.md
    ├── memory/
    │   ├── MEMORY.md                # Main memory (max 200 lines, always loaded)
    │   └── {topic}.md               # Topic-specific detailed notes
    ├── sessions/
    │   ├── {session-id}.json        # Full session data
    │   └── .current-session         # Pointer to active session
    ├── sessions-index.json          # Session metadata index
    ├── plans/
    │   └── {session-id}.md          # Plan mode plan files
    └── skills/
        └── {skill-name}.md          # Project-specific skills
```

---

## Critical Data Structures

### AppConfig (Enhanced)
```python
{
  # Normal model
  "model_provider": "anthropic",
  "model": "claude-sonnet-4",

  # Thinking model (optional)
  "model_thinking_provider": "openai",
  "model_thinking": "o1-preview",

  # Critique model (optional)
  "model_critique_provider": "anthropic",
  "model_critique": "claude-opus-4",

  # VLM model (optional)
  "model_vlm_provider": "anthropic",
  "model_vlm": "claude-sonnet-4",

  # Compact model (optional)
  "model_compact_provider": "anthropic",
  "model_compact": "claude-haiku-4",

  # Other config...
  "api_key": str,
  "max_tokens": int,
  "temperature": float
}
```

### ThinkingLevel Enum
```python
class ThinkingLevel(Enum):
    OFF = 0              # No thinking phase
    QUICK = 1            # 50 words
    NORMAL = 2           # 100 words [DEFAULT]
    EXTENDED = 3         # 150 words
    DEEP = 4             # 200 words
    SELF_CRITIQUE = 5    # 100 words + critique phase
```

### LoadedSkill
```python
{
  "metadata": {
    "name": "commit",
    "description": "Git commit best practices",
    "namespace": "default",
    "file_path": Path(".opendev/skills/commit.md")
  },
  "content": str  # Markdown content with frontmatter stripped
}
```

### Reminder Template Format
```markdown
--- nudge_permission_error ---
Permission denied. Check file permissions and working directory.
Use `ls -la` to inspect. Verify you have write access.

--- nudge_edit_mismatch ---
Edit failed: old_string not found. Verify exact string match
including whitespace/indentation. Use Read tool to confirm.

--- thinking_trace_reminder ---
Your thinking trace from previous phase:
<thinking>{trace}</thinking>
Consider this reasoning as you proceed.
```

---

## References

For deep dives into specific components:

- **Agent System**: `swecli/core/agents/` (main_agent.py, planning_agent.py)
- **Model Selection**: `swecli/models/config.py`, `swecli/config/models.py`
- **Thinking/Critique**: `swecli/core/context_engineering/tools/handlers/` (thinking_handler.py, critique_handler.py)
- **Skills System**: `swecli/core/skills.py`
- **System Reminders**: `swecli/core/agents/prompts/reminders.py`, `templates/reminders.md`
- **Tool System**: `swecli/core/context_engineering/tools/` (registry.py, handlers/*, implementations/*)
- **Prompt System**: `swecli/core/agents/prompts/` (composition.py, templates/)
- **UI System**: `swecli/ui_textual/` (TUI), `swecli/web/` + `web-ui/` (Web)
- **Context Engineering**: `swecli/core/context_engineering/` (compaction, memory, MCP, symbol_tools)
- **Persistence**: `swecli/core/context_engineering/history/session_manager.py`
- **Configuration**: `swecli/core/runtime/config.py`

---

**Document Status**: Complete
**Last Updated**: 2026-02-25
**Purpose**: Enhanced system architecture with model providers, thinking/critique, skills, and reminders
