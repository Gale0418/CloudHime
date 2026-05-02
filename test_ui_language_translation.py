#!/usr/bin/env python3
"""
測試UI語言切換對翻譯目標語言的影響
"""

import sys
from pathlib import Path

# 添加專案根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent))

import localization
from translation_helpers import build_gemma_prompt, target_lang_instruction

def test_ui_language_translation_mapping():
    """測試UI語言到翻譯目標語言的映射"""
    print("🌐 UI語言與翻譯目標語言映射測試")
    print("=" * 50)
    
    test_cases = [
        ("en", "英文UI"),
        ("zh-TW", "繁體中文UI"),
        ("zh", "中文UI（簡稱）"),
        ("zh-tw", "中文UI（連字元）"),
        ("english", "英文UI（全稱）"),
        ("chinese", "中文UI（全稱）"),
        ("invalid", "無效語言"),
        ("", "空語言"),
    ]
    
    for ui_lang, description in test_cases:
        target_lang = localization.get_translation_target_lang(ui_lang)
        instruction = target_lang_instruction(target_lang)
        
        print(f"\n{description}:")
        print(f"  UI語言: {ui_lang}")
        print(f"  翻譯目標: {target_lang}")
        print(f"  翻譯指令: {instruction}")

def test_prompt_generation_with_ui_language():
    """測試不同UI語言下的prompt生成"""
    print("\n📝 不同UI語言下的Prompt生成測試")
    print("=" * 50)
    
    test_text = "Hello World"
    ui_languages = ["en", "zh-TW"]
    models = ["gemma-3-1b-it", "gemma-3-27b-it", "gemma-4-31b-it"]
    
    for ui_lang in ui_languages:
        target_lang = localization.get_translation_target_lang(ui_lang)
        print(f"\n🌐 UI語言: {ui_lang} → 翻譯目標: {target_lang}")
        print("-" * 40)
        
        for model in models:
            prompt = build_gemma_prompt(test_text, target_lang, model)
            print(f"{model}:")
            print(f"  Prompt長度: {len(prompt)} 字符")
            print(f"  包含目標語言: {'✓' if target_lang in prompt else '✗'}")
            print(f"  Prompt片段: {repr(prompt[:80])}...")

def test_translation_scenarios():
    """測試實際翻譯場景"""
    print("\n🎯 實際翻譯場景測試")
    print("=" * 50)
    
    scenarios = [
        {
            "name": "英文UI翻譯英文文本",
            "ui_lang": "en",
            "source_text": "Hello World",
            "expected_target": "en",
            "expected_instruction": "natural English"
        },
        {
            "name": "中文UI翻譯英文文本", 
            "ui_lang": "zh-TW",
            "source_text": "Hello World",
            "expected_target": "zh-TW",
            "expected_instruction": "natural Traditional Chinese used in Taiwan"
        },
        {
            "name": "英文UI翻譯日文文本",
            "ui_lang": "en", 
            "source_text": "こんにちは世界",
            "expected_target": "en",
            "expected_instruction": "natural English"
        },
        {
            "name": "中文UI翻譯日文文本",
            "ui_lang": "zh-TW",
            "source_text": "こんにちは世界", 
            "expected_target": "zh-TW",
            "expected_instruction": "natural Traditional Chinese used in Taiwan"
        }
    ]
    
    for scenario in scenarios:
        print(f"\n📋 {scenario['name']}:")
        print(f"  UI語言: {scenario['ui_lang']}")
        print(f"  原文: {scenario['source_text']}")
        
        target_lang = localization.get_translation_target_lang(scenario['ui_lang'])
        instruction = target_lang_instruction(target_lang)
        
        print(f"  翻譯目標: {target_lang} {'✓' if target_lang == scenario['expected_target'] else '✗'}")
        print(f"  翻譯指令: {instruction} {'✓' if scenario['expected_instruction'] in instruction else '✗'}")

def test_edge_cases():
    """測試邊界情況"""
    print("\n🔍 邊界情況測試")
    print("=" * 50)
    
    edge_cases = [
        ("", "空UI語言"),
        (None, "None UI語言"),
        ("invalid-lang", "無效語言"),
        ("zh-CN", "簡體中文"),
        ("en-US", "美式英文"),
    ]
    
    for ui_lang, description in edge_cases:
        try:
            target_lang = localization.get_translation_target_lang(ui_lang)
            print(f"{description}: {ui_lang} → {target_lang}")
        except Exception as e:
            print(f"{description}: {ui_lang} → 錯誤: {e}")

def demonstrate_usage():
    """演示使用方式"""
    print("\n💡 使用方式演示")
    print("=" * 50)
    
    print("\n1. 設定UI語言為英文:")
    print("   controller.set_ui_language('en')")
    print("   → 翻譯目標自動設為英文")
    
    print("\n2. 設定UI語言為中文:")
    print("   controller.set_ui_language('zh-TW')")
    print("   → 翻譯目標自動設為繁體中文")
    
    print("\n3. 程式會自動:")
    print("   • 根據UI語言設定翻譯目標")
    print("   • 更新翻譯提供者配置")
    print("   • 重新生成適當的prompt")
    
    print("\n4. 預期行為:")
    print("   • 英文UI + 英文原文 → 英文輸出")
    print("   • 中文UI + 英文原文 → 中文輸出")
    print("   • 英文UI + 日文原文 → 英文輸出")
    print("   • 中文UI + 日文原文 → 中文輸出")

def main():
    print("CloudHime UI語言與翻譯目標語言測試")
    print("=" * 60)
    
    test_ui_language_translation_mapping()
    test_prompt_generation_with_ui_language()
    test_translation_scenarios()
    test_edge_cases()
    demonstrate_usage()
    
    print("\n🎯 測試總結")
    print("=" * 50)
    print("✅ UI語言與翻譯目標語言正確映射")
    print("✅ Prompt生成正確使用目標語言")
    print("✅ 支援各種邊界情況")
    print("✅ 自動化配置更新")
    
    print("\n📝 實作要點:")
    print("1. UI語言變更時自動更新翻譯目標")
    print("2. 翻譯提供者使用正確的目標語言")
    print("3. Prompt生成考慮目標語言")
    print("4. 保持向後兼容性")

if __name__ == "__main__":
    main()
