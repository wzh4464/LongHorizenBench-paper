# Channel System Architecture

## Overview

The channel system abstracts multi-channel messaging into a unified interface, enabling the agent to communicate through Telegram, WhatsApp, Web, and CLI without channel-specific logic in the core. A ChannelAdapter converts between channel-native formats and a pair of normalized message types (InboundMessage and OutboundMessage). The MessageRouter coordinates session resolution, workspace selection, reset policies, and agent dispatch for every inbound message regardless of origin channel.

## End-to-End Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          External Channels                                │
│                                                                           │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐            │
│  │ Telegram  │  │ WhatsApp  │  │   Web UI  │  │    CLI    │            │
│  │  Bot API  │  │ Cloud API │  │ WebSocket │  │   REPL    │            │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘            │
│        │               │              │              │                    │
└────────┼───────────────┼──────────────┼──────────────┼────────────────────┘
         │               │              │              │
         ▼               ▼              ▼              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        Channel Adapter Layer                              │
│                                                                           │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                │
│  │TelegramAdapter│  │WhatsAppAdapter│  │ MockAdapter   │                │
│  │(skeleton)     │  │(skeleton)     │  │(testing)      │                │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘                │
│          │                  │                   │                         │
│          │   Converts raw channel messages      │                         │
│          │   to/from InboundMessage /           │                         │
│          │   OutboundMessage                    │                         │
│          │                                      │                         │
└──────────┼──────────────────────────────────────┼─────────────────────────┘
           │                                      │
           ▼                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         MessageRouter                                     │
│                                                                           │
│  handle_inbound(adapter, inbound_message)                                │
│  │                                                                        │
│  ├─[1] Get adapter for channel                                           │
│  ├─[2] Resolve session (find existing or create new)                     │
│  ├─[3] Check reset policy (expired → create fresh session)               │
│  ├─[4] Handle workspace selection (if not confirmed)                     │
│  ├─[5] Convert to ChatMessage with provenance                            │
│  ├─[6] Dispatch to agent executor                                        │
│  └─[7] Save session                                                      │
│                                                                           │
│  Dependencies:                                                            │
│  ├── SessionManager (session CRUD)                                       │
│  ├── WorkspaceSelector (workspace prompt and parsing)                    │
│  └── agent_executor: Callable[[Session, str], str]                       │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         Agent Execution                                   │
│                                                                           │
│  agent_executor(session, message_text) → response_text                   │
│  │                                                                        │
│  ├── Sync: loop.run_in_executor(None, executor, session, text)           │
│  └── Async: await executor(session, text)                                │
│                                                                           │
│  Response → OutboundMessage → adapter.send(delivery_context, message)    │
└──────────────────────────────────────────────────────────────────────────┘
```

## Message Models

### InboundMessage

Unified representation of a message arriving from any channel.

```
InboundMessage (Dataclass)
│
├── channel: str              Channel name ("telegram", "whatsapp", "web", "cli")
├── user_id: str              Channel-specific user ID (@user, +phone, session_id)
├── text: str                 Message content
├── timestamp: datetime       When sent (defaults to now)
├── thread_id: Optional[str]  Thread/topic ID (for threaded channels)
├── chat_type: str            "direct" or "group"
├── attachments: list[MessageAttachment]
├── reply_to_message_id: Optional[str]
├── metadata: dict            Channel-specific metadata (chat_id, language, etc.)
└── raw: dict                 Original raw message payload from channel
```

### OutboundMessage

Unified representation of a message sent from agent to any channel.

```
OutboundMessage (Dataclass)
│
├── text: str                 Message content
├── thread_id: Optional[str]  Thread to reply in
├── reply_to_message_id: Optional[str]
├── attachments: list[MessageAttachment]
├── parse_mode: str           "markdown", "html", or "plain"
├── disable_preview: bool     Disable link previews
└── metadata: dict            Channel-specific metadata (buttons, keyboards)
```

### MessageAttachment

```
AttachmentType (Enum)
│  IMAGE, FILE, AUDIO, VIDEO, DOCUMENT

