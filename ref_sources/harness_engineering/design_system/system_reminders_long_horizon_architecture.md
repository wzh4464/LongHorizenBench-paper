# System Reminders & Long-Horizon Architecture

A diagram-heavy architecture reference covering how OpenDev maintains task quality across long conversations through a 3-tier context architecture: static system prompts, dynamic system reminders, and long-horizon persistence mechanisms.

---

## 1. High-Level Architecture

OpenDev's context architecture is organized into three tiers, each operating at a different timescale and serving a distinct role in maintaining agent coherence.

```mermaid
graph TB
    subgraph Tier1["Tier 1 - Static System Prompt"]
        direction LR
        PC[PromptComposer]
        S1["mode_awareness<br/>priority: 12"]
        S2["security_policy<br/>priority: 15"]
        S3["tone_and_style<br/>priority: 20"]
        S4["no_time_estimates<br/>priority: 25"]
        S5["interaction_pattern<br/>priority: 40"]
        S6["available_tools<br/>priority: 45"]
        S7["tool_selection<br/>priority: 50"]
        S8["code_quality<br/>priority: 55"]
        S9["action_safety<br/>priority: 56"]
        S10["read_before_edit<br/>priority: 58"]
        S11["error_recovery<br/>priority: 60"]
        S12["subagent_guide<br/>priority: 65<br/>⚡ conditional"]
        S13["git_workflow<br/>priority: 70<br/>⚡ conditional"]
        S14["task_tracking<br/>priority: 75<br/>⚡ conditional"]
        S15["output_awareness<br/>priority: 85"]
        S16["scratchpad<br/>priority: 87<br/>⚡ conditional"]
        S17["code_references<br/>priority: 90"]
        S18["system_reminders_note<br/>priority: 95"]
    end

    subgraph Tier2["Tier 2 - Dynamic System Reminders"]
        direction LR
        R1["thinking_trace_reminder"]
        R2["subagent_complete_signal"]
        R3["plan_approved_signal"]
        R4["incomplete_todos_nudge"]
        R5["failed_tool_nudge"]
        R6["consecutive_reads_nudge"]
        R7["tool_denied_nudge"]
        R8["completion_summary_nudge"]
        R9["all_todos_complete_nudge"]
        R10["plan_subagent_request"]
        R11["plan_file_reference"]
        R12["thinking_on_instruction"]
    end

    subgraph Tier3["Tier 3 - Long-Horizon Mechanisms"]
        direction LR
        LH1["Context Compaction"]
        LH2["Session Persistence"]
        LH3["Memory Systems"]
        LH4["Todo Enforcement"]
        LH5["Plan Mode"]
        LH6["ValidatedMessageList"]
    end

    PC -->|"compose(context)"| Tier1
    Tier1 -->|"role: system"| LLM["LLM API Call"]
    Tier2 -->|"role: user<br/>injected at<br/>decision points"| LLM
    Tier3 -->|"preserves context<br/>across turns &<br/>sessions"| LLM

    style Tier1 fill:#1a1a2e,stroke:#e94560,color:#fff
    style Tier2 fill:#16213e,stroke:#0f3460,color:#fff
    style Tier3 fill:#0f3460,stroke:#533483,color:#fff
```

**Tier 1** is assembled once per turn from 18 modular markdown sections. **Tier 2** injects targeted nudges as `role: user` messages at specific decision points within the ReAct loop. **Tier 3** operates across turns and sessions to preserve context beyond the model's context window.

---

## 2. Prompt Composition Pipeline

The system prompt is assembled at runtime by `PromptComposer` from individual markdown template files. Each section has a priority (lower = earlier in the final prompt) and an optional condition predicate.

```mermaid
flowchart LR
    subgraph Templates["templates/system/main/"]
        T1["main-mode-awareness.md"]
        T2["main-security-policy.md"]
        T3["...16 more .md files"]
    end

    subgraph Composer["PromptComposer"]
        REG["register_section()<br/>name, file_path,<br/>condition, priority"]
        FILT["Filter by<br/>condition(ctx)"]
        SORT["Sort by<br/>priority (asc)"]
        STRIP["_load_section()<br/>strip frontmatter<br/>(&lt;!-- ... --&gt;)"]
        JOIN["join with \\n\\n"]
    end

    Templates --> REG
    CTX["Runtime Context<br/>{in_git_repo, has_subagents,<br/>todo_tracking_enabled,<br/>session_id}"] --> FILT
    REG --> FILT --> SORT --> STRIP --> JOIN
    JOIN --> SP["Final System Prompt"]
```

