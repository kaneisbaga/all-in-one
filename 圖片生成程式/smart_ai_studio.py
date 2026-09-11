import os
import sys
import time
import re
import json
import random
import shutil
import threading
import subprocess
import urllib.parse
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

# ─── 編碼修正 ───────────────────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

APP_VERSION = "5.0 Supreme"
# HISTORY_FILE disabled to prevent generating studio_history.json
SETTINGS_FILE = "studio_settings.json"
FAVORITES_FILE = "studio_favorites.json"

# ─── 中文詞典 ─────────────────────────────────────────────────────────────
SMART_DICT = {
    "貓":"cat, fluffy detailed fur", "狗":"dog, highly detailed fur",
    "女孩":"girl", "少女":"young anime girl, intricate details",
    "男孩":"young boy", "美少女":"beautiful anime girl, elegant, masterpiece",
    "帥哥":"handsome young man, charming", "機器人":"futuristic robot, octane render",
    "動漫":"anime style, key visual", "寫實":"photorealistic, 8k raw photo, DSLR",
    "二次元":"anime artwork, vibrant colors",
    "賽博朋克":"cyberpunk, glowing neon lights, rain reflections",
    "科幻":"sci-fi, futuristic, unreal engine 5",
    "星空":"starry night sky, cosmic nebula, milky way",
    "大海":"crystal clear blue ocean, waves", "海邊":"sunny tropical beach, palm trees",
    "雨":"rainy day, wet asphalt reflections",
    "森林":"mystical enchanted forest, god rays",
    "古堡":"ancient gothic castle, dramatic volumetric lighting",
    "健身":"fitness workout, muscular, athletic",
    "帥氣":"cool, stylish, confident", "可愛":"cute, adorable, kawaii",
    "清涼":"summer outfit, light breezy clothing",
    "放鬆":"relaxing, peaceful atmosphere",
    "城市":"modern city skyline, urban landscape",
    "山":"majestic mountain range, misty peaks",
    "花":"beautiful blooming flowers, botanical",
    "劍":"fantasy sword, gleaming blade",
    "龍":"majestic dragon, fantasy beast, epic scale",
    "夕陽":"golden sunset, warm light, silhouette",
    "雪":"snow covered landscape, winter atmosphere",
}

STYLE_PRESETS = {
    "🌟 極致寫實":   "photorealistic, 8k raw photo, DSLR, hyper realistic lighting, sharp focus",
    "🌸 日系動漫":   "anime style, key visual, Kyoto Animation, Makoto Shinkai, vibrant colors",
    "🌃 賽博朋克":   "cyberpunk style, neon lights, holo billboards, rain reflections, blade runner",
    "🎨 水彩油畫":   "impressionist oil painting, rich brush strokes, artistic masterpiece, canvas",
    "🎮 3D CG":      "3D render, unreal engine 5, octane render, volumetric lighting, PBR",
    "🌌 奇幻史詩":   "epic fantasy, magical atmosphere, ethereal lighting, concept art, illustrated",
    "📷 電影膠片":   "cinematic, 35mm film grain, anamorphic lens flare, golden hour, shallow DOF",
    "🖤 暗黑美學":   "dark fantasy, gothic aesthetic, dramatic shadows, moody atmosphere, deep colors",
}

NEG_QUICK_TAGS = [
    ("低畫質", "blurry, low quality, jpeg artifacts, pixelated"),
    ("多餘手指", "extra fingers, bad hands, deformed hands, mutated"),
    ("浮水印", "watermark, text, signature, logo, copyright"),
    ("雨傘", "umbrella"),
    ("背景雜亂", "cluttered background, messy scene"),
    ("多人", "multiple people, crowd, extra person"),
    ("扭曲臉", "ugly face, deformed face, disfigured"),
    ("低細節", "low detail, flat colors, simple"),
]

INSPIRATION_PROMPTS = [
    "浮空城夕陽下的魔法少女", "賽博朋克夜市裡的霓虹拉麵館",
    "深海中發光的巨大水母與探險家", "雨後陽光穿透森林的神聖鹿",
    "蒸氣朋克風格的火車終點站", "太空站窗外俯瞰璀璨的地球夜景",
    "古堡圖書館裡看書的純白少女", "月光下奔跑的銀色狼群",
    "被藤蔓纏繞的廢棄機甲巨人", "雪中靜靜燃燒的藍色篝火",
    "彩虹瀑布旁的精靈少女", "沙漠中的未來廢土騎士",
]

QUALITY_BOOST = (
    "masterpiece, best quality, ultra-detailed, 8k uhd, "
    "sharp focus, cinematic lighting, ray tracing, award-winning art"
)

CHAR_EQUIP_TIERS = {
    "⚙️ 廢柴": "torn beginner rags, crude wooden weapon, extremely worn-out poor equipment, dirty ragged",
    "🗡️ 入門": "basic leather armor, simple iron sword, starter equipment, plain appearance",
    "⚔️ 精良": "steel plate armor, enchanted blade, mid-tier equipment, glowing runes, refined",
    "💎 史詩": "epic ornate fantasy armor, powerful magical weapon, glowing enchantments, particle effects",
    "👑 傳說": "legendary divine armor, god-tier mythical weapon, cosmic energy, radiant wings of light, overwhelming divine presence",
}
CHAR_ACTIONS = {
    "站立待機": "standing idle pose, relaxed neutral stance, full body front view",
    "攻擊揮劍": "dynamic attacking slash pose, intense battle action, full body",
    "奔跑衝刺": "running sprint pose, fast dynamic motion, full body",
    "跳躍騰空": "jumping high mid-air, powerful leap, full body",
    "施法魔法": "casting powerful spell, glowing magical hands, magic circle, full body",
    "防穮格擋": "defensive guard blocking stance, shield raised, full body",
    "勝利姿勢": "victory triumphant pose, arms raised celebrating, full body",
    "倒地受傷": "fallen defeated on ground, wounded struggling, full body",
}
CHAR_EXPRESSIONS = {
    "平静冷靜": "calm cool neutral expression, stoic",
    "自信微笑": "confident charming smile, charismatic",
    "憤怒激怒": "fierce angry expression, intense rage",
    "悟傷哀愁": "sad sorrowful melancholic expression",
    "驚訝震驚": "surprised shocked wide eyes expression",
    "尅毅決心": "determined resolute strong-willed expression",
    "痛苦挣紮": "pained agonized suffering expression",
}
CHAR_AURAS = {
    "無光環": "",
    "🔥 火燈": "surrounded by dramatic fire aura, flame effects, burning ember particles",
    "❄️ 冰霜": "ice frost aura, crystalline ice shards floating, freezing cold effect",
    "⚡ 閃電": "crackling lightning aura, electric sparks, thunder energy",
    "✨ 神聖": "holy divine golden aura, sacred light beams, angelic radiance",
    "🌑 暗黑": "dark shadow aura, evil sinister energy, darkness tendrils",
    "☠️ 毒素": "poison toxic aura, sickly green mist, venom",
    "🌈 彩虹": "dazzling rainbow prismatic aura, colorful energy spectrum",
}
CHAR_BODY_TYPES = {
    "娇小": "petite small stature, short cute figure",
    "普通": "average normal height and build",
    "高桃": "tall slender elegant willowy figure",
    "壯碩": "muscular powerful buff imposing build",
}
CHAR_ART_STYLES = {
    "🌸 日系動漫": "anime JRPG character design style, vibrant detailed key visual illustration",
    "🎮 歐美卡通": "Western cartoon RPG game character design style",
    "🖼️ 奇幻寫實": "detailed fantasy realistic illustration, professional concept art",
    "👾 像素藝術": "retro pixel art game sprite style",
    "🌐 3D 渲染": "3D game character render, Unreal Engine 5, PBR materials, cinematic lighting",
}
CHAR_BACKGROUNDS = {
    "白底 (角色圖鑒)": "pure white background, clean character reference sheet",
    "史詩戰場": "epic fantasy battlefield, dramatic stormy sky, ruins",
    "廢土城市": "post-apocalyptic ruined city, dramatic lighting",
    "神秘地下城": "dark dungeon, stone walls, flickering torches",
    "魔法森林": "enchanted magical glowing forest, fireflies",
    "宇宙星空": "vast cosmic space, colorful nebula, stars",
}