MessageAttachment (Dataclass)
│
├── type: AttachmentType
├── filename: str
├── url: Optional[str]         Download URL
├── file_path: Optional[str]   Local file path (if downloaded)
├── mime_type: Optional[str]
├── size_bytes: Optional[int]
└── metadata: dict             Channel-specific attachment metadata
```

## ChannelAdapter Interface

```
ChannelAdapter (ABC)
│
├── channel_name: str          Channel identifier
│
├── start() → None             Initialize connection and start listening
│   └── Connect to API, set up webhook/polling, register handlers
│
├── send(delivery_context, message: OutboundMessage) → None
│   └── Convert OutboundMessage to channel-native format and deliver
│       delivery_context: dict with channel, user_id, thread_id, etc.
│
└── stop() → None              Gracefully shutdown
    └── Close connections, deregister webhooks, cleanup resources
```

Concrete adapters implement this interface for each channel:
- **TelegramAdapter** - Bot API via long polling or webhooks (skeleton)
- **WhatsAppAdapter** - Cloud API via webhooks (skeleton)
- **MockChannelAdapter** - In-memory adapter for testing with simulate_inbound() helper

## MessageRouter Flow

```
handle_inbound(adapter, inbound_message)
│
│ ┌────────────────────────────────────────────────────────────────┐
│ │ Step 1: Get Adapter                                            │
│ │ adapter = _adapters[message.channel]                           │
│ │ If not found → log error, return                               │
│ └────────────────────────────────────────────────────────────────┘
│
│ ┌────────────────────────────────────────────────────────────────┐
│ │ Step 2: Resolve Session                                        │
│ │ session = _resolve_session(channel, user_id, thread_id)        │
│ │                                                                 │
│ │ _resolve_session():                                            │
│ │   ├── find_session_by_channel_user(channel, user_id, thread_id)│
│ │   │   └── Found → load and return existing session             │
│ │   └── Not found → create new session with:                     │
│ │       ├── channel, channel_user_id, thread_id set              │
│ │       ├── workspace_confirmed = False                          │
│ │       └── delivery_context with channel metadata               │
│ └────────────────────────────────────────────────────────────────┘
│
│ ┌────────────────────────────────────────────────────────────────┐
│ │ Step 3: Check Reset Policy                                     │
│ │ if should_reset_session(session):                              │
│ │   └── Create fresh session (old session preserved on disk)     │
│ └────────────────────────────────────────────────────────────────┘
│
│ ┌────────────────────────────────────────────────────────────────┐
│ │ Step 4: Workspace Selection                                    │
│ │ if not session.workspace_confirmed:                            │
│ │   └── _handle_workspace_selection(adapter, session, message)   │
│ │       └── Returns without dispatching to agent                 │
│ └────────────────────────────────────────────────────────────────┘
│
│ ┌────────────────────────────────────────────────────────────────┐
│ │ Step 5: Convert to ChatMessage                                 │
│ │ ChatMessage(                                                    │
│ │   role="user",                                                 │
│ │   content=message.text,                                        │
│ │   provenance=InputProvenance(                                  │
│ │     kind="external_user",                                      │
│ │     source_channel=message.channel                             │
│ │   )                                                            │
│ │ )                                                               │
│ │ session.add_message(chat_message)                              │
│ └────────────────────────────────────────────────────────────────┘
│
│ ┌────────────────────────────────────────────────────────────────┐
│ │ Step 6: Dispatch to Agent                                      │
│ │ response = _dispatch_to_agent(session, message.text)           │
│ │                                                                 │
│ │ _dispatch_to_agent():                                          │
│ │   ├── If async executor: await executor(session, text)         │
│ │   └── If sync executor: run_in_executor(None, executor, ...)   │
│ │                                                                 │
│ │ adapter.send(delivery_context, OutboundMessage(text=response)) │
│ └────────────────────────────────────────────────────────────────┘
│
│ ┌────────────────────────────────────────────────────────────────┐
│ │ Step 7: Save Session                                           │
│ │ session_manager.save_session(session)                          │
│ └────────────────────────────────────────────────────────────────┘
```

## Workspace Selection State Machine

When a channel user sends their first message, the session has no working directory. The workspace selection flow prompts the user to choose a project.

```
                        ┌──────────────┐
                        │  New Session │
                        │  workspace_  │
                        │  confirmed   │
                        │  = False     │
                        └──────┬───────┘
                               │
                  First message from user
                               │
                               ▼
                ┌──────────────────────────┐
                │ WorkspaceSelector.prompt_ │
                │ workspace_selection()     │
                │                           │
                │ Get available workspaces  │
                │ from SessionManager       │
                └──────────┬───────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
        No workspaces            Has workspaces
              │                         │
              ▼                         ▼
    ┌──────────────────┐   ┌─────────────────────────┐
    │ "Please provide  │   │ "Select workspace:      │
    │  a project path" │   │  1. /path/to/project1   │
    └────────┬─────────┘   │  2. /path/to/project2   │
             │             │  Or provide a new path"  │
             │             └────────────┬─────────────┘
             │                          │
             └──────────┬───────────────┘
                        │
               User responds with
               number or path
                        │
                        ▼
         ┌──────────────────────────────┐
         │ WorkspaceSelector.parse_     │
         │ workspace_choice(input,      │
         │                  workspaces) │
         └──────────┬───────────────────┘
                    │
           ┌────────┴────────┐
           │                 │
      Valid choice      Invalid choice
           │                 │
           ▼                 ▼
  ┌──────────────┐  ┌────────────────┐
  │ Set session   │  │ Send error     │
  │ working_dir   │  │ message,       │
  │ workspace_    │  │ reprompt       │
  │ confirmed     │  └────────────────┘
  │ = True        │
  │               │
  │ Send confirm  │
  │ message       │
  └───────┬───────┘
          │
     Ready for agent
       execution
