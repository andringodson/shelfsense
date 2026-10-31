"""Synthesize the soundtrack: A-minor pad + pluck arpeggio + soft pulse, with whooshes/clicks in the same key,
placed on the event times logged by direct.py. Pure numpy; writes soundtrack.wav (48 kHz stereo)."""
import json, wave
import numpy as np

SR, DUR = 48000, 35.2
BPM = 92; BEAT = 60 / BPM
rng = np.random.default_rng(3)
events = json.load(open("capture.json"))["events"]
t = np.arange(int(SR * DUR)) / SR
L = np.zeros_like(t); R = np.zeros_like(t)

def hz(m): return 440 * 2 ** ((m - 69) / 12)

def add(sig, start, pan=0.0, gain=1.0):
    i = int(start * SR); n = min(len(sig), len(t) - i)
    if n <= 0: return
    L[i:i + n] += sig[:n] * gain * np.sqrt(0.5 * (1 - pan)); R[i:i + n] += sig[:n] * gain * np.sqrt(0.5 * (1 + pan))

def env(n, a, r):  # attack/release in seconds over n samples
    e = np.ones(n); A = int(a * SR); Rl = int(r * SR)
    e[:A] = np.linspace(0, 1, A); e[-Rl:] *= np.linspace(1, 0, Rl); return e

def bandnoise(n, lo, hi):
    spec = np.fft.rfft(rng.standard_normal(n)); f = np.fft.rfftfreq(n, 1 / SR)
    spec *= np.exp(-((np.log(np.maximum(f, 1)) - np.log((lo * hi) ** .5)) ** 2) / (2 * (np.log(hi / lo) / 2) ** 2))
    x = np.fft.irfft(spec, n); return x / (np.abs(x).max() + 1e-9)

# Chords (MIDI): Am9, Fmaj7, Cmaj7, G6 — 2 bars each
CHORDS = [[57, 60, 64, 67, 71], [53, 57, 60, 64], [48, 55, 60, 64, 71], [55, 59, 62, 64]]
BAR = 4 * BEAT

# Pad: soft additive voices, slow swell, slight detune for width
for ci in range(int(DUR / (2 * BAR)) + 1):
    start = ci * 2 * BAR; ch = CHORDS[ci % 4]; n = int((2 * BAR + 1.2) * SR); tt = np.arange(n) / SR
    for j, m in enumerate(ch):
        f = hz(m)
        for det, pan in ((0.9985, -0.6), (1.0015, 0.6)):
            v = np.sin(2 * np.pi * f * det * tt) + 0.25 * np.sin(4 * np.pi * f * det * tt) + 0.08 * np.sin(6 * np.pi * f * det * tt)
            add(v * env(n, 1.1, 1.4) * (1 + 0.15 * np.sin(2 * np.pi * 0.2 * tt + j)), start, pan, 0.022)

# Pluck arpeggio from the reveal on, with a ping-pong echo
REVEAL = next(t0 for t0, e in events if e == "reveal")
STOP = next(t0 for t0, e in events if e == "whoosh" and t0 > 30)
k = 0; s = REVEAL
while s < STOP + 2 * BEAT:
    ch = CHORDS[int(s / (2 * BAR)) % 4]; m = ch[[0, 2, 1, 3, 2, 4 % len(ch), 1, 2][k % 8] % len(ch)] + 12
    n = int(0.9 * SR); tt = np.arange(n) / SR; f = hz(m)
    v = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt) * np.exp(-tt * 18)) * np.exp(-tt * 6.5) * np.minimum(tt * 400, 1)
    g = 0.05 * (0.8 if k % 2 else 1.0) * (0.5 if s > 26.4 else 1.0)  # thin out under the stat cards
    add(v, s, -0.25, g); add(v, s + 0.75 * BEAT, 0.55, g * 0.35); add(v, s + 1.5 * BEAT, -0.55, g * 0.15)
    s += BEAT / 2; k += 1

