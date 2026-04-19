# Agent Harness Methodology

> How OpenDev orchestrates LLM reasoning, tool execution, context management, and safety into a cohesive agent runtime.

The **agent harness** is the infrastructure that wraps an LLM and turns it from a stateless text generator into a persistent, tool-using, self-correcting software engineering agent. This document describes the complete methodology: the execution loop, dispatch mechanisms, context lifecycle, safety layers, and extensibility points that make the system work.

---

## 1. The ReAct Execution Loop

The core of the agent harness is a **ReAct (Reasoning → Acting → Observing)** loop implemented in `ReactExecutor`. This is not a simple request-response cycle - it is a multi-phase iteration engine with interrupt handling, doom-loop detection, and cooperative cancellation.

### Execution Constants

```
MAX_CONCURRENT_TOOLS    = 5       # Parallel tool execution cap
MAX_REACT_ITERATIONS    = 200     # Safety cap per user turn
DOOM_LOOP_THRESHOLD     = 3       # Same tool+args N times triggers pause
OFFLOAD_THRESHOLD       = 8000    # Characters before output offloading
```

### Iteration Lifecycle

Each user message triggers an execution run. The run persists until the agent produces a final text response with no tool calls, or until an interrupt/safety cap is reached.

```
User Message
    │
    ▼
┌─────────────────────────────────────────────┐
│  Execution Run                              │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │ Drain injected messages (up to 3)    │   │
│  │ Check interrupt token                │   │
│  │ Check iteration safety cap (200)     │   │
│  └──────────────┬───────────────────────┘   │
│                 ▼                            │
│  ┌──────────────────────────────────────┐   │
│  │ Phase 1: Auto-Compaction             │   │
│  │  - Staged context optimization       │   │
│  │  - Token budget enforcement          │   │
│  └──────────────┬───────────────────────┘   │
│                 ▼                            │
│  ┌──────────────────────────────────────┐   │
│  │ Phase 2: Thinking (optional)         │   │
│  │  - Separate LLM call for reasoning   │   │
│  │  - Dedicated thinking system prompt   │   │
│  │  - Result injected as user message   │   │
│  └──────────────┬───────────────────────┘   │
│                 ▼                            │
│  ┌──────────────────────────────────────┐   │
│  │ Phase 3: Self-Critique (optional)    │   │
│  │  - LLM critiques thinking trace     │   │
│  │  - Refined reasoning injected        │   │
│  └──────────────┬───────────────────────┘   │
│                 ▼                            │
│  ┌──────────────────────────────────────┐   │
│  │ Phase 4: Action                      │   │
│  │  - Main LLM call WITH tool schemas   │   │
│  │  - Parses content + tool_calls       │   │
│  │  - Cost tracking & token calibration │   │
│  └──────────────┬───────────────────────┘   │
│                 ▼                            │
│  ┌──────────────────────────────────────┐   │
│  │ Phase 5: Tool Execution              │   │
│  │  - Sequential or parallel dispatch   │   │
│  │  - Approval checks per operation     │   │
│  │  - Results appended as tool messages │   │
│  └──────────────┬───────────────────────┘   │
│                 ▼                            │
│  ┌──────────────────────────────────────┐   │
│  │ Phase 6: Post-Processing             │   │
│  │  - Doom loop detection               │   │
│  │  - Completion evaluation             │   │
│  │  - Session persistence               │   │
│  └──────────────┬───────────────────────┘   │
│                 ▼                            │
│           CONTINUE or BREAK                  │
│                                             │
│  (On BREAK: check for new injected msgs)    │
└─────────────────────────────────────────────┘
    │
    ▼
Save session, fire Stop hook
```

### Iteration Context Tracking

Each execution run maintains an `IterationContext` that tracks behavioral signals across iterations:

- **iteration_count** - safety cap enforcement
- **consecutive_reads** - detects read-without-action patterns
- **consecutive_no_tool_calls** - triggers completion nudges
- **recent_tool_calls** - `deque(maxlen=20)` for doom-loop fingerprinting
- **todo_nudge_count** - limits incomplete-todo reminders
- **plan_approved_signal_injected** - prevents duplicate plan signals
- **doom_loop_warned** - prevents repeat doom-loop dialogs

### Tool Execution Strategies

