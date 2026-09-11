"""核心工具模組"""

import re


def format_time_input(text: str) -> str:
    """
    自動格式化時間輸入
    1634   → 16:34
    12301  → 1:23:01
    9      → 0:09
    123    → 1:23
    只保留數字，自動插入冒號
    """
    digits = re.sub(r"\D", "", text)
    if not digits:
        return "0:00"

    n = len(digits)
    if n <= 2:
        # 最多2位：秒
        return f"0:{digits.zfill(2)}"
    elif n == 3:
        # 3位：m:ss
        return f"{digits[0]}:{digits[1:]}"
    elif n == 4:
        # 4位：mm:ss
        return f"{digits[:2]}:{digits[2:]}"
    elif n == 5:
        # 5位：h:mm:ss
        return f"{digits[0]}:{digits[1:3]}:{digits[3:]}"
    elif n == 6:
        # 6位：hh:mm:ss
        return f"{digits[:2]}:{digits[2:4]}:{digits[4:]}"
    else:
        # 超過6位：取最後6位
        digits = digits[-6:]
        return f"{digits[:2]}:{digits[2:4]}:{digits[4:]}"


def parse_time(text: str) -> float:
    """將時間字串解析為秒數（浮點數）"""
    text = text.strip()
    parts = text.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        return 0.0
    return 0.0


def seconds_to_time_str(seconds: float, show_ms: bool = False) -> str:
    """將秒數轉換為時間字串"""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if show_ms:
        if h > 0:
            return f"{h}:{m:02d}:{s:06.3f}"
        else:
            return f"{m}:{s:06.3f}"
    else:
        si = int(s)
        if h > 0:
            return f"{h}:{m:02d}:{si:02d}"
        else:
            return f"{m}:{si:02d}"
