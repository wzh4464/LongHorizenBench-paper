# System Architecture Diagram

**Purpose**: This document presents the high-level architectural design of SWE-CLI, an agentic coding assistant. It emphasizes architectural patterns, layer responsibilities, and system design decisions suitable for academic publication.

**How to Read**: The system follows a 6-layer architecture from entry point to persistence, with clear separation of concerns and well-defined interfaces between layers.

---

## High-Level Architecture

```
┌──────────────────────────────────────────────┐
│            CLI Entry Point                   │
│  • Argument parsing                          │
│  • Environment initialization                │
│  • Service container bootstrapping           │
└───────────────────┬──────────────────────────┘
                    ↓
        ┌───────────┴───────────┐
        ↓ TUI (Textual)         ↓ Web (FastAPI + React)
    ┌───────────┐           ┌───────────┐
    │ Blocking  │           │ Polling   │
    │ Modals    │           │ WebSocket │
    │ (Direct)  │           │ (Async)   │
    └─────┬─────┘           └─────┬─────┘
          └───────────┬───────────┘
                      ↓
    ┌─────────────────────────────────────────┐
    │         Agent Layer (DI Pattern)        │
    │  ┌──────────────┬──────────────┐       │
    │  │ Normal Mode  │  Plan Mode   │       │
    │  │ (Full Tools) │ (Read-Only)  │       │
    │  └──────────────┴──────────────┘       │
    │                                         │
    │  ReAct Loop (Max 10 Iterations):       │
    │   Reason → Act → Execute → Observe     │
    └──────────────────┬──────────────────────┘
                       ↓
    ┌─────────────────────────────────────────┐
    │    Tool Execution (Handler Pattern)     │
    │  ┌─────────────────────────────────┐   │
    │  │ ToolRegistry (Central Dispatch) │   │
    │  └─────────────┬───────────────────┘   │
    │                ↓                        │
    │  ┌──────────────────────────────────┐  │
    │  │ Specialized Handlers:            │  │
    │  │ • File Operations                │  │
    │  │ • Process & Task Management      │  │
    │  │ • Web & Search Integration       │  │
    │  │ • MCP Protocol Integration       │  │
    │  │ • Code Symbol Navigation         │  │
    │  │ • User Interaction               │  │
    │  └──────────────────────────────────┘  │
    └──────────────────┬──────────────────────┘
                       ↓
    ┌─────────────────────────────────────────┐
    │      Context Engineering Layer          │
    │  • Modular Prompt Composition           │
    │  • Automatic Context Compaction         │
    │  • Persistent Memory System             │
    │  • Token-Efficient Tool Discovery       │
    │  • AST-based Symbol Analysis            │
    └──────────────────┬──────────────────────┘
                       ↓
    ┌─────────────────────────────────────────┐
    │         Persistence Layer               │
    │  • Session & Conversation Storage       │
    │  • Hierarchical Configuration           │
    │  • Model Provider Cache                 │
    │  • Message Validation & Invariants      │
    └─────────────────────────────────────────┘

Legend:
  ┌─────┐  Component/Layer
  ───→   Data/Control Flow
  • Item Bullet point/feature
```

---

## Layer Descriptions

### Layer 1: Entry Point
The entry point layer handles command-line argument parsing, environment initialization, and bootstraps core services. It determines the UI mode (TUI vs Web) and initializes the dependency injection container with all core managers (session, config, approval, mode, undo). This layer ensures proper setup before control passes to the UI layer.

### Layer 2: User Interface
The UI layer provides two distinct interfaces with different interaction patterns. The TUI uses a blocking modal approach for approvals and user prompts, leveraging direct function calls. The Web UI employs an event-driven architecture with WebSocket broadcasting and state polling for asynchronous resolution. Both interfaces bridge user interactions to the agent layer while maintaining their own state management and rendering logic.

### Layer 3: Agent
The agent layer implements the core ReAct (Reason-Act-Observe) loop with dependency injection for loose coupling. Two agent modes are supported: Normal mode with full tool access for implementation, and Plan mode with read-only tools for planning. Agents iterate up to 10 times, reasoning about the task, selecting tools, executing them, and observing results until completion. The layer integrates subagent spawning for specialized tasks like code exploration and web scraping.

### Layer 4: Tool Execution
Tool execution follows the Handler Pattern for extensible tool dispatch. The central ToolRegistry routes tool calls to specialized handlers based on tool categories. Handlers abstract tool implementations and manage approval workflows based on autonomy levels. The layer supports dynamic MCP tool integration, parallel batch execution, and background task management with interrupt handling.

### Layer 5: Context Engineering
This layer addresses token efficiency and context management. Modular prompt composition assembles system prompts from prioritized sections with conditional inclusion. Automatic compaction triggers when token count exceeds thresholds, summarizing older messages while preserving recent context. A persistent memory system maintains cross-session knowledge. Token-efficient MCP tool discovery ensures only discovered tools consume context. AST-based symbol tools enable semantic code navigation.

### Layer 6: Persistence
The persistence layer handles all storage operations with atomic writes and validation. Session management provides CRUD operations with auto-save and indexing for fast retrieval. Hierarchical configuration loading respects project-scoped, user-global, and environment-based settings. Provider caching reduces API calls for model metadata. Message validation enforces tool-use and tool-result pairing invariants at write time.

---

## Key Architectural Patterns

