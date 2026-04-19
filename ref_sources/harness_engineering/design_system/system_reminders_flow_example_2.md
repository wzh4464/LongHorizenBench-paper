# System Reminders - Example 2: The Agent That Gave Up

## The Setup

**System prompt** (excerpt, among thousands of tokens of other instructions):

> When a file edit fails, re-read the file to get the current content and retry. Do not give up after a single failure.

**User request:**

> "Add rate limiting to the /api/upload endpoint."

## What Happens

```
msg[0]   user        "Add rate limiting to the /api/upload endpoint."

msg[1]   assistant   read_file("routes/api.py")
msg[2]   tool        (400 lines of route handlers)
msg[3]   assistant   read_file("middleware/auth.py")
msg[4]   tool        (150 lines, looking for existing middleware patterns)
msg[5]   assistant   search("rate limit")
msg[6]   tool        (found rate_limiter.py utility)
msg[7]   assistant   read_file("utils/rate_limiter.py")
msg[8]   tool        (80 lines of rate limiter utility)
msg[9]   assistant   edit_file("routes/api.py",
                       old_content="def upload(request):",
                       new_content="@rate_limit(10, '1m')\ndef upload(request):")
msg[10]  tool        "Error: old_content not found in file"
```

The edit failed. Between msg[2] and msg[9], another tool reformatted the file, or the agent misremembered the exact content. The system prompt said "re-read and retry" - but that instruction is now 10 messages of file contents away.

```
msg[11]  assistant   "I wasn't able to modify the file. The content I
                      expected wasn't found. You may need to manually
                      add the rate limiter decorator to the upload endpoint."
```

The agent gave up.

## The Fork

```
                       msg[10]: edit_file returns
                       "old_content not found in file"
                                   │
                ┌──────────────────┴──────────────────┐
                │                                      │
         WITHOUT REMINDER                       WITH REMINDER
                │                                      │
                ▼                                      ▼
    Agent says "I couldn't           MainAgent._classify_error(
    modify the file..."              "old_content not found")
    Gives up. Tells user               → "edit_mismatch"
    to do it manually.                         │
                │                              ▼
                ▼                    get_reminder("nudge_edit_mismatch")
    User has to either do              → "The edit_file old_content did
    it themselves or say                  not match. Read the file again
    "just re-read the file              to get the exact current content,
     and try again"                      then retry."
                                               │
                                               ▼
                                     msg[12] assistant:
                                     read_file("routes/api.py")
                                               │
                                               ▼
                                     msg[13] tool:
                                     "async def upload(request: Request):"
                                     (the actual current content)
                                               │
                                               ▼
                                     msg[14] assistant:
                                     edit_file(old_content=
                                       "async def upload(request: Request):",
                                       ...)
                                               │
                                               ▼
                                     msg[15] tool:
                                     "File edited successfully"
                                               │
                                               ▼
                                         Task complete. ✓
```

The difference: the error-specific nudge tells the agent *exactly* what recovery step to take (re-read, then retry), instead of generic "try again." The agent misremembered `def upload(request):` but the file actually had `async def upload(request: Request):`.
