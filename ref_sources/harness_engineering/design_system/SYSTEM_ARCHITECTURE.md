# SWE-CLI System Architecture

**Complete ASCII System Diagram**

This document provides a comprehensive, single-view ASCII diagram of the entire SWE-CLI system architecture. It shows all layers, components, data flows, and decision points in one unified visualization.

---

## How to Read This Diagram

- **Top-to-bottom flow**: System layers from entry point → UI → agent → tools → context → persistence
- **Left-to-right alternatives**: Parallel paths (TUI vs Web, Normal vs Plan mode)
- **Boxes**: Components, handlers, or logical groupings
- **Arrows**: Data flow and control flow
- **Annotations**: Side notes explaining data structures, decision logic, or patterns
- **Numbered flows**: Key data flows traced through the system (see Flow Descriptions section)

---

## Complete System Architecture Diagram

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
│  │  • Bare positional arg    (interactive TUI with initial message)       │  │
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
│                              AGENT LAYER                                     │   Data: AgentDependencies
│  ════════════════════════════════════════════════════════════════════       │   ═════════════════════
│  swecli/core/agents/                                                         │   (DI Container)
│                                                                               │   ┌───────────────────┐
│  ┌──────────────────────────────────────────────────────────────────────┐   │   │ AgentDependencies │
│  │ AgentDependencies (models/agent_deps.py)                             │   │   │ ───────────────── │
│  │  Dependency Injection Container                                      │   │   │ • mode_manager    │
│  │  ───────────────────────────────                                     │   │   │ • approval_manager│
│  │  • mode_manager       (ModeManager - Normal/Plan mode)               │   │   │ • undo_manager    │
│  │  • approval_manager   (ApprovalManager - operation approval)         │   │   │ • session_manager │
│  │  • undo_manager       (UndoManager - history tracking)               │   │   │ • working_dir     │
│  │  • session_manager    (SessionManager - conversation persistence)    │   │   │ • console         │
│  │  • working_dir        (Path - current working directory)             │   │   │ • config          │
│  │  • console            (Rich Console - output)                        │   │   └───────────────────┘
│  │  • config             (AppConfig - runtime configuration)            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
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
│  │ ReAct Loop (agent.run_sync / agent.run)                             │   │
│  │  ════════════════════════════════════════                           │   │
│  │  1. Reason      (LLM analyzes situation)                            │   │
│  │  2. Act         (LLM selects tools to call)                         │   │   Flow ①: User message
│  │  3. Execute     (ToolRegistry.execute_tool)                         │   │   Flow ②: Tool execution
│  │  4. Observe     (LLM sees tool results)                             │   │   Flow ③: Session save
│  │  5. Loop        (repeat until completion or max 10 turns)           │   │
│  │                                                                      │   │
│  │  Loop Termination:                                                  │   │
│  │   • LLM outputs final response (no tool calls)                      │   │
│  │   • task_complete tool called                                       │   │
│  │   • Max iterations reached (10)                                     │   │
│  │   • Error or interrupt                                              │   │
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
│  HANDLER 5: NotebookEditHandler (handlers/notebook_edit_handler.py)          │
│  ═══════════════════════════════════════════════════════════════════         │
│  Handles Jupyter notebook cell editing                                       │
│                                                                               │
│  Tools:                                                                       │
│   • notebook_edit  → NotebookEditTool.edit_cell(path, cell_id, content)      │
│                                                                               │
│  Implementations:                                                             │
│   • implementations/notebook_edit_tool.py (NotebookEditTool)                 │
├───────────────────────────────────────────────────────────────────────────────┤
│  HANDLER 6: AskUserHandler (handlers/ask_user_handler.py)                    │
│  ══════════════════════════════════════════════════════                      │
│  Handles user interaction prompts                                            │
│                                                                               │
│  Tools:                                                                       │
│   • ask_user  → AskUserTool.ask_questions(questions, metadata)               │
│                                                                               │
│  UI Integration:                                                              │
│   • TUI: AskUserPromptController (blocking dialog)                           │
│   • Web: WebAskUserManager (polling state dict)                              │
│                                                                               │
│  Implementations:                                                             │
│   • implementations/ask_user_tool.py (AskUserTool)                           │
├───────────────────────────────────────────────────────────────────────────────┤
│  HANDLER 7: MCPHandler (mcp/handler.py)                                      │
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
│  HANDLER 8: ScreenshotToolHandler (handlers/screenshot_handler.py)           │
│  ═══════════════════════════════════════════════════════════════════         │
│  Handles screenshot capture and analysis                                     │
│                                                                               │
│  Tools:                                                                       │
│   • capture_screenshot      → ScreenshotHandler.capture()                    │
│   • capture_web_screenshot  → WebScreenshotTool.capture(url, viewport)       │
│   • analyze_image           → VLMTool.analyze_image(path, prompt)            │
│                                                                               │
│  Implementations:                                                             │
│   • implementations/web_screenshot_tool.py (WebScreenshotTool)               │
│   • implementations/vlm_tool.py (VLMTool)                                    │
├───────────────────────────────────────────────────────────────────────────────┤
│  HANDLER 9: TodoHandler (handlers/todo_handler.py)                           │
│  ══════════════════════════════════════════════════                          │
│  Handles task/todo management                                                │
│                                                                               │
│  Tools:                                                                       │
│   • write_todos   → TodoHandler.write_todos(todos)                           │
│   • update_todo   → TodoHandler.update_todo(id, status, title)               │
│   • complete_todo → TodoHandler.complete_todo(id)                            │
│   • list_todos    → TodoHandler.list_todos()                                 │
│                                                                               │
│  Auto-creation from Plans:                                                   │
│   • Parses plan content on exit_plan_mode                                    │
│   • Creates todos from implementation steps                                  │
├───────────────────────────────────────────────────────────────────────────────┤
│  HANDLER 10: ThinkingHandler (handlers/thinking_handler.py)                  │
│  ═══════════════════════════════════════════════════════                     │
│  Handles thinking mode control                                               │
│                                                                               │
│  Tools:                                                                       │
│   • thinking_mode  → Toggle extended thinking/reasoning                      │
│                                                                               │
│  Note: Integrated with LLM providers that support extended thinking          │
├───────────────────────────────────────────────────────────────────────────────┤
│  HANDLER 11: SearchToolsHandler (handlers/search_tools_handler.py)           │
│  ══════════════════════════════════════════════════════════════════          │
│  Handles MCP tool discovery                                                  │
│                                                                               │
│  Tools:                                                                       │
│   • search_tools  → Search and discover MCP tools by keyword                 │
│                                                                               │
│  Token-Efficient Pattern:                                                    │
│   1. Agent searches for tools by keyword                                     │
│   2. Handler returns matching tool names                                     │
│   3. ToolRegistry marks tools as "discovered"                                │
│   4. Only discovered tools included in future LLM context                    │
├───────────────────────────────────────────────────────────────────────────────┤
│  HANDLER 12: BatchToolHandler (handlers/batch_handler.py)                    │
│  ═══════════════════════════════════════════════════════                     │
│  Handles parallel/serial multi-tool execution                                │
│                                                                               │
│  Tools:                                                                       │
│   • batch_tool  → Execute multiple tools in parallel or serial order         │
│                                                                               │
│  Execution Modes:                                                             │
│   • parallel: Execute all tools concurrently (default)                       │
│   • serial:   Execute tools sequentially                                     │
│                                                                               │
│  Use Cases:                                                                   │
│   • Read multiple files in parallel                                          │
│   • Execute dependent operations in order                                    │
│   • Batch file operations                                                    │
├───────────────────────────────────────────────────────────────────────────────┤
│  ADDITIONAL TOOL IMPLEMENTATIONS                                             │
│  ════════════════════════════════════                                        │
│                                                                               │
│  Symbol Tools (LSP-based code navigation):                                   │
│   • find_symbol               → AST-based symbol search                      │
│   • find_referencing_symbols  → Find all references                          │
│   • insert_before_symbol      → Insert code before symbol                    │
│   • insert_after_symbol       → Insert code after symbol                     │
│   • replace_symbol_body       → Replace function/class body                  │
│   • rename_symbol             → Refactor symbol rename                       │
│                                                                               │
│  Plan Mode Tools:                                                             │
│   • enter_plan_mode  → Switch to planning mode                               │
│   • exit_plan_mode   → Present plan for approval                             │
│   • create_plan      → Write plan content to file                            │
│   • edit_plan        → Edit plan with search-replace                         │
│                                                                               │
│  Task Control:                                                                │
│   • task_complete    → Explicitly signal task completion                     │
│                                                                               │
│  Skills System:                                                               │
│   • invoke_skill     → Load skill content into context                       │
│                                                                               │
│  PDF Extraction:                                                              │
│   • read_pdf         → Extract text from PDF files                           │
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
│  │  Flow:                                                               │   │   Flow ④: Compaction
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