### 1. ReAct Loop Pattern
The agent follows an iterative Reason-Act-Observe cycle where the LLM analyzes the situation, selects tools to execute, observes results, and repeats until task completion. This pattern enables dynamic decision-making without hard-coded control flow, allowing the agent to adapt to changing circumstances.

### 2. Handler Pattern for Tool Dispatch
Tool execution uses a handler-based dispatch system where the ToolRegistry routes tool calls to specialized handlers. Each handler encapsulates logic for a category of related tools, enabling extensibility and separation of concerns. Handlers manage approval workflows and error handling uniformly.

### 3. Dependency Injection
All agents receive an AgentDependencies container with core services (session, mode, approval, undo managers). Tools receive a ToolExecutionContext during execution. This pattern enables loose coupling, testability, and consistent service access across the system.

### 4. Dual-Mode Agent Architecture
The system provides two agent modes with different tool access: Normal mode for implementation with full tool access, and Plan mode for planning with read-only tools. Mode switching is dynamic and preserves session context, enabling seamless transitions between planning and execution phases.

### 5. Event-Driven UI Communication
The TUI and Web UI implement different interaction patterns suited to their environments. The TUI uses blocking calls with immediate responses, while the Web UI broadcasts events via WebSocket and polls shared state for resolution. This pattern accommodates both synchronous and asynchronous user interaction models.

### 6. Token-Efficient Tool Discovery
MCP tools are not included in LLM context by default. Agents explicitly discover tools via keyword search or auto-discover on first use. Only discovered tools have their schemas included in subsequent LLM calls, preventing context bloat from hundreds of available tools.

### 7. Modular Prompt Composition
System prompts are assembled from individual markdown sections with priorities and conditional inclusion based on context. This pattern enables easy addition, removal, or reordering of prompt guidance without editing monolithic templates, improving maintainability.

### 8. Validated Message Lists
Message sequences enforce structural invariants at write time. Every tool-use message must have a corresponding tool-result message, and vice versa. Validation prevents corrupted message sequences from being persisted, ensuring conversation integrity.

---

## Primary Data Flow

The system operates as a continuous cycle:

1. **User Input**: User provides input via TUI or Web UI
2. **Session Update**: Input is added to the session's message history
3. **Agent Execution**: Agent enters ReAct loop with full message history
4. **Tool Selection**: Agent reasons and selects tools to execute
5. **Tool Execution**: ToolRegistry dispatches to handlers, which execute implementations
6. **Result Observation**: Tool results are added to message history
7. **Iteration**: Agent observes results and continues reasoning until task completion
8. **Persistence**: Complete session is saved with atomic writes
9. **UI Response**: Final response is displayed to user

**Approval Flow**: When a tool requires approval (based on autonomy level), the system pauses execution. In TUI mode, a blocking modal displays until user decision. In Web mode, an approval event is broadcast via WebSocket, and execution polls a shared state dict until the frontend submits a decision via API.

**Context Management**: Before each LLM call, token count is checked. If exceeding 90% of maximum context, automatic compaction triggers, summarizing older messages while preserving recent interactions.

**Subagent Spawning**: For specialized multi-step tasks (code exploration, web scraping, planning), the agent can spawn subagents that operate independently with their own tool context, returning results when complete.

---

## Novel Contributions

### Token-Efficient MCP Integration
Unlike traditional approaches that include all available tools in context, this system uses lazy discovery where tools are only included after explicit discovery or first use. This enables integration of hundreds of external tools without context bloat.

### Modular Prompt Architecture
System prompts are composed from prioritized, conditional sections rather than monolithic templates. This approach improves maintainability and enables context-aware prompt adaptation.

### Dual Interaction Patterns
The system supports both blocking (TUI) and asynchronous (Web) interaction patterns through a unified abstraction layer, accommodating different user interface paradigms without duplicating agent logic.

### Automatic Context Compaction
Proactive context management triggers summarization before token limits are reached, enabling indefinitely long conversations while preserving recent context fidelity.

### Validated Message Sequences
Enforcing tool-use and tool-result pairing at write time prevents a common class of errors in agentic systems where message sequences become corrupted during complex tool interactions.

---

## Design Decisions

### Why Hierarchical Configuration?
Enables per-project customization while maintaining user-global defaults and supporting environment-based overrides for CI/CD integration.

### Why Two UI Modes?
Different users prefer different interfaces. Terminal users value speed and keyboard-driven workflows, while web users prefer rich visualizations and mouse-based interactions. Supporting both maximizes accessibility.

### Why Handler Pattern for Tools?
As the tool set grows, a centralized dispatch pattern with specialized handlers prevents tool implementation logic from becoming monolithic. New tool categories can be added without modifying the core agent.

### Why Dual Agent Modes?
Separating planning (read-only tools) from implementation (full tools) encourages deliberate design before execution. Plan mode reduces risk of premature implementation while maintaining full exploration capabilities.

### Why Blocking vs Polling for Approvals?
Terminal-based modals can block naturally using synchronous calls. Web-based approvals require asynchronous resolution due to the HTTP request-response cycle and WebSocket event model. Each pattern is optimal for its environment.

---

## Legend

```
┌─────┐
│ Box │  Component, layer, or logical grouping
└─────┘

  ↓      Data flow or control flow (vertical)
  →      Data flow or control flow (horizontal)

═════    Section separator or emphasis

• Item   Bullet point for features or capabilities
```

---

**Document Status**: Abstracted for Academic Publication
**Audience**: Researchers, architects, and academics
**Focus**: Architectural patterns and design decisions
**Detailed Implementation**: See developer documentation
