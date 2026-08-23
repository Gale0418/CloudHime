import os
import time
import base64
import pytest
from pathlib import Path
from local_vision_assets import resolve_preferred_vision_assets
from local_vision_runtime import LocalVisionRuntime
from translation_providers import LocalMultimodalProvider

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VISION_MODEL_NAME = "gemma-3-4b-it"

@pytest.mark.skipif(not os.environ.get("TEST_VISION_INTEGRATION"), reason="Need TEST_VISION_INTEGRATION=1 to run real local vision test")
def test_local_vision_integration():
    """以 production asset resolver 啟動 llama-server，送出 example 圖片並驗證 vision request。"""
    assets = resolve_preferred_vision_assets(PROJECT_ROOT)
    assert assets.server_path.exists(), "Runtime binary missing"
    assert assets.model_path.exists(), "Text model missing"
    assert assets.projector_path.exists(), "Vision projector missing"

    runtime = LocalVisionRuntime(assets)
    try:
        start_time = time.perf_counter()
        state = runtime.start()
        assert state.name == "ready", f"Runtime failed to start: {state.detail}"
        startup_time = time.perf_counter() - start_time
        print(f"\n[Vision Test] Startup time: {startup_time:.2f}s, Mode: {state.mode}, URL: {state.base_url}")

        provider = LocalMultimodalProvider(
            base_url=state.base_url,
            model_name=VISION_MODEL_NAME,
            api_key=getattr(runtime, "api_key", ""),
            target_lang="zh-TW",
            enabled=True,
            timeout_seconds=60,
        )
        image_path = PROJECT_ROOT / "example" / "2026-07-10 00 37 20.png"
        if not image_path.exists():
            example_dir = PROJECT_ROOT / "example"
            png_files = list(example_dir.glob("*.png"))
            assert png_files, "No PNG files found in example directory"
            image_path = png_files[0]

        with open(image_path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("utf-8")
        prompt = (
            "Inspect this image and translate any visible text to Traditional Chinese. "
            "If there is no readable text, briefly describe the most prominent visible subject "
            "in Traditional Chinese. Return only the result."
        )
        image_parts = [{"inline_data": {"mime_type": "image/png", "data": encoded}}]
        req_start = time.perf_counter()
        result = provider.translate_screenshot(
            image_parts=image_parts,
            target_lang="zh-TW",
            source_text_hint=prompt,
        )
        req_time = time.perf_counter() - req_start
        print(f"[Vision Test] Translation request time: {req_time:.2f}s")
        assert result is not None
        assert result.text.strip(), "Translation result should not be empty"
        print(f"[Vision Test] Result:\n{result.text}")
    finally:
        stop_state = runtime.stop()
        assert stop_state.name == "stopped"
        assert runtime._process is None
        print("[Vision Test] Runtime stopped successfully.")
