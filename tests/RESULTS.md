# Test results

Synthetic assets only — no real footage. `tests/make_assets.py` builds a
180s testsrc2 video with a quiet sine bed and three loud bursts at
20–30s, 80–90s and 140–150s, plus a funscript that is dense/large in
exactly those windows and sparse/tiny elsewhere.

Run: `python3 tests/run_tests.py`

```
== script mode (--top 3)
clip 1: 15.0s -> 35.0s (score 6610.0)
clip 2: 75.0s -> 95.0s (score 6610.0)
clip 3: 135.0s -> 155.0s (score 6510.0)
PASS script: 3 clips, all bursts hit, durations match

== audio mode (--top 3)
clip 1: 15.0s -> 35.0s (score 0.8)
clip 2: 75.0s -> 95.0s (score 0.8)
clip 3: 135.0s -> 155.0s (score 0.8)
PASS audio: 3 clips, all bursts hit, durations match

PASS concat: reel exists, 60.0s
ALL TESTS PASSED
```

Auto mode was also checked by hand: with `test.funscript` sitting next
to `test.mp4` it picks script mode and produces the same segments.

Notes:
- Segments are the 10s peak window padded by 5s on both sides, so each
  10s burst lands as a 20s clip centred on it.
- Clip durations in clips.json matched the actual files (ffprobe)
  within 1.5s in every case; the reel is exactly 3 × 20s = 60.0s.
- Environment: ffmpeg 8.1.2, Python 3.12, no pip installs needed.
