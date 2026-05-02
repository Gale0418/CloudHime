#!/usr/bin/env python3
"""
演示使用者如何在CloudHime設定中使用自訂prompt
"""

import sys
from pathlib import Path

# 添加專案根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent))

from translation_helpers import build_gemma_prompt_with_override

def demo_user_scenarios():
    """演示用戶使用場景"""
    print("👤 CloudHime 使用者自訂Prompt 實際使用演示")
    print("=" * 60)
    
    scenarios = [
        {
            "user_type": "遊戲玩家",
            "goal": "翻譯遊戲文本",
            "custom_prompt": "請翻譯成遊戲風格，使用台灣玩家常用用語，保持簡潔有力",
            "example_text": "Start Game",
            "expected_style": "開始遊戲"
        },
        {
            "user_type": "技術文檔翻譯者",
            "goal": "翻譯技術內容",
            "custom_prompt": "請使用專業技術術語，保持準確性，避免過度口語化",
            "example_text": "System Configuration",
            "expected_style": "系統設定"
        },
        {
            "user_type": "小說翻譯者",
            "goal": "翻譯文學作品",
            "custom_prompt": "請保持文學性，使用優美的中文表達，保留原文情感色彩",
            "example_text": "The moonlight illuminated the path",
            "expected_style": "月光照亮了小徑"
        },
        {
            "user_type": "UI設計師",
            "goal": "翻譯介面文字",
            "custom_prompt": "請保持簡潔，符合UI設計規範，字數控制在原文的1.5倍內",
            "example_text": "Save Progress",
            "expected_style": "儲存進度"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n📋 場景 {i}: {scenario['user_type']}")
        print(f"目標: {scenario['goal']}")
        print("-" * 40)
        
        print(f"自訂Prompt: {scenario['custom_prompt']}")
        print(f"範例文本: {scenario['example_text']}")
        
        # 模擬不同模型的處理
        models = ["gemma-3-1b-it", "gemma-3-27b-it", "gemma-4-31b-it"]
        
        for model in models:
            prompt = build_gemma_prompt_with_override(
                scenario['example_text'], 
                scenario['custom_prompt'], 
                "zh-TW", 
                model
            )
            
            print(f"\n{model} 處理:")
            print(f"  Prompt長度: {len(prompt)} 字符")
            print(f"  包含自訂指令: {'✓' if scenario['custom_prompt'] in prompt else '✗'}")
            print(f"  預期風格: {scenario['expected_style']}")

def demo_settings_workflow():
    """演示設定工作流程"""
    print("\n⚙️ 設定工作流程演示")
    print("=" * 60)
    
    steps = [
        {
            "step": "1. 開啟設定面板",
            "action": "點擊CloudHime主介面的設定按鈕",
            "screenshot": "設定面板開啟"
        },
        {
            "step": "2. 切換到翻譯設定",
            "action": "在左側選單選擇「翻譯功能」",
            "screenshot": "翻譯設定頁面"
        },
        {
            "step": "3. 選擇AI模式",
            "action": "點擊「Gemma AI 翻譯」選項",
            "screenshot": "AI模式已選中"
        },
        {
            "step": "4. 輸入API Key",
            "action": "在「Google API KEY」欄位輸入有效的API密鑰",
            "screenshot": "API Key已輸入"
        },
        {
            "step": "5. 選擇AI模型",
            "action": "從「AI 模型」下拉選單選擇（建議Gemma 3 27B）",
            "screenshot": "模型已選擇"
        },
        {
            "step": "6. 輸入自訂Prompt",
            "action": "在「Gemma Prompt」文字框輸入自訂指令",
            "screenshot": "自訂Prompt已輸入"
        },
        {
            "step": "7. 儲存設定",
            "action": "點擊「儲存」按鈕",
            "screenshot": "設定已儲存"
        },
        {
            "step": "8. 測試翻譯",
            "action": "選擇任意文本進行翻譯測試",
            "screenshot": "翻譯結果符合自訂風格"
        }
    ]
    
    for step in steps:
        print(f"\n{step['step']}")
        print(f"操作: {step['action']}")
        print(f"結果: {step['screenshot']}")

def demo_prompt_examples():
    """演示實用的prompt範例"""
    print("\n💡 實用Prompt範例")
    print("=" * 60)
    
    categories = [
        {
            "category": "風格控制",
            "prompts": [
                "請保持簡潔風格，不要多餘解釋",
                "使用正式語氣，專業用語",
                "保持口語化，像對話一樣自然",
                "使用文學性表達，優美文字"
            ]
        },
        {
            "category": "內容類型",
            "prompts": [
                "這是遊戲UI文字，請使用遊戲用語",
                "這是技術文檔，請使用準確術語",
                "這是小說對話，請保持情感色彩",
                "這是商業文件，請使用正式語氣"
            ]
        },
        {
            "category": "本地化要求",
            "prompts": [
                "使用台灣本地化用語",
                "避免大陸用語，使用台灣慣用語",
                "考慮台灣文化背景",
                "使用台灣常見的表達方式"
            ]
        },
        {
            "category": "限制條件",
            "prompts": [
                "字數控制在原文的1.5倍內",
                "不要添加任何解釋或註釋",
                "保持原文的換行格式",
                "避免過度修飾，保持原意"
            ]
        }
    ]
    
    for category in categories:
        print(f"\n📂 {category['category']}:")
        for prompt in category['prompts']:
            print(f"  • {prompt}")

def demo_best_practices():
    """演示最佳實踐"""
    print("\n🎯 最佳實踐建議")
    print("=" * 60)
    
    practices = [
        {
            "practice": "保持簡潔",
            "description": "自訂prompt應該簡潔明確，避免過長",
            "example": "✓ 請使用遊戲用語  ✗ 請使用遊戲用語，並且要注意保持簡潔，不要過於冗長..."
        },
        {
            "practice": "明確目標",
            "description": "清楚說明想要的翻譯風格和要求",
            "example": "✓ 請翻譯成技術文檔風格  ✗ 請翻譯得好一點"
        },
        {
            "practice": "結合模型優勢",
            "description": "利用模型特定的優化，不要完全覆蓋",
            "example": "✓ 補充模型預設指令  ✗ 完全替換所有指令"
        },
        {
            "practice": "測試調整",
            "description": "根據實際翻譯結果調整prompt",
            "example": "✓ 觀察結果 → 微調prompt → 再測試  ✗ 一次設定從不修改"
        }
    ]
    
    for practice in practices:
        print(f"\n📋 {practice['practice']}:")
        print(f"說明: {practice['description']}")
        print(f"範例: {practice['example']}")

def demo_troubleshooting():
    """演示疑難排解"""
    print("\n🔧 疑難排解")
    print("=" * 60)
    
    issues = [
        {
            "issue": "自訂prompt沒有效果",
            "possible_causes": [
                "prompt過於模糊",
                "與預設指令衝突",
                "模型不理解指令"
            ],
            "solutions": [
                "使用更明確的指令",
                "檢查prompt語法",
                "嘗試不同模型"
            ]
        },
        {
            "issue": "翻譯結果不穩定",
            "possible_causes": [
                "prompt過於複雜",
                "模型限制",
                "文本類型不適合"
            ],
            "solutions": [
                "簡化prompt",
                "切換到更強的模型",
                "分段處理長文本"
            ]
        },
        {
            "issue": "翻譯風格不符合預期",
            "possible_causes": [
                "指令描述不夠具體",
                "模型理解偏差",
                "語言文化差異"
            ],
            "solutions": [
                "提供具體範例",
                "增加風格描述",
                "考慮本地化因素"
            ]
        }
    ]
    
    for issue in issues:
        print(f"\n❓ {issue['issue']}:")
        print("可能原因:")
        for cause in issue['possible_causes']:
            print(f"  • {cause}")
        print("解決方案:")
        for solution in issue['solutions']:
            print(f"  • {solution}")

def main():
    print("CloudHime 使用者自訂Prompt 完整使用指南")
    print("=" * 60)
    
    demo_user_scenarios()
    demo_settings_workflow()
    demo_prompt_examples()
    demo_best_practices()
    demo_troubleshooting()
    
    print("\n🎉 總結")
    print("=" * 60)
    print("✅ 使用者可以輕鬆自訂翻譯風格")
    print("✅ 自訂prompt與模型優化完美結合")
    print("✅ 支援各種翻譯場景和需求")
    print("✅ 提供完整的疑難排解指南")
    
    print("\n🚀 立即開始:")
    print("1. 開啟CloudHime設定")
    print("2. 輸入你的自訂prompt")
    print("3. 開始享受個人化翻譯！")

if __name__ == "__main__":
    main()
