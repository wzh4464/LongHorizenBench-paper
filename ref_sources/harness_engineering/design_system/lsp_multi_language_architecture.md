# LSP Multi-Language Architecture

## Overview

The system provides semantic code analysis - symbol lookup, reference finding, rename refactoring, and structural editing - across 30+ programming languages through a unified API built on the Language Server Protocol (LSP). Rather than implementing language-specific parsers, the system delegates analysis to standard language servers (Pyright, typescript-language-server, rust-analyzer, gopls, etc.) and exposes their capabilities through a layered abstraction.

Three design goals shape the architecture:

- **Language-agnostic tool interface.** The agent's tools (`find_symbol`, `find_referencing_symbols`, `rename_symbol`, etc.) accept a file path and a symbol name. Language detection, server selection, and protocol translation happen transparently below the tool layer.

- **On-demand server lifecycle.** Language servers are started only when a file of that language is first queried, and shut down gracefully when no longer needed. A session analyzing only Python files never starts the TypeScript or Rust servers.

- **Two-level caching.** Raw LSP responses and processed symbol trees are cached independently, keyed by file content hash. Repeated queries against unchanged files skip both the LSP round-trip and the post-processing step.


## End-to-End Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AGENT TOOL LAYER                                 │
│                                                                         │
│  ┌────────────┐ ┌──────────────────┐ ┌──────────────┐ ┌─────────────┐ │
│  │find_symbol │ │find_referencing  │ │rename_symbol │ │replace_     │ │
│  │            │ │_symbols          │ │              │ │symbol_body  │ │
│  └─────┬──────┘ └────────┬─────────┘ └──────┬───────┘ └──────┬──────┘ │
│        │                 │                   │                │        │
│  ┌─────┴──────┐ ┌────────┴──────┐            │                │        │
│  │insert_     │ │insert_        │            │                │        │
│  │before_     │ │after_         │            │                │        │
│  │symbol      │ │symbol         │            │                │        │
│  └─────┬──────┘ └────────┬──────┘            │                │        │
└────────┼─────────────────┼───────────────────┼────────────────┼────────┘
         │                 │                   │                │
         ▼                 ▼                   ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      SYMBOL RETRIEVER (retriever.py)                     │
