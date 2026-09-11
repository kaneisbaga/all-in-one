import os
import re
import sys
import time
import webbrowser
from pathlib import Path

def get_urls_from_txt_files(folder_path: Path) -> list[str]:
    """掃描資料夾內所有 .txt 檔案，並提取其中的網址"""
    url_pattern = re.compile(r'https?://[^\s"\'<>]+')
    urls = []
    seen = set()

    txt_files = list(folder_path.glob("*.txt"))
    if not txt_files:
        return []

    for file_path in txt_files:
        # 嘗試 UTF-8 與預設編碼讀取
        content = ""
        for encoding in ("utf-8", "utf-8-sig", "cp950", "gbk"):
            try:
                content = file_path.read_text(encoding=encoding)
                break
            except Exception:
                continue

        if content:
            matches = url_pattern.findall(content)
            for url in matches:
                # 剔除尾端標點符號
                cleaned_url = url.rstrip(".,;:)]}")
                if cleaned_url and cleaned_url not in seen:
                    seen.add(cleaned_url)
                    urls.append(cleaned_url)

    return urls

def main():
    folder = Path(__file__).resolve().parent
    urls = get_urls_from_txt_files(folder)

    if not urls:
        print("【提示】未在同資料夾的 .txt 檔案中找到任何有效網址 (需以 http:// 或 https:// 開頭)！")
        input("\n請按 Enter 鍵關閉...")
        return

    print("=" * 45)
    print(f" 共找到 {len(urls)} 個網址：")
    print("=" * 45)
    for url in urls:
        print(f"  -> {url}")
    print()

    if len(urls) >= 10:
        confirm = input(f"網址數量較多 ({len(urls)} 個)，確定要全部開啟嗎？(Y/n): ").strip().lower()
        if confirm == 'n':
            print("已取消開啟。")
            time.sleep(1)
            return

    print("正在使用預設瀏覽器開啟網頁...")
    for url in urls:
        webbrowser.open(url)
        time.sleep(0.15)  # 稍微間隔，避免瀏覽器同時處理過多標籤頁而遺漏

    print("\n所有網頁已開啟完成！")
    time.sleep(1)

if __name__ == "__main__":
    main()
