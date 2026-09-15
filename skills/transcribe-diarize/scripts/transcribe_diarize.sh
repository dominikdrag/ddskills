#!/usr/bin/env bash
# Local completed-file transcription and diarization.
# ASR: Parakeet TDT 0.6B v3 or WhisperKit large-v3-turbo.
# Diarization: FluidAudio offline for both engines.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE_DIR="${TRANSCRIBE_DIARIZE_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/transcribe-diarize}"

usage() {
  cat <<'EOF'
Usage: transcribe_diarize.sh INPUT [options]

Options:
  --engine parakeet|whisperkit  ASR engine; FluidAudio diarization (default: parakeet)
  --lang CODE                   Language code (default: pl)
  --speakers N                  Expected speaker count; omit for automatic
  --outdir DIR                  Output directory
  --roles "S1=Name,S2=Name"     Optional role mapping
  --model NAME                  Override the selected engine model
  --chunk-duration N            Parakeet chunk seconds (default: 120)
  --overlap N                   Parakeet overlap seconds (default: 15)
  --diarization-threshold N     FluidAudio threshold (default: 0.6)
  --keep-wav                    Retain normalized session.wav
  -h, --help                    Show this help
EOF
}

require_value() {
  local option="$1"
  local value="${2:-}"
  [[ -n "$value" ]] || {
    echo "missing value for $option" >&2
    exit 2
  }
}

INPUT=""
ENGINE="parakeet"
LANGUAGE="pl"
SPEAKERS=""
OUTDIR=""
ROLES=""
MODEL_OVERRIDE=""
CHUNK_DURATION="120"
OVERLAP_DURATION="15"
DIARIZATION_THRESHOLD="0.6"
KEEP_WAV=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --engine)
      require_value "$1" "${2:-}"
      ENGINE="$2"
      shift 2
      ;;
    --lang)
      require_value "$1" "${2:-}"
      LANGUAGE="$2"
      shift 2
      ;;
    --speakers)
      require_value "$1" "${2:-}"
      SPEAKERS="$2"
      shift 2
      ;;
    --outdir)
      require_value "$1" "${2:-}"
      OUTDIR="$2"
      shift 2
      ;;
    --roles)
      require_value "$1" "${2:-}"
      ROLES="$2"
      shift 2
      ;;
    --model)
      require_value "$1" "${2:-}"
      MODEL_OVERRIDE="$2"
      shift 2
      ;;
    --chunk-duration)
      require_value "$1" "${2:-}"
      CHUNK_DURATION="$2"
      shift 2
      ;;
    --overlap)
      require_value "$1" "${2:-}"
      OVERLAP_DURATION="$2"
      shift 2
      ;;
    --diarization-threshold)
      require_value "$1" "${2:-}"
      DIARIZATION_THRESHOLD="$2"
      shift 2
      ;;
    --keep-wav)
      KEEP_WAV=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ -n "$INPUT" ]]; then
        echo "only one input file is supported" >&2
        exit 2
      fi
      INPUT="$1"
      shift
      ;;
  esac
done

[[ -n "$INPUT" ]] || {
  usage >&2
  exit 2
}
[[ -f "$INPUT" ]] || {
  echo "input not found: $INPUT" >&2
  exit 1
}
[[ "$ENGINE" == "parakeet" || "$ENGINE" == "whisperkit" ]] || {
  echo "unsupported engine: $ENGINE" >&2
  exit 2
}
[[ -z "$SPEAKERS" || "$SPEAKERS" =~ ^[1-9][0-9]*$ ]] || {
  echo "--speakers must be a positive integer" >&2
  exit 2
}
[[ "$CHUNK_DURATION" =~ ^[1-9][0-9]*$ ]] || {
  echo "--chunk-duration must be a positive integer" >&2
  exit 2
}
[[ "$OVERLAP_DURATION" =~ ^[0-9]+$ ]] || {
  echo "--overlap must be a non-negative integer" >&2
  exit 2
}
(( OVERLAP_DURATION < CHUNK_DURATION )) || {
  echo "--overlap must be smaller than --chunk-duration" >&2
  exit 2
}
[[ "$DIARIZATION_THRESHOLD" =~ ^[0-9]+([.][0-9]+)?$ ]] || {
  echo "--diarization-threshold must be numeric" >&2
  exit 2
}

FFMPEG_EXECUTABLE="${FFMPEG_BIN:-$(command -v ffmpeg || true)}"
[[ -n "$FFMPEG_EXECUTABLE" && -x "$FFMPEG_EXECUTABLE" ]] || {
  echo "ffmpeg not found; install it or set FFMPEG_BIN" >&2
  exit 1
}

base="$(basename "$INPUT")"
base="${base%.*}"
if [[ -z "$OUTDIR" ]]; then
  OUTDIR="$(cd "$(dirname "$INPUT")" && pwd)/${base}-transcript"
fi
mkdir -p "$OUTDIR"
WAV="$OUTDIR/session.wav"
FLUID_PACKAGE="${FLUID_AUDIO_PACKAGE:-$CACHE_DIR/FluidAudio}"
DIARIZATION_JSON="$OUTDIR/session-diarization.json"

cleanup() {
  if (( KEEP_WAV == 0 )); then
    rm -f "$WAV"
  fi
}
trap cleanup EXIT

