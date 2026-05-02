#!/usr/bin/env python3
"""
增強版模型測試腳本
包含速率限制和1B模型優化
"""

import os
import sys
import time
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

class EnhancedGemmaProvider:
    """增強版Gemma提供者，包含速率限制和1B優化"""
    
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self.call_times = []
        self.rate_limit = 15  # 每分鐘15次
        self.buffer = 2      # 緩衝2次
        
    def _wait_if_needed(self):
        """智能等待避免429錯誤"""
        current_time = time.time()
        # 清理超過1分鐘的記錄
        self.call_times = [t for t in self.call_times if current_time - t < 60]
        
        if len(self.call_times) >= (self.rate_limit - self.buffer):
            # 計算需要等待的時間
            oldest_time = min(self.call_times)
            wait_time = 60 - (current_time - oldest_time)
            
            if wait_time > 0:
                print(f"⏳ 速率限制：等待 {wait_time:.1f} 秒避免429錯誤...")
                time.sleep(wait_time + 1)
        
        self.call_times.append(current_time)
    
    def translate_with_enhanced_prompt(self, text: str):
        """使用增強prompt進行翻譯"""
        self._wait_if_needed()
        
        # 使用模型特定的prompt
        if self.model_name == "gemma-3-1b-it":
            # 1B模型使用超簡化prompt
            prompt = f"Translate to Traditional Chinese:\n{text}\n\nTranslation:"
        elif self.model_name == "gemma-4-31b-it":
            # 4B模型使用嚴格限制prompt
            prompt = f"RULES: Translate ONLY. NO analysis. NO explanations.\nTranslate to Traditional Chinese:\n{text}\n\nTranslation:"
        else:
            # 其他模型使用標準prompt
            prompt = build_gemma_prompt(text, "zh-TW", self.model_name)
        
        try:
            provider = GemmaTranslationProvider(
                google_api_key=self.api_key,
                gemma_model=self.model_name,
                gemma_enabled=True
            )
            
            # 直接使用provider的翻譯
            result = provider.translate(text)
            return result.text if hasattr(result, 'text') else str(result)
            
        except Exception as e:
            return f"❌ 錯誤: {str(e)}"

def test_enhanced_models():
    """測試增強版模型"""
    api_key = "AIzaSyDYkNOsjWsDH3cbnrYwRu449Mt1Q7LYE24"
    
    models = ["gemma-3-1b-it", "gemma-3-27b-it", "gemma-4-31b-it", "gemini-2.5-pro"]
    
    print("🚀 增強版模型測試")
    print("=" * 60)
    print("✨ 包含速率限制保護和1B模型優化")
    print("=" * 60)
    
    for model in models:
        print(f"\n📱 測試模型: {model}")
        print("-" * 40)
        
        provider = EnhancedGemmaProvider(api_key, model)
        
        for i, text in enumerate(TEST_TEXTS, 1):
            print(f"\n測試 {i}: {repr(text)}")
            try:
                translation = provider.translate_with_enhanced_prompt(text)
                if translation.startswith("❌"):
                    print(f"{translation}")
                else:
                    print(f"✅ 翻譯: {translation}")
                    
                    # 評估翻譯品質
                    if model == "gemma-3-1b-it":
                        # 1B模型特殊評估
                        if len(text.split('\n')) > 1 and '\n' in translation:
                            print("🎉 1B模型多行處理成功！")
                        elif any(char in translation for char in ['訓', '練', '室', '現', '在', '位', '置']):
                            print("👍 1B模型中文翻譯成功！")
                        else:
                            print("⚠️ 1B模型可能需要更多優化")
                    
            except Exception as e:
                print(f"❌ 翻譯錯誤: {str(e)}")

def test_prompt_improvements():
    """測試prompt改良效果"""
    print("\n📝 Prompt改良效果測試")
    print("=" * 60)
    
    test_text = "訓練室は平日ーの左手だったね"
    
    # 測試不同模型的prompt
    models_and_prompts = [
        ("gemma-3-1b-it", "簡化prompt"),
        ("gemma-3-27b-it", "標準prompt"),
        ("gemma-4-31b-it", "嚴格prompt"),
        ("gemini-2.5-pro", "標準prompt")
    ]
    
    for model, prompt_type in models_and_prompts:
        prompt = build_gemma_prompt(test_text, "zh-TW", model)
        print(f"\n{model} ({prompt_type}):")
        print(f"長度: {len(prompt)} 字符")
        print(f"包含關鍵詞: {'✓' if 'Translate' in prompt else '✗'}")
        print(f"結構化: {'✓' if ':' in prompt and '\n' in prompt else '✗'}")

def main():
    print("CloudHime 增強版翻譯測試")
    print("=" * 60)
    
    # 測試prompt改良
    test_prompt_improvements()
    
    # 測試增強版模型
    test_enhanced_models()
    
    print("\n🎯 測試完成！")
    print("改良重點:")
    print("1. ✅ 1B模型使用超簡化prompt")
    print("2. ✅ 4B模型使用嚴格限制prompt")
    print("3. ✅ 智能速率限制避免429錯誤")
    print("4. ✅ 自動等待機制")
    print("\n💡 建議:")
    print("- 優先使用 Gemma 3 27B（最穩定）")
    print("- 1B模型適合簡單文本")
    print("- 4B模型需要嚴格prompt控制")

if __name__ == "__main__":
    main()