THEME = {
    "bg_main":  "#0b0d14",
    "bg_card":  "#161926",
    "bg_input": "#0d0f1e",
    "accent":   "#ff2a6d",
    "cyan":     "#05d9e8",
    "green":    "#22d3a0",
    "gold":     "#f59e0b",
    "text":     "#e2e8f0",
    "muted":    "#64748b",
    "border":   "#1e2740",
}


# ══════════════════════════════════════════════════════════════════════════════
class SmartAIStudioApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"✨ Smart AI Studio {APP_VERSION}")
        self.root.geometry("1320x860")
        self.root.configure(bg=THEME["bg_main"])
        self.root.minsize(1000, 650)

        self.preview_img_obj   = None
        self.current_filepath  = None
        self.generating        = False
        self.session_count     = 0

        self.history   = []  # Initialize empty history without loading from file
        self.favorites = self._load_json(FAVORITES_FILE, [])
        self.settings  = self._load_json(SETTINGS_FILE,  {})

        self.batch_count    = tk.IntVar(value=1)
        self.seed_var       = tk.StringVar(value="")
        self.output_dir     = tk.StringVar(value=self.settings.get("output_dir", os.getcwd()))
        self.neg_active_tags = set()
        self.enhance_var = tk.BooleanVar(value=True)

        # 角色設計預設屬性
        self.char_equip_var  = tk.StringVar(value="⚔️ 精良")
        self.char_action_var = tk.StringVar(value="站立待機")
        self.char_expr_var   = tk.StringVar(value="自信微笑")
        self.char_aura_var   = tk.StringVar(value="無光環")
        self.char_body_var   = tk.StringVar(value="普通")
        self.char_style_var  = tk.StringVar(value="🌸 日系動漫")
        self.char_bg_var     = tk.StringVar(value="白底 (角色圖鑑)")

        self._build_styles()
        self._build_ui()
        self._refresh_gallery()
        self._refresh_prompt_combo()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ── Styles ────────────────────────────────────────────────────────────────
    def _build_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        bg, card = THEME["bg_main"], THEME["bg_card"]
        s.configure("TFrame",       background=bg)
        s.configure("Card.TFrame",  background=card)
        s.configure("TLabel",       background=card, foreground=THEME["text"],  font=("Segoe UI", 9))
        s.configure("TRadiobutton", background=card, foreground="#cbd5e1",      font=("Segoe UI", 9))
        s.configure("Prog.Horizontal.TProgressbar",
                    troughcolor=THEME["bg_input"], background=THEME["cyan"], thickness=7)
        s.configure("TNotebook",     background=bg, borderwidth=0)
        s.configure("TNotebook.Tab", background=card, foreground=THEME["muted"],
                    font=("Segoe UI", 9, "bold"), padding=[12, 5])
        s.map("TNotebook.Tab",
              background=[("selected", bg)], foreground=[("selected", THEME["cyan"])])
        s.configure("TCombobox", fieldbackground=THEME["bg_input"],
                    background=THEME["bg_card"], foreground="white")
        s.map("TCombobox",
              fieldbackground=[("readonly", THEME["bg_input"])],
              foreground=[("readonly", "white")])

    # ── Main UI ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Top bar
        top = tk.Frame(self.root, bg=THEME["bg_main"])
        top.pack(fill="x", padx=22, pady=10)
        tk.Label(top, text=f"🚀 Smart AI Studio {APP_VERSION}",
                 bg=THEME["bg_main"], fg="#fff",
                 font=("Segoe UI", 15, "bold")).pack(side="left")
        tk.Label(top, text="即時預覽 · 收藏系統 · 負面詞快選 · 完整提示詞預覽 · 自訂儲存路徑",
                 bg=THEME["bg_main"], fg=THEME["muted"],
                 font=("Segoe UI", 9)).pack(side="left", padx=12)

        self.session_lbl = tk.Label(top, text="本次生成：0 張",
                                    bg=THEME["bg_main"], fg=THEME["cyan"],
                                    font=("Segoe UI", 9, "bold"))
        self.session_lbl.pack(side="right")

        # Body
        body = tk.Frame(self.root, bg=THEME["bg_main"])
        body.pack(fill="both", expand=True, padx=22, pady=(0, 12))
        self._build_left(body)
        self._build_right(body)

    # ── Left Panel ────────────────────────────────────────────────────────────
    def _build_left(self, parent):
        panel = tk.Frame(parent, bg=THEME["bg_card"], width=460)
        panel.pack(side="left", fill="y")
        panel.pack_propagate(False)

        inner = tk.Frame(panel, bg=THEME["bg_card"])
        inner.pack(fill="both", expand=True, padx=15, pady=12)

        nb = ttk.Notebook(inner)
        nb.pack(fill="both", expand=True)

        gen_tab  = tk.Frame(nb, bg=THEME["bg_card"])
        char_tab = tk.Frame(nb, bg=THEME["bg_card"])
        fav_tab  = tk.Frame(nb, bg=THEME["bg_card"])
        hist_tab = tk.Frame(nb, bg=THEME["bg_card"])
        nb.add(gen_tab,  text=" 🎨 生成設定 ")
        nb.add(char_tab, text=" ⚔️ 角色設計 ")
        nb.add(fav_tab,  text=" ⭐ 我的收藏 ")
        nb.add(hist_tab, text=" 📜 使用記錄 ")

        self._build_gen_tab(gen_tab)
        self._build_char_tab(char_tab)
        self._build_fav_tab(fav_tab)
        self._build_hist_tab(hist_tab)

    def _build_gen_tab(self, parent):
        # ── 直接容器（無捲動條）──
        p = tk.Frame(parent, bg=THEME["bg_card"])
        p.pack(fill="both", expand=True, padx=4, pady=4)

        def sec(txt):
            tk.Label(p, text=txt, bg=THEME["bg_card"], fg=THEME["cyan"],
                     font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))

        # 1. Prompt
        ph = tk.Frame(p, bg=THEME["bg_card"])
        ph.pack(fill="x")
        tk.Label(ph, text="💬 提示詞 Prompt", bg=THEME["bg_card"], fg=THEME["cyan"],
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self._btn(ph, "🎲 靈感搖獎", "#2563eb", self._roll_inspiration).pack(side="right")

        self.prompt_text = tk.Text(p, height=3, bg=THEME["bg_input"], fg="#fff",
                                   insertbackground=THEME["cyan"], font=("Segoe UI", 10),
                                   relief="flat", bd=0, highlightthickness=1,
                                   highlightbackground=THEME["border"])
        self.prompt_text.pack(fill="x", pady=(3, 0))
        self.prompt_text.insert("1.0", "星空下的璀璨美少女")

        self.prompt_history_var = tk.StringVar(value="── 點此套用歷史提示詞 ──")
        self.ph_combo = ttk.Combobox(p, textvariable=self.prompt_history_var,
                                     state="readonly", font=("Segoe UI", 9))
        self.ph_combo.pack(fill="x", pady=(3, 0))
        self.ph_combo.bind("<<ComboboxSelected>>", self._apply_prompt_history)

        # 2. Negative Prompt + Quick Tags
        sec("🛡️ 負面詞過濾 Negative Prompt")
        self.neg_text = tk.Entry(p, bg=THEME["bg_input"], fg="#94a3b8",
                                 insertbackground=THEME["cyan"], font=("Segoe UI", 9),
                                 relief="flat", bd=0, highlightthickness=1,
                                 highlightbackground=THEME["border"])
        self.neg_text.pack(fill="x")
        self.neg_text.insert(0, "blurry, low quality, distorted, bad anatomy, watermark")

        tk.Label(p, text="⚡ 快速負面詞（點選新增）", bg=THEME["bg_card"],
                 fg=THEME["muted"], font=("Segoe UI", 8)).pack(anchor="w", pady=(5, 2))

        neg_chip_frame = tk.Frame(p, bg=THEME["bg_card"])
        neg_chip_frame.pack(fill="x", pady=(0, 4))
        self.neg_chip_btns = {}
        for label, val in NEG_QUICK_TAGS:
            btn = tk.Button(neg_chip_frame, text=label,
                            font=("Segoe UI", 8), bg="#1e293b", fg="#94a3b8",
                            activebackground=THEME["accent"], activeforeground="white",
                            relief="flat", bd=0, cursor="hand2", padx=6, pady=2,
                            command=lambda l=label, v=val: self._toggle_neg_tag(l, v))
            btn.pack(side="left", padx=2, pady=2)
            self.neg_chip_btns[label] = btn

        # 3. Style
        sec("🎨 藝術畫風 (8 種)")
        self.style_var = tk.StringVar(value=list(STYLE_PRESETS.keys())[0])
        cols = tk.Frame(p, bg=THEME["bg_card"])
        cols.pack(fill="x")
        for i, name in enumerate(STYLE_PRESETS.keys()):
            ttk.Radiobutton(cols, text=name, value=name,
                            variable=self.style_var).grid(
                row=i // 2, column=i % 2, sticky="w", padx=2, pady=1)

        # 4. Size / Model
        sec("⚙️ 畫布規格 & 模型引擎")
        row = tk.Frame(p, bg=THEME["bg_card"])
        row.pack(fill="x", pady=(2, 0))

        self.size_var = tk.StringVar()
        sc = ttk.Combobox(row, textvariable=self.size_var, state="readonly",
                          font=("Segoe UI", 9), width=20,
                          values=["1440x1440 (2K正方)", "1280x720 (16:9橫版)",
                                  "720x1280 (9:16直版)", "2048x2048 (4K旗艦)"])
        sc.pack(side="left")
        sc.current(0)

        self.model_var = tk.StringVar()
        mc = ttk.Combobox(row, textvariable=self.model_var, state="readonly",
                          font=("Segoe UI", 9), width=18,
                          values=["flux (旗艦精細)", "turbo (超速快攻)", "any-dark (暗黑奇幻)"])
        mc.pack(side="left", padx=(8, 0))
        mc.current(0)

        # 5. Batch & Seed
        sec("🔢 批次生圖 & 種子")
        br = tk.Frame(p, bg=THEME["bg_card"])
        br.pack(fill="x")
        tk.Label(br, text="張數 (1-100):", bg=THEME["bg_card"], fg=THEME["muted"],
                 font=("Segoe UI", 9)).pack(side="left")
        batch_spin = ttk.Spinbox(br, from_=1, to=100, width=8,
                                 textvariable=self.batch_count, font=("Segoe UI", 9))
        batch_spin.pack(side="left", padx=6)

        sr = tk.Frame(p, bg=THEME["bg_card"])
        sr.pack(fill="x", pady=(4, 0))
        tk.Label(sr, text="Seed (留空=隨機):", bg=THEME["bg_card"], fg=THEME["muted"],
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(sr, textvariable=self.seed_var, bg=THEME["bg_input"], fg="#fff",
                 font=("Segoe UI", 9), width=10, relief="flat",
                 highlightthickness=1,
                 highlightbackground=THEME["border"]).pack(side="left", padx=6)
        self._btn(sr, "🎲", "#374151",
                  lambda: self.seed_var.set(str(random.randint(1, 9999999)))).pack(side="left")

        # 6. Output Folder
        sec("📁 圖片儲存位置")
        orow = tk.Frame(p, bg=THEME["bg_card"])
        orow.pack(fill="x")
        tk.Entry(orow, textvariable=self.output_dir, bg=THEME["bg_input"],
                 fg=THEME["cyan"], font=("Segoe UI", 8), relief="flat",
                 highlightthickness=1,
                 highlightbackground=THEME["border"]).pack(side="left", fill="x", expand=True)
        self._btn(orow, "📂", "#374151", self._pick_output_dir).pack(side="left", padx=(4, 0))

        # 7. Enhanced Prompt Preview
        sec("🔎 增強後完整 Prompt 預覽（送出至 AI 的內容）")
        pv_frame = tk.Frame(p, bg=THEME["bg_input"], bd=0, highlightthickness=1,
                            highlightbackground=THEME["border"])
        pv_frame.pack(fill="x", pady=(2, 6))
        self.prompt_preview = tk.Text(pv_frame, height=4, bg=THEME["bg_input"],
                                      fg="#94a3b8", font=("Segoe UI", 8),
                                      relief="flat", bd=0, state="disabled",
                                      wrap="word")
        self.prompt_preview.pack(fill="x", padx=6, pady=4)
        pv_copy_row = tk.Frame(p, bg=THEME["bg_card"])
        pv_copy_row.pack(fill="x", pady=(0, 4))
        self._btn(pv_copy_row, "📋 複製完整 Prompt", "#1e3a5f",
                  self._copy_enhanced_prompt).pack(side="left")
        self._btn(pv_copy_row, "🔄 預覽更新", "#1e293b",
                  self._update_preview_prompt).pack(side="left", padx=6)
        self.enhance_chk = tk.Checkbutton(p, text="🔧 增強 Prompt", variable=self.enhance_var,
            onvalue=True, offvalue=False, bg=THEME["bg_card"], fg=THEME["muted"],
            selectcolor=THEME["bg_input"], font=("Segoe UI", 9))
        self.enhance_chk.pack(side="left", padx=6)

        # 8. Progress
        self.progressbar = ttk.Progressbar(p, style="Prog.Horizontal.TProgressbar",
                                           mode="indeterminate")
        self.progressbar.pack(fill="x", pady=(8, 4))

        # 9. Generate Button
        self.btn_generate = tk.Button(
            p, text="✨ 開始 AI 智慧生圖", font=("Segoe UI", 12, "bold"),
            bg=THEME["accent"], fg="white", activebackground="#d60050",
            relief="flat", bd=0, cursor="hand2",
            command=self._start_generation)
        self.btn_generate.pack(fill="x", pady=(2, 6), ipady=8)

        self.status_label = tk.Label(p, text="🟢 系統就緒，可開始繪圖。",
                                     bg=THEME["bg_card"], fg=THEME["muted"],
                                     font=("Segoe UI", 9))
        self.status_label.pack(anchor="w")

    def _build_fav_tab(self, parent):
        tk.Label(parent, text="⭐ 已收藏的作品：", bg=THEME["bg_card"],
                 fg=THEME["cyan"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 4))

        fr = tk.Frame(parent, bg=THEME["bg_card"])
        fr.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(fr)
        sb.pack(side="right", fill="y")
        self.fav_listbox = tk.Listbox(fr, bg=THEME["bg_input"], fg=THEME["text"],
                                      font=("Segoe UI", 9), relief="flat",
                                      selectbackground=THEME["gold"],
                                      yscrollcommand=sb.set,
                                      bd=0, highlightthickness=0)
        self.fav_listbox.pack(fill="both", expand=True)
        sb.config(command=self.fav_listbox.yview)
        self.fav_listbox.bind("<Double-Button-1>", self._open_fav_image)

        btns = tk.Frame(parent, bg=THEME["bg_card"])
        btns.pack(fill="x", pady=8)
        self._btn(btns, "🖼 開啟預覽", "#1e3a5f", self._open_fav_image).pack(side="left")
        self._btn(btns, "🗑 移除收藏", "#7f1d1d", self._remove_favorite).pack(side="left", padx=6)
        self._refresh_fav_listbox()

    def _build_hist_tab(self, parent):
        tk.Label(parent, text="📜 最近生成記錄：", bg=THEME["bg_card"],
                 fg=THEME["cyan"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 4))
        fr = tk.Frame(parent, bg=THEME["bg_card"])
        fr.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(fr)
        sb.pack(side="right", fill="y")
        self.hist_listbox = tk.Listbox(fr, bg=THEME["bg_input"], fg=THEME["text"],
                                       font=("Segoe UI", 9), relief="flat",
                                       selectbackground=THEME["accent"],
                                       yscrollcommand=sb.set,
                                       bd=0, highlightthickness=0)
        self.hist_listbox.pack(fill="both", expand=True)
        sb.config(command=self.hist_listbox.yview)
        self.hist_listbox.bind("<Double-Button-1>", self._load_from_hist_lb)

        btns = tk.Frame(parent, bg=THEME["bg_card"])
        btns.pack(fill="x", pady=8)
        self._btn(btns, "📋 套用提示詞", "#1e3a5f", self._load_from_hist_lb).pack(side="left")
        self._btn(btns, "🗑 清除記錄",   "#7f1d1d", self._clear_history).pack(side="left", padx=6)
        self._refresh_hist_listbox()

    # ── Character Design Tab ───────────────────────────────────────────────────
    def _build_char_tab(self, parent):
        canvas = tk.Canvas(parent, bg=THEME["bg_card"], highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        scroll_frame = tk.Frame(canvas, bg=THEME["bg_card"])
        win_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        def _resize(e):
            canvas.itemconfig(win_id, width=e.width)
        def _scrollregion(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.bind("<Configure>", _resize)
        scroll_frame.bind("<Configure>", _scrollregion)
        canvas.bind("<Enter>", lambda e: canvas.bind_all(
            "<MouseWheel>", lambda ev: canvas.yview_scroll(-1*(ev.delta//120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        p = scroll_frame

        def sec(txt):
            tk.Label(p, text=txt, bg=THEME["bg_card"], fg=THEME["cyan"],
                     font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))

        tk.Label(p, text="⚔️ 遊戲角色設計工作室",
                 bg=THEME["bg_card"], fg=THEME["gold"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(8, 0))
        tk.Label(p, text="描述角色外貌 → 選擇屬性 → 生成各種一致角色變體",
                 bg=THEME["bg_card"], fg=THEME["muted"],
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 4))

        sec("🧬 角色核心外貌")
        tk.Label(p, text="描述頭髮、眼睛、種族、服裝基底（中英文皆可）",
                 bg=THEME["bg_card"], fg=THEME["muted"],
                 font=("Segoe UI", 8)).pack(anchor="w")
        self.char_desc_text = tk.Text(
            p, height=3, bg=THEME["bg_input"], fg="#fff",
            insertbackground=THEME["cyan"], font=("Segoe UI", 10),
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=THEME["border"])
        self.char_desc_text.pack(fill="x", pady=(3, 0))
        self.char_desc_text.insert("1.0", "銀髮藍眼精靈少女，尖耳，白色皮膚，細腰")

        sec("⚙️ 裝備等級")
        tier_frame = tk.Frame(p, bg=THEME["bg_card"])
        tier_frame.pack(fill="x")
        _tier_colors = {
            "⚙️ 廢柴": ("#374151", "#6b7280"),
            "🗡️ 入門": ("#78350f", "#b45309"),
            "⚔️ 精良": ("#1e3a8a", "#3b82f6"),
            "💎 史詩": ("#5b21b6", "#8b5cf6"),
            "👑 傳說": ("#92400e", "#f59e0b"),
        }
        self.char_tier_btns = {}

        def _select_tier(key):
            for k, btn in self.char_tier_btns.items():
                off, on = _tier_colors[k]
                btn.config(bg=on if k == key else off)
            self.char_equip_var.set(key)
            if hasattr(self, "char_prompt_preview"):
                self._update_char_preview()

        for key in CHAR_EQUIP_TIERS:
            off, on = _tier_colors[key]
            b = tk.Button(tier_frame, text=key,
                          font=("Segoe UI", 8, "bold"),
                          bg=off, fg="white", relief="flat", bd=0,
                          cursor="hand2", padx=4, pady=5,
                          command=lambda k=key: _select_tier(k))
            b.pack(side="left", padx=2, pady=2, expand=True, fill="x")
            self.char_tier_btns[key] = b
        _select_tier("⚔️ 精良")

        sec("🎭 動作姿態")
        action_cb = ttk.Combobox(p, textvariable=self.char_action_var,
                                  state="readonly", font=("Segoe UI", 9),
                                  values=list(CHAR_ACTIONS.keys()))
        action_cb.pack(fill="x")
        action_cb.current(0)
        action_cb.bind("<<ComboboxSelected>>", self._update_char_preview)

        sec("😊 表情")
        expr_cb = ttk.Combobox(p, textvariable=self.char_expr_var,
                               state="readonly", font=("Segoe UI", 9),
                               values=list(CHAR_EXPRESSIONS.keys()))
        expr_cb.pack(fill="x")
        expr_cb.current(1)
        expr_cb.bind("<<ComboboxSelected>>", self._update_char_preview)

        sec("✨ 光環效果")
        aura_cb = ttk.Combobox(p, textvariable=self.char_aura_var,
                               state="readonly", font=("Segoe UI", 9),
                               values=list(CHAR_AURAS.keys()))
        aura_cb.pack(fill="x")
        aura_cb.current(0)
        aura_cb.bind("<<ComboboxSelected>>", self._update_char_preview)

        sec("💪 體型")
        body_row = tk.Frame(p, bg=THEME["bg_card"])
        body_row.pack(fill="x")
        for key in CHAR_BODY_TYPES:
            tk.Radiobutton(body_row, text=key,
                           variable=self.char_body_var, value=key,
                           bg=THEME["bg_card"], fg="#cbd5e1",
                           activebackground=THEME["bg_card"],
                           selectcolor=THEME["bg_card"],
                           font=("Segoe UI", 9),
                           command=self._update_char_preview).pack(side="left", padx=6)

        sec("🎨 藝術風格")
        style_cb = ttk.Combobox(p, textvariable=self.char_style_var,
                                state="readonly", font=("Segoe UI", 9),
                                values=list(CHAR_ART_STYLES.keys()))
        style_cb.pack(fill="x")
        style_cb.current(0)
        style_cb.bind("<<ComboboxSelected>>", self._update_char_preview)

        sec("🖼️ 場景背景")
        bg_cb = ttk.Combobox(p, textvariable=self.char_bg_var,
                             state="readonly", font=("Segoe UI", 9),
                             values=list(CHAR_BACKGROUNDS.keys()))
        bg_cb.pack(fill="x")
        bg_cb.current(0)
        bg_cb.bind("<<ComboboxSelected>>", self._update_char_preview)

        sec("🔎 角色 Prompt 預覽")
        pv_frame = tk.Frame(p, bg=THEME["bg_input"], bd=0,
                            highlightthickness=1,
                            highlightbackground=THEME["border"])
        pv_frame.pack(fill="x", pady=(2, 4))
        self.char_prompt_preview = tk.Text(
            pv_frame, height=3, bg=THEME["bg_input"],
            fg="#94a3b8", font=("Segoe UI", 8),
            relief="flat", bd=0, state="disabled", wrap="word")
        self.char_prompt_preview.pack(fill="x", padx=6, pady=4)
        self._btn(p, "🔄 更新角色 Prompt 預覽", "#1e293b",
                  self._update_char_preview).pack(fill="x", pady=(0, 6))

        self.char_btn = tk.Button(
            p, text="⚔️ 生成遊戲角色",
            font=("Segoe UI", 12, "bold"),
            bg=THEME["gold"], fg="#0f172a",
            activebackground="#d97706",
            relief="flat", bd=0, cursor="hand2",
            command=self._start_char_generation)
        self.char_btn.pack(fill="x", pady=(4, 4), ipady=8)

        self.char_status_label = tk.Label(
            p, text="🟢 設定好屬性後，點擊生成角色",
            bg=THEME["bg_card"], fg=THEME["muted"],
            font=("Segoe UI", 9))
        self.char_status_label.pack(anchor="w", pady=(0, 12))
        
        self._update_char_preview()

    def _build_char_prompt(self) -> str:
        base   = self.char_desc_text.get("1.0", "end").strip()
        tier   = CHAR_EQUIP_TIERS.get(self.char_equip_var.get(), "")
        action = CHAR_ACTIONS.get(self.char_action_var.get(), "")
        expr   = CHAR_EXPRESSIONS.get(self.char_expr_var.get(), "")
        aura   = CHAR_AURAS.get(self.char_aura_var.get(), "")
        body   = CHAR_BODY_TYPES.get(self.char_body_var.get(), "")
        style  = CHAR_ART_STYLES.get(self.char_style_var.get(), "")
        bg     = CHAR_BACKGROUNDS.get(self.char_bg_var.get(), "")
        if re.search(r"[\u4e00-\u9fa5]", base):
            try:
                url = (f"https://api.mymemory.translated.net/get"
                       f"?q={urllib.parse.quote(base)}&langpair=zh-TW|en")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    t = json.loads(resp.read().decode()).get("responseData", {}).get("translatedText", "")
                    if t:
                        base = t
            except Exception:
                pass
        parts = [base, tier, action, expr, aura, body, style, bg,
                 "single game character, full body, character design sheet",
                 QUALITY_BOOST]
        return ", ".join(pt for pt in parts if pt)

    def _update_char_preview(self, *_):
        preview = self._build_char_prompt()
        self.char_prompt_preview.config(state="normal")
        self.char_prompt_preview.delete("1.0", "end")
        self.char_prompt_preview.insert("1.0", preview)
        self.char_prompt_preview.config(state="disabled")

    def _start_char_generation(self):
        if self.generating:
            return
        self._update_char_preview()
        prompt_full = self._build_char_prompt()
        self.generating = True
        self.char_btn.config(state="disabled", bg="#475569", text="⏳ 角色生成中...")
        self.progressbar.start(10)
        self.char_status_label.config(text="🔄 AI 正在繪製角色...", fg=THEME["cyan"])
        self._set_status("🔄 角色生成中...", THEME["cyan"])
        threading.Thread(target=self._char_worker, args=(prompt_full,), daemon=True).start()

    def _char_worker(self, prompt):
        try:
            seed    = self.seed_var.get().strip() or str(random.randint(1, 9999999))
            w, h    = 768, 1344
            model   = self.model_var.get().split()[0]
            out_dir = self.output_dir.get()
            os.makedirs(out_dir, exist_ok=True)

            enc = urllib.parse.quote(prompt)
            url = (f"https://image.pollinations.ai/prompt/{enc}"
                   f"?width={w}&height={h}&model={model}"
                   f"&seed={seed}&nologo=true")

            safe_char_prompt = re.sub(r'[\/\\\:\*\?\"\<\>\|\n\r\t]', '', self.char_desc_text.get("1.0", "end").strip()).strip()[:50]
            filepath = os.path.join(out_dir, f"{seed}_{safe_char_prompt}_{int(time.time())}.jpg")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as resp, \
                    open(filepath, "wb") as f:
                f.write(resp.read())

            self.history.insert(0, {
                "prompt": self.char_desc_text.get("1.0", "end").strip(),
                "enhanced": prompt, "path": filepath,
                "time": time.strftime("%Y-%m-%d %H:%M"), "seed": seed,
            })
            self.history = self.history[:80]
            self.root.after(0, self._show_preview, filepath)
            self.root.after(0, self._char_done, True)
        except Exception as e:
            self.root.after(0, self._set_status, f"❌ 錯誤: {e}", "#f87171")
            self.root.after(0, self._char_done, False)

    def _char_done(self, ok):
        self.generating = False
        self.progressbar.stop()
        self.char_btn.config(state="normal", bg=THEME["gold"], text="⚔️ 生成遊戲角色")
        if ok:
            self.session_count += 1
            self.session_lbl.config(text=f"本次生成：{self.session_count} 張")
            self.char_status_label.config(text="✅ 角色生成完成！點縮圖查看", fg=THEME["green"])
            self._set_status("✅ 角色生成完成！", THEME["green"])
            self._refresh_gallery()
            self._refresh_hist_listbox()
        else:
            self.char_status_label.config(text="❌ 生成失敗，請重試", fg="#f87171")

    # ── Right Panel ───────────────────────────────────────────────────────────

    def _build_right(self, parent):
        panel = tk.Frame(parent, bg=THEME["bg_card"])
        panel.pack(side="right", fill="both", expand=True, padx=(14, 0))

        tk.Label(panel, text="🖼️ 即時預覽 (點擊全螢幕 · 右鍵選單)",
                 bg=THEME["bg_card"], fg=THEME["cyan"],
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=(12, 4))

        self.canvas_frame = tk.Frame(panel, bg=THEME["bg_input"],
                                     highlightthickness=1,
                                     highlightbackground=THEME["border"])
        self.canvas_frame.pack(fill="both", expand=True, padx=14)

        self.image_label = tk.Label(self.canvas_frame,
                                    text="繪圖完成後影像將在此即時呈現",
                                    bg=THEME["bg_input"], fg=THEME["muted"],
                                    font=("Segoe UI", 11), cursor="hand2")
        self.image_label.pack(fill="both", expand=True)
        self.image_label.bind("<Button-1>",   self._open_fullscreen)
        self.image_label.bind("<Button-3>",   self._image_context_menu)

        # Action bar
        act = tk.Frame(panel, bg=THEME["bg_card"])
        act.pack(fill="x", padx=14, pady=8)
        self._btn(act, "🔍 全螢幕",      "#1e3a5f", self._open_fullscreen).pack(side="left")
        self._btn(act, "⭐ 加入收藏",    "#7c3a00", self._add_to_favorites).pack(side="left", padx=4)
        self._btn(act, "📋 另存新檔",    "#1e3a5f", self._save_as).pack(side="left", padx=4)
        self._btn(act, "🖥 設為桌布",   "#1e3a5f", self._set_as_wallpaper).pack(side="left", padx=4)
        self._btn(act, "📁 開啟資料夾", "#1e293b", self.open_folder).pack(side="left", padx=4)

        # Thumbnail gallery
        tk.Label(panel, text="📸 縮圖畫廊 (左鍵預覽 · 右鍵選單)",
                 bg=THEME["bg_card"], fg=THEME["muted"],
                 font=("Segoe UI", 9)).pack(anchor="w", padx=14)

        self.thumb_frame = tk.Frame(panel, bg=THEME["bg_card"])
        self.thumb_frame.pack(fill="x", padx=14, pady=(4, 10))

    # ── Generation ────────────────────────────────────────────────────────────
    def _start_generation(self):
        try:
            count = self.batch_count.get()
            if count < 1 or count > 100:
                messagebox.showwarning("提示", "批次張數請輸入 1 至 100 之間的整數！")
                return
        except Exception:
            messagebox.showwarning("提示", "請輸入有效的批次張數 (1-100)！")
            return

        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("提示", "請輸入提示詞！")
            return
        if self.generating:
            return
        self._update_preview_prompt()
        self.generating = True
        self.btn_generate.config(state="disabled", bg="#475569", text="⏳ 繪圖生成中...")
        self.progressbar.start(10)
        self._set_status("🔄 AI 正在渲染光影中...", THEME["cyan"])
        threading.Thread(target=self._worker, args=(prompt,), daemon=True).start()

    def _worker(self, prompt):
        count = self.batch_count.get()
        ok = 0
        for i in range(count):
            try:
                seed = self.seed_var.get().strip() or str(random.randint(1, 9999999))
                enhanced = self._enhance(prompt) if self.enhance_var.get() else prompt
                raw_size = self.size_var.get().split()[0]
                w, h = map(int, raw_size.split("x"))
                model = self.model_var.get().split()[0]
                out_dir = self.output_dir.get()
                os.makedirs(out_dir, exist_ok=True)

                enc = urllib.parse.quote(enhanced)
                url = (f"https://image.pollinations.ai/prompt/{enc}"
                       f"?width={w}&height={h}&model={model}"
                       f"&seed={seed}&nologo=true&enhance=true")

                safe_prompt = re.sub(r'[\/\\\:\*\?\"\<\>\|\n\r\t]', '', prompt).strip()[:50]
                filepath = os.path.join(out_dir, f"{seed}_{safe_prompt}_{int(time.time())+i}.jpg")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=90) as resp, \
                        open(filepath, "wb") as f:
                    f.write(resp.read())

                self.history.insert(0, {
                    "prompt": prompt, "enhanced": enhanced,
                    "path": filepath, "time": time.strftime("%Y-%m-%d %H:%M"),
                    "seed": seed,
                })
                self.history = self.history[:80]
                ok += 1
                self.root.after(0, self._show_preview, filepath)
            except Exception as e:
                self.root.after(0, self._set_status, f"❌ 錯誤: {e}", "#f87171")

        self.root.after(0, self._done, ok, count)

    def _done(self, ok, total):
        self.generating = False
        self.progressbar.stop()
        self.btn_generate.config(state="normal", bg=THEME["accent"], text="✨ 開始 AI 智慧生圖")
        self.session_count += ok
        self.session_lbl.config(text=f"本次生成：{self.session_count} 張")
        self._set_status(f"✅ 完成！成功生成 {ok}/{total} 張", THEME["green"])
        self._refresh_gallery()
        self._refresh_hist_listbox()
        self._refresh_prompt_combo()

    # ── Prompt Enhancer ───────────────────────────────────────────────────────
    def _enhance(self, prompt: str) -> str:
        terms = [en for zh, en in SMART_DICT.items() if zh in prompt]
        translated = prompt
        if re.search(r"[\u4e00-\u9fa5]", prompt):
            try:
                url = (f"https://api.mymemory.translated.net/get"
                       f"?q={urllib.parse.quote(prompt)}&langpair=zh-TW|en")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = resp.read().decode()
                    import json as _j
                    t = _j.loads(data).get("responseData", {}).get("translatedText", "")
                    if t:
                        translated = t
            except Exception:
                pass
        style = STYLE_PRESETS.get(self.style_var.get(), "")
        parts = [translated] + terms + [style, QUALITY_BOOST]
        return ", ".join(p for p in parts if p)

    def _update_preview_prompt(self, *_):
        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            return
        preview = self._enhance(prompt) if self.enhance_var.get() else prompt
        self.prompt_preview.config(state="normal")
        self.prompt_preview.delete("1.0", "end")
        self.prompt_preview.insert("1.0", preview)
        self.prompt_preview.config(state="disabled")

    def _copy_enhanced_prompt(self):
        self.prompt_preview.config(state="normal")
        text = self.prompt_preview.get("1.0", "end").strip()
        self.prompt_preview.config(state="disabled")
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self._set_status("📋 完整 Prompt 已複製到剪貼簿！", THEME["green"])

    # ── Negative Tag Toggle ───────────────────────────────────────────────────
    def _toggle_neg_tag(self, label: str, value: str):
        cur = self.neg_text.get()
        if label in self.neg_active_tags:
            self.neg_active_tags.discard(label)
            cur = cur.replace(f", {value}", "").replace(value, "").strip(", ")
            self.neg_chip_btns[label].config(bg="#1e293b", fg="#94a3b8")
        else:
            self.neg_active_tags.add(label)
            cur = (cur + f", {value}").strip(", ")
            self.neg_chip_btns[label].config(bg=THEME["accent"], fg="white")
        self.neg_text.delete(0, "end")
        self.neg_text.insert(0, cur)

    # ── Preview & Fullscreen ──────────────────────────────────────────────────
    def _show_preview(self, filepath):
        self.current_filepath = filepath
        try:
            img = Image.open(filepath)
            cw = self.canvas_frame.winfo_width()  or 700
            ch = self.canvas_frame.winfo_height() or 520
            img.thumbnail((cw - 10, ch - 10), Image.Resampling.LANCZOS)
            self.preview_img_obj = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.preview_img_obj, text="")
            
            # 尋找對應的歷史記錄以獲取 Seed
            matching_item = next((item for item in self.history if item.get("path") == filepath), None)
            if matching_item:
                seed = matching_item.get("seed", "無")
                self._set_status(f"📷 預覽圖片 | Seed: {seed} | 提示詞: {matching_item.get('prompt')[:40]}...", THEME["cyan"])
        except Exception:
            self.image_label.config(text=f"已儲存: {os.path.basename(filepath)}", image="")

    def _open_fullscreen(self, event=None):
        if not self.current_filepath or not os.path.exists(self.current_filepath):
            return
        win = tk.Toplevel(self.root)
        win.title("全螢幕預覽 (ESC / 點擊關閉)")
        win.configure(bg="#000")
        win.attributes("-fullscreen", True)
        win.bind("<Escape>",    lambda e: win.destroy())
        win.bind("<Button-1>", lambda e: win.destroy())
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        img = Image.open(self.current_filepath)
        img.thumbnail((sw, sh), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        lbl = tk.Label(win, image=photo, bg="#000")
        lbl.image = photo
        lbl.pack(expand=True)
        tk.Label(win, text="ESC 或點擊關閉", bg="#000", fg="#444",
                 font=("Segoe UI", 9)).pack(pady=4)

    def _image_context_menu(self, event=None):
        if not self.current_filepath:
            return
        menu = tk.Menu(self.root, tearoff=0, bg=THEME["bg_card"],
                       fg=THEME["text"], activebackground=THEME["accent"],
                       activeforeground="white")
        menu.add_command(label="⭐ 加入收藏",    command=self._add_to_favorites)
        menu.add_command(label="🔍 全螢幕預覽",  command=self._open_fullscreen)
        menu.add_command(label="🖥 設為桌布",   command=self._set_as_wallpaper)
        menu.add_command(label="📋 另存新檔",    command=self._save_as)
        menu.add_separator()
        menu.add_command(label="🗑 刪除此圖片",  command=self._delete_current)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ── Thumbnail Gallery ─────────────────────────────────────────────────────
    def _refresh_gallery(self):
        for w in self.thumb_frame.winfo_children():
            w.destroy()
        out_dir = self.output_dir.get()
        try:
            files = sorted(
                [f for f in os.listdir(out_dir)
                 if f.endswith(".jpg") and (f.startswith("studio_") or f.startswith("char_") or re.match(r'^\d+_', f))],
                key=lambda x: os.path.getmtime(os.path.join(out_dir, x)),
                reverse=True,
            )[:8]
        except Exception:
            return
        for fp in files:
            full = os.path.join(out_dir, fp)
            try:
                img = Image.open(full)
                img.thumbnail((82, 82), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                lbl = tk.Label(self.thumb_frame, image=photo, bg=THEME["bg_card"],
                               cursor="hand2", highlightthickness=2,
                               highlightbackground=THEME["border"])
                lbl.image = photo
                lbl.pack(side="left", padx=3, pady=2)
                lbl.bind("<Button-1>", lambda e, p=full: self._show_preview(p))
                lbl.bind("<Button-3>", lambda e, p=full: self._thumb_context(e, p))
                lbl.bind("<Enter>", lambda e, l=lbl: l.config(highlightbackground=THEME["cyan"]))
                lbl.bind("<Leave>", lambda e, l=lbl: l.config(highlightbackground=THEME["border"]))
            except Exception:
                pass

    def _thumb_context(self, event, path):
        self.current_filepath = path
        self._show_preview(path)
        self._image_context_menu(event)

    # ── Favorites ─────────────────────────────────────────────────────────────
    def _add_to_favorites(self):
        if not self.current_filepath or not os.path.exists(self.current_filepath):
            messagebox.showinfo("提示", "請先生成一張圖片！")
            return
        if self.current_filepath not in self.favorites:
            self.favorites.insert(0, self.current_filepath)
            self._save_json(FAVORITES_FILE, self.favorites)
            self._refresh_fav_listbox()
            self._set_status("⭐ 已加入收藏！", THEME["gold"])
        else:
            self._set_status("⭐ 此圖片已在收藏中。", THEME["muted"])

    def _refresh_fav_listbox(self):
        self.fav_listbox.delete(0, "end")
        self.favorites = [f for f in self.favorites if os.path.exists(f)]
        for fp in self.favorites:
            self.fav_listbox.insert("end", f"⭐ {os.path.basename(fp)}")

    def _open_fav_image(self, event=None):
        sel = self.fav_listbox.curselection()
        if sel:
            path = self.favorites[sel[0]]
            if os.path.exists(path):
                self._show_preview(path)

    def _remove_favorite(self):
        sel = self.fav_listbox.curselection()
        if sel:
            self.favorites.pop(sel[0])
            self._save_json(FAVORITES_FILE, self.favorites)
            self._refresh_fav_listbox()

    # ── Wallpaper ─────────────────────────────────────────────────────────────
    def _set_as_wallpaper(self):
        if not self.current_filepath or not os.path.exists(self.current_filepath):
            messagebox.showinfo("提示", "請先生成一張圖片！")
            return
        try:
            import ctypes
            ctypes.windll.user32.SystemParametersInfoW(20, 0, self.current_filepath, 3)
            self._set_status("🖥 已成功設定為 Windows 桌布！", THEME["green"])
        except Exception as e:
            messagebox.showerror("設定失敗", str(e))

    # ── Misc ──────────────────────────────────────────────────────────────────
    def _roll_inspiration(self):
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("1.0", random.choice(INSPIRATION_PROMPTS))
        self._update_preview_prompt()

    def _apply_prompt_history(self, event=None):
        v = self.prompt_history_var.get()
        if "──" not in v:
            self.prompt_text.delete("1.0", "end")
            self.prompt_text.insert("1.0", v)
            self._update_preview_prompt()

    def _load_from_hist_lb(self, event=None):
        sel = self.hist_listbox.curselection()
        if sel and sel[0] < len(self.history):
            item = self.history[sel[0]]
            p = item.get("prompt", "")
            seed = item.get("seed", "")
            
            # 填入提示詞與 Seed
            self.prompt_text.delete("1.0", "end")
            self.prompt_text.insert("1.0", p)
            self.char_desc_text.delete("1.0", "end")
            self.char_desc_text.insert("1.0", p)
            self.seed_var.set(seed)
            
            self._update_preview_prompt()
            self._update_char_preview()

    def _clear_history(self):
        if messagebox.askyesno("確認", "確定要清除所有記錄嗎？"):
            self.history = []
            # self._save_json(HISTORY_FILE, self.history)  # Disabled history saving
            self._refresh_hist_listbox()
            self._refresh_prompt_combo()

    def _refresh_hist_listbox(self):
        self.hist_listbox.delete(0, "end")
        for item in self.history[:40]:
            self.hist_listbox.insert(
                "end", f"[{item.get('time','')}] {item.get('prompt','')[:35]}")

    def _refresh_prompt_combo(self):
        prompts = list(dict.fromkeys(
            i["prompt"] for i in self.history if i.get("prompt")))[:20]
        self.ph_combo["values"] = prompts
        self.prompt_history_var.set("── 點此套用歷史提示詞 ──")

    def _refresh_fav_listbox(self):
        self.fav_listbox.delete(0, "end")
        self.favorites = [f for f in self.favorites if os.path.exists(f)]
        for fp in self.favorites:
            self.fav_listbox.insert("end", f"⭐ {os.path.basename(fp)}")

    def _pick_output_dir(self):
        d = filedialog.askdirectory(initialdir=self.output_dir.get())
        if d:
            self.output_dir.set(d)
            self.settings["output_dir"] = d
            self._save_json(SETTINGS_FILE, self.settings)
            self._refresh_gallery()

    def _save_as(self):
        if not self.current_filepath or not os.path.exists(self.current_filepath):
            messagebox.showinfo("提示", "請先生成一張圖片！")
            return
        dest = filedialog.asksaveasfilename(
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"), ("All", "*.*")],
            initialfile=os.path.basename(self.current_filepath))
        if dest:
            shutil.copy2(self.current_filepath, dest)
            self._set_status(f"✅ 已另存至: {os.path.basename(dest)}", THEME["green"])

    def _delete_current(self):
        if not self.current_filepath or not os.path.exists(self.current_filepath):
            return
        if messagebox.askyesno("確認刪除", f"確定要刪除這張圖片嗎？\n{os.path.basename(self.current_filepath)}"):
            os.remove(self.current_filepath)
            self.current_filepath = None
            self.image_label.config(image="", text="圖片已刪除")
            self._refresh_gallery()
            self._set_status("🗑 圖片已刪除。", THEME["muted"])

    def open_folder(self):
        os.startfile(self.output_dir.get())

    def _set_status(self, text, color):
        self.status_label.config(text=text, fg=color)

    @staticmethod
    def _btn(parent, text, color, cmd):
        return tk.Button(parent, text=text, font=("Segoe UI", 9, "bold"),
                         bg=color, fg="white", activebackground="#1d2535",
                         activeforeground="white", relief="flat", bd=0,
                         cursor="hand2", command=cmd, padx=8, pady=3)

    @staticmethod
    def _load_json(path, default):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return default

    @staticmethod
    def _save_json(path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def on_close(self):
        self.root.destroy()
        # Remove __pycache__ directory if it exists
        cache_dir = os.path.join(os.path.dirname(__file__), "__pycache__")
        if os.path.isdir(cache_dir):
            try:
                shutil.rmtree(cache_dir)
            except Exception:
                pass
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0) # WM_CLOSE
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import ctypes
            title = f"✨ Smart AI Studio {APP_VERSION}"
            hwnd = ctypes.windll.user32.FindWindowW(None, title)
            if hwnd:
                # 還原（若是最小化）並置頂已啟動的視窗
                ctypes.windll.user32.ShowWindow(hwnd, 9) # 9 = SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                # 關閉新開啟的 cmd 視窗
                console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                if console_hwnd:
                    ctypes.windll.user32.PostMessageW(console_hwnd, 0x0010, 0, 0)
                sys.exit(0)
        except Exception:
            pass

    root = tk.Tk()
    SmartAIStudioApp(root)
    root.mainloop()
