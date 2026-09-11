/**
 * Nonogram Main Application Controller
 * Orchestrates screens, gameplay input (mouse, touch, keyboard, drag with direction lock),
 * rendering, timer, hints, victory celebration, and confetti.
 */

class NonogramApp {
    constructor() {
        this.board = null;
        this.currentLevel = null;
        this.currentTool = "fill"; // "fill" (1), "cross" (-1), "question" (2), "erase" (0)
        this.timerInterval = null;
        this.timeElapsed = 0;
        this.currentZoom = 1;
        this.focusedCell = { r: 0, c: 0 };

        // Dragging state
        this.isDragging = false;
        this.dragButton = 0; // 0 for left, 2 for right
        this.dragStartPos = null;
        this.dragDirection = null; // null, "row", or "col"
        this.dragTargetVal = 0;
        this.currentBatchMoves = [];
        this.affectedCellsInStroke = new Set();

        // Confetti particles
        this.confettiAnimId = null;
        this.confettiParticles = [];

        this.settings = window.storageManager.getSettings();
        this.init();
    }

    init() {
        this.applyTheme(this.settings.theme);
        window.soundCtrl.setMuted(!this.settings.soundEnabled);
        window.soundCtrl.setVolume(this.settings.soundVolume ?? 0.6);
        const soundIcon = document.getElementById("sound-icon");
        if (soundIcon) soundIcon.textContent = this.settings.soundEnabled ? "🔊" : "🔇";

        this.bindGlobalEvents();
        this.initScreens();
        this.initEditor();
        this.initConverter();
        this.initTutorial();
        this.initSettingsModal();
        this.initRandomLevelModal();
        this.initPrintModal();

        // Check for active resume game
        this.checkActiveGameResume();
    }

    /* ===================================================================
       Theme & Sound Management
       =================================================================== */
    applyTheme(theme) {
        document.body.setAttribute("data-theme", theme);
        this.settings.theme = theme;
        window.storageManager.saveSettings(this.settings);
        const icon = document.getElementById("theme-icon");
        if (icon) {
            const icons = { dark: "🌑", light: "☀️", retro: "👾", cyber: "⚡" };
            icon.textContent = icons[theme] || "🎨";
        }
        const select = document.getElementById("setting-theme");
        if (select && select.value !== theme) select.value = theme;
    }

    cycleTheme() {
        const themes = ["dark", "light", "retro", "cyber"];
        const nextIdx = (themes.indexOf(this.settings.theme) + 1) % themes.length;
        this.applyTheme(themes[nextIdx]);
        window.soundCtrl.playButton();
    }

    /* ===================================================================
       Screen Navigation
       =================================================================== */
    switchScreen(screenName) {
        window.soundCtrl.playButton();
        document.querySelectorAll(".screen-panel").forEach(panel => {
            panel.classList.remove("active");
        });
        document.querySelectorAll(".nav-btn").forEach(btn => {
            btn.classList.remove("active");
            if (btn.dataset.screen === screenName) btn.classList.add("active");
        });

        const target = document.getElementById(`screen-${screenName}`);
        if (target) {
            target.classList.add("active");
        }

        if (screenName === "levels") {
            this.renderLevelList();
            this.checkActiveGameResume();
            this.stopTimer();
        } else if (screenName === "editor") {
            this.renderEditorBoard();
        }
    }

