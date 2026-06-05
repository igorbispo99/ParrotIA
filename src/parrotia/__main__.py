"""Allow ``python -m parrotia`` to run the headless CLI."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
