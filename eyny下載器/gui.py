import os
import re
import sys
import time
import datetime
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from downloader import (
    DownloaderEngine,
    TXT_FILE_PATH,
    DOWNLOAD_DIR,
    RETRY_PREFIX,
    DEFAULT_MAX_WORKERS,
    DEFAULT_RETRY_DELAY,
    format_size,
    format_speed,
    clean_part_files
)

# 設定外觀與預設主題
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class BatchAddDialog(ctk.CTkToplevel):
    """批次新增網址對話框"""
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.title("批次新增伊莉網址")
        self.geometry("520x420")
        self.minsize(450, 320)
        self.transient(parent)
        self.grab_set()
        
        # 標題
        self.label = ctk.CTkLabel(
            self,
            text="請在下方貼上一行一個伊莉影片或列表網址：",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.label.pack(padx=20, pady=(15, 5), anchor="w")
        
        # 文字輸入區
        self.textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(size=13))
        self.textbox.pack(padx=20, pady=10, fill="both", expand=True)
        
        # 按鈕列
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=20, pady=(0, 15), fill="x")
        
        self.btn_confirm = ctk.CTkButton(
            btn_frame,
            text="確認新增",
            command=self.on_confirm,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1f6aa5",
            hover_color="#144870"
        )
        self.btn_confirm.pack(side="right", padx=(10, 0))
        
        self.btn_cancel = ctk.CTkButton(
            btn_frame,
            text="取消",
            command=self.destroy,
            fg_color="#555555",
            hover_color="#333333"
        )
        self.btn_cancel.pack(side="right")
        
    def on_confirm(self):
        text = self.textbox.get("1.0", "end").strip()
        if text:
            urls = [line.strip() for line in text.splitlines() if line.strip()]
            self.callback(urls)
        self.destroy()

class EynyDownloaderGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # 視窗基本設定
        self.title("Eyny 影片下載器 (Eyny Video Downloader)")
        self.geometry("1000x720")
        self.minsize(920, 640)
        
        # 核心下載引擎與狀態
        self.download_dir_path = DOWNLOAD_DIR
        self.txt_file_path = TXT_FILE_PATH
        self.max_workers_val = DEFAULT_MAX_WORKERS
        self.is_downloading = False
        self.download_thread = None
        self.engine = None
        
        # 排程與剪貼簿監控狀態
        self.scheduler_active = False
        self.auto_clipboard_active = True
        self.last_clipboard_content = ""
        self.last_file_mtime = 0
        self.auto_scroll_log = True
        
        # 建構 UI
        self.setup_ui()
        
        # 載入現有佇列
        self.refresh_queue_from_file(show_log=False)
        
        # 啟動定時檢查（排程計時器、剪貼簿監控、檔案外部變更偵測）
        self.after(1000, self.timer_tick)
        
        # 啟動時自動開始持續監控下載
        self.after(500, self._auto_start_daemon)

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # ── 頂部導覽列 (Header) ──
        header_frame = ctk.CTkFrame(self, corner_radius=8, fg_color=("gray85", "#23272d"))
        header_frame.grid(row=0, column=0, columnspan=2, padx=15, pady=(12, 8), sticky="nsew")
        
        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", padx=15, pady=8)
        
        app_title = ctk.CTkLabel(
            title_box,
            text="🎬 Eyny 影片下載器",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        app_title.pack(anchor="w")
        
        app_sub = ctk.CTkLabel(
            title_box,
            text="支援單一影片、頻道列表解析、自動分段合併與定時排程",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70")
        )
        app_sub.pack(anchor="w")
        
        # 右側狀態徽章與外觀切換
        right_header = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_header.pack(side="right", padx=15, pady=8)
        
        self.status_badge = ctk.CTkLabel(
            right_header,
            text="🟢 閒置中",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("gray75", "#2f3640"),
            corner_radius=6,
            padx=12,
            pady=4
        )
        self.status_badge.pack(side="left", padx=(0, 15))
        
        self.theme_switch = ctk.CTkSegmentedButton(
            right_header,
            values=["深色", "淺色"],
            command=self.change_theme
        )
        self.theme_switch.set("深色")
        self.theme_switch.pack(side="left")

        # ── 主畫面左右分割 ──
        # 左側：佇列管理面板
        self.setup_left_panel()
        
        # 右側：控制面板、進度與日誌
        self.setup_right_panel()

    def setup_left_panel(self):
        left_frame = ctk.CTkFrame(self, corner_radius=8)
        left_frame.grid(row=1, column=0, padx=(15, 8), pady=(0, 12), sticky="nsew")
        left_frame.grid_rowconfigure(2, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        
        # 標題與計數
        header_box = ctk.CTkFrame(left_frame, fg_color="transparent")
        header_box.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        
        q_title = ctk.CTkLabel(
            header_box,
            text="📋 待下載清單",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        q_title.pack(side="left")
        
        self.queue_count_label = ctk.CTkLabel(
            header_box,
            text="(共 0 部)",
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray65")
        )
        self.queue_count_label.pack(side="left", padx=6)
        
        # 單一新增網址區
        input_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        input_frame.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)
        
        self.url_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="貼上伊莉影片或頻道網址...",
            font=ctk.CTkFont(size=13)
        )
        self.url_entry.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.url_entry.bind("<Return>", lambda e: self.add_single_url())
        
        btn_add = ctk.CTkButton(
            input_frame,
            text="＋ 新增",
            width=65,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.add_single_url
        )
        btn_add.grid(row=0, column=1, padx=(0, 4))
        
        btn_paste = ctk.CTkButton(
            input_frame,
            text="📋 貼上",
            width=65,
            fg_color=("gray70", "#3d424b"),
            hover_color=("gray60", "#4f5560"),
            command=self.paste_and_add
        )
        btn_paste.grid(row=0, column=2)
        
        # 佇列清單滾動區 (Scrollable Frame)
        self.queue_scroll = ctk.CTkScrollableFrame(
            left_frame,
            label_text="下載佇列項目",
            label_font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("gray95", "#1e2126")
        )
        self.queue_scroll.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="nsew")
        self.queue_scroll.grid_columnconfigure(0, weight=1)
        
        # 佇列底部操作列
        bottom_box = ctk.CTkFrame(left_frame, fg_color="transparent")
        bottom_box.grid(row=3, column=0, padx=12, pady=(0, 10), sticky="ew")
        
        btn_batch = ctk.CTkButton(
            bottom_box,
            text="📝 批次新增",
            width=90,
            command=self.open_batch_dialog
        )
        btn_batch.pack(side="left", padx=(0, 6))
        
        btn_clear = ctk.CTkButton(
            bottom_box,
            text="🗑️ 清空清單",
            width=85,
            fg_color="#8c2d2d",
            hover_color="#6d1f1f",
            command=self.clear_queue
        )
        btn_clear.pack(side="left", padx=(0, 6))
        
        btn_open_txt = ctk.CTkButton(
            bottom_box,
            text="📄 開啟TXT",
            width=80,
            fg_color=("gray70", "#3d424b"),
            hover_color=("gray60", "#4f5560"),
            command=self.open_txt_file
        )
        btn_open_txt.pack(side="left", padx=(0, 6))
        
        btn_refresh = ctk.CTkButton(
            bottom_box,
            text="🔄 重新整理",
            width=80,
            fg_color=("gray70", "#3d424b"),
            hover_color=("gray60", "#4f5560"),
            command=lambda: self.refresh_queue_from_file(show_log=True)
        )
        btn_refresh.pack(side="right")
        
        # 剪貼簿自動監聽開關
        self.cb_monitor_switch = ctk.CTkSwitch(
            left_frame,
            text="📋 自動監聽剪貼簿 (複製伊莉網址時自動加入佇列)",
            font=ctk.CTkFont(size=12),
            command=self.toggle_clipboard_monitor
        )
        self.cb_monitor_switch.select()
        self.cb_monitor_switch.grid(row=4, column=0, padx=14, pady=(0, 12), sticky="w")

    def setup_right_panel(self):
        right_frame = ctk.CTkFrame(self, fg_color="transparent")
        right_frame.grid(row=1, column=1, padx=(8, 15), pady=(0, 12), sticky="nsew")
        right_frame.grid_rowconfigure(3, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        
        # ── 1. 操作按鈕列 ──
        action_frame = ctk.CTkFrame(right_frame, corner_radius=8)
        action_frame.grid(row=0, column=0, pady=(0, 8), sticky="ew")
        
        btn_row = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_row.pack(padx=12, pady=10, fill="x")
        
        self.btn_start = ctk.CTkButton(
            btn_row,
            text="▶ 開始下載",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#27ae60",
            hover_color="#1e8449",
            height=40,
            command=self.start_download
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 8))
        
        self.btn_stop = ctk.CTkButton(
            btn_row,
            text="⏹ 停止下載",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#c0392b",
            hover_color="#962d22",
            height=40,
            state="disabled",
            command=self.stop_download
        )
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=(0, 8))
        
        self.btn_folder = ctk.CTkButton(
            btn_row,
            text="📂 下載資料夾",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("gray70", "#3d424b"),
            hover_color=("gray60", "#4f5560"),
            height=40,
            command=self.open_download_folder
        )
        self.btn_folder.pack(side="right", padx=(0, 0))

        # ── 2. 設定與排程 ──
        settings_frame = ctk.CTkFrame(right_frame, corner_radius=8)
        settings_frame.grid(row=1, column=0, pady=(0, 8), sticky="ew")
        
        # 下載路徑列
        path_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        path_row.pack(padx=12, pady=(10, 6), fill="x")
        
        lbl_path = ctk.CTkLabel(path_row, text="儲存資料夾:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_path.pack(side="left", padx=(0, 8))
        
        self.entry_dir = ctk.CTkEntry(path_row, font=ctk.CTkFont(size=12))
        self.entry_dir.insert(0, self.download_dir_path)
        self.entry_dir.configure(state="readonly")
        self.entry_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))
        
        btn_change_dir = ctk.CTkButton(
            path_row,
            text="變更路徑",
            width=75,
            command=self.select_download_dir
        )
        btn_change_dir.pack(side="right")
        
        # 排程與線程設定列
        sched_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        sched_row.pack(padx=12, pady=(0, 6), fill="x")
        
        self.sched_switch = ctk.CTkSwitch(
            sched_row,
            text="⏰ 定時排程 (每整點 05 分自動下載)",
            font=ctk.CTkFont(size=12),
            command=self.toggle_scheduler
        )
        self.sched_switch.pack(side="left")
        
        self.sched_countdown_label = ctk.CTkLabel(
            sched_row,
            text="排程未啟動",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray65")
        )
        self.sched_countdown_label.pack(side="right")
        
        # 併發線程設定列 (P1 優化控制)
        perf_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        perf_row.pack(padx=12, pady=(0, 10), fill="x")
        
        lbl_workers = ctk.CTkLabel(perf_row, text="⚡ 下載線程數 (併發):", font=ctk.CTkFont(size=12))
        lbl_workers.pack(side="left", padx=(0, 6))
        
        self.combo_workers = ctk.CTkOptionMenu(
            perf_row,
            values=["4 線程", "8 線程", "10 線程 (推薦)", "16 線程 (極速)", "20 線程"],
            width=130,
            command=self.on_worker_change
        )
        self.combo_workers.set("10 線程 (推薦)")
        self.combo_workers.pack(side="left", padx=(0, 15))
        
        lbl_retry_info = ctk.CTkLabel(
            perf_row,
            text="💡 失敗自動每隔 1 小時重試，直到下載完成",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70")
        )
        lbl_retry_info.pack(side="left", padx=(0, 6))

        # ── 3. 即時進度卡片 ──
        prog_frame = ctk.CTkFrame(right_frame, corner_radius=8)
        prog_frame.grid(row=2, column=0, pady=(0, 8), sticky="ew")
        
        p_box = ctk.CTkFrame(prog_frame, fg_color="transparent")
        p_box.pack(padx=12, pady=10, fill="x")
        
        # 當前任務名稱
        self.lbl_task = ctk.CTkLabel(
            p_box,
            text="當前任務: 尚未開始",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        self.lbl_task.pack(fill="x", pady=(0, 4))
        
        # 當前檔案進度條
        self.prog_current = ctk.CTkProgressBar(p_box, height=12)
        self.prog_current.set(0)
        self.prog_current.pack(fill="x", pady=(0, 4))
        
        # 進度詳情 (百分比、分段、速度)
        det_row = ctk.CTkFrame(p_box, fg_color="transparent")
        det_row.pack(fill="x", pady=(0, 6))
        
        self.lbl_prog_detail = ctk.CTkLabel(
            det_row,
            text="0% (0 / 0) - 0.0 MB/s",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70")
        )
        self.lbl_prog_detail.pack(side="left")
        
        self.lbl_overall = ctk.CTkLabel(
            det_row,
            text="總進度: 0 / 0",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70")
        )
        self.lbl_overall.pack(side="right")
        
        # 佇列總進度條
        self.prog_overall = ctk.CTkProgressBar(p_box, height=6, progress_color="#1f6aa5")
        self.prog_overall.set(0)
        self.prog_overall.pack(fill="x")

        # ── 4. 即時紀錄與日誌 ──
        log_frame = ctk.CTkFrame(right_frame, corner_radius=8)
        log_frame.grid(row=3, column=0, sticky="nsew")
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.grid(row=0, column=0, padx=12, pady=(8, 4), sticky="ew")
        
        lbl_log = ctk.CTkLabel(log_header, text="📜 即時執行紀錄", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_log.pack(side="left")
        
        btn_copy_log = ctk.CTkButton(
            log_header,
            text="複製日誌",
            width=65,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color=("gray70", "#3d424b"),
            hover_color=("gray60", "#4f5560"),
            command=self.copy_log
        )
        btn_copy_log.pack(side="right", padx=(6, 0))
        
        btn_clear_log = ctk.CTkButton(
            log_header,
            text="清空",
            width=50,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color=("gray70", "#3d424b"),
            hover_color=("gray60", "#4f5560"),
            command=self.clear_log
        )
        btn_clear_log.pack(side="right")
        
        # 日誌文字框
        self.log_box = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            state="disabled"
        )
        self.log_box.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="nsew")
        
        # 設定日誌顏色標籤 (Tkinter Text Tag)
        text_widget = self.log_box._textbox
        text_widget.tag_config("info", foreground="#CCCCCC")
        text_widget.tag_config("success", foreground="#2ecc71")
        text_widget.tag_config("warning", foreground="#f39c12")
        text_widget.tag_config("error", foreground="#e74c3c")
        text_widget.tag_config("time", foreground="#888888")

    # ── 佇列與檔案管理 ──
    def load_queue_items(self) -> list[dict]:
        """從待下載.txt讀取網址"""
        if not os.path.exists(self.txt_file_path):
            return []
        items = []
        try:
            with open(self.txt_file_path, "r", encoding="utf-8-sig") as f:
                lines = f.readlines()
            
            for line in lines:
                l = line.strip().lstrip('\ufeff')
                if not l or l.startswith(RETRY_PREFIX):
                    continue
                if "eyny.com" in l:
                    items.append({
                        "url": l
                    })
        except Exception as e:
            self.log(f"讀取待下載清單出錯: {e}", "error")
        return items

    def refresh_queue_from_file(self, show_log=False):
        """重新整理左側佇列清單"""
        items = self.load_queue_items()
        
        # 清空清單 UI
        for widget in self.queue_scroll.winfo_children():
            widget.destroy()
            
        self.queue_count_label.configure(text=f"(共 {len(items)} 部)")
        
        if not items:
            empty_lbl = ctk.CTkLabel(
                self.queue_scroll,
                text="目前沒有待下載的網址\n可手動新增或複製伊莉網址自動抓取",
                font=ctk.CTkFont(size=12),
                text_color=("gray50", "gray60")
            )
            empty_lbl.pack(pady=30)
        else:
            for idx, item in enumerate(items):
                self.create_queue_item_row(idx, item["url"])
                
        if show_log:
            self.log(f"佇列清單已重新整理，共 {len(items)} 個待處理項目。")

    def create_queue_item_row(self, index: int, url: str):
        """建立單一佇列卡片（已移除重試次數標籤）"""
        card = ctk.CTkFrame(self.queue_scroll, corner_radius=6, fg_color=("gray90", "#282c34"))
        card.pack(fill="x", pady=3, padx=2)
        
        # 編號
        idx_lbl = ctk.CTkLabel(
            card,
            text=f"{index + 1}.",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=26
        )
        idx_lbl.pack(side="left", padx=(6, 2), pady=6)
        
        # 類型圖標 (影片 / 列表)
        is_video = "watch?v=" in url
        type_badge = ctk.CTkLabel(
            card,
            text="🎬 影片" if is_video else "📑 列表",
            font=ctk.CTkFont(size=11),
            fg_color="#1f6aa5" if is_video else "#8e44ad",
            corner_radius=4,
            padx=6,
            pady=2
        )
        type_badge.pack(side="left", padx=(0, 6))
        
        # 網址文本 (自動省略)
        clean_display = url.replace("https://", "").replace("http://", "")
        if len(clean_display) > 34:
            clean_display = clean_display[:18] + "..." + clean_display[-12:]
            
        url_lbl = ctk.CTkLabel(
            card,
            text=clean_display,
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        url_lbl.pack(side="left", fill="x", expand=True, padx=(0, 6))
        
        # 刪除按鈕
        btn_del = ctk.CTkButton(
            card,
            text="✕",
            width=28,
            height=24,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="transparent",
            hover_color="#c0392b",
            text_color=("gray30", "gray75"),
            command=lambda: self.delete_queue_item(url)
        )
        btn_del.pack(side="right", padx=(0, 4))

    def add_single_url(self):
        url = self.url_entry.get().strip()
        if not url:
            return
        if self.append_url_to_file(url):
            self.url_entry.delete(0, "end")
            self.refresh_queue_from_file()
            self.log(f"已新增網址至佇列: {url}", "success")
        else:
            self.log(f"網址格式不符或已存在於佇列中: {url}", "warning")

    def paste_and_add(self):
        try:
            clip = self.clipboard_get().strip()
            if clip:
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, clip)
                self.add_single_url()
        except Exception as e:
            self.log(f"讀取剪貼簿失敗: {e}", "warning")

    def open_batch_dialog(self):
        BatchAddDialog(self, self.batch_add_urls)

    def batch_add_urls(self, urls: list[str]):
        added_count = 0
        for url in urls:
            if self.append_url_to_file(url):
                added_count += 1
        self.refresh_queue_from_file()
        self.log(f"批次新增完成，共成功加入 {added_count} 個伊莉網址！", "success")

    def append_url_to_file(self, url: str) -> bool:
        """驗證並將單一網址追加寫入待下載.txt"""
        if "eyny.com" not in url:
            return False
            
        match = re.search(r"https?://\S*eyny\.com\S*", url, re.IGNORECASE)
        if not match:
            return False
            
        clean_url = match.group(0).strip()
        
        # 檢查是否已存在
        items = self.load_queue_items()
        existing_urls = {item["url"] for item in items}
        if clean_url in existing_urls:
            return False
            
        try:
            prefix = ""
            if os.path.exists(self.txt_file_path) and os.path.getsize(self.txt_file_path) > 0:
                prefix = "\n"
            with open(self.txt_file_path, "a", encoding="utf-8-sig") as f:
                f.write(f"{prefix}{clean_url}\n")
            # 立即通知下載引擎有新網址，從待機狀態喚醒
            if self.engine and self.is_downloading:
                self.engine.notify_new_url()
            return True
        except Exception as e:
            self.log(f"寫入待下載.txt失敗: {e}", "error")
            return False

    def delete_queue_item(self, target_url: str):
        """從待下載.txt刪除指定網址"""
        if not os.path.exists(self.txt_file_path):
            return
        try:
            with open(self.txt_file_path, "r", encoding="utf-8-sig") as f:
                lines = f.readlines()
                
            new_lines = []
            skip_next = False
            for i, line in enumerate(lines):
                if skip_next:
                    skip_next = False
                    continue
                stripped = line.strip().lstrip('\ufeff')
                if stripped == target_url:
                    # 如果前一行是重試計數，也一併移除
                    if new_lines and new_lines[-1].strip().startswith(RETRY_PREFIX):
                        new_lines.pop()
                    continue
                new_lines.append(line)
                
            with open(self.txt_file_path, "w", encoding="utf-8-sig") as f:
                f.writelines(new_lines)
                
            self.refresh_queue_from_file()
            self.log(f"已從佇列刪除網址: {target_url}")
        except Exception as e:
            self.log(f"刪除網址失敗: {e}", "error")

    def clear_queue(self):
        """清空待下載清單"""
        if messagebox.askyesno("確認清空", "確定要清空待下載清單中的所有網址嗎？"):
            try:
                with open(self.txt_file_path, "w", encoding="utf-8-sig") as f:
                    f.write("")
                self.refresh_queue_from_file()
                self.log("已清空待下載清單。", "warning")
            except Exception as e:
                self.log(f"清空失敗: {e}", "error")

    def open_txt_file(self):
        """以系統預設程式開啟待下載.txt"""
        if not os.path.exists(self.txt_file_path):
            with open(self.txt_file_path, "w", encoding="utf-8-sig") as f:
                f.write("")
        try:
            os.startfile(self.txt_file_path)
        except Exception as e:
            self.log(f"開啟檔案失敗: {e}", "error")

    def open_download_folder(self):
        """開啟下載儲存資料夾"""
        os.makedirs(self.download_dir_path, exist_ok=True)
        try:
            os.startfile(self.download_dir_path)
        except Exception as e:
            self.log(f"開啟資料夾失敗: {e}", "error")

    def select_download_dir(self):
        """選擇新的下載儲存資料夾"""
        selected = filedialog.askdirectory(initialdir=self.download_dir_path)
        if selected:
            self.download_dir_path = selected
            self.entry_dir.configure(state="normal")
            self.entry_dir.delete(0, "end")
            self.entry_dir.insert(0, selected)
            self.entry_dir.configure(state="readonly")
            self.log(f"下載儲存路徑已變更為: {selected}", "info")

    # ── 下載控制 ──
    def _auto_start_daemon(self):
        """啟動時自動開始持續監控下載 Daemon"""
        self.log("🚀 下載器已啟動，持續監控佇列中...", "success")
        self._do_start_download()

    def start_download(self):
        """手動啟動下載（已在執行中時重設等待計時並立即重新嘗試）"""
        if self.is_downloading:
            if self.engine:
                self.engine.reset_retry_times()
                self.log("已重設重試等待時間，立即檢查並下載佇列任務！", "info")
            return
        self._do_start_download()

    def _do_start_download(self):
        """實際啟動下載 Daemon 執行緒"""
        if self.is_downloading:
            return

        self.is_downloading = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.status_badge.configure(text="🚀 監控中...", fg_color="#1f6aa5")

        self.engine = DownloaderEngine(
            txt_path=self.txt_file_path,
            download_dir=self.download_dir_path,
            retry_delay_seconds=DEFAULT_RETRY_DELAY,
            max_workers=self.max_workers_val,
            log_callback=self.thread_safe_log,
            progress_callback=self.thread_safe_progress,
            status_callback=self.thread_safe_status,
            task_callback=self.thread_safe_task,
            queue_callback=self.thread_safe_queue_refresh,
            overall_progress_callback=self.thread_safe_overall
        )

        self.download_thread = threading.Thread(target=self._run_download_thread, daemon=True)
        self.download_thread.start()

    def _run_download_thread(self):
        try:
            self.engine.process_queue()
        except Exception as e:
            self.thread_safe_log(f"下載過程發生未預期錯誤: {e}", "error")
        finally:
            self.after(0, self._on_download_finished)

    def _on_download_finished(self):
        self.is_downloading = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.status_badge.configure(text="⏹ 已停止", fg_color=("gray75", "#2f3640"))
        self.refresh_queue_from_file()
        self.lbl_task.configure(text="當前任務: 已停止")
        self.prog_current.set(0)
        self.lbl_prog_detail.configure(text="")

    def stop_download(self):
        """停止下載任務"""
        if not self.is_downloading or not self.engine:
            return
        self.log("正在停止下載作業，請稍候...", "warning")
        self.status_badge.configure(text="⏸ 正在停止...", fg_color="#d35400")
        self.engine.stop()

    # ── 執行緒安全 UI 回調 ──
    def thread_safe_log(self, msg: str, level: str = "info"):
        self.after(0, lambda: self.log(msg, level))

    def thread_safe_progress(self, percent: float, detail: str, speed: str):
        self.after(0, lambda: self._update_progress_ui(percent, detail, speed))

    def _update_progress_ui(self, percent: float, detail: str, speed: str):
        self.prog_current.set(percent / 100.0)
        spd = f" - {speed}" if speed else ""
        self.lbl_prog_detail.configure(text=f"{detail}{spd}")

    def thread_safe_status(self, status_text: str):
        self.after(0, lambda: self.status_badge.configure(text=f"🔵 {status_text}"))

    def thread_safe_task(self, title: str):
        self.after(0, lambda: self.lbl_task.configure(text=f"當前任務: {title}"))

    def thread_safe_queue_refresh(self):
        self.after(0, self.refresh_queue_from_file)

    def thread_safe_overall(self, current: int, total: int):
        self.after(0, lambda: self._update_overall_ui(current, total))

    def _update_overall_ui(self, current: int, total: int):
        if total > 0:
            pct = current / total
            self.prog_overall.set(pct)
            self.lbl_overall.configure(text=f"總進度: {current} / {total} 完成")
            if current == total:
                if sys.platform.startswith('win'):
                    try:
                        import winsound
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                    except Exception:
                        pass
        else:
            self.prog_overall.set(0)
            self.lbl_overall.configure(text="總進度: 0 / 0")

    # ── 日誌系統 ──
    def log(self, msg: str, level: str = "info"):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        
        # 寫入時間戳記
        self.log_box.insert("end", f"[{now_str}] ", "time")
        
        # 寫入訊息主體
        self.log_box.insert("end", f"{msg}\n", level)
        
        if self.auto_scroll_log:
            self.log_box.see("end")
            
        self.log_box.configure(state="disabled")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def copy_log(self):
        content = self.log_box.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("提示", "已將完整日誌內容複製到剪貼簿。")

    # ── 下載參數與排程 ──
    def on_worker_change(self, choice: str):
        match = re.search(r"\d+", choice)
        if match:
            self.max_workers_val = int(match.group(0))
            self.log(f"⚡ 已設定 M3U8 併發下載線程為: {self.max_workers_val} 線程", "info")

    def toggle_scheduler(self):
        self.scheduler_active = self.sched_switch.get() == 1
        if self.scheduler_active:
            self.log("⏰ 已啟用定時排程（每整點 05 分自動執行下載）。", "success")
        else:
            self.log("⏰ 已停用定時排程。", "warning")
            self.sched_countdown_label.configure(text="排程未啟動")

    def toggle_clipboard_monitor(self):
        self.auto_clipboard_active = self.cb_monitor_switch.get() == 1
        if self.auto_clipboard_active:
            self.log("📋 已啟用剪貼簿自動監聽。", "info")
        else:
            self.log("📋 已停用剪貼簿自動監聽。", "info")

    def timer_tick(self):
        """每秒觸發的計時循環：處理排程倒數、剪貼簿監控與外部檔案同步"""
        now = datetime.datetime.now()
        
        # 1. 排程倒數計算
        if self.scheduler_active:
            next_run = now.replace(minute=5, second=0, microsecond=0)
            if next_run <= now:
                next_run += datetime.timedelta(hours=1)
                
            wait_seconds = int((next_run - now).total_seconds())
            mins, secs = divmod(wait_seconds, 60)
            self.sched_countdown_label.configure(
                text=f"下次執行: {next_run.strftime('%H:%M:%S')} (剩餘 {mins}分{secs}秒)"
            )
            
            # 到達整點 05 分且目前未在下載中
            if wait_seconds == 0 and not self.is_downloading:
                self.log("⏰ 到達定時排程時間，開始自動執行佇列下載！", "success")
                self.start_download()

        # 2. 剪貼簿監聽 (支援多網址與文章中連結擷取)
        if self.auto_clipboard_active:
            try:
                clip = self.clipboard_get()
                if clip and clip != self.last_clipboard_content:
                    self.last_clipboard_content = clip
                    if "eyny.com" in clip:
                        matches = re.findall(r"https?://\S*eyny\.com\S*", clip, re.IGNORECASE)
                        added_count = 0
                        for found_url in matches:
                            clean_u = found_url.strip().rstrip("。，,;；'\"`()[]{}<>、")
                            if self.append_url_to_file(clean_u):
                                added_count += 1
                                self.log(f"【剪貼簿偵測】已自動存入待下載.txt: {clean_u}", "success")
                        if added_count > 0:
                            self.refresh_queue_from_file()
            except Exception:
                pass

        # 3. 外部檔案變更偵測 (例如由 AHK 或其他程式修改待下載.txt)
        if os.path.exists(self.txt_file_path):
            try:
                mtime = os.path.getmtime(self.txt_file_path)
                if self.last_file_mtime != 0 and mtime > self.last_file_mtime:
                    # 無論下載中或閒置，都更新佇列顯示
                    self.refresh_queue_from_file()
                    # 通知下載引擎有新網址（從待機狀態立即喚醒）
                    if self.engine and self.is_downloading:
                        self.engine.notify_new_url()
                self.last_file_mtime = mtime
            except Exception:
                pass

        # 下一秒再次執行
        self.after(1000, self.timer_tick)

    def change_theme(self, choice: str):
        if choice == "深色":
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")

def main():
    try:
        app = EynyDownloaderGUI()
        app.mainloop()
    except Exception:
        import traceback
        import tkinter.messagebox as mb
        mb.showerror("啟動失敗", f"下載器發生未預期的錯誤：\n\n{traceback.format_exc()}")

if __name__ == "__main__":
    main()

