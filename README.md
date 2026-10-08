# GoPro GPS Date-Time SRT file creator

Generate `.srt` subtitle files that show the interpolated GPS UTC time at every frame, from GoPro `.MP4` clips with embedded GPMF telemetry. The SRT can then be burned into the video with ffmpeg or used as a reference track in editors.  Useful when when watching video of a flight to correspond events to GPS time for later review of flight data.

## What's in this repo

- `gopro_gps_srt.py` — the generator. Python 3, stdlib only. Shells out to `exiftool` to read GPMF.
- `gopro-srt.sh` — Linux/macOS one-click launcher: runs the generator over every `*.mp4` next to it.
- `gopro-srt.bat` — Windows equivalent.

## Requirements

- Python 3 (no pip packages needed)
- `exiftool` on `PATH`

### Linux / macOS

```bash
sudo apt install -y libimage-exiftool-perl python3   # Debian/Ubuntu
brew install exiftool                                # macOS
```

`exiftool` lands on `PATH`. Nothing else to configure — `gopro-srt.sh` just calls it.

### Windows

exiftool is **not** on `PATH` by default on most Windows installs, so `gopro-srt.bat` looks for `exiftool.exe` in three places and uses the first hit:

1. `%EXIFTOOL_DIR%` — set it as a real environment variable (`setx EXIFTOOL_DIR "C:\Tools\exiftool"`), or uncomment and edit this line near the top of the script:

   ```batch
   rem set "EXIFTOOL_DIR=C:\Tools\exiftool"
   ```

2. The script's own folder — just drop `exiftool.exe` next to `gopro-srt.bat`.
3. `PATH`.

It prints which one it used, and if none of them pan out it tells you so and stops without touching anything. Nothing is hardcoded to a particular machine.

Download exiftool from <https://exiftool.org/> if you don't have it. If you take the standalone Windows build, rename `exiftool(-k).exe` to `exiftool.exe` first, or it will wait for a keypress and never return.

The batch file prefers the `py` launcher and falls back to `python.exe`.

#### Optional: self-cleanup

If you work by copying these three files into each folder of footage, set this near the top of `gopro-srt.bat`:

```batch
set "CLEANUP=1"
```

On a **successful** run the script then deletes `gopro_gps_srt.py`, `gopro-srt.sh` and itself, leaving just the MP4s and the new `.srt` files. It is `0` by default, and a failed run never deletes anything.

## Usage

Drop `gopro-srt.bat` (Windows) or `gopro-srt.sh` (Linux/macOS) into a folder of GoPro `.MP4` files and run it. One `.srt` is written next to each MP4. Speed-up exports (`*32x.MP4`, `*64x.MP4`, …) are skipped — they don't carry the GPMF telemetry track (see [Speed-up / timelapse filter](#speed-up--timelapse-filter) below if you want to change which files are skipped).

Direct invocation:

```bash
python3 gopro_gps_srt.py GH010039.MP4
python3 gopro_gps_srt.py *.MP4
python3 gopro_gps_srt.py --offset -1.5 GH010039.MP4
python3 gopro_gps_srt.py --hz 30 GH010039.MP4
```

GoPro models that record GPS: HERO5–HERO11, HERO13, MAX, MAX2, Fusion. **HERO12 does not record GPS.** GPS must also have been enabled in the camera's Regional Settings at recording time.

## The `--offset` flag

GoPro's embedded GPS UTC (the `GPSU` field in GPMF) is not perfectly aligned with wall-clock time. Two effects compound:

1. **GPS chip processing latency.** Each fix is reported roughly 0.8s after it actually occurred. You can see this in the raw GPMF: the sub-second portion of every `GPSDateTime` row is consistently `.799` on a HERO11.
2. **Firmware buffering.** The GoPro adds about another second on top.

Without correction, the SRT runs roughly **2 seconds ahead** of reality on a HERO11. The default `--offset -2.2` cancels this; the value was measured against a ground-truth clock visible in the footage.

If a different camera or firmware version shows a different lag, tune empirically:

```bash
python3 gopro_gps_srt.py --offset -1.8 GH010039.MP4
```

Compare the new SRT against a known clock in-frame. Once a value works across multiple clips, change `DEFAULT_OFFSET_SEC` near the top of `gopro_gps_srt.py` so you don't have to pass `--offset` each run.

## Speed-up / timelapse filter

Speed-up and timelapse files named like `A01_32x.MP4`, `B02_64x.MP4`, `_8x.MP4`, etc. are re-encoded from the original clip and **don't carry the GPMF telemetry track**, so SRT generation isn't possible. The script silently skips any file whose name ends in `<digits>x.MP4`.

The match is a single regex near the top of `gopro_gps_srt.py`:

```python
SPEEDUP_RE = re.compile(r'\d+x\.mp4$', re.IGNORECASE)
```

That covers every `2x`, `4x`, `8x`, `15x`, `30x`, `32x`, `60x`, `64x` etc. ending. To change the behaviour:

- **Skip more patterns** — e.g. also skip files ending in `_PROXY.MP4`:
  ```python
  SPEEDUP_RE = re.compile(r'(\d+x|_PROXY)\.mp4$', re.IGNORECASE)
  ```
- **Skip fewer patterns** — e.g. allow `32x` and `64x` through (in case a future firmware does start writing GPMF into them) but keep skipping all the others:
  ```python
  SPEEDUP_RE = re.compile(r'(?!32|64)\d+x\.mp4$', re.IGNORECASE)
  ```
- **Skip nothing at all** — set it to a pattern that can never match:
  ```python
  SPEEDUP_RE = re.compile(r'(?!)')
  ```
  Speed-up files passed in will then be attempted and will just `[skip]` themselves at the "only 0 valid GPS samples" check.

## Output format

One `.srt` per input MP4, 10 entries per second (configurable via `--hz`):

```
1
00:00:00,000 --> 00:00:00,100
2026-03-29 19:30:40.589 UTC

2
00:00:00,100 --> 00:00:00,200
2026-03-29 19:30:40.689 UTC
```

## How the timing math works

The script asks exiftool for two columns: `SampleTime` (the start of each GPMF payload in video-time) and `GPSDateTime` (the GPS UTC inside that payload).

1. Pre-lock garbage is dropped by keeping only the longest run of samples whose UTC values increase monotonically with gaps under 5 seconds. GPS receivers often emit cached/stale UTC before the first real fix.
2. The UTC at video t=0 is back-projected from the first kept sample's actual `SampleTime`, not from its index in the list — so error doesn't accumulate across long clips.
3. The configured `--offset` is added.
4. Output is interpolated at 10 Hz across the full container duration (taken from the MP4 itself, since GPS can stop short or have gaps).
