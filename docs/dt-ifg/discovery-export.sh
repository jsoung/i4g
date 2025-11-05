#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: discovery-export.sh --project PROJECT_ID [options]

Required flags:
  --project PROJECT_ID   Target Google Cloud project ID.

Optional flags:
  --out PATH             Zip file to write. Defaults to ../outputs/PROJECT-discovery-TIMESTAMP.zip.
  --log-days N           Include up to N days of logs (0 disables log capture).
  --log-limit N          Maximum log entries to fetch when logs are enabled (default 500).
  --keep-temp            Preserve the working directory for inspection.
  --help                 Show this help message.
EOF
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

ORIGINAL_ARGS=("$@")
PROJECT=""
OUTPUT_PATH=""
LOG_DAYS=0
LOG_LIMIT=500
KEEP_TEMP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      if [[ -z "${2:-}" ]]; then
        echo "--project requires a value" >&2
        usage
        exit 1
      fi
      PROJECT="$2"
      shift 2
      ;;
    --out)
      if [[ -z "${2:-}" ]]; then
        echo "--out requires a value" >&2
        usage
        exit 1
      fi
      OUTPUT_PATH="$2"
      shift 2
      ;;
    --log-days)
      if [[ -z "${2:-}" ]]; then
        echo "--log-days requires a value" >&2
        usage
        exit 1
      fi
      LOG_DAYS="$2"
      shift 2
      ;;
    --log-limit)
      if [[ -z "${2:-}" ]]; then
        echo "--log-limit requires a value" >&2
        usage
        exit 1
      fi
      LOG_LIMIT="$2"
      shift 2
      ;;
    --keep-temp)
      KEEP_TEMP=1
      shift
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$PROJECT" ]]; then
  echo "Missing required flag: --project" >&2
  usage
  exit 1
fi

if ! [[ "$LOG_DAYS" =~ ^[0-9]+$ ]]; then
  echo "--log-days must be an integer" >&2
  exit 1
fi

if ! [[ "$LOG_LIMIT" =~ ^[0-9]+$ ]]; then
  echo "--log-limit must be an integer" >&2
  exit 1
fi

for tool in gcloud zip python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Required tool not found on PATH: $tool" >&2
    exit 1
  fi
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"

abspath() {
  python3 - "$1" <<'PY'
import os
import sys

print(os.path.abspath(sys.argv[1]))
PY
}

if [[ -z "$OUTPUT_PATH" ]]; then
  OUTPUT_PATH="$REPO_ROOT/outputs/${PROJECT}-discovery-$TIMESTAMP.zip"
fi

mkdir -p "$(dirname "$OUTPUT_PATH")"
OUTPUT_PATH="$(abspath "$OUTPUT_PATH")"

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/discovery-${PROJECT}-XXXXXX")"

