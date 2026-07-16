import unittest
from copy import deepcopy

from ocr_text_processing import (
    normalize_ocr_text,
    is_valid_content,
    merge_horizontal_lines
)

class TestOCRTextProcessing(unittest.TestCase):
    
    def test_normalize_ocr_text(self):
        """測試 normalize_ocr_text: 移除 CJK 中間空白與標點前空白"""
        self.assertEqual(normalize_ocr_text("測 試"), "測試")
        self.assertEqual(normalize_ocr_text("天 氣 真 好"), "天氣真好")
        self.assertEqual(normalize_ocr_text("測試 ，"), "測試，")
        self.assertEqual(normalize_ocr_text("你好 ！"), "你好！")
        self.assertEqual(normalize_ocr_text("「 測試"), "「測試")
        self.assertEqual(normalize_ocr_text("（ 括號"), "（括號")

    def test_is_valid_content(self):
        """測試 is_valid_content: 拒絕無效內容，接受單一 CJK 與數字"""
        # 拒絕空白
        self.assertFalse(is_valid_content(""))
        self.assertFalse(is_valid_content("   "))
        
        # 拒絕純符號
        self.assertFalse(is_valid_content("-=_"))
        self.assertFalse(is_valid_content("..."))
        
        # 拒絕特定無意義英文字母組合
        self.assertFalse(is_valid_content("ii"))
        self.assertFalse(is_valid_content("ll"))
        self.assertFalse(is_valid_content("rr"))
        
        # 接受單一 CJK
        self.assertTrue(is_valid_content("我"))
        self.assertTrue(is_valid_content("好"))
        
        # 接受數字
        self.assertTrue(is_valid_content("123"))
        self.assertTrue(is_valid_content("4"))

    def test_merge_horizontal_lines(self):
        """測試 merge_horizontal_lines: 相同水平線合併，處理 CJK 與英文的空白拼接，並回傳正確 bbox"""
        items = [
            {'text': 'Hello', 'x': 10, 'y': 10, 'w': 40, 'h': 20},
            {'text': 'World', 'x': 55, 'y': 11, 'w': 40, 'h': 20},
            {'text': '中', 'x': 100, 'y': 10, 'w': 20, 'h': 20},
            {'text': '文', 'x': 122, 'y': 10, 'w': 20, 'h': 20},
        ]
        merged = merge_horizontal_lines(items)
        
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['text'], 'Hello World中文')
        
        # 預期的 bbox:
        # min x = 10
        # min y = 10
        # max x = 122 + 20 = 142
        # max y = max(10+20, 11+20) = 31
        # w = 142 - 10 = 132
        # h = 31 - 10 = 21
        self.assertEqual(merged[0]['x'], 10)
        self.assertEqual(merged[0]['y'], 10)
        self.assertEqual(merged[0]['w'], 132)
        self.assertEqual(merged[0]['h'], 21)

    def test_merge_horizontal_lines_no_mutation(self):
        """測試 merge_horizontal_lines: 不應該原地改動呼叫端傳入的 items (純函式無副作用)"""
        items = [
            {'text': 'B', 'x': 50, 'y': 10, 'w': 20, 'h': 20},
            {'text': 'A', 'x': 10, 'y': 10, 'w': 20, 'h': 20},
        ]
        original_items = deepcopy(items)
        merge_horizontal_lines(items)
        
        # 確認傳入的 items 完全沒被改變 (順序跟內容都不該動)
        self.assertEqual(items, original_items)

    def test_normalize_ocr_text_collapses_horizontal_space_and_cjk_punctuation(self):
        self.assertEqual(normalize_ocr_text("  「  測 試  !  」  "), "「測試!」")
        self.assertEqual(normalize_ocr_text("Hello   World\nSecond\tline"), "Hello World\nSecond line")

    def test_merge_horizontal_lines_keeps_small_punctuation_with_large_text(self):
        items = [
            {"text": "測試", "x": 0, "y": 0, "w": 48, "h": 30, "confidence": 0.9},
            {"text": "！", "x": 50, "y": 15, "w": 8, "h": 10, "confidence": 0.6},
        ]

        merged = merge_horizontal_lines(items)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["text"], "測試！")
        self.assertEqual((merged[0]["x"], merged[0]["y"], merged[0]["w"], merged[0]["h"]), (0, 0, 58, 30))

    def test_merge_horizontal_lines_does_not_chain_across_rows(self):
        items = [
            {"text": "第一", "x": 0, "y": 0, "w": 35, "h": 20},
            {"text": "行", "x": 38, "y": 9, "w": 18, "h": 20},
            {"text": "第二行", "x": 0, "y": 18, "w": 56, "h": 20},
        ]

        merged = merge_horizontal_lines(items)

        self.assertEqual([item["text"] for item in merged], ["第一行", "第二行"])

    def test_merge_horizontal_lines_preserves_weighted_confidence(self):
        items = [
            {"text": "AB", "x": 0, "y": 0, "w": 20, "h": 20, "confidence": 0.9},
            {"text": "CDEF", "x": 22, "y": 0, "w": 40, "h": 20, "confidence": 50},
        ]

        merged = merge_horizontal_lines(items)

        self.assertEqual(len(merged), 1)
        self.assertAlmostEqual(merged[0]["confidence"], (0.9 * 2 + 0.5 * 4) / 6)
    def test_merge_horizontal_lines_rejects_tall_bridge_between_rows(self):
        items = [
            {"text": "上", "x": 0, "y": 0, "w": 10, "h": 10},
            {"text": "高框", "x": 12, "y": 0, "w": 20, "h": 40},
            {"text": "下", "x": 34, "y": 30, "w": 10, "h": 10},
        ]

        merged = merge_horizontal_lines(items)

        self.assertEqual([item["text"] for item in merged], ["上高框", "下"])

    def test_merge_horizontal_lines_ignores_empty_token_confidence(self):
        items = [
            {"text": "", "x": 0, "y": 0, "w": 1, "h": 20, "confidence": 1.0},
            {"text": "AB", "x": 2, "y": 0, "w": 20, "h": 20, "confidence": 0.5},
        ]

        merged = merge_horizontal_lines(items)

        self.assertEqual(merged[0]["text"], "AB")
        self.assertAlmostEqual(merged[0]["confidence"], 0.5)
if __name__ == '__main__':
    unittest.main()
