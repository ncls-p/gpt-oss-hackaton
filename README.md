# gpt-oss-hackathon

Small demo project showing a filesystem-listing use case with an LLM adapter.

This repo provides two modes to produce directory listings:

- a direct `ls`-style use case (`LsUseCase`) that expects an `ls`-like command
- a natural-language use case (`NaturalLanguageListUseCase`) that uses function-calling with an LLM to interpret freeform queries

The entrypoint is `main.py` which wires adapters and the chosen use case together.

## Requirements

- Python 3.11+
- An OpenAI API key if you want to use the LLM-enabled flows (set `OPENAI_API_KEY` in your environment or a `.env` file).

Dependencies are declared in `pyproject.toml` and include `openai` and `python-dotenv`.

## Install

Create a virtual environment and install the package in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

If you prefer not to install in editable mode, you can also install the requirements listed in `pyproject.toml` using your preferred tool.

## Configuration

Create a `.env` file at the project root or export the variable directly in your shell:

```bash
export OPENAI_API_KEY="sk-..."
# or in a .env file:
# OPENAI_API_KEY=sk-...
```

`main.py` attempts to load a `.env` automatically if `python-dotenv` is available.

## Usage

Run the CLI directly with a traditional `ls`-like command:

```bash
python main.py ls -la /path/to/dir
```

Or provide a natural language query (either by passing `--nl` or by omitting an `ls` prefix):

```bash
python main.py --nl "show me python files in the current directory"
# or
python main.py "what are the largest files here?"
```

If no arguments are provided, `main.py` will prompt you for input interactively.

Notes:

- The `--nl` flag forces natural-language processing.
- The implementation lives under the `gpt_oss_hackathon` package; adapters are in `gpt_oss_hackathon/adapters` and use cases in `gpt_oss_hackathon/usecases.py`.

## Running tests

Run the unit tests with pytest:

```bash
python -m pytest -q
```

There is a focused test in `tests/test_ls_usecase.py` which validates the listing use case behavior.

## Contributing

Small, focused PRs are welcome. Please include a test for any behavior you add or change.

## Further improvements

- Add more adapters and examples.
- Add CI that runs the test suite and lints.

---

Happy hacking!
