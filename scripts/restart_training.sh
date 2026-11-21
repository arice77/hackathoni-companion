#!/bin/sh
# Quit and reopen the synthetic training form on screen 1 (writes receipts to runs/).
cd "$(dirname "$0")/.."
mkdir -p runs && rm -f runs/draft-saved.json
osascript -e 'quit app id "in.hackathoni.crop-loss-training"' 2>/dev/null || pkill -f CropLossTraining
sleep 1
open --env TRAINING_RECEIPT_DIR="$PWD/runs" "apps/aims-training/build/Crop Loss Training.app"
