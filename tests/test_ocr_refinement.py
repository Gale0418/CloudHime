import unittest

try:
    from ocr_refinement import (
        normalize_translation_compare_text,
        should_fallback_to_text_translation,
        is_suspiciously_short_translation,
        score_ocr_candidate_text,
        choose_better_ocr_candidate,
        merge_google_lines_into_items
    )
except ImportError:
    # 為了在完全沒有目標檔案的 RED 階段仍能被 unittest 掃描到，
    # 這裡給定 None 的 mock，讓它會在執行階段失敗，而不是在 module import 時卡死。
    normalize_translation_compare_text = None
    should_fallback_to_text_translation = None
    is_suspiciously_short_translation = None
    score_ocr_candidate_text = None
    choose_better_ocr_candidate = None
    merge_google_lines_into_items = None


class TestOcrRefinement(unittest.TestCase):

    def test_normalize_translation_compare_text(self):
        # 1. compare text 正規化會去掉空白與常見括號/標點，並轉小寫。
        if normalize_translation_compare_text is None:
            self.fail("ocr_refinement module or function not implemented")
            
        self.assertEqual(normalize_translation_compare_text("Hello  World"), "helloworld")
        self.assertEqual(normalize_translation_compare_text("【測試】(括號)！"), "測試括號")
        self.assertEqual(normalize_translation_compare_text("A B c"), "abc")

    def test_should_fallback_to_text_translation(self):
        # 2. 當翻譯結果含日文假名，或與 source hint 高相似時，會回傳 True。
        if should_fallback_to_text_translation is None:
            self.fail("ocr_refinement module or function not implemented")
            
        self.assertTrue(should_fallback_to_text_translation("This is a test", "これはテストです"))
        self.assertTrue(should_fallback_to_text_translation("identical text", "identical text"))
        self.assertFalse(should_fallback_to_text_translation("This is a test", "這是一個測試"))

    def test_is_suspiciously_short_translation(self):
        # 3. 當 source 很長、translated 很短時，會回傳 True。
        if is_suspiciously_short_translation is None:
            self.fail("ocr_refinement module or function not implemented")
            
        long_source = "A very long source text that has many many words and characters in it to be translated."
        short_translated = "很短"
        normal_translated = "這是一段很長很長的來源文字，裡面有很多很多的單字和字元需要被翻譯。"
        
        self.assertTrue(is_suspiciously_short_translation(long_source, short_translated))
        self.assertFalse(is_suspiciously_short_translation(long_source, normal_translated))

    def test_score_ocr_candidate_text(self):
        # 4. score_ocr_candidate_text 對正常 CJK 文字分數高於噪聲字串。
        if score_ocr_candidate_text is None:
            self.fail("ocr_refinement module or function not implemented")
            
        score_good = score_ocr_candidate_text("這是一個正常的中文句子")
        score_bad = score_ocr_candidate_text("!@#$%^&*()")
        self.assertGreater(score_good, score_bad)

    def test_choose_better_ocr_candidate(self):
        # 5. 目前策略是：google_norm 有值就優先回 google_norm，否則回 local_norm。
        if choose_better_ocr_candidate is None:
            self.fail("ocr_refinement module or function not implemented")
            
        self.assertEqual(choose_better_ocr_candidate("local text", "google text"), "google text")
        self.assertEqual(choose_better_ocr_candidate("local text", ""), "local text")
        self.assertEqual(choose_better_ocr_candidate("local text", None), "local text")

    def test_merge_google_lines_into_items_equal_count(self):
        # 6-a. 在 google_lines 與 local_items 數量相等時，逐項替換文字但保留 x/y/w/h。
        if merge_google_lines_into_items is None:
            self.fail("ocr_refinement module or function not implemented")
            
        google_lines = ["line 1", "line 2"]
        local_items = [
            {"text": "l1", "x": 0, "y": 0, "w": 10, "h": 10},
            {"text": "l2", "x": 0, "y": 10, "w": 10, "h": 10}
        ]
        
        result = merge_google_lines_into_items(google_lines, local_items)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["text"], "line 1")
        self.assertEqual(result[0]["x"], 0)
        self.assertEqual(result[0]["y"], 0)
        self.assertEqual(result[0]["w"], 10)
        self.assertEqual(result[0]["h"], 10)
        self.assertEqual(result[1]["text"], "line 2")
        self.assertEqual(result[1]["x"], 0)
        self.assertEqual(result[1]["y"], 10)
        self.assertEqual(result[1]["w"], 10)
        self.assertEqual(result[1]["h"], 10)

    def test_merge_google_lines_into_items_fewer_google_lines(self):
        # 6-b. 在 google_lines 較少時，按群組合併 local_items 並生成合併後 x/y/w/h。
        if merge_google_lines_into_items is None:
            self.fail("ocr_refinement module or function not implemented")
            
        google_lines = ["merged line"]
        local_items = [
            {"text": "part 1", "x": 0, "y": 0, "w": 10, "h": 10},
            {"text": "part 2", "x": 0, "y": 10, "w": 10, "h": 10}
        ]
        
        result = merge_google_lines_into_items(google_lines, local_items)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "merged line")
        self.assertEqual(result[0]["x"], 0)
        self.assertEqual(result[0]["y"], 0)
        self.assertEqual(result[0]["w"], 10)
        self.assertEqual(result[0]["h"], 20)

    def test_merge_google_lines_into_items_empty_google_lines(self):
        # 6-c. 在 google_lines 為空時，回傳 items 的拷貝，不要直接回原物件。
        if merge_google_lines_into_items is None:
            self.fail("ocr_refinement module or function not implemented")
            
        google_lines = []
        local_items = [
            {"text": "l1", "x": 0, "y": 0, "w": 10, "h": 10}
        ]
        
        result = merge_google_lines_into_items(google_lines, local_items)
        self.assertEqual(result, local_items)
        self.assertIsNot(result, local_items)

if __name__ == '__main__':
    unittest.main()
