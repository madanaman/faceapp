# Contributing

Thanks for taking a look at Local Face Photos. This project is early and intentionally local-first.

## Ground Rules

- Do not upload private photo libraries, face crops, SQLite databases, or unredacted personal paths in issues or pull requests.
- Prefer synthetic media or heavily anonymized screenshots when reporting UI bugs.
- Keep changes focused and covered by the lightweight tests where possible.

## Development Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the app:

```sh
make run
```

Run checks:

```sh
make check
```

You can use a custom Python interpreter:

```sh
PYTHON_BIN=/path/to/python make check
```

## Pull Requests

Good pull requests usually include:

- a concise description of the behavior change
- screenshots for UI changes, using non-private media
- focused tests for bug fixes or parsing/filtering behavior
- notes about any new environment variables or generated files

Heavy InsightFace model/runtime tests are not required in CI. If your change affects detection quality or scan performance, include notes from a small local test folder.
