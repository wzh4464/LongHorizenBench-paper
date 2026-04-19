# Adaptive Context Compaction

---

## Abstract

In ReAct-based coding agents, tool observations (file contents, command outputs, search results) accumulate across iterations and dominate the context window - typically consuming 70-80% of available tokens. Current systems treat observations as immutable, retaining them at full fidelity until an emergency compaction threshold forces lossy summarization. We propose **Adaptive Context Compaction (ACC)**, a framework that continuously reduces context pressure by applying fidelity reduction strategies of increasing aggressiveness as pressure rises. Three strategies - *fading*, *archival*, and *full compaction* - activate at distinct pressure thresholds, analogous to how biological memory consolidates from working memory to long-term storage. ACC reduces peak context consumption by approximately 50% and in many sessions eliminates the need for emergency compaction entirely.

---

## 1. The Observation Accumulation Problem

A ReAct agent operates in a loop: *reason* about the current state, *act* by calling a tool, *observe* the result, repeat. Each observation appends to the context window sent to the language model on the next iteration.

```
Iteration 1:  [System] [User] [Think] [Act: read_file] [Observe: 500 lines]
Iteration 2:  [System] [User] [Think] [Act: read_file] [Observe: 500 lines] [Think] [Act: edit] [Observe: diff]
Iteration 3:  ...all prior observations still present...
     ⋮
Iteration N:  [System] [User] [O₁] [O₂] [O₃] ... [Oₙ]  ← context window full
```

Two properties make this problematic:

1. **Observations are heavy.** A single `read_file` can produce 2,000-3,000 tokens. A bash command running tests may produce 5,000+. Across 30 tool calls, observations alone consume 45,000-90,000 tokens.

2. **Observations are perishable.** The agent read that file at iteration 3 to understand its structure. By iteration 20, it has already edited the file, run tests, and moved on. The original 500-line content is stale - yet it still occupies the same token budget as when it was fresh.

The standard mitigation is binary compaction: do nothing until the context window reaches a critical threshold (typically 95-99%), then invoke an LLM to summarize the entire middle section of the conversation. This has three failure modes:

- **Late activation.** By the time compaction fires, attention dilution across too many tokens has already degraded performance.
- **Information loss.** Emergency summarization is lossy. File paths, line numbers, error messages, and decision rationale are frequently dropped.
- **Single shot.** The agent gets one compaction event. If context grows back to the threshold, it must re-compact the already-compressed summary, compounding losses.

---

## 2. Fidelity Reduction Strategies

ACC replaces the binary compact/don't-compact decision with three strategies activated by pressure thresholds:

```
                    Context Pressure
      ──────────────────────────────────────────────►

      ┌────────────┐    ┌────────────┐    ┌────────────┐
      │            │    │            │    │            │
      │   ACTIVE   │───►│  FADED     │───►│  ARCHIVED  │
      │            │    │            │    │            │
      └────────────┘    └────────────┘    └────────────┘

      Full content       Compact ref       On disk
      in context         in context         (retrievable)
      ~1500 tokens       ~15 tokens         0 tokens
```

**Active** - The observation is recent and potentially relevant. Full content remains in the message array. This is the default state for the most recent N tool results.

**Faded** - The observation has aged past a recency threshold. Its content is replaced in-place with a minimal reference: `[ref: tool_call_id - see history]`. The message structure is preserved (required by API format), but the payload drops from ~1,500 tokens to ~15.

**Archived** - Observations exceeding a size threshold at birth are written to the filesystem, never entering the context window at full resolution. The agent receives a preview (first ~150 tokens) plus a file path for on-demand retrieval.

Transitions are governed by two dimensions:

- **Age**: observation is N+ tool calls old → in-place content replacement (fading)
- **Size**: observation exceeds S tokens at birth → write-to-disk before insertion (archival)

---

## 3. Architecture

