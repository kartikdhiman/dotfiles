#!/usr/bin/env bash

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <Antigravity.tar.gz>"
    exit 1
fi

ARCHIVE="$1"

if [ ! -f "$ARCHIVE" ]; then
    echo "Error: File not found: $ARCHIVE"
    exit 1
fi

TMPDIR=$(mktemp -d)

echo "Extracting archive..."
tar -xzf "$ARCHIVE" -C "$TMPDIR"

APPDIR=$(find "$TMPDIR" -maxdepth 1 -type d -name "Antigravity*" | head -n1)

if [ -z "$APPDIR" ]; then
    echo "Error: Could not find extracted Antigravity directory."
    rm -rf "$TMPDIR"
    exit 1
fi

echo "Replacing installation..."
sudo rm -rf /opt/antigravity
sudo mv "$APPDIR" /opt/antigravity

echo "Fixing chrome-sandbox permissions..."
sudo chown root:root /opt/antigravity/chrome-sandbox
sudo chmod 4755 /opt/antigravity/chrome-sandbox

echo "Updating symlink..."
sudo ln -sf /opt/antigravity/antigravity /usr/local/bin/antigravity

rm -rf "$TMPDIR"

echo ""
echo "✅ Antigravity updated successfully!"
echo "Launch it using: antigravity"
