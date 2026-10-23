"""向後相容的 OCR 文字處理 API；實作統一由 ocr_quality 提供。"""

from ocr_quality import (
    is_valid_content,
    merge_horizontal_lines,
    needs_cjk_tight_join,
    normalize_ocr_text,
)

__all__ = [
    "normalize_ocr_text",
    "is_valid_content",
    "needs_cjk_tight_join",
    "merge_horizontal_lines",
]
