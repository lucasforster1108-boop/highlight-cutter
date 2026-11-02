#!/usr/bin/env python3
"""Build the synthetic test assets (no real footage, nothing adult):

- test.mp4: 180s of ffmpeg testsrc2 + a quiet sine bed, with three loud
  bursts at known times (20-30s, 80-90s, 140-150s).
- test.funscript: dense, large actions inside the same three windows,
  sparse tiny actions everywhere else.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
BURSTS = [(20, 30), (80, 90), (140, 150)]
DURATION = 180


def make_video():
    path = os.path.join(OUT, "test.mp4")
    fc = (
        "[1:a]volume=0.03[bed];"
        "[2:a]adelay=20000|20000,volume=0.9[b1];"
        "[3:a]adelay=80000|80000,volume=0.9[b2];"
        "[4:a]adelay=140000|140000,volume=0.9[b3];"
        "[bed][b1][b2][b3]amix=inputs=4:normalize=0[aout]"
    )
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-f", "lavfi", "-i", f"testsrc2=duration={DURATION}:size=640x360:rate=30",
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={DURATION}",
           "-f", "lavfi", "-i", "sine=frequency=880:duration=10",
           "-f", "lavfi", "-i", "sine=frequency=880:duration=10",
           "-f", "lavfi", "-i", "sine=frequency=880:duration=10",
           "-filter_complex", fc,
           "-map", "0:v", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-c:a", "aac", "-b:a", "96k", "-t", str(DURATION), path]
    subprocess.run(cmd, check=True)
    print("made", path)


def make_funscript():
    actions = []
    t = 0.0
    flip = False
    while t < DURATION:
        in_burst = any(s <= t < e for s, e in BURSTS)
        if in_burst:
            pos = 95 if flip else 5
            actions.append({"at": int(t * 1000), "pos": pos})
            t += 0.15
        else:
            pos = 55 if flip else 45
            actions.append({"at": int(t * 1000), "pos": pos})
            t += 2.0
        flip = not flip
    data = {"version": "1.0", "inverted": False, "range": 100, "actions": actions}
    path = os.path.join(OUT, "test.funscript")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"made {path} ({len(actions)} actions)")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    make_video()
    make_funscript()
