#!/bin/bash
set -euo pipefail

echo "Starting account-job wrapper..."

# Default runtime paths so the settings layer resolves to writable locations.
export I4G_PROJECT_ROOT="${I4G_PROJECT_ROOT:-/app}"
export I4G_DATA_DIR="${I4G_DATA_DIR:-/tmp/i4g}"
export I4G_STORAGE__SQLITE_PATH="${I4G_STORAGE__SQLITE_PATH:-$I4G_DATA_DIR/i4g_store.db}"
export I4G_VECTOR__CHROMA_DIR="${I4G_VECTOR__CHROMA_DIR:-$I4G_DATA_DIR/chroma_store}"

# Copy baked artifacts to the ephemeral volume so SQLite/Chroma are writable in Cloud Run.
if [ -d "/app/data" ] && [[ "$I4G_DATA_DIR" == /tmp/* ]]; then
    echo "Syncing /app/data into $I4G_DATA_DIR ..."
    mkdir -p "$I4G_DATA_DIR"
    rsync -a --delete /app/data/ "$I4G_DATA_DIR"/
    ls -la "$I4G_DATA_DIR"
else
    echo "Skipping data sync. /app/data exists: $([ -d "/app/data" ] && echo yes || echo no). I4G_DATA_DIR: $I4G_DATA_DIR"
fi

echo "Executing i4g-account-job..."
exec i4g-account-job
