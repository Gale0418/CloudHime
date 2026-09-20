"""完整／輕量包的模型契約與 ZIP64 封裝；不連網、不自行取得模型。"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_vision_assets import GEMMA_ASSET_MANIFEST

LICENSE_ROOT = Path(__file__).resolve().parent / "model-licenses"
LICENSE_NAMES = ("NOTICE.txt", "MODEL-USE-TERMS.txt", "GEMMA-TERMS.html", "GEMMA-PROHIBITED-USE.html")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_model(path, spec):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != spec.size:
        raise ValueError(f"Model size/type mismatch: {path}")
    if sha256(path) != spec.sha256:
        raise ValueError(f"Model SHA256 mismatch: {path}")


def stage_models(dist, source):
    """只接受固定 revision 的兩個資產；不覆寫既有模型目錄。"""
    dist, source = Path(dist).resolve(), Path(source).resolve()
    internal = dist / "_internal"
    if not (dist / "CloudHime.exe").is_file() or not internal.is_dir():
        raise ValueError("Not a frozen CloudHime distribution")
    for spec in GEMMA_ASSET_MANIFEST:
        check_model(source / spec.name, spec)
    for name in LICENSE_NAMES:
        if not (LICENSE_ROOT / name).is_file():
            raise ValueError(f"Missing model terms: {name}")
    target = internal / "models"
    target.mkdir(exist_ok=False)
    for spec in GEMMA_ASSET_MANIFEST:
        shutil.copy2(source / spec.name, target / spec.name)
    for name in LICENSE_NAMES:
        shutil.copy2(LICENSE_ROOT / name, target / name)
    verify_models(dist, "full")


def verify_models(dist, flavor="auto"):
    dist = Path(dist).resolve()
    model_root = dist / "_internal" / "models"
    expected = {model_root / spec.name for spec in GEMMA_ASSET_MANIFEST}
    found = {p for p in dist.rglob("*") if p.is_file() and
             (".gguf" in p.name.lower() or p.name.lower().startswith("mmproj"))}
    if flavor == "auto":
        flavor = "full" if found else "light"
    if flavor == "light":
        if found:
            raise ValueError("Light release must not bundle model/projector files")
        return 0
    if found != expected:
        raise ValueError("Full release requires exactly the pinned model and projector")
    for spec in GEMMA_ASSET_MANIFEST:
        check_model(model_root / spec.name, spec)
    for name in LICENSE_NAMES:
        supplied = model_root / name
        if not supplied.is_file() or sha256(supplied) != sha256(LICENSE_ROOT / name):
            raise ValueError(f"Missing or changed model terms: {name}")
    return len(expected)


def create_archive(dist, output):
    dist, output = Path(dist).resolve(), Path(output).resolve()
    if output == dist or dist in output.parents:
        raise ValueError("Archive must be outside the distribution")
    files = sorted(p for p in dist.rglob("*") if p.is_file())
    if not files:
        raise ValueError("Empty distribution")
    if any(p.is_symlink() or dist not in p.resolve().parents for p in files):
        raise ValueError("Distribution must not contain linked external files")
    # Exclusive creation protects previous release archives; ZIP64 handles GGUF >2GB.
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as archive:
        for path in files:
            archive.write(path, path.relative_to(dist).as_posix())


def create_upload_archive(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file() or source == output:
        raise ValueError("Upload archive requires a separate existing MSIX file")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as archive:
        archive.write(source, source.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("stage", "verify", "zip", "zip-upload"))
    parser.add_argument("--dist", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--flavor", choices=("auto", "light", "full"), default="auto")
    args = parser.parse_args()
    if args.command == "zip-upload":
        if args.source is None or args.output is None:
            parser.error("zip-upload requires --source and --output")
        create_upload_archive(args.source, args.output)
        return
    if args.dist is None:
        parser.error("--dist is required")
    if args.command == "stage":
        if args.source is None:
            parser.error("stage requires --source")
        stage_models(args.dist, args.source)
    elif args.command == "verify":
        print(verify_models(args.dist, args.flavor))
    else:
        if args.output is None:
            parser.error("zip requires --output")
        verify_models(args.dist, args.flavor)
        create_archive(args.dist, args.output)


if __name__ == "__main__":
    main()
