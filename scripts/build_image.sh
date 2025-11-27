#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: scripts/build_image.sh <name> <tag> [options]

Positional arguments:
  name                  Image/Dockerfile base name (e.g. account-job)
  tag                   Image tag suffix (e.g. dev)

Options:
  -f, --dockerfile PATH    Override Dockerfile path (default: docker/<name>.Dockerfile)
  -i, --image IMAGE        Override full image tag (default: <registry>/<name>:<tag>)
      --registry PREFIX    Registry/repo prefix (default: us-central1-docker.pkg.dev/i4g-dev/applications)
      --smoker VALUE       Include smoke-test data (true/false, default: false)
  -a, --build-arg KEY=VAL  Additional build arguments (repeatable)
  -h, --help               Show this message

Examples:
  scripts/build_image.sh account-job dev --smoker true
USAGE
}

SCRIPT_DIR=$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)

DOCKERFILE=""
IMAGE_TAG=""
REGISTRY_PREFIX="us-central1-docker.pkg.dev/i4g-dev/applications"
SMOKER="false"
EXTRA_BUILD_ARGS=()
POSITIONAL=()
TEMP_SMOKE_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -f|--dockerfile)
            DOCKERFILE="$2"
            shift 2
            ;;
        -i|--image)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --registry)
            REGISTRY_PREFIX="$2"
            shift 2
            ;;
        --smoker)
            SMOKER=$(printf '%s' "$2" | tr '[:upper:]' '[:lower:]')
            if [[ "$SMOKER" != "true" && "$SMOKER" != "false" ]]; then
                echo "Error: --smoker must be 'true' or 'false'" >&2
                exit 1
            fi
            shift 2
            ;;
        -a|--build-arg)
            EXTRA_BUILD_ARGS+=("$2")
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            POSITIONAL+=("$1")
            shift
            ;;
    esac
done

if [[ ${#POSITIONAL[@]} -lt 2 ]]; then
    echo "Error: name and tag positional arguments are required" >&2
    usage
    exit 1
fi

NAME="${POSITIONAL[0]}"
TAG_VALUE="${POSITIONAL[1]}"

if [[ -z "$DOCKERFILE" ]]; then
    DOCKERFILE="$REPO_ROOT/docker/${NAME}.Dockerfile"
fi

if [[ -z "$IMAGE_TAG" ]]; then
    trimmed_prefix="${REGISTRY_PREFIX%/}"
    IMAGE_TAG="${trimmed_prefix}/${NAME}:${TAG_VALUE}"
fi

if [[ ! -f "$DOCKERFILE" ]]; then
    echo "Error: Dockerfile not found at $DOCKERFILE" >&2
    exit 1
fi

if [[ "$SMOKER" == "true" ]]; then
    SMOKE_CONTEXT_PATH="$REPO_ROOT/data"
    if [[ ! -d "$SMOKE_CONTEXT_PATH" ]]; then
        echo "Error: data directory not found at $SMOKE_CONTEXT_PATH" >&2
        exit 1
    fi
else
    TEMP_SMOKE_DIR=$(mktemp -d)
    SMOKE_CONTEXT_PATH="$TEMP_SMOKE_DIR"
fi

cleanup() {
    if [[ -n "$TEMP_SMOKE_DIR" && -d "$TEMP_SMOKE_DIR" ]]; then
        rm -rf "$TEMP_SMOKE_DIR"
    fi
}
trap cleanup EXIT

BUILD_CMD=(docker buildx build --platform linux/amd64 -f "$DOCKERFILE" -t "$IMAGE_TAG" --build-arg "SMOKER=$SMOKER" --build-context "smoke_data=$SMOKE_CONTEXT_PATH")

if ((${#EXTRA_BUILD_ARGS[@]})); then
    for arg in "${EXTRA_BUILD_ARGS[@]}"; do
        BUILD_CMD+=("--build-arg" "$arg")
    done
fi

BUILD_CMD+=(--push "$REPO_ROOT")

echo "Running: ${BUILD_CMD[*]}"
"${BUILD_CMD[@]}"
