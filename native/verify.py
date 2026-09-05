"""Explicit offline local gate; never installs a toolchain or invokes Actions."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rustup = shutil.which("rustup")
    if rustup is None:
        print("BLOCKED: rustup and installed Rust 1.98.1 are required; nothing was downloaded.", file=sys.stderr)
        return 2
    prefix = [rustup, "run", "1.98.1"]  # No --install: missing toolchains fail closed.
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(root / "native" / "target")
    commands = [
        [*prefix, "cargo", "fmt", "--manifest-path", "native/Cargo.toml", "--", "--check"],
        [*prefix, "cargo", "test", "--manifest-path", "native/Cargo.toml", "--locked", "--offline"],
        [*prefix, "cargo", "clippy", "--manifest-path", "native/Cargo.toml", "--all-targets", "--locked", "--offline", "--", "-D", "warnings"],
        [*prefix, "cargo", "build", "--manifest-path", "native/Cargo.toml", "--release", "--locked", "--offline"],
    ]
    try:
        version = subprocess.run(
            [*prefix, "rustc", "--version"], cwd=root, env=env, check=True,
            capture_output=True, text=True, timeout=30,
        )
        if version.stdout.split()[:2] != ["rustc", "1.98.1"]:
            print("BLOCKED: installed compiler is not exactly Rust 1.98.1.", file=sys.stderr)
            return 2
        print(version.stdout.strip())
        for command in commands:
            subprocess.run(command, cwd=root, env=env, check=True, timeout=300)
        env["CLOUDHIME_NATIVE_FRAME_METRICS"] = "1"
        subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests/test_native_frame_metrics.py", "-k", "compiled"],
            cwd=root, env=env, check=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Native verification did not pass: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
