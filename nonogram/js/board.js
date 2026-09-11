/**
 * Nonogram Board Model & Game State Manager
 * Handles cell modifications, line completion checks, undo/redo history,
 * clue strike-throughs, and victory verification.
 */

class NonogramBoard {
    constructor(levelData) {
        this.level = levelData;
        this.width = levelData.width;
        this.height = levelData.height;
        this.solution = levelData.grid; // 2D binary array [height][width]
        this.rowClues = levelData.rowClues;
        this.colClues = levelData.colClues;
        this.colors = levelData.colors || null;

        // Current board state: 0 = empty, 1 = filled, -1 = cross, 2 = question
        this.grid = Array.from({ length: this.height }, () => new Array(this.width).fill(0));

        // Track which clues have been manually or automatically struck through
        // Keys format: "r-rowIdx-clueIdx" or "c-colIdx-clueIdx"
        this.struckClues = new Set();

        // Line satisfied cache
        this.rowSatisfied = new Array(this.height).fill(false);
        this.colSatisfied = new Array(this.width).fill(false);

        // History stacks for multi-level Undo / Redo
        this.undoStack = [];
        this.redoStack = [];

        this.mistakesCount = 0;
        this.isCompleted = false;
        this.timeElapsed = 0;
    }

    /**
     * Get cell state at (r, c)
     */
    getCell(r, c) {
        if (r < 0 || r >= this.height || c < 0 || c >= this.width) return 0;
        return this.grid[r][c];
    }

    /**
     * Directly set cell state, returning whether change occurred
     */
    setCell(r, c, newVal) {
        if (this.isCompleted) return false;
        if (r < 0 || r >= this.height || c < 0 || c >= this.width) return false;

        const prevVal = this.grid[r][c];
        if (prevVal === newVal) return false;

        this.grid[r][c] = newVal;
        return true;
    }

    /**
     * Group a drag or single click into an undoable action
     */
    commitMove(moves) {
        if (!moves || moves.length === 0) return;
        this.undoStack.push(moves);
        this.redoStack = []; // Clear redo history on new action
        this.updateLineStatus();
    }

    /**
     * Undo last batch of cell changes
     */
    undo() {
        if (this.isCompleted || this.undoStack.length === 0) return null;
        const lastMove = this.undoStack.pop();
        const reversed = [];

        for (let i = lastMove.length - 1; i >= 0; i--) {
            const { r, c, prevVal, newVal } = lastMove[i];
            this.grid[r][c] = prevVal;
            reversed.push({ r, c, prevVal: newVal, newVal: prevVal });
        }

        this.redoStack.push(lastMove);
        this.updateLineStatus();
        return reversed;
    }

    /**
     * Redo last undone batch
     */
    redo() {
        if (this.isCompleted || this.redoStack.length === 0) return null;
        const nextMove = this.redoStack.pop();

        for (let i = 0; i < nextMove.length; i++) {
            const { r, c, newVal } = nextMove[i];
            this.grid[r][c] = newVal;
        }

        this.undoStack.push(nextMove);
        this.updateLineStatus();
        return nextMove;
    }

    /**
     * Check if a row currently matches its clue sequence and solution
     */
    isRowMatching(r) {
        if (!this.solution) return false;
        const target = this.rowClues[r];
        const isZeroRow = target.length === 1 && target[0] === 0;

        if (isZeroRow) {
            let hasCross = false;
            for (let c = 0; c < this.width; c++) {
                if (this.grid[r][c] === 1) return false;
                if (this.grid[r][c] === -1) hasCross = true;
            }
            return hasCross;
        }

        let hasFilled = false;
        for (let c = 0; c < this.width; c++) {
            const isFilled = this.grid[r][c] === 1;
            const shouldBeFilled = this.solution[r][c] === 1;
            if (isFilled !== shouldBeFilled) return false;
            if (isFilled) hasFilled = true;
        }
        return hasFilled;
    }

    /**
     * Check if a col currently matches its clue sequence and solution
     */
    isColMatching(c) {
        if (!this.solution) return false;
        const target = this.colClues[c];
        const isZeroCol = target.length === 1 && target[0] === 0;

        if (isZeroCol) {
            let hasCross = false;
            for (let r = 0; r < this.height; r++) {
                if (this.grid[r][c] === 1) return false;
                if (this.grid[r][c] === -1) hasCross = true;
            }
            return hasCross;
        }

        let hasFilled = false;
        for (let r = 0; r < this.height; r++) {
            const isFilled = this.grid[r][c] === 1;
            const shouldBeFilled = this.solution[r][c] === 1;
            if (isFilled !== shouldBeFilled) return false;
            if (isFilled) hasFilled = true;
        }
        return hasFilled;
    }

