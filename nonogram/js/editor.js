/**
 * Nonogram Level Creator & Editor
 * Allows interactive puzzle creation, live clue preview, color palette styling,
 * solvability verification, and import/export via shareable codes.
 */

class LevelEditor {
    constructor() {
        this.size = 10;
        this.grid = Array.from({ length: this.size }, () => new Array(this.size).fill(0));
        this.colors = Array.from({ length: this.size }, () => new Array(this.size).fill(""));
        this.currentColor = "#3b82f6"; // Default accent blue
        this.paintMode = "fill"; // "fill" or "erase" or "color"
        this.isMouseDown = false;
        this.onCluesUpdated = null;
    }

    setSize(newSize) {
        this.size = newSize;
        this.grid = Array.from({ length: this.size }, () => new Array(this.size).fill(0));
        this.colors = Array.from({ length: this.size }, () => new Array(this.size).fill(""));
    }

    setCell(r, c, isFill) {
        if (r < 0 || r >= this.size || c < 0 || c >= this.size) return;
        this.grid[r][c] = isFill ? 1 : 0;
        if (isFill) {
            this.colors[r][c] = this.currentColor;
        } else {
            this.colors[r][c] = "";
        }
    }

    toggleCell(r, c) {
        if (r < 0 || r >= this.size || c < 0 || c >= this.size) return;
        const current = this.grid[r][c];
        const next = current === 1 ? 0 : 1;
        this.setCell(r, c, next === 1);
        return next;
    }

    clear() {
        this.grid = Array.from({ length: this.size }, () => new Array(this.size).fill(0));
        this.colors = Array.from({ length: this.size }, () => new Array(this.size).fill(""));
    }

    invert() {
        for (let r = 0; r < this.size; r++) {
            for (let c = 0; c < this.size; c++) {
                const next = this.grid[r][c] === 1 ? 0 : 1;
                this.grid[r][c] = next;
                this.colors[r][c] = next === 1 ? this.currentColor : "";
            }
        }
    }

    getClues() {
        return window.generateCluesFromGrid(this.grid);
    }

    exportJson(title = "自訂數織謎題") {
        const { rowClues, colClues } = this.getClues();
        const data = {
            id: `custom_${Date.now()}`,
            title: title.trim() || "自訂數織謎題",
            category: `${this.size}x${this.size}`,
            difficulty: "自製",
            width: this.size,
            height: this.size,
            grid: this.grid,
            colors: this.colors,
            rowClues,
            colClues,
            isCustom: true,
            createdAt: Date.now()
        };

        const jsonStr = JSON.stringify(data);
        // UTF-8 safe base64
        const b64 = btoa(encodeURIComponent(jsonStr).replace(/%([0-9A-F]{2})/g, (match, p1) => {
            return String.fromCharCode('0x' + p1);
        }));

        return { json: jsonStr, shareCode: b64, puzzle: data };
    }

    importShareCode(code) {
        try {
            const rawJson = decodeURIComponent(Array.prototype.map.call(atob(code.trim()), (c) => {
                return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
            }).join(''));

            const puzzle = JSON.parse(rawJson);
            if (!puzzle.grid || !Array.isArray(puzzle.grid)) {
                throw new Error("無效的謎題格式！");
            }

            this.size = puzzle.width || puzzle.grid.length;
            this.grid = puzzle.grid;
            this.colors = puzzle.colors || Array.from({ length: this.size }, () => new Array(this.size).fill(""));
            return puzzle;
        } catch (e) {
            throw new Error("分享碼解析失敗，請確認代碼是否正確。");
        }
    }
}

window.levelEditor = new LevelEditor();
