#!/usr/bin/env python3
"""highlight-cutter: pull the intense parts out of a long video.

Two signal sources:
  - a funscript next to the video (action intensity over time)
  - the audio track itself (volume peaks)

It finds the top-N busiest windows, pads them, merges the ones that are
close together, cuts them out with ffmpeg and optionally stitches the
clips into a single highlight reel.
"""

import argparse
import json
import math
import os
import struct
import subprocess
import sys

WINDOW = 10.0   # seconds, scoring window
STEP = 1.0      # seconds, sliding step


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def probe_duration(path):
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", path])
    if p.returncode != 0:
        die(f"ffprobe failed on {path}: {p.stderr.strip()[:200]}")
    try:
        return float(json.loads(p.stdout)["format"]["duration"])
    except Exception:
        die(f"could not read duration of {path}")


# ---------------------------------------------------------------- script mode

def script_scores(script_path, duration):
    """Sliding-window intensity from funscript actions.

    score(window) = total |position change| inside the window
                    + 10 * number of actions (so dense-but-tiny jitter
                    still registers, and sparse-but-huge strokes do too).
    Returns a list of (window_start, score), one per STEP.
    """
    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    actions = sorted(data.get("actions", []), key=lambda a: a["at"])
    if not actions:
        die(f"no actions found in {script_path}")
    times = [a["at"] / 1000.0 for a in actions]
    poss = [a["pos"] for a in actions]

    scores = []
    n = int(max(0.0, duration - WINDOW) / STEP) + 1
    j0 = 0  # left edge index into actions
    for i in range(n):
        start = i * STEP
        end = start + WINDOW
        while j0 < len(times) and times[j0] < start:
            j0 += 1
        move = 0.0
        count = 0
        prev = None
        j = j0
        while j < len(times) and times[j] < end:
            if prev is not None:
                move += abs(poss[j] - prev)
            prev = poss[j]
            count += 1
            j += 1
        scores.append((start, move + 10.0 * count))
    return scores


# ----------------------------------------------------------------- audio mode