    /* ===================================================================
       Level Selection Screen
       =================================================================== */
    renderLevelList(filterCategory = "all") {
        const container = document.getElementById("level-cards-container");
        if (!container) return;
        container.innerHTML = "";

        const progress = window.storageManager.getProgress();
        const customLevels = window.storageManager.getCustomLevels();
        const allLevels = [...window.PUZZLE_LEVELS, ...customLevels];

        const filtered = allLevels.filter(lvl => {
            if (filterCategory === "all") return true;
            if (filterCategory === "custom") return lvl.isCustom;
            return lvl.category === filterCategory;
        });

        if (filtered.length === 0) {
            container.innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">
                    此分類下尚無關卡。可前往「自製關卡」或「圖片轉數織」新增專屬關卡！
                </div>
            `;
            return;
        }

        filtered.forEach(lvl => {
            const record = progress[lvl.id] || {};
            const isCompleted = record.completed || false;
            const stars = record.stars || 0;
            const starsText = "⭐".repeat(stars) || (isCompleted ? "⭐" : "☆☆☆");

            const card = document.createElement("div");
            card.className = `level-card ${isCompleted ? "completed" : ""}`;
            card.innerHTML = `
                <div class="card-top">
                    <div class="card-title-group">
                        <h3>${lvl.title}</h3>
                        <div class="card-tags">
                            <span class="badge">${lvl.category}</span>
                            <span class="badge" style="background: var(--bg-surface-elevated); color: var(--text-muted); border-color: var(--border-color);">${lvl.difficulty || "普通"}</span>
                        </div>
                    </div>
                    ${isCompleted ? '<div class="card-complete-badge" title="已通關">✓</div>' : ''}
                </div>
                <div class="card-bottom">
                    <span class="card-record">${record.bestTime ? `最佳: ${this.formatTime(record.bestTime)}` : "尚未挑戰"}</span>
                    <span class="card-stars">${starsText}</span>
                </div>
            `;

            card.addEventListener("click", () => {
                this.startLevel(lvl);
            });

            container.appendChild(card);
        });
    }

    checkActiveGameResume() {
        const banner = document.getElementById("resume-banner");
        const active = window.storageManager.getActiveGame();
        if (!banner) return;

        if (active && active.levelId && !active.isCompleted) {
            const allLevels = [...window.PUZZLE_LEVELS, ...window.storageManager.getCustomLevels()];
            const lvl = allLevels.find(l => l.id === active.levelId);
            if (lvl) {
                document.getElementById("resume-title").textContent = lvl.title;
                document.getElementById("resume-time").textContent = `已進行 ${this.formatTime(active.timeElapsed || 0)}`;
                banner.classList.remove("hidden");

                document.getElementById("btn-resume-game").onclick = () => {
                    this.startLevel(lvl, active);
                };
                document.getElementById("btn-discard-game").onclick = () => {
                    window.storageManager.clearActiveGame();
                    banner.classList.add("hidden");
                };
                return;
            }
        }
        banner.classList.add("hidden");
    }

    /* ===================================================================
       Game Board Setup & Rendering
       =================================================================== */
    startLevel(levelData, savedState = null) {
        this.currentLevel = levelData;
        this.board = new NonogramBoard(levelData);

        if (savedState) {
            this.board.deserialize(savedState);
            this.timeElapsed = savedState.timeElapsed || 0;
        } else {
            this.timeElapsed = 0;
        }

        this.currentZoom = 1;
        this.updateZoomDisplay();

        // Update top bar labels
        document.getElementById("current-puzzle-title").textContent = levelData.title;
        document.getElementById("current-puzzle-badge").textContent = `${levelData.width}x${levelData.height} ${levelData.difficulty || ""}`;

        // Reset hint toast
        const hintToast = document.getElementById("hint-toast");
        if (hintToast) hintToast.classList.add("hidden");

        this.renderBoard();
        this.updateMistakesDisplay();
        this.updateProgressDisplay();
        this.updateUndoRedoButtons();

        // Start timer
        this.startTimer();

        // Switch screen to game
        this.switchScreen("game");
    }

    renderBoard() {
        const boardWrapper = document.getElementById("board-wrapper");
        const colCluesElem = document.getElementById("col-clues");
        const rowCluesElem = document.getElementById("row-clues");
        const gridElem = document.getElementById("nonogram-grid");
        const cornerElem = document.getElementById("clue-corner");

        if (!boardWrapper || !this.board) return;

        const width = this.board.width;
        const height = this.board.height;

        // Calculate dynamic cell sizing
        let cellSize = 36;
        if (width <= 5) cellSize = 48;
        else if (width <= 10) cellSize = 36;
        else if (width <= 15) cellSize = 28;
        else cellSize = 22;

        // Determine max clues in any row or column to calculate padding
        const maxColClues = Math.max(...this.board.colClues.map(c => c.length));
        const maxRowClues = Math.max(...this.board.rowClues.map(r => r.length));

        // Setup CSS Grid templates on wrapper
        boardWrapper.style.gridTemplateColumns = `auto repeat(${width}, ${cellSize}px)`;
        boardWrapper.style.gridTemplateRows = `auto repeat(${height}, ${cellSize}px)`;

        // Setup corner spacer
        cornerElem.style.gridColumn = "1 / 2";
        cornerElem.style.gridRow = "1 / 2";

        // Setup Column Clues container
        colCluesElem.style.gridColumn = `2 / ${width + 2}`;
        colCluesElem.style.gridRow = "1 / 2";
        colCluesElem.style.gridTemplateColumns = `repeat(${width}, ${cellSize}px)`;
        colCluesElem.innerHTML = "";

        for (let c = 0; c < width; c++) {
            const colItem = document.createElement("div");
            colItem.className = `col-clue-item col-${c} ${(c + 1) % 5 === 0 && c < width - 1 ? "border-5" : ""}`;
            if (this.board.colSatisfied[c]) colItem.classList.add("satisfied");

            const clues = this.board.colClues[c];
            clues.forEach((num, idx) => {
                const numSpan = document.createElement("span");
                numSpan.className = `clue-num ${this.board.isClueStruck('c', c, idx) ? "struck" : ""}`;
                numSpan.textContent = num;
                numSpan.addEventListener("click", (e) => {
                    e.stopPropagation();
                    const struck = this.board.toggleClue('c', c, idx);
                    numSpan.classList.toggle("struck", struck);
                    window.soundCtrl.playClueClick();
                    this.saveActiveGameDebounced();
                });
                colItem.appendChild(numSpan);
            });

            colCluesElem.appendChild(colItem);
        }

        // Setup Row Clues container
        rowCluesElem.style.gridColumn = "1 / 2";
        rowCluesElem.style.gridRow = `2 / ${height + 2}`;
        rowCluesElem.style.gridTemplateRows = `repeat(${height}, ${cellSize}px)`;
        rowCluesElem.innerHTML = "";

        for (let r = 0; r < height; r++) {
            const rowItem = document.createElement("div");
            rowItem.className = `row-clue-item row-${r} ${(r + 1) % 5 === 0 && r < height - 1 ? "border-5" : ""}`;
            if (this.board.rowSatisfied[r]) rowItem.classList.add("satisfied");

            const clues = this.board.rowClues[r];
            clues.forEach((num, idx) => {
                const numSpan = document.createElement("span");
                numSpan.className = `clue-num ${this.board.isClueStruck('r', r, idx) ? "struck" : ""}`;
                numSpan.textContent = num;
                numSpan.addEventListener("click", (e) => {
                    e.stopPropagation();
                    const struck = this.board.toggleClue('r', r, idx);
                    numSpan.classList.toggle("struck", struck);
                    window.soundCtrl.playClueClick();
                    this.saveActiveGameDebounced();
                });
                rowItem.appendChild(numSpan);
            });

            rowCluesElem.appendChild(rowItem);
        }

        // Setup Nonogram Grid container
        gridElem.style.gridColumn = `2 / ${width + 2}`;
        gridElem.style.gridRow = `2 / ${height + 2}`;
        gridElem.style.gridTemplateColumns = `repeat(${width}, ${cellSize}px)`;
        gridElem.style.gridTemplateRows = `repeat(${height}, ${cellSize}px)`;
        gridElem.innerHTML = "";

        // Build grid cells
        for (let r = 0; r < height; r++) {
            for (let c = 0; c < width; c++) {
                const cell = document.createElement("div");
                cell.className = "grid-cell";
                cell.dataset.r = r;
                cell.dataset.c = c;

                if ((c + 1) % 5 === 0 && c < width - 1) cell.classList.add("border-r-5");
                if ((r + 1) % 5 === 0 && r < height - 1) cell.classList.add("border-b-5");

                const val = this.board.getCell(r, c);
                if (val === 1) cell.classList.add("state-fill");
                else if (val === -1) cell.classList.add("state-cross");
                else if (val === 2) cell.classList.add("state-question");

                gridElem.appendChild(cell);
            }
        }
    }

    /* ===================================================================
       Mouse & Touch Interaction with Direction Locking
       =================================================================== */
    bindGlobalEvents() {
        // Globally disable right-click context menu across the entire application
        window.addEventListener("contextmenu", (e) => {
            e.preventDefault();
            return false;
        }, { capture: true });
        document.addEventListener("contextmenu", (e) => {
            e.preventDefault();
            return false;
        }, { capture: true });

        // Navigation Buttons
        document.querySelectorAll(".nav-btn[data-screen]").forEach(btn => {
            btn.addEventListener("click", () => this.switchScreen(btn.dataset.screen));
        });

        // Header controls
        document.getElementById("btn-logo-home")?.addEventListener("click", () => this.switchScreen("levels"));
        document.getElementById("btn-theme-toggle")?.addEventListener("click", () => this.cycleTheme());
        document.getElementById("btn-sound-toggle")?.addEventListener("click", () => {
            this.settings.soundEnabled = !this.settings.soundEnabled;
            window.soundCtrl.setMuted(!this.settings.soundEnabled);
            const icon = document.getElementById("sound-icon");
            if (icon) icon.textContent = this.settings.soundEnabled ? "🔊" : "🔇";
            window.storageManager.saveSettings(this.settings);
            const soundCheck = document.getElementById("setting-sound");
            if (soundCheck) soundCheck.checked = this.settings.soundEnabled;
        });

        // Level Filter tabs
        document.querySelectorAll(".filter-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                this.renderLevelList(btn.dataset.category);
            });
        });

        // In-game topbar buttons
        document.getElementById("btn-back-to-levels")?.addEventListener("click", () => this.switchScreen("levels"));
        document.getElementById("btn-undo")?.addEventListener("click", () => this.handleUndo());
        document.getElementById("btn-redo")?.addEventListener("click", () => this.handleRedo());
        document.getElementById("btn-hint")?.addEventListener("click", () => this.requestHint());
        document.getElementById("btn-restart")?.addEventListener("click", () => {
            if (confirm("確定要重新開始本關嗎？所有目前進度將被重置。")) {
                this.startLevel(this.currentLevel);
            }
        });
        document.getElementById("btn-close-hint")?.addEventListener("click", () => {
            document.getElementById("hint-toast")?.classList.add("hidden");
        });

        // In-game bottom tool selection buttons
        document.querySelectorAll(".tool-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".tool-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                this.currentTool = btn.dataset.tool;
                window.soundCtrl.playButton();
            });
        });

        // Zoom controls
        document.getElementById("btn-zoom-in")?.addEventListener("click", () => this.adjustZoom(0.15));
        document.getElementById("btn-zoom-out")?.addEventListener("click", () => this.adjustZoom(-0.15));
        document.getElementById("btn-zoom-reset")?.addEventListener("click", () => this.resetZoom());

        // Victory modal buttons
        document.getElementById("btn-next-level")?.addEventListener("click", () => this.goToNextLevel());
        document.getElementById("btn-replay-level")?.addEventListener("click", () => {
            document.getElementById("modal-victory")?.classList.add("hidden");
            this.stopConfetti();
            this.startLevel(this.currentLevel);
        });
        document.getElementById("btn-victory-back")?.addEventListener("click", () => {
            document.getElementById("modal-victory")?.classList.add("hidden");
            this.stopConfetti();
            this.switchScreen("levels");
        });

        // Grid Pointer & Drag Events
        const gridElem = document.getElementById("nonogram-grid");
        if (gridElem) {
            gridElem.addEventListener("contextmenu", (e) => e.preventDefault());

            gridElem.addEventListener("mousedown", (e) => this.onGridMouseDown(e));
            window.addEventListener("mousemove", (e) => this.onGridMouseMove(e));
            window.addEventListener("mouseup", (e) => this.onGridMouseUp(e));

            // Touch events
            gridElem.addEventListener("touchstart", (e) => this.onTouchStart(e), { passive: false });
            gridElem.addEventListener("touchmove", (e) => this.onTouchMove(e), { passive: false });
            gridElem.addEventListener("touchend", (e) => this.onTouchEnd(e));
        }

        // Crosshair hover events on board
        const boardWrapper = document.getElementById("board-wrapper");
        if (boardWrapper) {
            boardWrapper.addEventListener("mouseover", (e) => this.onCellHover(e));
            boardWrapper.addEventListener("mouseleave", () => this.clearCrosshair());
        }

        // Keyboard navigation & shortcuts
        window.addEventListener("keydown", (e) => this.onKeyDown(e));
    }

    onCellHover(e) {
        if (!this.settings.highlightCurrentLine) return;
        const cell = e.target.closest(".grid-cell");
        if (!cell) {
            this.clearCrosshair();
            return;
        }

        const r = parseInt(cell.dataset.r, 10);
        const c = parseInt(cell.dataset.c, 10);
        this.setCrosshair(r, c);
    }

    setCrosshair(r, c) {
        this.clearCrosshair();
        if (!this.settings.highlightCurrentLine) return;

        document.querySelector(`.row-${r}`)?.classList.add("highlight-line");
        document.querySelector(`.col-${c}`)?.classList.add("highlight-line");

        document.querySelectorAll(`.grid-cell[data-r="${r}"]`).forEach(el => el.classList.add("highlight-line"));
        document.querySelectorAll(`.grid-cell[data-c="${c}"]`).forEach(el => el.classList.add("highlight-line"));
    }

    clearCrosshair() {
        document.querySelectorAll(".highlight-line").forEach(el => el.classList.remove("highlight-line"));
    }

    /* ===================================================================
       Drag Action Engine with Direction Locking
       =================================================================== */
    onGridMouseDown(e) {
        if (!this.board || this.board.isCompleted) return;
        const cell = e.target.closest(".grid-cell");
        if (!cell) return;

        const r = parseInt(cell.dataset.r, 10);
        const c = parseInt(cell.dataset.c, 10);

        this.isDragging = true;
        this.dragButton = e.button; // 0 = Left, 2 = Right
        this.dragStartPos = { r, c };
        this.dragDirection = null;
        this.currentBatchMoves = [];
        this.affectedCellsInStroke.clear();

        // Determine target value for this stroke
        const currentVal = this.board.getCell(r, c);
        if (e.button === 2) {
            // Right click: always cross or toggle cross off
            this.dragTargetVal = currentVal === -1 ? 0 : -1;
        } else {
            // Left click: follow selected tool
            if (this.currentTool === "fill") {
                this.dragTargetVal = currentVal === 1 ? 0 : 1;
            } else if (this.currentTool === "cross") {
                this.dragTargetVal = currentVal === -1 ? 0 : -1;
            } else if (this.currentTool === "question") {
                this.dragTargetVal = currentVal === 2 ? 0 : 2;
            } else if (this.currentTool === "erase") {
                this.dragTargetVal = 0;
            }
        }

        this.applyCellChange(r, c, this.dragTargetVal);
    }

    onGridMouseMove(e) {
        if (!this.isDragging || !this.board || this.board.isCompleted) return;

        // Find cell under mouse point
        const elem = document.elementFromPoint(e.clientX, e.clientY);
        const cell = elem ? elem.closest(".grid-cell") : null;
        if (!cell) return;

        let r = parseInt(cell.dataset.r, 10);
        let c = parseInt(cell.dataset.c, 10);

        // Direction locking with continuous line interpolation
        if (this.settings.dragDirectionLock && this.dragStartPos) {
            const startR = this.dragStartPos.r;
            const startC = this.dragStartPos.c;

            if (!this.dragDirection) {
                const diffR = Math.abs(r - startR);
                const diffC = Math.abs(c - startC);
                if (diffR > 0 || diffC > 0) {
                    this.dragDirection = diffR >= diffC ? "col" : "row";
                }
            }

            if (this.dragDirection === "col") {
                const minR = Math.min(startR, r);
                const maxR = Math.max(startR, r);
                for (let currR = minR; currR <= maxR; currR++) {
                    this.applyCellChange(currR, startC, this.dragTargetVal);
                }
                return;
            } else if (this.dragDirection === "row") {
                const minC = Math.min(startC, c);
                const maxC = Math.max(startC, c);
                for (let currC = minC; currC <= maxC; currC++) {
                    this.applyCellChange(startR, currC, this.dragTargetVal);
                }
                return;
            }
        }

        // Free dragging (direction lock OFF)
        this.applyCellChange(r, c, this.dragTargetVal);
    }

    onGridMouseUp(e) {
        if (!this.isDragging) return;
        this.isDragging = false;
        this.dragStartPos = null;
        this.dragDirection = null;

        if (this.currentBatchMoves.length > 0) {
            this.board.commitMove(this.currentBatchMoves);
            this.currentBatchMoves = [];
            this.afterMoveMade();
        }
    }

    onTouchStart(e) {
        if (!this.board || this.board.isCompleted) return;
        const touch = e.touches[0];
        const elem = document.elementFromPoint(touch.clientX, touch.clientY);
        const cell = elem ? elem.closest(".grid-cell") : null;
        if (!cell) return;

        e.preventDefault();
        const r = parseInt(cell.dataset.r, 10);
        const c = parseInt(cell.dataset.c, 10);

        this.isDragging = true;
        this.dragButton = 0;
        this.dragStartPos = { r, c };
        this.dragDirection = null;
        this.currentBatchMoves = [];
        this.affectedCellsInStroke.clear();

        const currentVal = this.board.getCell(r, c);
        if (this.currentTool === "fill") {
            this.dragTargetVal = currentVal === 1 ? 0 : 1;
        } else if (this.currentTool === "cross") {
            this.dragTargetVal = currentVal === -1 ? 0 : -1;
        } else if (this.currentTool === "question") {
            this.dragTargetVal = currentVal === 2 ? 0 : 2;
        } else {
            this.dragTargetVal = 0;
        }

        this.applyCellChange(r, c, this.dragTargetVal);
    }

    onTouchMove(e) {
        if (!this.isDragging || !this.board) return;
        e.preventDefault();
        const touch = e.touches[0];
        const elem = document.elementFromPoint(touch.clientX, touch.clientY);
        const cell = elem ? elem.closest(".grid-cell") : null;
        if (!cell) return;

        let r = parseInt(cell.dataset.r, 10);
        let c = parseInt(cell.dataset.c, 10);

        if (this.settings.dragDirectionLock && this.dragStartPos) {
            const startR = this.dragStartPos.r;
            const startC = this.dragStartPos.c;

            if (!this.dragDirection) {
                const diffR = Math.abs(r - startR);
                const diffC = Math.abs(c - startC);
                if (diffR > 0 || diffC > 0) {
                    this.dragDirection = diffR >= diffC ? "col" : "row";
                }
            }

            if (this.dragDirection === "col") {
                const minR = Math.min(startR, r);
                const maxR = Math.max(startR, r);
                for (let currR = minR; currR <= maxR; currR++) {
                    this.applyCellChange(currR, startC, this.dragTargetVal);
                }
                return;
            } else if (this.dragDirection === "row") {
                const minC = Math.min(startC, c);
                const maxC = Math.max(startC, c);
                for (let currC = minC; currC <= maxC; currC++) {
                    this.applyCellChange(startR, currC, this.dragTargetVal);
                }
                return;
            }
        }

        // Free dragging (direction lock OFF)
        this.applyCellChange(r, c, this.dragTargetVal);
    }

    onTouchEnd(e) {
        this.onGridMouseUp(e);
    }

    applyCellChange(r, c, targetVal) {
        const key = `${r},${c}`;
        if (this.affectedCellsInStroke.has(key)) return;

        const prevVal = this.board.getCell(r, c);
        if (prevVal === targetVal) return;

        // In Strict Mode: if user tries to FILL a cell that should NOT be filled:
        if (this.settings.strictMistakes && targetVal === 1 && this.board.solution && this.board.solution[r][c] === 0) {
            this.handleMistake(r, c);
            targetVal = -1; // Auto-mark as cross to penalize and correct
        }

        // Apply to board
        this.board.setCell(r, c, targetVal);
        this.affectedCellsInStroke.add(key);
        this.currentBatchMoves.push({ r, c, prevVal, newVal: targetVal });

        // Update DOM element visually
        this.updateCellDOM(r, c, targetVal);

        // Play appropriate sound
        if (targetVal === 1) {
            window.soundCtrl.playFill();
        } else if (targetVal === -1) {
            window.soundCtrl.playCross();
        } else if (targetVal === 0) {
            window.soundCtrl.playErase();
        }
    }

    updateCellDOM(r, c, val) {
        const cell = document.querySelector(`.grid-cell[data-r="${r}"][data-c="${c}"]`);
        if (!cell) return;

        cell.classList.remove("state-fill", "state-cross", "state-question", "hint-glow");
        if (val === 1) cell.classList.add("state-fill");
        else if (val === -1) cell.classList.add("state-cross");
        else if (val === 2) cell.classList.add("state-question");
    }

    /* ===================================================================
       Mistakes & Game Over Handling
       =================================================================== */
    handleMistake(r, c) {
        this.board.mistakesCount++;
        this.updateMistakesDisplay();
        window.soundCtrl.playMistake();

        const cell = document.querySelector(`.grid-cell[data-r="${r}"][data-c="${c}"]`);
        if (cell) {
            cell.classList.add("mistake-flash");
            setTimeout(() => cell.classList.remove("mistake-flash"), 400);
        }

        if (this.settings.strictMistakes && this.board.mistakesCount >= 3) {
            setTimeout(() => {
                alert("💔 挑戰失敗！累計失誤已達 3 次。按確定重新開始本關。");
                this.startLevel(this.currentLevel);
            }, 300);
        }
    }

    updateMistakesDisplay() {
        const valElem = document.getElementById("game-mistakes");
        const iconElem = document.getElementById("mistake-icon");
        if (!valElem || !this.board) return;

        if (this.settings.strictMistakes) {
            const lives = Math.max(0, 3 - this.board.mistakesCount);
            iconElem.textContent = "❤️";
            valElem.textContent = `${lives} / 3`;
            valElem.title = `嚴格模式：剩餘 ${lives} 顆心，3 次失誤失敗`;
        } else {
            iconElem.textContent = "✨";
            valElem.textContent = "休閒模式";
            valElem.title = "休閒模式：自由推導，無失誤懲罰";
        }
    }

    processAutoCross(newly) {
        if (!this.settings.autoCrossCompleted || !this.board || this.board.isCompleted) return;

        let pendingRows = [...(newly?.newRows || [])];
        let pendingCols = [...(newly?.newCols || [])];
        const allAutoCrossMoves = [];

        while (pendingRows.length > 0 || pendingCols.length > 0) {
            const batchMoves = [];
            pendingRows.forEach(r => {
                const changes = this.board.autoCrossRow(r);
                changes.forEach(ch => {
                    batchMoves.push(ch);
                    this.updateCellDOM(ch.r, ch.c, -1);
                });
            });
            pendingCols.forEach(c => {
                const changes = this.board.autoCrossCol(c);
                changes.forEach(ch => {
                    batchMoves.push(ch);
                    this.updateCellDOM(ch.r, ch.c, -1);
                });
            });

            pendingRows = [];
            pendingCols = [];

            if (batchMoves.length > 0) {
                allAutoCrossMoves.push(...batchMoves);
                const cascade = this.board.updateLineStatus();
                pendingRows.push(...cascade.newRows);
                pendingCols.push(...cascade.newCols);
            }
        }

        if (allAutoCrossMoves.length > 0) {
            this.board.commitMove(allAutoCrossMoves);
        }
    }

    updateLineSatisfiedStyles() {
        if (!this.board) return;
        for (let r = 0; r < this.board.height; r++) {
            const rowElem = document.querySelector(`.row-${r}`);
            if (rowElem) rowElem.classList.toggle("satisfied", !!this.board.rowSatisfied[r]);
        }
        for (let c = 0; c < this.board.width; c++) {
            const colElem = document.querySelector(`.col-${c}`);
            if (colElem) colElem.classList.toggle("satisfied", !!this.board.colSatisfied[c]);
        }
    }

    /* ===================================================================
       After Move Flow: Auto-cross, Victory, Auto-save
       =================================================================== */
    afterMoveMade() {
        // Check satisfied lines
        const newly = this.board.updateLineStatus();

        if (newly.newRows.length > 0 || newly.newCols.length > 0) {
            window.soundCtrl.playLineComplete();
            this.processAutoCross(newly);
        }

        this.updateLineSatisfiedStyles();
        this.updateProgressDisplay();
        this.updateUndoRedoButtons();
        this.saveActiveGameDebounced();

        // Check Victory Condition
        if (this.board.checkVictory()) {
            this.handleVictory();
        }
    }

    updateProgressDisplay() {
        const progElem = document.getElementById("game-progress");
        if (!progElem || !this.board) return;
        const prog = this.board.getProgress();
        progElem.textContent = `${prog.percent}%`;
    }

    updateUndoRedoButtons() {
        const undoBtn = document.getElementById("btn-undo");
        const redoBtn = document.getElementById("btn-redo");
        if (undoBtn) undoBtn.disabled = !this.board || this.board.undoStack.length === 0;
        if (redoBtn) redoBtn.disabled = !this.board || this.board.redoStack.length === 0;
    }

    handleUndo() {
        if (!this.board) return;
        const changes = this.board.undo();
        if (changes) {
            changes.forEach(ch => this.updateCellDOM(ch.r, ch.c, ch.newVal));
            this.afterMoveMade();
            window.soundCtrl.playButton();
        }
    }

    handleRedo() {
        if (!this.board) return;
        const changes = this.board.redo();
        if (changes) {
            changes.forEach(ch => this.updateCellDOM(ch.r, ch.c, ch.newVal));
            this.afterMoveMade();
            window.soundCtrl.playButton();
        }
    }

    /* ===================================================================
       Victory Celebration & Pixel Art Reveal
       =================================================================== */
    handleVictory() {
        this.stopTimer();
        window.soundCtrl.playVictory();
        window.storageManager.clearActiveGame();

        // Calculate stars
        let stars = 3;
        if (this.board.mistakesCount > 3) stars = 1;
        else if (this.board.mistakesCount > 1) stars = 2;

        window.storageManager.saveLevelRecord(this.board.level.id, {
            time: this.timeElapsed,
            stars,
            mistakes: this.board.mistakesCount
        });

        // Setup Victory Modal
        document.getElementById("victory-level-title").textContent = this.currentLevel.title;
        document.getElementById("victory-time").textContent = this.formatTime(this.timeElapsed);
        document.getElementById("victory-stars").textContent = "⭐".repeat(stars);
        document.getElementById("victory-mistakes").textContent = this.board.mistakesCount;

        // Render Colored Pixel Art Canvas
        this.renderVictoryPixelArt();

        // Launch Confetti
        this.startConfetti();

        // Open modal
        const modal = document.getElementById("modal-victory");
        if (modal) modal.classList.remove("hidden");
    }

    renderVictoryPixelArt() {
        const artContainer = document.getElementById("victory-art-canvas");
        if (!artContainer) return;
        artContainer.innerHTML = "";

        const width = this.board.width;
        const height = this.board.height;
        const colors = this.board.colors;

        // Size each pixel to fit nicely in 240px container
        const pixelSize = Math.max(8, Math.min(24, Math.floor(240 / Math.max(width, height))));

        artContainer.style.gridTemplateColumns = `repeat(${width}, ${pixelSize}px)`;
        artContainer.style.gridTemplateRows = `repeat(${height}, ${pixelSize}px)`;

        for (let r = 0; r < height; r++) {
            for (let c = 0; c < width; c++) {
                const pixel = document.createElement("div");
                pixel.className = "art-pixel";
                const isFilled = this.board.solution[r][c] === 1;

                if (isFilled) {
                    const colorHex = (colors && colors[r] && colors[r][c]) ? colors[r][c] : "var(--primary)";
                    pixel.style.backgroundColor = colorHex;
                } else {
                    pixel.style.backgroundColor = "transparent";
                }
                artContainer.appendChild(pixel);
            }
        }
    }

    goToNextLevel() {
        document.getElementById("modal-victory")?.classList.add("hidden");
        this.stopConfetti();

        const all = [...window.PUZZLE_LEVELS, ...window.storageManager.getCustomLevels()];
        const currentIdx = all.findIndex(lvl => lvl.id === this.currentLevel.id);
        if (currentIdx >= 0 && currentIdx + 1 < all.length) {
            this.startLevel(all[currentIdx + 1]);
        } else {
            alert("🎉 太強了！您已通關此列表的所有關卡！");
            this.switchScreen("levels");
        }
    }

    /* ===================================================================
       Hints & Logic Solver Integration
       =================================================================== */
    requestHint() {
        if (!this.board || this.board.isCompleted) return;

        const hint = window.NonogramSolver.findHint(
            this.board.grid,
            this.board.rowClues,
            this.board.colClues,
            this.board.solution
        );

        if (!hint) {
            this.showHintToast("目前沒有找到更多推導線索，或是所有線索皆已完成！");
            return;
        }

        window.soundCtrl.playHint();
        this.showHintToast(hint.message);

        // Highlight target cell with glowing animation
        document.querySelectorAll(".hint-glow").forEach(el => el.classList.remove("hint-glow"));
        const targetCell = document.querySelector(`.grid-cell[data-r="${hint.row}"][data-c="${hint.col}"]`);
        if (targetCell) {
            targetCell.classList.add("hint-glow");
            targetCell.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
        }
    }

    showHintToast(msg) {
        const toast = document.getElementById("hint-toast");
        const text = document.getElementById("hint-text");
        if (toast && text) {
            text.textContent = msg;
            toast.classList.remove("hidden");
        }
    }

    /* ===================================================================
       Timer & Auto-Save
       =================================================================== */
    startTimer() {
        this.stopTimer();
        this.updateTimerDisplay();
        this.timerInterval = setInterval(() => {
            this.timeElapsed++;
            this.updateTimerDisplay();
            if (this.board) this.board.timeElapsed = this.timeElapsed;
        }, 1000);
    }

    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    updateTimerDisplay() {
        const timerElem = document.getElementById("game-timer");
        if (timerElem) timerElem.textContent = this.formatTime(this.timeElapsed);
    }

    formatTime(sec) {
        const m = Math.floor(sec / 60).toString().padStart(2, "0");
        const s = (sec % 60).toString().padStart(2, "0");
        return `${m}:${s}`;
    }

    saveActiveGameDebounced() {
        if (!this.board || this.board.isCompleted) return;
        window.storageManager.saveActiveGame(this.board.serialize());
    }

    /* ===================================================================
       Zoom Controls
       =================================================================== */
    adjustZoom(delta) {
        this.currentZoom = Math.max(0.6, Math.min(2.0, this.currentZoom + delta));
        this.updateZoomDisplay();
    }

    resetZoom() {
        this.currentZoom = 1;
        this.updateZoomDisplay();
    }

    updateZoomDisplay() {
        const boardWrapper = document.getElementById("board-wrapper");
        const zoomText = document.getElementById("zoom-level");
        if (boardWrapper) boardWrapper.style.transform = `scale(${this.currentZoom})`;
        if (zoomText) zoomText.textContent = `${Math.round(this.currentZoom * 100)}%`;
    }

    /* ===================================================================
       Keyboard Shortcuts
       =================================================================== */
    onKeyDown(e) {
        // Escape closes any open modal
        if (e.key === "Escape") {
            document.querySelectorAll(".modal-overlay").forEach(m => m.classList.add("hidden"));
            return;
        }

        // Ignore if user is typing in an input or textarea
        if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;

        // Undo / Redo
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
            e.preventDefault();
            if (e.shiftKey) this.handleRedo();
            else this.handleUndo();
            return;
        }
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
            e.preventDefault();
            this.handleRedo();
            return;
        }

        // Hint (H)
        if (e.key.toLowerCase() === "h") {
            this.requestHint();
            return;
        }

        // Tool switching
        if (e.key.toLowerCase() === "z" || e.code === "Space") {
            e.preventDefault();
            this.selectTool("fill");
            this.applyToolToFocusedCell();
        } else if (e.key.toLowerCase() === "x") {
            e.preventDefault();
            this.selectTool("cross");
            this.applyToolToFocusedCell();
        } else if (e.key.toLowerCase() === "c") {
            e.preventDefault();
            this.selectTool("question");
            this.applyToolToFocusedCell();
        } else if (e.key.toLowerCase() === "e" || e.key === "Delete" || e.key === "Backspace") {
            e.preventDefault();
            this.selectTool("erase");
            this.applyToolToFocusedCell();
        }

        // WASD / Arrow keys for cursor navigation
        if (this.board && ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "KeyW", "KeyS", "KeyA", "KeyD"].includes(e.code)) {
            e.preventDefault();
            let { r, c } = this.focusedCell;
            if (e.code === "ArrowUp" || e.code === "KeyW") r = Math.max(0, r - 1);
            if (e.code === "ArrowDown" || e.code === "KeyS") r = Math.min(this.board.height - 1, r + 1);
            if (e.code === "ArrowLeft" || e.code === "KeyA") c = Math.max(0, c - 1);
            if (e.code === "ArrowRight" || e.code === "KeyD") c = Math.min(this.board.width - 1, c + 1);

            this.focusedCell = { r, c };
            this.setCrosshair(r, c);
        }
    }

    selectTool(tool) {
        this.currentTool = tool;
        document.querySelectorAll(".tool-btn").forEach(b => {
            b.classList.toggle("active", b.dataset.tool === tool);
        });
    }

    applyToolToFocusedCell() {
        if (!this.board || this.board.isCompleted) return;
        const { r, c } = this.focusedCell;
        let targetVal = 0;
        const currentVal = this.board.getCell(r, c);

        if (this.currentTool === "fill") targetVal = currentVal === 1 ? 0 : 1;
        else if (this.currentTool === "cross") targetVal = currentVal === -1 ? 0 : -1;
        else if (this.currentTool === "question") targetVal = currentVal === 2 ? 0 : 2;
        else targetVal = 0;

        this.applyCellChange(r, c, targetVal);
        this.board.commitMove([{ r, c, prevVal: currentVal, newVal: targetVal }]);
        this.afterMoveMade();
    }

    /* ===================================================================
       Confetti Particle Engine
       =================================================================== */
    startConfetti() {
        const canvas = document.getElementById("confetti-canvas");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        const colors = ["#ff3366", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#00f0ff"];
        this.confettiParticles = [];

        for (let i = 0; i < 120; i++) {
            this.confettiParticles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height - canvas.height,
                w: Math.random() * 10 + 6,
                h: Math.random() * 8 + 4,
                color: colors[Math.floor(Math.random() * colors.length)],
                vx: (Math.random() - 0.5) * 3,
                vy: Math.random() * 4 + 2,
                rot: Math.random() * 360,
                vrot: (Math.random() - 0.5) * 8
            });
        }

        const render = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            this.confettiParticles.forEach(p => {
                p.x += p.vx;
                p.y += p.vy;
                p.rot += p.vrot;

                if (p.y > canvas.height) {
                    p.y = -20;
                    p.x = Math.random() * canvas.width;
                }

                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate((p.rot * Math.PI) / 180);
                ctx.fillStyle = p.color;
                ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
                ctx.restore();
            });

            this.confettiAnimId = requestAnimationFrame(render);
        };

        if (this.confettiAnimId) cancelAnimationFrame(this.confettiAnimId);
        render();
    }

    stopConfetti() {
        if (this.confettiAnimId) {
            cancelAnimationFrame(this.confettiAnimId);
            this.confettiAnimId = null;
        }
        const canvas = document.getElementById("confetti-canvas");
        if (canvas) {
            const ctx = canvas.getContext("2d");
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
    }

    /* ===================================================================
       Level Editor Controller
       =================================================================== */
    initEditor() {
        const sizeSelect = document.getElementById("editor-size-select");
        sizeSelect?.addEventListener("change", (e) => {
            window.levelEditor.setSize(parseInt(e.target.value, 10));
            this.renderEditorBoard();
        });

        // Palette colors
        document.querySelectorAll(".palette-color").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".palette-color").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                window.levelEditor.currentColor = btn.dataset.color;
            });
        });

        document.getElementById("editor-custom-color")?.addEventListener("input", (e) => {
            window.levelEditor.currentColor = e.target.value;
        });

        // Editor Action Buttons
        document.getElementById("btn-editor-invert")?.addEventListener("click", () => {
            window.levelEditor.invert();
            this.renderEditorBoard();
        });

        document.getElementById("btn-editor-clear")?.addEventListener("click", () => {
            if (confirm("確定要清空畫布嗎？")) {
                window.levelEditor.clear();
                this.renderEditorBoard();
            }
        });

        document.getElementById("btn-editor-verify")?.addEventListener("click", () => {
            const badge = document.getElementById("editor-verify-result");
            badge.classList.remove("hidden", "success", "warning", "error");
            const res = window.NonogramSolver.checkSolvability(window.levelEditor.grid);
            badge.textContent = res.message;

            if (res.solvable && res.unique && res.logical) {
                badge.classList.add("success");
            } else if (res.solvable && res.unique) {
                badge.classList.add("warning");
            } else {
                badge.classList.add("error");
            }
        });

        document.getElementById("btn-editor-playtest")?.addEventListener("click", () => {
            const title = document.getElementById("editor-puzzle-name").value;
            const { puzzle } = window.levelEditor.exportJson(title);
            this.startLevel(puzzle);
        });

        document.getElementById("btn-editor-save")?.addEventListener("click", () => {
            const title = document.getElementById("editor-puzzle-name").value;
            const { puzzle } = window.levelEditor.exportJson(title);
            window.storageManager.saveCustomLevel(puzzle);
            alert("✅ 關卡已成功保存至您的「自訂關卡庫」！");
            this.renderLevelList();
        });

        document.getElementById("btn-editor-export")?.addEventListener("click", () => {
            const title = document.getElementById("editor-puzzle-name").value;
            const { shareCode } = window.levelEditor.exportJson(title);
            this.openShareModal("匯出關卡代碼", "複製下方分享代碼，好友可在自製關卡中匯入：", shareCode, true);
        });

        document.getElementById("btn-editor-import")?.addEventListener("click", () => {
            this.openShareModal("匯入關卡代碼", "請在下方貼上收到的關卡代碼：", "", false);
        });
    }

    renderEditorBoard() {
        const boardGridWrapper = document.getElementById("editor-board-grid-wrapper");
        const colCluesElem = document.getElementById("editor-col-clues");
        const rowCluesElem = document.getElementById("editor-row-clues");
        const gridElem = document.getElementById("editor-grid");

        if (!boardGridWrapper) return;
        const size = window.levelEditor.size;
        const clues = window.levelEditor.getClues();

        let cellSize = 36;
        if (size <= 5) cellSize = 48;
        else if (size <= 10) cellSize = 36;
        else if (size <= 15) cellSize = 28;
        else cellSize = 22;

        boardGridWrapper.style.gridTemplateColumns = `auto repeat(${size}, ${cellSize}px)`;
        boardGridWrapper.style.gridTemplateRows = `auto repeat(${size}, ${cellSize}px)`;

        // Col Clues
        colCluesElem.style.gridColumn = `2 / ${size + 2}`;
        colCluesElem.style.gridRow = "1 / 2";
        colCluesElem.style.gridTemplateColumns = `repeat(${size}, ${cellSize}px)`;
        colCluesElem.innerHTML = "";

        for (let c = 0; c < size; c++) {
            const item = document.createElement("div");
            item.className = `col-clue-item ${(c + 1) % 5 === 0 && c < size - 1 ? "border-5" : ""}`;
            clues.colClues[c].forEach(num => {
                const span = document.createElement("span");
                span.textContent = num;
                item.appendChild(span);
            });
            colCluesElem.appendChild(item);
        }

        // Row Clues
        rowCluesElem.style.gridColumn = "1 / 2";
        rowCluesElem.style.gridRow = `2 / ${size + 2}`;
        rowCluesElem.style.gridTemplateRows = `repeat(${size}, ${cellSize}px)`;
        rowCluesElem.innerHTML = "";

        for (let r = 0; r < size; r++) {
            const item = document.createElement("div");
            item.className = `row-clue-item ${(r + 1) % 5 === 0 && r < size - 1 ? "border-5" : ""}`;
            clues.rowClues[r].forEach(num => {
                const span = document.createElement("span");
                span.textContent = num;
                item.appendChild(span);
            });
            rowCluesElem.appendChild(item);
        }

        // Grid
        gridElem.style.gridColumn = `2 / ${size + 2}`;
        gridElem.style.gridRow = `2 / ${size + 2}`;
        gridElem.style.gridTemplateColumns = `repeat(${size}, ${cellSize}px)`;
        gridElem.style.gridTemplateRows = `repeat(${size}, ${cellSize}px)`;
        gridElem.innerHTML = "";

        for (let r = 0; r < size; r++) {
            for (let c = 0; c < size; c++) {
                const cell = document.createElement("div");
                cell.className = "grid-cell";
                cell.dataset.r = r;
                cell.dataset.c = c;
                if ((c + 1) % 5 === 0 && c < size - 1) cell.classList.add("border-r-5");
                if ((r + 1) % 5 === 0 && r < size - 1) cell.classList.add("border-b-5");

                if (window.levelEditor.grid[r][c] === 1) {
                    cell.classList.add("state-fill");
                    const colHex = window.levelEditor.colors[r][c] || "var(--primary)";
                    cell.style.setProperty("--cell-fill", colHex);
                }

                cell.addEventListener("mousedown", (e) => {
                    if (e.button === 2) {
                        // Right-click: erase
                        window.levelEditor.setCell(r, c, false);
                        cell.classList.remove("state-fill");
                        cell.style.removeProperty("--cell-fill");
                        this.renderEditorBoard();
                        window.soundCtrl.playErase();
                        return;
                    }
                    const isFill = window.levelEditor.toggleCell(r, c) === 1;
                    cell.classList.toggle("state-fill", isFill);
                    if (isFill) {
                        cell.style.setProperty("--cell-fill", window.levelEditor.currentColor);
                    }
                    this.renderEditorBoard();
                    window.soundCtrl.playFill();
                });

                gridElem.appendChild(cell);
            }
        }
    }

    /* ===================================================================
       Image to Nonogram Converter Controller
       =================================================================== */
    initConverter() {
        const dropzone = document.getElementById("image-dropzone");
        const fileInput = document.getElementById("image-file-input");

        const handleFile = async (file) => {
            try {
                await window.imageConverter.loadImageFromFile(file);
                this.updateConverterOriginalPreview();
                this.runConverterProcess();
            } catch (err) {
                alert(err.message);
            }
        };

        fileInput?.addEventListener("change", (e) => {
            if (e.target.files && e.target.files[0]) handleFile(e.target.files[0]);
        });

        dropzone?.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropzone.classList.add("drag-over");
        });
        dropzone?.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
        dropzone?.addEventListener("drop", (e) => {
            e.preventDefault();
            dropzone.classList.remove("drag-over");
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleFile(e.dataTransfer.files[0]);
            }
        });

        // Controls binding
        const sizeSelect = document.getElementById("converter-size");
        const thresholdSlider = document.getElementById("converter-threshold");
        const contrastSlider = document.getElementById("converter-contrast");
        const ditherCheck = document.getElementById("converter-dither");
        const invertCheck = document.getElementById("converter-invert");

        sizeSelect?.addEventListener("change", (e) => {
            window.imageConverter.targetSize = parseInt(e.target.value, 10);
            this.runConverterProcess();
        });

        thresholdSlider?.addEventListener("input", (e) => {
            window.imageConverter.threshold = parseInt(e.target.value, 10);
            document.getElementById("threshold-val").textContent = e.target.value;
            this.runConverterProcess();
        });

        contrastSlider?.addEventListener("input", (e) => {
            window.imageConverter.contrast = parseInt(e.target.value, 10);
            document.getElementById("contrast-val").textContent = e.target.value;
            this.runConverterProcess();
        });

        ditherCheck?.addEventListener("change", (e) => {
            window.imageConverter.dithering = e.target.checked;
            this.runConverterProcess();
        });

        invertCheck?.addEventListener("change", (e) => {
            window.imageConverter.invert = e.target.checked;
            this.runConverterProcess();
        });

        // Play / Save buttons
        document.getElementById("btn-converter-play")?.addEventListener("click", () => {
            const puzzle = window.imageConverter.toPuzzle("自訂圖片謎題");
            if (puzzle) this.startLevel(puzzle);
        });

        document.getElementById("btn-converter-save")?.addEventListener("click", () => {
            const title = prompt("請輸入自訂圖片關卡名稱：", "我的圖片謎題");
            if (title) {
                const puzzle = window.imageConverter.toPuzzle(title);
                window.storageManager.saveCustomLevel(puzzle);
                alert("✅ 已成功保存至自訂關卡庫！");
                this.renderLevelList();
            }
        });
    }

    updateConverterOriginalPreview() {
        const wrapper = document.getElementById("original-preview-wrapper");
        if (!wrapper || !window.imageConverter.currentImage) return;
        wrapper.innerHTML = "";
        const img = window.imageConverter.currentImage.cloneNode();
        img.style.maxWidth = "100%";
        img.style.maxHeight = "260px";
        img.style.borderRadius = "6px";
        img.style.objectFit = "contain";
        wrapper.appendChild(img);
    }

    runConverterProcess() {
        if (!window.imageConverter.currentImage) return;
        const res = window.imageConverter.process();
        if (!res) return;

        // Enable action buttons
        document.getElementById("btn-converter-play").disabled = false;
        document.getElementById("btn-converter-save").disabled = false;

        // Render pixel grid preview
        const wrapper = document.getElementById("converter-pixel-preview");
        wrapper.innerHTML = "";

        const size = res.width;
        const pixelBox = document.createElement("div");
        pixelBox.style.display = "grid";
        pixelBox.style.gridTemplateColumns = `repeat(${size}, 1fr)`;
        pixelBox.style.width = "220px";
        pixelBox.style.height = "220px";
        pixelBox.style.border = "1px solid var(--border-color)";
        pixelBox.style.borderRadius = "4px";
        pixelBox.style.overflow = "hidden";

        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                const px = document.createElement("div");
                const isBlack = res.grid[y][x] === 1;
                px.style.backgroundColor = isBlack ? (res.colors[y][x] || "#1e293b") : "#ffffff";
                pixelBox.appendChild(px);
            }
        }
        wrapper.appendChild(pixelBox);

        // Check solvability
        const solvabilityTag = document.getElementById("converter-solvability-info");
        const solRes = window.NonogramSolver.checkSolvability(res.grid);
        solvabilityTag.classList.remove("hidden", "success", "warning", "error");
        solvabilityTag.textContent = solRes.message;

        if (solRes.solvable && solRes.unique && solRes.logical) solvabilityTag.classList.add("success");
        else if (solRes.solvable && solRes.unique) solvabilityTag.classList.add("warning");
        else solvabilityTag.classList.add("error");
    }

    /* ===================================================================
       Tutorial & Rules Modal
       =================================================================== */
    initTutorial() {
        const modal = document.getElementById("modal-tutorial");
        document.getElementById("btn-open-tutorial")?.addEventListener("click", () => {
            modal?.classList.remove("hidden");
            window.soundCtrl.playButton();
        });
        document.getElementById("btn-close-tutorial")?.addEventListener("click", () => modal?.classList.add("hidden"));
        document.getElementById("btn-got-it")?.addEventListener("click", () => modal?.classList.add("hidden"));
    }

    /* ===================================================================
       Settings Modal & Live Sync
       =================================================================== */
    initSettingsModal() {
        const modal = document.getElementById("modal-settings");
        document.getElementById("btn-settings")?.addEventListener("click", () => {
            this.syncSettingsUI();
            modal?.classList.remove("hidden");
            window.soundCtrl.playButton();
        });
        document.getElementById("btn-close-settings")?.addEventListener("click", () => modal?.classList.add("hidden"));
        modal?.addEventListener("click", (e) => {
            if (e.target === modal) modal.classList.add("hidden");
        });

        const themeSelect = document.getElementById("setting-theme");
        const soundCheck = document.getElementById("setting-sound");
        const volumeSlider = document.getElementById("setting-volume");
        const volumeDesc = document.getElementById("setting-volume-desc");
        const autoCrossCheck = document.getElementById("setting-auto-cross");
        const directionLockCheck = document.getElementById("setting-direction-lock");
        const highlightCheck = document.getElementById("setting-highlight-cross");
        const strictCheck = document.getElementById("setting-strict-mode");

        if (themeSelect) {
            themeSelect.value = this.settings.theme;
            themeSelect.addEventListener("change", (e) => this.applyTheme(e.target.value));
        }
        if (soundCheck) {
            soundCheck.checked = !!this.settings.soundEnabled;
            soundCheck.addEventListener("change", (e) => {
                this.settings.soundEnabled = e.target.checked;
                window.soundCtrl.setMuted(!e.target.checked);
                const icon = document.getElementById("sound-icon");
                if (icon) icon.textContent = e.target.checked ? "🔊" : "🔇";
                window.storageManager.saveSettings(this.settings);
                if (e.target.checked) window.soundCtrl.playFill();
            });
        }
        if (volumeSlider) {
            const volPct = Math.round((this.settings.soundVolume ?? 0.6) * 100);
            volumeSlider.value = volPct;
            if (volumeDesc) volumeDesc.textContent = `調節遊戲音效大小 (${volPct}%)`;
            volumeSlider.addEventListener("input", (e) => {
                const val = parseInt(e.target.value, 10);
                this.settings.soundVolume = val / 100;
                window.soundCtrl.setVolume(this.settings.soundVolume);
                if (volumeDesc) volumeDesc.textContent = `調節遊戲音效大小 (${val}%)`;
                window.storageManager.saveSettings(this.settings);
            });
            volumeSlider.addEventListener("change", () => {
                window.soundCtrl.playButton();
            });
        }
        if (autoCrossCheck) {
            autoCrossCheck.checked = !!this.settings.autoCrossCompleted;
            autoCrossCheck.addEventListener("change", (e) => {
                this.settings.autoCrossCompleted = e.target.checked;
                window.storageManager.saveSettings(this.settings);
                if (this.settings.autoCrossCompleted && this.board && !this.board.isCompleted) {
                    const allSatisfiedRows = [];
                    const allSatisfiedCols = [];
                    for (let r = 0; r < this.board.height; r++) {
                        if (this.board.isRowMatching(r)) allSatisfiedRows.push(r);
                    }
                    for (let c = 0; c < this.board.width; c++) {
                        if (this.board.isColMatching(c)) allSatisfiedCols.push(c);
                    }
                    this.processAutoCross({ newRows: allSatisfiedRows, newCols: allSatisfiedCols });
                    this.updateLineSatisfiedStyles();
                    this.afterMoveMade();
                }
            });
        }
        if (directionLockCheck) {
            directionLockCheck.checked = !!this.settings.dragDirectionLock;
            directionLockCheck.addEventListener("change", (e) => {
                this.settings.dragDirectionLock = e.target.checked;
                window.storageManager.saveSettings(this.settings);
            });
        }
        if (highlightCheck) {
            highlightCheck.checked = !!this.settings.highlightCurrentLine;
            highlightCheck.addEventListener("change", (e) => {
                this.settings.highlightCurrentLine = e.target.checked;
                window.storageManager.saveSettings(this.settings);
                if (!this.settings.highlightCurrentLine) {
                    this.clearCrosshair();
                } else if (this.focusedCell) {
                    this.setCrosshair(this.focusedCell.r, this.focusedCell.c);
                }
            });
        }
        if (strictCheck) {
            strictCheck.checked = !!this.settings.strictMistakes;
            strictCheck.addEventListener("change", (e) => {
                this.settings.strictMistakes = e.target.checked;
                window.storageManager.saveSettings(this.settings);
                this.updateMistakesDisplay();
            });
        }

        document.getElementById("btn-clear-all-data")?.addEventListener("click", () => {
            if (confirm("⚠️ 警告：這將會清除您所有的遊戲紀錄、星級成就與自訂關卡，無法還原！確定要執行嗎？")) {
                localStorage.clear();
                alert("已成功清除所有本機遊戲資料。即將重新整理頁面。");
                location.reload();
            }
        });
    }

    syncSettingsUI() {
        const themeSelect = document.getElementById("setting-theme");
        const soundCheck = document.getElementById("setting-sound");
        const volumeSlider = document.getElementById("setting-volume");
        const volumeDesc = document.getElementById("setting-volume-desc");
        const autoCrossCheck = document.getElementById("setting-auto-cross");
        const directionLockCheck = document.getElementById("setting-direction-lock");
        const highlightCheck = document.getElementById("setting-highlight-cross");
        const strictCheck = document.getElementById("setting-strict-mode");

        if (themeSelect) themeSelect.value = this.settings.theme;
        if (soundCheck) soundCheck.checked = !!this.settings.soundEnabled;
        if (volumeSlider) {
            const volPct = Math.round((this.settings.soundVolume ?? 0.6) * 100);
            volumeSlider.value = volPct;
            if (volumeDesc) volumeDesc.textContent = `調節遊戲音效大小 (${volPct}%)`;
        }
        if (autoCrossCheck) autoCrossCheck.checked = !!this.settings.autoCrossCompleted;
        if (directionLockCheck) directionLockCheck.checked = !!this.settings.dragDirectionLock;
        if (highlightCheck) highlightCheck.checked = !!this.settings.highlightCurrentLine;
        if (strictCheck) strictCheck.checked = !!this.settings.strictMistakes;
    }

    /* ===================================================================
       Share / Import Modal
       =================================================================== */
    openShareModal(title, desc, code, isExport) {
        const modal = document.getElementById("modal-share");
        document.getElementById("share-modal-title").textContent = title;
        document.getElementById("share-modal-desc").textContent = desc;
        const textarea = document.getElementById("share-code-textarea");
        textarea.value = code;

        const copyBtn = document.getElementById("btn-copy-code");
        const importBtn = document.getElementById("btn-confirm-import");
        const statusMsg = document.getElementById("share-modal-status");
        statusMsg.classList.add("hidden");

        if (isExport) {
            copyBtn.style.display = "inline-flex";
            importBtn.style.display = "none";
        } else {
            copyBtn.style.display = "none";
            importBtn.style.display = "inline-flex";
        }

        copyBtn.onclick = () => {
            textarea.select();
            navigator.clipboard.writeText(textarea.value).then(() => {
                statusMsg.textContent = "✅ 已成功複製分享碼至剪貼簿！";
                statusMsg.className = "status-msg success";
                statusMsg.classList.remove("hidden");
            });
        };

        importBtn.onclick = () => {
            try {
                const puzzle = window.levelEditor.importShareCode(textarea.value);
                window.storageManager.saveCustomLevel(puzzle);
                statusMsg.textContent = "✅ 關卡匯入成功！已加入您的關卡列表。";
                statusMsg.className = "status-msg success";
                statusMsg.classList.remove("hidden");
                this.renderLevelList();
                this.renderEditorBoard();
                setTimeout(() => modal.classList.add("hidden"), 1200);
            } catch (err) {
                statusMsg.textContent = `❌ ${err.message}`;
                statusMsg.className = "status-msg error";
                statusMsg.classList.remove("hidden");
            }
        };

        document.getElementById("btn-close-share").onclick = () => modal.classList.add("hidden");
        modal.classList.remove("hidden");
    }

    /* ===================================================================
       Random Level Generator Modal
       =================================================================== */
    initRandomLevelModal() {
        const modal = document.getElementById("modal-random-level");
        let selectedSize = 5;

        const openModal = () => {
            modal?.classList.remove("hidden");
            window.soundCtrl?.playButton();
        };

        document.getElementById("btn-open-random")?.addEventListener("click", openModal);
        document.getElementById("btn-quick-random")?.addEventListener("click", openModal);
        document.getElementById("card-random-challenge")?.addEventListener("click", (e) => {
            if (e.target.tagName !== "BUTTON") openModal();
        });

        document.getElementById("btn-close-random")?.addEventListener("click", () => modal?.classList.add("hidden"));
        document.getElementById("btn-cancel-random")?.addEventListener("click", () => modal?.classList.add("hidden"));
        modal?.addEventListener("click", (e) => {
            if (e.target === modal) modal.classList.add("hidden");
        });

        // Size Segmented Control
        document.querySelectorAll("#random-size-select .segment-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll("#random-size-select .segment-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                selectedSize = parseInt(btn.dataset.size, 10);
                window.soundCtrl?.playButton();
            });
        });

        // Start random game button
        document.getElementById("btn-start-random-game")?.addEventListener("click", () => {
            window.soundCtrl?.playButton();
            modal?.classList.add("hidden");
            
            const randomPuzzle = window.RandomPuzzleGenerator.generate(selectedSize, selectedSize);
            this.startLevel(randomPuzzle);
        });
    }

    /* ===================================================================
       Worksheet & Answer Sheet Print Modal
       =================================================================== */
    initPrintModal() {
        const modal = document.getElementById("modal-print");

        const openModal = () => {
            if (!this.worksheetPrinter) {
                this.worksheetPrinter = new window.WorksheetPrinter();
                this.worksheetPrinter.init();
            }
            modal?.classList.remove("hidden");
            window.soundCtrl?.playButton();
            this.worksheetPrinter.generateNewBatch();
        };

        document.getElementById("btn-open-print")?.addEventListener("click", openModal);
        document.getElementById("btn-quick-print")?.addEventListener("click", openModal);
        document.getElementById("card-print-worksheet")?.addEventListener("click", (e) => {
            if (e.target.tagName !== "BUTTON") openModal();
        });

        document.getElementById("btn-close-print")?.addEventListener("click", () => modal?.classList.add("hidden"));
        modal?.addEventListener("click", (e) => {
            if (e.target === modal) modal.classList.add("hidden");
        });
    }

    initScreens() {
        this.renderLevelList();
    }
}

// Instantiate application once DOM is ready
window.addEventListener("DOMContentLoaded", () => {
    window.app = new NonogramApp();
});