│                                                                         │
│  Unified API for all symbol operations:                                  │
│  • find_symbol(pattern, file_path?)    → list[Symbol]                   │
│  • find_references_by_name(name, file) → list[Location]                 │
│  • rename_symbol_by_name(name, file, new_name) → WorkspaceEdit          │
│  • find_symbol_at_position(file, line, col) → Symbol                    │
│  • get_document_symbols(file)          → list[Symbol]                   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    LSP SERVER WRAPPER (wrapper.py)                        │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Language Detection                                                │   │
│  │                                                                   │   │
│  │  file_path → extension → _EXTENSION_TO_LANGUAGE → Language enum   │   │
│  │                                                                   │   │
│  │  .py → PYTHON    .ts/.tsx/.js → TYPESCRIPT    .rs → RUST         │   │
│  │  .go → GO        .java → JAVA                 .kt → KOTLIN      │   │
│  │  .rb → RUBY      .cpp/.cc/.h → CPP            .cs → CSHARP      │   │
│  │  .dart → DART    .php → PHP    .ex → ELIXIR   .hs → HASKELL     │   │
│  │  .swift → SWIFT  .zig → ZIG    .lua → LUA     .sh → BASH        │   │
│  │  .scala → SCALA  .jl → JULIA   .r → R         .pl → PERL        │   │
│  │  ... (30+ languages)                                              │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Per-Language Server Pool                                          │   │
│  │                                                                   │   │
│  │  _servers: dict[Language, SolidLanguageServer]                    │   │
│  │                                                                   │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │   │
│  │  │ Pyright  │ │TS Server │ │  gopls   │ │ rust-    │  ...       │   │
│  │  │ (Python) │ │ (TS/JS)  │ │  (Go)    │ │ analyzer │           │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │   │
│  │                                                                   │   │
│  │  Lazy init: server created on first query for that language       │   │
│  │  Singleton: one server per language, reused across queries        │   │
│  │  Liveliness: checked before each use, recreated if terminated     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Symbol Conversion                                                 │   │
│  │                                                                   │   │
│  │  UnifiedSymbolInformation  ──convert──▶  Symbol                   │   │
│  │  (LSP-internal format)                   (agent-facing format)    │   │
│  │                                                                   │   │
│  │  Recursive child processing, range extraction, body preview       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               SOLID LANGUAGE SERVER (ls.py)                               │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Two-Level Cache                                                   │   │
│  │                                                                   │   │
│  │  Level 1: Raw Document Symbols                                    │   │
│  │  ┌─────────────────────────────────────────────┐                 │   │
│  │  │ Key: relative_file_path                      │                 │   │
│  │  │ Value: (content_hash, raw_lsp_response)      │                 │   │
│  │  │ Storage: .solidlsp/cache/<lang>/             │                 │   │
│  │  │          raw_document_symbols.pkl             │                 │   │
│  │  │ Invalidation: MD5(file_content) mismatch     │                 │   │
│  │  └─────────────────────────────────────────────┘                 │   │
│  │                                                                   │   │
│  │  Level 2: Processed Symbol Trees                                  │   │
│  │  ┌─────────────────────────────────────────────┐                 │   │
│  │  │ Key: relative_file_path                      │                 │   │
│  │  │ Value: (content_hash, DocumentSymbols)       │                 │   │
│  │  │ Storage: .solidlsp/cache/<lang>/             │                 │   │
│  │  │          document_symbols.pkl                 │                 │   │
│  │  │ Invalidation: hash mismatch OR version bump  │                 │   │
│  │  └─────────────────────────────────────────────┘                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ File Buffer Management                                            │   │
│  │                                                                   │   │
│  │  LSPFileBuffer per open file:                                     │   │
│  │  • URI, contents, version, language_id                            │   │
│  │  • Reference counting (open/close)                                │   │
│  │  • Content hash for cache validation                              │   │
│  │  • didOpen on first ref, didClose on last deref                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ LSP Protocol Operations                                           │   │
│  │                                                                   │   │
│  │  textDocument/documentSymbol → list[DocumentSymbol]               │   │
│  │  textDocument/definition     → list[Location]                     │   │
│  │  textDocument/references     → list[Location]                     │   │
│  │  textDocument/rename         → WorkspaceEdit                      │   │
│  │  workspace/symbol            → list[SymbolInformation]            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ File Ignore System                                                │   │
│  │                                                                   │   │
│  │  pathspec.PathSpec with GitWildMatchPattern                       │   │
│  │  • is_ignored_dirname(): ".", "node_modules", "venv", etc.        │   │
│  │  • is_ignored_path(): gitignore-style path matching               │   │
│  │  • Per-language overrides (Python adds __pycache__, venv)         │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│             LANGUAGE SERVER HANDLER (ls_handler.py)                       │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Subprocess Management                                             │   │
│  │                                                                   │   │
│  │  start():                                                         │   │
│  │    subprocess.Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)    │   │
│  │    spawn daemon thread → _read_ls_process_stdout()                │   │
│  │    spawn daemon thread → _read_ls_process_stderr()                │   │
│  │    start_new_session=True (independent process group)             │   │
│  │                                                                   │   │
│  │  stop():                                                          │   │
│  │    Stage 1: LSP shutdown request + exit notification              │   │
│  │    Stage 2: process.terminate()                                   │   │
│  │    Stage 3: wait(timeout) → process.kill() if hung               │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ JSON-RPC 2.0 Communication                                        │   │
│  │                                                                   │   │
│  │  send_request(method, params):                                    │   │
│  │    1. Generate request ID (thread-safe counter)                   │   │
│  │    2. Register Request in _pending_requests                       │   │
│  │    3. Write JSON-RPC message to stdin (lock-protected)            │   │
│  │    4. Block on Request.get_result(timeout)                        │   │
│  │                                                                   │   │
│  │  _read_ls_process_stdout():                                       │   │
│  │    loop:                                                          │   │
│  │      1. Read "Content-Length: N\r\n\r\n" header                   │   │
│  │      2. Read N bytes as JSON body                                 │   │
│  │      3. Route: response → _response_handler()                     │   │
│  │             notification → on_notification_handlers                │   │
│  │             request → on_request_handlers                         │   │
│  │                                                                   │   │
│  │  _response_handler(response):                                     │   │
│  │    Match response.id to _pending_requests                         │   │
│  │    Set result on matching Request (unblocks caller)               │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Thread Safety                                                     │   │
│  │                                                                   │   │
│  │  _stdin_lock: protects writes to server's stdin                   │   │
│  │  _request_id_lock: protects ID counter increment                  │   │
│  │  _response_handlers_lock: protects pending requests dict          │   │
│  │  _tasks_lock: protects background task tracking                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```


## Data Structures

### Symbol

The `Symbol` class (`lsp/symbol.py`) is the agent-facing representation of a code element:

```
Symbol
├── name: str                    ("my_function")
├── kind: SymbolKind             (FUNCTION, CLASS, METHOD, VARIABLE, ...)
├── file_path: str               ("/repo/src/main.py")
├── start_line: int              (0-indexed)
├── start_character: int
├── end_line: int
├── end_character: int
├── container_name: str | None   ("MyClass" if method)
├── children: list[Symbol]       (nested symbols)
├── parent: Symbol | None        (enclosing symbol)
└── name_path: str (computed)    ("MyClass.my_function")
```

`SymbolKind` is an enum with 26 values matching the LSP specification: FILE, MODULE, NAMESPACE, PACKAGE, CLASS, INTERFACE, ENUM, STRUCT, FUNCTION, METHOD, PROPERTY, FIELD, CONSTRUCTOR, VARIABLE, CONSTANT, STRING, NUMBER, BOOLEAN, ARRAY, OBJECT, KEY, NULL, ENUMMEMBER, EVENT, OPERATOR, TYPEPARAMETER. The `is_container()` method distinguishes symbols that can have children (CLASS, MODULE, etc.) from leaf symbols (VARIABLE, CONSTANT, etc.).

### NamePathMatcher

Pattern matching for symbol lookup (`lsp/symbol.py`). Supports three matching modes:

- **Exact match:** `"MyClass.method"` matches only that specific path.
- **Partial path:** `"method"` matches any symbol whose name path ends with `".method"` - so `"pkg.MyClass.method"` matches.
- **Wildcards:** `"My*"` matches `"MyClass"`, `"MyModule"`, `"MyFactory"` via `fnmatch` glob patterns.

### DocumentSymbols

Internal container (`ls.py`) wrapping the root symbol list returned by a document symbol request. Provides `iter_symbols()` for depth-first traversal and caches flattened symbol lists for repeated access.

### LSPFileBuffer

Tracks open files at the protocol level (`ls.py`). Each buffer carries a URI, content string, version counter, language ID, reference count, and content hash (MD5). Reference counting ensures `didOpen` is sent on first access and `didClose` on last release.


## Language Detection and Server Selection

When a tool receives a file path, the wrapper resolves the language through a static extension-to-language mapping (`wrapper.py:24-75`). The mapping covers 30+ extensions:

| Extensions | Language | Server |
|-----------|----------|--------|
| `.py` | PYTHON | Pyright |
| `.ts`, `.tsx`, `.js`, `.jsx` | TYPESCRIPT | typescript-language-server |
| `.rs` | RUST | rust-analyzer |
| `.go` | GO | gopls |
| `.java` | JAVA | Eclipse JDT.LS |
| `.kt` | KOTLIN | kotlin-language-server |
| `.cs` | CSHARP | OmniSharp |
| `.rb` | RUBY | Solargraph / ruby-lsp |
| `.dart` | DART | dart analysis-server |
| `.cpp`, `.cc`, `.h`, `.hpp` | CPP | clangd |
| `.php` | PHP | intelephense |
| `.ex`, `.exs` | ELIXIR | elixir-ls |
| `.hs` | HASKELL | haskell-language-server |
| `.swift` | SWIFT | sourcekit-lsp |
| `.zig` | ZIG | zls |
| `.lua` | LUA | lua-language-server |
| `.sh`, `.bash` | BASH | bash-language-server |
| `.scala` | SCALA | metals |
| `.jl` | JULIA | LanguageServer.jl |
| `.r`, `.R` | R | languageserver |
| `.pl`, `.pm` | PERL | PerlNavigator |

Each language maps to a concrete server class via `Language.get_ls_class()`, which dynamically imports the class from the `language_servers/` directory. This factory pattern allows adding new languages by dropping in a new server class without modifying the core framework.


## Per-Language Server Customization

Every language server extends `SolidLanguageServer` with language-specific overrides:

```
SolidLanguageServer (base)
    │
    ├── PyrightServer (Python)
    │     └── is_ignored_dirname(): adds "venv", "__pycache__"
    │
    ├── TypeScriptLanguageServer (TypeScript/JavaScript)
    │     └── is_ignored_dirname(): adds "node_modules"
    │
    ├── RustAnalyzer (Rust)
    │     └── Custom initialization options (cargo features, etc.)
    │
    ├── Gopls (Go)
    │     └── Custom initialization options (build flags, etc.)
    │
    ├── EclipseJDTLS (Java)
    │     └── Complex initialization (workspace setup, classpath)
    │
    └── ... (30+ language implementations)
