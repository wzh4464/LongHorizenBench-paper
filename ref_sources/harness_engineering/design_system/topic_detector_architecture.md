# Topic Detector Architecture

## Overview

The topic detector generates session titles by analyzing recent conversation messages with a lightweight LLM call running on a background thread. It selects the cheapest available model for the configured provider, sends the last 4 messages with a structured prompt, and parses a JSON response indicating whether a new topic was introduced and what it should be titled. The system operates alongside a simpler heuristic title generator in SessionManager, forming a dual title generation strategy: fast heuristic for initial save, refined LLM-based detection for topic changes.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     Session Save Trigger                                  │
│                                                                           │
│  SessionManager.save_session()                                           │
│  │                                                                        │
│  ├── Write metadata to {session_id}.json                                 │
│  ├── Append messages to {session_id}.jsonl                               │
│  ├── Update sessions-index.json                                          │
│  │                                                                        │
│  ├── If no title exists:                                                 │
│  │   └── generate_title(messages)          ◄── Heuristic (fast, free)    │
│  │       └── First user message, first sentence, truncate to 50 chars    │
│  │                                                                        │
│  └── If topic_detection enabled:                                         │
│      └── topic_detector.detect(session_manager, session_id, messages)    │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      TopicDetector.detect()                               │
│                                                                           │
│  ├── Check: self._client is not None?                                    │
│  │   └── None (no API key) → return immediately (no-op)                  │
│  │                                                                        │
│  ├── Extract last _MAX_RECENT_MESSAGES (4) from messages                 │
│  │                                                                        │
│  └── Spawn daemon thread:                                                │
│      └── threading.Thread(target=_detect_and_update, daemon=True)        │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
                          │
              [Background Thread]
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                   _detect_and_update()                                     │
│                                                                           │
│  ├── _call_llm(recent_messages)                                          │
│  │   │                                                                    │
│  │   ├── Build API payload:                                              │
│  │   │   ├── messages[0] = system message (topic detection prompt)       │
│  │   │   ├── messages[1..N] = conversation (role/content pairs)          │
│  │   │   └── messages[N+1] = "Analyze the conversation above..."        │
│  │   │                                                                    │
│  │   ├── Parameters:                                                     │
│  │   │   ├── max_tokens = 100                                            │
│  │   │   └── temperature = 0.0 (deterministic)                           │
│  │   │                                                                    │
│  │   ├── POST to provider API endpoint                                   │
│  │   │                                                                    │
│  │   └── Parse response content as JSON                                  │
│  │       └── Returns {"isNewTopic": bool, "title": str|null}            │
│  │                                                                        │
│  ├── If result is None (LLM error):                                      │
│  │   └── return (keep existing title)                                    │
│  │                                                                        │
│  ├── If isNewTopic == False:                                             │
│  │   └── return (keep existing title)                                    │
│  │                                                                        │
│  └── If isNewTopic == True:                                              │
│      ├── title = result["title"][:50]    ◄── Truncate to 50 chars       │
│      └── session_manager.set_title(session_id, title)                    │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                 SessionManager.set_title()                                 │
│                                                                           │
│  ├── Truncate title to 50 chars                                          │
│  │                                                                        │
│  ├── If session is current session (in-memory):                          │
│  │   ├── session.metadata["title"] = title                               │
│  │   └── save_session()                                                  │
│  │                                                                        │
│  └── If session is not current (on disk):                                │
│      ├── Load {session_id}.json                                          │
│      ├── Update metadata.title                                           │
│      ├── Write back {session_id}.json                                    │
│      └── Update sessions-index.json entry                                │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

## Cheap Model Selection

The topic detector uses the cheapest available model to minimize cost and latency for what is essentially a classification task.

```
_CHEAP_MODELS = {
    "openai":     "gpt-4o-mini",
    "anthropic":  "claude-3-5-haiku-20241022",
    "fireworks":  "accounts/fireworks/models/llama-v3p1-8b-instruct",
}

_ENV_KEYS = {
    "openai":     "OPENAI_API_KEY",
    "anthropic":  "ANTHROPIC_API_KEY",
    "fireworks":  "FIREWORKS_API_KEY",
}
```

### Resolution Logic

```
_resolve_cheap_model(config)
│
├── Step 1: Try user's configured provider
│   ├── provider = config.model_provider
│   ├── Check: provider in _CHEAP_MODELS?
│   ├── Check: _ENV_KEYS[provider] in environment?
│   └── If both: return (provider, _CHEAP_MODELS[provider])
│
├── Step 2: Fall back to any available provider
│   ├── For provider in ["openai", "anthropic", "fireworks"]:
│   │   ├── Check: _ENV_KEYS[provider] in environment?
│   │   └── If yes: return (provider, _CHEAP_MODELS[provider])
│   └── None found → return None
│
└── If None:
    └── TopicDetector._client = None
        └── detect() becomes a no-op
```

This ensures the detector works regardless of which provider the user has configured for their main agent, as long as any API key is available.

## Detection Prompt

The system prompt loaded from `memory/memory-topic-detection.md`:

```
You are a conversation topic analyzer. Your job is to determine if the
user's latest message introduces a new conversation topic.

Analyze the conversation and respond with a JSON object containing
exactly two fields:
- "isNewTopic": boolean - true if the latest message starts a new topic
- "title": string or null - a 2-3 word title if isNewTopic is true,
  null otherwise

Output only the JSON object, no other text.
```

## LLM Call Construction

