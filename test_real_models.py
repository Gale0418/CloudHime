#!/usr/bin/env python3
"""
實際API測試腳本
測試4種模型的真實翻譯效果
"""

import os
import sys
from pathlib import Path

# 添加專案根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent))

from translation_helpers import build_gemma_prompt
from translation_providers import GemmaTranslationProvider

# 測試用例
TEST_TEXTS = [
    "Exclusive Invite: Forbes Wine Club",
    "訓練室は平日ーの左手だったね",
    "📍 現在地\nロマーシャの部屋",
    "GP 下 5.5 works best when prompts define the outcome"
]

def test_with_api_key():
    """使用API Key測試4種模型"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        # 直接使用已知的API Key
        api_key = "AIzaSyDYkNOsjWsDH3cbnrYwRu449Mt1Q7LYE24"
        print("🔑 使用已配置的API Key進行測試")
    
    models = ["gemma-3-1b-it", "gemma-3-27b-it", "gemma-4-31b-it", "gemini-2.5-pro"]
    
    print("🧪 開始測試4種模型的翻譯效果")
    print("=" * 60)
    
    for model in models:
        print(f"\n📱 測試模型: {model}")
        print("-" * 40)
        
        try:
            provider = GemmaTranslationProvider(
                google_api_key=api_key,
                gemma_model=model,
                gemma_enabled=True
            )
            
            for i, text in enumerate(TEST_TEXTS, 1):
                print(f"\n測試 {i}: {repr(text)}")
                try:
                    result = provider.translate(text)
                    if hasattr(result, 'text'):
                        translation = result.text
                        print(f"✅ 翻譯: {translation}")
                    elif isinstance(result, str):
                        print(f"✅ 翻譯: {result}")
                    else:
                        print(f"❌ 翻譯失敗：未知結果類型 {type(result)}")
                except Exception as e:
                    print(f"❌ 翻譯錯誤: {str(e)}")
                    
        except Exception as e:
            print(f"❌ 模型 {model} 初始化失敗: {str(e)}")

def test_prompt_quality():
    """測試prompt品質"""
    print("\n📝 Prompt品質分析")
    print("=" * 60)
    
    for text in TEST_TEXTS:
        prompt = build_gemma_prompt(text)
        print(f"\n原文: {repr(text)}")
        print(f"Prompt長度: {len(prompt)} 字符")
        print(f"包含關鍵詞: {'✓' if 'ONLY' in prompt and 'explanation' in prompt else '✗'}")
        print(f"結構化: {'✓' if 'Requirements:' in prompt else '✗'}")

def main():
    print("CloudHime 翻譯品質實測")
    print("=" * 60)
    
    # 先測試prompt品質
    test_prompt_quality()
    
    # 直接測試實際翻譯（使用已配置的API Key）
    test_with_api_key()
    
    print("\n🎯 建議改良方向：")
    print("1. 根據實際結果調整prompt結構")
    print("2. 針對不同模型特性優化")
    print("3. 增加錯誤處理和重試機制")
    print("4. 監控翻譯品質和響應時間")

if __name__ == "__main__":
    main()
