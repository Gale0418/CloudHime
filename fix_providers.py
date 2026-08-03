from __future__ import annotations

from pathlib import Path


DEFAULT_TRANSLATION_PROVIDERS_PATH = Path("d:/MyGame/CloudHime/translation_providers.py")


def replace_exactly_once(content: str, target: str, replacement: str) -> str:
    count = content.count(target)
    if count != 1:
        raise RuntimeError(
            f"expected exactly one target occurrence, found {count}: {target[:80]!r}"
        )
    return content.replace(target, replacement, 1)


def rewrite_translation_providers(content: str) -> str:
    rewritten = replace_exactly_once(
        content,
        "translated = clean_model_output(extract_gemma_text(payload))",
        "translated = clean_model_output_multiline(extract_gemma_text(payload))",
    )
    return replace_exactly_once(
        rewritten,
        "except Exception:\n            return text",
        "except Exception as e:\n            raise RuntimeError(f\"Fallback translation failed: {e}\")",
    )


def patch_file(path: Path = DEFAULT_TRANSLATION_PROVIDERS_PATH) -> None:
    content = path.read_text(encoding="utf-8")
    rewritten = rewrite_translation_providers(content)
    path.write_text(rewritten, encoding="utf-8")


if __name__ == "__main__":
    patch_file()
    print("Done")