"""Allow `python -m yinv`."""

from yinv.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
