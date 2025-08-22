# GPT OSS Hackathon

A Python application demonstrating Clean Architecture principles with file operations and LLM integration. This project showcases proper separation of concerns, dependency inversion, and ports & adapters pattern for building maintainable and testable software.

## Features

- **File Operations**: List and search files in directories with natural language interfaces
- **LLM Integration**: Text generation capabilities using OpenAI's API
- **Clean Architecture**: Proper layered architecture with dependency inversion
- **Tool Integration**: LLM-powered file management tools
- **Comprehensive Testing**: Full test suite with pytest
- **HTTP API**: RESTful API endpoints for all functionality

## Installation

### Prerequisites

- Python 3.11 or higher (see [`.python-version`](.python-version))
- OpenAI API key (for LLM functionality)

### Setup

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd gpt-oss-hackathon
   ```

2. **Create and activate a virtual environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:

   Using pip (from [`pyproject.toml`](pyproject.toml)):

   ```bash
   pip install -e .
   ```

   For development dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

   Alternatively, if you have `uv` installed (recommended for faster dependency resolution):

   ```bash
   uv sync
   ```

4. **Configure environment variables**:
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

```bash
uv run uvicorn src.main:app --reload
```

The API will be available at `http://localhost:8000` and interactive documentation at `http://localhost:8000/docs`.

### Examples

#### CLI Usage

##### File Operations

The application can list and search files in directories:

```python
# List all files in a directory
python src/main.py
# Output: Lists files in /Users/ncls/work/perso/gpt-oss-hackaton/src

# The application demonstrates:
# - Listing files with details (name, size, type)
# - Searching for specific file patterns (e.g., *.py files)
# - Proper error handling for file operations
```

##### Text Generation

The application includes LLM-powered text generation:

```python
# Generate text with custom prompts
python src/main.py
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

### Project Structure

The application follows Clean Architecture with these key components:

- **Entities** ([`src/entities/`](src/entities/)): Core business objects (File, LLM)
- **Use Cases** ([`src/use_cases/`](src/use_cases/)): Business logic and workflows
- **Ports** ([`src/ports/`](src/ports/)): Abstract interfaces for external dependencies
- **Adapters** ([`src/adapters/`](src/adapters/)): Concrete implementations (Local FS, OpenAI)
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
```

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