### Priority Bands

```mermaid
graph LR
    subgraph Band1["10-30: Core Identity"]
        B1A["12 mode_awareness"]
        B1B["15 security_policy"]
        B1C["20 tone_and_style"]
        B1D["25 no_time_estimates"]
    end
    subgraph Band2["40-50: Tool Guidance"]
        B2A["40 interaction_pattern"]
        B2B["45 available_tools"]
        B2C["50 tool_selection"]
    end
    subgraph Band3["55-65: Code & Safety"]
        B3A["55 code_quality"]
        B3B["56 action_safety"]
        B3C["58 read_before_edit"]
        B3D["60 error_recovery"]
        B3E["65 subagent_guide ⚡"]
    end
    subgraph Band4["70-95: Conditional & Context"]
        B4A["70 git_workflow ⚡"]
        B4B["75 task_tracking ⚡"]
        B4C["85 output_awareness"]
        B4D["87 scratchpad ⚡"]
        B4E["90 code_references"]
        B4F["95 system_reminders_note"]
    end

    Band1 --> Band2 --> Band3 --> Band4

    style Band1 fill:#2d3436,stroke:#00b894,color:#fff
    style Band2 fill:#2d3436,stroke:#00cec9,color:#fff
    style Band3 fill:#2d3436,stroke:#0984e3,color:#fff
    style Band4 fill:#2d3436,stroke:#6c5ce7,color:#fff
```

Sections marked with ⚡ are conditional - they are only included when their predicate evaluates to `True` against the runtime context dict.

### Variable Substitution Flow

Template files use `${VAR}` placeholders resolved by `PromptRenderer` at render time.

```mermaid
flowchart LR
    TV["PromptVariables<br/>EDIT_TOOL, WRITE_TOOL,<br/>READ_TOOL, BASH_TOOL,<br/>GLOB_TOOL, GREP_TOOL,<br/>EXPLORE_SUBAGENT, ..."]
    RV["Runtime Variables<br/>(**runtime_vars)"]
    TV --> MERGE["to_dict(**runtime_vars)"]
    RV --> MERGE
    MERGE --> REGEX["re.sub(r'\\$\\{([^}]+)\\}',<br/>replace_var, content)"]
    TPL["Template .md<br/>${EDIT_TOOL.name}<br/>${GLOB_TOOL_NAME}"] --> REGEX
    REGEX --> RESOLVED["Resolved Prompt"]
```

---

## 3. System Reminder Lifecycle

System reminders are short, targeted messages injected into the conversation as `role: user` messages. They are stored in `reminders.md` as named sections and retrieved at runtime by `get_reminder()`.

```mermaid
sequenceDiagram
    participant Store as reminders.md<br/>(--- section_name ---)
    participant Parser as _parse_sections()
    participant Cache as Module Cache<br/>(_sections dict)
    participant Caller as ReactExecutor
    participant API as get_reminder(name, **kwargs)
    participant Conv as Conversation<br/>(ctx.messages)
    participant LLM as LLM

    Note over Store: 20+ named sections<br/>delimited by --- markers

    Caller->>API: get_reminder("failed_tool_nudge")
    API->>Cache: lookup "failed_tool_nudge"
    alt Cache miss
        Cache->>Parser: _parse_sections()
        Parser->>Store: read reminders.md
        Store-->>Parser: raw text
        Parser-->>Cache: {name: content} dict
    end
    Cache-->>API: template string
    API->>API: template.format(**kwargs)
    API-->>Caller: formatted reminder
    Caller->>Conv: append({role: "user", content: reminder})
    Conv->>LLM: included in next API call
```

The module-level `_sections` cache ensures `reminders.md` is parsed only once per process lifetime. The `get_reminder()` function also supports fallback to standalone `.txt` template files for longer prompts.

---

## 4. Injection Point Map

Every system reminder injection point within the ReAct loop is annotated below. The loop runs in `ReactExecutor._run_iteration_inner()` (react_executor.py).

