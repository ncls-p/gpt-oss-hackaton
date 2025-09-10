# GPT OSS Hackathon

A Python application demonstrating Clean Architecture principles with file operations and LLM integration. This project showcases proper separation of concerns, dependency inversion, and ports & adapters pattern for building maintainable and testable software.

## Features

- **File Operations**: List and search files in directories with natural language interfaces
- **LLM Integration**: Text generation capabilities using OpenAI's API
- **Clean Architecture**: Proper layered architecture with dependency inversion
- **Tool Integration**: LLM-powered file management tools
- **Comprehensive Testing**: Full test suite with pytest
- **HTTP API**: RESTful API endpoints for all functionality
- **Tools API + UI**: Tools-enabled assistant endpoint with a minimal web UI
- **System Controls**: New hardware/system tools (volume, brightness, idle, network, battery, processes)

## Installation

### Prerequisites

- Python 3.11 or higher (see [`.python-version`](.python-version))
- OpenAI API key (for LLM functionality)

### Setup (uv recommended)

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd gpt-oss-hackathon
   ```

2. **Install dependencies (uv recommended)**

   - With `uv` (recommended):

     ```bash
     uv sync
     ```

   - Pip alternative (if you don't want `uv`):
     ```bash
     python -m venv .venv
     source .venv/bin/activate  # Windows: .venv\Scripts\activate
     pip install -e .            # or: pip install -e ".[dev]"
     ```

3. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

## Usage

### Running the Application

The application can be used in two ways:

#### CLI Interface

Execute the main CLI entrypoint:

```bash
python src/main.py
```

This will run demonstrations of both file operations and LLM text generation capabilities.

#### HTTP API Server

Start the FastAPI server:

- With `uv` (recommended):

  ```bash
  uv run uvicorn src.main:app --reload
  ```

- With pip/active venv:
  ```bash
  uvicorn src.main:app --reload
  ```

The API will be available at `http://localhost:8000` and interactive documentation at `http://localhost:8000/docs`.
Additionally, a minimal tools UI is available at `http://localhost:8000/ui/tools`.

#### Desktop UI (Qt)

Run a native desktop interface (no browser required):

- With `uv` (recommended):

  ```bash
  uv run hack-ui
  ```

  (Direct alternative without console script: `uv run python -m src.ui.app`)

- With pip/active venv:
  ```bash
  hack-ui
  ```
  (Direct alternative: `python -m src.ui.app`)

Features:

- Prompt, system message, temperature, max tokens, tool steps, and “require final tool” toggle
- Run actions without blocking (background thread)
- Final assistant text viewer and a steps panel (double-click to inspect)
- Save results to JSON

### Examples

#### CLI Usage

##### File Operations

The application can list and search files in directories:

```bash
# List all files in a directory (demo CLI)
uv run python -m src.main
# Output: Lists files in ./src (depending on config)

# The application demonstrates:
# - Listing files with details (name, size, type)
# - Searching for specific file patterns (e.g., *.py files)
# - Proper error handling for file operations
```

##### Text Generation

The application includes LLM-powered text generation:

```bash
# Generate text with custom prompts
uv run python -m src.main
# Output: Generates haiku about programming and explains clean architecture

# Features demonstrated:
# - Basic text generation with temperature control
# - System message customization
# - Token limit management
# - Error handling for LLM operations
```

#### API Usage

##### List Files

```bash
curl -X GET "http://localhost:8000/files?directory=/path/to/directory"
```

Example response:

```json
{
  "files": [
    {
      "name": "example.py",
      "path": "/path/to/directory/example.py",
      "size_mb": 0.1,
      "type": "py"
    }
  ]
}
```

##### Search Files

```bash
curl -X GET "http://localhost:8000/files/search?directory=/path/to/directory&pattern=*.py"
```

For recursive search:

```bash
curl -X GET "http://localhost:8000/files/search?directory=/path/to/directory&pattern=*.py&recursive=true"
```

Example response:

```json
{
  "files": [
    {
      "name": "example.py",
      "path": "/path/to/directory/example.py",
      "size_mb": 0.1,
      "type": "py"
    }
  ]
}
```

##### Generate Text

```bash
curl -X POST "http://localhost:8000/generate-text" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write a haiku about programming",
    "temperature": 0.7,
    "max_tokens": 1000
  }'
```

With system message:

```bash
curl -X POST "http://localhost:8000/generate-text" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain clean architecture",
    "system_message": "You are a software architect",
    "temperature": 0.3,
    "max_tokens": 500
  }'
```

Example response:

```json
{
  "text": "Generated text content...",
  "model": "gpt-3.5-turbo",
  "provider": "openai"
}
```

##### Python Client Example

```python
import requests

# List files
response = requests.get("http://localhost:8000/files?directory=/path/to/directory")
files = response.json()["files"]

# Search files
response = requests.get("http://localhost:8000/files/search?directory=/path/to/directory&pattern=*.py")
matching_files = response.json()["files"]

# Generate text
response = requests.post(
    "http://localhost:8000/generate-text",
    json={"prompt": "Write a haiku about programming"}
)
generated_text = response.json()["text"]
```