```

Pending workspace selections are tracked in `_pending_workspace_selection` keyed by `(channel, user_id, thread_id)`.

## Reset Policies

Each channel has a default policy controlling when sessions automatically reset.

```
Channel      Mode     Parameter             Behavior
─────────    ─────    ──────────            ─────────
telegram     idle     idle_minutes: 60      Reset after 60 min inactivity
whatsapp     idle     idle_minutes: 30      Reset after 30 min inactivity
slack        daily    at_hour_utc: 4        Reset daily at 04:00 UTC
discord      idle     idle_minutes: 120     Reset after 120 min inactivity
web          never    -                     Never auto-reset
cli          never    -                     Never auto-reset
default      idle     idle_minutes: 60      Fallback for unknown channels
```

### should_reset_session() Logic

```
should_reset_session(session)
│
├── Get policy for session.channel
│
├── mode == "never"?
│   └── return False
│
├── mode == "idle"?
│   └── return (now - session.last_activity) > idle_minutes
│
├── mode == "daily"?
│   └── return day_boundary_crossed AND past reset_hour_utc
│
└── Unknown mode → return False
```

When a session is reset, a new session is created. The old session remains on disk and can be listed/resumed.

## Message Provenance

Every inbound message is tagged with an InputProvenance record tracking its origin.

```
InputProvenance (Pydantic Model)
│
├── kind: str                "external_user" | "forwarded" | "system"
├── source_channel: str      Channel the message arrived from
└── source_session_id: Optional[str]   If forwarded from another session
```

This enables:
- Audit trails for multi-channel conversations
- Distinguishing user-initiated messages from forwarded or system-generated ones
- Tracing message flow when sessions span channels

## Delivery Context

The delivery context is a dict carrying channel-specific routing metadata needed to send a response back to the correct user and thread.

```
delivery_context = {
    "channel": "telegram",
    "user_id": "@alice",
    "thread_id": "topic_123",
    "chat_id": 12345678,          # Telegram-specific
    "message_id": 987654,         # For reply threading
    ...additional channel metadata
}
```

The adapter interprets this context to route the OutboundMessage to the correct recipient. This decouples the router from channel-specific addressing.

## Adapter Registration

```
MessageRouter
│
├── register_adapter(adapter: ChannelAdapter) → None
│   └── _adapters[adapter.channel_name] = adapter
│
└── get_adapter(channel_name: str) → ChannelAdapter
    └── Lookup by name, raise if not found
```

Multiple adapters can be registered simultaneously, enabling the system to serve Telegram, WhatsApp, and Web users in a single process.

## Key Files Reference

| Component | File | Key Elements |
|-----------|------|--------------|
| Adapter interface, messages | `swecli/core/channels/base.py` | ChannelAdapter, InboundMessage, OutboundMessage, AttachmentType |
| Message router | `swecli/core/channels/router.py` | MessageRouter, handle_inbound(), _resolve_session() |
| Workspace selection | `swecli/core/channels/workspace_selector.py` | WorkspaceSelector, prompt_workspace_selection(), parse_workspace_choice() |
| Reset policies | `swecli/core/channels/reset_policies.py` | CHANNEL_RESET_POLICIES, should_reset_session() |
| Mock adapter | `swecli/core/channels/mock.py` | MockChannelAdapter, simulate_inbound() |
| Provenance model | `swecli/models/message.py` | InputProvenance |
| Session model | `swecli/models/session.py` | Session (channel, workspace_confirmed, delivery_context fields) |
