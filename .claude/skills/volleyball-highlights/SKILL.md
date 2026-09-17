---
name: volleyball-highlights
description: Turn a raw, uncommentated multi-cam volleyball match video (YouTube URL or local file) into a highlight reel by reading the burned-in scoreboard and pinpointing the loud moment before each score change. Use when the user asks to make a highlight reel, clip highlights, or find key plays from volleyball (or similar scoreboard-overlay sports) game footage.
---

# Volleyball Highlights

Builds a highlight reel from raw gym-cam volleyball footage that has **no commentary** but **does** have a burned-in scoreboard overlay. There's no ML highlight model here — the reliable signal is: the scoreboard changes when a point is scored, and the scoreboard is slow to update, so the real action (the kill/ace/big rally) happened a few seconds *before* the number on screen changes. The pipeline finds score changes visually, then finds the loudest moment (crowd reaction, ball contact) just before each one, and cuts around that.

Two scripts do all the mechanical ffmpeg/yt-dlp work (`scripts/prepare.py`, `scripts/cut_reel.py`). The one thing they can't do is *look at the scoreboard* — that's the step you (Claude) do directly, since it needs actual vision and judgment (misreads, obstructed views, set changes, referee resets).

## Prerequisites

Check once per environment, don't assume they're installed:

```bash
which ffmpeg ffprobe   # required always
which yt-dlp           # only required if the source is a YouTube URL
```

If missing, install with the environment's package manager (e.g. `apt-get install -y ffmpeg`, `brew install ffmpeg yt-dlp`, or `pip install yt-dlp`). Don't proceed until `ffmpeg`/`ffprobe` are on PATH.

## Step 1 — Prepare (mechanical, run the script)

```bash
python3 .claude/skills/volleyball-highlights/scripts/prepare.py \
  --input "<youtube-url-or-local-path>" \
  --workdir /tmp/vb-highlights/<match-name> \
  --frame-interval 4 \
  --grid 5x6
```

This downloads the video (if a URL), extracts an audio loudness log (`rms.json`), and builds numbered contact-sheet JPEGs in `<workdir>/sheets/` — grids of small sampled frames, `sheet_0001.jpg`, `sheet_0002.jpg`, etc. It also writes `manifest.json` with the exact formula for turning a sheet+cell position into a timestamp, and prints the total sheet count.

If the scoreboard is small/hard to read in a full frame, rerun with `--scoreboard-crop "w,h,x,y"` (ffmpeg crop syntax, pixels) once you know roughly where it sits on screen — look at one sample frame first if needed (`ffmpeg -ss 30 -i <video> -frames:v 1 sample.jpg`) to figure out the crop box.

## Step 2 — Read the scoreboard (you do this, not a script)

Read `manifest.json` for `frame_interval`, `grid_cols`, `cells_per_sheet`. Then, **for each contact sheet in order**, use the Read tool to view the image and track both teams' scores cell by cell, left-to-right, top-to-bottom, sheet by sheet.

For every cell where a score just ticked up from the previous cell, record the timestamp of *that* cell using:

```
timestamp = ((sheet_number - 1) * cells_per_sheet + row * grid_cols + col) * frame_interval
```

Rules of thumb while reading:
- **Normal increment (+1 to one team):** record it as an event.
- **Jump of +2 or more:** the sampling interval likely skipped over a point (or two rallies happened close together) — still record one event at that timestamp; the audio-peak step later can usually still isolate the more recent rally. Don't try to interpolate a fake in-between timestamp.
- **Score resets to 0-0 (or drops to a much lower number on both sides):** that's a new set boundary, not a misread — skip it, don't record an event.
- **A single team's score decreases (and it's not a full-match reset):** that's almost always an OCR/reading error on your part or a camera obstruction — re-check the neighboring cells before trusting it, and skip if it doesn't resolve.
- **Scoreboard fully obstructed or off-screen in a cell:** skip that cell, don't guess.

Write the final list to a JSON file, e.g. `/tmp/vb-highlights/<match-name>/events.json`:

```json
[
  {"score_change_time": 143.0, "note": "home 12->13"},
  {"score_change_time": 289.0, "note": "away 8->9"}
]
```

This step is the one part of the pipeline that's genuinely slow (one vision read per contact sheet) — for a long match this may be dozens of sheets. Work through them systematically rather than sampling a subset, since a missed sheet is a missed point.

## Step 3 — Cut and stitch (mechanical, run the script)

Get the video duration from `manifest.json` (`duration_seconds`), then:

```bash
python3 .claude/skills/volleyball-highlights/scripts/cut_reel.py \
  --input "<same path prepare.py used — check manifest.json's source_video>" \
  --rms /tmp/vb-highlights/<match-name>/rms.json \
  --events /tmp/vb-highlights/<match-name>/events.json \
  --duration <duration_seconds> \
  --outdir /tmp/vb-highlights/<match-name>/clips \
  --reel /tmp/vb-highlights/<match-name>/highlight_reel.mp4
```

This finds the loudest audio moment in the ~20s before each score-change timestamp (the actual play), cuts a clip padded around it, merges clips that land close together, and stitches everything into `highlight_reel.mp4`. Individual clips remain in `clips/` for review before sharing anything.

Useful tuning flags if the defaults feel off after watching the output:
- `--lookback` — widen if the board is very slow to update, narrow if unrelated plays are getting swept in.
- `--pad-before` / `--pad-after` — how much runway around the peak moment.
- `--max-clip` — hard ceiling per clip (prevents runaway clips when the peak-to-score-change gap is large).
- `--merge-gap` — how close two events need to be to combine into one clip instead of two.

## Step 4 — Hand off

Tell the user where `highlight_reel.mp4` and the individual `clips/` ended up, and how many highlights were found. Suggest they skim the reel before uploading anywhere — this is a heuristic (loudness + scoreboard), not certainty, so it will occasionally include a false positive (whistle, timeout, crowd noise unrelated to a kill) or miss a quiet-crowd point.

## Known limitations (be upfront about these)

- No commentary/captions means there's no semantic signal — this is loudness + scoreboard timing only, tuned by hand, not a highlight-quality model. It doesn't know a great defensive dig from a lucky net roll unless the crowd reacts.
- If the venue is quiet (small crowd, no PA), the audio-peak step is less reliable; consider using ffmpeg motion/scene-change detection as an additional anchor if this becomes a problem often — not implemented yet.
- The contact-sheet tile filter drops trailing frames that don't fill a complete grid, so the last few seconds of the match may not get sampled. Use a smaller `--grid` or `--frame-interval` if the match's final point matters.
- This is per-match manual-ish work (you read every contact sheet) — it trades subscription cost for your time reading images. If that trade stops being worth it for high volume, revisit with a real vision-based action-spotting model.
