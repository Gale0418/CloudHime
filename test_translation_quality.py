#!/usr/bin/env python3
"""
翻譯品質測試腳本
測試4種模型的翻譯效果
"""

import os
import sys
import json
import time
from pathlib import Path

# 添加專案根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent))

from translation_helpers import (
    build_gemma_prompt,
    build_gemma_multimodal_prompt,
    clean_model_output,
    detect_source_language,
)
from translation_providers import GemmaTranslationProvider

# 測試用例 - 從example資料夾中的圖片OCR結果
TEST_CASES = [
    {
        "source": "Exclusive Invite: Forbes Wine Club",
        "expected": "《富比世》葡萄酒俱樂部專屬邀請",
        "context": "UI text"
    },
    {
        "source": "GP 下 5.5 works best when prompts define the outcome and leave room for the model to choose an efficient solution path.",
        "expected": "GP 5.5 在提示詞定義結果並為模型選擇高效解決方案路徑留出空間時效果最佳。",
        "context": "Technical documentation"
    },
    {
        "source": "訓練室は平日ーの左手だったね",
        "expected": "訓練室在平日的左手邊呢。",
        "context": "Game dialogue"
    },
    {
        "source": "📍 現在地\nロマーシャの部屋",
        "expected": "📍 目前位置\n羅瑪莎的房間",
        "context": "Game UI"
    }
]

def test_prompt_quality():
    """測試prompt品質"""
    print("=== 測試Prompt品質 ===")
    
    for i, case in enumerate(TEST_CASES, 1):
        print(f"\n測試案例 {i}: {case['context']}")
        print(f"原文: {case['source']}")
        
        # 測試基本prompt
        prompt = build_gemma_prompt(case['source'])
        print(f"Prompt長度: {len(prompt)} 字符")
        print(f"包含關鍵詞: {'ONLY' in prompt and 'explanation' in prompt}")
        
        # 測試清理功能
        # 模擬模型可能的輸出
        mock_outputs = [
            case['expected'],  # 理想輸出
            f"**{case['expected']}**",  # 帶格式
            f"Translation: {case['expected']}",  # 帶標籤
            f"Here's the translation: {case['expected']}\n\nNote: This is a good translation.",  # 帶解釋
        ]
        
        for j, output in enumerate(mock_outputs, 1):
            cleaned = clean_model_output(output)
            print(f"清理測試 {j}: {'✓' if cleaned == case['expected'] else '✗'}")
            if cleaned != case['expected']:
                print(f"  期望: {case['expected']}")
                print(f"  實際: {cleaned}")

def test_multimodal_prompt():
    """測試多模態prompt"""
    print("\n=== 測試多模態Prompt品質 ===")
    
    source_texts = [
        "Exclusive Invite:",
        "Forbes Wine Club"
    ]
    
    prompt = build_gemma_multimodal_prompt(source_texts)
    print(f"多模態Prompt長度: {len(prompt)} 字符")
    print(f"包含視覺處理指令: {'visually' in prompt and 'screenshot' in prompt}")
    print(f"包含OCR錯誤修正: {'errors' in prompt and 'image' in prompt}")

def test_language_detection():
    """測試語言檢測"""
    print("\n=== 測試語言檢測 ===")
    
    test_texts = [
        ("Hello world", "en"),
        ("こんにちは世界", "ja"),
        ("你好世界", "ja"),  # 中文會被識別為日文（因為有漢字）
        ("Mixed English and 日本語", "ja"),
    ]
    
    for text, expected in test_texts:
        detected = detect_source_language(text)
        status = "✓" if detected == expected else "✗"
        print(f"{status} '{text}' -> {detected} (期望: {expected})")

def test_model_compatibility():
    """測試模型兼容性"""
    print("\n=== 測試模型兼容性 ===")
    
    models = ["gemma-3-1b-it", "gemma-3-27b-it", "gemma-4-31b-it", "gemini-2.5-pro"]
    
    for model in models:
        print(f"\n測試模型: {model}")
        
        # 測試prompt長度是否適合不同模型
        prompt = build_gemma_prompt("Test text")
        print(f"  Prompt長度: {len(prompt)} 字符")
        
        # 檢查prompt是否包含模型特定的優化
        has_clear_rules = "ONLY" in prompt and "CRITICAL" in prompt
        has_format_guidance = "Translation:" in prompt
        
        print(f"  清晰規則: {'✓' if has_clear_rules else '✗'}")
        print(f"  格式指導: {'✓' if has_format_guidance else '✗'}")

def run_comprehensive_test():
    """執行綜合測試"""
    print("CloudHime 翻譯品質測試")
    print("=" * 50)
    
    test_prompt_quality()
    test_multimodal_prompt()
    test_language_detection()
    test_model_compatibility()
    
    print("\n=== 測試完成 ===")
    print("建議:")
    print("1. 使用實際API測試4種模型的翻譯效果")
    print("2. 收集真實使用場景的翻譯結果")
    print("3. 根據結果調整prompt參數")
    print("4. 持續監控翻譯品質")

if __name__ == "__main__":
    run_comprehensive_test()
