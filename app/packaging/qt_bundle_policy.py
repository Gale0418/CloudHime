"""Keep the Widgets release free of unused Qt add-ons collected by hooks."""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath


# QtGui's platform-input/image plugins otherwise pull in Virtual Keyboard,
# QML/Quick and PDF. CloudHime does not use those plugins or Python modules.
UNUSED_QT_BINARIES = frozenset({
    "qtvirtualkeyboardplugin.dll", "qt6virtualkeyboard.dll", "qpdf.dll",
    "qt6pdf.dll", "qt6qml.dll", "qt6qmlmeta.dll", "qt6qmlmodels.dll",
    "qt6qmlworkerscript.dll", "qt6quick.dll",
})
REVIEWED_QT_LIBRARIES = frozenset({
    "qt6core.dll", "qt6gui.dll", "qt6network.dll", "qt6opengl.dll",
    "qt6svg.dll", "qt6widgets.dll",
})


def is_unused_qt_binary(entry: tuple) -> bool:
    destination = PurePosixPath(str(entry[0]).replace("\\", "/"))
    return destination.name.casefold() in UNUSED_QT_BINARIES


def verify_qt_bundle(dist: Path) -> list[str]:
    """Reject unused or newly introduced Qt libraries pending module review."""
    if not dist.is_dir():
        raise ValueError(f"Release dist directory not found: {dist}")
    rejected = []
    for path in dist.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.casefold()
        if name in UNUSED_QT_BINARIES or (
            name.startswith("qt6") and name.endswith(".dll")
            and name not in REVIEWED_QT_LIBRARIES
        ):
            rejected.append(path.relative_to(dist).as_posix())
    return sorted(rejected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    args = parser.parse_args()
    try:
        rejected = verify_qt_bundle(args.dist)
    except ValueError as exc:
        parser.error(str(exc))
    if rejected:
        print("Unreviewed/unused Qt binaries: " + ", ".join(rejected))
        return 1
    print("Qt module inventory passed (source delivery and Store terms are separate gates).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
