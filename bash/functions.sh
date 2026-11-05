# ================================
# Wayland Clipboard Shortcuts
# Backend: wl-copy / wl-paste (from wl-clipboard)
# Install: sudo apt install wl-clipboard
# ================================

copy() {
    # If arguments are given, copy them.
    # Otherwise, read from stdin.
    if [ $# -gt 0 ]; then
        printf "%s" "$*" | wl-copy
    else
        wl-copy
    fi
}

paste() {
    wl-paste
}
