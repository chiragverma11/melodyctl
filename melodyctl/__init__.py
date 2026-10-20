"""melodyctl - CLI + protocol toolkit for HeyMelody-family earbuds.

Package layout:
  protocol.py   framing, command ids, capability tables, decoders (pure)
  transport.py  RFCOMM session (address, channel, connect, send/receive)
  errors.py     MelodyctlError + formatting
  cli.py        argparse surface and command handlers
  data/         generated device profiles (whitelist -> capabilities)

The console script points at ``melodyctl.cli:main``; ``melodyctl.py`` in the
repository root is a thin shim for running from a checkout.
"""

from .errors import MelodyctlError
from .protocol import *  # noqa: F401,F403
from .transport import ADDR_DEFAULT, Buds

__version__ = "1.5.2"