## Data Flow Descriptions

### Flow ①: User Message Flow

```
User Input
  ↓
UI Layer (TUI or Web)
  ↓
Session.add_message(user_message)
  ↓
Agent.run(prompt, deps, message_history)
  ↓
ReAct Loop:
  1. LLM reasoning (analyze situation)
  2. LLM tool selection (decide actions)
  3. ToolRegistry.execute_tool(name, args, context)
     ↓
     Handler dispatch → Implementation execution
     ↓
     Return result
  4. Session.add_message(tool_result)
  5. LLM observes results
  6. Repeat or complete
  ↓
Session.add_message(assistant_message)
  ↓
SessionManager.save_session()
  ↓
Display response to user
```

### Flow ②: Tool Execution Flow

```
Agent selects tool (from LLM response)
  ↓
ToolRegistry.execute_tool(name, arguments, context)
  ↓
Check if approval needed:
  • Auto mode → Skip approval
  • Semi-Auto mode → Check patterns (write/edit/bash → ask, read → skip)
  • Manual mode → Always ask
  ↓
If approval needed:
  TUI Path:
    • UICallback.request_approval()
    • ApprovalController.show_modal()
    • Block until user clicks
    • Return decision

  Web Path:
    • WebApprovalManager.request_approval()
    • Broadcast via WebSocket (approval_required event)
    • Poll state._pending_approvals dict
    • User responds via POST /api/approvals/{approval_id}
    • Resolve and return decision
  ↓
Find handler for tool_name:
  • file tools → FileToolHandler
  • process tools → ProcessToolHandler
  • web tools → WebToolHandler
  • mcp__ prefix → MCPHandler
  • etc.
  ↓
Handler.execute(arguments, context)
  ↓
Implementation execution (e.g., BashTool.execute, WriteTool.write)
  ↓
Return result dict:
  {
    "success": bool,
    "output": str,
    "error": Optional[str]
  }
  ↓
Add to session messages (as tool_result)
```