```mermaid
flowchart TD
    START(["Iteration Start"]) --> COMPACT["Auto-Compaction Check<br/>_maybe_compact()"]
    COMPACT --> CHK_INT1{"Interrupt?<br/>pre-thinking"}

    CHK_INT1 -->|No| THINK_CHK{"Thinking<br/>visible?"}
    CHK_INT1 -->|Yes| BREAK(["BREAK"])

    THINK_CHK -->|Yes| THINK["Thinking Phase<br/>_get_thinking_trace()"]
    THINK_CHK -->|No| SUBAGENT_CHK

    THINK --> CRITIQUE{"Self-critique<br/>enabled?"}
    CRITIQUE -->|Yes| CRIT["Critique & Refine"]
    CRITIQUE -->|No| INJ1

    CRIT --> INJ1

    INJ1["💉 thinking_trace_reminder<br/>Inject trace as user msg"]

    INJ1 --> SUBAGENT_CHK{"Subagent just<br/>completed?"}
    SUBAGENT_CHK -->|Yes| INJ2["💉 subagent_complete_signal<br/>Nudge to synthesize results"]
    SUBAGENT_CHK -->|No| DRAIN

    INJ2 --> DRAIN["Drain injected<br/>user messages"]

    DRAIN --> CHK_INT2{"Interrupt?<br/>pre-action"}
    CHK_INT2 -->|Yes| BREAK
    CHK_INT2 -->|No| ACTION

    ACTION["Action Phase<br/>call_llm_with_progress()"]

    ACTION --> PARSE["Parse Response"]
    PARSE --> TC_CHK{"Has tool<br/>calls?"}

    TC_CHK -->|No| FAILED_CHK{"Last tool<br/>failed?"}
    FAILED_CHK -->|Yes| INJ3["💉 failed_tool_nudge<br/>Retry after failure"]
    FAILED_CHK -->|No| TODO_CHK1{"Incomplete<br/>todos?"}

    TODO_CHK1 -->|Yes| INJ4["💉 incomplete_todos_nudge<br/>Block premature completion"]
    TODO_CHK1 -->|No| EMPTY_CHK{"Empty<br/>content?"}

    EMPTY_CHK -->|Yes| INJ5["💉 completion_summary_nudge<br/>Request summary"]
    EMPTY_CHK -->|No| DONE(["BREAK - task complete"])

    INJ3 --> CONTINUE(["CONTINUE"])
    INJ4 --> CONTINUE
    INJ5 --> CONTINUE

    TC_CHK -->|Yes| EXEC["Execute Tool Calls"]
    EXEC --> PLAN_CHK{"present_plan<br/>approved?"}
    PLAN_CHK -->|Yes| INJ6["💉 plan_approved_signal<br/>Inject plan + todo list"]
    PLAN_CHK -->|No| TODO_CHK2

    INJ6 --> TODO_CHK2{"All todos<br/>complete?"}
    TODO_CHK2 -->|Yes| INJ7["💉 all_todos_complete_nudge<br/>Signal to call task_complete"]
    TODO_CHK2 -->|No| DENIED_CHK

    INJ7 --> DENIED_CHK{"Tool<br/>denied?"}
    DENIED_CHK -->|Yes| INJ8["💉 tool_denied_nudge<br/>Don't re-attempt same call"]
    DENIED_CHK -->|No| READ_CHK

    INJ8 --> READ_CHK{"5+ consecutive<br/>reads?"}
    READ_CHK -->|Yes| INJ9["💉 consecutive_reads_nudge<br/>Take action, stop exploring"]
    READ_CHK -->|No| PERSIST

    INJ9 --> PERSIST["Persist Step<br/>_persist_step()"]
    PERSIST --> CONTINUE

    style INJ1 fill:#e17055,stroke:#d63031,color:#fff
    style INJ2 fill:#e17055,stroke:#d63031,color:#fff
    style INJ3 fill:#e17055,stroke:#d63031,color:#fff
    style INJ4 fill:#e17055,stroke:#d63031,color:#fff
    style INJ5 fill:#e17055,stroke:#d63031,color:#fff
    style INJ6 fill:#e17055,stroke:#d63031,color:#fff
    style INJ7 fill:#e17055,stroke:#d63031,color:#fff
    style INJ8 fill:#e17055,stroke:#d63031,color:#fff
    style INJ9 fill:#e17055,stroke:#d63031,color:#fff
```

Two additional reminders are injected outside the core loop:

- **plan_subagent_request** - injected by `QueryProcessor` when the user toggles plan mode via `/mode` or `Shift+Tab`
- **plan_file_reference** - injected on session resume when a plan file exists from a prior session

