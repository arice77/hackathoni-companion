#!/bin/sh
# Build the synthetic crop-loss training form into build/Crop Loss Training.app
set -e
cd "$(dirname "$0")"
APP="build/Crop Loss Training.app"
mkdir -p "$APP/Contents/MacOS"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>in.hackathoni.crop-loss-training</string>
<key>CFBundleName</key><string>Crop Loss Training</string>
<key>CFBundleExecutable</key><string>CropLossTraining</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
swiftc -swift-version 5 -O TrainingForm.swift -o "$APP/Contents/MacOS/CropLossTraining" -framework AppKit
codesign --force --sign - "$APP" 2>/dev/null
echo "built $APP"
