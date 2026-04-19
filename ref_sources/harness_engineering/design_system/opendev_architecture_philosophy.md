# OpenDev Architecture Philosophy

> *LLMs are interchangeable compute units - you slot the right model into the right cognitive task, not the right agent.*

---

## Figure: OpenDev Four-Level Architecture with Per-Workflow LLM Binding

```
                                            OpenDev
                                               │
                 ┌─────────────────────────────┼──────────────────────────────┐
                 │                             │                              │
                 ▼                             ▼                              ▼
┌─ Session A ─────────────────┐  ┌─ Session B ──────────────────┐  ┌─ Session N ─ ─ ─ ─ ─ ─ ┐
│                             │  │                              │         · · ·
│  ┌────────────────────────┐ │  │  ┌────────────────────────┐  │  │                         │
│  │     Main Agent         │ │  │  │     Main Agent         │  │
│  │                        │ │  │  │                        │  │  │                         │
│  │  ┌──────────────────┐  │ │  │  │  ┌──────────────────┐  │  │
│  │  │  Execution       │╌╌┼╌┼╌╌┼╌╌┼╌╌│  Execution       │╌╌┼╌╌┼╌╌▶ Sonnet 4.6  │        │
│  │  ├──────────────────┤  │ │  │  │  ├──────────────────┤  │  │
│  │  │  Thinking        │╌╌┼╌┼╌╌┼╌╌┼╌╌│  Thinking        │╌╌┼╌╌┼╌╌▶ Opus 4.6    │        │
│  │  ├──────────────────┤  │ │  │  │  ├──────────────────┤  │  │
│  │  │  Compact         │╌╌┼╌┼╌╌┼╌╌┼╌╌│  Compact         │╌╌┼╌╌┼╌╌▶ Qwen 3.5    │        │
│  │  └──────────────────┘  │ │  │  │  └──────────────────┘  │  │
│  └────────────────────────┘ │  │  └────────────────────────┘  │  │                         │
│                             │  │                              │
│  ┌────────────────────────┐ │  │  ┌────────────────────────┐  │  │                         │
│  │   Planning Agent       │ │  │  │   Explorer Agent       │  │
│  │                        │ │  │  │                        │  │  │                         │
│  │  ┌──────────────────┐  │ │  │  │  ┌──────────────────┐  │  │
│  │  │  Thinking        │╌╌┼╌┼╌╌┼╌╌┼╌╌│  Execution       │╌╌┼╌╌┼╌╌▶ DeepSeek V3.2        │
│  │  ├──────────────────┤  │ │  │  │  ├──────────────────┤  │  │
│  │  │  Compact         │╌╌┼╌┼╌╌┼╌╌┼╌╌│  Compact         │╌╌┼╌╌┼╌╌▶ GLM 5       │        │
│  │  └──────────────────┘  │ │  │  │  └──────────────────┘  │  │
│  └────────────────────────┘ │  │  └────────────────────────┘  │  │                         │
│                             │  │                              │
│  ┌────────────────────────┐ │  │  ┌────────────────────────┐  │  │                         │
│  │   Explorer Agent       │ │  │  │   SubAgent (...)       │  │
│  │  ┌──────────────────┐  │ │  │  │  ┌──────────────────┐  │  │  │                         │
│  │  │  Execution       │╌╌┼╌┼╌╌┼╌╌┼╌╌│  Execution       │╌╌┼╌╌┼╌╌▶ Gemini 3.1
│  │  ├──────────────────┤  │ │  │  │  └──────────────────┘  │  │  │                         │
│  │  │  Compact         │╌╌┼╌┼╌╌┼╌╌┼╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┼╌╌┼╌╌▶ Qwen 3.5
│  │  └──────────────────┘  │ │  │  └────────────────────────┘  │  │                         │
│  └────────────────────────┘ │  │                              │
│                             │  │                              │  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
│  ┌────────────────────────┐ │  └──────────────────────────────┘
│  │   SubAgent (...)       │ │
│  │  ┌──────────────────┐  │ │
│  │  │  Execution       │╌╌┼╌┼╌╌▶ Kimi K2.5
│  │  └──────────────────┘  │ │
│  └────────────────────────┘ │
│                             │
└─────────────────────────────┘

                                ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
                                All workflow arrows (╌╌▶) point into
                                the shared LLM Pool below:
                                ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌

           ╔═══════════════════════════════════════════════════════════════╗
           ║                          LLM Pool                            ║
           ║                                                              ║
           ║   Sonnet 4.6       Opus 4.6       GPT 5       Gemini 3.1    ║
           ║                                                              ║
           ║   Qwen 3.5         Kimi K2.5      DeepSeek V3.2    GLM 5    ║
           ║                                                              ║
           ╚═══════════════════════════════════════════════════════════════╝
```

---

### Description

The figure presents the complete OpenDev system as a four-level hierarchy read top-to-bottom, from the most abstract layer to the most concrete. A shared LLM pool at the bottom serves as the compute substrate for all cognitive work.

