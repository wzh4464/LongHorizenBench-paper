# Agentic Context Engineering (ACE): Architecture Reference

**Version**: 1.0
**Last Updated**: 2026-03-04
**Scope**: Complete architecture of the ACE memory/learning subsystem

---

## Key Source Files

**Core ACE module** (`swecli/core/context_engineering/memory/`):

- `__init__.py`: Public API, re-exports all ACE components
- `playbook.py`: Bullet and Playbook data structures, CRUD, serialization
- `delta.py`: DeltaOperation and DeltaBatch mutation types
- `roles.py`: LLM-powered Reflector and Curator roles
- `selector.py`: BulletSelector hybrid retrieval (effectiveness + recency + semantic)
- `embeddings.py`: EmbeddingCache, cosine similarity, batch embedding generation
- `conversation_summarizer.py`: Incremental episodic memory via ConversationSummarizer
- `reflection/reflector.py`: Rule-based ExecutionReflector (no API calls)

**Integration files**:

- `swecli/repl/tool_executor.py`: `record_tool_learnings()` 4-step ACE workflow
- `swecli/repl/query_processor.py`: Lazy ACE init, delegates to ContextPicker and ToolExecutor
- `swecli/models/session.py`: `playbook` field, `get_playbook()` / `update_playbook()`
- `swecli/core/context_engineering/context_picker/picker.py`: `_pick_playbook_strategies()` injects bullets into system prompt

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Data Model](#2-data-model)
3. [Reflector (LLM-Powered Analysis)](#3-reflector-llm-powered-analysis)
4. [Curator (LLM-Powered Mutation Planning)](#4-curator-llm-powered-mutation-planning)
5. [ExecutionReflector (Rule-Based Pattern Extraction)](#5-executionreflector-rule-based-pattern-extraction)
6. [BulletSelector (Hybrid Retrieval)](#6-bulletselector-hybrid-retrieval)
7. [EmbeddingCache](#7-embeddingcache)
8. [ConversationSummarizer (Episodic Memory)](#8-conversationsummarizer-episodic-memory)
9. [Integration Architecture](#9-integration-architecture)
10. [Graceful Degradation & Error Handling](#10-graceful-degradation--error-handling)
11. [Configuration & Tuning](#11-configuration--tuning)
12. [Limitations & Future Work](#12-limitations--future-work)

---

## 1. System Overview

ACE (Agentic Context Engineering) is the memory and learning subsystem within OpenDev. It replaces raw conversation history with a curated **playbook** of strategy bullets that evolve based on execution feedback. The design draws from the ACE paper ([arXiv:2510.04618](https://arxiv.org/abs/2510.04618)).

### Architecture Diagram

```
 ┌─────────────────────────────────────────────────────────────────┐
 │                        ReAct Loop                               │
 │                                                                 │
 │  Phase 1: Pick Context          Phase 2: Reason & Act          │
 │  ┌──────────────────┐           ┌──────────────────┐           │
 │  │  ContextPicker    │           │  Main Agent       │           │
 │  │  ┌──────────────┐ │  inject   │  (Generator)      │           │
 │  │  │ BulletSelector├─┼─────────►│  System prompt +   │           │
 │  │  │ (top-K)      │ │ bullets   │  playbook bullets  │           │
 │  │  └──────┬───────┘ │           └────────┬─────────┘           │
 │  │         │         │                    │                     │
 │  │    Playbook       │                    │ tool calls          │
 │  │    (read)         │                    ▼                     │
 │  └──────────────────┘           ┌──────────────────┐           │
 │                                 │  Tool Execution   │           │
 │                                 └────────┬─────────┘           │
 │                                          │                     │
 │  Phase 4: Persist & Learn       Phase 3: Observe               │
 │  ┌──────────────────┐           ┌──────────────────┐           │
 │  │  Curator           │◄──────── │  Reflector         │           │
 │  │  (LLM-powered)     │ analysis │  (LLM-powered)     │           │
 │  │                    │          │                    │           │
 │  │  DeltaBatch:       │          │  ReflectorOutput:  │           │
 │  │  ADD / UPDATE /    │          │  reasoning, tags,  │           │
 │  │  TAG / REMOVE      │          │  root cause,       │           │
 │  │         │          │          │  key insight       │           │
 │  │         ▼          │          └──────────────────┘           │
 │  │    Playbook        │                                         │
 │  │    (write)         │                                         │
 │  │         │          │                                         │
 │  │         ▼          │                                         │
 │  │    Session.update  │                                         │
 │  │    _playbook()     │                                         │
 │  └──────────────────┘                                           │
 └─────────────────────────────────────────────────────────────────┘
```

### The 4-Role Pipeline

1. **Generator**: The main agent itself (uses `agent_normal.txt` system prompt). Produces answers using playbook strategies injected into context.
2. **Reflector**: LLM-powered analysis of what the Generator did. Classifies playbook bullets as helpful/harmful/neutral. Extracts root cause analysis and key insights.
3. **Curator**: LLM-powered mutation planner. Reads the Reflector's output and decides how to evolve the playbook (add, update, tag, or remove bullets).
4. **Playbook**: The persistent data store. A curated collection of strategy bullets with effectiveness counters. Serialized to session JSON.

### Design Rationale

Why playbook bullets instead of raw history?

- **Bounded growth**: Bullets are a fixed-size structure (capped by K=30 selection). Raw history grows linearly with conversation length.
- **Reusable knowledge**: A bullet like "Run tests after code changes" is reusable across queries. A raw conversation turn is not.
- **Effectiveness tracking**: Each bullet has helpful/harmful/neutral counters. The system learns which strategies work and which don't, without human intervention.
- **Semantic retrieval**: Bullets can be scored by query relevance. Raw history requires expensive summarization or full-context inclusion.

---

## 2. Data Model

### Bullet (dataclass)

Source: `playbook.py:18-48`

```python
@dataclass
class Bullet:
    id: str          # e.g., "file-00001"
    section: str     # e.g., "file_operations"
    content: str     # Strategy text
    helpful: int     # Times marked helpful
    harmful: int     # Times marked harmful
    neutral: int     # Times marked neutral
    created_at: str  # ISO 8601 UTC timestamp
    updated_at: str  # ISO 8601 UTC timestamp
```

**ID generation** (`playbook.py:344-348`): `{section_prefix}-{sequence:05d}` where `section_prefix` is the first word of the section name, lowercased. Example: section "file_operations" → prefix "file" → ID "file-00003".

**Tagging** (`playbook.py:41-47`): The `tag()` method increments one of the three counters (helpful, harmful, neutral) and updates `updated_at`.

### Playbook (class)

Source: `playbook.py:50-354`

Internal state:

- `_bullets: Dict[str, Bullet]`: bullet_id to Bullet mapping
- `_sections: Dict[str, List[str]]`: section_name to list of bullet_ids
- `_next_id: int`: auto-incrementing counter for ID generation

**CRUD operations**:

- `add_bullet(section, content, bullet_id?, metadata?)` → Bullet
- `update_bullet(bullet_id, content?, metadata?)` → Optional[Bullet]
- `tag_bullet(bullet_id, tag, increment=1)` → Optional[Bullet]
- `remove_bullet(bullet_id)` → None
- `get_bullet(bullet_id)` → Optional[Bullet]
- `bullets()` → List[Bullet]

**Serialization** (`playbook.py:143-197`):

- `to_dict()` / `from_dict(payload)`: Dict conversion
- `dumps()` / `loads(data)`: JSON string conversion
- `save_to_file(path)` / `load_from_file(path)`: File persistence

Example JSON:

```json
{
  "bullets": {
    "file-00001": {
      "id": "file-00001",
      "section": "file_operations",
      "content": "Read file before writing to preserve important data",
      "helpful": 3,
      "harmful": 0,
      "neutral": 1,
      "created_at": "2026-03-01T10:00:00+00:00",
      "updated_at": "2026-03-04T14:30:00+00:00"
    }
  },
  "sections": {
    "file_operations": ["file-00001"]
  },
  "next_id": 1
}
```

**Presentation** (`playbook.py:245-327`):

- `as_prompt()`: Returns ALL bullets formatted for LLM context (no selection)
- `as_context(query?, max_strategies=30, ...)`: Uses BulletSelector for intelligent top-K selection
- `stats()`: Returns section count, bullet count, and aggregate tag totals

### DeltaOperation (dataclass)

Source: `delta.py:16-55`

```python
@dataclass
class DeltaOperation:
    type: OperationType   # "ADD" | "UPDATE" | "TAG" | "REMOVE"
    section: str          # Target section name
    content: Optional[str]     # New/updated content (ADD, UPDATE)
    bullet_id: Optional[str]   # Target bullet (UPDATE, TAG, REMOVE)
    metadata: Dict[str, int]   # Counter values (TAG: {"helpful": 1})
```

**Operation types**:

- **ADD**: Creates a new bullet in the specified section. `content` required.
- **UPDATE**: Modifies content or metadata of an existing bullet. `bullet_id` required.
- **TAG**: Increments counters on an existing bullet. `bullet_id` + `metadata` required. Only `helpful`, `harmful`, `neutral` keys accepted.
- **REMOVE**: Deletes a bullet from the playbook. `bullet_id` required.

### DeltaBatch (dataclass)

Source: `delta.py:58-81`

```python
@dataclass
class DeltaBatch:
    reasoning: str                        # Curator's reasoning for changes
    operations: List[DeltaOperation]      # Ordered list of mutations
```

**Parsing** (`delta.py:66-74`): `DeltaBatch.from_json(payload)` iterates `payload["operations"]` and creates `DeltaOperation` instances via `DeltaOperation.from_json()`.

**Application** (`playbook.py:202-240`): `Playbook.apply_delta(delta)` dispatches each operation by type: ADD calls `add_bullet()`, UPDATE calls `update_bullet()`, TAG calls `tag_bullet()`, REMOVE calls `remove_bullet()`.

---

## 3. Reflector (LLM-Powered Analysis)

Source: `roles.py:95-199`

The Reflector analyzes the main agent's response to extract lessons and classify playbook bullets.

### Initialization

```python
Reflector(
    llm_client,                    # swecli's AnyLLMClient
    prompt_template=None,          # Override with custom prompt
    max_retries=3,                 # JSON parsing retry limit
    retry_prompt=None,             # Custom retry hint
)
```

- **Prompt**: Loaded via `load_prompt("memory/reflector_prompt")` from `templates/memory/reflector_prompt.md`
- **Retry prompt**: Loaded via `get_reminder("json_retry_simple")`

### Input

The `reflect()` method (`roles.py:126-199`) takes:

- `question`: The user's original query
- `agent_response`: AgentResponse(content, reasoning, tool_calls). Content is **truncated to 1000 chars** (`roles.py:150`)
- `playbook`: Current Playbook instance (formatted via `as_prompt()`)
- `ground_truth`: Optional known-correct answer
- `feedback`: Optional external feedback

### Prompt Construction

The base prompt is assembled by formatting the template with:

```
question, agent_response (truncated), tool_summary, ground_truth, feedback, playbook_content
```

Tool summary is derived from `agent_response.tool_calls`, just tool names joined by commas, or "No tools used".

### Output

`ReflectorOutput` (`roles.py:75-83`):

```
reasoning                Step-by-step analysis
error_identification     What went wrong (if anything)
root_cause_analysis      Why it went wrong
correct_approach         What should have been done
key_insight              Distilled lesson
bullet_tags              List[BulletTag(id, tag)] classifying existing bullets
```

**Bullet tags** are parsed from the JSON response's `bullet_tags` array. Each entry must have `id` (string) and `tag` (string, lowercased). These are later applied to the playbook via `tag_bullet()`.

### JSON Retry Loop

```
for attempt in range(3):
    try:
        response = llm_client.chat_completion(messages)
        data = _safe_json_loads(response_text)     # strips ```json fences
        return ReflectorOutput(...)
    except ValueError:
        prompt = base_prompt + retry_prompt         # append hint
```

The `_safe_json_loads()` helper (`roles.py:20-47`) strips markdown code fences (`\`\`\`json ... \`\`\``) before parsing. It also detects truncated JSON (mismatched braces) and raises a specific error.

If all 3 attempts fail, raises `RuntimeError("Reflector failed to produce valid JSON.")`.

---

## 4. Curator (LLM-Powered Mutation Planning)

Source: `roles.py:203-272`

The Curator transforms Reflector analysis into concrete playbook mutations.

### Initialization

```python
Curator(
    llm_client,                    # swecli's AnyLLMClient
    prompt_template=None,          # Override with custom prompt
    max_retries=3,                 # JSON parsing retry limit
    retry_prompt=None,             # Custom retry hint
)
```

- **Prompt**: Loaded via `load_prompt("memory/curator_prompt")` from `templates/memory/curator_prompt.md`
- **Retry prompt**: Loaded via `get_reminder("json_retry_with_fields")`

### Input

The `curate()` method (`roles.py:234-271`) takes:

- `reflection`: ReflectorOutput from the previous step
- `playbook`: Current Playbook instance
- `question_context`: The original user query
- `progress`: Counter string (e.g., "Query #5") tracking how many learning cycles have occurred

### Prompt Construction

The base prompt is formatted with:

```
progress, stats (JSON of playbook.stats()), reflection (JSON of reflection.raw),
playbook (as_prompt()), question_context
```

### Output

`CuratorOutput` (`roles.py:87-90`):

```
delta      DeltaBatch with reasoning + list of DeltaOperation
raw        Raw JSON dict from LLM response
```

The DeltaBatch is parsed via `DeltaBatch.from_json(data)`. The caller then applies it: `playbook.apply_delta(curator_output.delta)`.

### JSON Retry Loop

Same pattern as Reflector: 3 attempts, appending `json_retry_with_fields` reminder on failure. Falls through to `RuntimeError("Curator failed to produce valid JSON.")`.

---

## 5. ExecutionReflector (Rule-Based Pattern Extraction)

Source: `reflection/reflector.py:33-341`

The ExecutionReflector is **complementary** to the LLM-powered Reflector. It runs **without API calls**, using heuristic pattern matching on tool execution sequences.

### Design

```
ExecutionReflector(
    min_tool_calls=2,        # Minimum tool calls to trigger analysis
    min_confidence=0.6,      # Minimum confidence threshold for results
)
```

### Reflection Pipeline

```python
def reflect(query, tool_calls, outcome="success") -> Optional[ReflectionResult]:
    if not _is_worth_learning(tool_calls, outcome):
        return None
    result = (
        _extract_file_operation_pattern(tool_calls, query)
        or _extract_code_navigation_pattern(tool_calls, query)
        or _extract_testing_pattern(tool_calls, query)
        or _extract_shell_command_pattern(tool_calls, query)
        or _extract_error_recovery_pattern(tool_calls, query, outcome)
    )
    if result and result.confidence >= min_confidence:
        return result
    return None
```

**Worth-learning gate** (`reflection/reflector.py:99-123`):

- Single trivial operations (lone `read_file` or `list_files`) are skipped
- Multi-step sequences (>= `min_tool_calls`) pass
- Error outcomes with any tool calls pass

### ReflectionResult (dataclass)

```python
@dataclass
class ReflectionResult:
    category: str       # e.g., "file_operations", "testing", "error_handling"
    content: str        # Distilled strategy text
    confidence: float   # 0.0 to 1.0
    reasoning: str      # Why this pattern is worth learning
```

### Pattern Extractors

**File operations** (`reflection/reflector.py:125-171`):

```
Pattern                  Confidence   Example
─────────────────────── ────────── ──────────────────────────────────
list_files → read_file   0.75        "List directory before reading files"
read_file → write_file   0.80        "Read file before writing to preserve data"
3+ read_file calls       0.70        "Read multiple related files for context"
```

**Code navigation** (`reflection/reflector.py:173-206`):

```
Pattern                  Confidence   Example
─────────────────────── ────────── ──────────────────────────────────
search → read_file       0.80        "Search before reading for targeted access"
2+ search calls          0.70        "Multiple searches for thorough exploration"
```

**Testing** (`reflection/reflector.py:208-255`):

```
Pattern                  Confidence   Example
─────────────────────── ────────── ──────────────────────────────────
write/edit → test run    0.85        "Run tests after code changes"
read test → test run     0.70        "Review tests before running them"
```

**Shell commands** (`reflection/reflector.py:257-307`):

```
Pattern                  Confidence   Example
─────────────────────── ────────── ──────────────────────────────────
install → run/test       0.80        "Install dependencies before running"
git status → git ops     0.75        "Check status before git operations"
```

**Error recovery** (`reflection/reflector.py:309-341`):

```
Pattern                  Confidence   Example
─────────────────────── ────────── ──────────────────────────────────
read_file + error        0.70        "List directory to verify file exists"
run_command + error      0.65        "Verify environment before retrying"
```

---

## 6. BulletSelector (Hybrid Retrieval)

Source: `selector.py:26-318`

The BulletSelector implements intelligent top-K bullet selection using three scoring factors.

### Initialization

```python
BulletSelector(
    weights={"effectiveness": 0.5, "recency": 0.3, "semantic": 0.2},
    embedding_model="text-embedding-3-small",
    cache_file=None,    # Path for persistent embedding cache
)
```

### Selection Flow

```python
def select(bullets, max_count=30, query=None) -> List[Bullet]:
    if len(bullets) <= max_count:
        return bullets                        # Short-circuit
    if query and weights["semantic"] > 0:
        _batch_generate_embeddings(query, bullets)  # N+1 → 1 API call
    scored = [_score_bullet(b, query) for b in bullets]
    scored.sort(key=score, reverse=True)
    return [sb.bullet for sb in scored[:max_count]]
```

After selection completes, the embedding cache is saved to disk (if `cache_file` is set). Failures are silently ignored.

### Scoring Factors

**Final score** = `0.5 × effectiveness + 0.3 × recency + 0.2 × semantic`

#### Effectiveness Score (weight: 0.5)

Source: `selector.py:194-220`

```
effectiveness = (helpful × 1.0 + neutral × 0.5 + harmful × 0.0) / total
```

- Untested bullets (total = 0) → 0.5 (neutral, neither promoted nor demoted)
- All-helpful bullets → 1.0
- All-harmful bullets → 0.0
- Mixed → proportional

Example:

```
helpful=3, neutral=1, harmful=0 → (3.0 + 0.5 + 0.0) / 4 = 0.875
helpful=0, neutral=0, harmful=2 → (0.0 + 0.0 + 0.0) / 2 = 0.000
helpful=0, neutral=0, harmful=0 → 0.500 (untested)
```

#### Recency Score (weight: 0.3)

Source: `selector.py:222-252`

```
recency = 1.0 / (1.0 + days_old × 0.1)
```

Decay curve:

```
Days old    Score
──────────  ─────
0           1.000
1           0.909
3           0.769
7           0.588
14          0.417
30          0.250
60          0.143
90          0.100
```

If `updated_at` cannot be parsed → returns 0.5 (neutral).

#### Semantic Score (weight: 0.2)

Source: `selector.py:254-290`

```
raw_similarity = cosine_similarity(query_embedding, bullet_embedding)
semantic = (raw_similarity + 1.0) / 2.0    # normalize [-1,1] → [0,1]
```

- Uses EmbeddingCache for efficient lookups
- Falls back to 0.5 if embedding generation fails

### Batch Embedding Optimization

Source: `selector.py:112-153`

Before scoring, `_batch_generate_embeddings()` collects all cache-missing texts (query + bullet contents) and generates them in a **single API call** via `EmbeddingCache.batch_get_or_generate()`. This reduces API calls from N+1 to 1.

If batch generation fails, individual generation happens naturally in `_semantic_score()`.

### Selection Stats

Source: `selector.py:292-318`

`get_selection_stats(bullets, selected)` returns:

```python
{
    "total_bullets": 50,
    "selected_bullets": 30,
    "selection_rate": 0.6,
    "avg_all_score": 0.42,
    "avg_selected_score": 0.67,
    "score_improvement": 0.25,
}
```

---

## 7. EmbeddingCache

Source: `embeddings.py:51-267`

### Cache Key

Source: `embeddings.py:255-266`

```python
key = SHA256(f"{model}:{text}")[:16]    # 16-char hex prefix
```

### Storage

- **In-memory**: `Dict[str, EmbeddingMetadata]` mapping cache_key → metadata
- **On-disk**: JSON file with model name and full cache contents

### Core Operations

- `get(text, model?)` returns Optional[List[float]]: Cache lookup
- `set(text, embedding, model?)`: Cache store
- `get_or_generate(text, model?, generator?)` returns List[float]: Cache-through with fallback to generator
- `batch_get_or_generate(texts, model?, generator?)` returns List[List[float]]: Batch cache-through

**Batch optimization** (`embeddings.py:129-169`): Checks cache for each text. Collects cache misses. Calls generator once for all misses. Caches results.

### Persistence

- `save_to_file(path)`: Writes JSON to disk, creates parent directories
- `load_from_file(path)` returns Optional[EmbeddingCache]: Returns None if file missing or corrupted

### Embedding Generation

Source: `embeddings.py:336-379`

```python
def generate_embeddings(texts, model="text-embedding-3-small", provider="openai"):
    from any_llm import embedding
    response = embedding(model=model, inputs=texts, provider=provider)
    return [item.embedding for item in response.data]
```

**Fallback**: If `any_llm.embedding()` fails (import error, API error, etc.), returns **random vectors** of dimension 1536. This allows the system to keep functioning; semantic scores will be meaningless but effectiveness and recency scores still work.

### Similarity Functions

Source: `embeddings.py:269-333`

- `cosine_similarity(vec1, vec2)` returns float in [-1.0, 1.0]. Uses numpy for efficiency. Returns 0.0 if either vector has zero norm.
- `batch_cosine_similarity(query_vec, vectors)` returns List[float]. Vectorized numpy operation for computing similarity against multiple vectors in one pass.

---

## 8. ConversationSummarizer (Episodic Memory)

Source: `conversation_summarizer.py`

The ConversationSummarizer provides **episodic memory** through incremental LLM-generated conversation summaries. It complements the playbook (which stores distilled strategies) by maintaining a running narrative of what happened in the session.

### Design

```python
ConversationSummarizer(
    regenerate_threshold=5,    # Regenerate after N new messages
    max_summary_length=500,    # Max chars in summary
    exclude_last_n=6,          # Keep last 6 messages as working memory
)
```

### Incremental Summarization

Source: `conversation_summarizer.py:54-127`

```
┌─────────────────────────────────────────────────┐
│               Full Message History                │
│                                                   │
│  [msg 0] [msg 1] ... [msg N-7] │ [msg N-6] ... [msg N]
│  ──────────────────────────────┼──────────────────
│  Already summarized  │  New    │  Working memory
│                      │  msgs   │  (excluded)
│                      │         │
│  ◄── previous ──►    │◄─new──►│◄── exclude_last_n ──►
│       summary        │  batch  │
└─────────────────────────────────────────────────┘
```

The `generate_summary()` method:

1. Filters out system messages
2. Calculates `end_index = len(filtered) - exclude_last_n`
3. Extracts new messages since `last_summarized_index`
4. Builds prompt with `previous_summary` + `new_messages`
5. Calls LLM to produce merged summary
6. Truncates to `max_summary_length` (500 chars)
7. Caches result with updated `last_summarized_index`

**Trigger**: `needs_regeneration(current_message_count)` returns True when `current_count - cached_count >= regenerate_threshold` (5 messages).

### Message Formatting

Source: `conversation_summarizer.py:129-149`

Messages are formatted for the summarization prompt:

- User messages: `"User: {content[:200]}"`
- Assistant with tools: `"Assistant: [Called tools: tool1, tool2]"`
- Assistant with text: `"Assistant: {content[:200]}"`
- Tool results: `"Tool: [result received]"` (output omitted to save tokens)

### Session Persistence

- `to_dict()` → serializes `{summary, message_count, last_summarized_index}`
- `load_from_dict(data)` → restores `ConversationSummary` from dict

---

## 9. Integration Architecture

### End-to-End Data Flow

```
User Query
    │
    ▼
QueryProcessor.process_query()
    │
    ├──► ContextPicker.pick_context()
    │       │
    │       └──► _pick_playbook_strategies(query)
    │               │
    │               ├── session.get_playbook()
    │               │       └── Playbook.from_dict(session.playbook)
    │               │
    │               └── playbook.as_context(query, max_strategies=30)
    │                       └── BulletSelector.select(bullets, max_count, query)
    │                               ├── _batch_generate_embeddings()
    │                               ├── _score_bullet() × N
    │                               └── return top-K bullets
    │
    │   [Selected bullets injected into system prompt]
    │   "## Learned Strategies\n{strategies_content}"
    │
    ├──► ReactExecutor.execute()
    │       │
    │       ├── LLM call (system prompt includes playbook bullets)
    │       ├── Tool execution
    │       └── _record_agent_response(content, tool_calls)
    │               └── tool_executor.set_last_agent_response(...)
    │
    └──► ToolExecutor.record_tool_learnings(query, tool_calls, outcome, agent)
            │
            ├── Step 1: Get playbook
            │       session.get_playbook()
            │
            ├── Step 2: Reflect
            │       reflector.reflect(question, agent_response, playbook, feedback)
            │       └── LLM call → ReflectorOutput
            │
            ├── Step 3: Apply bullet tags
            │       for tag in reflection.bullet_tags:
            │           playbook.tag_bullet(tag.id, tag.tag)
            │
            ├── Step 4: Curate
            │       curator.curate(reflection, playbook, query, progress)
            │       └── LLM call → CuratorOutput with DeltaBatch
            │
            ├── Step 5: Apply delta
            │       playbook.apply_delta(curator_output.delta)
            │
            └── Step 6: Persist
                    session.update_playbook(playbook)
```

### QueryProcessor Lazy Initialization

Source: `query_processor.py:232-249`

ACE components (Reflector and Curator) are initialized lazily on first use:

```python
def _init_ace_components(self, agent):
    if self._ace_reflector is None:
        try:
            self._ace_reflector = Reflector(agent.client)
            self._ace_curator = Curator(agent.client)
        except Exception:
            pass    # Silently skip; learning disabled
```

This avoids initialization overhead when ACE is not needed (e.g., simple queries that don't trigger tool execution).

### ToolExecutor 4-Step Workflow

Source: `tool_executor.py:165-266`

The `record_tool_learnings()` method orchestrates the full ACE pipeline:

1. **Retrieve playbook**: `playbook = session.get_playbook()`
2. **Format feedback**: Tool names, parameters, and results summarized as text
3. **Reflect**: `reflector.reflect(question=query, agent_response=..., playbook=playbook, feedback=feedback)`
4. **Tag bullets**: Apply `reflection.bullet_tags` to playbook
5. **Curate**: `curator.curate(reflection=reflection, playbook=playbook, question_context=query, progress=f"Query #{execution_count}")`
6. **Apply & persist**: `playbook.apply_delta(curator_output.delta)` then `session.update_playbook(playbook)`

Debug logging to `/tmp/swecli_debug/playbook_evolution.log` tracks each evolution step.

### ContextPicker Injection

Source: `context_picker/picker.py:276-356`

The `_pick_playbook_strategies()` method:

1. Gets playbook from session: `session.get_playbook()`
2. Reads config for max_strategies, use_selection, weights, embedding_model, cache settings
3. Calls `playbook.as_context(query, max_strategies, ...)` to select top-K bullets
4. Returns strategies as context pieces

These pieces are appended to the system prompt in `_assemble_system_prompt()`:

```
{base_system_prompt}

## Learned Strategies
{strategies_content}
```

### Session Storage

Source: `models/session.py`

The session model stores the serialized playbook:

```python
class ChatSession:
    playbook: Optional[dict] = Field(default_factory=dict)

    def get_playbook(self) -> Playbook:
        if not self.playbook:
            return Playbook()
        return Playbook.from_dict(self.playbook)

    def update_playbook(self, playbook: Playbook) -> None:
        self.playbook = playbook.to_dict()
        self.updated_at = datetime.now()
```

Sessions are persisted as JSON in `~/.opendev/sessions/`. The playbook travels with the session, so when a session is restored, its playbook is restored too.

---

## 10. Graceful Degradation & Error Handling

ACE is designed so that failures in any component **never break query processing**. The system degrades gracefully at every layer.

### Failure Modes

**ACE component initialization fails** (QueryProcessor):

- Reflector/Curator init is wrapped in `try/except` → `pass`
- If `_ace_reflector` remains `None`, `record_tool_learnings()` is never called
- Result: Learning is silently disabled. Query processing continues normally.

**LLM returns invalid JSON** (Reflector/Curator):

- 3 retry attempts with progressively helpful prompts
- First retry: base prompt + `json_retry_simple` reminder
- Second retry: same (retry prompt re-appended)
- After 3 failures: `RuntimeError` raised, caught by caller → learning skipped for this turn

**Embedding API fails** (generate_embeddings):

- Falls back to random vectors (dimension 1536)
- Semantic scores become meaningless but don't crash
- Effectiveness (0.5 weight) and recency (0.3 weight) still produce useful rankings

**Embedding cache save fails** (BulletSelector):

- Wrapped in `try/except` → `pass`
- Embeddings are lost but will be regenerated on next selection
- No data corruption risk

**Embedding cache file corrupted** (EmbeddingCache.load_from_file):

- JSON decode or key errors → returns `None`
- Fresh cache is created, embeddings regenerated

**record_tool_learnings() itself fails** (ToolExecutor):

- Entire method is wrapped in a catch-all `try/except`
- Error logged to `/tmp/swecli_debug/playbook_evolution.log`
- Query processing continues unaffected

### Debug Logging

All ACE operations are logged to `/tmp/swecli_debug/playbook_evolution.log`:

- Playbook state before/after delta application
- Reflector output (reasoning, tags)
- Curator output (reasoning, operations)
- Error details when components fail

---

## 11. Configuration & Tuning

### BulletSelector Defaults

```
effectiveness weight    0.5     Helpful/harmful ratio importance
recency weight          0.3     Recent-update preference
semantic weight         0.2     Query-similarity importance
max_strategies (K)      30      Maximum bullets in context
embedding model         text-embedding-3-small
```

### Reflector / Curator

```
max_retries             3       JSON parsing retry limit
agent_response truncation  1000 chars   Prevents oversized prompts
```

### ConversationSummarizer

```
regenerate_threshold    5       Messages between regenerations
exclude_last_n          6       Recent messages kept as working memory
max_summary_length      500     Character limit on summaries
```

### ExecutionReflector

```
min_tool_calls          2       Minimum tool calls to trigger analysis
min_confidence          0.6     Minimum confidence to accept a result
```

### ContextPicker

Playbook config is read from the hierarchical config system (project > user > defaults):

```
config.playbook.max_strategies      30
config.playbook.use_selection       true
config.playbook.scoring_weights     {effectiveness: 0.5, recency: 0.3, semantic: 0.2}
config.playbook.embedding_model     "text-embedding-3-small"
config.playbook.cache_embeddings    true
config.playbook.cache_file          (derived from session path)
```

---

## 12. Limitations & Future Work

### Current Limitations

- **No cross-session playbook sharing**: Each session has an isolated playbook. Strategies learned in one session are not available in another, even for the same project.
- **No global strategy repository**: There is no mechanism to promote high-value bullets to a project-wide or user-wide knowledge base.
- **Semantic scoring depends on embedding API**: If the embedding API is unavailable, semantic scoring degrades to random (effectively disabled). The system still works via effectiveness + recency, but with reduced precision.
- **Rule-based ExecutionReflector covers limited patterns**: Only 5 pattern categories (file ops, code navigation, testing, shell commands, error recovery). Complex multi-step workflows or domain-specific patterns are not captured.
- **Learning adds latency**: Each learning cycle requires 2 additional LLM calls (Reflector + Curator). This adds latency after each tool execution round.
- **No bullet pruning by age**: Old, low-effectiveness bullets are never automatically cleaned up. The playbook can accumulate stale entries over long sessions.

### Future Directions

- **Cross-session playbook merging**: Allow high-confidence bullets to be promoted to a project-level playbook that seeds new sessions.
- **Global strategy repository**: A curated set of universally-useful strategies (e.g., "run tests after changes") that bootstrap new sessions.
- **Bullet pruning**: Automatically remove bullets with consistently harmful ratings or very old untested entries.
- **Richer pattern detection**: Extend ExecutionReflector with more sophisticated sequence analysis (n-gram patterns, conditional workflows).
- **Offline embedding generation**: Use local embedding models to eliminate API dependency for semantic scoring.

---

## References

- ACE Paper: [Agentic Context Engineering](https://arxiv.org/abs/2510.04618) (arXiv:2510.04618)
- ACE Repository: [kayba-ai/agentic-context-engine](https://github.com/kayba-ai/agentic-context-engine)
- Related design docs:
  - [Context Engineering Architecture](./context_engineering_architecture.md): Section 5 covers ACE briefly
  - [OpenCode Improvements](./opencode_improvements.md): Mentions ACE integration context
