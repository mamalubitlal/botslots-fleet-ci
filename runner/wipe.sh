#!/bin/bash
# Wipe all plaintext at run end (ciphertext-only tree guarantee).
rm -rf fleet fleet_bundle.tar.gz ~/.taskmarket ~/.config/opencode /tmp/fleet_work
shred -u /tmp/bundle_pw 2>/dev/null || true
echo "wiped"
