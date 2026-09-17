#!/usr/bin/env python3
"""
Stage 1 of the volleyball-highlights skill.

Downloads/locates the source video, extracts an audio RMS-level log (for
finding the loud moment of a play), and builds scoreboard "contact sheet"
images (grids of sampled frames) that Claude reads visually to spot score
changes. Everything here is mechanical (ffmpeg/yt-dlp); no video judgment
happens in this script.
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
        sys.exit(
            f"error: '{binary}' not found on PATH.\n"
            f"Install it first (e.g. 'apt install {binary}' / 'brew install {binary}')."
        )


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def ffprobe_duration(path: Path) -> float:
    """Prefer ffprobe; fall back to parsing ffmpeg's own stderr banner if ffprobe
    isn't installed (e.g. pip-installed imageio-ffmpeg ships ffmpeg but not ffprobe)."""
    if shutil.which("ffprobe"):
        result = run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ])
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())

    result = run(["ffmpeg", "-i", str(path)])
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        sys.exit(f"error: could not determine duration of {path} (ffprobe missing and ffmpeg banner unparseable)")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def acquire_source(source: str, workdir: Path) -> Path:
    if re.match(r"^https?://", source):
        require("yt-dlp")
        dest = workdir / "source.mp4"
        cmd = [
            "yt-dlp", "-f", "bv*[ext=mp4]+ba[ext=mp4]/mp4/best",
            "-o", str(dest), source,
        ]
        print(f"$ {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0 or not dest.exists():
            sys.exit("error: yt-dlp download failed")
        return dest
    path = Path(source).expanduser().resolve()
    if not path.exists():
        sys.exit(f"error: input file not found: {path}")
    return path


def extract_audio_rms(video: Path, workdir: Path, window_seconds: float) -> Path:
    """One ffmpeg pass: resample audio, chop into fixed windows, log RMS dB per window."""
    log_path = workdir / "rms.log"
    sample_rate = 22050
    n_samples = int(sample_rate * window_seconds)
    filt = (
        f"aformat=sample_rates={sample_rate}:channel_layouts=mono,"
        f"asetnsamples=n={n_samples}:p=0,"
        f"astats=metadata=1:reset=1,"
        f"ametadata=print:key=lavfi.astats.Overall.RMS_level:file={log_path}"
    )
    cmd = ["ffmpeg", "-y", "-i", str(video), "-vn", "-af", filt, "-f", "null", "-"]
    print(f"$ {' '.join(cmd)}")
    result = run(cmd)
    if result.returncode != 0:
        sys.exit(f"error: ffmpeg audio analysis failed\n{result.stderr[-2000:]}")
    if not log_path.exists():
        sys.exit("error: expected rms.log was not produced (does the source have an audio track?)")
    return log_path


def parse_rms_log(log_path: Path) -> list[tuple[float, float]]:
    time_re = re.compile(r"pts_time:([0-9.]+)")
    rms_re = re.compile(r"RMS_level=(-?[0-9.]+|-inf|nan)")
    points: list[tuple[float, float]] = []
    current_time = None
    for line in log_path.read_text(errors="ignore").splitlines():
        tmatch = time_re.search(line)
        if tmatch:
            current_time = float(tmatch.group(1))
            continue
        rmatch = rms_re.search(line)
        if rmatch and current_time is not None:
            raw = rmatch.group(1)
            value = -120.0 if raw in ("-inf", "nan") else float(raw)
            points.append((current_time, value))
    return points


def build_contact_sheets(
    video: Path, workdir: Path, interval: float, cols: int, rows: int, crop: str | None
) -> tuple[Path, int]:
    sheets_dir = workdir / "sheets"
    sheets_dir.mkdir(exist_ok=True)
    cells = cols * rows
    vf_parts = []
    if crop:
        w, h, x, y = crop.split(",")
        vf_parts.append(f"crop={w}:{h}:{x}:{y}")
    vf_parts.append(f"fps=1/{interval}")
    vf_parts.append("scale=320:-1")
    vf_parts.append(f"tile={cols}x{rows}")
    vf = ",".join(vf_parts)
    out_pattern = str(sheets_dir / "sheet_%04d.jpg")
    cmd = ["ffmpeg", "-y", "-i", str(video), "-vf", vf, "-q:v", "3", "-vsync", "vfr", out_pattern]
    print(f"$ {' '.join(cmd)}")
    result = run(cmd)
    if result.returncode != 0:
        sys.exit(f"error: ffmpeg contact-sheet generation failed\n{result.stderr[-2000:]}")
    sheet_files = sorted(sheets_dir.glob("sheet_*.jpg"))
    if not sheet_files:
        sys.exit("error: no contact sheets were produced -- check --frame-interval/--grid vs video length")
    return sheets_dir, len(sheet_files)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="YouTube URL or local video file path")
    ap.add_argument("--workdir", required=True, help="Directory for all intermediate/output files")
    ap.add_argument("--frame-interval", type=float, default=4.0,
                     help="Seconds between sampled scoreboard frames (default: 4)")
    ap.add_argument("--audio-window", type=float, default=0.5,
                     help="Seconds per audio RMS measurement window (default: 0.5)")
    ap.add_argument("--grid", default="5x6", help="Contact sheet grid as COLSxROWS (default: 5x6)")
    ap.add_argument("--scoreboard-crop", default=None,
                     help="Optional 'w,h,x,y' crop to the scoreboard region before sampling")
    args = ap.parse_args()

    require("ffmpeg")

    workdir = Path(args.workdir).expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    cols, rows = (int(v) for v in args.grid.lower().split("x"))

    video = acquire_source(args.input, workdir)
    duration = ffprobe_duration(video)

    rms_log = extract_audio_rms(video, workdir, args.audio_window)
    rms_points = parse_rms_log(rms_log)
    rms_json = workdir / "rms.json"
    rms_json.write_text(json.dumps(rms_points))

    sheets_dir, n_sheets = build_contact_sheets(
        video, workdir, args.frame_interval, cols, rows, args.scoreboard_crop
    )

    cells_per_sheet = cols * rows
    manifest = {
        "source_video": str(video),
        "duration_seconds": duration,
        "frame_interval": args.frame_interval,
        "grid_cols": cols,
        "grid_rows": rows,
        "cells_per_sheet": cells_per_sheet,
        "sheet_count": n_sheets,
        "sheets_dir": str(sheets_dir),
        "rms_json": str(rms_json),
        "rms_window_seconds": args.audio_window,
        "note": (
            "Timestamp of the cell at row r, col c (0-indexed) in sheet_XXXX.jpg "
            "(XXXX is 1-based) = ((XXXX-1) * cells_per_sheet + r*grid_cols + c) * frame_interval. "
            "If total frames don't divide evenly into the grid, the final sheet's leftover "
            "cells are padded solid black (not a real frame) -- ignore those when reading scores."
        ),
    }
    manifest_path = workdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(f"\nDone. {n_sheets} contact sheet(s) in {sheets_dir}")
    print(f"Manifest: {manifest_path}")
    print("Next: read each sheet image and log score-change timestamps, per SKILL.md.")


if __name__ == "__main__":
    main()
