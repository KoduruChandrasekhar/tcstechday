#!/usr/bin/env bash
# Stage the backend for a Hugging Face Docker Space and (optionally) upload it.
#
#   deploy/hf_space.sh                      # stage only -> deploy/.hf_space (inspect it, or `docker build` it)
#   deploy/hf_space.sh <user>/<space-name>  # stage + upload with the `hf` CLI (run `hf auth login` first)
#
# The bundle holds only what the server needs: Dockerfile, backend/app, backend/requirements.txt, data/synthetic.
# Set GEMINI_API_KEY as a Space *secret* (Settings -> Variables and secrets); never upload .env.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/deploy/.hf_space"

rm -rf "$OUT"
mkdir -p "$OUT/backend" "$OUT/data"
cp "$ROOT/Dockerfile" "$ROOT/.dockerignore" "$OUT/"
cp "$ROOT/backend/requirements.txt" "$OUT/backend/"
cp -R "$ROOT/backend/app" "$OUT/backend/app"
cp -R "$ROOT/data/synthetic" "$OUT/data/synthetic"
find "$OUT" -name "__pycache__" -type d -prune -exec rm -rf {} +
cp "$ROOT/deploy/hf_space_README.md" "$OUT/README.md"
echo "staged $(du -sh "$OUT" | cut -f1) in $OUT"

if [[ $# -ge 1 ]]; then
  hf upload "$1" "$OUT" . --repo-type space --commit-message "Deploy PromoForge backend"
  echo "uploaded -> https://huggingface.co/spaces/$1"
fi
