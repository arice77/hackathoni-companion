#!/bin/sh
# Quit and reopen THIS worktree's copy of the synthetic training form on screen 1.
# Other worktrees run their own copy with the same bundle id, so match by executable path, not bundle id.
cd "$(dirname "$0")/.."
APP="$PWD/apps/aims-training/build/Crop Loss Training.app"
mkdir -p runs && rm -f runs/training-*.json runs/draft-saved.json
pkill -f "$APP/Contents/MacOS/CropLossTraining" 2>/dev/null
sleep 1
open -n --env TRAINING_RECEIPT_DIR="$PWD/runs" "$APP"
