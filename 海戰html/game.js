/**
 * NAVAL COMBAT - P2P MULTIPLAYER & SMART AI GAME ENGINE
 */

const SHIPS_CONFIG = [
    { id: 'carrier', name: '航空母艦 (Carrier)', length: 5 },
    { id: 'battleship', name: '戰列艦 (Battleship)', length: 4 },
    { id: 'cruiser', name: '巡洋艦 (Cruiser)', length: 3 },
    { id: 'submarine', name: '潛水艇 (Submarine)', length: 3 },
    { id: 'destroyer', name: '驅逐艦 (Destroyer)', length: 2 }
];

const BOARD_SIZE = 10;
const PEER_PREFIX = 'agy-navy-pin-';

class NavalGame {
    constructor() {
        this.gameMode = null; // 'online-host' | 'online-guest' | 'solo-ai'
        this.peer = null;
        this.conn = null;
        this.roomPin = null;

        // 玩家本機棋盤狀態
        this.myGrid = this.createEmptyGrid();
        this.myShips = []; // { id, name, length, positions: [{x, y, hit: bool}] }
        this.selectedShipIndex = 0;
        this.shipOrientation = 'H'; // 'H' 水平 | 'V' 垂直
        this.isMyReady = false;
        this.isOpponentReady = false;

        // 敵方棋盤狀態
        this.enemyGrid = this.createEmptyGrid(); // 記錄我方對敵方的攻擊: null, 'hit', 'miss'
        this.enemySunkShips = [];

        // 對戰狀態
        this.currentTurn = null; // 'me' | 'opponent'
        this.isGameOver = false;
        this.totalShots = 0;
        this.totalHits = 0;
        this.startTime = null;

        // AI 狀態 (用於單機模式)
        this.aiFleet = [];
        this.aiTargetQueue = [];
        this.aiHitStack = [];

        this.initUI();
        this.checkUrlForPin();
    }

    createEmptyGrid() {
        return Array.from({ length: BOARD_SIZE }, () => Array(BOARD_SIZE).fill(null));
    }

    /* ================= UI 綁定與初始化 ================= */
    initUI() {
        // 大廳頁籤切換
        document.getElementById('tabHost').addEventListener('click', () => this.switchTab('host'));
        document.getElementById('tabJoin').addEventListener('click', () => this.switchTab('join'));
        document.getElementById('tabSolo').addEventListener('click', () => this.switchTab('solo'));

        // 大廳按鈕
        document.getElementById('btnCreateRoom').addEventListener('click', () => this.startHosting());
        document.getElementById('btnJoinRoom').addEventListener('click', () => this.joinByPin());
        document.getElementById('btnStartSolo').addEventListener('click', () => this.startSoloMode());
        document.getElementById('btnCopyPin').addEventListener('click', () => this.copyPin());
        document.getElementById('btnCopyLink').addEventListener('click', () => this.copyInviteLink());

        // 靜音切換
        document.getElementById('btnSoundToggle').addEventListener('click', () => {
            const muted = window.soundManager.toggleMute();
            document.getElementById('btnSoundToggle').innerText = muted ? '🔇 靜音' : '🔊 音效';
        });

        // 戰術教學彈窗
        const tutorialModal = document.getElementById('tutorialModal');
        const openTutorial = () => {
            window.soundManager.playClick();
            tutorialModal.classList.remove('hidden');
        };
        const closeTutorial = () => {
            window.soundManager.playClick();
            tutorialModal.classList.add('hidden');
        };
        document.getElementById('btnTutorial').addEventListener('click', openTutorial);
        document.getElementById('btnCloseTutorial').addEventListener('click', closeTutorial);
        document.getElementById('btnGotItTutorial').addEventListener('click', closeTutorial);


        // 佈陣階段按鈕
        document.getElementById('btnRotateShip').addEventListener('click', () => this.toggleOrientation());
        document.getElementById('btnRandomFleet').addEventListener('click', () => this.randomizeMyFleet());
        document.getElementById('btnResetFleet').addEventListener('click', () => this.resetFleet());
        document.getElementById('btnConfirmReady').addEventListener('click', () => this.confirmReady());

        // 鍵盤空白鍵旋轉
        window.addEventListener('keydown', (e) => {
            if (e.code === 'Space' && !document.getElementById('viewDeployment').classList.contains('hidden')) {
                e.preventDefault();
                this.toggleOrientation();
            }
        });

        // 聊天與罐頭語
        document.getElementById('btnSendChat').addEventListener('click', () => this.sendChatMessage());
        document.getElementById('chatInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendChatMessage();
        });

