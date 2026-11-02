#!/usr/bin/env python3
"""End-to-end test for cut.py against the synthetic assets.

Asserts, for both script mode and audio mode:
  - 3 clips come out, and every known burst window overlaps a clip
  - clip files exist and their real durations roughly match clips.json
  - clips.json has the expected structure
Also checks --concat produces a reel.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "output")
VIDEO = os.path.join(OUT, "test.mp4")
BURSTS = [(20, 30), (80, 90), (140, 150)]


def ffprobe_duration(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "json", path],
                       capture_output=True, text=True)
    return float(json.loads(p.stdout)["format"]["duration"])


def overlaps(clip, burst):
    return clip["start"] < burst[1] and clip["end"] > burst[0]


def check_mode(mode, extra_args):
    outdir = os.path.join(OUT, f"result_{mode}")
    cmd = [sys.executable, os.path.join(ROOT, "cut.py"), VIDEO,
           "--mode", mode, "--top", "3", "-o", outdir] + extra_args
    print("== $", " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True)
    print(p.stdout.strip())
    assert p.returncode == 0, p.stderr

    with open(os.path.join(outdir, "clips.json"), encoding="utf-8") as f:
        clips = json.load(f)
    assert isinstance(clips, list) and len(clips) == 3, f"expected 3 clips, got {clips}"
    for c in clips:
        for key in ("start", "end", "duration", "score", "file", "mode"):
            assert key in c, f"missing key {key} in {c}"
        assert c["mode"] == mode
        path = os.path.join(outdir, c["file"])
        assert os.path.isfile(path), f"clip file missing: {path}"
        real = ffprobe_duration(path)
        assert abs(real - c["duration"]) < 1.5, \
            f"{c['file']}: json says {c['duration']}s, file is {real:.2f}s"
    for burst in BURSTS:
        assert any(overlaps(c, burst) for c in clips), \
            f"{mode} mode: no clip overlaps burst {burst}; clips={clips}"
    print(f"PASS {mode}: 3 clips, all bursts hit, durations match")
    return outdir


def main():
    if not os.path.isfile(VIDEO):
        subprocess.run([sys.executable, os.path.join(HERE, "make_assets.py")],
                       check=True)
    outdir = check_mode("script", ["--script", os.path.join(OUT, "test.funscript")])
    check_mode("audio", [])

    # --concat on the script-mode output set
    reel_dir = os.path.join(OUT, "result_concat")
    cmd = [sys.executable, os.path.join(ROOT, "cut.py"), VIDEO,
           "--mode", "script", "--script", os.path.join(OUT, "test.funscript"),
           "--top", "3", "--concat", "-o", reel_dir]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    reel = os.path.join(reel_dir, "test_highlights.mp4")
    assert os.path.isfile(reel), "highlight reel missing"
    d = ffprobe_duration(reel)
    print(f"PASS concat: reel exists, {d:.1f}s")
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
