import os
from pathlib import Path

import pytest

from dev_local_gemma_provider import LocalGemmaProvider



MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "gemma-3-4b-it.Q4_K_M.gguf"
RUN_LOCAL_MODEL = os.getenv("CLOUDHIME_RUN_LOCAL_MODEL") == "1"


@pytest.mark.skipif(not RUN_LOCAL_MODEL, reason="set CLOUDHIME_RUN_LOCAL_MODEL=1")
def test_embedded_local_gemma_translates_with_llama_cpp():
    provider = LocalGemmaProvider(
        model_path=str(MODEL_PATH),
        target_lang="zh-TW",
        enabled=True,
        temperature=0.2,
        repeat_penalty=1.15,
    )

    assert provider.available() is True

    result = provider.translate("Welcome to Two Point Museum.", target_lang="zh-TW")

    assert result.provider == "local_gemma"
    assert "雙點博物館" in result.text
