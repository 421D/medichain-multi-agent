"""Project-root pytest config.

The `testpaths = ["tests"]` setting in pyproject.toml already restricts
the default `pytest` invocation to the `tests/` directory. This file
covers the *explicit* `pytest .` case: it tells pytest to ignore the
root-level entry points (demo script, research MCP server), which
are CLI tools rather than pytest cases.

Real pytest cases live in `tests/`.
"""
collect_ignore_glob = [
    "test_*.py",          # ad-hoc dev scripts at project root
    "demo_*.py",
    "run_*.py",
    "mcp_server.py",      # research MCP server, run as a subprocess via `python -m`
]