```

**Customization points available to each server:**

- `_start_server()` - Language-specific initialization sequence
- `is_ignored_dirname(dirname)` - Directories to skip (e.g., `venv` for Python, `node_modules` for TypeScript)
- `_get_wait_time_for_cross_file_referencing()` - How long to wait for the server to index before cross-file queries
- `_determine_log_level(message)` - Classify server stderr output as debug, info, warning, or error
- `_send_references_request()` - Language-specific workarounds for reference-finding edge cases
- Custom LSP initialization parameters (capabilities, workspace settings, exclude patterns)


## Two-Level Cache

```
Query: get_document_symbols("/repo/src/main.py")
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  Level 2 Cache Check (Processed Symbol Trees)             │
│                                                           │
│  Key: "src/main.py"                                       │
│  Stored: (content_hash, DocumentSymbols)                  │
│  File: .solidlsp/cache/python/document_symbols.pkl        │
│                                                           │
│  if hash(current_content) == stored_hash:                 │
│      return cached DocumentSymbols    ◄── FAST PATH       │
│  else:                                                    │
│      ▼                                                    │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  Level 1 Cache Check (Raw LSP Responses)                  │
│                                                           │
│  Key: "src/main.py"                                       │
│  Stored: (content_hash, raw_lsp_symbols)                  │
│  File: .solidlsp/cache/python/raw_document_symbols.pkl    │
│                                                           │
│  if hash(current_content) == stored_hash:                 │
│      raw_symbols = cached     ◄── SKIP LSP CALL           │
│  else:                                                    │
│      raw_symbols = server.send.document_symbol()          │
│      update Level 1 cache                                 │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  Symbol Post-Processing                                   │
│                                                           │
│  For each raw symbol:                                     │
│    1. Extract range, selection range (with fallbacks)      │
│    2. Retrieve symbol body from file content               │
│    3. Build parent-child relationships                     │
│    4. Handle overload indices for same-name siblings       │
│    5. Convert to UnifiedSymbolInformation                  │
│                                                           │
│  Update Level 2 cache                                     │
│  Return DocumentSymbols                                   │
└──────────────────────────────────────────────────────────┘
```

**Cache invalidation** is content-based: the MD5 hash of the file content is compared against the stored hash. If the file has not changed, the cached result is returned without contacting the language server. If the file changed but the raw LSP response format has not changed (no version bump), only Level 2 is recomputed from the cached Level 1 data.

**Cache storage** uses pickle serialization in the project's `.solidlsp/cache/<language_id>/` directory. A version field in each cache file ensures that caches from incompatible schema versions are discarded rather than producing errors.


## JSON-RPC Communication

The handler (`ls_handler.py`) manages the subprocess and JSON-RPC 2.0 protocol:

```
┌──────────────────────────┐         ┌──────────────────────────┐
│      Caller Thread        │         │   Language Server Process │
│                           │         │                          │
│  send_request(method,     │  stdin  │                          │
│               params)     │ ──────▶ │  Receives JSON-RPC msg   │
│                           │         │  Processes request        │
│  Block on                 │         │                          │
│  Request.get_result()     │  stdout │                          │
│          ▲                │ ◀────── │  Sends JSON-RPC response  │
│          │                │         │                          │
│  Reader thread matches    │         │                          │
│  response.id → Request    │         │                          │
│  and unblocks caller      │         │                          │
└──────────────────────────┘         └──────────────────────────┘