---

## 5. Long-Horizon Quality Architecture

Six mechanisms work together to maintain task quality across long conversations that may span hundreds of turns or multiple sessions.

```mermaid
graph TB
    subgraph Compaction["1. Context Compaction"]
        direction TB
        CT_MON["ContextTokenMonitor<br/>tiktoken estimation"] --> CT_CHK{"usage > 99%<br/>of max_context?"}
        CT_CHK -->|Yes| CT_SAN["Sanitize tool results<br/>(replace with summaries)"]
        CT_SAN --> CT_LLM["LLM-based<br/>summarization"]
        CT_LLM --> CT_MERGE["head[0] + [SUMMARY] + tail[N]"]
        CT_CHK -->|No| CT_SKIP["Skip"]
        CT_API["API prompt_tokens<br/>calibration"] -.->|"replaces<br/>estimate"| CT_MON
    end

    subgraph Persistence["2. Session Persistence"]
        direction TB
        SP_JSON["Session .json<br/>(metadata, messages)"]
        SP_IDX["sessions-index.json<br/>(self-healing cache)"]
        SP_TOPIC["TopicDetector<br/>(background LLM thread)"]
        SP_ADD["add_message()<br/>auto-save every N turns"]
        SP_ADD --> SP_JSON
        SP_TOPIC -.->|"set_title()"| SP_IDX
    end

    subgraph Memory["3. Memory Systems"]
        direction TB
        MEM_SUM["ConversationSummarizer<br/>incremental, 5-msg trigger<br/>excludes last 6 msgs"]
        MEM_PB["Playbook (ACE)<br/>Bullet objects with<br/>helpful/harmful/neutral<br/>effectiveness scoring"]
        MEM_REF["Reflector<br/>LLM-powered outcome analysis"]
        MEM_CUR["Curator<br/>Delta ops: ADD, UPDATE,<br/>TAG, REMOVE"]
        MEM_REF --> MEM_CUR --> MEM_PB
    end

    subgraph TodoEnforce["4. Todo Enforcement"]
        direction TB
        TD_CREATE["create_todo()<br/>status: todo"]
        TD_UPDATE["update_todo()<br/>status: doing<br/>(single active)"]
        TD_DONE["complete_todo()<br/>status: done"]
        TD_GATE{"Completion<br/>gate"}
        TD_CREATE --> TD_UPDATE --> TD_DONE --> TD_GATE
        TD_GATE -->|"incomplete?"| TD_NUDGE["incomplete_todos_nudge<br/>(max 2 nudges)"]
        TD_GATE -->|"all done"| TD_FINISH["all_todos_complete_nudge"]
    end

    subgraph PlanMode["5. Plan Mode"]
        direction TB
        PM_RO["Read-only tool<br/>restriction"]
        PM_EXPLORE["Exploration phase<br/>(PlanningAgent)"]
        PM_PRESENT["present_plan<br/>for approval"]
        PM_EXEC["Execution phase<br/>(MainAgent)"]
        PM_RO --> PM_EXPLORE --> PM_PRESENT --> PM_EXEC
    end

    subgraph VML["6. ValidatedMessageList"]
        direction TB
        VML_SM["State machine:<br/>EXPECT_ANY ↔<br/>EXPECT_TOOL_RESULTS"]
        VML_REPAIR["Auto-repair:<br/>synthetic error results<br/>for orphaned tool calls"]
        VML_LOCK["Thread-safe<br/>(threading.Lock)"]
        VML_SM --> VML_REPAIR
        VML_LOCK -.-> VML_SM
    end

    LLM_CALL["LLM API Call"] --> Compaction
    Compaction --> Persistence
    Memory -.->|"playbook bullets<br/>selected for prompt"| LLM_CALL
    TodoEnforce -->|"nudges block<br/>premature completion"| LLM_CALL
    PlanMode -->|"controls which<br/>tools are available"| LLM_CALL
    VML -->|"enforces message<br/>pair integrity"| LLM_CALL

    style Compaction fill:#2d3436,stroke:#00b894,color:#fff
    style Persistence fill:#2d3436,stroke:#00cec9,color:#fff
    style Memory fill:#2d3436,stroke:#0984e3,color:#fff
    style TodoEnforce fill:#2d3436,stroke:#fdcb6e,color:#000
    style PlanMode fill:#2d3436,stroke:#e17055,color:#fff
    style VML fill:#2d3436,stroke:#6c5ce7,color:#fff
```

