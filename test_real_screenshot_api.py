#!/usr/bin/env python3
"""
真實API截圖翻譯測試
使用實際的Google API測試截圖翻譯功能
"""

import sys
import os
import time
from pathlib import Path

# 添加專案根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent))

import cv2
import google.generativeai as genai
from translation_helpers import (
    encode_image_for_ai,
    is_valid_screenshot_translation,
    clean_screenshot_translation_output,
    build_gemma_screenshot_prompt_v3
)

# 設置API密鑰
GOOGLE_API_KEY = "AIzaSyDYkNOsjWsDH3cbnrYwRu449Mt1Q7LYE24"

def load_test_image():
    """載入測試圖片"""
    image_path = Path(__file__).parent / "example" / "2026-05-01 14 21 52.png"
    
    if not image_path.exists():
        print(f"❌ 找不到圖片: {image_path}")
        return None
    
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"❌ 無法載入圖片: {image_path}")
        return None
    
    print(f"✅ 成功載入圖片: {image_path}")
    print(f"   圖片尺寸: {img.shape}")
    return img

def setup_api():
    """設置API"""
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        print("✅ API配置成功")
        return True
    except Exception as e:
        print(f"❌ API配置失敗: {e}")
        return False

def test_single_model(model_name, img, prompt):
    """測試單個模型"""
    print(f"\n🤖 測試模型: {model_name}")
    print("-" * 50)
    
    try:
        # 編碼圖片
        encoded_image = encode_image_for_ai(img)
        if not encoded_image:
            print("❌ 圖片編碼失敗")
            return None
        
        # 準備API請求
        model = genai.GenerativeModel(model_name)
        
        # 創建圖片部分
        image_part = {
            "mime_type": "image/png",
            "data": encoded_image
        }
        
        print(f"📤 發送請求到 {model_name}...")
        start_time = time.time()
        
        # 發送請求
        response = model.generate_content(
            contents=[prompt, image_part],
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2048,
            )
        )
        
        end_time = time.time()
        print(f"⏱️  響應時間: {end_time - start_time:.2f} 秒")
        
        # 獲取結果
        raw_output = response.text
        print(f"📤 原始輸出長度: {len(raw_output)} 字符")
        print(f"📤 原始輸出: {raw_output[:200]}{'...' if len(raw_output) > 200 else ''}")
        
        # 清理輸出
        cleaned_output = clean_screenshot_translation_output(raw_output)
        print(f"🧹 清理後長度: {len(cleaned_output)} 字符")
        print(f"🧹 清理後內容: {cleaned_output}")
        
        # 驗證結果
        is_valid = is_valid_screenshot_translation(cleaned_output)
        print(f"✅ 驗證結果: {'通過' if is_valid else '失敗'}")
        
        # 檢查是否會fallback
        will_fallback = len(cleaned_output.strip()) < 1
        print(f"🔄 Fallback: {'是' if will_fallback else '否'}")
        
        return {
            "model": model_name,
            "raw_output": raw_output,
            "cleaned_output": cleaned_output,
            "is_valid": is_valid,
            "will_fallback": will_fallback,
            "response_time": end_time - start_time,
            "success": True
        }
        
    except Exception as e:
        print(f"❌ 模型 {model_name} 測試失敗: {e}")
        return {
            "model": model_name,
            "error": str(e),
            "success": False
        }

def test_all_models(img):
    """測試所有模型"""
    print("\n🎯 開始真實API測試")
    print("=" * 60)
    
    # 模擬OCR結果（基於圖片內容）
    ocr_texts = [
        "合輯 - 【空之境界 第五章 預告片…】",
        "合輯是 YouTube 幫你整理的播放清單"
    ]
    
    # 生成prompt
    prompt = build_gemma_screenshot_prompt_v3(ocr_texts, "zh-TW")
    print(f"📝 Prompt長度: {len(prompt)} 字符")
    print(f"📝 Prompt預覽: {prompt[:150]}...")
    
    # 要測試的模型列表
    models_to_test = [
        "gemma-3-1b-it",
        "gemma-3-27b-it", 
        "gemma-4-31b-it"
    ]
    
    results = []
    
    for model in models_to_test:
        print(f"\n{'='*60}")
        result = test_single_model(model, img, prompt)
        results.append(result)
        
        # 添加延遲避免速率限制
        if result and result.get("success"):
            print("⏳ 等待 3 秒避免速率限制...")
            time.sleep(3)
    
    return results

def analyze_results(results):
    """分析測試結果"""
    print("\n📊 測試結果分析")
    print("=" * 60)
    
    successful_results = [r for r in results if r.get("success", False)]
    failed_results = [r for r in results if not r.get("success", False)]
    
    print(f"✅ 成功測試: {len(successful_results)}/{len(results)}")
    print(f"❌ 失敗測試: {len(failed_results)}/{len(results)}")
    
    if successful_results:
        print(f"\n📈 成功測試詳情:")
        for result in successful_results:
            model = result["model"]
            response_time = result["response_time"]
            is_valid = result["is_valid"]
            will_fallback = result["will_fallback"]
            output_length = len(result["cleaned_output"])
            
            print(f"  🤖 {model}:")
            print(f"     ⏱️  響應時間: {response_time:.2f}s")
            print(f"     📏 輸出長度: {output_length} 字符")
            print(f"     ✅ 驗證結果: {'通過' if is_valid else '失敗'}")
            print(f"     🔄 Fallback: {'是' if will_fallback else '否'}")
            print()
    
    if failed_results:
        print(f"\n❌ 失敗測試詳情:")
        for result in failed_results:
            model = result["model"]
            error = result.get("error", "未知錯誤")
            print(f"  🤖 {model}: {error}")
    
    # 統計分析
    if successful_results:
        valid_count = sum(1 for r in successful_results if r["is_valid"])
        fallback_count = sum(1 for r in successful_results if r["will_fallback"])
        avg_response_time = sum(r["response_time"] for r in successful_results) / len(successful_results)
        
        print(f"\n📊 統計分析:")
        print(f"  ✅ 驗證通過率: {valid_count}/{len(successful_results)} ({valid_count/len(successful_results)*100:.1f}%)")
        print(f"  🔄 Fallback率: {fallback_count}/{len(successful_results)} ({fallback_count/len(successful_results)*100:.1f}%)")
        print(f"  ⏱️  平均響應時間: {avg_response_time:.2f}s")
        
        # 輸出樣本展示
        print(f"\n📝 輸出樣本展示:")
        for result in successful_results:
            if result["cleaned_output"]:
                print(f"  🤖 {result['model']}:")
                print(f"     {result['cleaned_output'][:100]}{'...' if len(result['cleaned_output']) > 100 else ''}")
                print()

def main():
    print("CloudHime 真實API截圖翻譯測試")
    print("=" * 60)
    print("⚠️  注意: 這會使用真實的Google API")
    print("⚠️  可能會產生API費用")
    print()
    
    # 設置API
    if not setup_api():
        print("❌ 無法設置API，退出測試")
        return
    
    # 載入圖片
    img = load_test_image()
    if img is None:
        print("❌ 無法載入圖片，退出測試")
        return
    
    # 確認是否繼續
    print("\n🤔 確認要進行真實API測試嗎？")
    print("這會使用Google API並可能產生費用")
    print("按 Enter 繼續，Ctrl+C 取消...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n❌ 用戶取消測試")
        return
    
    # 執行測試
    results = test_all_models(img)
    
    # 分析結果
    analyze_results(results)
    
    print("\n🎉 測試完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