Message format (JSON-RPC 2.0 over stdio):
  Header:  "Content-Length: N\r\n\r\n"
  Body:    {"jsonrpc": "2.0", "id": 1, "method": "textDocument/definition", "params": {...}}
  Response: {"jsonrpc": "2.0", "id": 1, "result": [...]}
```

**Thread model:**

- Two daemon threads per server: one reading stdout (parses JSON-RPC responses and routes them to waiting callers), one reading stderr (classifies log output by severity).
- Request IDs are generated by a thread-safe counter. Each `send_request()` call registers a `Request` object in `_pending_requests`, writes the JSON-RPC message to stdin under a lock, and blocks until the reader thread sets the result.
- Configurable per-request timeout prevents indefinite waits on hung servers.


## Query Data Flow

A complete example tracing `find_referencing_symbols("my_function", file_path="/repo/src/main.py")`:

```
1. Tool Layer (find_referencing_symbols.py)
   │  Receives arguments: symbol_name, file_path, include_declaration
   │  Creates SymbolRetriever(workspace_root)
   │
   ▼
2. SymbolRetriever.find_references_by_name() (retriever.py)
   │  Step A: find_symbol("my_function", "/repo/src/main.py")
   │          → NamePathMatcher matches against document symbols
   │          → Returns Symbol with start_line=41, start_character=4
   │
   │  Step B: find_references("/repo/src/main.py", line=41, character=4)
   │
   ▼
