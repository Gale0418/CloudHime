#!/usr/bin/env python3
"""
專門測試1B模型改良效果
"""

import sys
import time
from pathlib import Path

# 添加專案根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent))

from translation_helpers import build_gemma_prompt

def test_1b_prompt_optimization():
    """測試1B模型的prompt優化"""
    print("🔧 Gemma 3 1B 模型專用測試")
    print("=" * 50)
    
    test_cases = [
        {
            "text": "Hello",
            "expected": "你好",
            "difficulty": "簡單"
        },
        {
            "text": "Welcome",
            "expected": "歡迎",
            "difficulty": "簡單"
        },
        {
            "text": "Start Game",
            "expected": "開始遊戲",
            "difficulty": "中等"
        },
        {
            "text": "訓練室",
            "expected": "訓練室",
            "difficulty": "簡單中文"
        },
        {
            "text": "ゲーム開始",
            "expected": "遊戲開始",
            "difficulty": "日文"
        }
    ]
    
    # 測試不同prompt長度的效果
    prompt_strategies = [
        {
            "name": "超簡化",
            "builder": lambda text: f"Translate to Chinese:\n{text}\n\nTranslation:"
        },
        {
            "name": "標準簡化", 
            "builder": lambda text: f"Translate to Traditional Chinese:\n{text}\n\nTranslation:"
        },
        {
            "name": "帶角色",
            "builder": lambda text: f"You are a translator. Translate to Traditional Chinese:\n{text}\n\nTranslation:"
        },
        {
            "name": "模型優化",
            "builder": lambda text: build_gemma_prompt(text, "zh-TW", "gemma-3-1b-it")
        }
    ]
    
    for strategy in prompt_strategies:
        print(f"\n📝 測試策略: {strategy['name']}")
        print("-" * 30)
        
        for i, case in enumerate(test_cases, 1):
            prompt = strategy['builder'](case['text'])
            print(f"測試 {i} ({case['difficulty']}): {case['text']}")
            print(f"Prompt長度: {len(prompt)} 字符")
            print(f"Prompt: {repr(prompt[:50])}...")
            
            # 分析prompt特點
            if "You are" in prompt:
                print("特點: 包含角色設定")
            elif "Rules" in prompt or "Requirements" in prompt:
                print("特點: 包含規則列表")
            elif len(prompt) < 100:
                print("特點: 極簡prompt")
            else:
                print("特點: 詳細prompt")
            print()

def analyze_1b_characteristics():
    """分析1B模型的特性"""
    print("\n🧠 Gemma 3 1B 模型特性分析")
    print("=" * 50)
    
    characteristics = {
        "優點": [
            "響應速度快",
            "資源消耗少",
            "適合簡單文本",
            "成本較低"
        ],
        "缺點": [
            "理解能力有限",
            "複雜句式處理困難",
            "多行文本容易遺漏",
            "上下文理解較弱"
        ],
        "適用場景": [
            "單詞翻譯",
            "簡短句子",
            "UI按鈕文字",
            "簡單標籤"
        ],
        "不適用場景": [
            "長段落翻譯",
            "複雜對話",
            "文學作品",
            "技術文檔"
        ]
    }
    
    for category, items in characteristics.items():
        print(f"\n{category}:")
        for item in items:
            print(f"  • {item}")

def suggest_1b_optimization():
    """1B模型優化建議"""
    print("\n💡 Gemma 3 1B 優化建議")
    print("=" * 50)
    
    suggestions = [
        {
            "類別": "Prompt優化",
            "建議": [
                "使用極簡prompt，避免複雜指令",
                "直接給出翻譯任務，不要角色設定",
                "避免多步驟指示",
                "使用簡單的句式結構"
            ]
        },
        {
            "類別": "文本預處理",
            "建議": [
                "將長文本拆分為短句",
                "避免複雜的標點符號",
                "簡化專有名詞",
                "統一文本格式"
            ]
        },
        {
            "類別": "後處理",
            "建議": [
                "添加結果驗證",
                "設置信賴度閾值",
                "準備fallback機制",
                "結果緩存機制"
            ]
        },
        {
            "類別": "使用策略",
            "建議": [
                "僅用於簡單文本",
                "與其他模型組合使用",
                "作為快速預覽選項",
                "用於批量簡單翻譯"
            ]
        }
    ]
    
    for suggestion in suggestions:
        print(f"\n{suggestion['類別']}:")
        for item in suggestion['建議']:
            print(f"  • {item}")

def create_1b_optimized_prompt_examples():
    """創建1B模型優化的prompt範例"""
    print("\n📋 1B模型優化Prompt範例")
    print("=" * 50)
    
    examples = [
        {
            "場景": "UI按鈕",
            "原文": "Start Game",
            "優化prompt": "Translate to Chinese:\nStart Game\n\nTranslation:",
            "說明": "最簡單的指令，適合單詞或短語"
        },
        {
            "場景": "簡單句子",
            "原文": "Welcome to the game",
            "優化prompt": "Translate to Traditional Chinese:\nWelcome to the game\n\nTranslation:",
            "說明": "指定目標語言，保持簡潔"
        },
        {
            "場景": "日文簡單文本",
            "原文": "ゲーム開始",
            "優化prompt": "Translate to Traditional Chinese:\nゲーム開始\n\nTranslation:",
            "說明": "直接翻譯，不需要語言檢測"
        },
        {
            "場景": "多行簡單文本",
            "原文": "Menu\nSettings\nExit",
            "優化prompt": "Translate to Traditional Chinese:\nMenu\nSettings\nExit\n\nTranslation:",
            "說明": "保持換行，讓模型理解格式"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n範例 {i}: {example['場景']}")
        print(f"原文: {example['原文']}")
        print(f"Prompt: {example['優化prompt']}")
        print(f"說明: {example['說明']}")

def main():
    print("CloudHime Gemma 3 1B 模型專門優化")
    print("=" * 60)
    
    test_1b_prompt_optimization()
    analyze_1b_characteristics()
    suggest_1b_optimization()
    create_1b_optimized_prompt_examples()
    
    print("\n🎯 總結")
    print("=" * 50)
    print("1B模型優化成功關鍵:")
    print("1. ✅ 使用超簡化prompt（< 100字符）")
    print("2. ✅ 避免複雜指令和角色設定")
    print("3. ✅ 適合簡單、短文本翻譯")
    print("4. ✅ 作為快速響應的選擇")
    print("\n推薦使用順序:")
    print("1. Gemma 3 27B（主要選擇）")
    print("2. Gemma 3 1B（簡單文本快速響應）")
    print("3. Gemini 2.5 Pro（高品質但不穩定）")
    print("4. Gemma 4 31B（需要嚴格prompt控制）")

if __name__ == "__main__":
    main()