---

## 6. Conversation Lifecycle

A complete end-to-end sequence showing how a single turn flows through all three tiers, with annotations showing where each mechanism activates.

```mermaid
sequenceDiagram
    participant User
    participant QP as QueryProcessor
    participant RE as ReactExecutor
    participant CC as ContextCompactor
    participant SM as SessionManager
    participant PC as PromptComposer
    participant Agent
    participant LLM
    participant Tools as ToolRegistry
    participant Todo as TodoHandler
    participant VML as ValidatedMessageList

    User->>QP: user input
    QP->>SM: add_message(user_msg)
    Note over SM: Auto-save every N turns

    QP->>RE: execute(query, messages, agent, ...)
    RE->>VML: Wrap messages in ValidatedMessageList

    loop ReAct Iteration (max 200)
        RE->>RE: _drain_injected_messages()

        RE->>CC: should_compact(messages, system_prompt)?
        alt Usage > 99% of max_context
            CC->>CC: sanitize tool results
            CC->>LLM: summarize middle messages
            LLM-->>CC: summary
            CC->>RE: compacted messages (head + summary + tail)
        end
        Note over RE: Push context_usage_pct to UI

        alt Thinking visible & not post-subagent
            RE->>Agent: build_system_prompt(thinking_visible=True)
            Agent->>PC: compose(context)
            PC-->>Agent: thinking system prompt
            RE->>LLM: thinking call (no tools)
            LLM-->>RE: thinking trace
            RE->>RE: 💉 thinking_trace_reminder
        end

        alt Subagent just completed
            RE->>RE: 💉 subagent_complete_signal
        end

        RE->>Agent: build_system_prompt()
        Agent->>PC: compose(context)
        PC-->>Agent: action system prompt
        RE->>LLM: action call (with tools)
        LLM-->>RE: response (content + tool_calls)

        Note over RE: Calibrate compactor with API prompt_tokens

        alt No tool calls
            alt Last tool failed
                RE->>RE: 💉 failed_tool_nudge → CONTINUE
            else Incomplete todos
                RE->>RE: 💉 incomplete_todos_nudge → CONTINUE
            else Empty content
                RE->>RE: 💉 completion_summary_nudge → CONTINUE
            else Has content
                RE->>SM: add_message(assistant_msg)
                Note over RE: BREAK
            end
        else Has tool calls
            RE->>VML: append(assistant + tool_calls)
            Note over VML: Enter EXPECT_TOOL_RESULTS

            loop For each tool call
                RE->>Tools: execute_tool(name, args)
                Tools-->>RE: result
                RE->>VML: append(tool result)
                Note over VML: Discard from pending set
            end

            alt present_plan approved
                RE->>RE: 💉 plan_approved_signal
            end
            alt All todos complete
                RE->>Todo: has_incomplete_todos()?
                Todo-->>RE: false
                RE->>RE: 💉 all_todos_complete_nudge
            end
            alt Tool denied
                RE->>RE: 💉 tool_denied_nudge
            end
            alt 5+ consecutive reads
                RE->>RE: 💉 consecutive_reads_nudge
            end

            RE->>SM: add_message(assistant_msg + tool_calls)
            Note over RE: CONTINUE
        end
    end

    RE->>SM: save_session() (final flush)
```

---

## 7. Context Budget Architecture

The context budget determines when compaction fires and how much of the conversation is preserved.

