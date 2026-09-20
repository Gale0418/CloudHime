"""Small, testable process boundaries for CloudHime's owned llama-server.

The child receives a per-launch key via its environment, never via argv or a
persistent key file. This does not hide memory/environment from a privileged
local debugger. No parent environment or unrelated process is modified.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
import os
from pathlib import Path
import re
import sys
from typing import Any

MAX_STDERR_LINE_CHARS = 4096
_OVERSIZED_LINE = "[oversized runtime stderr line omitted]\n"
_KEY = re.compile(r"[A-Za-z0-9._~-]{1,256}\Z")


def build_runtime_environment(key: str, inherited: Mapping[str, str] | None = None) -> dict[str, str]:
    """Keep OS/CUDA settings, but do not inherit llama tools/log/auth overrides."""
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError("runtime_key_invalid")
    source = os.environ if inherited is None else inherited
    environment = {name: value for name, value in source.items()
                   if not name.upper().startswith("LLAMA_")}
    environment["LLAMA_API_KEY"] = key
    # PyInstaller puts the C++ runtime beside Qt, not in its top-level DLL
    # directory. Add it only for our helper; never change the parent PATH or
    # process-wide SetDllDirectory state.
    bundle_root = getattr(sys, "_MEIPASS", None)
    if sys.platform == "win32" and getattr(sys, "frozen", False) and bundle_root:
        root = Path(bundle_root).resolve()
        qt_dir = (root / "PySide6").resolve()
        if qt_dir.parent == root and (qt_dir / "MSVCP140.dll").is_file():
            path_key = next((name for name in environment if name.upper() == "PATH"), "PATH")
            existing = environment.get(path_key, "")
            environment[path_key] = str(qt_dir) + (";" + existing if existing else "")
    return environment


def iter_redacted_stderr(stream: Any, key: str) -> Iterator[str]:
    """Read bounded lines; discard an oversized line rather than leak fragments.

    Production TextIO pipes always support readline(size). Iterator-only test
    transports are still accepted, but oversized values are never retained.
    """
    reader = getattr(stream, "readline", None)
    if callable(reader):
        discarding = False
        while True:
            line = reader(MAX_STDERR_LINE_CHARS + 1)
            if not line:
                return
            if not isinstance(line, str):
                raise TypeError("runtime_stderr_must_be_text")
            if discarding:
                discarding = not line.endswith("\n")
                continue
            if len(line) > MAX_STDERR_LINE_CHARS:
                discarding = not line.endswith("\n")
                yield _OVERSIZED_LINE
                continue
            yield (line.replace(key, "[REDACTED]") if key else line)[:MAX_STDERR_LINE_CHARS]
    else:
        for line in stream:
            if not isinstance(line, str):
                raise TypeError("runtime_stderr_must_be_text")
            if len(line) > MAX_STDERR_LINE_CHARS:
                yield _OVERSIZED_LINE
            else:
                yield (line.replace(key, "[REDACTED]") if key else line)[:MAX_STDERR_LINE_CHARS]


def terminate_and_reap(proc: Any, timeout: float) -> None:
    """Bounded terminate -> wait -> kill -> wait for this handle only.

    The drain thread owns and closes stderr: closing it here could deadlock on
    TextIO's read lock when a descendant still holds the pipe's write end.
    If both shutdown attempts fail, return without unbounded waiting or killing
    unrelated processes by name.
    """
    if proc is None:
        return
    reaped = False
    try:
        proc.terminate()
    except Exception:
        pass
    else:
        try:
            proc.wait(timeout=timeout)
            reaped = True
        except Exception:
            pass
    if not reaped:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=timeout)
            reaped = True
        except Exception:
            pass
