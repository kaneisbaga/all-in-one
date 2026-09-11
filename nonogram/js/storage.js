/**
 * LocalStorage Persistence Manager
 * Manages game settings, level completion records, custom created puzzles,
 * and automatic session restoration.
 */

class StorageManager {
    constructor() {
        this.SETTINGS_KEY = "nonogram_settings_v1";
        this.PROGRESS_KEY = "nonogram_progress_v1";
        this.CUSTOM_LEVELS_KEY = "nonogram_custom_levels_v1";
        this.ACTIVE_GAME_KEY = "nonogram_active_game_v1";

        this.defaultSettings = {
            theme: "dark",
            soundEnabled: true,
            soundVolume: 0.6,
            autoCrossCompleted: true,
            strictMistakes: false,
            highlightCurrentLine: true,
            dragDirectionLock: true
        };
    }

    getSettings() {
        try {
            const raw = localStorage.getItem(this.SETTINGS_KEY);
            return raw ? { ...this.defaultSettings, ...JSON.parse(raw) } : { ...this.defaultSettings };
        } catch (e) {
            console.error("Failed to load settings:", e);
            return { ...this.defaultSettings };
        }
    }

    saveSettings(settings) {
        try {
            localStorage.setItem(this.SETTINGS_KEY, JSON.stringify(settings));
        } catch (e) {
            console.error("Failed to save settings:", e);
        }
    }

    getProgress() {
        try {
            const raw = localStorage.getItem(this.PROGRESS_KEY);
            return raw ? JSON.parse(raw) : {};
        } catch (e) {
            console.error("Failed to load progress:", e);
            return {};
        }
    }

    saveLevelRecord(levelId, record) {
        try {
            const progress = this.getProgress();
            const prev = progress[levelId] || {};
            const bestTime = prev.bestTime ? Math.min(prev.bestTime, record.time) : record.time;
            const stars = Math.max(prev.stars || 1, record.stars || 1);

            progress[levelId] = {
                completed: true,
                bestTime,
                stars,
                lastCompletedAt: Date.now()
            };
            localStorage.setItem(this.PROGRESS_KEY, JSON.stringify(progress));
        } catch (e) {
            console.error("Failed to save record:", e);
        }
    }

    getCustomLevels() {
        try {
            const raw = localStorage.getItem(this.CUSTOM_LEVELS_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            console.error("Failed to load custom levels:", e);
            return [];
        }
    }

    saveCustomLevel(level) {
        try {
            const levels = this.getCustomLevels();
            const idx = levels.findIndex(l => l.id === level.id);
            if (idx >= 0) {
                levels[idx] = level;
            } else {
                levels.push(level);
            }
            localStorage.setItem(this.CUSTOM_LEVELS_KEY, JSON.stringify(levels));
        } catch (e) {
            console.error("Failed to save custom level:", e);
        }
    }

    deleteCustomLevel(levelId) {
        try {
            const levels = this.getCustomLevels().filter(l => l.id !== levelId);
            localStorage.setItem(this.CUSTOM_LEVELS_KEY, JSON.stringify(levels));
        } catch (e) {
            console.error("Failed to delete custom level:", e);
        }
    }

    saveActiveGame(state) {
        try {
            if (!state) {
                localStorage.removeItem(this.ACTIVE_GAME_KEY);
            } else {
                localStorage.setItem(this.ACTIVE_GAME_KEY, JSON.stringify(state));
            }
        } catch (e) {
            console.error("Failed to save active game:", e);
        }
    }

    getActiveGame() {
        try {
            const raw = localStorage.getItem(this.ACTIVE_GAME_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            console.error("Failed to load active game:", e);
            return null;
        }
    }

    clearActiveGame() {
        try {
            localStorage.removeItem(this.ACTIVE_GAME_KEY);
        } catch (e) {
            console.error("Failed to clear active game:", e);
        }
    }
}

window.storageManager = new StorageManager();