3. LSPServerWrapper.find_references() (wrapper.py)
   │  get_language_from_path(".py") → Language.PYTHON
   │  get_server(PYTHON) → PyrightServer (lazy init if first use)
   │
   ▼
4. SolidLanguageServer.request_references() (ls.py)
   │  open_file("src/main.py") → LSPFileBuffer (ref_count++)
   │  Wait for LS initialization if needed
   │  _send_references_request(relative_path, line=41, col=4)
   │
   ▼
5. Handler.send_request("textDocument/references", params) (ls_handler.py)
   │  Generate request ID = 7
   │  Register Request(id=7) in _pending_requests
   │  Write JSON-RPC to stdin:
   │    {"jsonrpc":"2.0","id":7,"method":"textDocument/references",
   │     "params":{"textDocument":{"uri":"file:///repo/src/main.py"},
   │              "position":{"line":41,"character":4},
   │              "context":{"includeDeclaration":true}}}
   │  Block on Request(7).get_result(timeout=30)
   │
   ▼
6. Language Server Process (Pyright)
   │  Analyzes Python source, finds all references
   │  Returns JSON-RPC response with locations
   │
   ▼
7. Reader Thread (_read_ls_process_stdout)
   │  Parses response, matches id=7
   │  Sets result on Request(7) → unblocks caller
   │
   ▼
8. Back in ls.py
   │  Convert URIs to absolute paths
   │  Filter by is_ignored_path() (exclude venv/, __pycache__/)
   │  Close file buffer (ref_count--)
   │  Return list[Location]
   │
   ▼
9. Back in wrapper.py
   │  Format each Location as {file, line (1-indexed), character, end_line, end_character}
   │
   ▼
10. Back in find_referencing_symbols.py
    │  Group references by file
    │  Read code snippets for each reference location
    │  Format output:
    │    "Found 5 reference(s) to 'my_function' across 3 files"
    │    Per-file groups with line numbers and code context
    │
    ▼
11. Return to ToolRegistry → Agent receives formatted result
```


## Server Lifecycle

```
┌──────────────────────────────────────────────────────────────┐
│                    Server Lifecycle                            │
│                                                               │
│  IDLE ──first query──▶ STARTING ──initialized──▶ RUNNING     │
│                           │                         │         │
│                           │                    query/query     │
│                           │                         │         │
│                           │                         ▼         │
│                           │                      RUNNING      │
│                           │                         │         │
│                           │                   terminated?     │
│                           │                    /        \     │
│                           │                  no          yes  │
│                           │                  │            │   │
│                           │                  ▼            ▼   │
│                           │               RUNNING    STOPPED  │
│                           │                            │      │
│                           │                  next query │      │
│                           │                            ▼      │
│                           └─────────────────────── STARTING   │
│                                                               │
│  Shutdown sequence (graceful):                                │
│    1. Send LSP shutdown request + exit notification            │
│    2. Close stdin                                             │
│    3. process.terminate()                                     │
│    4. Wait 2 seconds → process.kill() if still alive          │
│    5. Close stdout/stderr pipes                               │
└──────────────────────────────────────────────────────────────┘
```

Servers are singleton per language within a wrapper instance. The wrapper checks `is_running()` before each use. If a server has terminated (crash, timeout), the next query recreates it transparently - the caller never sees the restart.


## Symbol Tools

Six tools expose LSP capabilities to the agent:

### Read-Only Tools

| Tool | Purpose | Arguments | Output |
|------|---------|-----------|--------|
| `find_symbol` | Locate symbol definitions | `symbol_name` (pattern), `file_path` (optional) | List of symbols with kind, file, line, preview |
| `find_referencing_symbols` | Find all usages of a symbol | `symbol_name`, `file_path` (required), `include_declaration` | References grouped by file with code snippets |

### Write Tools

| Tool | Purpose | Arguments | Output |
|------|---------|-----------|--------|
| `rename_symbol` | Rename across codebase | `symbol_name`, `file_path`, `new_name` | Files modified with edit counts |
| `replace_symbol_body` | Replace implementation | `symbol_name`, `file_path`, `new_body`, `preserve_signature` | Updated file content |
| `insert_before_symbol` | Insert code before | `symbol_name`, `file_path`, `content` | Code inserted with indentation |
| `insert_after_symbol` | Insert code after | `symbol_name`, `file_path`, `content` | Code inserted with indentation |

**Identifier validation** (`rename_symbol.py`): New names must start with a letter or underscore and contain only alphanumeric characters or underscores. This validation covers most languages.

**Signature preservation** (`replace_symbol_body.py`): When `preserve_signature=True` (default), the tool detects the body boundary - colon for Python, opening brace for C-like languages - and replaces only the body while keeping the signature, decorators, and docstring intact.

**Edit ordering** (`rename_symbol.py`): When a rename produces edits across multiple locations in the same file, edits are sorted in reverse order (bottom-to-top) so that earlier edits do not shift the line numbers of later ones.


## Error Handling

```
SolidLSPException
├── cause: Exception | None
├── is_language_server_terminated() → bool
└── get_affected_language() → Language | None

