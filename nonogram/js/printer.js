/**
 * Nonogram Worksheet & Answer Sheet Printer Engine
 * Generates print-ready A4 worksheets with questions and answer keys (including clues).
 * Features a minimalist simple header to maximize printable space for puzzles.
 * Supports 5x5 and 10x10 puzzles, up to 16 questions per batch, and 100% logically solvable puzzles.
 */

class WorksheetPrinter {
    constructor() {
        this.currentSize = 5;
        this.currentCount = 4;
        this.currentSource = "random"; // 'random' or 'builtin'
        this.includeQuestions = true;
        this.includeAnswers = true;
        this.currentPuzzles = [];
        this.activePreviewTab = "all"; // 'all', 'questions', 'answers'
    }

    /**
     * Initialize event bindings and preview inside modal
     */
    init() {
        this.bindEvents();
    }

    bindEvents() {
        // Size buttons
        document.querySelectorAll(".print-size-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".print-size-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                this.currentSize = parseInt(btn.dataset.size, 10);
                this.generateNewBatch();
            });
        });

        // Count preset chips
        document.querySelectorAll(".print-count-chip").forEach(chip => {
            chip.addEventListener("click", () => {
                document.querySelectorAll(".print-count-chip").forEach(c => c.classList.remove("active"));
                chip.classList.add("active");
                this.currentCount = parseInt(chip.dataset.count, 10);
                const input = document.getElementById("print-count-input");
                if (input) input.value = this.currentCount;
                this.generateNewBatch();
            });
        });

        // Count number input
        const countInput = document.getElementById("print-count-input");
        countInput?.addEventListener("change", (e) => {
            let val = parseInt(e.target.value, 10);
            if (isNaN(val) || val < 1) val = 1;
            if (val > 16) val = 16;
            this.currentCount = val;
            e.target.value = val;
            this.updateCountChips();
            this.generateNewBatch();
        });

        document.getElementById("btn-print-count-minus")?.addEventListener("click", () => {
            if (this.currentCount > 1) {
                this.currentCount--;
                if (countInput) countInput.value = this.currentCount;
                this.updateCountChips();
                this.generateNewBatch();
            }
        });

        document.getElementById("btn-print-count-plus")?.addEventListener("click", () => {
            if (this.currentCount < 16) {
                this.currentCount++;
                if (countInput) countInput.value = this.currentCount;
                this.updateCountChips();
                this.generateNewBatch();
            }
        });

        // Source radio buttons
        document.querySelectorAll("input[name='print-source']").forEach(radio => {
            radio.addEventListener("change", (e) => {
                this.currentSource = e.target.value;
                this.generateNewBatch();
            });
        });

        // Checkboxes
        document.getElementById("print-chk-questions")?.addEventListener("change", (e) => {
            this.includeQuestions = e.target.checked;
            this.renderPreview();
        });

        document.getElementById("print-chk-answers")?.addEventListener("change", (e) => {
            this.includeAnswers = e.target.checked;
            this.renderPreview();
        });

        // Regenerate batch button
        document.getElementById("btn-regenerate-print")?.addEventListener("click", () => {
            this.generateNewBatch();
            window.soundCtrl?.playButton();
        });

        // Preview Tab buttons
        document.querySelectorAll(".preview-tab-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".preview-tab-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                this.activePreviewTab = btn.dataset.tab;
                this.renderPreview();
            });
        });

        // Main Print trigger button
        document.getElementById("btn-do-print")?.addEventListener("click", () => {
            this.executePrint();
        });
    }

    updateCountChips() {
        document.querySelectorAll(".print-count-chip").forEach(c => {
            c.classList.toggle("active", parseInt(c.dataset.count, 10) === this.currentCount);
        });
    }

    /**
     * Generate or select puzzles according to options
     */
    generateNewBatch() {
        const loadingIndicator = document.getElementById("print-preview-loading");
        if (loadingIndicator) loadingIndicator.classList.remove("hidden");

        setTimeout(() => {
            const puzzles = [];
            if (this.currentSource === "random") {
                for (let i = 0; i < this.currentCount; i++) {
                    const p = window.RandomPuzzleGenerator.generate(this.currentSize, this.currentSize);
                    puzzles.push(p);
                }
            } else {
                // Builtin puzzles
                const matching = window.PUZZLE_LEVELS.filter(l => l.width === this.currentSize && l.height === this.currentSize);
                const shuffled = [...matching].sort(() => 0.5 - Math.random());
                for (let i = 0; i < this.currentCount; i++) {
                    puzzles.push(shuffled[i % shuffled.length]);
                }
            }

            this.currentPuzzles = puzzles;
            this.renderPreview();

            if (loadingIndicator) loadingIndicator.classList.add("hidden");
        }, 30);
    }

    /**
     * Max puzzles that can legibly fit on a single A4 page
     */
    getPageCapacity(size, totalCount) {
        if (size <= 5) {
            // 5x5: simple header allows up to 16 puzzles in 4x4 on 1 page!
            return 16;
        } else {
            // 10x10:
            if (totalCount <= 6) return 6;
            if (totalCount <= 8) return 8; // 8 puzzles fit on 1 page with compact 11px cells!
            return 6; // 9+ puzzles: split nicely 6 per page
        }
    }

    /**
     * Determine optimal cell size based on puzzle dimension and count per page
     */
    getCellSize(size, pageCount) {
        if (size <= 5) {
            if (pageCount <= 2) return 26;
            if (pageCount <= 4) return 21;
            if (pageCount <= 6) return 18;
            if (pageCount <= 9) return 16;
            if (pageCount <= 12) return 14.5;
            return 13; // 13-16 puzzles
        } else {
            // 10x10
            if (pageCount <= 2) return 16;
            if (pageCount <= 4) return 14;
            if (pageCount <= 6) return 12.5;
            return 11; // 7-8 puzzles
        }
    }

    /**
     * Determine CSS grid columns class based on dimension and count per page
     */
    getGridColsClass(size, pageCount) {
        if (size <= 5) {
            if (pageCount <= 1) return "grid-cols-1";
            if (pageCount <= 4) return "grid-cols-2";
            if (pageCount <= 9) return "grid-cols-3";
            return "grid-cols-4"; // 10-16 puzzles
        } else {
            // 10x10
            if (pageCount <= 1) return "grid-cols-1";
            return "grid-cols-2";
        }
    }

    /**
     * Helper to chunk an array
     */
    chunkArray(array, size) {
        const results = [];
        for (let i = 0; i < array.length; i += size) {
            results.push(array.slice(i, i + size));
        }
        return results;
    }

    /**
     * Render the HTML inside preview container and printable-area
     */
    renderPreview() {
        const previewContainer = document.getElementById("print-preview-sheets");
        const printArea = document.getElementById("printable-area");
        if (!previewContainer) return;

        // Build HTML pages for Questions and Answers
        const questionsPages = this.includeQuestions ? this.buildQuestionsPages(this.currentPuzzles, this.currentSize) : [];
        const answersPages = this.includeAnswers ? this.buildAnswersPages(this.currentPuzzles, this.currentSize) : [];

        // Printable Area receives full document for @media print
        if (printArea) {
            const allPrintPages = [];
            if (this.includeQuestions) allPrintPages.push(...questionsPages);
            if (this.includeAnswers) allPrintPages.push(...answersPages);

            printArea.innerHTML = `
                <div class="print-document">
                    ${allPrintPages.join('<div class="print-page-break"></div>')}
                </div>
            `;
        }

        // Live Preview inside modal
        let previewHtml = "";
        if (this.activePreviewTab === "all") {
            if (this.includeQuestions) {
                previewHtml += questionsPages.map(pageHtml => `<div class="a4-preview-page">${pageHtml}</div>`).join("");
            }
            if (this.includeAnswers) {
                previewHtml += answersPages.map(pageHtml => `<div class="a4-preview-page">${pageHtml}</div>`).join("");
            }
        } else if (this.activePreviewTab === "questions") {
            if (this.includeQuestions && questionsPages.length > 0) {
                previewHtml += questionsPages.map(pageHtml => `<div class="a4-preview-page">${pageHtml}</div>`).join("");
            } else {
                previewHtml = `<div class="preview-empty-notice">未勾選列印題目卷</div>`;
            }
        } else if (this.activePreviewTab === "answers") {
            if (this.includeAnswers && answersPages.length > 0) {
                previewHtml += answersPages.map(pageHtml => `<div class="a4-preview-page">${pageHtml}</div>`).join("");
            } else {
                previewHtml = `<div class="preview-empty-notice">未勾選列印答案卷</div>`;
            }
        }

        if (!this.includeQuestions && !this.includeAnswers) {
            previewHtml = `<div class="preview-empty-notice">請至少勾選「列印題目卷」或「列印答案卷」</div>`;
        }

        previewContainer.innerHTML = previewHtml;
    }

    /**
     * Construct pages HTML for Questions Sheet (Simple Minimalist Header)
     */
    buildQuestionsPages(puzzles, size) {
        const capacity = this.getPageCapacity(size, puzzles.length);
        const chunks = this.chunkArray(puzzles, capacity);
        const totalPages = chunks.length;

        return chunks.map((chunk, pageIdx) => {
            const cellSize = this.getCellSize(size, chunk.length);
            const gridColClass = this.getGridColsClass(size, chunk.length);
            const pageNum = pageIdx + 1;
            const pageStr = totalPages > 1 ? `（第 ${pageNum}/${totalPages} 頁）` : "";

            let cardsHtml = "";
            chunk.forEach((p, idxInChunk) => {
                const globalIdx = pageIdx * capacity + idxInChunk + 1;
                cardsHtml += `
                    <div class="print-puzzle-card">
                        <div class="print-card-header">
                            <span class="print-puzzle-badge">第 ${globalIdx} 題</span>
                            <span class="print-puzzle-name">${p.title}</span>
                            <span class="print-puzzle-dim">(${size}×${size})</span>
                        </div>
                        <div class="print-puzzle-board-wrap">
                            ${this.renderPrintBoardHtml(p, false, cellSize)}
                        </div>
                    </div>
                `;
            });

            return `
                <div class="sheet-page sheet-questions">
                    <header class="sheet-header simple-header">
                        <div class="header-main-row">
                            <div class="sheet-title-group">
                                <span class="sheet-title-main">🧩 Nonogram 數織題目卷</span>
                                <span class="sheet-badge-dim">${size}×${size}</span>
                                <span class="sheet-badge-count">共 ${puzzles.length} 題${pageStr}</span>
                            </div>
                            <div class="sheet-student-fields">
                                <span class="field-item">姓名：<span class="field-line"></span></span>
                                <span class="field-item">日期：<span class="field-line"></span></span>
                                <span class="field-item">得分：<span class="field-box">/ 100</span></span>
                            </div>
                        </div>
                    </header>

                    <main class="sheet-puzzles-grid ${gridColClass}">
                        ${cardsHtml}
                    </main>

                    <footer class="sheet-footer">
                        <span>Nonogram Pixel Art Puzzle Worksheet • A4 規格</span>
                        <span>題目卷 ${totalPages > 1 ? `第 ${pageNum} 頁 / 共 ${totalPages} 頁` : ""}</span>
                    </footer>
                </div>
            `;
        });
    }

    /**
     * Construct pages HTML for Answers Sheet (MUST include clues as requested, Simple Minimalist Header)
     */
    buildAnswersPages(puzzles, size) {
        const capacity = this.getPageCapacity(size, puzzles.length);
        const chunks = this.chunkArray(puzzles, capacity);
        const totalPages = chunks.length;

        return chunks.map((chunk, pageIdx) => {
            const cellSize = this.getCellSize(size, chunk.length);
            const gridColClass = this.getGridColsClass(size, chunk.length);
            const pageNum = pageIdx + 1;
            const pageStr = totalPages > 1 ? `（第 ${pageNum}/${totalPages} 頁）` : "";

            let cardsHtml = "";
            chunk.forEach((p, idxInChunk) => {
                const globalIdx = pageIdx * capacity + idxInChunk + 1;
                cardsHtml += `
                    <div class="print-puzzle-card answer-card">
                        <div class="print-card-header">
                            <span class="print-puzzle-badge answer-badge">第 ${globalIdx} 題 解答</span>
                            <span class="print-puzzle-name">${p.title}</span>
                            <span class="print-puzzle-dim">(${size}×${size})</span>
                        </div>
                        <div class="print-puzzle-board-wrap">
                            ${this.renderPrintBoardHtml(p, true, cellSize)}
                        </div>
                    </div>
                `;
            });

            return `
                <div class="sheet-page sheet-answers">
                    <header class="sheet-header answer-header simple-header">
                        <div class="header-main-row">
                            <div class="sheet-title-group">
                                <span class="sheet-title-main answer-title">🔑 Nonogram 數織【答案卷】</span>
                                <span class="sheet-badge-dim answer-badge">${size}×${size}</span>
                                <span class="sheet-badge-count">含題目數字線索${pageStr}</span>
                            </div>
                            <div class="sheet-student-fields">
                                <span class="field-item">批改人員：<span class="field-line"></span></span>
                                <span class="field-item">評分：<span class="field-box">優 / 良 / 佳</span></span>
                            </div>
                        </div>
                    </header>

                    <main class="sheet-puzzles-grid ${gridColClass}">
                        ${cardsHtml}
                    </main>

                    <footer class="sheet-footer">
                        <span>Nonogram Pixel Art Puzzle Worksheet • A4 規格</span>
                        <span>答案卷 ${totalPages > 1 ? `第 ${pageNum} 頁 / 共 ${totalPages} 頁` : ""}</span>
                    </footer>
                </div>
            `;
        });
    }

    /**
     * Render the grid and clue numbers table/HTML for print
     * @param {Object} puzzle 
     * @param {boolean} isAnswer whether to fill the cells
     * @param {number} cellSize size in pixels
     */
    renderPrintBoardHtml(puzzle, isAnswer, cellSize = 18) {
        const width = puzzle.width;
        const height = puzzle.height;
        const rowClues = puzzle.rowClues;
        const colClues = puzzle.colClues;
        const grid = puzzle.grid;

        // Clue font size proportional to cell size
        const clueFontSize = Math.max(8, Math.min(12, Math.round(cellSize * 0.65)));

        // Render Column Clues (Top)
        let colCluesHtml = "";
        for (let c = 0; c < width; c++) {
            const isBorder5 = (c + 1) % 5 === 0 && c < width - 1;
            const clues = colClues[c];
            const clueNums = clues.map(num => `<span class="print-clue-num" style="font-size: ${clueFontSize}px;">${num}</span>`).join("");
            colCluesHtml += `
                <div class="print-col-clue ${isBorder5 ? "border-r-bold" : ""}">
                    ${clueNums}
                </div>
            `;
        }

        // Render Row Clues (Left)
        let rowCluesHtml = "";
        for (let r = 0; r < height; r++) {
            const isBorder5 = (r + 1) % 5 === 0 && r < height - 1;
            const clues = rowClues[r];
            const clueNums = clues.map(num => `<span class="print-clue-num" style="font-size: ${clueFontSize}px;">${num}</span>`).join("");
            rowCluesHtml += `
                <div class="print-row-clue ${isBorder5 ? "border-b-bold" : ""}">
                    ${clueNums}
                </div>
            `;
        }

        // Render Cells
        let cellsHtml = "";
        for (let r = 0; r < height; r++) {
            for (let c = 0; c < width; c++) {
                const isBorderR = (c + 1) % 5 === 0 && c < width - 1;
                const isBorderB = (r + 1) % 5 === 0 && r < height - 1;
                const isFilled = isAnswer && grid[r][c] === 1;

                cellsHtml += `
                    <div class="print-cell ${isBorderR ? "border-r-bold" : ""} ${isBorderB ? "border-b-bold" : ""} ${isFilled ? "cell-filled" : ""}">
                    </div>
                `;
            }
        }

        return `
            <div class="print-board-layout" style="--cell-size: ${cellSize}px; --grid-cols: ${width}; --grid-rows: ${height};">
                <div class="print-corner-spacer"></div>
                <div class="print-col-clues-container" style="grid-template-columns: repeat(${width}, ${cellSize}px);">
                    ${colCluesHtml}
                </div>
                <div class="print-row-clues-container" style="grid-template-rows: repeat(${height}, ${cellSize}px);">
                    ${rowCluesHtml}
                </div>
                <div class="print-grid-cells-container" style="grid-template-columns: repeat(${width}, ${cellSize}px); grid-template-rows: repeat(${height}, ${cellSize}px);">
                    ${cellsHtml}
                </div>
            </div>
        `;
    }

    /**
     * Trigger browser print dialog
     */
    executePrint() {
        if (!this.includeQuestions && !this.includeAnswers) {
            alert("請至少選擇列印題目卷或答案卷！");
            return;
        }

        window.soundCtrl?.playButton();
        window.print();
    }
}

window.WorksheetPrinter = WorksheetPrinter;
