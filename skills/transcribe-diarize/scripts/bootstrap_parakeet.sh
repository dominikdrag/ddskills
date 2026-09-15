#!/usr/bin/env bash
# Explicitly install the verified Parakeet + FluidAudio runtime in a user cache.
set -euo pipefail

CACHE_DIR="${TRANSCRIBE_DIARIZE_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/transcribe-diarize}"
PYTHON_BOOTSTRAP="${PYTHON_BOOTSTRAP:-}"
MLX_AUDIO_VERSION="0.4.5"

usage() {
  cat <<'EOF'
Usage: bootstrap_parakeet.sh [options]

Options:
  --cache-dir DIR          Install under DIR
  --python EXECUTABLE     Python used to create the venv
  --mlx-audio-version VER MLX-Audio version (default: 0.4.5)
  -h, --help              Show this help

This command downloads Python packages and the FluidAudio repository.
It never reads or uploads an audio recording.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cache-dir)
      [[ -n "${2:-}" ]] || { echo "missing value for $1" >&2; exit 2; }
      CACHE_DIR="$2"
      shift 2
      ;;
    --python)
      [[ -n "${2:-}" ]] || { echo "missing value for $1" >&2; exit 2; }
      PYTHON_BOOTSTRAP="$2"
      shift 2
      ;;
    --mlx-audio-version)
      [[ -n "${2:-}" ]] || { echo "missing value for $1" >&2; exit 2; }
      MLX_AUDIO_VERSION="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]] || {
  echo "Parakeet through MLX-Audio requires an Apple Silicon Mac" >&2
  exit 1
}
command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
command -v swift >/dev/null || { echo "Swift is required" >&2; exit 1; }
command -v ffmpeg >/dev/null || {
  echo "ffmpeg is required; install it with: brew install ffmpeg" >&2
  exit 1
}

if [[ -z "$PYTHON_BOOTSTRAP" ]]; then
  for candidate in python3.12 python3.13 python3.14 python3; do
    if command -v "$candidate" >/dev/null; then
      PYTHON_BOOTSTRAP="$(command -v "$candidate")"
      break
    fi
  done
fi
[[ -n "$PYTHON_BOOTSTRAP" && -x "$PYTHON_BOOTSTRAP" ]] || {
  echo "Python 3 was not found; pass --python EXECUTABLE" >&2
  exit 1
}

mkdir -p "$CACHE_DIR"
VENV="$CACHE_DIR/parakeet-venv"
FLUID_AUDIO="$CACHE_DIR/FluidAudio"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Creating Python environment: $VENV" >&2
  "$PYTHON_BOOTSTRAP" -m venv "$VENV"
fi

echo "Installing MLX-Audio $MLX_AUDIO_VERSION in the dedicated environment." >&2
PIP_DISABLE_PIP_VERSION_CHECK=1 \
  "$VENV/bin/python" -m pip install "mlx-audio==$MLX_AUDIO_VERSION"

if [[ ! -d "$FLUID_AUDIO/.git" ]]; then
  echo "Cloning FluidAudio: $FLUID_AUDIO" >&2
  git clone --depth 1 https://github.com/FluidInference/FluidAudio.git "$FLUID_AUDIO"
else
  echo "Using existing FluidAudio checkout without updating it." >&2
fi

echo "Building FluidAudio CLI." >&2
swift build --package-path "$FLUID_AUDIO" -c release --product fluidaudiocli

echo "Bootstrap complete." >&2
echo "  Parakeet Python: $VENV/bin/python" >&2
echo "  FluidAudio:      $FLUID_AUDIO" >&2
echo "  FluidAudio commit: $(git -C "$FLUID_AUDIO" rev-parse HEAD)" >&2
