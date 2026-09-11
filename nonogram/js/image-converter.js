/**
 * Image-to-Nonogram Converter
 * Converts uploaded user images into playable Nonogram puzzles with
 * live thresholding, contrast adjustment, dithering, and color extraction.
 */

class ImageConverter {
    constructor() {
        this.currentImage = null;
        this.targetSize = 10;
        this.threshold = 128;
        this.contrast = 0;
        this.invert = false;
        this.dithering = false;

        this.processedGrid = null;
        this.extractedColors = null;
    }

    loadImageFromFile(file) {
        return new Promise((resolve, reject) => {
            if (!file.type.startsWith("image/")) {
                reject(new Error("所選檔案不是圖片格式！"));
                return;
            }

            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    this.currentImage = img;
                    resolve(img);
                };
                img.onerror = () => reject(new Error("圖片載入失敗！"));
                img.src = e.target.result;
            };
            reader.onerror = () => reject(new Error("檔案讀取失敗！"));
            reader.readAsDataURL(file);
        });
    }

    process() {
        if (!this.currentImage) return null;

        const size = this.targetSize;
        const canvas = document.createElement("canvas");
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });

        // Draw image fit within canvas preserving aspect ratio
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, size, size);

        const img = this.currentImage;
        const hRatio = size / img.width;
        const vRatio = size / img.height;
        const ratio = Math.min(hRatio, vRatio);
        const centerShiftX = (size - img.width * ratio) / 2;
        const centerShiftY = (size - img.height * ratio) / 2;

        ctx.drawImage(img, 0, 0, img.width, img.height,
            centerShiftX, centerShiftY, img.width * ratio, img.height * ratio);

        const imgData = ctx.getImageData(0, 0, size, size);
        const data = imgData.data;

        // Contrast factor calculation
        const factor = (259 * (this.contrast + 255)) / (255 * (259 - this.contrast));

        // Create luminance matrix
        const grayMatrix = Array.from({ length: size }, () => new Array(size).fill(0));
        const colorMatrix = Array.from({ length: size }, () => new Array(size).fill(""));

        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                const idx = (y * size + x) * 4;
                let r = data[idx];
                let g = data[idx + 1];
                let b = data[idx + 2];
                const a = data[idx + 3];

                // If transparent, consider white
                if (a < 50) {
                    r = 255;
                    g = 255;
                    b = 255;
                }

                // Apply contrast
                r = Math.min(255, Math.max(0, factor * (r - 128) + 128));
                g = Math.min(255, Math.max(0, factor * (g - 128) + 128));
                b = Math.min(255, Math.max(0, factor * (b - 128) + 128));

                // Perceived luminance (ITU-R BT.601)
                const gray = 0.299 * r + 0.587 * g + 0.114 * b;
                grayMatrix[y][x] = gray;

                // Store hex color
                const hexR = Math.round(r).toString(16).padStart(2, "0");
                const hexG = Math.round(g).toString(16).padStart(2, "0");
                const hexB = Math.round(b).toString(16).padStart(2, "0");
                colorMatrix[y][x] = `#${hexR}${hexG}${hexB}`;
            }
        }

        // Binarization: Threshold or Floyd-Steinberg Dithering
        const grid = Array.from({ length: size }, () => new Array(size).fill(0));
        const finalColors = Array.from({ length: size }, () => new Array(size).fill(""));

        if (!this.dithering) {
            for (let y = 0; y < size; y++) {
                for (let x = 0; x < size; x++) {
                    const lum = grayMatrix[y][x];
                    let isBlack = lum < this.threshold;
                    if (this.invert) isBlack = !isBlack;
                    grid[y][x] = isBlack ? 1 : 0;
                    finalColors[y][x] = isBlack ? colorMatrix[y][x] : "";
                }
            }
        } else {
            // Floyd-Steinberg error diffusion
            const ditherMatrix = grayMatrix.map(row => [...row]);
            for (let y = 0; y < size; y++) {
                for (let x = 0; x < size; x++) {
                    const oldVal = ditherMatrix[y][x];
                    const newVal = oldVal < this.threshold ? 0 : 255;
                    const error = oldVal - newVal;

                    let isBlack = newVal === 0;
                    if (this.invert) isBlack = !isBlack;
                    grid[y][x] = isBlack ? 1 : 0;
                    finalColors[y][x] = isBlack ? colorMatrix[y][x] : "";

                    // Distribute error
                    if (x + 1 < size) ditherMatrix[y][x + 1] += (error * 7) / 16;
                    if (x - 1 >= 0 && y + 1 < size) ditherMatrix[y + 1][x - 1] += (error * 3) / 16;
                    if (y + 1 < size) ditherMatrix[y + 1][x] += (error * 5) / 16;
                    if (x + 1 < size && y + 1 < size) ditherMatrix[y + 1][x + 1] += (error * 1) / 16;
                }
            }
        }

        this.processedGrid = grid;
        this.extractedColors = finalColors;

        const { rowClues, colClues } = window.generateCluesFromGrid(grid);
        return {
            grid,
            colors: finalColors,
            width: size,
            height: size,
            rowClues,
            colClues
        };
    }

    /**
     * Create playable puzzle object
     */
    toPuzzle(title = "自訂圖片謎題") {
        if (!this.processedGrid) return null;
        const size = this.targetSize;
        const { rowClues, colClues } = window.generateCluesFromGrid(this.processedGrid);

        return {
            id: `custom_img_${Date.now()}`,
            title: title.trim() || "自訂圖片謎題",
            category: `${size}x${size}`,
            difficulty: "自製",
            width: size,
            height: size,
            grid: this.processedGrid,
            colors: this.extractedColors,
            rowClues,
            colClues,
            isCustom: true
        };
    }
}

window.imageConverter = new ImageConverter();