run_fluidaudio() {
  local diarization_args=(
    process "$WAV"
    --mode offline
    --threshold "$DIARIZATION_THRESHOLD"
    --output "$DIARIZATION_JSON"
  )
  if [[ -n "$SPEAKERS" ]]; then
    diarization_args+=(--num-speakers "$SPEAKERS")
  fi

  if [[ -n "${FLUID_AUDIO_CLI:-}" ]]; then
    [[ -x "$FLUID_AUDIO_CLI" ]] || {
      echo "FLUID_AUDIO_CLI is not executable: $FLUID_AUDIO_CLI" >&2
      exit 1
    }
    "$FLUID_AUDIO_CLI" "${diarization_args[@]}"
  else
    [[ -d "$FLUID_PACKAGE" ]] || {
      echo "FluidAudio checkout missing. Run: $SCRIPT_DIR/bootstrap_parakeet.sh" >&2
      exit 1
    }
    command -v swift >/dev/null || {
      echo "Swift is required to run FluidAudio" >&2
      exit 1
    }
    swift run --package-path "$FLUID_PACKAGE" -c release \
      fluidaudiocli "${diarization_args[@]}"
  fi

  [[ -f "$DIARIZATION_JSON" ]] || {
    echo "FluidAudio output missing: $DIARIZATION_JSON" >&2
    exit 1
  }
}

echo "[1/4] Normalizing first audio stream to mono 16 kHz PCM." >&2
"$FFMPEG_EXECUTABLE" -y -hide_banner -loglevel error -stats \
  -i "$INPUT" -map 0:a:0 -vn -ac 1 -ar 16000 -c:a pcm_s16le "$WAV"

if [[ "$ENGINE" == "parakeet" ]]; then
  PARAKEET_MODEL="${MODEL_OVERRIDE:-mlx-community/parakeet-tdt-0.6b-v3}"
  PARAKEET_EXECUTABLE="${PARAKEET_PYTHON:-$CACHE_DIR/parakeet-venv/bin/python}"
  ASR_BASE="$OUTDIR/session-asr"
  ASR_JSON="$ASR_BASE.json"

  [[ -x "$PARAKEET_EXECUTABLE" ]] || {
    echo "Parakeet runtime missing. Run: $SCRIPT_DIR/bootstrap_parakeet.sh" >&2
    exit 1
  }
  "$PARAKEET_EXECUTABLE" -c 'import mlx_audio' 2>/dev/null || {
    echo "mlx_audio is unavailable in $PARAKEET_EXECUTABLE" >&2
    exit 1
  }

  echo "[2/4] Transcribing with $PARAKEET_MODEL (language=$LANGUAGE)." >&2
  HF_HOME="${HF_HOME:-$CACHE_DIR/huggingface}" \
    HF_HUB_DISABLE_TELEMETRY=1 \
    DO_NOT_TRACK=1 \
    "$PARAKEET_EXECUTABLE" -m mlx_audio.stt.generate \
      --model "$PARAKEET_MODEL" \
      --audio "$WAV" \
      --output-path "$ASR_BASE" \
      --format json \
      --chunk-duration "$CHUNK_DURATION" \
      --gen-kwargs "{\"overlap_duration\":$OVERLAP_DURATION}" \
      --language "$LANGUAGE"

  [[ -f "$ASR_JSON" ]] || {
    echo "Parakeet output missing: $ASR_JSON" >&2
    exit 1
  }
else
  WHISPER_MODEL="${MODEL_OVERRIDE:-large-v3-v20240930_626MB}"
  WHISPER_EXECUTABLE="${WHISPERKIT_CLI:-$(command -v whisperkit-cli || command -v argmax-cli || true)}"
  ASR_JSON="$OUTDIR/session.json"
  [[ -n "$WHISPER_EXECUTABLE" && -x "$WHISPER_EXECUTABLE" ]] || {
    echo "WhisperKit CLI not found; install whisperkit-cli or set WHISPERKIT_CLI" >&2
    exit 1
  }

  echo "[2/4] Transcribing with WhisperKit $WHISPER_MODEL (language=$LANGUAGE)." >&2
  "$WHISPER_EXECUTABLE" transcribe \
    --audio-path "$WAV" \
    --model "$WHISPER_MODEL" \
    --model-prefix openai \
    --language "$LANGUAGE" \
    --word-timestamps \
    --chunking-strategy none \
    --report \
    --report-path "$OUTDIR" >/dev/null

  [[ -f "$ASR_JSON" ]] || {
    echo "WhisperKit output missing: $ASR_JSON" >&2
    exit 1
  }
fi

echo "[3/4] Diarizing with FluidAudio${SPEAKERS:+ (speakers=$SPEAKERS)}." >&2
run_fluidaudio

echo "[4/4] Aligning ASR words to FluidAudio speaker intervals." >&2
ALIGN_ARGS=("$ASR_JSON" "$DIARIZATION_JSON" --outdir "$OUTDIR")
if [[ -n "$ROLES" ]]; then
  ALIGN_ARGS+=(--roles "$ROLES")
fi
python3 "$SCRIPT_DIR/align_parakeet_fluidaudio.py" "${ALIGN_ARGS[@]}"

echo "Done. Outputs: $OUTDIR" >&2
echo "  transcript.md       anonymous speaker labels" >&2
if [[ -n "$ROLES" ]]; then
  echo "  transcript_roles.md mapped role labels" >&2
fi
echo "  turns.json          structured source-time turns" >&2
