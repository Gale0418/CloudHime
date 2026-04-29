from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


POLL_INTERVAL_SECONDS = 2.0
SYNC_TIMEOUT_SECONDS = 30.0
WATCHED_FILES = (
    "project.md",
    "progress.md",
    "tasks.md",
)


def file_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_mtime_ns, stat.st_size


def snapshot(paths: tuple[Path, ...]) -> dict[str, tuple[int, int] | None]:
    return {str(path): file_signature(path) for path in paths}


def sync_visual_state(repo_root: Path) -> int:
    sync_script = repo_root / "MissionCenter" / "sync_visual_state.py"
    try:
        result = subprocess.run(
            [sys.executable, str(sync_script)],
            cwd=repo_root,
            check=False,
            timeout=SYNC_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(f"Sync timed out after {SYNC_TIMEOUT_SECONDS:.0f}s.")
        return 124
    return result.returncode


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    mission_dir = repo_root / "MissionCenter"
    watched_paths = tuple(mission_dir / name for name in WATCHED_FILES)

    print("MissionCenter watcher started.")
    print("Watching: " + ", ".join(path.name for path in watched_paths))

    last_snapshot = None
    while True:
        current_snapshot = snapshot(watched_paths)
        if current_snapshot != last_snapshot:
            code = sync_visual_state(repo_root)
            if code == 0:
                print("Synced visual state.")
            else:
                print(f"Sync failed with exit code {code}.")
            last_snapshot = current_snapshot
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
