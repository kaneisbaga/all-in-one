# ⚓ 現代海戰 (Naval Combat Game) - 跨電腦遠端連線對戰

一款支援兩台電腦跨網路即時對抗的現代軍事雷達風格海戰遊戲！採用類似 **Kahoot** 的 6 位數房間 PIN 碼機制，輸入號碼即可快速連線開戰。

---

## 🎮 特色功能

1. **Kahoot 風格 6 位數 PIN 碼連線**：
   - 房主點擊「建立對戰」，立即生成如 `582 914` 醒目大號碼。
   - 另一台電腦輸入 6 位數字（或點擊專屬邀請網址）即可一秒加入對決。
2. **WebRTC P2P 網際網路直連 (PeerJS)**：
   - 兩台電腦直接點對點通訊，**不需要自己架設伺服器**，免開 Port / 免轉發，跨不同 Wi-Fi / 外網皆可連線。
3. **經典 10×10 海戰規則**：
   - 包含 5 艘經典軍艦：航空母艦 (5格)、戰列艦 (4格)、巡洋艦 (3格)、潛水艇 (3格)、驅逐艦 (2格)。
   - 支援手動佈陣（空白鍵切換水平/垂直旋轉）或「一鍵隨機佈陣」。
4. **軍事雷達科技視覺與 Web Audio 音效**：
   - 深海軍事科技藍 UI、即時旋轉雷達掃描線、逼真砲火爆炸與水花動畫。
   - 純程式合成音效（聲納探測、主砲轟鳴、水花噴濺、金屬爆炸、沉沒警報與勝利號角），免下載任何音訊檔，內建靜音開關。
5. **戰情通訊與互動**：
   - 即時文字聊天室與戰術罐頭嘲諷語（「鎖定你了！」、「好險沒中！」、「GG WP!」）。
   - 敵艦戰損狀態監控、戰後統計數據彈窗與一鍵重賽（Rematch）機制。
6. **智械 AI 單機練靶模式**：
   - 朋友還沒上線？內建採用智慧獵殺 (Hunt & Target) 演算法的 AI 電腦，提供極具挑戰性的單人對決。

---

## 🚀 如何啟動遊玩？

本專案為**純靜態免安裝**網頁應用，無需安裝 Node.js、Python 或任何伺服器環境。

### 步驟 1：開啟遊戲
- 直接在檔案總管中**雙擊 `index.html`**（使用 Chrome、Edge、Brave、Firefox 等現代瀏覽器開啟）。

### 步驟 2：兩台電腦連線對戰
1. **電腦 A（房主）**：
   - 點擊「**生成對戰房間 (GENERATE PIN)**」。
   - 畫面上會顯示大字體的 6 位數 PIN 碼（例如 `729 481`）。
   - 也可以點擊「複製邀請網址」直接貼給朋友。
2. **電腦 B（加入者）**：
   - 打開 `index.html`，切換到「**輸入 PIN (JOIN)**」分頁。
   - 輸入電腦 A 的 6 位數字 PIN 碼，點擊「**加入對戰 (JOIN BATTLE)**」。
3. **開始對決**：
   - 雙方連線成功後會自動進入「艦隊佈陣」階段。
   - 放置好 5 艘戰艦後點擊「準備完成」，系統將隨機決定先攻方，正式打響海戰！

---

## 🌐 想放在網路上讓朋友點網址就玩？

你可以直接將本專案資料夾上傳到免費靜態主機（如 **GitHub Pages**、**Vercel** 或 **Netlify**）：
- **GitHub Pages**：將本資料夾建立為 GitHub Repo，在 Settings -> Pages 選擇 main 分支發布。
- 發布後會得到一組專屬網址（例如 `https://yourname.github.io/naval-combat/`），朋友點開就能直接連線！

---

## 📂 專案檔案架構

- [`index.html`](file:///C:/Users/kanei/OneDrive/%E6%A1%8C%E9%9D%A2/Antigravity%20CLI/index.html) - 主遊戲頁面與 DOM 結構（大廳、佈陣、對戰雙棋盤、戰情報告）
- [`style.css`](file:///C:/Users/kanei/OneDrive/%E6%A1%8C%E9%9D%A2/Antigravity%20CLI/style.css) - 現代軍事雷達科技樣式、動態掃描線與打擊動畫
- [`game.js`](file:///C:/Users/kanei/OneDrive/%E6%A1%8C%E9%9D%A2/Antigravity%20CLI/game.js) - 核心遊戲狀態機、PeerJS P2P 網路通訊協定、智慧 AI 演算法
- [`audio.js`](file:///C:/Users/kanei/OneDrive/%E6%A1%8C%E9%9D%A2/Antigravity%20CLI/audio.js) - Web Audio API 純代碼合成聲納、砲擊、爆炸與號角音效
- [`TUTORIAL.md`](file:///C:/Users/kanei/OneDrive/%E6%A1%8C%E9%9D%A2/Antigravity%20CLI/TUTORIAL.md) - 完整戰術手冊、遊戲規則與五大必勝戰術指南
- [`README.md`](file:///C:/Users/kanei/OneDrive/%E6%A1%8C%E9%9D%A2/Antigravity%20CLI/README.md) - 快速啟動指引與連線說明
