from translation_helpers import (
    clean_model_output,
    clean_model_output_multiline,
    clean_screenshot_translation_output,
    is_valid_screenshot_translation,
    parse_segmented_translation_json,
    ui_text,
)


def test_clean_model_output_preserves_order_for_unmarked_cjk_lines():
    source = "第一行比較長\n短句"

    assert clean_model_output(source) == source


def test_clean_model_output_shortest_selection_is_limited_to_explicit_candidates():
    source = '說明：「這是比較長的翻譯」\nAnswer translation: 短'

    assert clean_model_output(source) == "短"


def test_translation_prefix_is_removed_before_header_rejection():
    assert clean_model_output("Translation: 測試") == "測試"
    assert clean_model_output_multiline("Translation: 測試\nInput: source") == "測試"
    assert clean_model_output("Translation: Input: source") == ""


def test_screenshot_cleaning_allows_latin_only_for_english_target():
    assert clean_screenshot_translation_output("Hello world", target_lang="en") == "Hello world"
    assert clean_screenshot_translation_output("Hello world", target_lang="zh-TW") == ""
    assert clean_screenshot_translation_output("Translation: Hello", target_lang="en") == "Hello"
    assert clean_screenshot_translation_output("Translation: Input: source", target_lang="en") == ""


def test_screenshot_validation_is_target_aware():
    assert is_valid_screenshot_translation("Hello", target_lang="en") is True
    assert is_valid_screenshot_translation("Hello", target_lang="zh-TW") is False
    assert is_valid_screenshot_translation("翻譯結果", target_lang="zh-TW") is True


def test_segmented_translation_ignores_extra_out_of_range_segments():
    payload = (
        '{"segments":['
        '{"index":0,"translation":"測試"},'
        '{"index":1,"translation":"多餘"}'
        ']}'
    )

    assert parse_segmented_translation_json(payload, expected_count=1) == ["測試"]

def test_segmented_translation_repairs_literal_backslash_escape():
    payload = r'''{"segments":[{"index":0,"translation":"\V(CEEL第 6 話 1)"}]}'''

    assert parse_segmented_translation_json(payload, expected_count=1) == [r"\V(CEEL第 6 話 1)"]

def test_segment_index_rejects_bool():
    payload = '{"segments":[{"index":true,"translation":"測試"}]}'

    assert parse_segmented_translation_json(payload, expected_count=1) == []

def test_ui_text_falls_back_to_shared_localization_catalog():
    assert ui_text("en", "settings_knowledge_ready") == "✓ Knowledge pack ready"
    assert ui_text("zh-TW", "settings_knowledge_ready") == "✓ 小本本已建立"
    assert ui_text("en", "settings_save_failed") == "Settings could not be saved"
    assert ui_text("en", "settings_knowledge_progress", percent=42) == "Researching… 42%"
    assert ui_text("zh-TW", "settings_knowledge_progress", percent=42) == "正在查資料… 42%"
