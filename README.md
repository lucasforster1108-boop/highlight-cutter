[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md) | [한국어](README_ko.md)

# highlight-cutter

I keep downloading two-hour videos, watching twenty minutes, and never
coming back. So I wrote this: it finds the most intense parts of a long
video and cuts them into a short highlight reel first. If the highlights
are good, I'll make time for the full thing.

It reads one of two signals:

- **A funscript** sitting next to the video (same name, `.funscript`).
  It scores every 10-second window by how much action is packed into it —
  how many actions there are and how far they move.
- **The audio track.** No script? It measures volume instead and picks
  the loudest stretches. Plenty of videos give themselves away this way.

Everything runs locally. No uploads, no accounts, no API keys.

## Install

You need Python 3 and ffmpeg (with ffprobe) on your PATH. That's it —
the script only uses the Python standard library.

```bash
# Debian / Ubuntu
sudo apt install ffmpeg
# macOS
brew install ffmpeg
# Windows
winget install ffmpeg
```

## Usage

```bash
# auto: uses the funscript if one is there, audio if not
python3 cut.py movie.mp4

# force a mode, take the top 5 moments, 5s of padding on each side
python3 cut.py movie.mp4 --mode script --top 5 --pad 5

# also stitch the clips into a single highlight reel
python3 cut.py movie.mp4 --concat -o highlights/
```

Output lands in `<video>_highlights/` (or your `-o` folder):

- `movie_clip01_123s.mp4`, … — the clips themselves
- `movie_highlights.mp4` — only with `--concat`, all clips joined
- `clips.json` — every segment's start, end, duration, score and mode,
  so you can re-cut or post-process without running the detection again

## Parameters

| Flag | Default | What it does |
| --- | --- | --- |
| `--script` | same name as video | Path to the funscript, if it isn't next to the video |
| `--mode` | `auto` | `auto` / `script` / `audio`. Auto = script when a `.funscript` is found, else audio |
| `--top` | 5 | How many highlight segments to pick |
| `--pad` | 5 | Seconds of breathing room added before and after each segment |
| `--merge-gap` | 30 | Segments closer than this (seconds) get merged into one |
| `--concat` | off | Also join the clips into one highlight reel |
| `-o` | `<video>_highlights` | Output directory |

## How scoring works

Both modes slide a 10-second window over the video, one second at a
time. Script mode scores a window by total position change plus a
per-action bonus; audio mode by summed RMS volume. Then it greedily
takes the strongest window, ignores everything within `--merge-gap`
seconds of it, and repeats until it has `--top` segments. Padded
segments that end up close together are merged.

Clips are **re-encoded** (libx264 + AAC), not stream-copied. That is
deliberate: stream copy can only cut on keyframes, so your "highlight"
could start several seconds early in the middle of the previous scene.
Re-encoding cuts exactly where the score says. The price is speed.

## Limitations

- **Intense is not the same as good.** The tool finds the busiest or
  loudest moments. Sometimes that's the main event; sometimes it's a
  shouting match or a camera being dropped. It narrows two hours down
  to ten minutes — the final judgement is still yours.
- **Scores are relative to the video itself.** A quiet, slow video
  still produces a top 5; they're just the least quiet parts. Tune
  `--top` and `--merge-gap` per video instead of trusting defaults
  blindly — dialogue-heavy videos do better in script mode, and
  music-driven ones can fool audio mode completely.
- **Re-encoding is slow.** A two-hour 1080p source takes a while to
  slice up. Run it, go make tea.
- Audio mode needs an audio track (sounds obvious, but silent screen
  recordings exist, and they fail with an error instead of a guess).

## Tests

Fully synthetic test assets (an ffmpeg test pattern plus sine bursts —
no real footage). `tests/run_tests.py` verifies that both modes find
the three planted bursts, that clip files match `clips.json`, and that
`--concat` produces a reel. See `tests/RESULTS.md`.

## License

MIT
