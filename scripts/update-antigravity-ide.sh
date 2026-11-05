#!/usr/bin/env bash

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <Antigravity-IDE.tar.gz>"
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
    echo "Error: Could not find extracted Antigravity-IDE directory."
    rm -rf "$TMPDIR"
    exit 1
fi

echo "Replacing installation..."
sudo rm -rf /opt/antigravity-ide
sudo mv "$APPDIR" /opt/antigravity-ide

echo "Fixing chrome-sandbox permissions..."
sudo chown root:root /opt/antigravity-ide/chrome-sandbox
sudo chmod 4755 /opt/antigravity-ide/chrome-sandbox

echo "Updating symlink..."
sudo ln -sf /opt/antigravity-ide/antigravity-ide /usr/local/bin/antigravity-ide

rm -rf "$TMPDIR"

echo ""
echo "✅ Antigravity IDE updated successfully!"
echo "Launch it using: antigravity-ide"