LanguageServerTerminatedException
├── language: Language
└── cause: Exception | None
```

When a language server process terminates unexpectedly:

1. The stdout reader thread detects EOF and raises `LanguageServerTerminatedException`.
2. All pending requests for that server are cancelled (their callers receive the exception).
3. The exception propagates to the wrapper, which marks the server as stopped.
4. The next query for that language triggers a fresh server creation.

At the tool level, symbol tools catch exceptions and return structured error responses (`{"success": False, "error": "..."}`) rather than propagating raw exceptions to the agent.


## Key Files Reference

| Component | File Path | Key Elements |
|-----------|-----------|-------------|
| LSP Wrapper | `core/context_engineering/tools/lsp/wrapper.py` | `LSPServerWrapper`, `get_lsp_wrapper()`, `_EXTENSION_TO_LANGUAGE` |
| Symbol Retriever | `core/context_engineering/tools/lsp/retriever.py` | `SymbolRetriever`, `find_symbol()`, `find_references_by_name()` |
| Symbol Data | `core/context_engineering/tools/lsp/symbol.py` | `Symbol`, `SymbolKind`, `NamePathMatcher` |
| Language Server Base | `core/context_engineering/tools/lsp/ls.py` | `SolidLanguageServer`, `DocumentSymbols`, `LSPFileBuffer` |
| Server Handler | `core/context_engineering/tools/lsp/ls_handler.py` | `SolidLanguageServerHandler`, `Request`, JSON-RPC communication |
| Language Config | `core/context_engineering/tools/lsp/ls_config.py` | `Language` enum (30+ values), `LanguageServerConfig` |
| LSP Types | `core/context_engineering/tools/lsp/ls_types.py` | `UnifiedSymbolInformation`, `Location`, `Position`, `Range` |
| Settings | `core/context_engineering/tools/lsp/settings.py` | `SolidLSPSettings`, cache paths, per-language settings |
| Exceptions | `core/context_engineering/tools/lsp/ls_exceptions.py` | `SolidLSPException`, `LanguageServerTerminatedException` |
| find_symbol Tool | `core/context_engineering/tools/symbol_tools/find_symbol.py` | `handle_find_symbol()` |
| find_references Tool | `core/context_engineering/tools/symbol_tools/find_referencing_symbols.py` | `handle_find_referencing_symbols()` |
| replace_body Tool | `core/context_engineering/tools/symbol_tools/replace_symbol_body.py` | `handle_replace_symbol_body()`, `_find_body_start()` |
| rename Tool | `core/context_engineering/tools/symbol_tools/rename_symbol.py` | `handle_rename_symbol()`, `_apply_edit()` |
| insert Tool | `core/context_engineering/tools/symbol_tools/insert_symbol.py` | `handle_insert_before_symbol()`, `handle_insert_after_symbol()` |
| Language Servers | `core/context_engineering/tools/lsp/language_servers/` | Per-language `SolidLanguageServer` subclasses |