```
_call_llm(recent_messages)
│
├── messages = [
│   │
│   ├── {                                          ◄── System prompt
│   │     "role": "system",
│   │     "content": <topic_detection_prompt>
│   │   }
│   │
│   ├── {                                          ◄── Conversation history
│   │     "role": "user",                              (last 4 messages)
│   │     "content": "fix the login bug"
│   │   }
│   ├── {
│   │     "role": "assistant",
│   │     "content": "I found the issue in auth.py..."
│   │   }
│   ├── {
│   │     "role": "user",
│   │     "content": "now help me set up dark mode"
│   │   }
│   │
│   └── {                                          ◄── Analysis prompt
│         "role": "user",
│         "content": "Analyze the conversation above..."
│       }
│   ]
│
├── Parameters:
│   ├── model: "gpt-4o-mini" (or equivalent cheap model)
│   ├── max_tokens: 100
│   └── temperature: 0.0
│
├── POST → provider API endpoint
│
└── Parse response.choices[0].message.content as JSON
```

## Response Parsing

```
Expected LLM response:
  {"isNewTopic": true, "title": "Dark Mode Setup"}

Parsing flow:
│
├── Extract content string from API response
│
├── json.loads(content)
│   │
│   ├── Success:
│   │   ├── Check "isNewTopic" field (bool)
│   │   ├── Check "title" field (str or null)
│   │   └── Return parsed dict
│   │
│   └── Failure (json.JSONDecodeError):
│       ├── Log debug message
│       └── Return None (keep existing title)
│
├── If isNewTopic == True and title is not None:
│   └── title[:50] → set_title()
│
└── If isNewTopic == False or title is None:
    └── No action (existing title preserved)
```

## Dual Title Generation

The system uses two complementary mechanisms for session titles.

```
┌────────────────────────────────┐    ┌────────────────────────────────────┐
│ Heuristic Title Generator      │    │ LLM Topic Detector                 │
│ (SessionManager.generate_      │    │ (TopicDetector)                    │
│  title)                        │    │                                    │
│                                │    │                                    │
│ Trigger: First save_session()  │    │ Trigger: Every save_session()      │
│          when no title exists  │    │          if topic_detection=True   │
│                                │    │                                    │
│ Method:  First user message,   │    │ Method:  LLM analyzes last 4       │
│          first sentence,       │    │          messages for topic change │
│          truncate to 50 chars  │    │                                    │
│                                │    │                                    │
│ Cost:    Zero (string ops)     │    │ Cost:    ~100 tokens per call      │
│                                │    │          (cheap model)             │
│                                │    │                                    │
│ Latency: Microseconds          │    │ Latency: 200-500ms (background)   │
│          (synchronous)         │    │          (non-blocking)            │
│                                │    │                                    │
│ Quality: Low (just first       │    │ Quality: High (understands topic   │
│          sentence)             │    │          changes mid-session)      │
│                                │    │                                    │
│ Purpose: Immediate fallback    │    │ Purpose: Refined title that        │
│          title                 │    │          tracks conversation       │
│                                │    │          evolution                 │
└────────────────────────────────┘    └────────────────────────────────────┘

Timeline:

  save_session() called
       │
       ├── No title? → generate_title() sets heuristic title instantly
       │                "fix the login bug"
       │
       └── topic_detector.detect() fires background thread
                │
                └── [200ms later] LLM returns isNewTopic=false
                    → title unchanged: "fix the login bug"

  ... user switches topic ...

  save_session() called
       │
       └── topic_detector.detect() fires background thread
                │
                └── [300ms later] LLM returns isNewTopic=true, "Dark Mode"
                    → set_title() updates to "Dark Mode"
```

## Session Index Update Flow

```
set_title(session_id, title)
│
├── title = title[:50]
│
├── Is this the current session?
│   │
│   YES:
│   ├── session.metadata["title"] = title
│   └── save_session()
│       ├── Write {session_id}.json (metadata)
│       └── Update sessions-index.json:
│           {
│             "entries": [
│               {
│                 "sessionId": "abc12345",
│                 "title": "Dark Mode",    ◄── Updated
│                 "modified": "2026-03-02T...",
│                 ...
│               }
│             ]
│           }
│
│   NO (session on disk, not current):
│   ├── Load {session_id}.json from disk
│   ├── Update metadata.title
│   ├── Write back {session_id}.json
│   └── Update sessions-index.json entry
│       └── Atomic write via tempfile + rename
```

## Graceful Degradation

The topic detector is designed to fail silently at every level.

```
Failure Point              Behavior                     Result
──────────────             ────────                     ──────
No API key available       _client = None               detect() returns immediately
                                                         (no thread spawned)

topic_detection = False    Config flag checked           detect() returns immediately

LLM API error              Exception caught in          Logged as debug, existing
                           _call_llm()                  title preserved

HTTP timeout               Caught by httpx timeout      Logged as debug, existing
                                                         title preserved

Malformed JSON response    json.JSONDecodeError caught  Return None, existing
                                                         title preserved

Missing isNewTopic field   KeyError caught              Return None, existing
                                                         title preserved

set_title() file error     Exception in SessionManager  Logged as warning,
                                                         session unaffected

Thread crash               Daemon thread, no cleanup    Main thread unaffected
                           needed
```

No failure in the topic detector can affect the main agent loop or session persistence.

## Key Files Reference

| Component | File | Key Elements |
|-----------|------|--------------|
| Topic detector | `swecli/core/context_engineering/history/topic_detector.py` | TopicDetector, detect(), _call_llm(), _resolve_cheap_model() |
| Detection prompt | `swecli/core/agents/prompts/templates/memory/memory-topic-detection.md` | LLM instruction template |
| Session manager | `swecli/core/context_engineering/history/session_manager.py` | set_title(), generate_title(), save_session() |
| Config flag | `swecli/models/config.py` | AppConfig.topic_detection |
| Session model | `swecli/models/session.py` | Session.metadata["title"], SessionMetadata.title |
| Tests | `tests/test_topic_detector.py` | Init, detection, prompt template tests |