def audio_scores(video_path, duration):
    """Sliding-window RMS volume from the audio track.

    Pulls mono 8 kHz PCM out of ffmpeg and does the math with the
    standard library only. score(window) = sum of per-second RMS.
    """
    cmd = ["ffmpeg", "-v", "error", "-i", video_path,
           "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        die("ffmpeg could not extract audio (does the video have an audio track?)")
    raw = p.stdout
    if len(raw) < 16000:
        die("audio track is empty or too short")
    samples = struct.unpack("<%dh" % (len(raw) // 2), raw)

    per_sec = []
    sr = 8000
    for sec in range(int(duration) + 1):
        chunk = samples[sec * sr:(sec + 1) * sr]
        if not chunk:
            break
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) / 32768.0
        per_sec.append(rms)

    scores = []
    w = int(WINDOW)
    for i in range(max(1, len(per_sec) - w + 1)):
        scores.append((float(i), sum(per_sec[i:i + w])))
    return scores


# ------------------------------------------------------------- peak selection

def pick_segments(scores, duration, top, pad, merge_gap):
    """Greedy peak picking: take the strongest window, suppress anything
    within merge_gap of it, repeat. Then pad, merge overlaps, sort."""
    pool = sorted(scores, key=lambda x: x[1], reverse=True)
    chosen = []
    for start, score in pool:
        if len(chosen) >= top:
            break
        if all(abs(start - c[0]) >= merge_gap for c in chosen):
            chosen.append((start, score))
    if not chosen:
        return []

    segs = []
    for start, score in chosen:
        s = max(0.0, start - pad)
        e = min(duration, start + WINDOW + pad)
        segs.append({"start": round(s, 2), "end": round(e, 2), "score": round(score, 2)})
    segs.sort(key=lambda s: s["start"])

    merged = [segs[0]]
    for seg in segs[1:]:
        last = merged[-1]
        if seg["start"] - last["end"] <= merge_gap:
            last["end"] = max(last["end"], seg["end"])
            last["score"] = max(last["score"], seg["score"])
        else:
            merged.append(seg)
    return merged


# ------------------------------------------------------------------- cutting

def cut_clip(video, seg, out_path):
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-ss", f"{seg['start']:.2f}", "-to", f"{seg['end']:.2f}",
           "-i", video,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-c:a", "aac", "-b:a", "128k", out_path]
    p = run(cmd)
    if p.returncode != 0:
        die(f"ffmpeg cut failed: {p.stderr.strip()[:300]}")


def concat_clips(clip_paths, out_path):
    list_path = out_path + ".list.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for cp in clip_paths:
            f.write("file '%s'\n" % os.path.abspath(cp).replace("'", "'\\''"))
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
           "-i", list_path, "-c", "copy", out_path]
    p = run(cmd)
    os.remove(list_path)
    if p.returncode != 0:
        die(f"ffmpeg concat failed: {p.stderr.strip()[:300]}")


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(
        description="Cut the highlight moments out of a long video, "
                    "guided by a funscript or by audio volume.")
    ap.add_argument("video", help="input video file")
    ap.add_argument("--script", help="funscript file (default: same name as video, .funscript)")
    ap.add_argument("--mode", choices=["auto", "script", "audio"], default="auto")
    ap.add_argument("--top", type=int, default=5, help="how many highlight segments to pick (default 5)")
    ap.add_argument("--pad", type=float, default=5, help="seconds of breathing room added on both sides (default 5)")
    ap.add_argument("--merge-gap", type=float, default=30,
                    help="segments closer than this (seconds) get merged (default 30)")
    ap.add_argument("--concat", action="store_true", help="also stitch the clips into one highlight reel")
    ap.add_argument("-o", "--outdir", help="output directory (default: <video>_highlights)")
    args = ap.parse_args()

    if not os.path.isfile(args.video):
        die(f"video not found: {args.video}")
    base, _ = os.path.splitext(args.video)
    outdir = args.outdir or (base + "_highlights")

    mode = args.mode
    script_path = args.script or (base + ".funscript")
    if mode == "auto":
        mode = "script" if os.path.isfile(script_path) else "audio"
    if mode == "script" and not os.path.isfile(script_path):
        die(f"script mode needs a funscript, not found: {script_path}")

    duration = probe_duration(args.video)
    print(f"video: {args.video} ({duration:.1f}s), mode: {mode}")

    if mode == "script":
        scores = script_scores(script_path, duration)
    else:
        scores = audio_scores(args.video, duration)

    segs = pick_segments(scores, duration, args.top, args.pad, args.merge_gap)
    if not segs:
        die("no segments picked (video too short?)")
    os.makedirs(outdir, exist_ok=True)

    stem = os.path.splitext(os.path.basename(args.video))[0]
    clips = []
    for i, seg in enumerate(segs, 1):
        name = f"{stem}_clip{i:02d}_{int(seg['start'])}s.mp4"
        path = os.path.join(outdir, name)
        cut_clip(args.video, seg, path)
        seg = dict(seg)
        seg["duration"] = round(seg["end"] - seg["start"], 2)
        seg["file"] = name
        seg["mode"] = mode
        clips.append(seg)
        print(f"clip {i}: {seg['start']:.1f}s -> {seg['end']:.1f}s "
              f"(score {seg['score']}) -> {name}")

    if args.concat and len(clips) > 1:
        reel = os.path.join(outdir, f"{stem}_highlights.mp4")
        concat_clips([os.path.join(outdir, c["file"]) for c in clips], reel)
        print(f"highlight reel -> {reel}")

    with open(os.path.join(outdir, "clips.json"), "w", encoding="utf-8") as f:
        json.dump(clips, f, indent=2, ensure_ascii=False)
    print(f"wrote {os.path.join(outdir, 'clips.json')}")


if __name__ == "__main__":
    main()
