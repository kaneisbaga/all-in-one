import os
import re
import sys
import time
import datetime
import urllib.request
import urllib.parse
import threading
import queue
import itertools
import concurrent.futures
import ctypes
from playwright.sync_api import sync_playwright

# 強制 Windows 終端機以 UTF-8 輸出，避免 CP950 編碼錯誤
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# 設定檔案與下載路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TXT_FILE_PATH = os.path.join(BASE_DIR, "待下載.txt")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

RETRY_PREFIX = "#重試:"
DEFAULT_MAX_WORKERS = 10  # M3U8 併發下載執行緒數 (P1 優化)
DEFAULT_RETRY_DELAY = 3600  # 下載失敗後隔 1 小時 (3600 秒) 重新嘗試

# 偵測影片已刪除或不存在的關鍵字（頁面標題或內文）
DELETED_KEYWORDS = [
    "影片已刪除", "此影片已被刪除", "視頻已刪除", "已被刪除",
    "不存在", "找不到", "無法找到", "404", "找不到影片", "影片不存在",
    "視頻不存在", "找不到此影片", "抱歉，您訪問的頁面不存在", "您要查看的頁面不存在",
    "該視頻已被刪除", "此帖不存在", "帖子不存在", "頁面不存在", "該影片不存在",
    "該視頻不存在", "已被管理員刪除", "私有影片", "未發布", "版權原因",
    "video not found", "video has been deleted", "deleted", "file not found", "not found"
]

# Windows 電源管理防休眠常數
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_AWAYMODE_REQUIRED = 0x00000040

def prevent_sleep():
    """防止系統在下載進行中進入休眠狀態"""
    if sys.platform.startswith('win'):
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
            )
        except Exception:
            pass

def allow_sleep():
    """恢復系統預設休眠行為"""
    if sys.platform.startswith('win'):
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        except Exception:
            pass

def clean_part_files(directory: str):
    """清理下載目錄中殘留的 .part 暫存檔"""
    try:
        if os.path.exists(directory):
            for f in os.listdir(directory):
                if f.endswith(".part"):
                    part_path = os.path.join(directory, f)
                    try:
                        os.remove(part_path)
                    except Exception:
                        pass
    except Exception:
        pass

def is_valid_title(title: str) -> bool:
    """驗證標題是否為真實有效的影片標題，而非載入中狀態或預設頁面標題"""
    if not title:
        return False
    t = title.strip()
    if not t:
        return False
    t_lower = t.lower()
    if t_lower in ("about:blank", "blank", "just a moment...", "just a moment", "eyny", "伊莉影片區", "伊莉討論區"):
        return False
    if t_lower.startswith("loading") or t_lower.startswith("http://") or t_lower.startswith("https://"):
        return False
    return True

