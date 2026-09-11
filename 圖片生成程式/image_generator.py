import os
import sys
import time
import re
import urllib.parse
import urllib.request
import json

# 強制 Windows console 使用 UTF-8 編碼
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stdin.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 常用詞彙智慧對照表
SMART_DICT = {
    "貓": "cat, fluffy detailed fur", "狗": "dog, highly detailed fur", "女孩": "girl", 
    "少女": "anime girl, intricate details", "男孩": "boy",
    "美少女": "beautiful anime girl, masterpiece", "帥哥": "handsome man", "機器人": "futuristic robot, octane render",
    "動漫": "anime style, key visual, Kyoto Animation style", "寫實": "photorealistic, 8k raw photo, DSLR", 
    "二次元": "anime artwork, vibrant colors", "賽博朋克": "cyberpunk, glowing neon lights, ray tracing", 
    "科幻": "sci-fi, futuristic, unreal engine 5", "星空": "starry night sky, cosmic nebula, sparkling stars", 
    "大海": "crystal clear blue ocean", "海邊": "sunny tropical beach", "雨": "rainy day, wet asphalt reflections",
    "森林": "mystical enchanted forest, sunbeams", "古堡": "ancient gothic castle, dramatic volumetric lighting",
    "健身": "fitness workout, muscular, athletic gym outfit", "帥氣": "cool, stylish",
    "可愛": "cute, adorable", "清涼": "summer outfit, light clothing", "放鬆": "relaxing, peaceful atmosphere"
}

def translate_and_enhance(prompt):
    """
    超高畫質提示詞增強引擎
    加入 8K UHD, Unreal Engine 5, Ray Tracing 等極致畫質關鍵字
    """
    enhanced_terms = []
    
    for zh, en in SMART_DICT.items():
        if zh in prompt:
            enhanced_terms.append(en)
            
    has_chinese = bool(re.search(r'[\u4e00-\u9fa5]', prompt))
    translated_base = prompt
    
    if has_chinese:
        try:
            url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(prompt)}&langpair=zh-TW|en"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('responseData') and data['responseData'].get('translatedText'):
                    translated_base = data['responseData']['translatedText']
        except Exception:
            pass

    # 頂級畫質修飾詞 (8K, 超高精細, 光線追蹤, 銳利對焦)
    ultra_quality_boosters = "masterpiece, 8k resolution, ultra detailed, extremely sharp focus, cinematic volumetric lighting, ray tracing, unreal engine 5 render, award winning quality"
    
    if enhanced_terms:
        final_prompt = f"{translated_base}, {', '.join(enhanced_terms)}, {ultra_quality_boosters}"
    else:
        final_prompt = f"{translated_base}, {ultra_quality_boosters}"
        
    return final_prompt

def generate_image(prompt, width=1440, height=1440, model="flux"):
    """
    生成 1440x1440 2K 級超高清解析度圖片
    """
    print(f"\n[💎 極致畫質模式] 正在生成 2K 超高清圖片...")
    enhanced_prompt = translate_and_enhance(prompt)
    print(f"原始輸入: \"{prompt}\"")
    print(f"✨ 8K畫質增強 Prompt: \"{enhanced_prompt}\"")
    print(f"📐 高解析度規格: {width}x{height} (2K Ultra-HD) | 模型: {model}")
    
    encoded_prompt = urllib.parse.quote(enhanced_prompt)
    
    # 建構 API URL，啟用高畫質渲染與畫質增強標籤
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&model={model}&nologo=true&enhance=true"
    
    timestamp = int(time.time())
    filename = f"ultra_hd_{timestamp}.jpg"
    filepath = os.path.join(os.getcwd(), filename)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        start_time = time.time()
        with urllib.request.urlopen(req, timeout=90) as response, open(filepath, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
        
        elapsed = round(time.time() - start_time, 2)
        print(f"\n[成功] 2K超高清圖片繪製完成！(耗時 {elapsed} 秒)")
        print(f"📁 儲存路徑: {filepath}")
        return filepath
    except Exception as e:
        print(f"\n[錯誤] 生成圖片時發生例外: {e}")
        return None

def main():
    print("============================================================")
    print("      💎 2K Ultra-HD 頂級畫質 AI 繪圖生成器")
    print("      解析度提升至 1440x1440 • 注入 8K 物理光影質感")
    print("============================================================")
    
    while True:
        try:
            print("\n------------------------------------------------------------")
            prompt = input("請輸入您的提示詞 Prompt (輸入 'q' 退出): ").strip()
            
            if not prompt:
                continue
            if prompt.lower() in ['q', 'exit', 'quit']:
                print("感謝使用，程式已關閉！")
                break
            
            generate_image(prompt)
            
        except KeyboardInterrupt:
            print("\n程式已手動中斷。")
            break

if __name__ == "__main__":
    main()
