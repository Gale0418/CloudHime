from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass
from typing import Any

import localization


SETTINGS_SCHEMA_VERSION = 5
SETTINGS_FILENAME = "cloudhime_settings.json"
SETTINGS_APP_DIR = "CloudHime"
RELIEF_OFFSET_MIN = -500
RELIEF_OFFSET_MAX = 500
ACTIVE_WORK_TITLE_MAX = 240

GEMMA_MODEL_ALIASES = {
    "translategemma-4b-it-local": "gemma-3-4b-it-local",
    "gemma-4-26b-it": "gemma-4-26b-a4b-it",
    "gemma-3-1b-it": "gemma-4-31b-it",
    "gemma-3-27b-it": "gemma-4-31b-it",
}
LOCAL_MULTIMODAL_MODEL_ALIASES = {
    "translategemma-4b-it-local": "gemma-3-4b-it-local",
}


@dataclass(frozen=True)
class SettingsPaths:
    appdata_file: str
    legacy_file: str


def create_settings_paths(script_dir: str, appdata_root: str | None = None) -> SettingsPaths:
    appdata_base = appdata_root or os.getenv("APPDATA") or os.path.expanduser("~")
    settings_dir = os.path.join(appdata_base, SETTINGS_APP_DIR)
    appdata_file = os.path.join(settings_dir, SETTINGS_FILENAME)
    legacy_file = os.path.join(script_dir, SETTINGS_FILENAME)
    return SettingsPaths(appdata_file=appdata_file, legacy_file=legacy_file)


def appdata_companion_path(paths: SettingsPaths, filename: str) -> str:
    return os.path.join(os.path.dirname(paths.appdata_file), filename)


def load_settings_data(paths: SettingsPaths) -> tuple[dict[str, Any], str | None]:
    # AppData is canonical whenever it contains a valid settings object.
    for settings_path in (paths.appdata_file, paths.legacy_file):
        try:
            with open(settings_path, "r", encoding="utf-8") as fp:
                payload = json.load(fp)
            if isinstance(payload, dict):
                return payload, settings_path
        except Exception:
            continue
    return {}, None

