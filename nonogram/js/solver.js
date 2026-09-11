/**
 * Nonogram Logic Solver & Intelligent Hint Engine
 * Implements line-by-line intersection deduction, explanation generation,
 * and uniqueness verification for custom puzzles.
 */

class NonogramSolver {
    /**
     * Compute all valid configurations for a single line given current state and clues.
     * lineState: array of length N, with values: 0 = unassigned/empty, 1 = filled, -1 = crossed
     * clues: array of integers (e.g. [2, 3] or [0])
     */
    static getValidLineConfigurations(lineState, clues) {
        const length = lineState.length;
        if (clues.length === 1 && clues[0] === 0) {
            // Clue [0] means entirely crosses
            const allCross = lineState.every(v => v !== 1);
            return allCross ? [new Array(length).fill(-1)] : [];
        }

        const validConfigs = [];
        const numBlocks = clues.length;

        // Memoized search or recursive backtracking
        function placeBlocks(blockIdx, currentPos, currentLine) {
            if (blockIdx === numBlocks) {
                // All blocks placed; ensure remaining cells can be crosses
                for (let i = currentPos; i < length; i++) {
                    if (lineState[i] === 1) return; // conflict: cell is filled
                    currentLine[i] = -1;
                }
                validConfigs.push([...currentLine]);
                return;
            }

            const blockSize = clues[blockIdx];
            // Calculate minimum remaining space needed for subsequent blocks
            let minRemaining = 0;
            for (let b = blockIdx + 1; b < numBlocks; b++) {
                minRemaining += clues[b] + 1;
            }

            const maxStart = length - minRemaining - blockSize;

            for (let start = currentPos; start <= maxStart; start++) {
                // Verify all cells between currentPos and start-1 can be crossed
                let canFillGaps = true;
                for (let i = currentPos; i < start; i++) {
                    if (lineState[i] === 1) {
                        canFillGaps = false;
                        break;
                    }
                }
                if (!canFillGaps) break; // Cannot skip past a filled cell without putting a block on it

                // Verify block cells can all be filled
                let canPlaceBlock = true;
                for (let i = start; i < start + blockSize; i++) {
                    if (lineState[i] === -1) {
                        canPlaceBlock = false;
                        break;
                    }
                }

                // If block can be placed, check delimiter right after block (must be crossed if not at end)
                if (canPlaceBlock) {
                    const delimiterPos = start + blockSize;
                    if (delimiterPos < length && lineState[delimiterPos] === 1) {
                        canPlaceBlock = false;
                    }
                }

                if (canPlaceBlock) {
                    const nextLine = [...currentLine];
                    for (let i = currentPos; i < start; i++) {
                        nextLine[i] = -1;
                    }
                    for (let i = start; i < start + blockSize; i++) {
                        nextLine[i] = 1;
                    }
                    if (start + blockSize < length) {
                        nextLine[start + blockSize] = -1;
                    }
                    placeBlocks(blockIdx + 1, start + blockSize + 1, nextLine);
                }
            }
        }

        placeBlocks(0, 0, new Array(length).fill(0));
        return validConfigs;
    }

    /**
     * Analyze a single line and find cell deductions (cells that are identical across all valid configs).
     */
    static deduceLine(lineState, clues) {
        const configs = this.getValidLineConfigurations(lineState, clues);
        if (configs.length === 0) {
            return { contradiction: true, deductions: [] };
        }

        const length = lineState.length;
        const deductions = [];

        for (let i = 0; i < length; i++) {
            if (lineState[i] !== 0) continue; // Already filled or crossed

            const firstVal = configs[0][i];
            let allSame = true;
            for (let c = 1; c < configs.length; c++) {
                if (configs[c][i] !== firstVal) {
                    allSame = false;
                    break;
                }
            }

            if (allSame) {
                deductions.push({
                    index: i,
                    val: firstVal // 1 for fill, -1 for cross
                });
            }
        }

        return { contradiction: false, deductions, configCount: configs.length };
    }

