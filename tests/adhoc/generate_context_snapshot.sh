#!/usr/bin/env bash
set -euo pipefail

# generate_context_snapshot.sh
# Run from repo root. Produces /tmp/i4g_snapshot and i4g_snapshot.zip.

OUT_DIR="/tmp/i4g_snapshot_$(date +%s)"
ZIP_NAME="i4g_snapshot_$(date +%Y%m%d_%H%M%S).zip"
mkdir -p "$OUT_DIR"

echo "Creating repository snapshot in $OUT_DIR"

# 1) Basic repo shape
echo "Repository: $(basename $(pwd))" > "$OUT_DIR/repo_info.txt"
echo "Generated: $(date -u)" >> "$OUT_DIR/repo_info.txt"

# 2) File tree (limited depth to avoid giant output)
if command -v tree >/dev/null 2>&1; then
  tree -L 4 -I '__pycache__|.git|venv|env' > "$OUT_DIR/repo_tree.txt" || true
else
  find . -maxdepth 4 -type f -not -path "./.git/*" | sed 's/^\.\///' > "$OUT_DIR/repo_tree.txt"
fi

# 3) List python modules under src/ (dotted path)
PY_MODULE_FILE="$OUT_DIR/py_modules.txt"
> "$PY_MODULE_FILE"
if [ -d "src" ]; then
  find src -name "*.py" -not -path "*/__pycache__/*" -not -path "*/tests/*" | while read -r f; do
    # turn src/i4g/path/name.py -> i4g.path.name
    mod=$(echo "$f" | sed -E 's|^src/||; s|/|.|g; s|\.py$||')
    echo "$mod" >> "$PY_MODULE_FILE"
  done
fi

# 4) Grab top-of-file previews for key files
PREVIEW_DIR="$OUT_DIR/previews"
mkdir -p "$PREVIEW_DIR"

# files to snapshot (common): README, prd, dev_guide, pyproject, tox.ini
for file in README.md docs/prd.md docs/dev_guide.md pyproject.toml tox.ini; do
  if [ -f "$file" ]; then
    echo "=== $file ===" > "$PREVIEW_DIR/$(basename $file).preview.txt"
    sed -n '1,200p' "$file" >> "$PREVIEW_DIR/$(basename $file).preview.txt"
  fi
done

# 5) Collect a small preview of top changed/important modules.
# Heuristic: pick modules in src/i4g with largest size (so likely important)
if [ -d "src/i4g" ]; then
  find src/i4g -name "*.py" -not -path "*/__pycache__/*" -exec stat -f "%z %N" {} + | sort -nr | head -n 40 | sed 's/^[0-9]* //' > "$OUT_DIR/top_modules.txt"
  mkdir -p "$PREVIEW_DIR/modules"
  while read -r f; do
    base=$(basename "$f")
    echo "=== $f ===" > "$PREVIEW_DIR/modules/${base}.preview.txt"
    sed -n '1,240p' "$f" >> "$PREVIEW_DIR/modules/${base}.preview.txt"
  done < "$OUT_DIR/top_modules.txt"
fi

# 6) Optional: include latest git commit summary if repo is git
if command -v git >/dev/null 2>&1 && [ -d ".git" ]; then
  git log -n 5 --pretty=format:"%h %ad %s (%an)" --date=short > "$OUT_DIR/git_recent_commits.txt" || true
  git rev-parse --abbrev-ref HEAD > "$OUT_DIR/git_branch.txt" || true
fi

# 7) Make zip
ZIP_FULL_PATH="$(pwd)/$ZIP_NAME"
cd "$OUT_DIR"
zip -r "$ZIP_FULL_PATH" . >/dev/null
cd - > /dev/null

echo "Snapshot created: $ZIP_FULL_PATH"
echo "Upload this file into the chat to sync me to your repo state."
