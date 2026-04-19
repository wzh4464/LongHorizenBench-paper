# Message Queue Architecture

## Architecture Diagram

```mermaid
graph TD
    UI[Textual UI Input] -->|Submits Message| TR[TextualRunner]
    TR -->|enqueue_message| MP[MessageProcessor]
    
    subgraph Background Thread
        MP --> CheckTarget{Is live target active\n& Not a command?}
        
        CheckTarget -->|Yes| LQ[Live Injection Queue\nReactExecutor._injection_queue]
        CheckTarget -->|No| PQ[Primary Pending Queue\nqueue.Queue]
        
        PQ --> Loop[Processor Loop]
        Loop --> TypeCheck{Message Type}
        TypeCheck -->|Slash Command| CMD[CommandRouter]
        TypeCheck -->|Standard Query| QRY[TextualRunner._run_query]
    End
    
    LQ --> AgentLoop[Active Agent ReAct Loop]
    AgentLoop -->|Mid-execution Feedback| AgentRun[Agent Execution]
    
    CMD -->|Execute Command| Sys[SWE-CLI System]
    QRY -->|Execute Query| Sys
    
    MP -.->|Update UI State| UID[UI Display Indicator\n'N messages queued']
    Loop -.->|Needs Display flag| Ledger[DisplayLedger / ConversationLog]
```

## Overview
The SWE-CLI Textual UI handles user inputs asynchronously to ensure UI responsiveness while long-running tasks (like agent ReAct loops) are executing. This is achieved using a background processing queue managed by the `MessageProcessor` and orchestrated through the `TextualRunner`.

## Core Components
1. **`MessageProcessor`**: Runs a continuous background thread (`_processor_thread`) to dequeue and process user messages and slash commands sequentially.
2. **`TextualRunner`**: Acts as the bridge between the Textual UI and the SWE-CLI core runtime. It delegates user inputs from the UI to the `MessageProcessor`.
3. **Live Injection Queue (`ReactExecutor._injection_queue`)**: A secondary queue used specifically for injecting messages into an active agent loop so the agent can receive mid-execution feedback without waiting for the primary queue to drain.

## Message Handling Flow
1. **User Input Submission**: A user submits a message via the UI input field.
2. **Enqueueing**: The `TextualRunner` captures the input and calls `MessageProcessor.enqueue_message(text, needs_display)`.
3. **Live Injection Check**:
   - If an agent is currently running and the message is *not* a slash command, `MessageProcessor` checks if `_injection_target` (hooked to `react_executor.inject_user_message`) is active.
   - If active, the message is injected directly into `ReactExecutor._injection_queue` instead of the primary pending queue. 
4. **Queue Processing**:
   - If no live target is active (or if it's a command), the message is placed into the primary `_pending` queue (`queue.Queue`).
   - The background loop dequeues the message and identifies whether it is a slash command (starts with `/`) or a standard query.
5. **Dispatch & Execution**:
   - **Commands**: Dispatched via the `handle_command` callback to `TextualRunner._run_command`, which routes it through the `CommandRouter`.
   - **Queries**: Dispatched via the `handle_query` callback to `TextualRunner._run_query`.

## Display Updates & UI State
- The message processor dynamically updates the UI to show how many messages are currently queued (`app.update_queue_indicator`), which calculates the sum of the primary queue and the active injection queue.
- The `needs_display` flag ensures that messages queued while the assistant was busy are rendered to the `DisplayLedger` conversation log only when they actually begin processing, maintaining a logical visual flow.
