"""Run a fail-closed functional smoke against a frozen CloudHime runtime."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Mapping

from local_vision_assets import VisionAssets
from vision_smoke_benchmark import run_smoke


PROJECT_ROOT = Path(__file__).resolve().parent
RUNTIME_MANIFEST_NAME = "runtime-manifest.json"
MIN_SERVER_BYTES = 4_096
MIN_MODEL_BYTES = 1_048_576
MIN_PROJECTOR_BYTES = 1_048_576
_FORBIDDEN_MARKERS = ("placeholder", "fixture", "fake")


class ReleaseSmokeError(RuntimeError):
    """Raised when a release smoke input is not a real, verifiable artifact."""


def _load_runtime_manifest_validator():
    module_path = PROJECT_ROOT / "packaging" / "runtime_manifest.py"
    spec = importlib.util.spec_from_file_location(
        "cloudhime_runtime_manifest_for_smoke", module_path
    )
    if spec is None or spec.loader is None:
        raise ReleaseSmokeError(f"runtime manifest validator is unavailable: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_manifest


_validate_manifest = _load_runtime_manifest_validator()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_file(path: Path, *, label: str, minimum_bytes: int = 1) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ReleaseSmokeError(f"{label}_missing: {resolved}")
    if resolved.stat().st_size < minimum_bytes:
        raise ReleaseSmokeError(
            f"{label}_too_small: {resolved} ({resolved.stat().st_size} < {minimum_bytes})"
        )
    return resolved


def validate_release_inputs(
    runtime_dir: str | Path,
    model_path: str | Path,
    projector_path: str | Path,
    image_path: str | Path,
) -> VisionAssets:
    runtime = Path(runtime_dir).expanduser().resolve()
    if not runtime.is_dir():
        raise ReleaseSmokeError(f"runtime_dir_missing: {runtime}")

    server = _required_file(
        runtime / "llama-server.exe",
        label="server",
        minimum_bytes=MIN_SERVER_BYTES,
    )
    manifest_path = runtime / RUNTIME_MANIFEST_NAME
    if not manifest_path.is_file():
        raise ReleaseSmokeError(f"runtime_manifest_missing: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _validate_manifest(runtime, manifest)
    except Exception as exc:
        raise ReleaseSmokeError(f"runtime_manifest_invalid: {exc}") from exc

    version = str(manifest.get("server", {}).get("version", "")).casefold()
    build_source = str(manifest.get("build", {}).get("source_commit", "")).casefold()
    for marker in _FORBIDDEN_MARKERS:
        if marker in version or marker in build_source:
            raise ReleaseSmokeError(
                f"runtime_manifest_placeholder_rejected: marker={marker}"
            )

    model = _required_file(
        Path(model_path), label="model", minimum_bytes=MIN_MODEL_BYTES
    )
    projector = _required_file(
        Path(projector_path), label="projector", minimum_bytes=MIN_PROJECTOR_BYTES
    )
    image = _required_file(Path(image_path), label="image")
    return VisionAssets(
        server_path=server,
        model_path=model,
        projector_path=projector,
    )


def _functional_complete(result: Mapping[str, Any]) -> bool:
    image_count = int(result.get("image_count", 0) or 0)
    case_count = int(result.get("case_count", 0) or 0)
    image_results = list(result.get("image_results", []))
    if (
        str(result.get("evaluation_mode") or "") != "technical_coverage"
        or image_count <= 0
        or len(image_results) != image_count
        or int(result.get("request_success_images", 0) or 0) != image_count
        or int(result.get("request_success_cases", 0) or 0) != case_count
        or int(result.get("successful_images", 0) or 0) != image_count
        or int(result.get("successful_cases", 0) or 0) != case_count
    ):
        return False
    return all(
        str(item.get("actual") or "").strip() and not str(item.get("error") or "").strip()
        for item in image_results
    )


def run_release_smoke(
    runtime_dir: str | Path,
    model_path: str | Path,
    projector_path: str | Path,
    image_path: str | Path,
    *,
    require_gpu: bool = False,
    force_cpu: bool = False,
    timeout_seconds: int = 120,
    startup_timeout_seconds: int = 90,
    context_size: int = 4096,
    gpu_layers: int = 999,
) -> dict[str, Any]:
    image = Path(image_path).expanduser().resolve()
    assets = validate_release_inputs(runtime_dir, model_path, projector_path, image)
    temporary = PROJECT_ROOT / f".tmp-release-functional-{uuid.uuid4().hex}"
    temporary.mkdir()
    try:
        manifest_path = temporary / "functional-smoke.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "evaluation_mode": "technical_coverage",
                    "cases": [{
                        "sample_source": str(image),
                        "category": "release_functional_smoke",
                    }],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = run_smoke(
            manifest_path,
            max_cases=1,
            timeout_seconds=timeout_seconds,
            startup_timeout_seconds=startup_timeout_seconds,
            context_size=context_size,
            gpu_layers=gpu_layers,
            require_gpu=require_gpu,
            force_cpu=force_cpu,
            assets=assets,
            image_root=image.parent,
        )
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    if not _functional_complete(result):
        raise ReleaseSmokeError(
            "functional_smoke_failed: runtime or image request did not produce non-empty output"
        )
    result = dict(result)
    result["manifest"] = "generated_ephemeral"
    return result


def _configure_stdout_for_unicode() -> None:
    stream = sys.stdout
    reconfigure = getattr(stream, "reconfigure", None)
    encoding = str(getattr(stream, "encoding", "") or "").lower().replace("-", "")
    if not callable(reconfigure) or encoding in {"utf8", "utf8sig"}:
        return
    try:
        reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, OSError, ValueError):
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CloudHime frozen runtime functional vision smoke"
    )
    parser.add_argument("--runtime-dir", required=True, type=Path)
    parser.add_argument("--model", "--model-path", dest="model_path", required=True, type=Path)
    parser.add_argument(
        "--projector", "--projector-path", dest="projector_path", required=True, type=Path
    )
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--require-gpu", action="store_true")
    parser.add_argument("--force-cpu", action="store_true")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--startup-timeout", type=int, default=90)
    parser.add_argument("--context-size", type=int, default=4096)
    parser.add_argument("--gpu-layers", type=int, default=999)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.validate_only:
            assets = validate_release_inputs(
                args.runtime_dir,
                args.model_path,
                args.projector_path,
                args.image,
            )
            _configure_stdout_for_unicode()
            payload = {
                "validation": "passed",
                "server": str(assets.server_path),
                "model": str(assets.model_path),
                "projector": str(assets.projector_path),
                "image": str(args.image.expanduser().resolve()),
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print("Release functional smoke inputs passed.")
            return 0
        result = run_release_smoke(
            args.runtime_dir,
            args.model_path,
            args.projector_path,
            args.image,
            require_gpu=args.require_gpu,
            force_cpu=args.force_cpu,
            timeout_seconds=args.timeout,
            startup_timeout_seconds=args.startup_timeout,
            context_size=args.context_size,
            gpu_layers=args.gpu_layers,
        )
    except (OSError, ValueError, ReleaseSmokeError) as exc:
        print(f"release functional smoke failed: {exc}", file=sys.stderr)
        return 2
    _configure_stdout_for_unicode()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            "Release functional smoke passed: "
            f"mode={result.get('runtime_mode')} images={result.get('successful_images')}/"
            f"{result.get('image_count')} requests={result.get('request_success_images')}/"
            f"{result.get('image_count')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