### 3.1 System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                       ReAct Executor                         │
│                                                              │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐  │
│   │  Reason  │──►│   Act    │──►│ Observe  │──►│ Record │  │
│   └──────────┘   └──────────┘   └────┬─────┘   └───┬────┘  │
│                                      │              │        │
│                            ┌─────────▼─────────┐   │        │
│                            │  Size Gate         │   │        │
│                            │  |O| > threshold?  │   │        │
│                            └──┬──────────┬──────┘   │        │
│                          no   │          │  yes      │        │
│                               │          │           │        │
│                               ▼          ▼           │        │
│                          ┌────────┐ ┌─────────┐     │        │
│                          │ Insert │ │ Archive │     │        │
│                          │ full   │ │ to disk,│     │        │
│                          │ into   │ │ insert  │     │        │
│                          │ msgs   │ │ preview │     │        │
│                          └────────┘ └─────────┘     │        │
│                               │          │           │        │
│                               ▼          ▼           │        │
│                          ┌────────────────────┐      │        │
│                          │  Message Array     │      │        │
│                          │  [m₁, m₂, ... mₙ] │      │        │
│                          └─────────┬──────────┘      │        │
│                                    │                 │        │
│              ┌─────────────────────▼──────┐          │        │
│              │  Context Pressure Monitor  │          │        │
│              │  usage = tokens / capacity │          │        │
│              └──────┬────┬────┬────┬──────┘          │        │
│                     │    │    │    │                  │        │
│                < 70%│ 70%│ 80%│ 90%│ 99%             │        │
│                     │    │    │    │                  │        │
│                     ▼    ▼    ▼    ▼                  │        │
│                   none  warn fade  fade    emergency  │        │
│                              (6)   (3)    compaction  │        │
│                                                      │        │
│                          ┌───────────────────────┐   │        │
│                          │   Artifact Registry   │◄──┘        │
│                          │   (survives compact)  │            │
│                          └───────────────────────┘            │
└──────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   LLM API (messages)  │
                    └───────────────────────┘
```

### 3.2 Observation States in the Message Array

```
Messages sent to LLM at iteration 25 of a 30-tool-call session:

 Index  Role       State      Content
 ─────  ────       ─────      ───────
   0    system     ──         System prompt (permanent)
   1    user       ──         User query (permanent)
   2    assistant  ──         Tool call: read_file(config.py)
   3    tool       FADED      [ref: call_01 - see history]                 ← was 1800 tokens
   4    assistant  ──         Tool call: read_file(auth.py)
   5    tool       FADED      [ref: call_02 - see history]                 ← was 2200 tokens
   6    assistant  ──         Tool call: bash(pytest)
   7    tool       ARCHIVED   "PASSED 12 tests...\n[offloaded → file]"    ← was 4000 tokens
   ·    ·          ·          ·
  38    assistant  ──         Tool call: edit_file(routes.py)
  39    tool       ACTIVE     "✓ File edited +3/-1"                        ← full content
  40    assistant  ──         Tool call: bash(pytest)
  41    tool       ACTIVE     "PASSED 15 tests in 2.3s"                    ← full content
  42    assistant  ──         Tool call: read_file(routes.py)
  43    tool       ACTIVE     "1  from flask import...\n2  ..."            ← full content

  Active observations:  6 (recent)     → ~9,000 tokens
  Faded observations:  19 (old)        → ~300 tokens     (was ~28,000)
  Archived at birth:    5 (large)      → ~750 tokens     (was ~15,000)
```

### 3.3 Context Pressure Stages

```
         Context Window Utilization
         ─────────────────────────

  100% ┤ ╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶  Emergency Compaction
       │
   99% ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  COMPACT threshold
       │                                     ╭─╮
   90% ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─╱─ ─╲─ ─  AGGRESSIVE threshold
       │                              ╭────╯     ╰─╮
   80% ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─╱─ ─ ─ ─ ─ ─ ╲  FADE threshold
       │                        ╭───╯               ╰──╮
   70% ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─╱─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╲  WARNING
       │                 ╭───╯                           ╰──
   60% ┤            ╭───╯
       │       ╭───╯            Fading keeps pressure
   50% ┤  ╭───╯                oscillating below 90%
       │ ╱
   40% ┤╱
       │
       ┼─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────►
        it.1  it.5  it.10 it.15 it.20 it.25 it.30 it.35

  Without ACC:  Linear growth → hits 99% → emergency compaction at ~it.30
  With ACC:     Sawtooth pattern → fading sheds tokens → stays below 90%
