#!/bin/bash
# Print a git tree id of the working tree, untracked non-ignored files included, without touching the real index.
# Usage (inside the worktree): snapshot.sh
set -euo pipefail
top=$(git rev-parse --show-toplevel)
tmp=$(mktemp "${TMPDIR:-/tmp}/snapshot-index.XXXXXX")
trap 'rm -f "$tmp"' EXIT
cp "$(git -C "$top" rev-parse --path-format=absolute --git-path index)" "$tmp" 2>/dev/null || rm -f "$tmp"
GIT_INDEX_FILE="$tmp" git -C "$top" add -A
GIT_INDEX_FILE="$tmp" git -C "$top" write-tree
