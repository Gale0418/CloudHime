"""Resolve logical corpus paths across the app and repository data roots."""
from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath


def resolve_corpus_path(
    source_root: str | Path,
    logical_path: str,
    *,
    map_app_example: bool = True,
) -> Path:
    """Resolve a safe relative corpus path, including a moved root-level example/.

    A checkout with the historical ``app/example`` layout continues to work.
    When ``app`` has moved next to the repository-level ``example`` directory,
    only logical ``example/...`` paths are redirected there.
    """
    if not isinstance(logical_path, str) or not logical_path or len(logical_path) > 1024:
        raise ValueError("Corpus path must be bounded, nonempty text")

    normalized = logical_path.replace("\\", "/")
    relative = PurePosixPath(normalized)
    windows_path = PureWindowsPath(logical_path)
    if (
        relative.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in relative.parts
        or ":" in normalized
    ):
        raise ValueError("Corpus path must stay inside the source checkout")
    parts = tuple(part for part in relative.parts if part not in {"", "."})
    if not parts:
        raise ValueError("Corpus path must identify a file")

    root = Path(source_root).resolve()
    containment_root = root
    path_root = root
    if (
        map_app_example
        and root.name.casefold() == "app"
        and parts[0] == "example"
        and (root.parent / "example").exists()
    ):
        path_root = root.parent
        containment_root = (root.parent / "example").resolve()
        if not containment_root.is_relative_to(root.parent):
            raise ValueError("Corpus symlink escapes the permitted corpus root")

    target = path_root.joinpath(*parts).resolve()
    if not target.is_relative_to(containment_root):
        raise ValueError("Corpus symlink escapes the permitted corpus root")
    return target
