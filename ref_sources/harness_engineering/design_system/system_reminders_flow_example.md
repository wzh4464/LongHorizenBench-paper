# System Reminders - How They Work

System reminders are short messages injected mid-conversation to correct agent behavior. They solve one problem: as conversations grow longer, the LLM stops acting on instructions from the system prompt. A 2-sentence reminder placed right before the next LLM call is more effective than a paragraph buried 25 messages ago.

## The Mechanism

```
reminders.md                reminders.py              react_executor.py
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────────────┐
│ --- name ---     │     │                  │     │ condition detected?      │
│ Template text    │────>│ get_reminder()   │────>│   yes → messages.append( │
│ with {variables} │     │ parse + format   │     │     role: "user",        │
└──────────────────┘     └──────────────────┘     │     content: reminder)   │
                                                  │   → force next iteration │
                                                  └──────────────────────────┘
```

Templates live in `reminders.md` as named sections. `get_reminder(name, **kwargs)` retrieves and fills placeholders. The ReAct loop detects the condition, injects the reminder as a **user-role message** (higher attention weight than system messages), and forces another LLM call.

---

## Example 1: The Agent That Forgot Half the Task

**System prompt says** (among thousands of tokens of instructions):
> Complete all todos before finishing.

**User:** "Add input validation to the signup form and write tests for it."

```
msg[0]   user        "Add validation to the signup form and write tests."
msg[1]   assistant   create_todo("Add input validation")
                     create_todo("Write tests for validation")
msg[2]   assistant   read_file("signup_form.py")
msg[3]   tool        (500 lines of form code)
         ...
         (15+ more messages: reading models, searching patterns,
          editing the form 3 times, running import checks)
         ...
msg[16]  assistant   update_todo("Add input validation" → done)
         ...
         (more tool outputs fill the context window)
         ...
msg[26]  assistant   "I've added input validation covering email, password,
                      and username. Let me know if you need anything else!"
```

The agent declared victory. The "Write tests" todo is still open - the system prompt instruction about completing all todos is 25 messages of file contents away.

```
                       msg[26]: Agent tries to finish
                       with 1 incomplete todo remaining
                                   │
                ┌──────────────────┴──────────────────┐
                │                                      │
         WITHOUT REMINDER                       WITH REMINDER
                │                                      │
                ▼                                      ▼
    Agent: "Done!"                   ReactExecutor detects:
    User must manually say           has_incomplete_todos() → true
    "You forgot the tests..."                  │
                │                              ▼
                ▼                    Injects:
    User loses trust.               "You have 1 incomplete todo(s):
    Agent looks unreliable.           - Write tests for validation
                                     Please complete these tasks
                                      before finishing."
                                               │
                                               ▼
                                     Agent reads test file, writes
                                     tests, marks todo done.
                                               │
                                               ▼
                                     "Done. Validation added, tests
                                      cover all 3 input types."
                                               │
                                               ▼
                                         Actually done. ✓
```

---

## Example 2: The Agent That Gave Up After One Failure

**System prompt says** (among thousands of tokens of instructions):
> When a file edit fails, re-read the file to get current content and retry.

**User:** "Add rate limiting to the /api/upload endpoint."

```
msg[0]   user        "Add rate limiting to /api/upload."
msg[1]   assistant   read_file("routes/api.py")
msg[2]   tool        (400 lines of route handlers)
         ...
         (reads middleware, searches for rate limiter utility,
          reads the utility - 6 more messages of file contents)
         ...
msg[9]   assistant   edit_file("routes/api.py",
                       old_content="def upload(request):", ...)
msg[10]  tool        "Error: old_content not found in file"
```

The edit failed - the file actually has `async def upload(request: Request):` but the agent misremembered it as `def upload(request):` after reading 800+ lines of other files. The system prompt said "re-read and retry" but that's 10 messages of file contents away.

```
msg[11]  assistant   "I couldn't modify the file. You may need to
                      manually add the rate limiter."
```

The agent gave up after one attempt.

```
                       msg[10]: edit_file returns
                       "old_content not found"
                                   │
                ┌──────────────────┴──────────────────┐
                │                                      │
         WITHOUT REMINDER                       WITH REMINDER
                │                                      │
                ▼                                      ▼
    Agent: "I couldn't do it,        _classify_error("old_content
    do it manually."                  not found") → "edit_mismatch"
                │                              │
                ▼                              ▼
    User has to say                  Injects:
    "just re-read and               "The edit_file old_content did
     try again..."                   not match. Read the file again
                                     to get the exact current content,
                                     then retry."
                                               │
                                               ▼
                                     Agent re-reads the file,
                                     sees the actual signature,
                                     retries edit → succeeds.
                                               │
                                               ▼
                                         Task complete. ✓
```

The error-specific nudge tells the agent the exact recovery step - not generic "try again," but "the content changed, re-read first." The agent's mistake was `def upload(request):` vs the actual `async def upload(request: Request):` - a common drift after reading many files.

---

## Guardrails

Reminders don't loop forever. Each type has a cap:

- `incomplete_todos_nudge` - max 2 fires, then allow completion
- `failed_tool_nudge` - max 3 fires, then accept failure
- `completion_summary_nudge` - fires once

After the cap, the system accepts the agent's judgment and moves on.