The executor chooses between three strategies based on tool call composition:

**Sequential** (default): Tools execute one at a time. Used for mixed tool calls where ordering may matter.

**Parallel subagent batch**: When ALL tool calls in a response are `spawn_subagent`, they execute concurrently in a `ThreadPoolExecutor(max_workers=5)`. This enables the agent to fan out research or exploration to multiple subagents simultaneously.

**Silent parallel**: When ALL tool calls are in the `PARALLELIZABLE_TOOLS` set (read-only operations like `read_file`, `list_files`, `search`, `fetch_url`, `web_search`), they execute concurrently. Display output is replayed sequentially after all complete, maintaining visual coherence.

```python
PARALLELIZABLE_TOOLS = frozenset({
    "read_file", "list_files", "search",
    "fetch_url", "web_search",
    "find_symbol", "find_referencing_symbols",
    "list_todos", "analyze_image",
    "capture_screenshot", "capture_web_screenshot",
    "read_pdf", "search_tools", ...
})
```

### Dual Execution Paths

The system provides two execution paths for different UI contexts:

- **ReactExecutor** - Used by the Textual TUI and REPL. Full-featured with interrupt handling, message injection, and rich display integration.
- **MainAgent.run_sync()** - Self-contained loop used by subagents and the Web UI. Simpler lifecycle but shares the same tool dispatch and approval infrastructure.

---

## 2. Tool Registry and Dispatch

The tool system follows a **handler-based dispatch** pattern where a central registry maps tool names to specialized handler methods.

### Architecture

```
ToolRegistry (central dispatch)
    │
    ├── FileToolHandler      → write_file, edit_file, read_file, list_files, search
    ├── ProcessToolHandler   → run_command, list_processes, get_process_output, kill_process
    ├── WebToolHandler       → fetch_url, web_search, capture_web_screenshot
    ├── NotebookToolHandler  → notebook_edit
    ├── ThinkingToolHandler  → thinking (extended reasoning)
    ├── CritiqueToolHandler  → critique (self-evaluation)
    ├── SearchToolsHandler   → search_tools (MCP discovery)
    ├── TodoToolHandler      → write_todos, update_todo, complete_todo, list_todos
    ├── SymbolToolHandler    → find_symbol, rename_symbol, replace_symbol_body, ...
    ├── McpToolHandler       → mcp__* (dynamic MCP tools)
    └── (inline handlers)    → spawn_subagent, task_complete, present_plan, invoke_skill, ...
```

### Execution Flow

```
Agent produces tool_call
    │
    ▼
Registry.execute_tool(name, args)
    │
    ├── Is it mcp__* prefix? → McpToolHandler (auto-discover if needed)
    │
    ├── Fire PreToolUse hook
    │   ├── Exit 0: continue (may modify args)
    │   ├── Exit 2: BLOCK operation
    │   └── Other: log error, continue
    │
    ├── Build ToolExecutionContext
    │   (mode_manager, approval_manager, undo_manager,
    │    task_monitor, session_manager, ui_callback,
    │    is_subagent, file_time_tracker)
    │
    ├── Dispatch to handler by name
    │   ├── Handler checks approval (if write/execute op)
    │   ├── Handler executes operation
    │   └── Handler returns result dict
    │
    └── Fire PostToolUse / PostToolUseFailure hook (async)
```

### ToolExecutionContext

Every tool handler receives a `ToolExecutionContext` dataclass carrying runtime dependencies. This avoids global state and enables subagent isolation:

```python
@dataclass
class ToolExecutionContext:
    mode_manager: Optional[Any]       # Current mode (normal/plan)
    approval_manager: Optional[Any]   # Interactive approval
    undo_manager: Optional[Any]       # Git snapshot undo
    task_monitor: Optional[Any]       # Background process tracking
    session_manager: Optional[Any]    # Conversation persistence
    ui_callback: Optional[Any]        # Display integration
    is_subagent: bool                 # Restricts certain behaviors
    file_time_tracker: Optional[Any]  # Stale-read detection
```

### Token-Efficient MCP Tool Discovery

MCP tools use a **lazy discovery** protocol to avoid bloating LLM context with tool schemas the agent may never use:

