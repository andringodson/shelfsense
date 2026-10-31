"""Narration with Kokoro (offline neural TTS): one wav per line, sized to its scene slot."""
import json, sys
import soundfile as sf
from kokoro_onnx import Kokoro

M = sys.argv[1]
k = Kokoro(f"{M}/kokoro-v1.0.onnx", f"{M}/voices-v1.0.bin")
VOICE = sys.argv[2] if len(sys.argv) > 2 else "af_heart"
for i, l in enumerate(json.load(open("narration.json"))):
    speed = 0.94
    while True:
        audio, sr = k.create(l["text"], voice=VOICE, speed=speed, lang="en-us")
        d = len(audio) / sr
        if d <= l["slot"] or speed >= 1.12: break
        speed += 0.03  # nudge faster only as much as the scene needs
    sf.write(f"vo/l{i}.wav", audio, sr)
    print(i, f"{d:.2f}s / slot {l['slot']}s @ speed {speed:.2f}", "OVER" if d > l["slot"] else "ok")