##### Tools Assistant (LLM with function-calling)

POST to `/assistant/tools` to let the model call tools like file listing, file reading, opening applications, and opening URLs. The response includes the final text and a trace of tool invocations.

One-shot via CLI (uv):

```bash
uv run hack-tools --prompt "List what you can do" --steps 3 --final-required
```

**Complete Tools Catalog (Capabilities)**

Below is the exhaustive list of tools exposed by the app, grouped by domain.

- "Domain Selection": pick a working domain
  - `domain.list`: list available domains (files, apps, system, project, git, web)
  - `domain.files`: select the files domain (can chain a list/search via `directory`/`pattern`)
  - `domain.apps`: select the applications domain
  - `domain.system`: select the system domain
  - `domain.project`: select the project domain (search/read ranges)
  - `domain.git`: select the Git domain (read-only)
  - `domain.web`: select the web scraping domain
  - `domain.describe`: describe tools of the active domain (name, description, schema)
  - `domain.reset`: reset the active domain (back to top-level)

- "Files": file and directory management (with `HACK_WORKSPACE_ROOT` safety guard)
  - `files.list`: list files in a directory
  - `files.search`: search for files by pattern in a directory
  - `files.read`: read a text file (~100KB cap)
  - `files.head`: read the first N lines or bytes of a UTF-8 text file
  - `files.tail`: read the last N lines (approx.) of a UTF-8 text file
  - `files.read_range`: read an inclusive line range from a UTF-8 text file
  - `files.write`: create/overwrite a UTF-8 text file
  - `files.write_range`: replace an inclusive line range with provided content
  - `files.replace_line`: replace a single 1-based line
  - `files.insert_range`: insert a block before the given line (len+1 to append)
  - `files.append`: append text to a file (create if missing)
  - `files.find_replace`: find/replace (regex or fixed), with optional apply
  - `files.apply_patch`: apply a unified diff patch (best-effort, requires `patch`)
  - `files.diff_preview`: preview the unified diff for a `replace_ranges` (no write)
  - `files.replace_ranges`: replace multiple, non-overlapping line ranges
  - `files.copy`: copy a file or directory (dirs_exist_ok)
  - `files.move`: move/rename a file or directory
  - `files.copy_lines`: copy a 1-based inclusive line range to another file/position
  - `files.move_lines`: move a 1-based inclusive line range to another file/position
  - `files.delete`: delete a file or directory (optionally recursive)
  - `files.detect_encoding`: detect encoding (utf-8/16/32)
  - `files.json_patch`: apply an RFC6902 JSON Patch to a JSON file
  - `files.yaml_update`: update a YAML mapping via dot path (list indices supported)
  - `files.snapshot_create`: create a directory snapshot (path, size, mtime, optional sha1)
  - `files.snapshot_diff`: diff two snapshots (added/removed/changed)
  - `files.mkdir`: create a directory (parents included by default)

- "Project": code navigation (read-only and safe)
  - `project.search_text`: search text with include/exclude globs, regex or fixed (ripgrep if available)
  - `project.read_range`: read a line range from a UTF-8 text file (with byte cap)
  - `project.symbols_index`: build a lightweight index of Python symbols (classes/functions)
  - `project.find_refs`: find references (word-boundary match) for a symbol

- "Git" (read-only)
  - `git.status`: repository status (porcelain)
  - `git.diff`: unified diff (entire repo or a path, optionally staged)
  - `git.log`: recent commits (short format)
  - `git.show`: show a commit or a file at a commit (size cap)
  - `git.blame`: blame a file (optional range)
  - `git.branch_list`: list branches
  - `git.current_branch`: current branch

- "System": simple system actions (best-effort, platform-dependent)
  - `system.open_url`: open a URL in the default browser
  - `system.open_path`: open a file/folder with the default application
  - `system.exec_ro`: run an allowlisted read-only command (`ls`, `cat`, `rg`, `git`)
  - `system.exec_custom`: run a custom command (interactive CLI asks user confirmation)
  - `system.os_info`: OS and Python runtime info
  - `system.resources`: CPU, load average, disk, memory (total/available/used/percent, process RSS)
  - `system.screenshot`: take a PNG screenshot
  - `system.speak`: text-to-speech for a short text (if available)
  - `system.clipboard_set`: write text to the clipboard
  - `system.clipboard_get`: read text from the clipboard
  - `system.notify`: system notification (title + message)
  - `system.open_terminal`: open a terminal at a given directory
  - `system.set_volume`: set system output volume (0–100). macOS: AppleScript; Linux: `amixer`; Windows: WinMM.
  - `system.network_info`: basic network info (interfaces, IPs) via `ifconfig`/`ipconfig`.
  - `system.battery_info`: battery status (level/status). macOS: `pmset`; Linux: `/sys/class/power_supply`; Windows: `powercfg`.
  - `system.process_list`: list active processes (limited). macOS/Linux: `ps aux`; Windows: `tasklist`. Accepts `limit` (1–50).
  - `system.set_brightness`: adjust screen brightness (0.0–1.0). macOS: AppleScript; Linux: `xrandr`; Windows: not supported natively.
  - `system.set_idle`: enable/disable idle/sleep with `timeout` seconds. macOS: `pmset`; Linux: `xset`; Windows: `powercfg`.