    /**
     * Find the best next hint for the player.
     * currentGrid: 2D array of state (0 = empty, 1 = filled, -1 = crossed)
     * rowClues: 2D array
     * colClues: 2D array
     * solution: 2D array (fallback check)
     */
    static findHint(currentGrid, rowClues, colClues, solution) {
        const height = currentGrid.length;
        const width = currentGrid[0].length;

        // 1. Scan rows for logical deductions
        for (let r = 0; r < height; r++) {
            const rowState = [...currentGrid[r]];
            const res = this.deduceLine(rowState, rowClues[r]);
            if (!res.contradiction && res.deductions.length > 0) {
                const deduction = res.deductions[0];
                const actionText = deduction.val === 1 ? "【填色 ■】" : "【打叉 ❌】";
                const clueStr = rowClues[r].join(" ");
                
                let reason = `第 ${r + 1} 列 (線索: [${clueStr}])：透過重疊邏輯推導，第 ${deduction.index + 1} 格必定為 ${actionText}！`;
                if (res.configCount === 1) {
                    reason = `第 ${r + 1} 列 (線索: [${clueStr}])：該行排列方式已完全確定，第 ${deduction.index + 1} 格必定為 ${actionText}！`;
                }

                return {
                    type: "logic",
                    row: r,
                    col: deduction.index,
                    val: deduction.val,
                    direction: "row",
                    lineIndex: r,
                    message: reason,
                    allLineDeductions: res.deductions.map(d => ({ row: r, col: d.index, val: d.val }))
                };
            }
        }

        // 2. Scan columns for logical deductions
        for (let c = 0; c < width; c++) {
            const colState = [];
            for (let r = 0; r < height; r++) {
                colState.push(currentGrid[r][c]);
            }
            const res = this.deduceLine(colState, colClues[c]);
            if (!res.contradiction && res.deductions.length > 0) {
                const deduction = res.deductions[0];
                const actionText = deduction.val === 1 ? "【填色 ■】" : "【打叉 ❌】";
                const clueStr = colClues[c].join(" ");

                let reason = `第 ${c + 1} 行 (線索: [${clueStr}])：透過重疊邏輯推導，第 ${deduction.index + 1} 格必定為 ${actionText}！`;
                if (res.configCount === 1) {
                    reason = `第 ${c + 1} 行 (線索: [${clueStr}])：該列排列方式已完全確定，第 ${deduction.index + 1} 格必定為 ${actionText}！`;
                }

                return {
                    type: "logic",
                    row: deduction.index,
                    col: c,
                    val: deduction.val,
                    direction: "col",
                    lineIndex: c,
                    message: reason,
                    allLineDeductions: res.deductions.map(d => ({ row: d.index, col: c, val: d.val }))
                };
            }
        }

        // 3. Fallback to solution comparison if player has made an error or puzzle requires deep lookahead
        if (solution) {
            // Check for player mistakes first
            for (let r = 0; r < height; r++) {
                for (let c = 0; c < width; c++) {
                    if (currentGrid[r][c] === 1 && solution[r][c] === 0) {
                        return {
                            type: "correction",
                            row: r,
                            col: c,
                            val: -1,
                            message: `注意：位於第 ${r + 1} 列、第 ${c + 1} 行的填色格與謎題答案不符，應標記為叉叉！`
                        };
                    }
                    if (currentGrid[r][c] === -1 && solution[r][c] === 1) {
                        return {
                            type: "correction",
                            row: r,
                            col: c,
                            val: 1,
                            message: `注意：位於第 ${r + 1} 列、第 ${c + 1} 行的叉叉標記有誤，此處應該填色！`
                        };
                    }
                }
            }

            // Find first unassigned cell that matches solution
            for (let r = 0; r < height; r++) {
                for (let c = 0; c < width; c++) {
                    if (currentGrid[r][c] === 0) {
                        const targetVal = solution[r][c] === 1 ? 1 : -1;
                        const actionText = targetVal === 1 ? "【填色 ■】" : "【打叉 ❌】";
                        return {
                            type: "direct",
                            row: r,
                            col: c,
                            val: targetVal,
                            message: `提示：第 ${r + 1} 列、第 ${c + 1} 行應為 ${actionText}。`
                        };
                    }
                }
            }
        }

        return null;
    }