# Soft pulse: rounded kick on 1 and 3 + sub root, reveal -> stats card
s = REVEAL
while s < 26.4:
    n = int(0.35 * SR); tt = np.arange(n) / SR
    kick = np.sin(2 * np.pi * (45 * tt + (75 / 18) * (1 - np.exp(-tt * 18)))) * np.exp(-tt * 9)
    add(kick, s, 0, 0.10)
    root = CHORDS[int(s / (2 * BAR)) % 4][0] - 12; nn = int(2 * BEAT * SR); t2 = np.arange(nn) / SR
    add(np.sin(2 * np.pi * hz(root) * t2) * env(nn, 0.02, 0.4), s, 0, 0.03)
    s += 2 * BEAT

# Whooshes on card transitions (bigger one at the reveal), a soft swoosh under the scroll
for t0, e in events:
    if e in ("whoosh", "reveal", "swoosh"):
        d = {"whoosh": 0.7, "reveal": 1.1, "swoosh": 1.3}[e]; n = int(d * SR); tt = np.arange(n) / SR
        shape = np.sin(np.pi * tt / d) ** 2
        add(bandnoise(n, 500, 4000) * shape, max(t0 - d * 0.45, 0), -0.3, {"whoosh": 0.05, "reveal": 0.075, "swoosh": 0.035}[e])
        add(bandnoise(n, 900, 6000) * shape[::-1] ** .7, max(t0 - d * 0.45, 0), 0.3, {"whoosh": 0.03, "reveal": 0.05, "swoosh": 0.02}[e])
        if e == "reveal":  # gentle low impact in key (A1)
            n2 = int(1.6 * SR); t2 = np.arange(n2) / SR
            add(np.sin(2 * np.pi * hz(45) * t2) * np.exp(-t2 * 2.5) * np.minimum(t2 * 200, 1), t0, 0, 0.12)
    if e == "click":  # tiny E6 tick, tucked under the mix
        n = int(0.06 * SR); tt = np.arange(n) / SR
        add(np.sin(2 * np.pi * hz(88) * tt) * np.exp(-tt * 90), t0, 0.15, 0.05)

# Music bus: fades + gentle saturation, normalised so the voice can sit on top
fade = np.minimum(t / 0.4, 1) * np.clip((DUR - t) / 2.6, 0, 1)
music = np.stack([L, R]) * fade
music = np.tanh(music * 1.4) / np.tanh(1.4)
music /= np.abs(music).max()

# Voice bus (narration.json + vo/l<i>.wav from voice.py), centred, music ducked underneath
import os, soundfile as sf
voice = np.zeros_like(t)
if os.path.exists("narration.json") and os.path.exists("vo/l0.wav"):
    for i, l in enumerate(json.load(open("narration.json"))):
        v, sr = sf.read(f"vo/l{i}.wav")
        v = np.interp(np.arange(int(len(v) * SR / sr)) * sr / SR, np.arange(len(v)), v)  # resample to 48 kHz
        a = int(l["at"] * SR); n = min(len(v), len(voice) - a); voice[a:a + n] += v[:n]
    voice /= np.abs(voice).max()
    # smoothed voice envelope -> ~7 dB duck on the music while she speaks
    env = np.abs(voice); win = int(0.25 * SR)
    c = np.concatenate([[0], np.cumsum(env)]); env = (c[win:] - c[:-win]) / win; env = np.pad(env, (win // 2, len(t) - len(env) - win // 2))  # O(n) moving average; env = np.minimum(env / (env.max() * 0.35), 1)
    music *= 1 - 0.55 * env
mix = music * 0.55 + np.stack([voice, voice]) * 0.9
mix = np.tanh(mix * 1.1) / np.tanh(1.1)
mix *= 10 ** (-1 / 20) / np.abs(mix).max()
pcm = (mix.T * 32767).astype("<i2")
with wave.open("soundtrack.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("soundtrack.wav", round(DUR, 1), "s, rms dBFS", round(20 * np.log10(np.sqrt((mix ** 2).mean())), 1))