1. At startup, MCP servers connect and their tool lists are cached - but NOT included in LLM tool schemas
2. The agent has a `search_tools` tool that searches across all registered and MCP tools by keyword
3. When `search_tools` discovers a relevant MCP tool, it calls an `on_discover` callback
4. The callback adds the tool to `_discovered_mcp_tools`, making its schema available to the LLM on the next turn
5. If the agent calls an MCP tool directly (without discovery), it is auto-discovered with a warning log

This means an agent connected to 10 MCP servers with 200+ tools only pays for the schemas of tools it actually needs.

### Stale-Read Detection (FileTimeTracker)

The `FileTimeTracker` prevents a subtle but dangerous failure mode: editing a file based on outdated content.

- Every `read_file` records the file's modification timestamp
- Before `edit_file` or `write_file`, `assert_fresh()` checks if the file changed since the last read
- If stale, the operation fails with a message asking the agent to re-read the file
- This catches cases where external processes (build tools, formatters, other agents) modify files between the agent's read and write

---

## 3. Prompt Composition

System prompts are not monolithic strings - they are assembled from modular, prioritized, conditionally-loaded markdown sections.

### PromptSection Model

```python
@dataclass
class PromptSection:
    name: str                                    # Section identifier
    file_path: str                               # Path to markdown template
    condition: Optional[Callable[[Dict], bool]]  # Inclusion predicate
    priority: int                                # Lower = earlier in prompt (default: 50)
    cacheable: bool                              # True = stable content (API caching eligible)
```

### Section Registry

The default `PromptComposer` registers 21 sections spanning identity, safety, tools, workflow, and context:

```
Priority 12  │ mode_awareness        │ Always
Priority 15  │ security_policy       │ Always
Priority 20  │ tone_and_style        │ Always
Priority 25  │ no_time_estimates     │ Always
Priority 40  │ interaction_pattern   │ Always
Priority 45  │ available_tools       │ Always
Priority 50  │ tool_selection        │ Always
Priority 55  │ code_quality          │ Always
Priority 56  │ action_safety         │ Always
Priority 58  │ read_before_edit      │ Always
Priority 60  │ error_recovery        │ Always
Priority 65  │ subagent_guide        │ Only when subagents enabled
Priority 70  │ git_workflow          │ Only in git repos
Priority 75  │ task_tracking         │ Only when todo tracking enabled
Priority 80  │ provider_*            │ Provider-specific (OpenAI/Anthropic/Fireworks)
Priority 85  │ output_awareness      │ Always
Priority 87  │ scratchpad            │ Dynamic (per session)
Priority 90  │ code_references       │ Always
Priority 95  │ system_reminders_note │ Dynamic (per turn)
```

### Two-Part Composition for Prompt Caching

The composer splits output into two segments:

- **Stable part** (cacheable sections): Core identity, policies, tool guidance - changes rarely. Eligible for Anthropic prompt caching, which avoids re-processing on every turn.
- **Dynamic part** (non-cacheable sections): Scratchpad state, reminders - changes every turn.

This separation ensures the majority of the system prompt hits cache, reducing latency and cost.

### Builder Hierarchy

```
BasePromptBuilder (abstract)
    ├── SystemPromptBuilder     (core_template = "system/main")
    ├── ThinkingPromptBuilder   (core_template = "system/thinking")
    └── PlanningPromptBuilder   (simplified, plan-mode specific)
```

Each builder assembles:
1. Modular prompt from `PromptComposer`
2. Environment context (OS, shell, git status, directory structure)
3. Project instructions (`CLAUDE.md` or `OPENDEV.md`)
4. Skills index (available skill metadata)
5. MCP section (connected server descriptions)

### Reminder System

Short, targeted messages injected into the conversation at specific moments:

- `thinking_trace_reminder` - wraps thinking output for the action phase
- `failed_tool_nudge` - error-specific recovery guidance
- `incomplete_todos_nudge` - prevents premature completion
- `plan_approved_signal` - tells agent to execute the approved plan
- `subagent_complete_signal` - signals subagent results are ready
- `nudge_permission_error`, `nudge_edit_mismatch`, `nudge_file_not_found` - error-specific corrective hints

Reminders are stored in `templates/reminders.md` using `--- SECTION_NAME ---` delimiters and support variable substitution via `str.format()`.

---