### Flow ③: Session Save Flow

```
Message added to session
  ↓
Session.add_message(message)
  ↓
ValidatedMessageList enforces invariants:
  • Every tool_use must have matching tool_result
  • Every tool_result must reference valid tool_use
  ↓
Session.updated_at = datetime.now()
  ↓
Check auto_save_interval:
  • If message_count % interval == 0 → Save
  ↓
SessionManager.save_session()
  ↓
Atomic write:
  1. Write to temp file (.tmp)
  2. Rename to final file (atomic)
  ↓
Update sessions-index.json:
  • Update metadata (message_count, total_tokens, updated_at)
  • Update title (from TopicDetector)
  ↓
Persist to:
  ~/.opendev/projects/{encoded-path}/sessions/{session-id}.json
```

### Flow ④: Context Compaction Flow

```
Before LLM call
  ↓
Check token count:
  total_tokens = sum(msg.token_estimate() for msg in session.messages)
  ↓
If total_tokens > 0.9 * max_context_tokens:
  ↓
  Compactor.compact(session)
    ↓
    1. Identify older messages (keep last N interactions)
    2. Summarize older messages with LLM
    3. Replace old messages with summary
    4. Keep recent messages intact
    ↓
  Update session.messages with compacted history
  ↓
  SessionManager.save_session()
  ↓
Proceed with LLM call using compacted context
```

