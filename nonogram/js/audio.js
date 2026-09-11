/**
 * Nonogram Sound Synthesizer using Web Audio API
 * Zero external audio files required. Crisp, pleasant retro/modern sound effects.
 */

class SoundController {
    constructor() {
        this.ctx = null;
        this.enabled = true;
        this.volume = 0.5;
        this.masterGain = null;
    }

    init() {
        if (!this.ctx) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                this.ctx = new AudioContext();
                this.masterGain = this.ctx.createGain();
                this.masterGain.gain.setValueAtTime(this.enabled ? this.volume : 0, this.ctx.currentTime);
                this.masterGain.connect(this.ctx.destination);
            }
        }
        if (this.ctx && this.ctx.state === 'suspended') {
            this.ctx.resume();
        }
    }

    setMuted(muted) {
        this.enabled = !muted;
        if (this.masterGain && this.ctx) {
            this.masterGain.gain.setValueAtTime(this.enabled ? this.volume : 0, this.ctx.currentTime);
        }
    }

    setVolume(val) {
        this.volume = Math.max(0, Math.min(1, val));
        if (this.masterGain && this.ctx && this.enabled) {
            this.masterGain.gain.setValueAtTime(this.volume, this.ctx.currentTime);
        }
    }

    playTone(freq, type = 'sine', duration = 0.1, gainVal = 0.3, detune = 0) {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = type;
        osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
        if (detune) osc.detune.setValueAtTime(detune, this.ctx.currentTime);

        gain.gain.setValueAtTime(gainVal, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);

        osc.connect(gain);
        gain.connect(this.masterGain);

        osc.start();
        osc.stop(this.ctx.currentTime + duration);
    }

    // Sound for filling a cell (pleasant warm chime)
    playFill() {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;

        const now = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = 'triangle';
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(587.33, now + 0.08); // A4 to D5

        gain.gain.setValueAtTime(0.25, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);

        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start(now);
        osc.stop(now + 0.12);
    }

    // Sound for marking an X (crisp tick/tap)
    playCross() {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;

        const now = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = 'square';
        osc.frequency.setValueAtTime(280, now);
        osc.frequency.exponentialRampToValueAtTime(140, now + 0.06);

        gain.gain.setValueAtTime(0.15, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.06);

        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start(now);
        osc.stop(now + 0.06);
    }

    // Sound for erasing a cell
    playErase() {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;

        const now = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(320, now);
        osc.frequency.exponentialRampToValueAtTime(200, now + 0.08);

        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);

        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start(now);
        osc.stop(now + 0.08);
    }

    // Clue mark toggle
    playClueClick() {
        this.playTone(880, 'sine', 0.04, 0.1);
    }

    // Row or column completed chime
    playLineComplete() {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;

        const notes = [523.25, 659.25, 783.99]; // C5, E5, G5
        notes.forEach((freq, idx) => {
            setTimeout(() => {
                this.playTone(freq, 'triangle', 0.15, 0.2);
            }, idx * 60);
        });
    }

    // Mistake / error alert
    playMistake() {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;

        const now = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(150, now);
        osc.frequency.linearRampToValueAtTime(100, now + 0.25);

        gain.gain.setValueAtTime(0.3, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);

        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start(now);
        osc.stop(now + 0.25);
    }

    // Victory fanfare (jubilant triumphant melody)
    playVictory() {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;

        const fanfare = [
            { freq: 523.25, delay: 0, dur: 0.12 },   // C5
            { freq: 523.25, delay: 130, dur: 0.12 }, // C5
            { freq: 523.25, delay: 260, dur: 0.12 }, // C5
            { freq: 659.25, delay: 390, dur: 0.25 }, // E5
            { freq: 783.99, delay: 650, dur: 0.2 },  // G5
            { freq: 1046.50, delay: 850, dur: 0.6 }  // C6
        ];

        fanfare.forEach(item => {
            setTimeout(() => {
                this.playTone(item.freq, 'sine', item.dur, 0.35);
                this.playTone(item.freq * 0.5, 'triangle', item.dur, 0.2); // bass backing
            }, item.delay);
        });
    }

    // Hint used sound
    playHint() {
        this.playTone(987.77, 'sine', 0.2, 0.2); // B5
        setTimeout(() => {
            this.playTone(1318.51, 'sine', 0.3, 0.25); // E6
        }, 120);
    }

    // Button click
    playButton() {
        this.playTone(600, 'sine', 0.05, 0.08);
    }
}

// Global audio singleton
window.soundCtrl = new SoundController();