## 4. Context Engineering: Staged Optimization

Long-running agent sessions accumulate large conversation histories. The `ContextCompactor` implements a **5-stage progressive optimization** strategy that activates as context usage grows:

### Stage Thresholds

```
                    0%                70%    80%    85%    90%    99%    100%
Context Window:     ├──────────────────┤──────┤──────┤──────┤──────┤──────┤
                    │    Normal Ops    │ Warn │ Mask │Prune │Aggr. │Compact│
```

### Stage Details

**Stage 1 - Warning (70%)**: Logs a warning and begins tracking context growth rate. No modifications.

**Stage 2 - Observation Masking (80%)**: Replaces old tool result messages with tombstone references `[ref: tool result {id} - see history]`. Keeps the 6 most recent tool results intact. Zero LLM cost.

**Stage 3 - Pruning (85%)**: Walks backwards through messages, protecting ~40K tokens of recent tool outputs. Replaces older tool outputs with `[pruned]`. Zero LLM cost - this is a fast, deterministic operation.

**Stage 4 - Aggressive Masking (90%)**: Same as Stage 2 but keeps only the last 3 tool results. More aggressive reclamation.

**Stage 5 - Full Compaction (99%)**: LLM-powered summarization:
1. Archives the full conversation to a scratch file for recovery
2. Keeps system prompt (index 0) and the last N messages
3. Summarizes the middle section via an LLM call (using a dedicated compact model if configured)
4. Injects an **ArtifactIndex** into the summary - a record of all file operations (create/modify/read/delete) so the agent retains file awareness
5. Adds the archive file path so the agent can `read_file` to recover specific details

### ArtifactIndex

The `ArtifactIndex` tracks every file operation across the session. It survives compaction and is embedded in the summary. This is critical: after compaction, the agent might lose memory of which files it created or modified. The index restores this knowledge without the full conversation history.

### Token Tracking

Two complementary approaches:

- **API calibration**: Uses the real `prompt_tokens` count from API responses, then estimates deltas for new messages added since the last call.
- **Tiktoken fallback**: Character-based estimation when API data is unavailable (first turn, or non-OpenAI providers).

### ValidatedMessageList

A `list` subclass that enforces message-pair invariants at write time:

- **State machine**: After an assistant message with tool_calls, the list expects exactly the matching tool result messages before any new user/assistant message
- If a new message arrives before all tool results, synthetic error results are auto-generated for the missing ones
- Thread-safe via `threading.Lock`
- Intercepts `append`, `extend`, `insert`, `__setitem__` to enforce invariants

This prevents malformed message sequences that would cause API errors - a common source of hard-to-debug failures in agent systems.

---

## 5. Output Offloading

Large tool outputs consume context disproportionately - tool results account for ~80% of context tokens in typical sessions. The offloading mechanism caps this:

1. When a tool result exceeds `OFFLOAD_THRESHOLD` (8000 characters), the full output is written to `~/.opendev/scratch/{session_id}/`
2. The tool result in the conversation is replaced with a **500-character preview** plus a file reference
3. The agent can `read_file` the scratch file if it needs the full content

This trades a small increase in tool calls for a large decrease in context consumption, extending the effective working memory of the agent.

---

## 6. Subagent Orchestration

The system supports spawning ephemeral subagents for isolated tasks. Each subagent is a complete `MainAgent` instance with its own tool set, system prompt, and conversation history.

### Built-in Subagents

```
code_explorer      → Read-only codebase exploration
planner            → Strategic planning and decomposition
pr_reviewer        → Pull request analysis
project_init       → Project scaffolding
security_reviewer  → Security vulnerability analysis
web_clone          → Website cloning
web_generator      → Web page generation
ask_user           → User interaction proxy
```

### Custom Agent Discovery

Custom agents are loaded from:
- `<project>/.opendev/agents.json` or `<project>/.opendev/agents/*.md` (project-scoped)
- `~/.opendev/agents.json` or `~/.opendev/agents/*.md` (user-global)

Each agent spec defines:
```python
class SubAgentSpec(TypedDict):
    name: str
    description: str
    system_prompt: str
    tools: NotRequired[list[str]]       # Allowed tools
    model: NotRequired[str]             # Model override
    docker_config: NotRequired[...]     # Docker isolation
```