def save_settings_data(paths: SettingsPaths, payload: dict[str, Any]) -> None:
    target = paths.appdata_file
    target_dir = os.path.dirname(target)
    os.makedirs(target_dir, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=target_dir or None, prefix=".cloudhime-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temp_path, target)
    except Exception:
        try:
            os.remove(temp_path)
        except Exception:
            pass
        raise

def should_migrate_to_appdata(paths: SettingsPaths, loaded_from_path: str | None) -> bool:
    return loaded_from_path == paths.legacy_file or not os.path.exists(paths.appdata_file)


def extract_backend_chain(settings: dict[str, Any]) -> Any:
    return settings.get("ocr_backend_chain", settings.get("ocr_backends", None))


def clamp_percent(value: Any, fallback: int = 40) -> int:
    try:
        numeric = int(value)
    except Exception:
        numeric = int(fallback)
    return max(0, min(100, numeric))


def clamp_local_gemma_temperature(value: Any, fallback: float = 0.2) -> float:
    try:
        numeric = float(value)
    except Exception:
        numeric = float(fallback)
    if not math.isfinite(numeric):
        numeric = float(fallback)
    return max(0.0, min(1.0, numeric))


def clamp_local_gemma_repeat_penalty(value: Any, fallback: float = 1.15) -> float:
    try:
        numeric = float(value)
    except Exception:
        numeric = float(fallback)
    if not math.isfinite(numeric):
        numeric = float(fallback)
    return max(1.0, min(2.0, numeric))


def clamp_local_multimodal_timeout(value: Any, fallback: int = 20) -> int:
    try:
        numeric = int(value)
    except Exception:
        numeric = int(fallback)
    return max(1, min(300, numeric))


def clamp_relief_offset(value: Any, fallback: int = 0) -> int:
    try:
        numeric = int(value)
    except Exception:
        numeric = int(fallback)
    return max(RELIEF_OFFSET_MIN, min(RELIEF_OFFSET_MAX, numeric))


def resolve_relief_offsets(settings: dict[str, Any]) -> tuple[int, int]:
    return (
        clamp_relief_offset(settings.get("region_relief_offset_x", 0)),
        clamp_relief_offset(settings.get("region_relief_offset_y", 0)),
    )


def resolve_region_opacity(settings: dict[str, Any], fallback: int = 40) -> int:
    # Canonical: region_relief_opacity. Legacy alias: region_frame_opacity.
    if "region_relief_opacity" in settings:
        return clamp_percent(settings.get("region_relief_opacity"), fallback)
    if "region_frame_opacity" in settings:
        return clamp_percent(settings.get("region_frame_opacity"), fallback)
    return clamp_percent(fallback, fallback)


def resolve_ui_language(settings: dict[str, Any], fallback: str = localization.DEFAULT_UI_LANGUAGE) -> str:
    return localization.normalize_ui_language(settings.get("ui_language", fallback), fallback=fallback)


def coerce_bool(value: Any, fallback: bool = False) -> bool:
    """Parse persisted booleans without treating the string "false" as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value in (0, 1):
            return bool(value)
        return fallback
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "on", "1"}:
            return True
        if normalized in {"false", "no", "off", "0", ""}:
            return False
    return fallback

def normalize_settings_payload(
    payload: dict[str, Any],
    region_opacity: int,
    ui_language: str | None = None,
) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["schema_version"] = SETTINGS_SCHEMA_VERSION
    opacity = clamp_percent(region_opacity, 40)
    offset_x, offset_y = resolve_relief_offsets(normalized)
    normalized["region_relief_offset_x"] = offset_x
    normalized["region_relief_offset_y"] = offset_y
    normalized.pop("region_relief_side", None)
    normalized.pop("region_relief_gap_px", None)
    normalized["region_relief_opacity"] = opacity
    normalized["region_frame_opacity"] = opacity
    active_work_title = normalized.get("active_work_title", "")
    normalized["active_work_title"] = (
        " ".join(active_work_title.split())[:ACTIVE_WORK_TITLE_MAX]
        if isinstance(active_work_title, str)
        else ""
    )
    normalized["ui_language"] = localization.normalize_ui_language(
        ui_language if ui_language is not None else normalized.get("ui_language", localization.DEFAULT_UI_LANGUAGE),
        fallback=localization.DEFAULT_UI_LANGUAGE,
    )
    normalized["local_gemma_temperature"] = clamp_local_gemma_temperature(normalized.get("local_gemma_temperature", 0.2))
    normalized["local_gemma_repeat_penalty"] = clamp_local_gemma_repeat_penalty(normalized.get("local_gemma_repeat_penalty", 1.15))
    normalized["local_multimodal_enabled"] = coerce_bool(normalized.get("local_multimodal_enabled", False))
    normalized["local_multimodal_cpu_only"] = coerce_bool(normalized.get("local_multimodal_cpu_only", False))
    normalized["japanese_ocr_rescue_enabled"] = coerce_bool(normalized.get("japanese_ocr_rescue_enabled", False))
    normalized["local_multimodal_base_url"] = str(normalized.get("local_multimodal_base_url", "http://127.0.0.1:8080/v1") or "http://127.0.0.1:8080/v1")
    if "gemma_model" in normalized:
        gemma_model = normalized["gemma_model"]
        normalized["gemma_model"] = GEMMA_MODEL_ALIASES.get(gemma_model, gemma_model)
    local_multimodal_model = str(normalized.get("local_multimodal_model", "") or "")
    normalized["local_multimodal_model"] = LOCAL_MULTIMODAL_MODEL_ALIASES.get(
        local_multimodal_model,
        local_multimodal_model,
    )
    normalized["local_multimodal_timeout_seconds"] = clamp_local_multimodal_timeout(
        normalized.get("local_multimodal_timeout_seconds", 20)
    )
    return normalized
