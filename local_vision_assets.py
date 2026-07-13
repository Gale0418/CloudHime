"""
local_vision_assets.py
-----------------------
Task 1：真機資產契約 – 視覺資產路徑解析與驗證。

職責：
- 以應用程式 root 解析 llama-server.exe、主模型與 projector 的絕對路徑。
- 驗證資產存在、大小符合下限，以及選用的 SHA-256 完整性。
- 完全不依賴 current working directory。
- 不啟動任何外部程序，不執行網路請求。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# 常數
# ──────────────────────────────────────────────────────────────────────────────

_SERVER_REL = Path("runtime") / "llama-server.exe"
_MODEL_REL = Path("models") / "gemma-3-4b-it.Q4_K_M.gguf"
_PROJECTOR_REL = Path("models") / "mmproj-model-f16.gguf"

# SHA-256 流式計算的讀取塊大小（8 MiB）
_SHA256_CHUNK_BYTES = 8 * 1024 * 1024

# 各資產生產環境最低大小（bytes）；可 import 供 LocalVisionRuntime 使用
# server launcher > 5 KB, model > 2 GB, projector > 800 MB
ASSET_MINIMUM_BYTES: dict[str, int] = {
    "server_path": 5_000,
    "model_path": 2_000_000_000,
    "projector_path": 800_000_000,
}


# ──────────────────────────────────────────────────────────────────────────────
# 例外
# ──────────────────────────────────────────────────────────────────────────────


class VisionAssetError(Exception):
    """資產驗證失敗的統一例外。

    Parameters
    ----------
    code:
        機器可讀的錯誤代碼，例如 ``"asset_missing"``、``"asset_too_small"``、
        ``"asset_sha256_mismatch"``。
    path:
        發生錯誤的資產路徑。
    detail:
        附加的人類可讀描述（選用）。
    """

    def __init__(self, code: str, *, path: Path, detail: str = "") -> None:
        self.code = code
        self.path = path
        self.detail = detail
        super().__init__(self._format())

    def _format(self) -> str:
        msg = f"{self.code}: {self.path}"
        if self.detail:
            msg += f" ({self.detail})"
        return msg


# ──────────────────────────────────────────────────────────────────────────────
# 資產資料類別
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class VisionAssets:
    """三個必要資產的絕對路徑容器（唯讀）。

    Attributes
    ----------
    server_path:
        ``runtime/llama-server.exe`` 的絕對路徑。
    model_path:
        ``models/gemma-3-4b-it.Q4_K_M.gguf`` 的絕對路徑。
    projector_path:
        ``models/mmproj-model-f16.gguf`` 的絕對路徑。
    """

    server_path: Path
    model_path: Path
    projector_path: Path


# ──────────────────────────────────────────────────────────────────────────────
# 公開 API
# ──────────────────────────────────────────────────────────────────────────────


def resolve_vision_assets(app_root: Path) -> VisionAssets:
    """以 *app_root* 解析三個資產的絕對路徑。

    不受 current working directory 影響；不驗證檔案是否存在。
    若需驗證，請在回傳後對各欄位呼叫 :func:`verify_asset`。

    Parameters
    ----------
    app_root:
        應用程式根目錄，PyInstaller frozen 環境傳入 resource root，
        原始碼執行傳入模組所在目錄（或明確指定的 project root）。

    Returns
    -------
    VisionAssets
        含三個絕對路徑的 frozen dataclass。
    """
    root = Path(app_root).resolve()
    return VisionAssets(
        server_path=root / _SERVER_REL,
        model_path=root / _MODEL_REL,
        projector_path=root / _PROJECTOR_REL,
    )


def verify_asset(
    path: Path,
    expected_sha256: Optional[str],
    minimum_bytes: int,
) -> None:
    """驗證單一資產的存在性、大小下限與 SHA-256 完整性。

    Parameters
    ----------
    path:
        要驗證的檔案路徑。
    expected_sha256:
        預期的十六進位 SHA-256 字串；傳入 ``None`` 則跳過雜湊驗證。
    minimum_bytes:
        可接受的最小檔案大小（bytes）；傳入 ``0`` 則不進行大小驗證。

    Raises
    ------
    VisionAssetError
        - code ``"asset_missing"``：檔案不存在。
        - code ``"asset_too_small"``：檔案大小小於 ``minimum_bytes``。
        - code ``"asset_sha256_mismatch"``：SHA-256 不符。
    """
    if not path.exists():
        raise VisionAssetError("asset_missing", path=path)

    if minimum_bytes > 0:
        actual_bytes = path.stat().st_size
        if actual_bytes < minimum_bytes:
            raise VisionAssetError(
                "asset_too_small",
                path=path,
                detail=f"got {actual_bytes}, want >={minimum_bytes}",
            )

    if expected_sha256 is not None:
        actual_sha = _sha256_file(path)
        if actual_sha != expected_sha256.lower():
            raise VisionAssetError(
                "asset_sha256_mismatch",
                path=path,
                detail=f"got {actual_sha}, want {expected_sha256.lower()}",
            )


# ──────────────────────────────────────────────────────────────────────────────
# 內部工具
# ──────────────────────────────────────────────────────────────────────────────


def _sha256_file(path: Path) -> str:
    """以串流方式計算檔案 SHA-256，避免大檔案佔用過多記憶體。"""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(_SHA256_CHUNK_BYTES)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# CLI 入口（python local_vision_assets.py --app-root .）
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Verify CloudHime local vision assets.")
    parser.add_argument("--app-root", default=".", help="Application root directory")
    args = parser.parse_args()

    app_root = Path(args.app_root).resolve()
    assets = resolve_vision_assets(app_root)

    missing: list[str] = []
    for field_name, path in [
        ("server_path", assets.server_path),
        ("model_path", assets.model_path),
        ("projector_path", assets.projector_path),
    ]:
        min_bytes = ASSET_MINIMUM_BYTES[field_name]
        try:
            verify_asset(path, None, minimum_bytes=min_bytes)
            size = path.stat().st_size
            print(f"  [OK] {field_name}: {path} ({size:,} bytes)")
        except VisionAssetError as exc:
            missing.append(f"  [ERROR] {field_name}: {path} -> {exc.code}")

    if missing:
        print("\n[local_vision_assets] Missing or invalid assets:")
        for line in missing:
            print(line)
        sys.exit(2)
    else:
        print("\n[local_vision_assets] All assets OK.")
        sys.exit(0)