### Flow ⑤: Approval Flow Comparison

**TUI Approval (Blocking):**
```
Tool requires approval
  ↓
UICallback.request_approval(tool_name, args)
  ↓
ApprovalController.show_modal(tool_name, args)
  ↓
Display modal dialog with:
  • Tool name and arguments
  • Approve / Deny buttons
  ↓
Block thread (wait for user interaction)
  ↓
User clicks button
  ↓
Modal returns decision immediately
  ↓
Continue tool execution
```

**Web Approval (Polling):**
```
Tool requires approval
  ↓
WebApprovalManager.request_approval(tool_name, args)
  ↓
Generate approval_id
  ↓
Add to state._pending_approvals[approval_id] = {
  "tool_name": tool_name,
  "arguments": args,
  "resolved": False
}
  ↓
Broadcast via WebSocket:
  ws.send_json({
    "type": "approval_required",
    "approval_id": approval_id,
    "tool_name": tool_name,
    "arguments": args
  })
  ↓
Frontend receives event → Show ApprovalDialog
  ↓
Poll state._pending_approvals every 100ms:
  while not state._pending_approvals[approval_id]["resolved"]:
    await asyncio.sleep(0.1)
  ↓
User clicks Approve/Deny in frontend
  ↓
Frontend sends POST /api/approvals/{approval_id}
  {
    "decision": "approved" | "denied"
  }
  ↓
Backend updates state._pending_approvals[approval_id]:
  {
    "resolved": True,
    "decision": decision
  }
  ↓
Polling loop exits
  ↓
Return decision to tool execution
```

---

## Key Decision Points

### 1. UI Mode Selection (CLI Entry Point)

```
Command line arguments:
  • opendev              → TUI (default)
  • opendev run ui       → Web UI
  • opendev -p "prompt"  → Non-interactive (no UI)
```

### 2. Agent Mode Selection (ModeManager)

```
ModeManager.current_mode:
  • "normal" → MainAgent (full tools, implementation mode)
  • "plan"   → PlanningAgent (read-only tools, planning mode)

Switching:
  • TUI: Shift+Tab or /mode command
  • Web: StatusBar mode toggle
  • Tools: enter_plan_mode, exit_plan_mode
```

### 3. Approval Decision (ApprovalManager)

```
ApprovalManager.autonomy_level:
  • "Auto"      → Skip all approvals (auto-approve everything)
  • "Semi-Auto" → Pattern-based:
      - write_file, edit_file, run_command → Ask user
      - read_file, list_files, search → Auto-approve
  • "Manual"    → Ask for every operation

Dangerous operations always ask (unless --dangerously-skip-permissions):
  • File deletions
  • Git destructive commands (reset --hard, push --force)
  • System modifications
```

### 4. Tool Routing (ToolRegistry)

```
Tool name → Handler mapping:
  • read_file, write_file, edit_file, list_files, search
      → FileToolHandler

  • run_command, list_processes, get_process_output, kill_process
      → ProcessToolHandler

  • spawn_subagent, get_subagent_output
      → ProcessToolHandler (via SubAgentManager)

  • fetch_url
      → WebToolHandler

  • web_search
      → WebSearchHandler

  • notebook_edit
      → NotebookEditHandler

  • ask_user
      → AskUserHandler

  • mcp__*
      → MCPHandler

  • capture_screenshot, capture_web_screenshot, analyze_image
      → ScreenshotToolHandler

  • write_todos, update_todo, complete_todo, list_todos
      → TodoHandler

  • thinking_mode
      → ThinkingHandler

  • search_tools
      → SearchToolsHandler

  • batch_tool
      → BatchToolHandler

  • Symbol tools (find_symbol, etc.)
      → Direct handlers in registry

  • Plan tools (enter_plan_mode, exit_plan_mode, create_plan, edit_plan)
      → Direct tool implementations

  • invoke_skill
      → Skills system handler

  • read_pdf
      → PDFTool
```

