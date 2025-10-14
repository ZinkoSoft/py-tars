from __future__ import annotations

from .service import main as _main


def main() -> None:
    """Run the LLM worker service."""

    raise SystemExit(_main())


if __name__ == "__main__":  # pragma: no cover - module entry point
    main()