```

### 3.4 Emergency Compaction (Last Resort)

When fading is insufficient and usage reaches 99%, full compaction activates. ACC enhances the standard compaction pipeline:

```
  ┌─────────────────────────────────────────────────────────┐
  │                  Compaction Pipeline                     │
  │                                                         │
  │  messages = [m₀, m₁, m₂, ... mₖ, ... mₙ₋₄, ... mₙ]   │
  │              ▲       ▲              ▲            ▲      │
  │              │       └──── middle ──┘            │      │
  │             head     (to summarize)             tail    │
  │           (keep)                              (keep)    │
  │                          │                              │
  │              ┌───────────┤                              │
  │              │           │                              │
  │              ▼           ▼                              │
  │     ┌──────────────┐  ┌─────────────────┐              │
  │     │ Pre-Compact  │  │  LLM-Powered    │              │
  │     │ Archive      │  │  Summarization  │              │
  │     │              │  │                 │              │
  │     │ Write full   │  │  Sanitize tool  │              │
  │     │ conversation │  │  results, then  │              │
  │     │ to disk as   │  │  structured     │              │
  │     │ searchable   │  │  summary with   │              │
  │     │ markdown     │  │  template       │              │
  │     └──────┬───────┘  └────────┬────────┘              │
  │            │                   │                        │
  │            ▼                   ▼                        │
  │     ┌────────────┐    ┌──────────────┐                 │
  │     │ archive    │    │ summary_text │                  │
  │     │ _path      │    │              │                  │
  │     └──────┬─────┘    └──────┬───────┘                 │
  │            │                 │                          │
  │            │    ┌────────────┤                          │
  │            │    │            │                          │
  │            │    ▼            │                          │
  │            │  ┌────────────────────────┐                │
  │            │  │   Artifact Registry    │                │
  │            │  │   .as_summary()        │                │
  │            │  │                        │                │
  │            │  │   ## Files Touched     │                │
  │            │  │   - a.py [modified]    │                │
  │            │  │   - b.py [created]     │                │
  │            │  └───────────┬────────────┘                │
  │            │              │                             │
  │            └──────┬───────┘                             │
  │                   │                                     │
  │                   ▼                                     │
  │         ┌──────────────────────┐                        │
  │         │ [CONVERSATION SUMMARY│                        │
  │         │  {LLM summary}      │                        │
  │         │                     │                        │
  │         │  ## Artifact Index   │                        │
  │         │  - a.py [modified]  │                        │
  │         │  - b.py [created]   │                        │
  │         │                     │                        │
  │         │  Archive: {path}]   │                        │
  │         └──────────────────────┘                        │
  │                   │                                     │
  │                   ▼                                     │
  │  result = [head] + [summary_msg] + [tail]              │
  │                                                         │
  └─────────────────────────────────────────────────────────┘
```

The **archive** makes compaction non-destructive - the agent can `read_file` the archive path to recover any detail the summary dropped. The **artifact registry** preserves file-level awareness (which files were touched, how) that evaluation studies identify as the weakest dimension of agent compaction (scoring 2.2-2.5/5.0).

---

## 4. Formal Model

Let $C$ be the context capacity (tokens), $S$ the system prompt, $Q$ the user query, and $O = \{o_1, o_2, \ldots, o_n\}$ the sequence of observations produced by $n$ tool calls.

Context utilization at iteration $k$:

$$U_k = |S| + |Q| + \sum_{i=1}^{k} |o_i| + \sum_{i=1}^{k} |a_i|$$

where $a_i$ is the assistant's reasoning at iteration $i$. Without adaptive compaction, $U_k$ grows monotonically until $U_k > C$.

ACC defines a fidelity function $\phi(o_i, k)$ that reduces the effective size of observation $o_i$ at iteration $k$:

$$\phi(o_i, k) = \begin{cases}
|o_i| & \text{if } k - i < R \text{ (active)} \\
\epsilon & \text{if } k - i \geq R \text{ (faded)} \\
\min(P, |o_i|) & \text{if } |o_i| > T \text{ (archived at birth)}
\end{cases}$$

where $R$ is the recency window (6 or 3 depending on pressure), $\epsilon \approx 15$ tokens is the reference placeholder size, $P \approx 150$ tokens is the archive preview size, and $T$ is the size threshold for archival.

The managed utilization becomes:

$$U_k^{*} = |S| + |Q| + \sum_{i=1}^{k} \phi(o_i, k) + \sum_{i=1}^{k} |a_i|$$

Since $\phi(o_i, k) \leq |o_i|$ for all $i$ and $\phi(o_i, k) = \epsilon \ll |o_i|$ for most $i$ when $k$ is large, $U_k^{*}$ grows sublinearly while $U_k$ grows linearly. The difference $U_k - U_k^{*}$ represents tokens recovered - typically 40-55% of total context at $k = 30$.

---

## 5. Artifact Registry

A separate concern from observation fidelity: the agent must retain awareness of which files it has interacted with, even after observations are faded or compacted away.

```
┌─────────────────────────────────────────────────────────┐
│                    Artifact Registry                     │
│                                                          │
│  ┌──────────────┬────────────────┬──────────────────┐   │
│  │  File Path   │  Operations    │  Last Detail     │   │
│  ├──────────────┼────────────────┼──────────────────┤   │
│  │ src/auth.py  │ read, modified │ +45/-12          │   │
│  │ src/routes.py│ read, modified │ +3/-1            │   │
│  │ tests/test.py│ created        │ 120 lines        │   │
│  │ config.yaml  │ read           │ 30 lines         │   │
│  │ README.md    │ read           │ 80 lines         │   │
│  └──────────────┴────────────────┴──────────────────┘   │
│                                                          │
│  Populated by:  _record_artifact() in ReAct executor    │
│  Consumed by:   compact() → injected into summary       │
│  Survives:      observation fading, full compaction      │
│  Serialized:    to_dict() / from_dict() for persistence  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

