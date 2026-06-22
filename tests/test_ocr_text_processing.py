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

if __name__ == '__main__':
    unittest.main()
