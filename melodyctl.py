#!/usr/bin/env python3
"""Shim so `python3 melodyctl.py ...` keeps working in a checkout.

The implementation lives in the ``melodyctl/`` package; installed copies use
the ``melodyctl`` console script (``melodyctl.cli:main``).
"""

from melodyctl.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
