#!/usr/bin/env python3
"""
gopro_gps_srt.py — Generate SRT subtitle files with interpolated GPS UTC times
                   from GoPro MP4(s) that have embedded GPMF telemetry.

REQUIREMENTS
------------
System packages (Ubuntu/Debian):
    sudo apt update
    sudo apt install -y libimage-exiftool-perl python3

  - libimage-exiftool-perl  provides the `exiftool` binary, which reads the
                            GoPro GPMF metadata track natively.
  - python3                 standard library only; no pip packages needed.

Optional (for the mux/burn-in step, not used by this script directly):
    sudo apt install -y ffmpeg

GoPro camera requirements:
  - GPS must have been ENABLED at recording time (Regional Settings on camera).
  - Supported models with GPS: HERO5-HERO11, HERO13, MAX, MAX2, Fusion.
    NOTE: HERO12 does NOT record GPS.

USAGE
-----
    python3 gopro_gps_srt.py GH010039.MP4                   # one file
    python3 gopro_gps_srt.py GH*.MP4                        # shell expands glob
    python3 gopro_gps_srt.py "GH*.MP4"                      # script expands glob
    python3 gopro_gps_srt.py --offset -1.2 GH010039.MP4     # tune chip-lag offset

For very large batches that exceed bash's argument length:
    find . -name 'GH*.MP4' -print0 | xargs -0 -n 50 python3 gopro_gps_srt.py

OUTPUT
------
For each input <name>.MP4, writes <name>.srt next to it.

TIMING NOTES
------------
GoPro's GPSU timestamps are emitted with a small but consistent sub-second
lag (commonly ~0.8s) and the firmware can add another ~1s on top. The default
--offset of -0.8 corrects the observable chip lag; tune it empirically by
comparing the SRT against a ground-truth clock in the footage.
"""

import argparse, subprocess, sys, os, glob, re
from datetime import datetime, timedelta

HZ = 10                       # SRT entries per second (10 = ticks every 100 ms)
MAX_DURATION_SEC = 6 * 3600   # sanity cap; raise if you really record longer clips
JUMP_THRESHOLD_SEC = 5.0      # gap that splits a "run" of monotonic GPS samples
DEFAULT_OFFSET_SEC = -2.2     # subtract from epoch to cancel GoPro GPS chip lag

# GoPro speed-up/timelapse exports (e.g. A01_32x.MP4, B01_64x.MP4) are derived
# files that don't carry the GPMF telemetry track, so SRT generation is
# impossible. Skip them silently.
SPEEDUP_RE = re.compile(r'\d+x\.mp4$', re.IGNORECASE)