        document.querySelectorAll('.taunt-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const text = btn.innerText;
                this.sendChatMessage(text);
            });
        });

        // 重賽與結束彈窗按鈕
        document.getElementById('btnRematch').addEventListener('click', () => this.requestRematch());
        document.getElementById('btnBackLobby').addEventListener('click', () => location.reload());

        // 繪製棋盤 DOM
        this.renderDeploymentBoard();
        this.renderBattleBoards();
        this.renderShipInventory();
    }

    switchTab(tab) {
        window.soundManager.playClick();
        document.querySelectorAll('.lobby-tab').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));

        if (tab === 'host') {
            document.getElementById('tabHost').classList.add('active');
            document.getElementById('hostContent').classList.add('active');
        } else if (tab === 'join') {
            document.getElementById('tabJoin').classList.add('active');
            document.getElementById('joinContent').classList.add('active');
            document.getElementById('inputPin').focus();
        } else if (tab === 'solo') {
            document.getElementById('tabSolo').classList.add('active');
            document.getElementById('soloContent').classList.add('active');
        }
    }

    checkUrlForPin() {
        const params = new URLSearchParams(window.location.search);
        const pin = params.get('pin');
        if (pin && pin.length === 6) {
            this.switchTab('join');
            document.getElementById('inputPin').value = pin;
            this.showToast(`已自動帶入房間 PIN: ${pin}`);
        }
    }

    showToast(msg) {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.innerText = msg;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    }

    showView(viewId) {
        document.querySelectorAll('.view-section').forEach(v => v.classList.add('hidden'));
        document.getElementById(viewId).classList.remove('hidden');
    }

    /* ================= PEERJS P2P 網路連線 ================= */
    getIceConfig() {
        return {
            config: {
                iceServers: [
                    { urls: 'stun:stun.l.google.com:19302' },
                    { urls: 'stun:stun1.l.google.com:19302' },
                    { urls: 'stun:stun2.l.google.com:19302' }
                ]
            }
        };
    }

    startHosting() {
        window.soundManager.playSonar();
        this.gameMode = 'online-host';
        this.roomPin = Math.floor(100000 + Math.random() * 900000).toString();
        const peerId = PEER_PREFIX + this.roomPin;

        document.getElementById('displayPin').innerText = `${this.roomPin.slice(0, 3)} ${this.roomPin.slice(3)}`;
        document.getElementById('hostWaitingBox').classList.remove('hidden');
        document.getElementById('btnCreateRoom').disabled = true;

        this.peer = new Peer(peerId, this.getIceConfig());

        this.peer.on('open', (id) => {
            console.log('Host Peer opened with ID:', id);
        });

        this.peer.on('connection', (conn) => {
            this.conn = conn;
            this.setupConnectionHandlers();
            this.showToast('對手已成功連線！進入佈陣階段...');
            setTimeout(() => this.goToDeployment(), 1000);
        });

        this.peer.on('error', (err) => {
            console.error('Peer error:', err);
            if (err.type === 'unavailable-id') {
                // PIN 碰撞，重試一個
                this.startHosting();
            } else {
                this.showToast(`連線訊號錯誤: ${err.type}`);
            }
        });
    }

    joinByPin() {
        const pin = document.getElementById('inputPin').value.trim().replace(/\s+/g, '');
        if (pin.length !== 6 || isNaN(pin)) {
            this.showToast('請輸入正確的 6 位數 PIN 碼！');
            return;
        }

        window.soundManager.playSonar();
        this.gameMode = 'online-guest';
        this.roomPin = pin;
        const hostPeerId = PEER_PREFIX + pin;

        document.getElementById('btnJoinRoom').innerText = '連線中...';
        document.getElementById('btnJoinRoom').disabled = true;

        this.peer = new Peer(this.getIceConfig());

        this.peer.on('open', (id) => {
            console.log('Guest Peer opened, connecting to host:', hostPeerId);
            this.conn = this.peer.connect(hostPeerId, { reliable: true });
            this.setupConnectionHandlers();
        });

        this.peer.on('error', (err) => {
            console.error('Peer error:', err);
            this.showToast('連線失敗，請檢查 PIN 碼是否正確且房主在線！');
            document.getElementById('btnJoinRoom').innerText = '加入對戰 (JOIN)';
            document.getElementById('btnJoinRoom').disabled = false;
        });
    }

    setupConnectionHandlers() {
        this.conn.on('open', () => {
            console.log('P2P DataConnection established!');
            this.showToast('雙方連線建立完畢！');
            if (this.gameMode === 'online-guest') {
                setTimeout(() => this.goToDeployment(), 800);
            }
        });

        this.conn.on('data', (data) => {
            this.handleIncomingData(data);
        });

        this.conn.on('close', () => {
            this.showToast('對手已斷開連線！');
            this.logBattle('系統', '對手已退出遊戲。', 'system');
        });
    }

    sendData(type, payload = {}) {
        if (this.conn && this.conn.open) {
            this.conn.send({ type, ...payload });
        }
    }

    handleIncomingData(data) {
        console.log('Received data:', data);
        switch (data.type) {
            case 'OPPONENT_READY':
                this.isOpponentReady = true;
                this.updateReadyUI();
                this.checkBothReady();
                break;

            case 'START_BATTLE':
                this.currentTurn = data.firstTurn === (this.gameMode === 'online-host' ? 'host' : 'guest') ? 'me' : 'opponent';
                this.goToBattle();
                break;

            case 'FIRE_SHOT':
                this.handleEnemyShotAtMe(data.x, data.y);
                break;

            case 'FIRE_RESULT':
                this.handleMyShotResult(data.x, data.y, data.hit, data.sunkShip, data.allSunk);
                break;

            case 'CHAT_MSG':
                this.displayChatMessage(data.sender, data.text);
                break;

            case 'REMATCH_OFFER':
                this.showToast('對手提議再來一局！');
                this.resetForRematch();
                break;
        }
    }

    fallbackCopyText(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
        } catch (e) {
            console.warn('Fallback copy error:', e);
        }
        document.body.removeChild(textarea);
    }

    copyPin() {
        if (!this.roomPin) return;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(this.roomPin).then(() => {
                this.showToast(`已複製 PIN 碼: ${this.roomPin}`);
            }).catch(() => {
                this.fallbackCopyText(this.roomPin);
                this.showToast(`已複製 PIN 碼: ${this.roomPin}`);
            });
        } else {
            this.fallbackCopyText(this.roomPin);
            this.showToast(`已複製 PIN 碼: ${this.roomPin}`);
        }
    }

    copyInviteLink() {
        if (!this.roomPin) return;
        const url = `${window.location.origin}${window.location.pathname}?pin=${this.roomPin}`;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(url).then(() => {
                this.showToast('已複製專屬對戰邀請連結！');
            }).catch(() => {
                this.fallbackCopyText(url);
                this.showToast('已複製專屬對戰邀請連結！');
            });
        } else {
            this.fallbackCopyText(url);
            this.showToast('已複製專屬對戰邀請連結！');
        }
    }

    /* ================= 單機模式 (SOLO VS SMART AI) ================= */
    startSoloMode() {
        window.soundManager.playSonar();
        this.gameMode = 'solo-ai';
        this.showToast('已啟動單機練靶模式！對手為智械雷達 AI');
        this.setupAiFleet();
        this.goToDeployment();
    }

    setupAiFleet() {
        this.aiFleet = [];
        const aiGrid = this.createEmptyGrid();

        SHIPS_CONFIG.forEach(ship => {
            let placed = false;
            while (!placed) {
                const orientation = Math.random() > 0.5 ? 'H' : 'V';
                const x = Math.floor(Math.random() * (orientation === 'H' ? BOARD_SIZE - ship.length + 1 : BOARD_SIZE));
                const y = Math.floor(Math.random() * (orientation === 'V' ? BOARD_SIZE - ship.length + 1 : BOARD_SIZE));

                let collision = false;
                for (let i = 0; i < ship.length; i++) {
                    const cx = orientation === 'H' ? x + i : x;
                    const cy = orientation === 'V' ? y + i : y;
                    if (aiGrid[cy][cx] !== null) {
                        collision = true;
                        break;
                    }
                }

                if (!collision) {
                    const positions = [];
                    for (let i = 0; i < ship.length; i++) {
                        const cx = orientation === 'H' ? x + i : x;
                        const cy = orientation === 'V' ? y + i : y;
                        aiGrid[cy][cx] = ship.id;
                        positions.push({ x: cx, y: cy, hit: false });
                    }
                    this.aiFleet.push({ id: ship.id, name: ship.name, length: ship.length, positions });
                    placed = true;
                }
            }
        });
    }

    /* ================= 艦隊佈陣階段 (DEPLOYMENT) ================= */
    goToDeployment() {
        this.showView('viewDeployment');
        this.resetFleet();
    }

    renderShipInventory() {
        const container = document.getElementById('shipInventoryList');
        container.innerHTML = '';

        SHIPS_CONFIG.forEach((ship, index) => {
            const item = document.createElement('div');
            item.className = `ship-item ${this.selectedShipIndex === index ? 'selected' : ''}`;
            const isPlaced = this.myShips.some(s => s.id === ship.id);
            if (isPlaced) item.classList.add('placed');

            item.innerHTML = `
                <div class="ship-item-name">${ship.name}</div>
                <div class="ship-blocks">
                    ${Array(ship.length).fill('<div class="ship-block-mini"></div>').join('')}
                </div>
            `;

            item.addEventListener('click', () => {
                window.soundManager.playClick();
                this.selectedShipIndex = index;
                this.renderShipInventory();
            });

            container.appendChild(item);
        });
    }

    toggleOrientation() {
        window.soundManager.playClick();
        this.shipOrientation = this.shipOrientation === 'H' ? 'V' : 'H';
        document.getElementById('rotateIndicator').innerText = this.shipOrientation === 'H' ? '水平' : '垂直';
    }

    renderDeploymentBoard() {
        const grid = document.getElementById('deploymentGrid');
        grid.innerHTML = '';

        for (let y = 0; y < BOARD_SIZE; y++) {
            for (let x = 0; x < BOARD_SIZE; x++) {
                const cell = document.createElement('div');
                cell.className = 'grid-cell';
                cell.dataset.x = x;
                cell.dataset.y = y;

                cell.addEventListener('mouseenter', () => this.handleDeployPreview(x, y));
                cell.addEventListener('mouseleave', () => this.clearDeployPreview());
                cell.addEventListener('click', () => this.handleDeployClick(x, y));
                cell.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    this.toggleOrientation();
                    this.handleDeployPreview(x, y);
                });

                grid.appendChild(cell);
            }
        }
    }

    canPlaceShip(shipLen, startX, startY, orientation) {
        if (orientation === 'H') {
            if (startX + shipLen > BOARD_SIZE) return false;
            for (let i = 0; i < shipLen; i++) {
                if (this.myGrid[startY][startX + i] !== null) return false;
            }
        } else {
            if (startY + shipLen > BOARD_SIZE) return false;
            for (let i = 0; i < shipLen; i++) {
                if (this.myGrid[startY + i][startX] !== null) return false;
            }
        }
        return true;
    }

    handleDeployPreview(x, y) {
        this.clearDeployPreview();
        const currentShip = SHIPS_CONFIG[this.selectedShipIndex];
        if (!currentShip || this.myShips.some(s => s.id === currentShip.id)) return;

        const isValid = this.canPlaceShip(currentShip.length, x, y, this.shipOrientation);
        const className = isValid ? 'preview-valid' : 'preview-invalid';

        for (let i = 0; i < currentShip.length; i++) {
            const px = this.shipOrientation === 'H' ? x + i : x;
            const py = this.shipOrientation === 'V' ? y + i : y;
            if (px < BOARD_SIZE && py < BOARD_SIZE) {
                const cell = document.querySelector(`#deploymentGrid .grid-cell[data-x="${px}"][data-y="${py}"]`);
                if (cell) cell.classList.add(className);
            }
        }
    }

    clearDeployPreview() {
        document.querySelectorAll('#deploymentGrid .grid-cell').forEach(cell => {
            cell.classList.remove('preview-valid', 'preview-invalid');
        });
    }

    handleDeployClick(x, y) {
        const currentShip = SHIPS_CONFIG[this.selectedShipIndex];
        if (!currentShip) return;

        // 若該艦已擺放，先移除
        this.removeShip(currentShip.id);

        if (this.canPlaceShip(currentShip.length, x, y, this.shipOrientation)) {
            window.soundManager.playClick();
            const positions = [];
            for (let i = 0; i < currentShip.length; i++) {
                const px = this.shipOrientation === 'H' ? x + i : x;
                const py = this.shipOrientation === 'V' ? y + i : y;
                this.myGrid[py][px] = currentShip.id;
                positions.push({ x: px, y: py, hit: false });
            }

            this.myShips.push({
                id: currentShip.id,
                name: currentShip.name,
                length: currentShip.length,
                positions
            });

            // 自動切換到下一艘尚未放置的戰艦
            const nextIdx = SHIPS_CONFIG.findIndex(s => !this.myShips.some(placed => placed.id === s.id));
            if (nextIdx !== -1) {
                this.selectedShipIndex = nextIdx;
            }

            this.updateDeploymentGridVisuals();
            this.renderShipInventory();
        } else {
            window.soundManager.playMiss();
        }
    }

    removeShip(shipId) {
        const index = this.myShips.findIndex(s => s.id === shipId);
        if (index !== -1) {
            for (let y = 0; y < BOARD_SIZE; y++) {
                for (let x = 0; x < BOARD_SIZE; x++) {
                    if (this.myGrid[y][x] === shipId) {
                        this.myGrid[y][x] = null;
                    }
                }
            }
            this.myShips.splice(index, 1);
        }
    }

    updateDeploymentGridVisuals() {
        for (let y = 0; y < BOARD_SIZE; y++) {
            for (let x = 0; x < BOARD_SIZE; x++) {
                const cell = document.querySelector(`#deploymentGrid .grid-cell[data-x="${x}"][data-y="${y}"]`);
                if (cell) {
                    if (this.myGrid[y][x] !== null) {
                        cell.classList.add('has-ship');
                    } else {
                        cell.classList.remove('has-ship');
                    }
                }
            }
        }

        const btnReady = document.getElementById('btnConfirmReady');
        if (this.myShips.length === SHIPS_CONFIG.length) {
            btnReady.disabled = false;
            btnReady.classList.add('btn-primary');
            btnReady.innerText = '準備完成 (READY)';
        } else {
            btnReady.disabled = true;
            btnReady.innerText = `準備完成 (${this.myShips.length}/5)`;
        }
    }

    resetFleet() {
        window.soundManager.playClick();
        this.myGrid = this.createEmptyGrid();
        this.myShips = [];
        this.selectedShipIndex = 0;
        this.updateDeploymentGridVisuals();
        this.renderShipInventory();
    }

    randomizeMyFleet() {
        window.soundManager.playClick();
        this.resetFleet();

        SHIPS_CONFIG.forEach(ship => {
            let placed = false;
            while (!placed) {
                const orientation = Math.random() > 0.5 ? 'H' : 'V';
                const x = Math.floor(Math.random() * (orientation === 'H' ? BOARD_SIZE - ship.length + 1 : BOARD_SIZE));
                const y = Math.floor(Math.random() * (orientation === 'V' ? BOARD_SIZE - ship.length + 1 : BOARD_SIZE));

                if (this.canPlaceShip(ship.length, x, y, orientation)) {
                    const positions = [];
                    for (let i = 0; i < ship.length; i++) {
                        const px = orientation === 'H' ? x + i : x;
                        const py = orientation === 'V' ? y + i : y;
                        this.myGrid[py][px] = ship.id;
                        positions.push({ x: px, y: py, hit: false });
                    }
                    this.myShips.push({ id: ship.id, name: ship.name, length: ship.length, positions });
                    placed = true;
                }
            }
        });

        this.updateDeploymentGridVisuals();
        this.renderShipInventory();
        this.showToast('全艦隊已完成隨機戰術部署！');
    }

    confirmReady() {
        if (this.myShips.length < SHIPS_CONFIG.length) return;
        window.soundManager.playSonar();
        this.isMyReady = true;

        document.getElementById('btnConfirmReady').innerText = '已準備，等待對手...';
        document.getElementById('btnConfirmReady').disabled = true;
        document.getElementById('btnRandomFleet').disabled = true;
        document.getElementById('btnResetFleet').disabled = true;

        if (this.gameMode === 'solo-ai') {
            this.isOpponentReady = true;
            this.currentTurn = 'me';
            setTimeout(() => this.goToBattle(), 600);
        } else {
            this.sendData('OPPONENT_READY');
            this.checkBothReady();
        }
    }

    updateReadyUI() {
        if (this.isOpponentReady) {
            this.showToast('對手艦隊已就位準備完成！');
        }
    }

    checkBothReady() {
        if (this.isMyReady && this.isOpponentReady) {
            if (this.gameMode === 'online-host') {
                const firstTurn = Math.random() > 0.5 ? 'host' : 'guest';
                this.sendData('START_BATTLE', { firstTurn });
                this.currentTurn = firstTurn === 'host' ? 'me' : 'opponent';
                setTimeout(() => this.goToBattle(), 500);
            }
        }
    }

    /* ================= 對戰階段 (BATTLE ARENA) ================= */
    goToBattle() {
        this.showView('viewBattle');
        this.startTime = Date.now();
        this.isGameOver = false;
        this.totalShots = 0;
        this.totalHits = 0;

        this.renderFriendlyBoard();
        this.renderEnemyStatusTracker();
        this.updateTurnBanner();

        this.logBattle('系統', '對戰正式打響！雷達全域鎖定中...', 'system');
        if (this.currentTurn === 'me') {
            this.logBattle('系統', '我方取得先攻開火權！', 'system');
        } else {
            this.logBattle('系統', '敵方取得先攻，請注意規避敵火！', 'system');
            if (this.gameMode === 'solo-ai') {
                setTimeout(() => this.aiTakeTurn(), 1200);
            }
        }
    }

    renderBattleBoards() {
        // 我方棋盤 (Friendly)
        const friendlyGrid = document.getElementById('battleFriendlyGrid');
        friendlyGrid.innerHTML = '';
        for (let y = 0; y < BOARD_SIZE; y++) {
            for (let x = 0; x < BOARD_SIZE; x++) {
                const cell = document.createElement('div');
                cell.className = 'grid-cell';
                cell.id = `f-cell-${x}-${y}`;
                friendlyGrid.appendChild(cell);
            }
        }

        // 敵方雷達棋盤 (Enemy Radar)
        const enemyGrid = document.getElementById('battleEnemyGrid');
        enemyGrid.innerHTML = '';
        for (let y = 0; y < BOARD_SIZE; y++) {
            for (let x = 0; x < BOARD_SIZE; x++) {
                const cell = document.createElement('div');
                cell.className = 'grid-cell';
                cell.id = `e-cell-${x}-${y}`;
                cell.addEventListener('click', () => this.handlePlayerFire(x, y));
                enemyGrid.appendChild(cell);
            }
        }
    }

    renderFriendlyBoard() {
        for (let y = 0; y < BOARD_SIZE; y++) {
            for (let x = 0; x < BOARD_SIZE; x++) {
                const cell = document.getElementById(`f-cell-${x}-${y}`);
                if (!cell) continue;
                cell.className = 'grid-cell';
                if (this.myGrid[y][x] !== null) {
                    cell.classList.add('has-ship');
                }
            }
        }
    }

    renderEnemyStatusTracker() {
        const container = document.getElementById('enemyFleetStatus');
        container.innerHTML = '';
        SHIPS_CONFIG.forEach(ship => {
            const chip = document.createElement('div');
            chip.className = 'enemy-ship-chip';
            chip.id = `enemy-chip-${ship.id}`;
            chip.innerHTML = `
                <span>${ship.name}</span>
                <span>${ship.length} 格</span>
            `;
            container.appendChild(chip);
        });
    }

    updateTurnBanner() {
        const banner = document.getElementById('turnBanner');
        const text = document.getElementById('turnText');

        if (this.currentTurn === 'me') {
            text.className = 'turn-status your-turn';
            text.innerHTML = '⚡ 你的回合 - 請點擊右側敵方雷達開火！';
        } else {
            text.className = 'turn-status opponent-turn';
            text.innerHTML = '⏳ 敵方回合 - 敵艦正在測距瞄準中...';
        }
    }

    /* ================= 開火與命中判定 ================= */
    handlePlayerFire(x, y) {
        if (this.isGameOver) return;
        if (this.currentTurn !== 'me') {
            this.showToast('現在是對方的回合，請稍候！');
            return;
        }

        if (this.enemyGrid[y][x] !== null) {
            this.showToast('該座標已經開火過，請選擇其他座標！');
            return;
        }

        window.soundManager.playCannon();
        this.totalShots++;

        if (this.gameMode === 'solo-ai') {
            this.processAiShotTarget(x, y);
        } else {
            this.sendData('FIRE_SHOT', { x, y });
        }
    }

    // 處理自己開火的結果回饋
    handleMyShotResult(x, y, isHit, sunkShip, isAllSunk) {
        const cell = document.getElementById(`e-cell-${x}-${y}`);
        if (!cell) return;

        if (isHit) {
            window.soundManager.playHit();
            cell.classList.add('hit');
            this.enemyGrid[y][x] = 'hit';
            this.totalHits++;
            this.logBattle('我方砲火', `座標 [${String.fromCharCode(65 + y)}${x + 1}] 命中敵艦！💥`, 'hit');

            if (sunkShip) {
                window.soundManager.playSunk();
                this.logBattle('戰果通報', `敵方 【${sunkShip}】 已被徹底擊沉！`, 'sunk');
                const chip = document.getElementById(`enemy-chip-${sunkShip}`);
                if (chip) chip.classList.add('sunk');
            }
        } else {
            window.soundManager.playMiss();
            cell.classList.add('miss');
            this.enemyGrid[y][x] = 'miss';
            this.logBattle('我方砲火', `座標 [${String.fromCharCode(65 + y)}${x + 1}] 未命中，濺起巨大浪花。`, 'miss');
        }

        if (isAllSunk) {
            this.endGame(true);
        } else {
            this.currentTurn = 'opponent';
            this.updateTurnBanner();
            if (this.gameMode === 'solo-ai') {
                setTimeout(() => this.aiTakeTurn(), 1000);
            }
        }
    }

    // 處理敵方射向我的砲彈
    handleEnemyShotAtMe(x, y) {
        const cell = document.getElementById(`f-cell-${x}-${y}`);
        const shipId = this.myGrid[y][x];
        let isHit = false;
        let sunkShipName = null;

        if (shipId !== null) {
            isHit = true;
            window.soundManager.playHit();
            cell.classList.add('hit');
            this.logBattle('敵方砲火', `敵艦擊中了我們在 [${String.fromCharCode(65 + y)}${x + 1}] 的船艦！`, 'hit');

            // 尋找受損戰艦
            const ship = this.myShips.find(s => s.id === shipId);
            if (ship) {
                const pos = ship.positions.find(p => p.x === x && p.y === y);
                if (pos) pos.hit = true;

                if (ship.positions.every(p => p.hit)) {
                    sunkShipName = ship.name;
                    window.soundManager.playSunk();
                    this.logBattle('警報', `我方 【${ship.name}】 已被敵方擊沉！`, 'sunk');
                }
            }
        } else {
            window.soundManager.playMiss();
            cell.classList.add('miss');
            this.logBattle('敵方砲火', `敵方砲彈落在 [${String.fromCharCode(65 + y)}${x + 1}]，未造成損害。`, 'miss');
        }

        const isAllSunk = this.myShips.every(s => s.positions.every(p => p.hit));

        // 回傳結果給開火方
        this.sendData('FIRE_RESULT', {
            x, y,
            hit: isHit,
            sunkShip: sunkShipName,
            allSunk: isAllSunk
        });

        if (isAllSunk) {
            this.endGame(false);
        } else {
            this.currentTurn = 'me';
            this.updateTurnBanner();
        }
    }

    /* ================= 單機模式下 AI 邏輯 ================= */
    processAiShotTarget(x, y) {
        let isHit = false;
        let sunkShipName = null;

        for (const ship of this.aiFleet) {
            const pos = ship.positions.find(p => p.x === x && p.y === y);
            if (pos) {
                isHit = true;
                pos.hit = true;
                if (ship.positions.every(p => p.hit)) {
                    sunkShipName = ship.name;
                }
                break;
            }
        }

        const isAllSunk = this.aiFleet.every(s => s.positions.every(p => p.hit));
        this.handleMyShotResult(x, y, isHit, sunkShipName, isAllSunk);
    }

    aiTakeTurn() {
        if (this.isGameOver || this.currentTurn !== 'opponent') return;

        let target = null;

        // 智慧獵殺演算法 (Hunt and Target)
        while (this.aiTargetQueue.length > 0) {
            const candidate = this.aiTargetQueue.shift();
            const cell = document.getElementById(`f-cell-${candidate.x}-${candidate.y}`);
            if (cell && !cell.classList.contains('hit') && !cell.classList.contains('miss')) {
                target = candidate;
                break;
            }
        }

        // 若隊列為空，採用隨機棋盤間隔射擊法
        if (!target) {
            const available = [];
            for (let y = 0; y < BOARD_SIZE; y++) {
                for (let x = 0; x < BOARD_SIZE; x++) {
                    const cell = document.getElementById(`f-cell-${x}-${y}`);
                    if (!cell.classList.contains('hit') && !cell.classList.contains('miss')) {
                        // 棋盤格權重 (x + y) % 2 === 0
                        available.push({ x, y, priority: (x + y) % 2 === 0 });
                    }
                }
            }

            if (available.length > 0) {
                const preferred = available.filter(c => c.priority);
                const pool = preferred.length > 0 ? preferred : available;
                target = pool[Math.floor(Math.random() * pool.length)];
            }
        }

        if (target) {
            window.soundManager.playCannon();
            setTimeout(() => {
                const cell = document.getElementById(`f-cell-${target.x}-${target.y}`);
                const shipId = this.myGrid[target.y][target.x];
                let isHit = false;

                if (shipId !== null) {
                    isHit = true;
                    window.soundManager.playHit();
                    cell.classList.add('hit');
                    this.logBattle('AI 砲火', `敵方 AI 擊中了 [${String.fromCharCode(65 + target.y)}${target.x + 1}]！💥`, 'hit');

                    // 將相鄰上下左右 4 格加入優先射擊隊列
                    const dirs = [{ dx: 0, dy: -1 }, { dx: 0, dy: 1 }, { dx: -1, dy: 0 }, { dx: 1, dy: 0 }];
                    dirs.forEach(d => {
                        const nx = target.x + d.dx;
                        const ny = target.y + d.dy;
                        if (nx >= 0 && nx < BOARD_SIZE && ny >= 0 && ny < BOARD_SIZE) {
                            this.aiTargetQueue.push({ x: nx, y: ny });
                        }
                    });

                    const ship = this.myShips.find(s => s.id === shipId);
                    if (ship) {
                        const pos = ship.positions.find(p => p.x === target.x && p.y === target.y);
                        if (pos) pos.hit = true;
                        if (ship.positions.every(p => p.hit)) {
                            window.soundManager.playSunk();
                            this.logBattle('警報', `我方 【${ship.name}】 已被敵方 AI 擊沉！`, 'sunk');
                        }
                    }
                } else {
                    window.soundManager.playMiss();
                    cell.classList.add('miss');
                    this.logBattle('AI 砲火', `敵方 AI 射擊 [${String.fromCharCode(65 + target.y)}${target.x + 1}]，未命中。`, 'miss');
                }

                const isAllSunk = this.myShips.every(s => s.positions.every(p => p.hit));
                if (isAllSunk) {
                    this.endGame(false);
                } else {
                    this.currentTurn = 'me';
                    this.updateTurnBanner();
                }
            }, 600);
        }
    }

    /* ================= 遊戲結算 (VICTORY / DEFEAT) ================= */
    endGame(isWinner) {
        this.isGameOver = true;
        const modal = document.getElementById('gameOverModal');
        const title = document.getElementById('modalTitle');
        const icon = document.getElementById('modalIcon');
        const stats = document.getElementById('modalStats');

        modal.classList.remove('hidden');

        const durationSeconds = Math.floor((Date.now() - this.startTime) / 1000);
        const accuracy = this.totalShots > 0 ? Math.round((this.totalHits / this.totalShots) * 100) : 0;

        if (isWinner) {
            window.soundManager.playVictory();
            icon.innerText = '🏆';
            title.className = 'modal-title victory';
            title.innerText = '全面大捷！敵方艦隊已全數沉沒';
            this.logBattle('總部通報', '恭喜指揮官，你以卓越的戰術徹底瓦解了敵方艦隊！', 'system');
        } else {
            window.soundManager.playDefeat();
            icon.innerText = '💀';
            title.className = 'modal-title defeat';
            title.innerText = '戰線崩潰！我方艦隊全體沉沒';
            this.logBattle('總部通報', '全艦沉沒，我們失去了這片海域的控制權...', 'sunk');
        }

        stats.innerHTML = `
            <div>總開火次數: <strong>${this.totalShots} 次</strong></div>
            <div>命中率: <strong>${accuracy}%</strong></div>
            <div>命中數: <strong>${this.totalHits} 發</strong></div>
            <div>交戰耗時: <strong>${durationSeconds} 秒</strong></div>
        `;
    }

    requestRematch() {
        window.soundManager.playClick();
        if (this.gameMode === 'solo-ai') {
            this.resetForRematch();
        } else {
            this.sendData('REMATCH_OFFER');
            this.showToast('已向對手發送重賽請求...');
            this.resetForRematch();
        }
    }

    resetForRematch() {
        document.getElementById('gameOverModal').classList.add('hidden');
        this.isMyReady = false;
        this.isOpponentReady = false;
        this.enemyGrid = this.createEmptyGrid();
        this.isGameOver = false;

        document.getElementById('btnConfirmReady').disabled = false;
        document.getElementById('btnRandomFleet').disabled = false;
        document.getElementById('btnResetFleet').disabled = false;

        if (this.gameMode === 'solo-ai') {
            this.setupAiFleet();
        }

        this.goToDeployment();
    }

    /* ================= 戰術通訊與日誌 ================= */
    logBattle(sender, msg, type = 'system') {
        const list = document.getElementById('combatLogList');
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        const time = new Date().toLocaleTimeString('zh-TW', { hour12: false });
        entry.innerHTML = `<span style="color:var(--text-dim)">[${time}]</span> <strong>${sender}:</strong> ${msg}`;
        list.appendChild(entry);
        list.scrollTop = list.scrollHeight;
    }

    sendChatMessage(customText) {
        const input = document.getElementById('chatInput');
        const text = customText || input.value.trim();
        if (!text) return;

        window.soundManager.playClick();
        this.displayChatMessage('我方', text);

        if (this.conn && this.conn.open) {
            this.sendData('CHAT_MSG', { sender: '敵方', text });
        } else if (this.gameMode === 'solo-ai') {
            // AI 自動回覆趣味訊息
            setTimeout(() => {
                const aiResponses = [
                    '計算中... 你的下一發砲彈軌跡已在掌握。',
                    '海象惡劣，建議你調整射角。',
                    '人類的戰術確實令人印象深刻。',
                    '警告：主砲冷卻完成，準備迎擊！'
                ];
                const reply = aiResponses[Math.floor(Math.random() * aiResponses.length)];
                this.displayChatMessage('智械 AI', reply);
            }, 800);
        }

        if (!customText) input.value = '';
    }

    displayChatMessage(sender, text) {
        this.logBattle(sender, text, 'chat');
    }
}

// 啟動遊戲
window.addEventListener('DOMContentLoaded', () => {
    window.game = new NavalGame();
});