    /**
     * Auto-cross remaining empty cells in a completed row
     */
    autoCrossRow(r) {
        const changes = [];
        for (let c = 0; c < this.width; c++) {
            if (this.grid[r][c] === 0 || this.grid[r][c] === 2) {
                changes.push({ r, c, prevVal: this.grid[r][c], newVal: -1 });
                this.grid[r][c] = -1;
            }
        }
        return changes;
    }

    /**
     * Auto-cross remaining empty cells in a completed column
     */
    autoCrossCol(c) {
        const changes = [];
        for (let r = 0; r < this.height; r++) {
            if (this.grid[r][c] === 0 || this.grid[r][c] === 2) {
                changes.push({ r, c, prevVal: this.grid[r][c], newVal: -1 });
                this.grid[r][c] = -1;
            }
        }
        return changes;
    }

    /**
     * Update satisfied status for all rows and columns
     * Returns newly satisfied lines: { newRows: [], newCols: [] }
     */
    updateLineStatus() {
        const newlySatisfied = { newRows: [], newCols: [] };

        for (let r = 0; r < this.height; r++) {
            const match = this.isRowMatching(r);
            if (match && !this.rowSatisfied[r]) {
                newlySatisfied.newRows.push(r);
            }
            this.rowSatisfied[r] = match;
        }

        for (let c = 0; c < this.width; c++) {
            const match = this.isColMatching(c);
            if (match && !this.colSatisfied[c]) {
                newlySatisfied.newCols.push(c);
            }
            this.colSatisfied[c] = match;
        }

        return newlySatisfied;
    }

    /**
     * Toggle clue strike-through
     */
    toggleClue(type, lineIdx, clueIdx) {
        const key = `${type}-${lineIdx}-${clueIdx}`;
        if (this.struckClues.has(key)) {
            this.struckClues.delete(key);
            return false;
        } else {
            this.struckClues.add(key);
            return true;
        }
    }

    isClueStruck(type, lineIdx, clueIdx) {
        return this.struckClues.has(`${type}-${lineIdx}-${clueIdx}`);
    }

    /**
     * Check if entire puzzle is correctly solved
     */
    checkVictory() {
        for (let r = 0; r < this.height; r++) {
            for (let c = 0; c < this.width; c++) {
                const target = this.solution[r][c];
                const current = this.grid[r][c];
                // Solution 1 must be filled
                if (target === 1 && current !== 1) return false;
                // Solution 0 must NOT be filled (can be empty 0 or cross -1)
                if (target === 0 && current === 1) return false;
            }
        }
        this.isCompleted = true;
        return true;
    }

    /**
     * Count how many filled cells are placed correctly
     */
    getProgress() {
        let totalTarget = 0;
        let correctFilled = 0;
        let wrongFilled = 0;

        for (let r = 0; r < this.height; r++) {
            for (let c = 0; c < this.width; c++) {
                if (this.solution[r][c] === 1) totalTarget++;
                if (this.grid[r][c] === 1) {
                    if (this.solution[r][c] === 1) {
                        correctFilled++;
                    } else {
                        wrongFilled++;
                    }
                }
            }
        }

        const percent = totalTarget === 0 ? 100 : Math.round((correctFilled / totalTarget) * 100);
        return { percent, correctFilled, totalTarget, wrongFilled };
    }

    /**
     * Serialize board for saving
     */
    serialize() {
        return {
            levelId: this.level.id,
            grid: this.grid,
            timeElapsed: this.timeElapsed,
            mistakesCount: this.mistakesCount,
            isCompleted: this.isCompleted,
            struckClues: Array.from(this.struckClues)
        };
    }

    /**
     * Restore board from saved state
     */
    deserialize(data) {
        if (!data || !data.grid) return;
        this.grid = data.grid;
        this.timeElapsed = data.timeElapsed || 0;
        this.mistakesCount = data.mistakesCount || 0;
        this.isCompleted = data.isCompleted || false;
        if (data.struckClues) {
            this.struckClues = new Set(data.struckClues);
        }
        this.updateLineStatus();
    }
}

window.NonogramBoard = NonogramBoard;