cleanup() {
  local status=$?
  if [[ $status -ne 0 ]]; then
    echo "discovery-export.sh: failed (exit $status); keeping $WORK_DIR for inspection" >&2
    return
  fi

  if [[ $KEEP_TEMP -eq 1 ]]; then
    echo "discovery-export.sh: kept working files at $WORK_DIR" >&2
    return
  fi

  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

mkdir -p "$WORK_DIR/meta" "$WORK_DIR/asset" "$WORK_DIR/services" "$WORK_DIR/logging"
RUN_LOG="$WORK_DIR/run.log"

log() {
  local ts
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "[$ts] $*" | tee -a "$RUN_LOG"
}

join_args() {
  local acc=""
  local arg
  for arg in "$@"; do
    printf -v arg '%q' "$arg"
    if [[ -n "$acc" ]]; then
      acc+=" "
    fi
    acc+="$arg"
  done
  printf '%s' "$acc"
}

# run_cmd captures command output without aborting the whole script on errors.
run_cmd() {
  local label="$1"
  local outfile="$2"
  shift 2
  local stderr_file="${outfile}.stderr"
  log "Collecting $label"
  if "$@" >"$outfile" 2>"$stderr_file"; then
    if [[ ! -s "$stderr_file" ]]; then
      rm -f "$stderr_file"
    fi
  else
    local status=$?
    if [[ -s "$stderr_file" ]]; then
      mv "$stderr_file" "${outfile}.error"
    else
      touch "${outfile}.error"
    fi
    : >"$outfile"
    failures+=("$label (exit $status)")
    log "Failed to collect $label (exit $status)"
  fi
}

INVOCATION="$(join_args "${ORIGINAL_ARGS[@]}")"

cat <<EOF >"$WORK_DIR/README.txt"
Project: $PROJECT
Generated: $TIMESTAMP
Invocation: discovery-export.sh $INVOCATION
EOF

log "Starting discovery export for project $PROJECT"
log "Working directory: $WORK_DIR"

export CLOUDSDK_CORE_PROJECT="$PROJECT"
GCLOUD=(gcloud --project="$PROJECT" --quiet)
failures=()

run_cmd "gcloud_config" "$WORK_DIR/meta/gcloud-config.json" "${GCLOUD[@]}" config list --format=json
run_cmd "enabled_services" "$WORK_DIR/meta/enabled-services.json" "${GCLOUD[@]}" services list --enabled --format=json
run_cmd "project" "$WORK_DIR/meta/project.json" "${GCLOUD[@]}" projects describe "$PROJECT" --format=json
run_cmd "iam_policy" "$WORK_DIR/meta/iam-policy.json" "${GCLOUD[@]}" projects get-iam-policy "$PROJECT" --format=json
run_cmd "service_accounts" "$WORK_DIR/meta/service-accounts.json" "${GCLOUD[@]}" iam service-accounts list --format=json

ASSET_TYPES=(
  "cloud_run_services:run.googleapis.com/Service"
  "cloud_run_jobs:run.googleapis.com/Job"
  "cloud_functions:cloudfunctions.googleapis.com/CloudFunction"
  "pubsub_topics:pubsub.googleapis.com/Topic"
  "pubsub_subscriptions:pubsub.googleapis.com/Subscription"
  "cloud_sql_instances:sqladmin.googleapis.com/Instance"
  "firestore_databases:firestore.googleapis.com/Database"
)

for entry in "${ASSET_TYPES[@]}"; do
  IFS=: read -r label asset_type <<<"$entry"
  run_cmd "asset_$label" "$WORK_DIR/asset/${label}.json" "${GCLOUD[@]}" asset search-all-resources \
    --scope="projects/$PROJECT" \
    --asset-types="$asset_type" \
    --format=json
done

run_cmd "firestore_databases" "$WORK_DIR/services/firestore-databases.json" "${GCLOUD[@]}" firestore databases list --format=json
run_cmd "firestore_indexes_composite" "$WORK_DIR/services/firestore-indexes-composite.json" "${GCLOUD[@]}" firestore indexes composite list --database="(default)" --format=json

collect_firestore_single_field_indexes() {
  local label="firestore_indexes_single_field"
  local outfile="$WORK_DIR/services/firestore-indexes-single-field.json"
  local stderr_file="${outfile}.stderr"

  log "Collecting $label"
  if "${GCLOUD[@]}" firestore indexes single-field list --database="(default)" --format=json >"$outfile" 2>"$stderr_file"; then
    if [[ ! -s "$stderr_file" ]]; then
      rm -f "$stderr_file"
    fi
    return
  fi

  local status=$?
  local note=""

  if [[ $status -eq 0 ]]; then
    # Command succeeded but produced unexpected stderr; treat as best-effort success.
    rm -f "$stderr_file"
    return
  fi

  if [[ -s "$stderr_file" ]]; then
    if grep -qiE 'Datastore mode|datastore-mode|ALREADY_IN_DATASTORE_MODE|is in Datastore mode' "$stderr_file"; then
      note="Firestore is running in Datastore mode; single-field indexes are managed automatically and not listed via gcloud."
    elif grep -qiE 'INVALID_ARGUMENT' "$stderr_file"; then
      note="gcloud reported INVALID_ARGUMENT while listing single-field indexes (likely Datastore mode); indexes are omitted."
    fi
  else
    # No stderr and non-zero exit is also a Datastore-mode symptom; record note.
    if [[ $status -eq 2 ]]; then
      note="Firestore is running in Datastore mode; single-field indexes are managed automatically and not listed via gcloud."
    fi
  fi

  if [[ -n "$note" ]]; then
    cat <<EOF >"$outfile"
{
  "note": "$note"
}
EOF
    rm -f "$stderr_file"
    log "Firestore single-field indexes unavailable: $note"
    return
  fi

  if [[ -s "$stderr_file" ]]; then
    mv "$stderr_file" "${outfile}.error"
  else
    touch "${outfile}.error"
  fi
  : >"$outfile"
  failures+=("$label (exit $status)")
  log "Failed to collect $label (exit $status)"
}

collect_firestore_single_field_indexes
run_cmd "cloud_functions_list" "$WORK_DIR/services/cloud-functions.json" "${GCLOUD[@]}" functions list --format=json
run_cmd "pubsub_topics_list" "$WORK_DIR/services/pubsub-topics.json" "${GCLOUD[@]}" pubsub topics list --format=json
run_cmd "pubsub_subscriptions_list" "$WORK_DIR/services/pubsub-subscriptions.json" "${GCLOUD[@]}" pubsub subscriptions list --format=json
run_cmd "cloud_sql_instances_list" "$WORK_DIR/services/cloud-sql.json" "${GCLOUD[@]}" sql instances list --format=json
run_cmd "cloud_scheduler_jobs_list" "$WORK_DIR/services/cloud-scheduler-jobs.json" "${GCLOUD[@]}" scheduler jobs list --format=json

if (( LOG_DAYS > 0 )); then
  run_cmd "logging_recent" "$WORK_DIR/logging/recent.json" "${GCLOUD[@]}" logging read 'severity>=DEFAULT' \
    --freshness="${LOG_DAYS}d" \
    --limit="$LOG_LIMIT" \
    --format=json \
    --order=desc
fi

DISCOVERY_PROJECT="$PROJECT" DISCOVERY_TIMESTAMP="$TIMESTAMP" python3 - "$WORK_DIR" "$WORK_DIR/manifest.json" <<'PY'
import json
import os
import sys

root = sys.argv[1]
manifest_path = sys.argv[2]
files = []
for dirpath, _, filenames in os.walk(root):
    for name in filenames:
        files.append(os.path.relpath(os.path.join(dirpath, name), root))

manifest = {
    "project": os.environ.get("DISCOVERY_PROJECT", ""),
    "generated_at": os.environ.get("DISCOVERY_TIMESTAMP", ""),
    "file_count": len(files),
    "files": sorted(files),
}

with open(manifest_path, "w", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=2)
    handle.write("\n")
PY

log "Creating archive at $OUTPUT_PATH"
(
  cd "$WORK_DIR"
  zip -rq "$OUTPUT_PATH" .
)

EXIT_CODE=0

if (( ${#failures[@]} > 0 )); then
  EXIT_CODE=2
  log "Completed with ${#failures[@]} collector error(s):"
  for failure in "${failures[@]}"; do
    log "  - $failure"
  done
  log "Inspect the .error files inside the archive for details."
else
  log "Discovery export completed successfully"
fi

log "Archive ready: $OUTPUT_PATH"

exit $EXIT_CODE
