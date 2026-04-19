# SWE-CLI Design System Documentation

**Version**: 1.0
**Last Updated**: 2026-02-24
**Target Audience**: Developers, Contributors, System Architects

---

## Overview

This documentation provides a comprehensive guide to the SWE-CLI system architecture, design patterns, and execution flows. It serves as the primary technical reference for understanding, maintaining, and extending the system.

**SWE-CLI** is a sophisticated AI-powered software engineering CLI that combines:
- A dual-agent ReAct system (MainAgent + PlanningAgent)
- Modular tool registry with MCP integration
- Dual UI support (Textual TUI + React Web UI)
- Advanced context engineering and prompt composition
- Persistent session management with auto-compaction

---

## Documentation Structure

### 📚 Reading Paths

**For New Contributors** (recommended order):
1. [Architecture Overview](#01-architecture-overview) - Start here
2. [Agent System](#02-agent-system) - Understand the core reasoning engine
3. [Execution Flows](#05-execution-flows) - See how it all works together
4. [Extension Points](#09-extension-points) - Learn how to contribute

**For Feature Developers**:
- [Tool System](#03-tool-system) - Adding new capabilities
- [UI Architectures](#06-ui-architectures) - UI integration
- [Design Patterns](#08-design-patterns) - Follow established patterns

**For System Architects**:
- [System Architecture Diagram](#10-system-architecture-diagram) - High-level abstracted view
- [Architecture Overview](#01-architecture-overview) - System layers
- [Guardrails Architecture](#guardrails_architecturemd) - Safety & approval system
- [Data Structures](#07-data-structures) - Core models
- [Prompt Composition](#04-prompt-composition) - Prompt engineering

---

## File Index

### [01_architecture_overview.md](./01_architecture_overview.md)
**High-level system architecture and component relationships**

- System layers (Entry → UI → Agent → Tools → Context Engineering → Persistence)
- Component diagram with dependencies
- Technology stack per layer
- Data flow overview
- Component responsibility matrix

**Key Diagrams**: Component architecture, data flow, layer dependencies

---

### [02_agent_system.md](./02_agent_system.md)
**Deep dive into the agent architecture**

- MainAgent (main agent) vs PlanningAgent (read-only)
- ReAct loop implementation
- Subagent system architecture
- LLM integration (HTTP clients, provider routing, VLM support)
- Auto-context compaction
- Interrupt token system
- Graceful completion patterns

**Key Diagrams**: ReAct loop flowchart, agent hierarchy, provider routing, compaction flow

---

### [03_tool_system.md](./03_tool_system.md)
**Tool registry, handlers, and execution**

- ToolRegistry architecture
- Tool handler pattern
- Tool categories (File, Process, Web, MCP, Thinking, etc.)
- Tool execution context
- Approval integration
- MCP (Model Context Protocol) integration
- Batch tool execution

**Key Diagrams**: Tool execution sequence, handler dispatch flow, approval integration

---

### [04_prompt_composition.md](./04_prompt_composition.md)
**Modular prompt system**

- PromptComposer architecture
- Template section system
- Priority and condition evaluation
- Section registration and ordering
- Dynamic prompt assembly
- Variable substitution
- Template rendering

**Key Diagrams**: Prompt composition flow, section priority ordering, template rendering

---

### [05_execution_flows.md](./05_execution_flows.md)
**Key execution flows through the system**

- **Flow 1**: User message → Agent processing → Tool execution → Response
- **Flow 2**: Tool execution → Registry lookup → Handler dispatch → Result
- **Flow 3**: Session persistence (save/restore)
- **Flow 4**: Mode switching (Normal ↔ Plan)
- **Flow 5**: Web UI WebSocket flow (threaded agent + async broadcast)
- **Flow 6**: TUI real-time display flow (blocking approval)

**Key Diagrams**: Sequence diagrams for each flow, swimlane diagrams

---

### [06_ui_architectures.md](./06_ui_architectures.md)
**Textual TUI and Web UI architectures**

- **Textual TUI**: Widget hierarchy, event handling, real-time updates, blocking approval
- **Web UI**: FastAPI backend, React/Vite/Zustand frontend, WebSocket communication
- Approval flow differences (blocking vs polling)
- Ask-user flow differences (modal vs survey dialog)
- Message streaming
- State synchronization
- ThreadPoolExecutor + asyncio.run_coroutine_threadsafe pattern

**Key Diagrams**: TUI component hierarchy, Web UI architecture, WebSocket message flow

---

### [07_data_structures.md](./07_data_structures.md)
**Core data models and relationships**

- Session model (ChatSession)
- ChatMessage model (user, assistant, tool_use, tool_result)
- ValidatedMessageList (message pair invariants)
- ToolExecutionContext
- AgentDependencies (dependency injection)
- Configuration models (RuntimeConfig, ApprovalLevel, etc.)
- MCP models (MCPServer, MCPTool)

**Key Diagrams**: Entity relationship diagram, data model hierarchy, message validation flow

---

### [08_design_patterns.md](./08_design_patterns.md)
**Key patterns used throughout the codebase**

- **Dependency Injection**: AgentDependencies for core services
- **Handler Pattern**: ToolRegistry dispatching
- **Message Validation**: ValidatedMessageList enforcing pair invariants
- **Interrupt Token**: Centralized cancellation
- **ReAct Loop with Graceful Completion**: Iterative reasoning with max-turn limits
- **Approval Patterns**: TUI blocking vs Web polling
- **Modular Prompt Composition**: Priority-based section assembly
- **Lazy HTTP Client Initialization**: On-demand client creation
- **Token-Efficient MCP Discovery**: Cached tool discovery
- **Session Indexing & Self-Healing**: Automatic index repair

**Key Diagrams**: Pattern examples with UML-style diagrams, sequence diagrams

---

### [09_extension_points.md](./09_extension_points.md)
**How to extend the system**

- Adding new tools (handler + implementation)
- Creating custom subagents
- Adding prompt sections
- Implementing new UI modes
- Extending session storage
- Adding MCP servers
- Custom approval handlers
- Adding skills

**Key Diagrams**: Extension flow diagrams, integration points, plugin architecture

---

### [10_system_architecture_diagram.md](./10_system_architecture_diagram.md)
**High-level system architecture diagram (academic)**

- Abstracted 6-layer architecture diagram
- Layer responsibilities and relationships
- Key architectural patterns (ReAct, Handler, DI, Token-Efficient Discovery)
- Primary data flow overview
- Novel contributions and design decisions
- Suitable for academic publication and high-level understanding

**Key Diagrams**: Abstracted system architecture, pattern descriptions, data flow

---

### [progressive_context_decay.md](./progressive_context_decay.md)
**Progressive Context Decay - motivation, design decisions, research connections**

- Problem statement: tool outputs as 80% of context, binary compaction failure mode
- The decay-over-delete insight from Agent-Skills-for-Context-Engineering research
- Four mechanisms explained with rationale
- Token savings analysis, impact on evaluation dimensions
- Design decision rationale (why 80%, why 6 recent, why 8K chars)
- Future extensions (semantic masking, cross-session artifacts)

**Key Diagrams**: Before/after context usage curves, Mermaid data flow

---

### [progressive_context_decay_architecture.md](./progressive_context_decay_architecture.md)
**Progressive Context Decay - architecture reference**

- System position diagram (where decay layer sits in ReAct executor)
- Component architecture (ContextCompactor, ArtifactIndex, ReactExecutor methods)
- Staged trigger pipeline (NONE → WARNING → MASK → AGGRESSIVE → COMPACT)
- Message transformation diagram (observation masking before/after)
- Output offloading interception point
- Artifact index lifecycle (record → inject → survive compaction)
- Full compaction sequence (8-step flow)
- Filesystem layout, constants, integration points
- Token budget comparison (before vs after, 52% reduction)

**Key Diagrams**: ASCII architecture diagrams, component maps, data flow sequences

---

### [adaptive_context_compaction.md](./adaptive_context_compaction.md)
**Adaptive Context Compaction - continuous pressure-aware fidelity reduction**

- Three fidelity reduction strategies (fading, archival, full compaction) activated by pressure thresholds
- System overview diagram with size gate, pressure monitor, artifact registry
- Message array state visualization showing per-observation fidelity
- Context pressure curve (sawtooth vs linear growth)
- Compaction pipeline with archive and artifact injection
- Formal model of managed vs unmanaged context utilization
- Memory consolidation analogy (working memory → long-term storage)
- Quantitative impact: 54% total reduction, 78% observation reduction

**Key Diagrams**: System overview, fidelity state diagram, pressure curves, compaction pipeline, memory consolidation parallel

---

### [opencode_improvements.md](./opencode_improvements.md)
**OpenCode-Inspired Improvements - 13 implemented features + Phase 2-4 roadmap**

- Plan mode refactoring: 4-tool state machine replaced with Planner subagent + present_plan
- 9-pass edit tool fuzzy matching chain-of-responsibility (SimpleReplacer → MultiOccurrenceReplacer)
- Session cost tracking with CostTracker service, TUI status bar display, session persistence
- Doom-loop detection via tool call fingerprinting (MD5 sliding window, threshold=3)
- Staged context compaction: 4-stage progressive pressure (WARNING → MASK → AGGRESSIVE → COMPACT)
- Tool output offloading to scratch files (8000-char threshold)
- Lifecycle hooks system: 10 event types, blocking/async, stdin JSON protocol, global+project config merge
- ESC interrupt system: 6 targeted fixes for race conditions, process group kill, modal priority
- Thinking level simplification: Self-Critique merged into High (5→4 levels)
- Provider-specific prompt sections (OpenAI, Anthropic, Fireworks) via PromptComposer conditions
- Parallel subagent spawning: explicit prompt guidance, result synthesis instructions
- Subagent prompt refinements: Code Explorer stop conditions, Planner plan_file_path in output
- Web fetch auto-browser install for Playwright Chromium
- Phase 2-4 roadmap: Event Bus, Provider Abstraction, Snapshot Undo, SQLite Sessions, Permission Cascade, Session Forking, JSONC Config, Enterprise Sharing, File Watcher, TUI Enhancements

**Key Diagrams**: Plan mode before/after flow, replacer chain, cost tracking data flow, staged compaction thresholds, hooks event/command flow, interrupt fix priority logic

---

### [ace_architecture.md](./ace_architecture.md)
**Agentic Context Engineering (ACE) - Architecture Reference**

- System overview: 4-role pipeline (Generator → Reflector → Curator → Playbook)
- Data model: Bullet, Playbook, DeltaOperation, DeltaBatch
- LLM-powered Reflector: execution analysis, bullet tagging, JSON retry loop
- LLM-powered Curator: delta mutation planning, playbook evolution
- Rule-based ExecutionReflector: 5 pattern extractors (file ops, code nav, testing, shell, error recovery)
- BulletSelector hybrid retrieval: effectiveness (0.5) + recency (0.3) + semantic (0.2) scoring
- EmbeddingCache: SHA256 keys, batch optimization (N+1 → 1 API calls), disk persistence
- ConversationSummarizer: incremental episodic memory, 5-message trigger, 6-message working memory exclusion
- Integration architecture: QueryProcessor → ContextPicker → ReactExecutor → ToolExecutor pipeline
- Graceful degradation: every component fails silently, ACE errors never break query processing
- Configuration & tuning: all defaults and knobs documented

**Key Diagrams**: 4-role architecture diagram, end-to-end data flow, incremental summarization window, recency decay curve, pattern extractor table

---

### [agent_scaffolding_architecture.md](./agent_scaffolding_architecture.md)
**Agent construction and wiring - the build-time architecture**

- BaseAgent ABC (4 abstract methods, eager build) and AgentInterface protocol
- AgentFactory → AgentSuite construction pipeline (skills, subagents, main agent)
- MainAgent as the single concrete agent class - behavioral variation via allowed_tools and prompt override
- PromptComposer: priority-sorted conditional sections from markdown files
- ToolSchemaBuilder: filtered builtin schemas + MCP + spawn_subagent
- SubAgentSpec → register_subagent() flow, 8 builtin subagents, custom agents from config
- AgentDependencies vs SubAgentDeps injection paths

**Key Diagrams**: Full construction pipeline ASCII diagram, dependency flow

---

### [guardrails_architecture.md](./guardrails_architecture.md)
**Guardrails & Safety Architecture - multi-layered defense-in-depth system**

- Problem statement: why agentic coding tools need guardrails (arbitrary shell execution, file overwrites, no inherent LLM safety)
- Design philosophy: defense-in-depth with five independent layers, fail-closed, least privilege
- Layer 1: Prompt-level guardrails - security policy (P15), action safety (P56), read-before-edit (P58), error recovery (P60), git workflow (P70), system reminders
- Layer 2: Mode-based tool restrictions - Plan mode read-only whitelist (14 tools), subagent `allowed_tools` filtering, MCP discovery gating
- Layer 3: Runtime approval system - Manual/Semi-Auto/Auto autonomy levels, ApprovalRulesManager with pattern/command/prefix/danger rules, persistent permissions, TUI blocking vs Web WebSocket polling
- Layer 4: Tool-level validation - SAFE_COMMANDS allowlist, DANGEROUS_PATTERNS blocklist, 60s idle / 600s max timeouts, 30K output truncation, FileTimeTracker stale-read detection, backup creation, LSP diagnostics, server auto-background
- Layer 5: Hooks & extensibility - 10 lifecycle events, pre-tool blocking (exit code 2), post-tool async audit, regex matchers, JSON stdin protocol
- Cross-cutting: UndoManager (50-entry log, JSONL persistence), CommandHistory audit trail, subagent isolation, shadow git snapshots
- Full architecture diagram (ASCII) and runtime flow (Mermaid sequence diagram)

**Key Diagrams**: Five-layer architecture stack, approval flow decision tree, runtime execution sequence

---

### [agent_harness_methodology.md](./agent_harness_methodology.md)
**Agent Harness Methodology - how the system orchestrates LLM reasoning, tool execution, context management, and safety**

- The ReAct execution loop: 6-phase iteration lifecycle (compaction → thinking → critique → action → tool execution → post-processing)
- Iteration context tracking: doom-loop fingerprinting, completion nudges, safety caps (200 iterations)
- Three tool execution strategies: sequential, parallel subagent batch, silent parallel (read-only)
- Tool registry: handler-based dispatch with 30+ tools across 11 handler categories
- Token-efficient MCP discovery: lazy schema loading, search_tools-based progressive disclosure
- FileTimeTracker stale-read detection: mtime-based freshness assertion before edits
- Prompt composition: priority-ordered conditional sections, two-part caching (stable + dynamic)
- Staged context optimization: 5 progressive stages (warning → mask → prune → aggressive → compact)
- Output offloading: 8K-char threshold, scratch files, 500-char preview replacement
- Subagent orchestration: 8 built-in agents, custom agent discovery, parallel execution, Docker isolation
- Multi-layer safety: approval rules, dangerous patterns, hooks, stale-read, plan mode, doom-loop, iteration cap, cooperative cancellation
- Message injection: thread-safe queue for concurrent user input during agent execution
- Skills system: lazy-loaded markdown knowledge injection with YAML frontmatter
- ACE Playbook memory: hybrid retrieval (effectiveness 50% + recency 30% + semantic 20%)
- Session management: two-file format (JSON metadata + JSONL transcript), cross-process locking, self-healing index
- Design principles: progressive degradation, token efficiency, safety redundancy, composability, cooperative concurrency, LLM-decides/harness-constrains, reversibility by default

**Key Diagrams**: ReAct iteration lifecycle, tool dispatch flow, staged compaction thresholds, subagent execution flow, multi-layer safety stack

---

### [opencode_improvements_phase2.md](./opencode_improvements_phase2.md)
**OpenCode-Inspired Improvements Phase 2 - 11 implemented features**

- FileTime stale-read detection: mtime-based freshness check before file edits, 50ms tolerance, thread-safe
- Shadow git snapshot system: parallel bare repo at `~/.opendev/snapshot/<id>/`, tree-hash snapshots, per-step undo via `/undo`
- LSP diagnostics after edit: auto-check for Error-level diagnostics, appended to tool output
- Anthropic prompt caching: two-part system prompt (stable + dynamic), `cache_control: {"type": "ephemeral"}`, ~88% input cost reduction
- Two-tier compaction: fast pruning pass at 85% (40K token protection budget) before LLM compaction
- Persistent permission rules: save/load approval rules to `~/.opendev/permissions.json`, `/permissions` command
- Doom loop → permission-based pause: blocking approval prompt instead of advisory warning
- Dynamic truncation hints: agent-aware offloading advice based on subagent capability
- Cost display in Web UI + exit summary: WebSocket broadcasts for cost/context, session cost on REPL exit
- Error prompt table removal: markdown tables → bullet lists in error-recovery and output-awareness templates

**Key Diagrams**: Architecture impact diagram, FileTime flow, snapshot lifecycle, Anthropic cache request flow, prune budget algorithm, approval pause flow

---

## Quick Reference

### Critical Files

| Component | Key Files |
|-----------|-----------|
| **Entry Points** | `swecli/cli.py`, `swecli/ui_textual/runner.py`, `swecli/web/server.py` |
| **Agent Core** | `swecli/core/agents/main_agent.py`, `swecli/core/agents/planning_agent.py` |
| **Tools** | `swecli/core/context_engineering/tools/registry.py`, `handlers/*.py`, `implementations/*.py` |
| **Prompts** | `swecli/core/agents/prompts/composition.py`, `templates/system/main/*.md` |
| **Session** | `swecli/core/context_engineering/history/session_manager.py`, `swecli/models/session.py` |
| **UI (TUI)** | `swecli/ui_textual/chat_app.py`, `swecli/ui_textual/ui_callback.py` |
| **UI (Web)** | `swecli/web/server.py`, `swecli/web/websocket.py`, `swecli/web/state.py` |
| **Config** | `swecli/core/runtime/config.py`, `swecli/core/runtime/mode_manager.py` |
| **MCP** | `swecli/core/context_engineering/mcp/manager.py`, `swecli/core/context_engineering/mcp/client.py` |

### Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 18, Vite, TypeScript, Zustand, TailwindCSS, Radix UI |
| **Backend** | Python 3.10+, FastAPI, WebSockets, asyncio |
| **TUI** | Textual (Python TUI framework) |
| **LLM** | HTTP clients, models.dev API, OpenAI/Anthropic SDKs |
| **Storage** | JSON files, SQLite (future), filesystem |
| **Tools** | MCP protocol, subprocess management, AST parsing |

### Glossary

- **ReAct**: Reasoning and Acting loop - agent reasons about next action, executes tools, loops until task completion
- **MCP**: Model Context Protocol - standard for LLM tool integration
- **Subagent**: Specialized agent for specific tasks (code exploration, planning, web generation, etc.)
- **Tool Handler**: Dispatcher for specific tool categories (file, process, web, etc.)
- **Approval Level**: Manual, Semi-Auto, Auto - controls when user approval is required
- **Context Compaction**: Automatic message history compression when approaching token limits
- **ValidatedMessageList**: Message list that enforces tool_use ↔ tool_result pairing
- **InterruptToken**: Thread-safe cancellation mechanism
- **Session Index**: JSON index of all sessions for fast lookup (with self-healing)
- **PromptComposer**: Modular system for assembling system prompts from sections

---

## Navigation Tips

1. **Use the table of contents** in each file for quick navigation
2. **Mermaid diagrams** are best viewed in GitHub or a markdown viewer with Mermaid support
3. **Code examples** include file paths (e.g., `swecli/core/agents/main_agent.py:123`) for easy reference
4. **Cross-references** link to related sections across files

---

## Contributing to Documentation

When updating this documentation:

1. **Verify accuracy**: Check code examples against actual source files
2. **Update diagrams**: Keep Mermaid diagrams in sync with code changes
3. **Cross-reference**: Update links when moving or renaming sections
4. **Add examples**: Include code snippets with file paths and line numbers
5. **Keep it current**: Update version and last updated date

---

## Additional Resources

- **Project README**: `/README.md` - Getting started guide
- **CLAUDE.md**: `/CLAUDE.md` - Development guidelines for AI assistants
- **Code Documentation**: Inline docstrings and type hints throughout codebase
- **Tests**: `tests/` directory - Unit and integration tests with examples

---

**Ready to dive in?** Start with [Architecture Overview](./01_architecture_overview.md) for a high-level understanding of the system.
