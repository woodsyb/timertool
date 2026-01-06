# Project Rules

## CRITICAL: Python Environment

**ALWAYS use `uv` for ALL Python operations. NEVER use bare `python`, `python3`, `pip`, or `pip3` commands.**

- Run scripts: `uv run python script.py`
- Run modules: `uv run python -m module`
- Install packages: `uv add package` or `uv pip install package`
- Run tests: `uv run pytest`

This is a Windows desktop app (Tkinter) - tkinter is not available outside the uv-managed environment.
