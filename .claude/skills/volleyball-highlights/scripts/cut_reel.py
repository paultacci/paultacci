#!/usr/bin/env python3
"""
Stage 2 of the volleyball-highlights skill.

Takes score-change timestamps (found by Claude reading contact sheets in
stage 1) plus the audio RMS log, locates the actual loud moment just before
each score update (the scoreboard lags the play), cuts one clip per rally
around that moment, and stitches them into a single reel.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def require(binary: str) -> None:
    if shutil.which(binary) is None:
        sys.exit(f"error: '{binary}' not found on PATH.")


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def probe_duration(path: Path) -> float | None:
    if shutil.which("ffprobe"):
        result = run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ])
        if result.returncode == 0 and result.stdout.strip():
            try:
                return float(result.stdout.strip())
            except ValueError:
                pass
    result = run(["ffmpeg", "-i", str(path)])
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def find_peak(rms_points: list[tuple[float, float]], start: float, end: float) -> float | None:
    window = [(t, v) for t, v in rms_points if start <= t <= end]
    if not window:
        return None
    return max(window, key=lambda p: p[1])[0]


def compute_clip_windows(
    events: list[dict],
    rms_points: list[tuple[float, float]],
    lookback: float,
    pad_before: float,
    pad_after: float,
    max_clip: float,
    merge_gap: float,
    duration: float,
    no_audio_window: float = 12.0,
) -> list[tuple[float, float]]:
    """With audio: anchor each clip on the loudest moment shortly before the score
    change (the actual play), then pad around it. Without audio (globally, or just
    no data in a given event's lookback window -- e.g. near the start of the video),
    there's no peak to anchor on, so fall back to a fixed window ending at the score
    change: [t - no_audio_window, t + pad_after]. Less precise, but scoreboard-only."""
    raw: list[tuple[float, float]] = []
    for ev in events:
        t = float(ev["score_change_time"])
        peak = find_peak(rms_points, max(0.0, t - lookback), t + 2.0) if rms_points else None
        if peak is not None:
            start = max(0.0, peak - pad_before)
            end = min(duration, max(peak + pad_after, t + 1.0))
        else:
            start = max(0.0, t - no_audio_window)
            end = min(duration, t + pad_after)
        if end - start > max_clip:
            start = end - max_clip
        raw.append((start, end))

    raw.sort()
    merged: list[list[float]] = []
    for start, end in raw:
        if merged and start - merged[-1][1] <= merge_gap:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


def cut_clip(source: Path, start: float, end: float, out_path: Path) -> bool:
    expected_len = end - start
    cmd = [
        "ffmpeg", "-y", "-ss", f"{start:.2f}", "-to", f"{end:.2f}",
        "-i", str(source), "-c", "copy", "-avoid_negative_ts", "make_zero", str(out_path),
    ]
    result = run(cmd)
    if result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
        actual_len = probe_duration(out_path)
        # Stream copy can only cut on keyframes; with a sparse-keyframe source it can silently
        # snap to a keyframe far from the intended point and produce a wildly wrong-length clip.
        tolerance = max(2.0, 0.25 * expected_len)
        if actual_len is not None and abs(actual_len - expected_len) <= tolerance:
            return True
    # Fallback: re-encode for a frame-accurate cut instead of a keyframe-aligned one.
    cmd = [
        "ffmpeg", "-y", "-ss", f"{start:.2f}", "-to", f"{end:.2f}",
        "-i", str(source), "-c:v", "libx264", "-c:a", "aac", str(out_path),
    ]
    result = run(cmd)
    return result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0


def stitch_reel(clip_paths: list[Path], reel_path: Path, workdir: Path) -> None:
    list_file = workdir / "concat_list.txt"
    list_file.write_text("".join(f"file '{p.resolve()}'\n" for p in clip_paths))
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(reel_path)]
    result = run(cmd)
    if result.returncode != 0:
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
                "-c:v", "libx264", "-c:a", "aac", str(reel_path)]
        result = run(cmd)
        if result.returncode != 0:
            sys.exit(f"error: reel stitching failed\n{result.stderr[-2000:]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="Source video path (same one used in prepare.py)")
    ap.add_argument("--rms", required=True, help="rms.json produced by prepare.py")
    ap.add_argument("--events", required=True,
                     help="JSON file: list of {\"score_change_time\": seconds, \"note\": \"...\"}")
    ap.add_argument("--duration", type=float, required=True, help="Video duration in seconds")
    ap.add_argument("--outdir", required=True, help="Directory to write individual clips into")
    ap.add_argument("--reel", required=True, help="Output path for the stitched highlight reel")
    ap.add_argument("--lookback", type=float, default=20.0,
                     help="Seconds before a score change to search for the play's loud peak")
    ap.add_argument("--pad-before", type=float, default=6.0, help="Seconds to keep before the peak")
    ap.add_argument("--pad-after", type=float, default=3.0, help="Seconds to keep after the peak")
    ap.add_argument("--max-clip", type=float, default=18.0, help="Hard cap on clip length (seconds)")
    ap.add_argument("--merge-gap", type=float, default=4.0,
                     help="Merge two candidate clips if closer together than this (seconds)")
    ap.add_argument("--no-audio-window", type=float, default=12.0,
                     help="Fixed seconds before a score change to include when there's no audio "
                          "peak to anchor on (no audio track, or silence near that timestamp)")
    args = ap.parse_args()

    require("ffmpeg")

    source = Path(args.input).expanduser().resolve()
    events = json.loads(Path(args.events).read_text())
    rms_points = [tuple(p) for p in json.loads(Path(args.rms).read_text())]

    if not events:
        sys.exit("error: no events provided -- nothing to cut")

    if not rms_points:
        print("note: no audio data -- clips will be timed from the scoreboard alone "
              f"(fixed {args.no_audio_window:.0f}s window before each score change)")

    windows = compute_clip_windows(
        events, rms_points, args.lookback, args.pad_before, args.pad_after,
        args.max_clip, args.merge_gap, args.duration, args.no_audio_window,
    )

    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    clip_paths = []
    for i, (start, end) in enumerate(windows, start=1):
        clip_path = outdir / f"clip_{i:03d}_{int(start)}s.mp4"
        print(f"Cutting clip {i}/{len(windows)}: {start:.1f}s - {end:.1f}s -> {clip_path.name}")
        if cut_clip(source, start, end, clip_path):
            clip_paths.append(clip_path)
        else:
            print(f"  warning: failed to cut clip {i}, skipping")

    if not clip_paths:
        sys.exit("error: all clip cuts failed")

    reel_path = Path(args.reel).expanduser().resolve()
    reel_path.parent.mkdir(parents=True, exist_ok=True)
    stitch_reel(clip_paths, reel_path, outdir)

    print(f"\nDone. {len(clip_paths)} clip(s) in {outdir}")
    print(f"Stitched reel: {reel_path}")


if __name__ == "__main__":
    main()
