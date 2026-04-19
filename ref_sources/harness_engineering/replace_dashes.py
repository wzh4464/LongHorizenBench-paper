import re

filename = '/Users/nghibui/codes/swe-cli/technical_report/sections/architecture.tex'

with open(filename, 'r') as f:
    lines = f.readlines()

replacements = {
    # Line 13
    "pipeline sequentially -- from the entry point": "pipeline sequentially, from the entry point",
    # Line 17
    "distinct LLMs -- Normal, Thinking, Critique, VLM, and Compact -- each": "distinct LLMs (Normal, Thinking, Critique, VLM, and Compact), each",
    # Line 30
    "two distinct modes -- \emph{Plan Mode} and \emph{Normal Mode} -- with the agent": "two distinct modes, \emph{Plan Mode} and \emph{Normal Mode}, with the agent",
    # Line 39
    "decision per prompt -- the agent does not switch": "decision per prompt; the agent does not switch",
    # Line 41
    "Write operations -- file edits, command execution, file deletion -- are not": "Write operations (file edits, command execution, file deletion) are not",
    # Line 43
    "} the findings -- identifying patterns": "} the findings, identifying patterns",
    # Line 47
    "all tools -- file reading, file writing, code editing, command execution, and subagent spawning": "all tools, including file reading, file writing, code editing, command execution, and subagent spawning",
    # Line 49
    "unexpected results -- a test failure that reveals a deeper issue, a dependency conflict, or a scope change -- the user": "unexpected results (such as a test failure that reveals a deeper issue, a dependency conflict, or a scope change), the user",
    # Line 51
    "schema -- not because a runtime check": "schema, not because a runtime check",
    # Line 71
    "iteration -- follow-up instructions or system signals delivered through a thread-safe queue.": "iteration, such as follow-up instructions or system signals delivered through a thread-safe queue.",
    # Line 73
    "queue -- deferring completion if either condition holds": "queue, deferring completion if either condition holds",
    # Line 84
    "routing (our approach -- complexity in selection logic but enables workload optimization)": "routing (our approach, which introduces complexity in selection logic but enables workload optimization)",
    "execution (maximum quality but prohibitive latency and cost)": "execution (maximum quality but prohibitive latency and cost)",
    # Line 100
    "startup latency -- only models actually used in a session are initialized": "startup latency, as only models actually used in a session are initialized",
    # Line 118
    "chain-of-thought prompting (inflexible -- cannot adapt depth": "chain-of-thought prompting (inflexible because it cannot adapt depth",
    "phase (our primary approach -- enables depth control": "phase (our primary approach, which enables depth control",
    # Line 168
    "\emph{injection queue} -- a thread-safe queue through which": "\emph{injection queue}, which is a thread-safe queue through which",
    # Line 170
    "trace -- a structured analysis of the current situation, potential approaches, and risks -- without access": "trace (a structured analysis of the current situation, potential approaches, and risks) without access",
    "use: when tools are available, models tend to act quickly rather than think deeply. Six configurable depth levels -- from OFF to DEEP -- let users balance": "use: when tools are available, models tend to act quickly rather than think deeply. Six configurable depth levels, ranging from OFF to DEEP, let users balance",
    "selectively -- justified for complex tasks": "selectively, as it is justified for complex tasks",
    # Line 174
    "execution strategy -- parallel execution via a thread pool when all calls are independent (e.g., multiple file reads), or sequential execution when dependencies exist -- runs the tools": "execution strategy (such as parallel execution via a thread pool when all calls are independent, e.g., multiple file reads, or sequential execution when dependencies exist), and runs the tools",
    # Line 178
    "termination -- preventing premature": "termination to prevent premature",
    # Line 200
    "specific role -- an exploration subagent does not need write capabilities. Third, restricted tools limit the blast radius of errors: an exploration subagent cannot accidentally modify files.": "specific role, meaning an exploration subagent does not need write capabilities. Third, restricted tools limit the blast radius of errors: an exploration subagent cannot accidentally modify files.",
    # Line 259
    "session -- git workflow rules in a non-repository directory, subagent orchestration guidance when subagents are unused, task-tracking instructions when the feature is disabled -- consume": "session (such as git workflow rules in a non-repository directory, subagent orchestration guidance when subagents are unused, or task-tracking instructions when the feature is disabled) consume",
    "sections that \emph{do} matter, making the agent's behavior noisier. The fix is not to trim the prompt by hand but to make loading \emph{context-sensitive} from the start.": "sections that \emph{do} matter, making the agent's behavior noisier. The fix is not to trim the prompt by hand, but to make loading \emph{context-sensitive} from the start.",
    # Line 267
    "priority -- lower values appear": "priority: lower values appear",
    # Line 275
    "function; dashed borders": "function. Dashed borders",
    "function -- dashed borders": "function. Dashed borders",
    "Dynamic Context -- organize": "Dynamic Context, which organize",
    # Line 285
    "identifiers -- for example": "identifiers; for example",
    # Line 287
    "proceeds -- the agent starts": "proceeds, so the agent starts",
    "wholesale (e.g., the templates directory is absent), the builder falls back to a monolithic core template, guaranteeing": "wholesale (e.g., the templates directory is absent), the builder falls back to a monolithic core template. This guarantees",
    # Line 298
    "loops -- after three failed attempts, the agent": "loops; after three failed attempts, the agent",
    # Line 309
    "grows -- tool calls accumulate, file contents are read, code is written -- the system prompt": "grows, as tool calls accumulate, file contents are read, and code is written, the system prompt",
    # Line 311
    "prompt -- effective initially": "prompt, which is effective initially",
    "turns -- wastes": "turns, which wastes",
    "approach -- inject": "approach, which injects",
    # Line 316
    "Tier~1 -- Static system prompt.": "Tier~1: Static system prompt.",
    # Line 318
    "Tier~2 -- Dynamic system reminders.": "Tier~2: Dynamic system reminders.",
    # Line 320
    "Tier~3 -- Long-horizon persistence.": "Tier~3: Long-horizon persistence.",
    # Line 339
    "recency -- immediately before the next LLM call -- to counteract": "recency, immediately before the next LLM call, to counteract",
    # Line 343
    "lost -- the model has already internalized": "lost, as the model has already internalized",
    # Line 354
    "run -- after two attempts, accept": "run; after two attempts, accept",
    # Line 363
    "dispatch -- where reminders diverge": "dispatch, where reminders diverge",
    # Line 367
    "mechanism -- the system works without them; it works better with them.": "mechanism. The system works without them, but it works better with them.",
    # Line 369
    "rates -- ``read the file again''": "rates, as ``read the file again''",
    # Line 381 to 386
    "manager -- Controls": "manager: Controls",
    "manager -- Gates": "manager: Gates",
    "manager -- Tracks": "manager: Tracks",
    "manager -- Manages": "manager: Manages",
    "directory -- Current": "directory: Current",
    "Configuration -- Resolved": "Configuration: Resolved",
    # Line 391
    "alternative -- a service locator where components query a global registry -- reduces": "alternative, a service locator where components query a global registry, reduces",
    # Line 407
    "surprise -- users get": "surprise: users get"
}

changed = False
for i, line in enumerate(lines):
    for target, rep in replacements.items():
        if target in line:
            lines[i] = lines[i].replace(target, rep)
            changed = True

# Also blindly handle any leftover " -- " just in case
for i, line in enumerate(lines):
    if " -- " in line:
        # replace with ", " safely as a fallback
        lines[i] = re.sub(r' -- ', ', ', lines[i])

with open(filename, 'w') as f:
    f.writelines(lines)

print("Replaced successfully.")
