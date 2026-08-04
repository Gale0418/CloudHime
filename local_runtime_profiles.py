"""Immutable launch profiles for the single local llama-server runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RuntimeProfileName = Literal["text", "vision"]
ALL_RUNTIME_ASSET_FIELDS = ("server_path", "model_path", "projector_path")


@dataclass(frozen=True)
class LocalRuntimeProfile:
    name: RuntimeProfileName
    required_asset_fields: tuple[str, ...]

    @property
    def requires_projector(self) -> bool:
        return "projector_path" in self.required_asset_fields


TEXT_RUNTIME_PROFILE = LocalRuntimeProfile(
    name="text",
    required_asset_fields=("server_path", "model_path"),
)
VISION_RUNTIME_PROFILE = LocalRuntimeProfile(
    name="vision",
    required_asset_fields=ALL_RUNTIME_ASSET_FIELDS,
)


def resolve_runtime_profile(profile: LocalRuntimeProfile | str | None) -> LocalRuntimeProfile:
    if profile is None:
        return VISION_RUNTIME_PROFILE
    if isinstance(profile, LocalRuntimeProfile):
        return profile
    normalized = str(profile).strip().lower()
    if normalized == "text":
        return TEXT_RUNTIME_PROFILE
    if normalized == "vision":
        return VISION_RUNTIME_PROFILE
    raise ValueError(f"unsupported_runtime_profile: {profile}")