The registry is populated incrementally as tool calls execute - `read_file` records a "read", `write_file` records "created", `edit_file` records "modified" with line delta. Multiple operations on the same file merge into a single entry with a combined operation list.

---

## 6. Memory Consolidation Analogy

ACC draws a structural parallel to memory consolidation in cognitive science:

```
  Biological Memory                     Adaptive Context Compaction

  ┌────────────────┐                    ┌────────────────┐
  │  Sensory       │                    │  Tool Output   │
  │  Buffer        │ ← raw stimulus     │  (raw)         │ ← tool execution
  └───────┬────────┘                    └───────┬────────┘
          │ attention gate                      │ size gate
          ▼                                     ▼
  ┌────────────────┐                    ┌────────────────┐
  │  Working       │                    │  Active        │
  │  Memory        │ ← limited capacity │  Observation   │ ← in message array
  │  (7±2 items)   │                    │  (recent N)    │
  └───────┬────────┘                    └───────┬────────┘
          │ rehearsal decay                     │ recency decay
          ▼                                     ▼
  ┌────────────────┐                    ┌────────────────┐
  │  Long-term     │                    │  Faded /       │
  │  Memory        │ ← gist, not exact  │  Archived      │ ← ref pointer,
  │  (retrievable) │                    │  (retrievable) │   not content
  └────────────────┘                    └────────────────┘
```

The key parallels: working memory holds 7±2 items (active observations are limited to the most recent 3-6); long-term memory stores meaning rather than verbatim content (faded observations store the fact that a tool was called, not its output); and archived memories can be recalled with effort (archived observations are retrievable via `read_file` on the scratch path).

---

## 7. Quantitative Impact

For a representative 40-iteration session with 30 tool calls:

```
                    Without ACC          With ACC           Reduction
                    ───────────          ────────           ─────────
  System prompt        3,000               3,000               0%
  User messages        2,000               2,000               0%
  Assistant text       5,000               5,000               0%
  Tool call args      10,000              10,000               0%
  Observations        45,000              10,050              78%
    Active (6)            -                9,000
    Faded (19)            -                  300
    Archived (5)          -                  750
                    ───────────          ────────
  Total               65,000              30,050              54%

  Emergency compactions needed:     1-2               0
  Information loss events:          1-2               0
```

The 78% reduction in observation tokens is the primary driver. This shifts the context budget from observation-dominated to balanced, leaving headroom for longer sessions without quality degradation.

---

## 8. Related Concepts

- **Anchored summarization** (context-compression skill): ACC's compaction injects the artifact registry as an anchor for structured summaries
- **Observation masking** (context-optimization skill): Direct inspiration for the fading mechanism
- **Scratch pad pattern** (filesystem-context skill): Inspiration for output archival to disk
- **Lost-in-middle** (Liu et al. 2024): ACC prevents dilution by removing stale content rather than relying on position
- **KV-cache stability** (context-optimization skill): Faded references are cache-stable (same tokens every iteration)
