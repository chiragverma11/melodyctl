"""Error types and formatting: MelodyctlError + classify_error/emit_error."""
from __future__ import annotations

import json
import sys

from .protocol import _ERRNO_HINTS


class MelodyctlError(Exception):
    """A user-facing failure carrying a stable code and an optional hint."""

    def __init__(self, message: str, code: str = "error", hint: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint

# ---- command ids (little-endian on the wire) --------------------------------
def classify_error(exc: BaseException) -> tuple[str, str]:
    """Map an exception to a stable (code, hint) pair."""
    if isinstance(exc, MelodyctlError):
        return (exc.code, exc.hint)
    if isinstance(exc, AttributeError) and "AF_BLUETOOTH" in str(exc):
        return ("no_bluetooth_support",
                "Install melodyctl with a system Python "
                "(uv tool install --python /usr/bin/python3 ...).")
    if isinstance(exc, TimeoutError):
        return _ERRNO_HINTS[110]
    err = getattr(exc, "errno", None)
    if err in _ERRNO_HINTS:
        return _ERRNO_HINTS[err]
    return ("error", "")


def emit_error(exc: BaseException, json_mode: bool) -> None:
    """Print one clean line - or a JSON object under --json - describing a failure."""
    code, hint = classify_error(exc)
    message = getattr(exc, "strerror", None) or str(exc) or exc.__class__.__name__
    if not json_mode:
        print(f"error: {message}", file=sys.stderr)
        if hint:
            print(f"hint:  {hint}", file=sys.stderr)
        return
    err: dict[str, str] = {"code": code, "message": message}
    if hint:
        err["hint"] = hint
    print(json.dumps({"error": err}), file=sys.stderr)