**Level 0 - OpenDev (top).** The topmost element is drawn as a dashed-border box with a diamond icon containing only the name "OpenDev." The dashed border indicates that this is an abstract orchestrator, not an active reasoning component. OpenDev does not call LLMs, use tools, or maintain conversation state itself. It manages session lifecycles, provides the user interface, persists state to disk, and routes user input downward into the appropriate session. One instance manages all sessions below it, shown by the three downward branches fanning out from the single box.

**Level 1 - Sessions.** Below OpenDev, three session containers are arranged horizontally: Session A, Session B, and Session N. Sessions A and B have solid borders representing active, fully instantiated sessions. Session N uses a dashed border with ellipsis ("· · ·") to indicate that the number of concurrent sessions is unbounded.

Each session is an **isolated workspace** - its own conversation history, its own context window budget, its own project scope, its own team of agents. Sessions do not share state with each other. A user debugging a backend API in Session A has no interference with a user building a frontend in Session B. Killing a session destroys all its agents. Starting a session creates fresh ones. The session is the fundamental unit of isolation.

The two fully drawn sessions demonstrate that **agent composition varies per session**. Session A contains four agents (Main, Planning, Explorer, SubAgent) - a full team for a complex task. Session B contains three (Main, Explorer, SubAgent) - a leaner configuration where strategic planning isn't needed. Which agents are active depends on the task.

**Level 2 - Agents (inside each session).** Within each session box, multiple agent boxes are stacked vertically. Each agent has a label, a role, its own tool permissions, and its own context window:

- **Main Agent** - present in every session. Full tool access: file editing, command execution, code generation. Drives the core ReAct loop that interacts with the codebase.
- **Planning Agent** - present when strategic decomposition is needed. Restricted to read-only tools - it can read files and search code but cannot modify anything. This constraint makes it safe to let it reason freely without risk of damaging the codebase.
- **Explorer Agent** - spawned for focused codebase search. Fast, lightweight, disposable - created to answer a specific question, then discarded after returning its result to the calling agent.
- **SubAgent (...)** - the ellipsis indicates an open-ended set. Additional specialized agents (web generation, code review, testing) can be spawned on demand. The agent taxonomy is extensible without modifying the core architecture.

Agents within a session can communicate - Main can spawn an Explorer, receive its findings, and continue. But each agent maintains its own context window. The Explorer's raw search results do not pollute Main's context; only the distilled finding crosses the boundary.

**Level 3 - Workflows (inside each agent).** Within each agent box, small rectangular blocks stacked vertically represent cognitive workflows. A workflow is a specific **kind of thinking** - the lowest-level unit of computation where an LLM is actually invoked. Three workflow types appear:

- **Execution** - the ReAct loop. Reason about the next action, call a tool, observe the result, repeat. The only workflow that interacts with the external environment (filesystem, shell, network). Requires a fast, tool-capable model. Appears in nearly every agent.
- **Thinking** - extended reasoning without tool calls. The agent pauses execution to reason deeply: weighing alternatives, synthesizing information, considering edge cases. Benefits from the strongest available model because reasoning depth directly determines output quality. Appears in Main and Planning agents but not in lightweight agents like Explorer.
- **Compact** - context compression. When the context window approaches its limit, this workflow summarizes old history, masks stale tool outputs, and archives the full conversation to disk. A housekeeping task where cheap, fast models are preferred because quality plateaus early. Appears in every agent that accumulates context over multiple turns.

Not every agent contains every workflow. Explorer uses Execution and Compact but not Thinking. Planning uses Thinking and Compact. A SubAgent might use only Execution. An agent is defined by which workflows it contains combined with which tools it can access.

**Workflow-to-LLM binding arrows.** Every workflow block has a rightward dashed arrow (╌╌▶) that exits its agent, exits its session, and terminates at a specific model name. All arrows point into the shared LLM Pool at the bottom. This is the figure's central visual message: **model selection is per-workflow, not per-agent or per-session**.

The arrows demonstrate four properties:

*Many-to-one.* Multiple Execution workflows across different agents and sessions can point to the same model. Both Main Agents bind their Execution to Sonnet 4.6. The model is a shared resource consumed independently by each workflow.

*One-to-many within an agent.* Different workflows within a single agent point to different models. Main Agent uses Sonnet 4.6 for Execution, Opus 4.6 for Thinking, and Qwen 3.5 for Compact - three models, three cost tiers, three capability profiles, one agent.

*Same workflow type, different models across agents.* Main Agent's Execution uses Sonnet 4.6 while Explorer Agent's Execution uses DeepSeek V3.2. The same cognitive primitive is backed by different models depending on the agent's workload.

*Cost gradient.* Frontier models (Opus 4.6) are reserved for Thinking where reasoning quality is critical. Mid-tier models (Sonnet 4.6, DeepSeek V3.2) handle Execution where speed matters. Budget models (Qwen 3.5, GLM 5) handle Compact where the task is mechanical. This gradient emerges naturally from per-workflow binding.

**LLM Pool (bottom).** A large double-bordered box contains eight model names arranged in two rows. The pool is drawn as a single shared resource separate from all sessions and agents to emphasize that **models are not owned by any component** - they are infrastructure. Any workflow, in any agent, in any session, can be configured to use any model in the pool. The pool is open-ended: adding a new model means adding it here and optionally rebinding workflows to use it. No agent code changes. No session code changes. Only configuration.
