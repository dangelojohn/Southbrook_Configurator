#!/usr/bin/env bash
# scripts/install-hooks.sh — symlink canonical hooks into .git/hooks/
#
# Run once after cloning the repo. Idempotent — safe to re-run.
# Uses RELATIVE symlinks so the install isn't tied to a specific $HOME.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$ROOT/scripts/hooks"
DEST_DIR="$ROOT/.git/hooks"

if [ ! -d "$DEST_DIR" ]; then
    echo "FAIL: $DEST_DIR not found — is this a git repo?"
    exit 1
fi
if [ ! -d "$SRC_DIR" ]; then
    echo "FAIL: $SRC_DIR not found — nothing to install"
    exit 1
fi

for hook in "$SRC_DIR"/*; do
    [ -f "$hook" ] || continue
    name=$(basename "$hook")
    chmod +x "$hook"
    ln -snf "../../scripts/hooks/$name" "$DEST_DIR/$name"
    echo "installed: .git/hooks/$name -> ../../scripts/hooks/$name"
done

echo "Done."