    /**
     * Check if a puzzle grid has a unique solution.
     * Returns: { solvable: boolean, unique: boolean, logical: boolean, solutionsCount: number }
     */
    static checkSolvability(grid) {
        const height = grid.length;
        const width = grid[0].length;
        const { rowClues, colClues } = window.generateCluesFromGrid(grid);

        let current = Array.from({ length: height }, () => new Array(width).fill(0));
        let changed = true;
        let iteration = 0;
        const maxIter = height * width;

        // Line deduction loop
        while (changed && iteration < maxIter) {
            changed = false;
            iteration++;

            // Deduce rows
            for (let r = 0; r < height; r++) {
                const res = this.deduceLine(current[r], rowClues[r]);
                if (res.contradiction) return { solvable: false, unique: false, logical: false, solutionsCount: 0 };
                for (const d of res.deductions) {
                    current[r][d.index] = d.val;
                    changed = true;
                }
            }

            // Deduce cols
            for (let c = 0; c < width; c++) {
                const colState = [];
                for (let r = 0; r < height; r++) colState.push(current[r][c]);
                const res = this.deduceLine(colState, colClues[c]);
                if (res.contradiction) return { solvable: false, unique: false, logical: false, solutionsCount: 0 };
                for (const d of res.deductions) {
                    current[d.index][c] = d.val;
                    changed = true;
                }
            }
        }

        // Check if fully solved purely logically
        let unassigned = 0;
        for (let r = 0; r < height; r++) {
            for (let c = 0; c < width; c++) {
                if (current[r][c] === 0) unassigned++;
            }
        }

        if (unassigned === 0) {
            return {
                solvable: true,
                unique: true,
                logical: true,
                solutionsCount: 1,
                message: "完美謎題！完全可透過純邏輯推理破關，具備唯一解。"
            };
        }

        // If not completely solved by pure line intersection, use quick backtracking to test uniqueness
        let solutionsFound = 0;
        function backtrack(board, r, c) {
            if (solutionsFound >= 2) return;
            if (r === height) {
                solutionsFound++;
                return;
            }

            const nextR = c + 1 === width ? r + 1 : r;
            const nextC = c + 1 === width ? 0 : c + 1;

            if (board[r][c] !== 0) {
                backtrack(board, nextR, nextC);
                return;
            }

            // Try 1 and -1
            for (const val of [1, -1]) {
                board[r][c] = val;
                // Quick validation of completed lines
                let valid = true;
                if (nextC === 0) {
                    // Row r is complete
                    const configs = NonogramSolver.getValidLineConfigurations(board[r], rowClues[r]);
                    if (configs.length === 0) valid = false;
                }
                if (valid && nextR === height) {
                    // Col c is complete
                    const colState = [];
                    for (let i = 0; i < height; i++) colState.push(board[i][c]);
                    const configs = NonogramSolver.getValidLineConfigurations(colState, colClues[c]);
                    if (configs.length === 0) valid = false;
                }

                if (valid) {
                    backtrack(board, nextR, nextC);
                }
                board[r][c] = 0;
            }
        }

        const cloneBoard = current.map(row => [...row]);
        backtrack(cloneBoard, 0, 0);

        if (solutionsFound === 1) {
            return {
                solvable: true,
                unique: true,
                logical: false,
                solutionsCount: 1,
                message: "此題目有唯一解（部分格子需適度假設與分支驗證）。"
            };
        } else if (solutionsFound > 1) {
            return {
                solvable: true,
                unique: false,
                logical: false,
                solutionsCount: solutionsFound,
                message: "注意：此謎題存在多組解（無唯一解），建議調整線索或圖樣！"
            };
        } else {
            return {
                solvable: false,
                unique: false,
                logical: false,
                solutionsCount: 0,
                message: "此謎題無解或存在矛盾。"
            };
        }
    }
}

window.NonogramSolver = NonogramSolver;