def clean_video_title(title: str) -> str:
    """清理影片標題，移除常見網站後綴（如 - 伊莉影片區 等）與載入字樣"""
    if not title:
        return ""
    cleaned = title.strip()
    # 移除網站常見後綴
    cleaned = re.sub(r'\s*-\s*伊莉影片區.*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*-\s*影片\s*-\s*伊莉討論區.*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*-\s*eyny.*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*-\s*伊莉.*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    return cleaned if cleaned else title.strip()

def sanitize_filename(filename: str) -> str:
    """清理檔名中 Windows 不合法的半形字元，保留中文及全形符號，並限制長度"""
    cleaned = clean_video_title(filename)
    cleaned = re.sub(r'[\\/*?"<>|]', "", cleaned)
    cleaned = re.sub(r'[\x00-\x1f\x7f]', "", cleaned)
    cleaned = cleaned.replace(":", "：")
    cleaned = cleaned.strip()
    if len(cleaned) > 150:
        cleaned = cleaned[:150].rstrip()
    return cleaned

IGNORE_CODE_WORDS = {
    'MP', 'HD', 'FHD', 'UHD', 'P', 'K', 'EP', 'VOL', 'NO', 'PART', 'PAGE', 'V',
    'WWW', 'HTTPS', 'HTTP', 'EYNY', 'VIDEO', 'VID', 'DOWNLOAD', 'FPS', 'X264',
    'X265', 'H264', 'H265', 'HEVC', '1080P', '720P', '480P', '360P', '240P', '144P', '4K', '2K'
}

def extract_video_code(title: str) -> str | None:
    """從標題或檔名中擷取影片番號（如 FNS-013, FSDSS-929, FC2-PPV-1234567, S2M-020 等）
    
    回傳標準化番號（大寫英文-數字格式）或 None
    """
    if not title:
        return None
        
    # 1. 處理 FC2-PPV / FC2
    m_fc2 = re.search(r'(?:FC2[-_\s]*(?:PPV)?[-_\s]*)(\d{4,8})', title, re.IGNORECASE)
    if m_fc2:
        if 'ppv' in title.lower():
            return f'FC2-PPV-{m_fc2.group(1)}'
        return f'FC2-{m_fc2.group(1)}'
        
    # 2. 處理 HEYZO
    m_heyzo = re.search(r'HEYZO[-_\s]*(\d{3,6})', title, re.IGNORECASE)
    if m_heyzo:
        return f'HEYZO-{m_heyzo.group(1)}'

    # 3. 處理標準番號: 英數代碼 (至少含1個字母) + 分隔符 (-, _, 空白) + 數字
    # 例如 FSDSS-929, FNS-013, S2M-020, T28-555, ABP-123
    m_sep = re.search(r'(?<![A-Za-z0-9])(?=[A-Za-z0-9]*[A-Za-z])([A-Za-z0-9]{2,10})[-_\s](\d{2,8})(?![A-Za-z0-9])', title)
    if m_sep:
        letters = m_sep.group(1).upper()
        digits = m_sep.group(2)
        if letters not in IGNORE_CODE_WORDS and not re.match(r'^\d+$', letters):
            return f'{letters}-{digits}'

    # 4. 比對無分隔符但標準英文字母 (3~6位) + 數字 (3~5位) 例如 FSDSS929, FNS013
    m_nosep = re.search(r'(?<![A-Za-z0-9])([A-Za-z]{3,6})(\d{3,5})(?![A-Za-z0-9])', title)
    if m_nosep:
        letters = m_nosep.group(1).upper()
        digits = m_nosep.group(2)
        if letters not in IGNORE_CODE_WORDS:
            return f'{letters}-{digits}'

    return None

def find_existing_duplicate_file(download_dir: str, title: str) -> tuple[bool, str, str]:
    """檢查下載目錄中是否已存在相同番號或完全相同標題的影片
    
    回傳: (is_duplicate, reason, matched_file_name)
    """
    if not os.path.exists(download_dir):
        return False, "", ""
        
    code = extract_video_code(title)
    
    try:
        files = os.listdir(download_dir)
    except Exception:
        return False, "", ""
        
    for fname in files:
        if fname.endswith(".part") or not fname.lower().endswith((".mp4", ".mkv", ".ts", ".flv", ".avi", ".wmv")):
            continue
            
        full_path = os.path.join(download_dir, fname)
        try:
            if not os.path.isfile(full_path) or os.path.getsize(full_path) == 0:
                continue
        except Exception:
            continue
            
        # 1. 番號比對
        if code:
            existing_code = extract_video_code(fname)
            if existing_code and existing_code == code:
                return True, f"番號重複 [{code}]", fname
                
        # 2. 完全相同標題檔名比對
        safe_name = sanitize_filename(title)
        if safe_name:
            fname_no_ext = os.path.splitext(fname)[0]
            if fname_no_ext == safe_name:
                return True, "標題完全相同", fname
                
    return False, "", ""

def get_unique_dest_path(download_dir: str, title: str) -> tuple[str, str]:
    """生成不衝突的下載檔案路徑，若已有同名檔案自動加上 (1), (2)...
    
    回傳: (dest_path, filename)
    """
    safe_name = sanitize_filename(title)
    if not safe_name:
        safe_name = f"eyny_video_{int(time.time())}"
    
    filename = f"{safe_name}.mp4"
    dest_path = os.path.join(download_dir, filename)
    if not os.path.exists(dest_path):
        return dest_path, filename
        
    counter = 1
    while True:
        candidate_name = f"{safe_name} ({counter}).mp4"
        candidate_path = os.path.join(download_dir, candidate_name)
        if not os.path.exists(candidate_path):
            return candidate_path, candidate_name
        counter += 1

def check_is_403(status: int = 0, title: str = "", page_text: str = "", html_content: str = "") -> bool:
    """判斷頁面是否出現 403 Forbidden 或存取被拒"""
    if status == 403:
        return True
    t_lower = (title or "").lower()
    if "403 forbidden" in t_lower or "403 - forbidden" in t_lower or (t_lower.startswith("403") and "forbidden" in t_lower):
        return True
    b_lower = (page_text or "").lower()
    if "403 forbidden" in b_lower or "403 - forbidden" in b_lower or "403 access denied" in b_lower or "http 403" in b_lower:
        return True
    h_lower = (html_content or "").lower()
    if "<title>403 forbidden</title>" in h_lower or "<h1>403 forbidden</h1>" in h_lower or "403 - forbidden" in h_lower:
        return True
    return False

def get_available_resolutions(page, html_content: str = "", current_url: str = "") -> dict[str, dict]:
    """獲取頁面中所有可用的 480、360、240、144 畫質資訊
    
    回傳字典格式:
    {
        '480': {'href': str, 'isActive': bool, 'isLink': bool},
        ...
    }
    """
    TARGET_RESOLUTIONS = {'480', '360', '240', '144'}
    found = {}
    
    # 1. 檢查目前 URL query
    if current_url:
        m_curr = re.search(r'size=(\d+)', current_url)
        if m_curr and m_curr.group(1) in TARGET_RESOLUTIONS:
            found[m_curr.group(1)] = {'href': current_url, 'isActive': True, 'isLink': False}

    # 2. 快速從 HTML 字串正規表示式比對
    if html_content:
        for m in re.finditer(r'<a[^>]*href="([^"]*size=(480|360|240|144)[^"]*)"[^>]*>', html_content, re.IGNORECASE):
            href, res = m.group(1), m.group(2)
            if res not in found:
                found[res] = {'href': href, 'isActive': False, 'isLink': True}
                
        for m in re.finditer(r'<font[^>]*style="([^"]*)"[^>]*>\s*(480|360|240|144)\s*</font>', html_content, re.IGNORECASE):
            style, res = m.group(1).lower(), m.group(2)
            is_active = 'red' in style or '#f' in style or 'rgb(255' in style
            if res not in found or is_active:
                found[res] = {'href': found.get(res, {}).get('href', ''), 'isActive': is_active, 'isLink': found.get(res, {}).get('isLink', False)}

        for m in re.finditer(r'<font[^>]*#(?:333|000|222|111)[^>]*>\s*(480|360|240|144)\s*</font>', html_content, re.IGNORECASE):
            res = m.group(1)
            if res not in found:
                found[res] = {'href': found.get(res, {}).get('href', ''), 'isActive': False, 'isLink': found.get(res, {}).get('isLink', False)}

    # 3. 從 DOM 元素深入評估
    if page:
        try:
            dom_res = page.evaluate('''() => {
                const targets = ['480', '360', '240', '144'];
                const resMap = {};
                
                // 檢查包含 size= 的超連結
                const sizeLinks = document.querySelectorAll('a[href*="size="]');
                for (let a of sizeLinks) {
                    const href = a.getAttribute('href') || '';
                    const m = href.match(/size=(\\d+)/);
                    if (m && targets.includes(m[1])) {
                        const style = window.getComputedStyle(a);
                        const inlineStyle = a.getAttribute('style') || '';
                        const isActive = inlineStyle.includes('red') || style.backgroundColor.includes('rgb(255, 0, 0)');
                        resMap[m[1]] = { href: href, isActive: isActive, isLink: true };
                    }
                }
                
                // 檢查所有標籤中的畫質標籤 (font, a, span, button 等)
                const elements = document.querySelectorAll('font, a, span, button, div, b, strong');
                for (let el of elements) {
                    const text = el.innerText ? el.innerText.trim() : '';
                    if (targets.includes(text)) {
                        const style = window.getComputedStyle(el);
                        const bg = style.backgroundColor;
                        const inlineStyle = el.getAttribute('style') || '';
                        const parent = el.parentElement;
                        const parentHref = parent && parent.tagName === 'A' ? (parent.getAttribute('href') || '') : '';
                        
                        const isBadge = parentHref.includes('size=') ||
                                        inlineStyle.includes('#333') || 
                                        inlineStyle.includes('#000') || 
                                        inlineStyle.includes('red') ||
                                        bg.includes('rgb(51, 51, 51)') || 
                                        bg.includes('rgb(0, 0, 0)') ||
                                        bg.includes('rgb(255, 0, 0)') ||
                                        style.border.includes('solid');
                                        
                        if (isBadge) {
                            const isActive = inlineStyle.includes('red') || bg.includes('rgb(255, 0, 0)');
                            const href = parentHref || (el.tagName === 'A' ? (el.getAttribute('href') || '') : '');
                            if (!resMap[text] || isActive) {
                                resMap[text] = {
                                    href: href || (resMap[text] ? resMap[text].href : ''),
                                    isActive: isActive,
                                    isLink: Boolean(href)
                                };
                            }
                        }
                    }
                }
                return resMap;
            }''')
            if dom_res and isinstance(dom_res, dict):
                for k, v in dom_res.items():
                    if k not in found or v.get('isActive'):
                        found[k] = v
        except Exception:
            pass
            
    return found

def select_best_resolution(available_map: dict) -> str | None:
    """依 480 -> 360 -> 240 -> 144 優先順序挑選最佳支援畫質 (若無 480 則往下降為 360、240、144)"""
    PRIORITY = ['480', '360', '240', '144']
    for res in PRIORITY:
        if res in available_map:
            return res
    return None

def has_required_resolution_badges(page, html_content: str = "", current_url: str = "") -> bool:
    """判斷網頁是否出現 480、360、240 或 144 畫質黑框/標籤"""
    res_map = get_available_resolutions(page, html_content=html_content, current_url=current_url)
    return len(res_map) > 0

def is_video_deleted(title: str, page_text: str) -> bool:
    """判斷頁面內容是否表示影片已被刪除"""
    combined = (title + " " + page_text).lower()
    for kw in DELETED_KEYWORDS:
        if kw.lower() in combined:
            return True
    return False

def format_size(bytes_num: int) -> str:
    """格式化位元組大小"""
    if bytes_num < 1024:
        return f"{bytes_num} B"
    elif bytes_num < 1024 * 1024:
        return f"{bytes_num / 1024:.1f} KB"
    elif bytes_num < 1024 * 1024 * 1024:
        return f"{bytes_num / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_num / (1024 * 1024 * 1024):.2f} GB"

def format_speed(bytes_per_sec: float) -> str:
    """格式化下載速度"""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.0f} B/s"
    elif bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    else:
        return f"{bytes_per_sec / (1024 * 1024):.2f} MB/s"

