# Extension Points

**File**: `09_extension_points.md`
**Purpose**: How to extend the system

---

## Table of Contents

- [Overview](#overview)
- [Adding New Tools](#adding-new-tools)
- [Creating Custom Subagents](#creating-custom-subagents)
- [Adding Prompt Sections](#adding-prompt-sections)
- [Implementing New UI Modes](#implementing-new-ui-modes)
- [Extending Session Storage](#extending-session-storage)
- [Adding MCP Servers](#adding-mcp-servers)
- [Custom Approval Handlers](#custom-approval-handlers)
- [Adding Skills](#adding-skills)

---

## Overview

SWE-CLI is designed for extensibility. This guide shows you how to extend the system at key extension points:

1. **Tools**: Add new capabilities (file operations, web scraping, etc.)
2. **Subagents**: Create specialized agents for specific tasks
3. **Prompt sections**: Modify agent behavior with new instructions
4. **UI modes**: Add custom user interfaces
5. **Storage backends**: Implement alternative session storage
6. **MCP servers**: Integrate external tool providers
7. **Approval handlers**: Custom approval logic
8. **Skills**: Add reusable command shortcuts

Each section includes:
- Step-by-step instructions
- Code examples
- Testing recommendations
- Integration points

---

## Adding New Tools

**Purpose**: Extend agent capabilities with new tools

### Step 1: Create Tool Implementation

Create a new file in `swecli/core/context_engineering/tools/implementations/`:

```python
# swecli/core/context_engineering/tools/implementations/my_tool.py
from typing import Optional

class MyTool:
    """My custom tool implementation"""

    def get_schema(self) -> dict:
        """Return JSON schema for LLM"""
        return {
            "name": "MyTool",
            "description": "Description of what the tool does",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Description of param1"
                    },
                    "param2": {
                        "type": "number",
                        "description": "Description of param2",
                        "default": 10
                    }
                },
                "required": ["param1"]
            }
        }

    async def execute(
        self,
        param1: str,
        param2: int = 10,
        context: "ToolExecutionContext" = None
    ) -> str:
        """
        Execute the tool

        Args:
            param1: First parameter
            param2: Second parameter (optional)
            context: Execution context

        Returns:
            Tool result as string
        """
        # Check for interruption
        if context and context.interrupt_token and context.interrupt_token.is_set():
            return "Operation interrupted"

        # Tool logic here
        result = f"Processed {param1} with param2={param2}"

        return result
```

### Step 2: Add to Handler

If your tool fits an existing category, add it to that handler. Otherwise, create a new handler.

**Option A: Add to existing handler**

```python
# swecli/core/context_engineering/tools/handlers/file_handler.py
from ..implementations.my_tool import MyTool

class FileOperationHandler(ToolHandler):
    def __init__(self):
        self.tools = {
            "Read": ReadTool(),
            "Write": WriteTool(),
            "MyTool": MyTool(),  # Add your tool
        }

    async def execute(self, tool_name: str, parameters: dict, context):
        if tool_name == "MyTool":
            tool = self.tools["MyTool"]
            return await tool.execute(**parameters, context=context)
        # ... existing tools
```

**Option B: Create new handler**

```python
# swecli/core/context_engineering/tools/handlers/my_handler.py
class MyHandler(ToolHandler):
    """Handler for my custom tools"""

    def __init__(self):
        self.tools = {
            "MyTool": MyTool(),
        }

    def get_tools(self) -> dict:
        """Return all tools"""
        return self.tools

    async def execute(
        self,
        tool_name: str,
        parameters: dict,
        context: ToolExecutionContext
    ) -> str:
        """Execute tool"""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool = self.tools[tool_name]
        return await tool.execute(**parameters, context=context)
```

### Step 3: Register Handler

```python
# swecli/core/context_engineering/tools/registry.py
from .handlers.my_handler import MyHandler

class ToolRegistry:
    def __init__(self):
        self.handlers = {
            "file": FileOperationHandler(),
            "process": ProcessExecutionHandler(),
            "my_category": MyHandler(),  # Register your handler
        }
```

### Step 4: Write Tests

```python
# tests/test_my_tool.py
import pytest
from swecli.core.context_engineering.tools.implementations.my_tool import MyTool
from swecli.models.tool_context import ToolExecutionContext

@pytest.mark.asyncio
async def test_my_tool_basic():
    """Test basic tool execution"""
    tool = MyTool()
    result = await tool.execute(param1="test", param2=20)
    assert "Processed test with param2=20" in result

@pytest.mark.asyncio
async def test_my_tool_interrupt():
    """Test tool respects interrupt token"""
    from swecli.core.interrupt.token import InterruptToken

    tool = MyTool()
    interrupt_token = InterruptToken()
    interrupt_token.set()

    context = ToolExecutionContext(interrupt_token=interrupt_token)
    result = await tool.execute(param1="test", context=context)

    assert "interrupted" in result.lower()
```

### Step 5: Document Tool

Add documentation to the tool's docstring:

```python
class MyTool:
    """
    My Custom Tool

    Processes input with custom logic.

    Usage:
        Tool: MyTool(param1="value", param2=10)

    Parameters:
        - param1 (string, required): Input value to process
        - param2 (number, optional): Processing parameter (default: 10)

    Returns:
        Processing result as string

    Example:
        Tool: MyTool(param1="hello", param2=5)
        Result: "Processed hello with param2=5"
    """
```

---

## Creating Custom Subagents

**Purpose**: Create specialized agents for specific tasks

### Step 1: Create Subagent Class

```python
# swecli/core/agents/subagents/agents/my_subagent.py
from typing import Optional
from swecli.core.agents.base_agent import BaseAgent

class MySubagent(BaseAgent):
    """Specialized agent for my specific task"""

    # Define allowed tools (read-only for safety)
    ALLOWED_TOOLS = [
        "Glob",
        "Grep",
        "Read",
        "WebFetch",
    ]

    def __init__(self, config, deps):
        super().__init__(config, deps)
        self.max_turns = 5  # Subagents typically have lower turn limits

    async def run(self, prompt: str) -> str:
        """
        Execute subagent task

        Args:
            prompt: Task description from parent agent

        Returns:
            Task result as string
        """
        # Create initial message
        self.session.add_message({
            "role": "user",
            "content": prompt
        })

        # Get specialized system prompt
        system_prompt = self._get_system_prompt()

        # ReAct loop
        for turn in range(self.max_turns):
            response = await self.llm_client.create_message(
                messages=self.session.messages,
                tools=self._get_allowed_tools(),
                system=system_prompt
            )

            if response.tool_calls:
                # Execute tools
                results = await self.tool_registry.execute_tools(
                    response.tool_calls
                )

                self.session.add_message({
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": response.tool_calls
                })

                for result in results:
                    self.session.add_message({
                        "role": "tool_result",
                        "content": result
                    })
            else:
                # Task complete
                return response.content

        return "Subagent max turns reached"

    def _get_system_prompt(self) -> str:
        """Get specialized system prompt for this subagent"""
        return """You are a specialized agent for [specific task].

Your goal: [Describe subagent purpose]

Tools available:
- Glob: Find files by pattern
- Grep: Search file contents
- Read: Read file contents
- WebFetch: Fetch web content

Guidelines:
- Focus on [specific task]
- Be thorough but concise
- Return results in [specific format]
"""

    def _get_allowed_tools(self) -> list:
        """Get tool schemas for allowed tools only"""
        all_tools = self.tool_registry.get_tool_schemas()
        return [t for t in all_tools if t["name"] in self.ALLOWED_TOOLS]
```

### Step 2: Register Subagent

```python
# swecli/core/agents/subagents/registry.py
from .agents.my_subagent import MySubagent

SUBAGENT_REGISTRY = {
    "code_explorer": CodeExplorer,
    "planner": Planner,
    "my_subagent": MySubagent,  # Register your subagent
}

def create_subagent(subagent_type: str, config, deps):
    """Create subagent instance"""
    if subagent_type not in SUBAGENT_REGISTRY:
        raise ValueError(f"Unknown subagent type: {subagent_type}")

    subagent_class = SUBAGENT_REGISTRY[subagent_type]
    return subagent_class(config, deps)
```

### Step 3: Use in Main Agent

```python
# Main agent delegates to subagent via Task tool
Tool: Task(
    subagent_type="my_subagent",
    prompt="Analyze the codebase for security vulnerabilities",
    description="Security analysis"
)
```

### Step 4: Write Tests

```python
# tests/test_my_subagent.py
@pytest.mark.asyncio
async def test_my_subagent():
    """Test subagent execution"""
    config = create_test_config()
    deps = create_test_deps()

    subagent = MySubagent(config, deps)
    result = await subagent.run("Test prompt")

    assert result  # Check result is non-empty
    assert len(subagent.session.messages) > 0  # Check messages were added
```

---

## Adding Prompt Sections

**Purpose**: Modify agent behavior with new instructions

### Step 1: Create Section Template

```markdown
# swecli/core/agents/prompts/templates/system/main/my-section.md

# My Custom Section

This section provides instructions for [specific feature or behavior].

## Key Guidelines

- Guideline 1: [Instruction]
- Guideline 2: [Instruction]
- Guideline 3: [Instruction]

## Examples

**Good**:
```example
[Good example]
```

**Bad**:
```example
[Bad example]
```

## Important Notes

**CRITICAL**: [Critical instruction that must be followed]

**IMPORTANT**: [Important but not critical instruction]
```

### Step 2: Register Section

```python
# swecli/core/agents/prompts/composition.py
class PromptComposer:
    def _register_sections(self):
        # ... existing sections

        self.register_section(
            name="my-section",
            template="my-section.md",
            priority=75,  # Choose appropriate priority (1-100)
            condition=lambda ctx: ctx.has_my_feature  # Optional condition
        )
```

### Step 3: Update Context (if conditional)

```python
# swecli/models/prompt_context.py
@dataclass
class PromptContext:
    # ... existing fields

    has_my_feature: bool = False  # Add your condition field
```

### Step 4: Test Section

```python
# tests/test_prompt_composition.py
def test_my_section_included():
    """Test section is included when condition met"""
    composer = PromptComposer(config)
    context = PromptContext(has_my_feature=True)
    prompt = composer.compose(context)

    assert "My Custom Section" in prompt

def test_my_section_excluded():
    """Test section is excluded when condition not met"""
    composer = PromptComposer(config)
    context = PromptContext(has_my_feature=False)
    prompt = composer.compose(context)

    assert "My Custom Section" not in prompt
```

---

## Implementing New UI Modes

**Purpose**: Add custom user interfaces (e.g., voice UI, mobile UI)

### Step 1: Create UI Implementation

```python
# swecli/ui_voice/voice_ui.py
class VoiceUI:
    """Voice-based UI implementation"""

    def __init__(self, agent):
        self.agent = agent
        self.callback = VoiceCallback(self)

    async def run(self):
        """Run voice UI loop"""
        print("Voice UI started. Say 'exit' to quit.")

        while True:
            # Record voice input
            audio = await self.record_audio()

            # Transcribe to text
            text = await self.transcribe(audio)

            if text.lower() == "exit":
                break

            # Process with agent
            response = await self.agent.run(text, ui_callback=self.callback)

            # Speak response
            await self.speak(response)

    async def record_audio(self):
        """Record audio from microphone"""
        # Implementation here
        pass

    async def transcribe(self, audio) -> str:
        """Transcribe audio to text"""
        # Use Whisper or similar
        pass

    async def speak(self, text: str):
        """Speak text using TTS"""
        # Use TTS engine
        pass
```

### Step 2: Create Callback Interface

```python
# swecli/ui_voice/voice_callback.py
class VoiceCallback:
    """Callback interface for voice UI"""

    def __init__(self, ui):
        self.ui = ui

    async def on_thinking_start(self):
        """Agent started thinking"""
        await self.ui.speak("Thinking...")

    async def on_tool_execution(self, tool_name: str, parameters: dict):
        """Agent executing tool"""
        await self.ui.speak(f"Executing {tool_name}")

    async def request_approval(self, operation: str) -> bool:
        """Request approval via voice"""
        await self.ui.speak(f"Approve {operation}? Say yes or no.")
        response = await self.ui.record_and_transcribe()
        return response.lower() in ["yes", "approve", "okay"]
```

### Step 3: Add CLI Entry Point

```python
# swecli/cli.py
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", choices=["tui", "web", "voice"], default="tui")

    args = parser.parse_args()

    if args.ui == "voice":
        from swecli.ui_voice.voice_ui import VoiceUI
        ui = VoiceUI(agent)
        asyncio.run(ui.run())
    elif args.ui == "web":
        # Web UI
        pass
    else:
        # TUI
        pass
```

---

## Extending Session Storage

**Purpose**: Implement alternative storage backends (SQLite, PostgreSQL, cloud)

### Step 1: Implement SessionManager Interface

```python
# swecli/core/context_engineering/history/sqlite_session_manager.py
import sqlite3
from typing import Optional

class SQLiteSessionManager:
    """SQLite-based session storage"""

    def __init__(self, db_path: str = "~/.opendev/sessions.db"):
        self.db_path = Path(db_path).expanduser()
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                metadata JSON
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP,
                tool_calls JSON,
                tool_call_id TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        conn.commit()
        conn.close()

    async def create_session(self) -> ChatSession:
        """Create new session"""
        session = ChatSession()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sessions (id, title, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session.id,
            session.title,
            session.created_at,
            session.updated_at,
            json.dumps(session.metadata)
        ))

        conn.commit()
        conn.close()

        return session

    async def save_session(self, session: ChatSession):
        """Save session to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Update session metadata
        cursor.execute("""
            UPDATE sessions
            SET title = ?, updated_at = ?, metadata = ?
            WHERE id = ?
        """, (
            session.title,
            session.updated_at,
            json.dumps(session.metadata),
            session.id
        ))

        # Save messages (delete existing, insert all)
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session.id,))

        for message in session.messages:
            cursor.execute("""
                INSERT INTO messages (session_id, role, content, timestamp, tool_calls, tool_call_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session.id,
                message["role"],
                message["content"],
                message.get("timestamp"),
                json.dumps(message.get("tool_calls")),
                message.get("tool_call_id")
            ))

        conn.commit()
        conn.close()

    async def load_session(self, session_id: str) -> ChatSession:
        """Load session from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Load session metadata
        cursor.execute("""
            SELECT title, created_at, updated_at, metadata
            FROM sessions
            WHERE id = ?
        """, (session_id,))

        row = cursor.fetchone()
        if not row:
            raise FileNotFoundError(f"Session {session_id} not found")

        title, created_at, updated_at, metadata = row

        # Load messages
        cursor.execute("""
            SELECT role, content, timestamp, tool_calls, tool_call_id
            FROM messages
            WHERE session_id = ?
            ORDER BY id
        """, (session_id,))

        messages = []
        for row in cursor.fetchall():
            role, content, timestamp, tool_calls, tool_call_id = row
            message = {
                "role": role,
                "content": content,
                "timestamp": timestamp
            }
            if tool_calls:
                message["tool_calls"] = json.loads(tool_calls)
            if tool_call_id:
                message["tool_call_id"] = tool_call_id

            messages.append(message)

        conn.close()

        return ChatSession(
            id=session_id,
            title=title,
            created_at=datetime.fromisoformat(created_at),
            updated_at=datetime.fromisoformat(updated_at),
            messages=ValidatedMessageList(messages),
            metadata=json.loads(metadata)
        )
```

### Step 2: Use Custom Storage

```python
# swecli/cli.py
from swecli.core.context_engineering.history.sqlite_session_manager import SQLiteSessionManager

# Use SQLite instead of file-based storage
session_manager = SQLiteSessionManager(db_path="~/.opendev/sessions.db")

deps = AgentDependencies(
    session_manager=session_manager,
    # ... other deps
)
```

---

## Adding MCP Servers

**Purpose**: Integrate external tool providers via MCP protocol

### Step 1: Add MCP Server

```bash
# Via CLI
opendev mcp add myserver uvx mcp-server-myserver --arg1 value1

# Or manually edit ~/.opendev/mcp/servers.json
{
  "myserver": {
    "command": "uvx",
    "args": ["mcp-server-myserver", "--arg1", "value1"],
    "env": {},
    "enabled": true
  }
}
```

### Step 2: Verify Tools

```bash
# List available MCP servers and tools
opendev mcp list

# Test server connection
opendev mcp test myserver
```

### Step 3: Use in Agent

```python
# Agent automatically discovers and uses MCP tools
# No code changes needed - tools appear in tool_registry

# Example: Agent uses MCP-provided SQLite tool
Tool: mcp_sqlite_query(
    query="SELECT * FROM users WHERE id = ?",
    params=[123]
)
```

---

## Custom Approval Handlers

**Purpose**: Implement custom approval logic (e.g., always approve for CI, external approval service)

### Step 1: Create Approval Handler

```python
# swecli/core/runtime/approval/custom_handler.py
class CustomApprovalHandler:
    """Custom approval logic"""

    async def requires_approval(
        self,
        tool_name: str,
        parameters: dict
    ) -> bool:
        """Determine if approval required"""
        # Custom logic here
        if tool_name == "Bash":
            command = parameters.get("command", "")
            # Example: Always approve git commands
            if command.startswith("git"):
                return False
            # Require approval for rm
            if "rm " in command:
                return True

        return False

    async def request_approval(
        self,
        tool_name: str,
        parameters: dict
    ) -> bool:
        """Request approval (custom implementation)"""
        # Example: Call external approval service
        response = await external_approval_service.request(
            tool=tool_name,
            params=parameters
        )
        return response["approved"]
```

### Step 2: Use Custom Handler

```python
# swecli/cli.py
approval_handler = CustomApprovalHandler()

deps = AgentDependencies(
    approval_manager=approval_handler,
    # ... other deps
)
```

---

## Adding Skills

**Purpose**: Create reusable command shortcuts

### Step 1: Create Skill File

```yaml
# ~/.opendev/skills/my-skill.yaml
name: my-skill
description: Description of what the skill does
version: 1.0.0

prompt: |
  This is the expanded prompt that gets injected when the skill is invoked.

  You can include:
  - Multi-line instructions
  - {{variables}} that get substituted
  - Detailed task descriptions

variables:
  target: "default value"
  option: "default option"

examples:
  - "/my-skill"
  - "/my-skill --target=custom --option=value"
```

### Step 2: Use Skill

```bash
# In chat
/my-skill

# With arguments
/my-skill --target=custom --option=value
```

### Step 3: Test Skill

```python
# tests/test_skills.py
from swecli.skills.loader import SkillLoader

def test_my_skill():
    """Test skill loading and expansion"""
    loader = SkillLoader()
    skill = loader.load_skill("my-skill")

    assert skill.name == "my-skill"
    assert "default value" in skill.prompt

    # Test variable substitution
    expanded = skill.expand(target="custom", option="value")
    assert "custom" in expanded
    assert "value" in expanded
```

---

## Summary

| Extension Point | Use Case | Key Files |
|----------------|----------|-----------|
| **Tools** | Add new capabilities | `implementations/`, `handlers/`, `registry.py` |
| **Subagents** | Specialized agents | `subagents/agents/`, `subagents/registry.py` |
| **Prompt Sections** | Modify behavior | `prompts/templates/system/main/` |
| **UI Modes** | New interfaces | `ui_*/` |
| **Storage** | Alternative backends | `history/session_manager.py` |
| **MCP Servers** | External tools | `~/.opendev/mcp/servers.json` |
| **Approval** | Custom logic | `runtime/approval/` |
| **Skills** | Command shortcuts | `~/.opendev/skills/` |

---

## Best Practices

1. **Follow existing patterns**: Study similar extensions before implementing
2. **Write tests**: All extensions should have tests
3. **Document well**: Add docstrings and examples
4. **Keep it simple**: Start with minimal implementation, add complexity as needed
5. **Respect invariants**: Don't break message pairing, approval flows, etc.

---

## Getting Help

- **Code examples**: See existing implementations in the codebase
- **Issues**: Report bugs or request features on GitHub
- **Documentation**: Refer to this design system documentation

---

**[← Back to Index](./00_INDEX.md)**