Tool filtering supports three modes:
- **Explicit list**: `["read_file", "search", "list_files"]`
- **All tools**: `"*"`
- **Exclusion**: `{"exclude": ["run_command", "write_file"]}`

### Execution Flow

```
Main Agent
    │
    ├── Calls spawn_subagent(type="code_explorer", prompt="...")
    │
    ▼
SubAgentManager.execute_subagent()
    │
    ├── Resolves SubAgentSpec (built-in or custom)
    ├── Filters tool registry to allowed tools
    ├── Builds specialized system prompt
    ├── Creates fresh MainAgent instance
    ├── Runs MainAgent.run_sync() (own ReAct loop)
    │
    ▼
Returns result as separate_response + completion_status
```

### Parallel Subagent Execution

When the main agent produces multiple `spawn_subagent` calls in a single response, they execute concurrently in a `ThreadPoolExecutor(max_workers=5)`. This enables fan-out patterns: research multiple topics, explore multiple code paths, or review multiple files simultaneously.

### Docker Isolation

Subagents can optionally execute inside Docker containers for sandboxed execution. The manager handles file copying into containers and falls back to local execution if Docker is unavailable.

---

## 7. Approval and Safety System

Safety is implemented as multiple independent layers, any of which can block an operation.

### Layer 1: Approval System

All write operations and command executions route through the `ApprovalManager`:

```
Tool handler prepares Operation
    │
    ▼
ApprovalRulesManager checks patterns
    │
    ├── AUTO_APPROVE  → proceed
    ├── AUTO_DENY     → block with reason
    ├── REQUIRE_EDIT  → user must edit before approve
    └── REQUIRE_APPROVAL → interactive prompt
         │
         ├── "Yes"                    → proceed
         ├── "Yes, don't ask again"   → add auto-approve rule, proceed
         └── "No"                     → block, feedback to agent
```

Rules are persisted at two levels:
- `~/.opendev/permissions.json` (user-global)
- `.opendev/permissions.json` (project-scoped)

### Layer 2: Dangerous Command Detection

The `ModeManager` maintains a regex list of known dangerous patterns:

```
rm -rf /            chmod -R 777         sudo
:(){ :|:& };:       mv /                 curl | bash
dd if=...of=/dev    mkfs                 fdisk
```

These always require explicit approval regardless of auto-approve rules.

### Layer 3: Hook System

The hook system fires external commands at lifecycle events. `PreToolUse` hooks can **block** operations by returning exit code 2:

```
HookEvent.PRE_TOOL_USE
    │
    ▼
Hook executor runs external command
    ├── stdin: JSON with tool name, args, session context
    ├── Exit 0: allow (may modify args via updatedInput)
    ├── Exit 2: BLOCK with reason
    └── Other: log error, continue
```

Available lifecycle events:
```
SessionStart         → Session begins
UserPromptSubmit     → User sends message
PreToolUse           → Before tool execution (can block)
PostToolUse          → After successful tool execution (async)
PostToolUseFailure   → After failed tool execution (async)
SubagentStart        → Subagent spawned
SubagentStop         → Subagent completed
Stop                 → Agent completing (can prevent)
PreCompact           → Before context compaction
SessionEnd           → Session ends
```

Security: Hook config is snapshotted at initialization. Mid-session changes to settings are not reflected, preventing TOCTOU attacks.

### Layer 4: Stale-Read Detection

`FileTimeTracker` prevents editing files based on outdated reads (described in Section 2).

### Layer 5: Plan Mode

When in `plan` mode, the agent's tool set is restricted to read-only operations. It can explore and reason but cannot modify files or execute commands. The agent builds a plan, presents it for approval, and only executes after user confirmation.

### Layer 6: Doom Loop Detection

Fingerprints each tool call as `tool_name + MD5(args)[:12]` and stores in a `deque(maxlen=20)`. If any fingerprint appears >= 3 times, execution pauses and the user is asked whether to continue or break.

### Layer 7: Iteration Safety Cap

`MAX_REACT_ITERATIONS = 200` prevents runaway loops. If reached, the agent is forced to complete.

### Layer 8: Cooperative Cancellation