def srt_time(secs):
    """Format seconds as SRT timestamp HH:MM:SS,mmm."""
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    ms = int(round((s - int(s)) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{ms:03d}"


def get_video_duration(video):
    """Get the video's actual duration in seconds from the MP4 container."""
    try:
        out = subprocess.check_output(
            ['exiftool', '-api', 'LargeFileSupport=1',
             '-n', '-Duration', '-s3', video],
            text=True, stderr=subprocess.DEVNULL).strip()
        return float(out) if out else None
    except (subprocess.CalledProcessError, ValueError):
        return None


def longest_monotonic_run(samples, jump_threshold=JUMP_THRESHOLD_SEC):
    """samples: list of (video_time_sec, utc_datetime). Return the longest run
    of samples whose UTC values increase monotonically with gaps < jump_threshold.

    GoPro receivers sometimes emit stale/cached GPS timestamps for the first
    few seconds before getting a fresh lock, then jump to the real UTC. The
    longest monotonic run is almost always the real recording."""
    if not samples:
        return []
    runs = []
    current = [samples[0]]
    for i in range(1, len(samples)):
        gap = (samples[i][1] - current[-1][1]).total_seconds()
        if 0 < gap < jump_threshold:
            current.append(samples[i])
        else:
            runs.append(current)
            current = [samples[i]]
    runs.append(current)
    return max(runs, key=len)


def process(video, hz=HZ, offset=DEFAULT_OFFSET_SEC):
    output = os.path.splitext(video)[0] + '.srt'

    try:
        out = subprocess.check_output(
            ['exiftool', '-ee', '-api', 'LargeFileSupport=1',
             '-p', '$SampleTime | $GPSDateTime', '-q', '-q', video],
            text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"  [skip] exiftool failed: {e}")
        return
    except FileNotFoundError:
        sys.exit("error: exiftool not found. "
                 "Install: sudo apt install libimage-exiftool-perl")

    # Parse each "SampleTime | GPSDateTime" row. Apply year sanity bounds so
    # pre-lock samples that carry year 0000 / 2021 garbage are dropped here.
    samples = []          # list of (video_time_sec, utc_datetime)
    for line in out.splitlines():
        if '|' not in line:
            continue
        st_str, ts_str = (p.strip() for p in line.split('|', 1))
        if st_str.endswith(' s'):
            st_str = st_str[:-2].strip()
        try:
            video_t = float(st_str)
        except ValueError:
            continue
        ts_str = ts_str.rstrip('Z').strip()
        if not ts_str:
            continue
        for fmt in ('%Y:%m:%d %H:%M:%S.%f', '%Y:%m:%d %H:%M:%S'):
            try:
                dt = datetime.strptime(ts_str, fmt)
                if 2010 <= dt.year <= 2100:
                    samples.append((video_t, dt))
                break
            except ValueError:
                pass

    if len(samples) < 2:
        print(f"  [skip] {video}: only {len(samples)} valid GPS samples "
              f"(was GPS on?)")
        return

    n_raw = len(samples)

    # Discard pre-lock outliers: receivers sometimes emit stale cached UTC
    # before real lock, then jump years/days when the real fix arrives. Keep
    # the longest run of samples spaced < JUMP_THRESHOLD_SEC apart.
    kept = longest_monotonic_run(samples)
    if len(kept) < 2:
        print(f"  [skip] {video}: no usable GPS run (saw {n_raw} samples)")
        return
    n_discarded = n_raw - len(kept)

    # Back-project to UTC at video t=0 using the first kept sample's actual
    # video-time (from exiftool's $SampleTime), then apply offset to cancel
    # the GoPro GPS chip's reporting lag.
    first_video_t, first_utc = kept[0]
    last_video_t,  last_utc  = kept[-1]
    epoch = first_utc - timedelta(seconds=first_video_t) \
                      + timedelta(seconds=offset)

    span = last_video_t + 1.0

    # Cross-check against the video container's reported duration. The
    # container is the source of truth for length; GPS can stop early or
    # have gaps.
    vid_dur = get_video_duration(video)
    if vid_dur and vid_dur > 0:
        duration = min(span, vid_dur + 5.0)
        # If GPS run is much shorter than the video, still cover the whole
        # video timeline using the back-projected epoch.
        duration = max(duration, vid_dur)
    else:
        duration = span

    if duration > MAX_DURATION_SEC:
        print(f"  [skip] {video}: computed duration {duration:.0f}s exceeds "
              f"{MAX_DURATION_SEC}s cap - bad timestamps?")
        print(f"        first kept GPS: {first_utc}  (video t={first_video_t:.2f}s)")
        print(f"        last  kept GPS: {last_utc}  (video t={last_video_t:.2f}s)")
        return

    interval = 1.0 / hz
    n = int(duration * hz)

    with open(output, 'w') as f:
        for i in range(n):
            t   = i * interval
            utc = epoch + timedelta(seconds=t)
            f.write(f"{i+1}\n{srt_time(t)} --> {srt_time(t+interval)}\n")
            f.write(utc.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ' UTC\n\n')

    sz = os.path.getsize(output)
    note = f", discarded {n_discarded} pre-lock samples" if n_discarded else ""
    print(f"  [ok] {video} -> {output} "
          f"({n} entries, {duration:.1f}s, {sz/1024:.1f} KB{note})")


# ---- entry point ----
def main():
    ap = argparse.ArgumentParser(
        description="Generate SRT files with UTC times from GoPro MP4 telemetry.")
    ap.add_argument('--offset', type=float, default=DEFAULT_OFFSET_SEC,
                    help=f"Seconds to add to back-projected epoch to cancel "
                         f"GoPro GPS chip lag (default {DEFAULT_OFFSET_SEC}).")
    ap.add_argument('--hz', type=int, default=HZ,
                    help=f"SRT entries per second (default {HZ}).")
    ap.add_argument('files', nargs='+',
                    help="MP4 files or glob patterns.")
    args = ap.parse_args()

    files = []
    for arg in args.files:
        matched = glob.glob(arg)
        files.extend(matched if matched else [arg])

    for v in files:
        if not os.path.isfile(v):
            print(f"  [skip] not a file: {v}")
            continue
        if SPEEDUP_RE.search(v):
            print(f"  [skip] speed-up export (no GPMF): {v}")
            continue
        print(f"Processing {v}...")
        process(v, hz=args.hz, offset=args.offset)


if __name__ == '__main__':
    main()
