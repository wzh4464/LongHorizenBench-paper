# SWE-CLI Complete System Architecture (Extended Detail)

**Single Unified ASCII Diagram - Full System with All Components**

```
┌════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════┐
│                                                   CLI ENTRY POINT (cli.py)                                                         │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐│
│  │ Parse: --prompt, --continue, --resume, -d, -v  |  Subcommands: config, mcp, run ui                                           ││
│  └────────────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────┘│
│                                                                ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐│
│  │                                        CORE MANAGERS INITIALIZATION                                                              ││
│  │  ConfigManager → SessionManager → ModeManager → ApprovalManager → UndoManager → MCPManager                                      ││
│  │  (hierarchical)   (project-scoped)  (Normal/Plan)  (Manual/Semi/Auto)  (undo stack)  (MCP servers)                             ││
│  └────────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┘
                                                                 ↓
┌════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════┐
│                                              AGENT FACTORY INITIALIZATION                                                          │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  STEP 1: Create Tool Implementations                                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ BashTool | FileOps | WriteTool | EditTool | ReadTool | GlobTool | GrepTool | WebFetchTool | WebSearchTool |                  │ │
│  │ AskUserTool | NotebookEditTool | ScreenshotTool | ThinkingTool | CritiqueTool                                                 │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  STEP 2: Create ToolRegistry(bash_tool, file_ops, write_tool, ...)                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ Internal Initialization:                                                                                                       │ │
│  │  • Create 8 Handler Categories: FileToolHandler, ProcessToolHandler, WebToolHandler, WebSearchHandler,                        │ │
│  │    NotebookEditHandler, AskUserHandler, McpToolHandler, ScreenshotToolHandler                                                 │ │
│  │  • Build _handlers dispatch map: {"write_file": file_handler.write, "run_command": process_handler.run, ...} [30+ tools]     │ │
│  │  • Initialize MCP state: _discovered_mcp_tools = set(), _mcp_manager = mcp_manager                                            │ │
│  │  • Register symbol tools: find_symbol, insert_before_symbol, insert_after_symbol, replace_symbol_body                         │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  STEP 3: Initialize Skills System                                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ skill_dirs = [swecli/skills/builtin/, .opendev/skills/, ~/.opendev/skills/]  (priority order: lowest → highest)              │ │
│  │ skill_loader = SkillLoader(skill_dirs)                                                                                         │ │
│  │ skill_loader.discover_skills() → Scan *.md files → Parse frontmatter (name, description, namespace) → Build _skills_metadata  │ │
│  │ registry.set_skill_loader(skill_loader)                                                                                        │ │
│  │                                                                                                                                 │ │
│  │ Lazy Loading: load_skill(name) → Check cache → Read file → Strip frontmatter → Create LoadedSkill → Cache                    │ │
│  │ Invocation: invoke_skill(name) → Load → Check dedup (session._invoked_skills) → Return content → Inject to LLM context       │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  STEP 4: Create SubAgentManager (if enabled)                                                                                       │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ SubAgentManager(config, tool_registry, ...) → Load subagent definitions (ask_user, code_explorer, planner, web_clone, ...)   │ │
│  │ registry.set_subagent_manager(subagent_manager)                                                                                │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  STEP 5: Create AgentDependencies (DI Container)                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ deps = AgentDependencies(mode_manager, approval_manager, undo_manager, session_manager, working_dir, console, config)         │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  STEP 6: Create Main Agent (MainAgent or PlanningAgent based on mode)                                                           │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ agent = MainAgent(config, tool_registry, deps, ui_callback)                                                                  │ │
│  │ Internal: Store config/registry/deps, Initialize interrupt_token, Set lazy HTTP client properties, Init thinking/critique     │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  STEP 7: System Prompt Composition (PromptComposer)                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ Register sections from templates/system/main/: main-introduction.md (0), main-security-policy.md (10), main-system.md (20),  │ │
│  │ main-doing-tasks.md (30), thinking-*.md (35, if enabled), main-tool-selection.md (40), main-subagent-guide.md (50, if enabled)│ │
│  │ main-git-workflow.md (60), main-tone-style.md (70) → Compose with variable substitution → Final system prompt                 │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  STEP 8: Tool Schema Generation (ToolSchemaBuilder.build())                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ Copy builtin schemas → Filter by allowed_tools → Add Task tool schema (if subagents) → Add discovered MCP schemas → Return   │ │
│  │ Initial ~30 tools: write, edit, read, glob, grep, bash, fetch, search, find_symbol, spawn_subagent, batch_tool, invoke_skill │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────┘
                                                                 ↓
┌════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════┐
│                                              PROVIDER SELECTION & MODEL ROUTING                                                    │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  AppConfig (models/config.py) - Five Model Types:                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ • Normal: model_provider + model (main model for action phase)                                                                │ │
│  │ • Thinking: model_thinking_provider + model_thinking (for thinking phase, fallback to normal)                                 │ │
│  │ • Critique: model_critique_provider + model_critique (for critique phase, fallback chain: critique→thinking→normal)           │ │
│  │ • VLM: model_vlm_provider + model_vlm (for image processing, fallback to normal if has vision capability)                     │ │
│  │ • Compact: model_compact_provider + model_compact (for summarization/compaction, fallback to normal)                          │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  MainAgent HTTP Client Properties (Lazy Initialization):                                                                         │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ @property _http_client: config.model_provider/model → create_http_client_for_provider()                                       │ │
│  │ @property _thinking_http_client: IF thinking_provider != provider: new client ELSE: reuse _http_client                        │ │
│  │ @property _critique_http_client: Fallback chain (critique→thinking→normal) IF different: new client ELSE: reuse               │ │
│  │ @property _vlm_http_client: IF images in messages: get_vlm_model_info() IF vlm_provider != provider: new ELSE: reuse          │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  create_http_client() - Provider Routing (components/api/configuration.py):                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ IF "anthropic": AnthropicAdapter (Messages API) - System extracted, tool_use→tool_calls                                       │ │
│  │ ELIF "openai": OpenAIResponsesAdapter (Responses API not Chat Completions) - System→instructions, reasoning items             │ │
│  │ ELSE: AgentHttpClient (OpenAI-compatible) - Fireworks/custom, 3x retry on 429/503, interrupt polling, threading               │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  ModelRegistry & Provider Cache (config/models.py):                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ Cache: ~/.opendev/cache/providers/{provider_id}.json (TTL: 24h) | Load: cache→blocking fetch→background refresh             │ │
│  │ Model Info: id, name, provider, context_length, capabilities[text/vision/reasoning], supports_temperature, api_type           │ │
│  │ Capability Detection: VLM="vision" in capabilities, Reasoning=o1/o3/o4 or "reasoning", Temperature=supports_temperature flag  │ │
│  │ Fallback Chains: get_critique_model_info()→critique→thinking→normal, get_thinking→thinking→normal, get_vlm→vlm→normal        │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  Parameter Building:                                                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ build_temperature_param(model, temp): IF reasoning_model OR !supports_temperature: {} ELSE: {temperature: temp}               │ │
│  │ build_max_tokens_param(model, tokens): IF uses_max_completion_tokens: {max_completion_tokens: N} ELSE: {max_tokens: N}       │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────┘
                                                                 ↓
┌════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════┐
│                                           THREE-PHASE REACT LOOP (EXTENDED)                                                        │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  User Query → PHASE 0: Auto-Compaction (if token_count > 0.9*max_tokens: summarize older messages, keep recent N intact)          │
│                                                                 ↓                                                                   │
│                                                      [Interrupt Check #1]                                                           │
│                                                                 ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              PHASE 1: THINKING (if enabled, via ThinkingHandler)                                              │ │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐│ │
│  │  │ ThinkingLevel Enum: OFF(0) | QUICK(1,50w) | NORMAL(2,100w)[DEFAULT] | EXTENDED(3,150w) | DEEP(4,200w) |                  ││ │
│  │  │                     SELF_CRITIQUE(5,100w+critique)                                                                        ││ │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘│ │
│  │  Model: model_thinking (fallback: normal) | HTTP Client: _thinking_http_client (lazy init)                                    │ │
│  │  System Prompt: build_system_prompt(thinking_visible=True) + thinking templates from prompts/templates/system/thinking/       │ │
│  │  LLM Call: agent.call_thinking_llm(messages) → NO tools, pure reasoning, word limit by level → Returns thinking_trace         │ │
│  │  UI Display: ui_callback.on_thinking(content) → Dark gray blocks, collapsible in TUI                                          │ │
│  │  Storage: thinking_handler.add_thinking(trace)                                                                                 │ │
│  │  Injection: thinking_trace_reminder + trace → Appended as user message for next phase                                         │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│                                                      [Interrupt Check #2]                                                           │
│                                                                 ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                            PHASE 2: CRITIQUE (if level==SELF_CRITIQUE, via CritiqueHandler)                                   │ │
│  │  Model: Fallback chain (model_critique → model_thinking → model) | HTTP Client: _critique_http_client (lazy init)            │ │
│  │  Step 1: Generate Critique                                                                                                     │ │
│  │    agent.call_critique_llm(thinking_trace) → Critique system prompt from templates/critique.md                                │ │
│  │    Evaluates: logic soundness, completeness, risks → Returns critique string (<100 words)                                     │ │
│  │  Step 2: Refine Thinking                                                                                                       │ │
│  │    _refine_thinking_with_critique() → Append critique as user msg → Call thinking LLM again → Returns improved thinking_trace │ │
│  │  UI Display: ui_callback.on_critique(content) → [Critique] prefix, only if thinking visible                                   │ │
│  │  Storage: critique_handler.add_critique(critique, thinking_ref)                                                                │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│                                                      [Interrupt Check #3]                                                           │
│                                                                 ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                                     PHASE 3: ACTION (Normal ReAct Loop)                                                        │ │
│  │  Model: Normal model + provider | HTTP Client: _http_client (lazy init)                                                       │ │
│  │  System Prompt: build_system_prompt(thinking_visible=False) → Excludes thinking-specific sections                             │ │
│  │  Messages: Base messages + thinking trace (if available) injected via thinking_trace_reminder                                 │ │
│  │  LLM Call: agent.call_llm(messages, tools) → WITH tool schemas, tool_choice="auto", VLM routing if images detected            │ │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐│ │
│  │  │ Tool Execution Loop (max 10 iterations):                                                                                   ││ │
│  │  │  1. LLM returns tool_calls (or text-only response)                                                                         ││ │
│  │  │  2. FOR tool_call IN tool_calls: ToolRegistry.execute_tool(tool_name, arguments, context)                                 ││ │
│  │  │  3. Handler dispatch via _handlers map OR mcp_handler for MCP tools                                                        ││ │
│  │  │  4. Implementation execution → Return result: {success: bool, output: str, ...}                                            ││ │
│  │  │  5. Session.add_message(tool_result) → Auto-save session                                                                   ││ │
│  │  │  6. UICallback.on_tool_result(result) → Display in UI                                                                      ││ │
│  │  │  7. IF error: _get_smart_nudge(error) → Inject system reminder after N failures                                            ││ │
│  │  │  8. Loop: Append results to messages → Call LLM again                                                                      ││ │
│  │  │  Termination: LLM outputs text only (no tools) | task_complete tool called | Max iterations (10) | Error/interrupt        ││ │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘│ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│                                          Session Save & UI Response → END                                                          │
└────────────────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────┘
                                                                 ↓
┌════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════┐
│                                     TOOL EXECUTION FLOW (ToolRegistry.execute_tool())                                              │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  Input: tool_name, arguments, context                                                                                              │
│                                                                 ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 1: MCP Tool Auto-Discovery (Token-Efficient Two-Phase Design)                                                            │ │
│  │  IF tool_name.startswith("mcp__"):  # Format: mcp__{server}__{tool_name}                                                      │ │
│  │    IF tool_name NOT IN _discovered_mcp_tools:                                                                                  │ │
│  │      discover_mcp_tool(tool_name) → Parse server name → Verify MCP server running → Add to _discovered_mcp_tools set         │ │
│  │      # Next schema build (ToolSchemaBuilder.build()) will include this tool → Token savings: 100-1000 per unused tool        │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 2: Handler Lookup                                                                                                         │ │
│  │  IF tool_name in _handlers: handler_func = _handlers[tool_name]  # Dispatch map with 30+ builtin tools                       │ │
│  │  ELIF tool_name.startswith("mcp__"): handler_func = _mcp_handler.execute  # Forward to MCP server                            │ │
│  │  ELSE: raise ValueError("Unknown tool")                                                                                        │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 3: Create ToolExecutionContext                                                                                            │ │
│  │  context = ToolExecutionContext(mode_manager, approval_manager, undo_manager, task_monitor, session_manager, ui_callback,    │ │
│  │                                  is_subagent, interrupt_token)                                                                 │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 4: Execute Handler                                                                                                        │ │
│  │  result = handler_func(arguments, context)                                                                                     │ │
│  │  Handler categories (8 total):                                                                                                 │ │
│  │   • FileToolHandler: write, edit, read, list_files, search, glob, grep                                                        │ │
│  │   • ProcessToolHandler: run_command, list_processes, get_process_output, kill_process                                         │ │
│  │   • WebToolHandler: fetch_url, web_screenshot                                                                                  │ │
│  │   • WebSearchHandler: web_search                                                                                               │ │
│  │   • NotebookEditHandler: notebook_edit                                                                                         │ │
│  │   • AskUserHandler: ask_user                                                                                                   │ │
│  │   • McpToolHandler: mcp__* (all MCP tools)                                                                                     │ │
│  │   • ScreenshotToolHandler: capture_screenshot                                                                                  │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 5: Return Result → {success: bool, output: str, metadata: {...}}                                                         │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  Special Tool: Batch Execution (batch_tool)                                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ Input: {invocations: [{tool: "write_file", input: {...}}, ...], mode: "parallel"|"serial"}                                    │ │
│  │ IF parallel: ThreadPoolExecutor(max_workers=5) → Execute all tools concurrently → Maintain order → Continue on failures       │ │
│  │ IF serial: Sequential loop → execute_tool() for each → Continue on failures                                                    │ │
│  │ Output: {success: true, results: [{tool: "write_file", success: true, ...}, ...]}                                             │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────┘
                                                                 ↓
┌════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════┐
│                                             SYSTEM REMINDERS FLOW                                                                  │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  Reminder Storage: prompts/templates/reminders.md (Section-based markdown)                                                         │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ --- nudge_permission_error ---                                                                                                 │ │
│  │ Permission denied. Check file permissions and working directory. Use `ls -la` to inspect.                                      │ │
│  │                                                                                                                                 │ │
│  │ --- nudge_edit_mismatch ---                                                                                                    │ │
│  │ Edit failed: old_string not found. Verify exact string match including whitespace/indentation.                                 │ │
│  │                                                                                                                                 │ │
│  │ --- incomplete_todos_nudge ---                                                                                                 │ │
│  │ You have {count} incomplete todos: {todo_list}. Please address before proceeding.                                             │ │
│  │                                                                                                                                 │ │
│  │ --- thinking_trace_reminder ---                                                                                                │ │
│  │ Your thinking trace from previous phase: <thinking>{trace}</thinking>                                                          │ │
│  │                                                                                                                                 │ │
│  │ --- ... (20+ reminders: failed_tool_nudge, nudge_rate_limit, nudge_timeout, nudge_syntax_error, etc.) ---                     │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  get_reminder(reminder_name, **kwargs) - Template Retrieval (prompts/reminders.py):                                               │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ Parse reminders.md on first call → Build sections dict → Lookup section → Format placeholders (.format(**kwargs)) → Return    │ │
│  │ Fallback: Check individual .txt files if not in sections                                                                       │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  Error Classification: _get_smart_nudge(error_message) → nudge_name (main_agent.py)                                             │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ Pattern Matching: "Permission denied"→nudge_permission_error | "not found"→nudge_file_not_found | "SyntaxError"→              │ │
│  │ nudge_syntax_error | "rate limit"/"429"→nudge_rate_limit | "timeout"→nudge_timeout | "old_string"→nudge_edit_mismatch |       │ │
│  │ ELSE→failed_tool_nudge                                                                                                         │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                 ↓                                                                   │
│  Injection Points (react_executor.py, query_processor.py):                                                                         │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ 1. Post-Tool-Failure: IF tool_result[success]==false AND error_count>2: reminder=get_reminder(nudge_name) → Append as system │ │
│  │    message: <system-reminder>{reminder}</system-reminder>                                                                      │ │
│  │ 2. Pre-Action-Phase (incomplete todos): IF todos_incomplete AND task_completed: reminder=get_reminder("incomplete_todos_nudge",│ │
│  │    count=len(incomplete), todo_list=format_todos(incomplete)) → Append as system message                                      │ │
│  │ 3. Pre-Action-Phase (thinking trace): IF thinking_trace: reminder=get_reminder("thinking_trace_reminder", trace=thinking_trace)│ │
│  │    → Append as user message                                                                                                    │ │
│  │ 4. Plan Mode Entry: IF mode_switch_to_plan: reminder=get_reminder("plan_mode_nudge") → Append as system message               │ │
│  │ 5. Skill System (dedup): IF skill already invoked: reminder=get_reminder("skill_already_loaded") → Return as tool result      │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════┐
│                                              INTERRUPT SYSTEM INTEGRATION                                                          │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  InterruptToken (core/runtime/interrupt_token.py): Shared state for ESC key detection                                             │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ State: _is_interrupted: threading.Event | Methods: check()→bool, set()→trigger interrupt, reset()→clear interrupt            │ │
│  │                                                                                                                                 │ │
│  │ Integration Points:                                                                                                             │ │
│  │  • Phase Transitions: IF interrupt_token.check(): raise KeyboardInterrupt (between thinking/critique/action phases)           │ │
│  │  • HTTP Client Polling: During LLM streaming, poll interrupt_token every 0.1s → Abort request if interrupted                  │ │
│  │  • Tool Execution: Long-running tools check context.task_monitor.check_interrupt()                                            │ │
│  │  • UI Event Handlers: TUI key binding on ESC → interrupt_token.set() | Web WebSocket abort command → interrupt_token.set()   │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════┐
│                                         KEY DATA FLOWS & CROSS-COMPONENT INTERACTIONS                                              │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  FLOW A: Tool Call Execution Path                                                                                                  │
│    User Message → LLM Response with tool_calls → ReactExecutor.run_iteration() FOR tool_call → ToolRegistry.execute_tool()        │
│    → Handler.execute() → Tool Implementation.run() → Session.add_message(tool_result) → UICallback.on_tool_result()               │
│                                                                                                                                     │
│  FLOW B: MCP Tool Discovery Path                                                                                                   │
│    LLM calls mcp__github__create_issue → ToolRegistry.execute_tool("mcp__github__create_issue") → IF NOT IN _discovered_mcp_tools │
│    → discover_mcp_tool() → Parse server name → Verify MCP server running → Add to _discovered_mcp_tools → McpToolHandler.execute()│
│    → Next LLM call → ToolSchemaBuilder.build() → Fetch _discovered_mcp_tools → Get schema from MCPManager → Include in tool list  │
│                                                                                                                                     │
│  FLOW C: Thinking → Critique → Action                                                                                              │
│    User Query → PHASE 1 call_thinking_llm() → thinking_trace → thinking_handler.add_thinking() → IF SELF_CRITIQUE: PHASE 2        │
│    call_critique_llm(thinking_trace) → critique → _refine_thinking_with_critique() → refined_trace →                              │
│    critique_handler.add_critique() → Inject thinking_trace_reminder → PHASE 3 call_llm(messages+trace, tools) → Normal ReAct     │
│                                                                                                                                     │
│  FLOW D: Skills Invocation                                                                                                         │
│    User types /commit → UI sends Skill tool call {skill_name: "commit"} → ToolRegistry.invoke_skill() →                           │
│    skill_loader.load_skill(name) → Check cache → Read *.md file → Strip frontmatter → Create LoadedSkill → Cache →               │
│    Check dedup (session._invoked_skills) → Track invocation → Return {success: true, output: skill_content} →                     │
│    LLM receives skill instructions in context                                                                                      │
│                                                                                                                                     │
│  FLOW E: System Reminder Injection on Error                                                                                        │
│    Tool execution fails → tool_result[success]==false → error_count++ → IF error_count>2: _get_smart_nudge(error) →              │
│    nudge_name (e.g., "nudge_edit_mismatch") → get_reminder(nudge_name) → reminder_text →                                          │
│    messages.append({role: "system", content: "<system-reminder>{reminder_text}</system-reminder>"}) → Next LLM call includes nudge│
│                                                                                                                                     │
│  FLOW F: Lazy HTTP Client Initialization                                                                                           │
│    First LLM call → agent.call_llm() → Access @property _http_client → IF not initialized: create_http_client(provider, model)   │
│    → Route to AnthropicAdapter/OpenAIResponsesAdapter/AgentHttpClient based on provider → Cache client → Reuse for subsequent     │
│    calls | Thinking/Critique clients initialized separately only if different provider                                            │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════┐
│                                           COMPONENT INTERACTION MATRIX                                                             │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                      │ Agent │ ToolRegistry │ SkillLoader │ MCPManager │ SystemPrompt │ UICallback │ SessionManager │ RemindersSystem│
│  ────────────────────┼───────┼──────────────┼─────────────┼────────────┼──────────────┼────────────┼────────────────┼────────────────┤
│  Agent               │   -   │      ✓       │      ✓      │     -      │      ✓       │     ✓      │       ✓        │       ✓        │
│  ToolRegistry        │   ✓   │      -       │      ✓      │     ✓      │      -       │     ✓      │       ✓        │       -        │
│  SkillLoader         │   ✓   │      ✓       │      -      │     -      │      ✓       │     -      │       -        │       -        │
│  MCPManager          │   -   │      ✓       │      -      │     -      │      -       │     -      │       -        │       -        │
│  SystemPrompt        │   ✓   │      ✓       │      ✓      │     -      │      -       │     -      │       -        │       ✓        │
│  UICallback          │   ✓   │      ✓       │      -      │     -      │      -       │     -      │       -        │       -        │
│  SessionManager      │   ✓   │      ✓       │      -      │     -      │      -       │     -      │       -        │       -        │
│  RemindersSystem     │   ✓   │      ✓       │      -      │     -      │      ✓       │     -      │       -        │       -        │
│                                                                                                                                         │
│  Legend: ✓ = Component A calls/uses Component B  |  - = No direct interaction                                                        │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**End of Single Unified System Architecture Diagram**
