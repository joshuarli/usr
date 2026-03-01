#!/bin/dash
set -eu

# Setup Touch ID for sudo on macOS (persists across OS updates)
# Includes pam_reattach for tmux support

if [ "$(uname)" != "Darwin" ]; then
  echo "macOS only"
  exit 1
fi

# Install pam-reattach for tmux support
if ! brew list pam-reattach >/dev/null 2>&1; then
  echo "Installing pam-reattach (for tmux support)..."
  brew install pam-reattach
fi

REATTACH_LIB="/opt/homebrew/lib/pam/pam_reattach.so"
if [ ! -f "$REATTACH_LIB" ]; then
  echo "Error: $REATTACH_LIB not found"
  exit 1
fi

SUDO_LOCAL="/etc/pam.d/sudo_local"

if [ -f "$SUDO_LOCAL" ] && grep -q pam_tid "$SUDO_LOCAL"; then
  echo "Touch ID sudo already configured in $SUDO_LOCAL"
  exit 0
fi

echo "Writing $SUDO_LOCAL (requires sudo)..."
sudo tee "$SUDO_LOCAL" >/dev/null <<'PAM'
auth       optional       /opt/homebrew/lib/pam/pam_reattach.so
auth       sufficient     pam_tid.so
PAM

echo "Done. Touch ID sudo is active (works in tmux too)."