### 5. Context Compaction Trigger

```
Before each LLM call:
  total_tokens = session.total_tokens()
  max_tokens = config.max_context_tokens

  if total_tokens > 0.9 * max_tokens:
    Compactor.compact(session)
    # Summarize older messages, keep recent ones
```

### 6. MCP Tool Discovery

```
Token-efficient pattern:

Option A - Explicit discovery:
  1. Agent calls search_tools(keyword="github")
  2. Returns matching tools: ["mcp__github__create_issue", ...]
  3. ToolRegistry marks tools as "discovered"
  4. Only discovered tools included in future LLM context

Option B - Auto-discovery on first use:
  1. Agent calls mcp__github__create_issue directly
  2. ToolRegistry auto-discovers and logs info
  3. Tool schema included in next LLM call
```

---

## Component Details

### Entry Point Layer
- **cli.py**: Argument parsing, config loading, manager initialization, UI selection
- **setup/wizard.py**: First-run setup wizard for API keys and preferences

### UI Layer Components

**TUI (Textual):**
- **ChatApp**: Main application container (Textual app)
- **ChatWidget**: Message display with markdown rendering
- **InputWidget**: User input with autocomplete
- **StatusBar**: Mode, autonomy level, git branch, model info
- **Sidebar**: Session list and navigation
- **UICallback**: Agent-to-UI bridge (tool calls, thinking, approvals)
- **Controllers**: ApprovalController, AskUserPromptController, PlanApprovalController

**Web UI:**
- **Backend (FastAPI)**: server.py, websocket.py, state.py
- **Frontend (React)**: ChatView, Sidebar, StatusBar, dialogs
- **Store (Zustand)**: Central state management in chat.ts
- **WebSocket Events**: Real-time updates for tool calls, approvals, ask-user prompts

### Agent Layer Components
- **MainAgent**: Full tool access, implementation mode
- **PlanningAgent**: Read-only tools, planning mode
- **SubAgentManager**: Spawns and manages specialized subagents
- **AgentDependencies**: DI container with all core managers

### Tool Layer Components
- **ToolRegistry**: Central dispatcher, MCP integration, skill loading
- **Handlers**: 12+ specialized handlers for different tool categories
- **Implementations**: Concrete tool implementations (BashTool, WriteTool, etc.)

### Context Engineering Components
- **PromptComposer**: Modular prompt assembly with sections
- **Compactor**: Automatic context compression
- **Memory**: Auto-memory files for persistent knowledge
- **MCPManager**: MCP server lifecycle and tool discovery
- **Symbol Tools**: AST-based code navigation

### Persistence Layer Components
- **SessionManager**: CRUD operations, auto-save, indexing
- **ConfigManager**: Hierarchical config loading
- **Provider Cache**: Model/provider info caching (24h TTL)
- **Data Models**: Session, ChatMessage, ToolCall, ValidatedMessageList

---

## Critical Data Structures

### ChatSession
```python
{
  "id": str,                        # 8-character hex
  "created_at": datetime,
  "updated_at": datetime,
  "messages": ValidatedMessageList, # Enforces tool_use ↔ tool_result pairing
  "context_files": list[str],
  "working_directory": str,
  "metadata": dict,                 # Title, summary, tags
  "playbook": dict,                 # ACE Playbook (learned strategies)
  "file_changes": list[FileChange]
}
```

### ChatMessage
```python
{
  "role": "user" | "assistant" | "system" | "tool",
  "content": str,
  "tool_calls": list[ToolCall],
  "metadata": dict,
  "thinking_trace": Optional[str],
  "reasoning_content": Optional[str],
  "token_usage": Optional[dict]
}
```