An `InterruptToken` is shared across all components. The user pressing ESC signals the token, which is checked at multiple points in the iteration lifecycle (pre-thinking, pre-action, during tool execution). This enables clean cancellation at any phase.

---

## 8. Mode Management: Normal and Plan

The system operates in two modes:

### Normal Mode
Full agent capabilities: read, write, execute, plan, and act. All tools available (subject to approval).

### Plan Mode
Read-only: the agent can explore the codebase and reason, but cannot modify files or execute commands. The workflow:

1. User activates plan mode (via `/mode` command or Shift+Tab)
2. Agent explores codebase using read-only tools
3. Agent calls `present_plan` with structured plan steps
4. Plan displayed for user review
5. User approves → todos auto-created from plan steps
6. Mode switches back to normal
7. `plan_approved_signal` injected, agent executes the plan

---

## 9. Error Recovery

Error recovery is not a single mechanism but a layered strategy:

### Error Classification

Failed tool calls are classified into categories:
```
permission_error  → file permissions issue
edit_mismatch     → content didn't match (stale read)
file_not_found    → wrong path
syntax_error      → code has syntax errors
rate_limit        → API rate limiting
timeout           → operation timed out
generic           → unclassified
```

### Error-Specific Nudges

Each error category has a targeted nudge message injected as a user message:

- **permission_error**: "Check file permissions, try with appropriate access"
- **edit_mismatch**: "Re-read the file to get current content, then retry"
- **file_not_found**: "Use list_files/search to find the correct path"
- **rate_limit**: "Reduce concurrency, wait before retrying"

### Retry Limits

`MAX_NUDGE_ATTEMPTS = 3` - after 3 consecutive nudges without the agent making a successful tool call, the system accepts the best-effort completion rather than continuing to loop.

### System Prompt Guidance

The `main-error-recovery.md` prompt section teaches the LLM common error patterns and resolution strategies at the instruction level, so the model can self-correct before needing a nudge.

---

## 10. Dependency Injection

The system uses a **Factory + Suite** pattern for dependency assembly:

### Construction Flow

```
RuntimeService.build_suite()
    │
    ├── EnvironmentCollector → env_context (OS, git, project info)
    │
    ├── ToolDependencies → bundled tool implementations
    │
    ├── ToolFactory → ToolRegistry (handler-based dispatch)
    │
    ├── AgentFactory
    │   ├── MainAgent (with all dependencies)
    │   ├── SubAgentManager (built-in + custom agents)
    │   └── SkillLoader (project + global + built-in skills)
    │
    └── RuntimeSuite
        ├── tool_registry: ToolRegistryInterface
        ├── agents: AgentSuite
        ├── agent_factory: AgentFactory
        ├── tool_factory: ToolFactory
        └── env_context: EnvironmentContext
```

### Setter Injection for Circular Dependencies

The tool registry needs the subagent manager (for `spawn_subagent`), and the subagent manager needs the tool registry (for filtered tool sets). This circular dependency is resolved via setter injection: the registry is constructed first, then the subagent manager and skill loader are attached via setter methods after construction.

---

## 11. Memory Systems

### ACE Playbook (Persistent Strategy Memory)

The Playbook is a structured store of **bullets** - strategy and insight entries that evolve based on feedback:

```python
@dataclass
class Bullet:
    id: str
    section: str       # Category grouping
    content: str       # The insight/strategy text
    helpful: int       # Positive feedback count
    harmful: int       # Negative feedback count
    neutral: int       # Neutral feedback count
    created_at: str
    updated_at: str
```

### Hybrid Retrieval (BulletSelector)

When retrieving relevant bullets, three factors are combined:

- **Effectiveness (50% weight)**: `helpful / (helpful + harmful + 1)` ratio - strategies that worked well are preferred
- **Recency (30% weight)**: Decay function `1 / (1 + days_old * 0.1)` - recent insights are more relevant
- **Semantic similarity (20% weight)**: Cosine similarity between query embedding and bullet embedding

An `EmbeddingCache` provides efficient batch embedding generation with disk persistence.

### Conversation Summarizer & Reflector

Additional memory components for:
- Summarizing conversations for long-term archival
- Reflecting on agent performance to generate new playbook bullets

---

## 12. Session and History Management

### Two-File Storage Format