```mermaid
graph TB
    subgraph Window["Model Context Window"]
        direction TB
        FULL["Full context window<br/>(e.g., 128K tokens)"]
        MAX["max_context_tokens<br/>= 80% of window<br/>(e.g., 102,400)"]
        THRESH["Compaction threshold<br/>= 99% of max_context<br/>(e.g., 101,376)"]
    end

    subgraph Budget["Token Budget Allocation"]
        direction TB
        SYS["System Prompt<br/>(Tier 1 sections)"]
        HIST["Conversation History"]
        SUMM["Compacted Summary Region<br/>[CONVERSATION SUMMARY]"]
        RECENT["Recent Messages<br/>min(5, max(2, len/3))"]
        RESP["Response Headroom<br/>20% of window<br/>(reserved, not counted)"]
    end

    FULL --> MAX
    MAX --> THRESH

    subgraph Counting["Token Counting Strategy"]
        direction LR
        TIKT["tiktoken estimate<br/>(initial)"]
        API_CAL["API prompt_tokens<br/>(calibration after<br/>first response)"]
        DELTA["Delta counting<br/>(new msgs since<br/>calibration)"]
        TIKT -->|"replaced by"| API_CAL
        API_CAL -->|"+ delta for<br/>new messages"| DELTA
    end

    Counting -->|"total tokens"| THRESH
    THRESH -->|"exceeded?"| TRIGGER["Trigger Compaction"]
    TRIGGER --> COMPACT_FLOW

    subgraph COMPACT_FLOW["Compaction Flow"]
        direction TB
        HEAD["head = messages[:1]<br/>(system message)"]
        MIDDLE["middle = messages[1:-N]<br/>(to be summarized)"]
        TAIL["tail = messages[-N:]<br/>(preserved recent)"]
        SAN["Sanitize tool results<br/>(truncate to 200 chars)"]
        LLM_SUM["LLM summarization<br/>(compact model or fallback)"]
        RESULT["[head] + [summary_msg] + [tail]"]
        MIDDLE --> SAN --> LLM_SUM --> RESULT
        HEAD --> RESULT
        TAIL --> RESULT
    end

    style Window fill:#2d3436,stroke:#00b894,color:#fff
    style Budget fill:#2d3436,stroke:#0984e3,color:#fff
    style Counting fill:#2d3436,stroke:#fdcb6e,color:#000
    style COMPACT_FLOW fill:#2d3436,stroke:#e17055,color:#fff
```

After compaction, the API calibration state is invalidated (`_api_prompt_tokens = 0`) so the next turn falls back to tiktoken estimation until a new API response provides fresh calibration.

---

## 8. Key Files Reference

| Mechanism | Source File | Key Lines/Classes |
|---|---|---|
| **PromptComposer** | `core/agents/prompts/composition.py` | `PromptComposer`, `create_default_composer()` (18 sections registered) |
| **PromptRenderer** | `core/agents/prompts/renderer.py` | `PromptRenderer.render()` - `${VAR}` substitution |
| **PromptVariables** | `core/agents/prompts/variables.py` | `PromptVariables` - tool refs, agent config |
| **Template Loader** | `core/agents/prompts/loader.py` | `load_prompt()`, `load_tool_description()`, frontmatter stripping |
| **System Reminders** | `core/agents/prompts/reminders.py` | `get_reminder()` - section parser + module cache |
| **Reminder Templates** | `core/agents/prompts/templates/reminders.md` | 20+ named sections (nudges, signals, instructions) |
| **ReAct Executor** | `repl/react_executor.py` | `ReactExecutor._run_iteration_inner()` - all injection points |
| **Context Compactor** | `core/context_engineering/compaction.py` | `ContextCompactor` - 99% threshold, sanitize, LLM summarize |
| **Token Monitor** | `core/context_engineering/retrieval/token_monitor.py` | `ContextTokenMonitor` - tiktoken-based estimation |
| **Session Manager** | `core/context_engineering/history/session_manager.py` | `SessionManager` - JSON persistence, self-healing index |
| **Topic Detector** | `core/context_engineering/history/topic_detector.py` | `TopicDetector` - background LLM thread for session titles |
| **Conversation Summarizer** | `core/context_engineering/memory/conversation_summarizer.py` | `ConversationSummarizer` - incremental, 5-msg trigger |
| **Playbook (ACE)** | `core/context_engineering/memory/playbook.py` | `Playbook`, `Bullet` - effectiveness-scored strategy store |
| **Reflector / Curator** | `core/context_engineering/memory/roles.py` | `Reflector`, `Curator` - LLM-powered learning loop |
| **Todo Handler** | `core/context_engineering/tools/handlers/todo_handler.py` | `TodoHandler` - todo/doing/done lifecycle, completion gate |
| **Mode Manager** | `core/runtime/mode_manager.py` | `ModeManager` - NORMAL/PLAN mode, plan storage |
| **ValidatedMessageList** | `core/context_engineering/validated_message_list.py` | State machine, auto-repair orphaned tool calls |
| **Prompt Templates** | `core/agents/prompts/templates/system/main/*.md` | 18 modular sections (see Section 2 priority bands) |