### ToolCall
```python
{
  "id": str,
  "name": str,
  "parameters": dict,
  "result": Optional[Any],
  "result_summary": Optional[str],  # Concise 1-2 line summary
  "error": Optional[str]
}
```

### AgentDependencies
```python
{
  "mode_manager": ModeManager,
  "approval_manager": ApprovalManager,
  "undo_manager": UndoManager,
  "session_manager": SessionManager,
  "working_dir": Path,
  "console": Console,
  "config": AppConfig
}
```

### ToolExecutionContext
```python
{
  "mode_manager": ModeManager,
  "approval_manager": ApprovalManager,
  "undo_manager": UndoManager,
  "task_monitor": TaskMonitor,
  "session_manager": SessionManager,
  "ui_callback": UICallback,
  "is_subagent": bool
}
```

---

## Architectural Patterns

### 1. Dependency Injection
All agents receive `AgentDependencies` containing core managers. Tools receive `ToolExecutionContext` during execution. This enables loose coupling and testability.

### 2. Handler Pattern
`ToolRegistry` dispatches tool calls to specialized handlers based on tool name. Each handler encapsulates logic for a category of tools (files, processes, web, MCP, etc.).

### 3. Modular Prompt Composition
System prompts are assembled from individual markdown sections with priorities and conditions. Enables easy addition/removal of prompt guidance without editing monolithic templates.

### 4. Event-Driven UI Communication
- **TUI**: Blocking calls with immediate responses (modal dialogs)
- **Web**: Event broadcasting via WebSocket + polling state dicts for async resolution

### 5. Token-Efficient Tool Discovery
Only tools explicitly discovered (via `search_tools` or first use) have their schemas included in LLM context. Prevents context bloat from hundreds of MCP tools.

### 6. Automatic Context Compaction
When token count exceeds 90% of max context, older messages are automatically summarized to preserve recent context while staying under limits.

### 7. Validated Message Lists
`ValidatedMessageList` enforces tool_use ↔ tool_result pairing invariants at write time, preventing corrupted message sequences from ever being persisted.

### 8. Hierarchical Configuration
Config priority: project `.opendev/settings.json` > user `~/.opendev/settings.json` > env vars > defaults. Enables per-project customization while maintaining global defaults.

---

## File System Structure

```
~/.opendev/
├── settings.json                    # User global config
├── mcp.json                         # Global MCP servers
├── cache/
│   └── providers/*.json             # Model/provider cache (24h TTL)
└── projects/{encoded-path}/
    ├── .opendev/
    │   ├── settings.json            # Project-scoped config
    │   └── mcp.json                 # Project-scoped MCP servers
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

## References

For deep dives into specific components:

- **Agent System**: `swecli/core/agents/` (main_agent.py, planning_agent.py)
- **Tool System**: `swecli/core/context_engineering/tools/` (registry.py, handlers/*, implementations/*)
- **Prompt System**: `swecli/core/agents/prompts/` (composition.py, templates/)
- **UI System**: `swecli/ui_textual/` (TUI), `swecli/web/` + `web-ui/` (Web)
- **Context Engineering**: `swecli/core/context_engineering/` (compaction, memory, MCP, symbol_tools)
- **Persistence**: `swecli/core/context_engineering/history/session_manager.py`
- **Models**: `swecli/models/` (session.py, message.py, agent_deps.py)
- **Configuration**: `swecli/core/runtime/config.py`
- **Entry Point**: `swecli/cli.py`

---

## Legend

```
┌─────┐
│ Box │  Component or logical grouping
└─────┘

  ↓      Data flow or control flow (downward)
  →      Data flow or control flow (horizontal)

═════    Section separator or emphasis

Flow ①   Numbered flow reference (see Flow Descriptions)

// Note: Side annotation or clarification
```

---

**Document Status**: Complete
**Last Updated**: 2026-02-24
**Purpose**: Single comprehensive view of SWE-CLI system architecture for developers and maintainers
