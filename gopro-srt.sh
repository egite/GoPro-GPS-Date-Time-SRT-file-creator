#!/bin/bash
# gopro-srt.sh — run gopro_gps_srt.py on every MP4 in this script's folder.
# Speed-up exports (*32x.MP4, *64x.MP4, etc.) are skipped by the Python script.

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

shopt -s nullglob nocaseglob
files=( *.mp4 )
shopt -u nocaseglob

if [ ${#files[@]} -eq 0 ]; then
  echo "No MP4 files found in $SCRIPT_DIR"
  exit 0
fi

python3 "$SCRIPT_DIR/gopro_gps_srt.py" "${files[@]}"
