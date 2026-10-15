#!/usr/bin/env python3
"""Search, plan, and write our recipes. Run with --help for the commands."""

import sys

try:
    import yaml  # noqa: F401
except ImportError:
    sys.exit("recipes needs PyYAML: `pip install pyyaml`, or run it with `uv run --with pyyaml`")

from cookbook.cli import main

if __name__ == "__main__":
    sys.exit(main())