Each session is persisted as two files:
- `{session_id}.json` - Session metadata (title, timestamps, channel, model info - no messages)
- `{session_id}.jsonl` - Message transcript (one JSON object per line, append-only)

The JSONL format enables efficient append-only writes. Messages are never rewritten - only appended.

### Cross-Process Safety

`exclusive_session_lock()` provides file-level locking for atomic writes. JSONL append operations are lock-protected for concurrent access from multiple channels (TUI, Web UI, programmatic).

### Session Index

`sessions-index.json` caches session metadata for O(1) list operations. It is self-healing: if corrupted, it is transparently rebuilt from individual session `.json` files.

### Snapshot Manager (Per-Step Undo)

The `SnapshotManager` creates shadow git snapshots after write operations (`write_file`, `edit_file`, `run_command`). Users can revert individual tool actions, providing fine-grained undo at the step level rather than the commit level.

### Topic Detection

The `TopicDetector` generates human-readable session titles from conversation content, used in the sidebar for session browsing.

---

## 13. Message Injection

Both `ReactExecutor` and `MainAgent` support injecting user messages into a running agent loop from external threads:

```python
# Thread-safe bounded queue
_injection_queue: queue.Queue[str] = queue.Queue(maxsize=10)
```

Messages are drained at iteration boundaries (up to 3 per drain). This enables:
- Users typing follow-up messages while the agent is working
- The UI thread sending control signals
- Preventing premature completion when new user input arrives

If the agent is about to complete (no tool calls) and new messages are in the queue, the loop continues instead of breaking.

---

## 14. Skills System

Skills are markdown files with YAML frontmatter that inject domain-specific knowledge into the agent's context on demand:

```markdown
---
name: commit
description: Git commit best practices
namespace: default
---
# Git Commit Skill
When making commits: ...
```

### Discovery and Loading

Skills are discovered from three directories (highest priority first):
1. `<project>/.opendev/skills/` - project-local overrides
2. `~/.opendev/skills/` - user-global
3. `swecli/skills/builtin/` - shipped with the tool

**Lazy loading**: Only YAML frontmatter is read at startup. Full content is loaded on-demand when the agent calls `invoke_skill`. If a skill was already loaded in the session, a short reminder is returned instead of the full content, avoiding redundancy.

Skills are listed in the system prompt via `build_skills_index()`, giving the agent awareness of available specialized knowledge.

---

## 15. Configuration

### Hierarchical Loading

```
.opendev/settings.json     (project - highest priority)
        │
        ▼
~/.opendev/settings.json   (user-global)
        │
        ▼
Default values             (lowest priority)
```

### Multi-Model Routing

The config supports 5 separate model slots, allowing different models for different cognitive tasks:

```
model / model_provider           → Main action model
model_thinking / model_thinking_provider  → Thinking phase
model_critique / model_critique_provider  → Self-critique phase
model_vlm / model_vlm_provider   → Vision tasks
model_compact / model_compact_provider   → Context compaction
```

This enables cost-performance optimization: use a capable model for action, a fast model for thinking, and a cheap model for compaction.

---

## 16. Design Principles Summary

The agent harness methodology is built on these core principles:

1. **Progressive degradation over hard failures**: Context compression activates in stages rather than crashing when context is full. Errors produce nudges rather than halting execution.

2. **Token efficiency as a first-class concern**: MCP lazy discovery, output offloading, two-part prompt caching, staged compaction - every design decision considers context window as a scarce resource.

3. **Safety through redundancy**: Multiple independent safety layers (approval, hooks, dangerous pattern detection, stale-read checks, doom-loop detection, plan mode, iteration caps) each catch different failure modes.

4. **Composability over monoliths**: Prompts are modular sections, tools are handler objects, agents are composable specs, config is hierarchical. No single component is a monolithic blob.

5. **Cooperative concurrency**: Thread-safe message injection, cooperative cancellation via InterruptToken, validated message lists - the system is designed for concurrent access from multiple threads and UI surfaces.

6. **The LLM decides, the harness constrains**: The agent loop never hard-codes if/else branching for conversation flows. The LLM chooses what to do; the harness provides tools, enforces safety, manages context, and handles failures.

7. **Reversibility by default**: Git snapshots for per-step undo, scratch file archives for compacted history, persistent session storage - the system preserves the ability to go back at every level.