- "Applications"
  - `application.open`: open an application by name, bundle id, or path (optional arguments)

- "Web": fetching and scraping (CSS selectors via selectolax)
  - `web.scrape`: fetch a page and extract content using a CSS selector (text/html/attr)
  - `web.links`: extract (text, href) pairs and resolve to absolute URLs
  - `web.fetch_json`: GET a JSON endpoint (UA/timeout/limits)
  - `web.post_json`: POST JSON and return parsed JSON response (limits)
  - `web.readability`: extract article-like main content + title (heuristic)
  - `web.download`: download a resource to a file (size cap)

- "Control" (run finalization)
  - `assistant.final` (+ aliases `final`, `json`, `assistant|channel>final`, `commentary`): signal completion and return `final_text`

Notes:
- "Files" tools enforce a safety boundary: paths constrained to `HACK_WORKSPACE_ROOT` (configurable), unless `HACK_WORKSPACE_ENFORCE=0`.
- Several tools have size guards (e.g., reads ~100KB, diffs/outputs ~20KB) for stability.
- Hardware/system controls are best-effort and platform-dependent; some require system utilities to be installed (`amixer`, `xrandr`, `xset`, etc.).

```bash
curl -X POST "http://localhost:8000/assistant/tools" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Open the Terminal application then read the file /etc/hosts",
    "system_message": "You are a computer assistant",
    "tool_max_steps": 2
  }'
```

Example response:

```json
{
  "text": "...final assistant message...",
  "steps": [
    {
      "name": "application.open",
      "arguments": { "app_info": "Terminal" },
      "result": "{...}"
    },
    {
      "name": "files.read",
      "arguments": { "path": "/etc/hosts" },
      "result": "{...}"
    }
  ]
}
```

Notes on multi-tool flows and finalization:

- The assistant can chain multiple tools in a single run.
- To explicitly end the loop, it should call the control tool `assistant.final` with a `final_text` field.
- When the Tools UI option “Require final tool” is enabled (default), normal assistant text alone does not end the run; the model must call `assistant.final`.



### Project Structure

The application follows Clean Architecture with these key components:

- **Entities** ([`src/entities/`](src/entities/)): Core business objects (File, LLM)
- **Use Cases** ([`src/use_cases/`](src/use_cases/)): Business logic and workflows
- **Ports** ([`src/ports/`](src/ports/)): Abstract interfaces for external dependencies
- **Adapters** ([`src/adapters/`](src/adapters/)): Concrete implementations (Local FS, OpenAI)
  - OpenAI tools adapter with composite registry (files, application, system)
- **Configuration** ([`src/config/`](src/config/)): Application settings and environment
- **Entry Point** ([`src/main.py`](src/main.py)): CLI interface and dependency injection

## Architecture

This project implements Clean Architecture principles with proper dependency inversion and separation of concerns. For detailed architectural documentation, see:

📖 **[Architecture Documentation](docs/ARCHITECTURE.md)**

The architecture documentation includes:

- Detailed layer descriptions
- Architecture diagrams
- Dependency flow explanations
- Design principles and benefits
- Testing strategies

## Testing

Run the test suite using [`pytest`](pytest.ini):

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test files
pytest tests/use_cases/files/test_list_files.py

# Run tests with verbose output
pytest -v
````

### Test Structure

Tests are organized to mirror the source structure:

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test interactions between layers
- **Configuration**: [`pytest.ini`](pytest.ini) and [`conftest.py`](tests/conftest.py)

## Dependencies

### Core Dependencies

- **openai**: OpenAI API integration for LLM functionality
- **python-dotenv**: Environment variable management
- **typing-extensions**: Enhanced type hints support
- **fastapi**: Modern, fast web framework for building APIs
- **uvicorn**: ASGI server for running FastAPI applications

### Development Dependencies

- **pytest**: Testing framework with coverage and mocking
- **basedpyright**: Static type checking
- **ruff**: Code formatting and linting
- **httpx**: HTTP client for testing API endpoints

See [`pyproject.toml`](pyproject.toml) for complete dependency specifications.

## Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes** following the existing architecture patterns
4. **Add tests** for new functionality
5. **Run the test suite**: `pytest`
6. **Run code quality checks**: `ruff check src tests`
7. **Submit a pull request**

### Development Guidelines

- Follow Clean Architecture principles
- Maintain proper separation of concerns
- Add comprehensive tests for new features
- Update documentation as needed
- Use type hints throughout the codebase

## License

This project is part of the GPT OSS Hackathon and is available for educational and demonstration purposes.