def parse_m3u8_playlist(m3u8_url: str, m3u8_content: str) -> list[str]:
    """解析 M3U8 內容，若為 Master Playlist 依 480 -> 360 -> 240 -> 144 優先順序挑選適當畫質子清單，最終回傳分段清單"""
    lines = [l.strip() for l in m3u8_content.splitlines() if l.strip()]
    base_url = m3u8_url.rsplit('/', 1)[0] + '/'
    
    # 檢查是否為 Master Playlist (包含 #EXT-X-STREAM-INF)
    is_master = any(l.startswith('#EXT-X-STREAM-INF') for l in lines)
    if is_master:
        streams = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('#EXT-X-STREAM-INF'):
                bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                bw = int(bw_match.group(1)) if bw_match else 0
                res_match = re.search(r'RESOLUTION=\d+x(\d+)', line)
                height = int(res_match.group(1)) if res_match else 0
                if i + 1 < len(lines) and not lines[i+1].startswith('#'):
                    sub_uri = lines[i+1]
                    if not sub_uri.startswith('http'):
                        sub_uri = urllib.parse.urljoin(base_url, sub_uri)
                    streams.append({
                        'bandwidth': bw,
                        'height': height,
                        'url': sub_uri
                    })
                    i += 1
            i += 1
            
        if streams:
            # 優先挑選 <= 480 畫質，順序: 480 -> 360 -> 240 -> 144
            chosen_stream = None
            for target_h in [480, 360, 240, 144]:
                matching = [s for s in streams if s['height'] == target_h]
                if matching:
                    matching.sort(key=lambda s: s['bandwidth'], reverse=True)
                    chosen_stream = matching[0]
                    break
            
            # 若無精確符合 height 的標籤，過濾 height <= 480 者
            if not chosen_stream:
                under_480 = [s for s in streams if 0 < s['height'] <= 480]
                if under_480:
                    under_480.sort(key=lambda s: (s['height'], s['bandwidth']), reverse=True)
                    chosen_stream = under_480[0]
            
            # 若仍未找到 (例如全部未標示 RESOLUTION 或高度未知)，以 bandwidth 最大者作為保底
            if not chosen_stream:
                streams.sort(key=lambda s: s['bandwidth'], reverse=True)
                chosen_stream = streams[0]
                
            best_sub_url = chosen_stream['url']
            try:
                req = urllib.request.Request(best_sub_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    sub_content = resp.read().decode('utf-8', errors='ignore')
                return parse_m3u8_playlist(best_sub_url, sub_content)
            except Exception:
                pass
            
    # 解析分段
    segments = []
    for line in lines:
        if not line.startswith('#'):
            if line.startswith('http'):
                segments.append(line)
            else:
                segments.append(urllib.parse.urljoin(base_url, line))
    return segments

def get_next_hour_05_timestamp(dt: datetime.datetime | None = None) -> float:
    """計算下個小時 05 分的 timestamp (例如 8:50 失敗 -> 9:05 重新嘗試)"""
    if dt is None:
        dt = datetime.datetime.now()
    target = dt.replace(minute=5, second=0, microsecond=0)
    if target <= dt:
        target += datetime.timedelta(hours=1)
    return target.timestamp()

class DownloaderEngine:
    def __init__(
        self,
        txt_path: str = TXT_FILE_PATH,
        download_dir: str = DOWNLOAD_DIR,
        retry_delay_seconds: int = DEFAULT_RETRY_DELAY,
        max_workers: int = DEFAULT_MAX_WORKERS,
        log_callback=None,
        progress_callback=None,
        status_callback=None,
        task_callback=None,
        queue_callback=None,
        overall_progress_callback=None,
        retry_limit: int = 0  # 保留以向下相容
    ):
        self.txt_path = txt_path
        self.download_dir = download_dir
        self.retry_delay_seconds = retry_delay_seconds  # 預設失敗 1 小時後重試
        self.max_workers = max_workers
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.task_callback = task_callback
        self.queue_callback = queue_callback
        self.overall_progress_callback = overall_progress_callback
        
        self.failed_retry_times: dict[str, float] = {}  # 紀錄各網址下次重試的 timestamp
        self.max_check_workers = 10  # 網址並行檢查最大數量 (最多 10 個並行)
        self.stop_event = threading.Event()
        self.new_url_event = threading.Event()
        self.file_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.is_running = False
        os.makedirs(self.download_dir, exist_ok=True)

    def log(self, msg: str, level: str = "info"):
        if self.log_callback:
            self.log_callback(msg, level)
        else:
            print(msg)

    def update_status(self, text: str):
        if self.status_callback:
            self.status_callback(text)

    def update_task(self, title: str):
        if self.task_callback:
            self.task_callback(title)

    def update_progress(self, percent: float, detail: str = "", speed: str = ""):
        if self.progress_callback:
            self.progress_callback(percent, detail, speed)

    def update_overall(self, current: int, total: int):
        if self.overall_progress_callback:
            self.overall_progress_callback(current, total)

    def notify_queue_changed(self):
        if self.queue_callback:
            self.queue_callback()

    def stop(self):
        """觸發停止下載"""
        self.stop_event.set()

    def reset_retry_times(self, url: str | None = None):
        """重設重試等待時間，可指定單一網址或重設全部"""
        with self.state_lock:
            if url:
                self.failed_retry_times.pop(url, None)
            else:
                self.failed_retry_times.clear()
        self.notify_new_url()

    def remove_url_from_lines(self, lines: list, url_idx: int) -> list:
        to_remove = {url_idx}
        if url_idx > 0 and lines[url_idx - 1].strip().startswith(RETRY_PREFIX):
            to_remove.add(url_idx - 1)
        return [l for i, l in enumerate(lines) if i not in to_remove]

    def remove_url_and_retry(self, lines: list, url_idx: int) -> list:
        return self.remove_url_from_lines(lines, url_idx)

    def save_lines(self, lines: list):
        cleaned = []
        last_empty = False
        for l in lines:
            if not l.strip():
                if not last_empty:
                    cleaned.append("\n")
                    last_empty = True
            else:
                cleaned.append(l)
                last_empty = False
        while cleaned and not cleaned[0].strip():
            cleaned.pop(0)
        while cleaned and not cleaned[-1].strip():
            cleaned.pop()
        with open(self.txt_path, "w", encoding="utf-8-sig") as f:
            f.writelines(cleaned)
        self.notify_queue_changed()

    def remove_url_from_file(self, target_url: str):
        """從待下載.txt中執行緒安全地移除指定網址（包含前置重試註解）"""
        with self.file_lock:
            if not os.path.exists(self.txt_path):
                return
            try:
                with open(self.txt_path, "r", encoding="utf-8-sig") as f:
                    lines = f.readlines()

                new_lines = []
                for line in lines:
                    stripped = line.strip().lstrip('\ufeff')
                    if stripped == target_url:
                        if new_lines and new_lines[-1].strip().startswith(RETRY_PREFIX):
                            new_lines.pop()
                        continue
                    new_lines.append(line)

                self.save_lines(new_lines)
            except Exception as e:
                self.log(f"更新待下載.txt失敗 ({target_url}): {e}", "error")

    def replace_channel_in_file(self, channel_url: str, new_sub_urls: list[str]) -> list[str]:
        """將列表網址替換為解析出的子影片網址（執行緒安全）"""
        with self.file_lock:
            if not os.path.exists(self.txt_path):
                return []
            try:
                with open(self.txt_path, "r", encoding="utf-8-sig") as f:
                    lines = f.readlines()

                existing_urls = set()
                for l in lines:
                    cl = l.strip().lstrip('\ufeff')
                    if cl and "eyny.com" in cl:
                        existing_urls.add(re.sub(r'://已下載(\d*)\.eyny\.com', r'://www\1.eyny.com', cl, flags=re.IGNORECASE))

                to_insert = []
                for su in new_sub_urls:
                    su_norm = re.sub(r'://已下載(\d*)\.eyny\.com', r'://www\1.eyny.com', su, flags=re.IGNORECASE)
                    if su_norm not in existing_urls:
                        to_insert.append(su)
                        existing_urls.add(su_norm)

                new_lines = []
                for line in lines:
                    stripped = line.strip().lstrip('\ufeff')
                    if stripped == channel_url:
                        if new_lines and new_lines[-1].strip().startswith(RETRY_PREFIX):
                            new_lines.pop()
                        for su in to_insert:
                            new_lines.append(f"{su}\n")
                    else:
                        new_lines.append(line)

                self.save_lines(new_lines)
                return to_insert
            except Exception as e:
                self.log(f"替換列表網址失敗 ({channel_url}): {e}", "error")
                return []

    def resolve_video(self, watch_url: str, browser=None) -> tuple[str, str, bool]:
        """使用 Playwright 繞過 Eyny 防護並動態提前返回影片真實來源 (支援 480、360、240、144 畫質向下依序降級)
        
        回傳: (title, video_src, is_deleted)
        """
        self.log(f"正在解析影片網址: {watch_url}")
        self.update_status("正在解析影片網址...")
        start_time = time.time()
        
        # 判斷是否需要自己啟動 Playwright / Browser
        own_browser = False
        p_instance = None
        
        if browser is None:
            own_browser = True
            p_instance = sync_playwright().start()
            browser = p_instance.chromium.launch(headless=True)
            
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        context.add_init_script("delete navigator.__proto__.webdriver;")
        page = context.new_page()
        
        captured_urls = []
        page.on("request", lambda r: captured_urls.append(r.url)
                if (".mp4" in r.url or ".m3u8" in r.url)
                and not r.url.endswith((".js", ".css", ".png", ".jpg", ".gif", ".webp"))
                else None)
        
        response_status = 0
        try:
            # 使用 domcontentloaded 加快初始回應
            try:
                resp = page.goto(watch_url, timeout=35000, wait_until="domcontentloaded")
                if resp:
                    response_status = resp.status
            except Exception:
                pass
            
            clicked_player = False
            switched_resolution = False
            chosen_res = None
            video_src = None
            title = ""
            
            # P2 動態條件輪詢 (每 250ms 檢查一次，最長等候 15 秒，命中立即提早返回)
            max_wait_iterations = 60  # 60 * 0.25s = 15s
            for iteration in range(max_wait_iterations):
                if self.stop_event.is_set():
                    context.close()
                    if own_browser:
                        browser.close()
                        p_instance.stop()
                    return None, None, False
                
                # 取得標題與內文
                if not is_valid_title(title):
                    try:
                        t = page.title().strip()
                        if is_valid_title(t):
                            cleaned_t = clean_video_title(t)
                            if is_valid_title(cleaned_t):
                                title = cleaned_t
                    except Exception:
                        pass

                if not is_valid_title(title):
                    try:
                        dom_t = page.evaluate("""() => {
                            const og = document.querySelector('meta[property="og:title"]');
                            if (og && og.content) return og.content;
                            const h1 = document.querySelector('h1, .video-title, #video-title, .title');
                            if (h1 && h1.innerText) return h1.innerText;
                            const docTitle = document.title;
                            if (docTitle && !docTitle.toLowerCase().startsWith('loading')) return docTitle;
                            return '';
                        }""")
                        if dom_t and is_valid_title(dom_t):
                            cleaned_dom = clean_video_title(dom_t)
                            if is_valid_title(cleaned_dom):
                                title = cleaned_dom
                    except Exception:
                        pass
                
                # 取得頁面文字與 HTML 內容進行條件審查
                try:
                    page_text = page.inner_text("body")
                except Exception:
                    page_text = ""
                try:
                    html_content = page.content()
                except Exception:
                    html_content = ""
                    
                # 條件 1：偵測 403 Forbidden -> 立即刪除網址
                if check_is_403(response_status, title, page_text, html_content):
                    self.log(f"【偵測】網頁出現 403 Forbidden（標題: {title}），自動刪除此網址。", "warning")
                    context.close()
                    if own_browser:
                        browser.close()
                        p_instance.stop()
                    return title, None, True

                # 條件 2：偵測是否已被刪除
                if is_video_deleted(title, page_text):
                    self.log(f"【偵測】頁面顯示影片已刪除（標題: {title}），立即移除連結。", "warning")
                    context.close()
                    if own_browser:
                        browser.close()
                        p_instance.stop()
                    return title, None, True
                
                # 條件 3：頁面載入後，檢查 480、360、240、144 畫質支援與降級挑選
                page_loaded = False
                if is_valid_title(title):
                    page_loaded = True
                else:
                    try:
                        page_loaded = bool(page.query_selector("#mediaplayer, #video_container, .block"))
                    except Exception:
                        page_loaded = False

                if page_loaded:
                    try:
                        curr_url = page.url
                    except Exception:
                        curr_url = watch_url
                    res_map = get_available_resolutions(page, html_content=html_content, current_url=curr_url or watch_url)
                    if iteration >= 6 and not res_map:
                        self.log(f"【偵測】網頁未出現 480、360、240 或 144 畫質黑框（標題: {title}），自動刪除此網址。", "warning")
                        try:
                            context.close()
                        except Exception:
                            pass
                        if own_browser:
                            try:
                                browser.close()
                                p_instance.stop()
                            except Exception:
                                pass
                        return title, None, True

                    # 依優先順序 480 -> 360 -> 240 -> 144 挑選畫質
                    if not chosen_res and res_map:
                        chosen_res = select_best_resolution(res_map)
                        if chosen_res:
                            self.log(f"【畫質選擇】偵測到可用畫質 {list(res_map.keys())}，已依優先順序 (480>360>240>144) 選定 [{chosen_res}p] 畫質。")

                    # 若選定畫質尚未啟動且有連結可切換，嘗試切換
                    if chosen_res and not switched_resolution and iteration >= 2:
                        res_info = res_map.get(chosen_res, {})
                        if not res_info.get('isActive') and res_info.get('href'):
                            try:
                                selector = f'a[href*="size={chosen_res}"]'
                                link_el = page.query_selector(selector)
                                if link_el:
                                    try:
                                        link_el.click(timeout=3000, no_wait_after=True)
                                    except Exception:
                                        full_target = urllib.parse.urljoin(curr_url, res_info['href'])
                                        page.goto(full_target, wait_until='domcontentloaded', timeout=15000)
                                    switched_resolution = True
                                else:
                                    full_target = urllib.parse.urljoin(curr_url, res_info['href'])
                                    page.goto(full_target, wait_until='domcontentloaded', timeout=15000)
                                    switched_resolution = True
                            except Exception:
                                pass

                # 檢查是否已捕獲到網路請求
                if captured_urls:
                    video_src = captured_urls[0]
                    
                # 檢查 DOM 中的 video 標籤
                if not video_src:
                    try:
                        video_el = page.query_selector("video")
                        if video_el:
                            v_src = video_el.get_attribute("src")
                            if not v_src:
                                s_el = video_el.query_selector("source")
                                if s_el:
                                    v_src = s_el.get_attribute("src")
                            if v_src:
                                video_src = v_src
                    except Exception:
                        pass
                        
                # 若尚未捕獲，在第 1.5 秒後嘗試點擊播放器按鈕
                if not video_src and iteration >= 6 and not clicked_player:
                    try:
                        player = page.query_selector("#mediaplayer")
                        if player:
                            player.click(timeout=2000, no_wait_after=True)
                            clicked_player = True
                    except Exception:
                        pass
                        
                # 核心提早返回：抓到 video_src 且 title 有效時，再次驗證畫質黑框後返回
                if video_src and is_valid_title(title):
                    try:
                        curr_url = page.url
                    except Exception:
                        curr_url = watch_url
                    has_badge = has_required_resolution_badges(page, html_content=html_content, current_url=curr_url or watch_url)
                    if not has_badge:
                        self.log(f"【偵測】網頁未出現 480、360、240 或 144 畫質黑框（標題: {title}），自動刪除此網址。", "warning")
                        try:
                            context.close()
                        except Exception:
                            pass
                        if own_browser:
                            try:
                                browser.close()
                                p_instance.stop()
                            except Exception:
                                pass
                        return title, None, True

                    elapsed = time.time() - start_time
                    res_str = f" [{chosen_res}p]" if chosen_res else ""
                    self.log(f"【動態命中】於 {elapsed:.1f} 秒內成功捕獲影片來源{res_str}！(標題: {title})", "success")
                    try:
                        context.close()
                    except Exception:
                        pass
                    if own_browser:
                        try:
                            browser.close()
                            p_instance.stop()
                        except Exception:
                            pass
                    return title, video_src, False
                    
                page.wait_for_timeout(250)
            
            # 若輪詢結束仍未命中有效標題，做最後一次保底提取
            if not is_valid_title(title):
                try:
                    t = page.title().strip()
                    cleaned_t = clean_video_title(t)
                    if cleaned_t:
                        title = cleaned_t
                except Exception:
                    pass
            try:
                page_text = page.inner_text("body")
            except Exception:
                page_text = ""
            try:
                html_content = page.content()
            except Exception:
                html_content = ""

            if check_is_403(response_status, title, page_text, html_content):
                self.log(f"【偵測】網頁出現 403 Forbidden（標題: {title}），自動刪除此網址。", "warning")
                try:
                    context.close()
                except Exception:
                    pass
                if own_browser:
                    try:
                        browser.close()
                        p_instance.stop()
                    except Exception:
                        pass
                return title, None, True

            if is_video_deleted(title, page_text):
                self.log(f"【偵測】頁面顯示影片已刪除（標題: {title}），立即移除連結。", "warning")
                try:
                    context.close()
                except Exception:
                    pass
                if own_browser:
                    try:
                        browser.close()
                        p_instance.stop()
                    except Exception:
                        pass
                return title, None, True

            try:
                curr_url = page.url
            except Exception:
                curr_url = watch_url
            if is_valid_title(title) and not has_required_resolution_badges(page, html_content=html_content, current_url=curr_url or watch_url):
                self.log(f"【偵測】網頁未出現 480、360、240 或 144 畫質黑框（標題: {title}），自動刪除此網址。", "warning")
                try:
                    context.close()
                except Exception:
                    pass
                if own_browser:
                    try:
                        browser.close()
                        p_instance.stop()
                    except Exception:
                        pass
                return title, None, True

            if not video_src and captured_urls:
                video_src = captured_urls[0]
                
            context.close()
            if own_browser:
                browser.close()
                p_instance.stop()
            return title, video_src, False
            
        except Exception as e:
            self.log(f"解析網址出錯: {e}", "error")
            try:
                context.close()
                if own_browser:
                    browser.close()
                    p_instance.stop()
            except Exception:
                pass
            return None, None, False

    def resolve_channel_videos(self, channel_url: str, browser=None) -> tuple[list[str], bool]:
        """使用 Playwright 繞過 Eyny 防護並動態解析頻道、列表、播放清單或論壇文章中的所有子影片
        
        回傳: (watch_urls, is_deleted)
        """
        self.log(f"正在解析列表/頻道頁面: {channel_url}")
        self.update_status("正在自動解析列表影片...")
        start_time = time.time()
        
        own_browser = False
        p_instance = None
        if browser is None:
            own_browser = True
            p_instance = sync_playwright().start()
            browser = p_instance.chromium.launch(headless=True)
            
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        context.add_init_script("delete navigator.__proto__.webdriver;")
        page = context.new_page()
        
        response_status = 0
        try:
            try:
                resp = page.goto(channel_url, timeout=35000, wait_until="domcontentloaded")
                if resp:
                    response_status = resp.status
            except Exception:
                pass
                
            watch_urls = []
            parsed_channel = urllib.parse.urlparse(page.url if page.url else channel_url)
            base_netloc = parsed_channel.netloc if parsed_channel.netloc else "video.eyny.com"
            base_scheme = parsed_channel.scheme if parsed_channel.scheme else "https"
            
            # 動態輪詢並向下滾動加載更多影片卡片
            for iteration in range(35):  # 35 * 0.25s = ~8.7s
                if self.stop_event.is_set():
                    context.close()
                    if own_browser:
                        browser.close()
                        p_instance.stop()
                    return [], False
                
                # 檢查 403 Forbidden 或刪除
                try:
                    p_title = page.title()
                except Exception:
                    p_title = ""
                try:
                    p_text = page.inner_text("body")
                except Exception:
                    p_text = ""
                try:
                    p_html = page.content()
                except Exception:
                    p_html = ""
                    
                if check_is_403(response_status, p_title, p_text, p_html):
                    self.log(f"【偵測】列表頁面出現 403 Forbidden，自動刪除此網址: {channel_url}", "warning")
                    context.close()
                    if own_browser:
                        browser.close()
                        p_instance.stop()
                    return [], True

                if is_video_deleted(p_title, p_text):
                    self.log(f"【偵測】列表頁面已被刪除，自動刪除此網址: {channel_url}", "warning")
                    context.close()
                    if own_browser:
                        browser.close()
                        p_instance.stop()
                    return [], True

                # 在適當時機滾動觸發懶加載
                if iteration in (4, 10, 18):
                    try:
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    except Exception:
                        pass

                # 1. 從所有 a 標籤提取 href
                try:
                    links = page.query_selector_all("a[href]")
                    for link in links:
                        href = link.get_attribute("href")
                        if not href:
                            continue
                        if "watch?v=" in href or "action=view" in href:
                            if href.startswith("/"):
                                full_url = f"{base_scheme}://{base_netloc}{href}"
                            elif not href.startswith("http"):
                                full_url = f"{base_scheme}://{base_netloc}/{href}"
                            else:
                                full_url = href
                                
                            match = re.search(r"watch\?v=([^&#\s\"'>]+)", full_url)
                            if match:
                                vid = match.group(1)
                                clean_url = f"{base_scheme}://{base_netloc}/watch?v={vid}"
                                if clean_url not in watch_urls:
                                    watch_urls.append(clean_url)
                except Exception:
                    pass

                # 2. 從 iframe / embed 標籤提取嵌入影片
                try:
                    iframes = page.query_selector_all("iframe[src], embed[src]")
                    for ifr in iframes:
                        src = ifr.get_attribute("src")
                        if src and "watch?v=" in src:
                            match = re.search(r"watch\?v=([^&#\s\"'>]+)", src)
                            if match:
                                vid = match.group(1)
                                clean_url = f"{base_scheme}://{base_netloc}/watch?v={vid}"
                                if clean_url not in watch_urls:
                                    watch_urls.append(clean_url)
                except Exception:
                    pass

                # 3. 從 HTML 內容全文正則掃描 (包含論壇文章內文、自訂屬性等)
                try:
                    content = page.content()
                    html_matches = re.findall(r"(?:https?://[^/]+)?/watch\?v=([^&#\s\"'<>\\]+)", content)
                    for vid in html_matches:
                        clean_url = f"{base_scheme}://{base_netloc}/watch?v={vid}"
                        if clean_url not in watch_urls:
                            watch_urls.append(clean_url)
                except Exception:
                    pass

                # 只要有找到子影片且至少等候過載入 (>= 6 次迭代)
                if watch_urls and iteration >= 6:
                    elapsed = time.time() - start_time
                    self.log(f"【動態命中】於 {elapsed:.1f} 秒內成功取得列表中 {len(watch_urls)} 部子影片！", "success")
                    break
                    
                page.wait_for_timeout(250)
                
            context.close()
            if own_browser:
                browser.close()
                p_instance.stop()
            return watch_urls, False
        except Exception as e:
            self.log(f"解析列表頁面出錯: {e}", "error")
            try:
                context.close()
                if own_browser:
                    browser.close()
                    p_instance.stop()
            except Exception:
                pass
            return [], False

    def download_direct(self, url: str, dest_path: str) -> bool:
        """下載直接 MP4 連結 (含 .part 暫存檔、即時速度與進度計算)"""
        part_path = dest_path + ".part"
        try:
            self.log(f"開始直接下載影片 (MP4)...")
            self.update_status("正在下載 MP4 影片...")
            
            # 清理舊暫存檔
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except Exception:
                    pass

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get('content-length', 0))
                bytes_downloaded = 0
                block_size = 1024 * 128
                
                start_time = time.time()
                last_update_time = start_time
                bytes_since_last = 0
                
                with open(part_path, 'wb') as f:
                    while True:
                        if self.stop_event.is_set():
                            self.log("下載已被使用者手動取消", "warning")
                            f.close()
                            if os.path.exists(part_path):
                                try:
                                    os.remove(part_path)
                                except Exception:
                                    pass
                            return False
                            
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        f.write(buffer)
                        bytes_downloaded += len(buffer)
                        bytes_since_last += len(buffer)
                        
                        now = time.time()
                        if now - last_update_time >= 0.25:
                            speed = bytes_since_last / (now - last_update_time) if (now - last_update_time) > 0 else 0
                            speed_str = format_speed(speed)
                            last_update_time = now
                            bytes_since_last = 0
                            
                            if total_size > 0:
                                pct = (bytes_downloaded / total_size) * 100
                                detail = f"{format_size(bytes_downloaded)} / {format_size(total_size)} ({pct:.1f}%)"
                                self.update_progress(pct, detail, speed_str)
                            else:
                                detail = f"已下載: {format_size(bytes_downloaded)}"
                                self.update_progress(0, detail, speed_str)

            # 下載完成後原子重命名
            if os.path.exists(part_path):
                os.replace(part_path, dest_path)

            self.update_progress(100.0, "下載完成", "")
            self.log("直接下載完成！", "success")
            return True
        except Exception as e:
            self.log(f"直接下載失敗: {e}", "error")
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except Exception:
                    pass
            return False

    def download_m3u8(self, m3u8_url: str, dest_path: str) -> bool:
        """下載 M3U8 分段影片 (支援 Master Playlist 畫質自動挑選、分段斷點續傳與 .part 暫存)"""
        part_path = dest_path + ".part"
        seg_dir = dest_path + ".segments"
        
        try:
            self.log(f"偵測為 M3U8 串流，解析串流清單...")
            self.update_status("正在解析 M3U8 串流...")
            
            # 清理舊的殘留 .part 檔 (保留 seg_dir 供斷點續傳)
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except Exception:
                    pass

            req = urllib.request.Request(
                m3u8_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                m3u8_content = response.read().decode('utf-8', errors='ignore')
                
            segments = parse_m3u8_playlist(m3u8_url, m3u8_content)
                        
            if not segments:
                self.log("找不到任何 M3U8 分段網址。", "error")
                return False
                
            total_segments = len(segments)
            os.makedirs(seg_dir, exist_ok=True)
            
            # ── 斷點續傳檢查：掃描已下載的分段 ──
            existing_indices = set()
            total_downloaded_bytes = 0
            
            for fname in os.listdir(seg_dir):
                if fname.endswith(".ts"):
                    try:
                        f_idx = int(fname.split(".")[0])
                        if 0 <= f_idx < total_segments:
                            f_path = os.path.join(seg_dir, fname)
                            f_size = os.path.getsize(f_path)
                            if f_size > 0:
                                existing_indices.add(f_idx)
                                total_downloaded_bytes += f_size
                    except Exception:
                        pass
                        
            completed_segments = len(existing_indices)
            missing_segments = [item for item in enumerate(segments) if item[0] not in existing_indices]
            
            if completed_segments > 0:
                self.log(f"【斷點續傳】發現先前暫存: 已完成 {completed_segments}/{total_segments} 分段 ({format_size(total_downloaded_bytes)})，接續下載剩餘 {len(missing_segments)} 個分段！", "info")
            else:
                workers = min(self.max_workers, total_segments)
                self.log(f"共找到 {total_segments} 個分段，啟動 {workers} 條執行緒高速併發下載...", "info")
                
            workers = min(self.max_workers, max(len(missing_segments), 1))
            self.update_status(f"高速下載中 ({completed_segments}/{total_segments} 分段, {workers} 線程)...")
            
            start_time = time.time()
            last_speed_time = start_time
            bytes_since_speed = 0
            
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            def fetch_and_save_segment(item: tuple[int, str]) -> tuple[int, int, bool]:
                """下載單一分段並直接寫入磁碟暫存檔"""
                idx, seg_url = item
                seg_file = os.path.join(seg_dir, f"{idx:06d}.ts")
                seg_tmp = f"{seg_file}.tmp"
                
                if self.stop_event.is_set():
                    return idx, 0, False
                    
                for attempt in range(3):
                    if self.stop_event.is_set():
                        return idx, 0, False
                    try:
                        seg_req = urllib.request.Request(seg_url, headers=headers)
                        with urllib.request.urlopen(seg_req, timeout=15) as seg_resp:
                            data = seg_resp.read()
                            if data:
                                with open(seg_tmp, 'wb') as sf:
                                    sf.write(data)
                                os.replace(seg_tmp, seg_file)
                                return idx, len(data), True
                    except Exception:
                        if os.path.exists(seg_tmp):
                            try:
                                os.remove(seg_tmp)
                            except Exception:
                                pass
                        if attempt < 2:
                            time.sleep(0.5)
                return idx, 0, False

            download_failed = False
            
            if missing_segments:
                WINDOW_SIZE = workers * 4
                seg_iter = iter(missing_segments)
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                    future_to_idx = {}
                    
                    for item in itertools.islice(seg_iter, WINDOW_SIZE):
                        fut = executor.submit(fetch_and_save_segment, item)
                        future_to_idx[fut] = item[0]
                        
                    while future_to_idx:
                        if self.stop_event.is_set():
                            download_failed = True
                            break
                            
                        done, _ = concurrent.futures.wait(
                            future_to_idx.keys(),
                            return_when=concurrent.futures.FIRST_COMPLETED
                        )
                        
                        for fut in done:
                            idx = future_to_idx.pop(fut)
                            try:
                                seg_idx, seg_len, success = fut.result()
                            except Exception:
                                success = False
                                seg_len = 0
                                
                            if not success:
                                if not self.stop_event.is_set():
                                    self.log(f"分段 {idx+1}/{total_segments} 重試多次後仍下載失敗。", "error")
                                download_failed = True
                                break
                                
                            completed_segments += 1
                            total_downloaded_bytes += seg_len
                            bytes_since_speed += seg_len
                            
                            try:
                                next_item = next(seg_iter)
                                new_fut = executor.submit(fetch_and_save_segment, next_item)
                                future_to_idx[new_fut] = next_item[0]
                            except StopIteration:
                                pass
                                
                        if download_failed:
                            break
                            
                        now = time.time()
                        if now - last_speed_time >= 0.25 or completed_segments == total_segments:
                            elapsed = now - last_speed_time
                            speed = bytes_since_speed / elapsed if elapsed > 0 else 0
                            speed_str = format_speed(speed)
                            last_speed_time = now
                            bytes_since_speed = 0
                            
                            pct = (completed_segments / total_segments) * 100
                            detail = f"分段: {completed_segments}/{total_segments} ({pct:.1f}%) - {format_size(total_downloaded_bytes)}"
                            self.update_progress(pct, detail, speed_str)

            if download_failed or self.stop_event.is_set():
                if self.stop_event.is_set():
                    self.log("【暫停】下載已被使用者手動取消，已下載之分段已保留以供下次斷點續傳。", "warning")
                return False

            # ── 全部完成，按序合併為單一影片檔 ──
            self.update_status("分段下載完成，正在合併影片...")
            self.log(f"共 {total_segments} 個分段下載完成，開始快速合併為完整影片...", "info")
            self.update_progress(100.0, f"正在合併 {total_segments} 個分段...", "")
            
            with open(part_path, 'wb') as outfile:
                for idx in range(total_segments):
                    seg_file = os.path.join(seg_dir, f"{idx:06d}.ts")
                    if not os.path.exists(seg_file):
                        self.log(f"合併時找不到分段檔案: {seg_file}", "error")
                        return False
                    with open(seg_file, 'rb') as infile:
                        while True:
                            chunk = infile.read(1024 * 512)
                            if not chunk:
                                break
                            outfile.write(chunk)
                            
            # 合併成功後原子重命名為目標檔案
            if os.path.exists(part_path):
                os.replace(part_path, dest_path)
                
            # 清理暫存分段目錄
            try:
                for f in os.listdir(seg_dir):
                    os.remove(os.path.join(seg_dir, f))
                os.rmdir(seg_dir)
            except Exception:
                pass

            total_time = time.time() - start_time
            avg_speed = format_speed(total_downloaded_bytes / total_time if total_time > 0 else 0)
            self.update_progress(100.0, f"共 {total_segments} 個分段合併完成 ({format_size(total_downloaded_bytes)})", "")
            self.log(f"M3U8 斷點續傳合併下載完成！(耗時: {total_time:.1f} 秒, 平均速度: {avg_speed})", "success")
            return True
            
        except Exception as e:
            self.log(f"M3U8 下載失敗: {e}", "error")
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except Exception:
                    pass
            return False

    def download_file(self, url: str, dest_path: str) -> bool:
        """判斷下載連結為 M3U8 還是直鏈影片並下載"""
        parsed_url = urllib.parse.urlparse(url)
        is_m3u8 = parsed_url.path.endswith(".m3u8") or ".m3u8" in url
        if is_m3u8:
            return self.download_m3u8(url, dest_path)
        else:
            return self.download_direct(url, dest_path)

    def _has_pending_urls(self) -> bool:
        """快速檢查 txt 中是否有未下載的伊莉網址"""
        if not os.path.exists(self.txt_path):
            return False
        try:
            with open(self.txt_path, "r", encoding="utf-8-sig") as f:
                for line in f:
                    l = line.strip().lstrip('\ufeff')
                    if l and not l.startswith(RETRY_PREFIX) and "eyny.com" in l:
                        return True
        except Exception:
            pass
        return False

    def _read_pending_lines(self) -> list:
        """讀取並預處理 txt，過濾已下載與舊格式重試標記"""
        with self.file_lock:
            if not os.path.exists(self.txt_path):
                return []
            with open(self.txt_path, "r", encoding="utf-8-sig") as f:
                lines = f.readlines()
            before_count = len(lines)
            lines = [l for l in lines if "已下載" not in l and not l.strip().startswith(RETRY_PREFIX)]
            if before_count != len(lines):
                self.save_lines(lines)
                with open(self.txt_path, "r", encoding="utf-8-sig") as f:
                    lines = f.readlines()
            return lines

    def notify_new_url(self):
        """從外部呼叫：通知引擎有新網址加入，立即從待機狀態喚醒"""
        if hasattr(self, 'new_url_event'):
            self.new_url_event.set()

    def _check_single_url(
        self,
        url: str,
        browser,
        stats: dict,
        download_queue: queue.Queue,
        check_queue: queue.Queue
    ):
        """檢查單一網址可下載性並分流（可下載 / 不可下載 / 檢查失敗 / 列表展開）"""
        if self.stop_event.is_set():
            return

        self.log(f"【開始檢查】{url}")

        if "watch?v=" in url:
            title, video_src, is_deleted = self.resolve_video(url, browser=browser)
            if self.stop_event.is_set():
                return

            # 情況 1：不可下載（403 Forbidden / 影片已刪除 / 未包含 480, 360, 240, 144 畫質黑框）
            if is_deleted:
                self.log(f"【不可下載】網址符合刪除條件（403 Forbidden / 未包含 480、360、240 或 144 畫質黑框 / 影片已刪除），已自待下載清單移除: {url}", "warning")
                self.remove_url_from_file(url)
                with self.state_lock:
                    self.failed_retry_times.pop(url, None)
                    stats["not_downloadable"] += 1
                    stats["checked_count"] += 1
                    stats["completed_tasks"] += 1
                    completed = stats["completed_tasks"]
                    total = stats["total_targets"]
                self.update_overall(completed, total)
                return

            # 情況 2：檢查失敗/未知（暫時無法取得真實下載連結）
            if not video_src:
                next_retry = get_next_hour_05_timestamp()
                next_retry_str = datetime.datetime.fromtimestamp(next_retry).strftime('%H:%M:%S')
                self.log(f"【檢查失敗】暫時無法取得影片下載連結，保留連結至待下載清單，將於下個小時 05 分 ({next_retry_str}) 重新嘗試: {url}", "warning")
                with self.state_lock:
                    self.failed_retry_times[url] = next_retry
                    stats["failed_or_unknown"] += 1
                    stats["checked_count"] += 1
                    stats["completed_tasks"] += 1
                    completed = stats["completed_tasks"]
                    total = stats["total_targets"]
                self.update_overall(completed, total)
                return

            # 情況 3：成功解析出影片來源，檢查是否為已存在之重複檔案
            video_code = extract_video_code(title)
            code_info = f" (識別番號: {video_code})" if video_code else ""

            is_dup, dup_reason, matched_file = find_existing_duplicate_file(self.download_dir, title)
            if is_dup:
                self.log(f"【不可下載】偵測到已存在相同影片（{dup_reason}，現存檔案: {matched_file}），自動略過並移除連結: {url}", "warning")
                self.remove_url_from_file(url)
                with self.state_lock:
                    self.failed_retry_times.pop(url, None)
                    stats["not_downloadable"] += 1
                    stats["checked_count"] += 1
                    stats["completed_tasks"] += 1
                    completed = stats["completed_tasks"]
                    total = stats["total_targets"]
                self.update_overall(completed, total)
                return

            # 情況 4：確認可下載！立即加入下載佇列
            self.log(f"【可下載】解析出真實連結！影片標題: {title}{code_info}，已立即加入下載佇列！", "success")
            with self.state_lock:
                stats["downloadable"] += 1
                stats["checked_count"] += 1
            download_queue.put({
                "url": url,
                "title": title,
                "video_src": video_src
            })

        else:
            # 頻道 / 列表 / 論壇文章頁面
            sub_urls, is_channel_deleted = self.resolve_channel_videos(url, browser=browser)
            if self.stop_event.is_set():
                return

            if is_channel_deleted:
                self.log(f"【不可下載】列表頁面出現 403 Forbidden 或已被刪除，已自待下載清單移除: {url}", "warning")
                self.remove_url_from_file(url)
                with self.state_lock:
                    self.failed_retry_times.pop(url, None)
                    stats["not_downloadable"] += 1
                    stats["checked_count"] += 1
                    stats["completed_tasks"] += 1
                    completed = stats["completed_tasks"]
                    total = stats["total_targets"]
                self.update_overall(completed, total)
                return

            if not sub_urls:
                next_retry = get_next_hour_05_timestamp()
                next_retry_str = datetime.datetime.fromtimestamp(next_retry).strftime('%H:%M:%S')
                self.log(f"【檢查失敗】在此列表頁面未找到任何影片網址，保留連結，將於下個小時 05 分 ({next_retry_str}) 重新嘗試: {url}", "warning")
                with self.state_lock:
                    self.failed_retry_times[url] = next_retry
                    stats["failed_or_unknown"] += 1
                    stats["checked_count"] += 1
                    stats["completed_tasks"] += 1
                    completed = stats["completed_tasks"]
                    total = stats["total_targets"]
                self.update_overall(completed, total)
                return

            # 成功解析出子影片列表
            added_urls = self.replace_channel_in_file(url, sub_urls)
            with self.state_lock:
                self.failed_retry_times.pop(url, None)
                stats["checked_count"] += 1
                if added_urls:
                    # 總目標數修正：扣除頻道網址本身 (1)，加入新增的子影片數量
                    stats["total_targets"] += len(added_urls) - 1
                    for sub_u in added_urls:
                        check_queue.put(sub_u)
                else:
                    stats["completed_tasks"] += 1
                completed = stats["completed_tasks"]
                total = stats["total_targets"]

            self.log(f"【列表展開】列表頁面解析出 {len(sub_urls)} 部影片 (新增 {len(added_urls)} 部)，已加入並行檢查佇列！", "success")
            self.update_overall(completed, total)

    def _run_batch(self, ready_items: list[str]):
        """批次執行網址並行檢查 (最多 10 線程) 與即時下載流水線"""
        total_items = len(ready_items)
        num_check_workers = min(self.max_check_workers, total_items)
        if num_check_workers <= 0:
            num_check_workers = 1

        self.log(f"【開始批次處理】共有 {total_items} 個待處理網址，啟動最多 {num_check_workers} 個並行檢查任務...")
        self.update_overall(0, total_items)
        self.update_status(f"正在並行檢查網址 (最多 {num_check_workers} 線程)...")

        check_queue = queue.Queue()
        download_queue = queue.Queue()

        for u in ready_items:
            check_queue.put(u)

        stats = {
            "total_targets": total_items,
            "checked_count": 0,
            "downloadable": 0,
            "not_downloadable": 0,
            "failed_or_unknown": 0,
            "completed_tasks": 0,
        }

        active_checkers = 0
        active_lock = threading.Lock()
        checking_finished_event = threading.Event()

        # ── 1. 下載 Worker 執行緒 (優先處理最先確認可下載的網址，不等待全部檢查完成) ──
        def download_worker_loop():
            while not self.stop_event.is_set():
                try:
                    item = download_queue.get(timeout=0.5)
                except queue.Empty:
                    if checking_finished_event.is_set() and download_queue.empty():
                        break
                    continue

                if item is None:
                    download_queue.task_done()
                    break

                try:
                    if self.stop_event.is_set():
                        download_queue.task_done()
                        break

                    url = item["url"]
                    title = item["title"]
                    video_src = item["video_src"]

                    dest_path, filename = get_unique_dest_path(self.download_dir, title if title else "eyny_video")
                    self.update_task(title if title else url)
                    self.update_status("正在下載影片...")
                    self.log(f"\n{'='*45}\n【開始下載】{title if title else url}\n儲存檔名: {filename}")

                    success = self.download_file(video_src, dest_path)

                    if success:
                        self.remove_url_from_file(url)
                        with self.state_lock:
                            self.failed_retry_times.pop(url, None)
                            stats["completed_tasks"] += 1
                            completed = stats["completed_tasks"]
                            total = stats["total_targets"]
                        self.log(f"【完成】影片下載成功並已儲存至: {filename}", "success")
                        self.update_overall(completed, total)
                    else:
                        if not self.stop_event.is_set():
                            next_retry = get_next_hour_05_timestamp()
                            next_retry_str = datetime.datetime.fromtimestamp(next_retry).strftime('%H:%M:%S')
                            with self.state_lock:
                                self.failed_retry_times[url] = next_retry
                                stats["completed_tasks"] += 1
                                completed = stats["completed_tasks"]
                                total = stats["total_targets"]
                            self.log(f"【失敗】影片下載失敗，保留連結至待下載清單，將於下個小時 05 分 ({next_retry_str}) 重新嘗試下載: {url}", "warning")
                            self.update_overall(completed, total)

                except Exception as e:
                    self.log(f"下載任務異常: {e}", "error")
                finally:
                    download_queue.task_done()

        download_thread = threading.Thread(target=download_worker_loop, daemon=True)
        download_thread.start()

        # ── 2. 網址並行檢查 Worker 執行緒群 (最多 10 個，補位維持並行數) ──
        def check_worker_loop(worker_id: int):
            nonlocal active_checkers
            try:
                with sync_playwright() as playwright_instance:
                    browser = playwright_instance.chromium.launch(headless=True)
                    while not self.stop_event.is_set():
                        try:
                            url = check_queue.get(timeout=0.5)
                        except queue.Empty:
                            with active_lock:
                                if check_queue.empty() and active_checkers == 0:
                                    break
                            continue

                        with active_lock:
                            active_checkers += 1

                        try:
                            self._check_single_url(url, browser, stats, download_queue, check_queue)
                        except Exception as e:
                            self.log(f"檢查網址出錯 ({url}): {e}", "error")
                        finally:
                            with active_lock:
                                active_checkers -= 1
                            check_queue.task_done()

                    try:
                        browser.close()
                    except Exception:
                        pass
            except Exception as e:
                self.log(f"檢查線程 #{worker_id} 異常: {e}", "error")

        check_threads = []
        for wid in range(num_check_workers):
            t = threading.Thread(target=check_worker_loop, args=(wid,), daemon=True)
            t.start()
            check_threads.append(t)

        # 等候所有檢查執行緒完成
        for t in check_threads:
            t.join()

        checking_finished_event.set()

        # 檢查完成摘要紀錄
        with self.state_lock:
            c_total = stats["checked_count"]
            c_down = stats["downloadable"]
            c_not = stats["not_downloadable"]
            c_fail = stats["failed_or_unknown"]
        self.log(
            f"\n{'='*45}\n【網址檢查完成】共完成 {c_total} 個網址檢查：\n"
            f"  - 可下載: {c_down} 個\n"
            f"  - 不可下載: {c_not} 個\n"
            f"  - 檢查失敗/未知: {c_fail} 個\n"
            f"{'='*45}",
            "info"
        )

        # 等候下載執行緒處理完所有已加入佇列的下載任務
        download_thread.join()

    def process_queue(self) -> bool:
        """持續監控與排程下載模式：
        - 批次最多並行 10 個網址檢查
        - 發現可下載網址立即優先開始下載，且不阻塞其他網址並行檢查
        - 遇到失敗網址保留在待下載.txt，間隔 1 小時後重新嘗試下載
        - 影片下載成功才從待下載清單刪除
        - 找不到影片（已刪除/不存在/404/無對應畫質）自動刪除連結
        - 遇到列表型網址自動解析裡面所有影片並立即執行下載
        - 若有新網址加入立即喚醒下載
        - 手動停止才退出
        """
        self.stop_event.clear()
        self.new_url_event.clear()
        self.is_running = True
        
        # 啟動時清理未完成的暫存檔並宣告防休眠
        clean_part_files(self.download_dir)
        prevent_sleep()

        try:
            while not self.stop_event.is_set():
                lines = self._read_pending_lines()

                pending_items = [
                    l.strip().lstrip('\ufeff') for l in lines
                    if l.strip() and not l.strip().startswith(RETRY_PREFIX)
                    and "eyny.com" in l
                ]

                # 清理已不在 pending_items 中的 failed_retry_times 鍵
                active_url_set = set(pending_items)
                with self.state_lock:
                    for k in list(self.failed_retry_times.keys()):
                        if k not in active_url_set:
                            del self.failed_retry_times[k]

                if not pending_items:
                    # 佇列完全為空：恢復系統休眠行為並進入待機
                    with self.state_lock:
                        self.failed_retry_times.clear()
                    allow_sleep()
                    self.update_status("✅ 完成，等待新網址...")
                    self.update_task("待機中，可繼續新增網址")
                    self.update_overall(0, 0)
                    self.new_url_event.clear()
                    # 每 2 秒輪詢一次，或被 notify_new_url() 立即喚醒
                    while not self.stop_event.is_set():
                        self.new_url_event.wait(timeout=2.0)
                        self.new_url_event.clear()
                        if self._has_pending_urls():
                            self.log("【偵測】發現新網址，繼續下載！", "success")
                            prevent_sleep()
                            break
                    continue

                # 檢查是否有當前可執行的網址（新網址或重試時間已到的網址）
                now = time.time()
                with self.state_lock:
                    ready_items = [
                        u for u in pending_items
                        if u not in self.failed_retry_times or self.failed_retry_times[u] <= now
                    ]

                if not ready_items:
                    # 佇列中所有網址都在等待下一個小時重試
                    allow_sleep()
                    with self.state_lock:
                        earliest_retry = min(self.failed_retry_times[u] for u in pending_items if u in self.failed_retry_times)
                    wait_seconds = max(1.0, earliest_retry - now)
                    retry_dt = datetime.datetime.fromtimestamp(earliest_retry)
                    retry_str = retry_dt.strftime("%H:%M:%S")
                    mins_left = int(wait_seconds // 60)
                    secs_left = int(wait_seconds % 60)
                    time_desc = f"{mins_left} 分 {secs_left} 秒" if mins_left > 0 else f"{secs_left} 秒"

                    self.update_status(f"⏳ 等待下個小時 05 分重試 ({retry_str})")
                    self.update_task(f"{len(pending_items)} 個失敗任務將於 {retry_str} (剩餘 {time_desc}) 重新嘗試")
                    
                    # 等候：有新網址會立即喚醒，否則等時間到自動繼續
                    self.new_url_event.clear()
                    self.new_url_event.wait(timeout=min(wait_seconds, 2.0))
                    self.new_url_event.clear()
                    
                    if self._has_pending_urls():
                        prevent_sleep()
                    continue

                # 有可執行的項目，開始執行本輪並行批次
                prevent_sleep()
                self._run_batch(ready_items)

            self.update_status("已停止下載")
            self.update_task("無進行中任務")
            return True
        finally:
            allow_sleep()
            self.is_running = False

# 保留 CLI 相容性
def main():
    engine = DownloaderEngine()
    engine.process_queue()

def scheduler_loop():
    engine = DownloaderEngine()
    print("啟動下載器，持續監控與排程下載...")
    engine.process_queue()

if __name__ == "__main__":
    scheduler_loop()
