# Reference — transcribe-diarize

Resolve `SKILL` to this skill's actual installed directory before running the examples; agent hosts and install scopes use different paths.

## Engine routing contract

The user's wording selects the ASR engine:

| User request | Engine flag | Verified model |
| --- | --- | --- |
| Mentions Parakeet | `--engine parakeet` | `mlx-community/parakeet-tdt-0.6b-v3` |
| Mentions WhisperKit | `--engine whisperkit` | `large-v3-v20240930_626MB` (large-v3-turbo) |
| Names neither | `--engine parakeet` | Parakeet default |
| Names both for comparison | run both | Keep language, speaker count, source, and FluidAudio settings equal |

If both are named without a comparison request, ask which engine to use.

## Verified pipelines

Parakeet:

```text
audio/video file
  -> first selected audio stream
  -> mono 16 kHz PCM WAV
  -> mlx-community/parakeet-tdt-0.6b-v3
  -> FluidAudio offline diarization
  -> token/speaker source-time alignment
  -> Markdown + structured JSON
```

WhisperKit:

```text
audio/video file
  -> first selected audio stream
  -> mono 16 kHz PCM WAV
  -> WhisperKit large-v3-v20240930_626MB
  -> word timestamps with chunking-strategy none
  -> FluidAudio offline diarization
  -> word/speaker source-time alignment
  -> Markdown + structured JSON
```

Both combinations were verified on long Polish two-speaker recordings. WhisperKit produced more readable Polish in that comparison. Parakeet remains the default when the user does not select an engine.

## Why WhisperKit disables VAD

WhisperKit CLI 1.0.0's default `vad` chunking repeated entire transcript windows at shifted timestamps on long completed recordings. The duplication existed in `session.json`, not only terminal output. The verified completed-file path therefore uses:

```text
--chunking-strategy none
```

After a WhisperKit run, verify:

- segment start times never move backwards;
- the final segment reaches the expected source duration;
- long exact segment texts are not duplicated.

## Bootstrap

The bootstrap is explicit because it downloads code and Python packages:

```bash
SKILL="/absolute/path/to/installed/transcribe-diarize"
bash "$SKILL/scripts/bootstrap_parakeet.sh"
```

Defaults:

- cache: `${XDG_CACHE_HOME:-$HOME/.cache}/transcribe-diarize`;
- Python environment: `<cache>/parakeet-venv`;
- MLX-Audio: `0.4.5`;
- FluidAudio checkout: `<cache>/FluidAudio`.

For WhisperKit, also install:

```bash
brew install whisperkit-cli
```

Override locations with:

- `TRANSCRIBE_DIARIZE_CACHE_DIR`;
- `PARAKEET_PYTHON`;
- `FLUID_AUDIO_PACKAGE`;
- `FLUID_AUDIO_CLI` for a prebuilt executable;
- `WHISPERKIT_CLI` for a standalone WhisperKit/Argmax executable.

The bootstrap does not update an existing FluidAudio checkout. Record and pin its commit when reproducibility matters.

## Orchestrator flags

`scripts/transcribe_diarize.sh INPUT [options]`

| Flag | Default | Meaning |
| --- | --- | --- |
| `INPUT` | — | Audio/video file readable by ffmpeg. Required. |
| `--engine` | `parakeet` | `parakeet` or `whisperkit`. |
| `--lang` | `pl` | Language code passed to the ASR engine. |
| `--speakers N` | automatic | Force FluidAudio to find exactly `N` speakers. |
| `--outdir DIR` | `<input-dir>/<base>-transcript` | Output directory. |
| `--roles "S1=...,S2=..."` | none | Add role names and write `transcript_roles.md`. |
| `--model NAME` | engine default | Override the selected engine model only when explicitly required. |
| `--chunk-duration N` | `120` | Parakeet chunk duration in seconds. |
| `--overlap N` | `15` | Parakeet chunk overlap in seconds. |
| `--diarization-threshold N` | `0.6` | FluidAudio clustering threshold. |
| `--keep-wav` | off | Retain the normalized `session.wav`. |

Environment overrides:

| Variable | Meaning |
| --- | --- |
| `FFMPEG_BIN` | ffmpeg executable. |
| `PARAKEET_PYTHON` | Python executable with MLX-Audio installed. |
| `FLUID_AUDIO_PACKAGE` | FluidAudio Swift package checkout. |
| `FLUID_AUDIO_CLI` | Prebuilt `fluidaudiocli`; avoids `swift run`. |
| `WHISPERKIT_CLI` | WhisperKit/Argmax executable. |
| `HF_HOME` | Hugging Face model cache used by Parakeet. |

## Manual Parakeet + FluidAudio pipeline

```bash
SKILL="/absolute/path/to/installed/transcribe-diarize"
WORK="/path/to/output"
INPUT="/path/to/input.qta"
PYTHON="${PARAKEET_PYTHON:-$HOME/.cache/transcribe-diarize/parakeet-venv/bin/python}"
FLUID_AUDIO="${FLUID_AUDIO_PACKAGE:-$HOME/.cache/transcribe-diarize/FluidAudio}"
mkdir -p "$WORK"

ffmpeg -y -i "$INPUT" -map 0:a:0 -vn -ac 1 -ar 16000 \
  -c:a pcm_s16le "$WORK/session.wav"

HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 \
"$PYTHON" -m mlx_audio.stt.generate \
  --model mlx-community/parakeet-tdt-0.6b-v3 \
  --audio "$WORK/session.wav" \
  --output-path "$WORK/session-asr" \
  --format json \
  --chunk-duration 120 \
  --gen-kwargs '{"overlap_duration":15}' \
  --language pl

swift run --package-path "$FLUID_AUDIO" -c release \
  fluidaudiocli process "$WORK/session.wav" \
  --mode offline \
  --threshold 0.6 \
  --num-speakers 2 \
  --output "$WORK/session-diarization.json"

python3 "$SKILL/scripts/align_parakeet_fluidaudio.py" \
  "$WORK/session-asr.json" \
  "$WORK/session-diarization.json" \
  --outdir "$WORK"
```

Only pass `--num-speakers` when the count is known.

## Manual WhisperKit large-v3-turbo + FluidAudio pipeline

```bash
SKILL="/absolute/path/to/installed/transcribe-diarize"
WORK="/path/to/output"
INPUT="/path/to/input.qta"
FLUID_AUDIO="${FLUID_AUDIO_PACKAGE:-$HOME/.cache/transcribe-diarize/FluidAudio}"
mkdir -p "$WORK"

ffmpeg -y -i "$INPUT" -map 0:a:0 -vn -ac 1 -ar 16000 \
  -c:a pcm_s16le "$WORK/session.wav"

whisperkit-cli transcribe \
  --audio-path "$WORK/session.wav" \
  --model large-v3-v20240930_626MB \
  --model-prefix openai \
  --language pl \
  --word-timestamps \
  --chunking-strategy none \
  --report \
  --report-path "$WORK" >/dev/null

swift run --package-path "$FLUID_AUDIO" -c release \
  fluidaudiocli process "$WORK/session.wav" \
  --mode offline \
  --threshold 0.6 \
  --num-speakers 2 \
  --output "$WORK/session-diarization.json"

python3 "$SKILL/scripts/align_parakeet_fluidaudio.py" \
  "$WORK/session.json" \
  "$WORK/session-diarization.json" \
  --outdir "$WORK"
```

Redirect WhisperKit's stdout so raw transcript text does not enter terminal logs. Errors remain on stderr.

## Alignment contract

`align_parakeet_fluidaudio.py` keeps its historical filename but accepts both ASR schemas:

- Parakeet `sentences[].tokens[]`, falling back to timestamped sentences;
- WhisperKit `segments[].words[]`, falling back to timestamped segments.

It then:

1. Orders units by their original source-audio `start` and `end` timestamps.
2. Removes exact duplicate units with the same source time and text.
3. Scores every speaker by overlap with FluidAudio `segments[]`.
4. Assigns the largest-overlap speaker.
5. Falls back to the nearest speaker interval when diarization has a gap.
6. Keeps tightly attached punctuation/subword pieces with their lexical neighbour.
7. Smooths short isolated speaker flips.
8. Groups adjacent same-speaker units into turns, breaking after a long pause.
9. Flags assignments made without direct diarization overlap as `needsReview`.
10. Writes generic and optionally role-labelled Markdown without altering spoken text.

All ordering uses source-audio time. Result arrival/completion order is not a transcript-ordering contract.

## Applying roles without rerunning models

First inspect `transcript.md`, then run only the aligner again.

Parakeet:

```bash
python3 "$SKILL/scripts/align_parakeet_fluidaudio.py" \
  "$WORK/session-asr.json" \
  "$WORK/session-diarization.json" \
  --outdir "$WORK" \
  --roles "S1=Interviewer,S2=Guest"
```

WhisperKit:

```bash
python3 "$SKILL/scripts/align_parakeet_fluidaudio.py" \
  "$WORK/session.json" \
  "$WORK/session-diarization.json" \
  --outdir "$WORK" \
  --roles "S1=Interviewer,S2=Guest"
```

Role labels must come from dialogue content and context. Anonymous diarization IDs do not establish identity.

## Multiple files from one conversation

FluidAudio speaker IDs can swap between separate files. Never copy `S1=Name` blindly from part 1 to later parts.

1. Run every part without roles.
2. Compare duration-weighted mean speaker embeddings:

```bash
python3 "$SKILL/scripts/compare_fluidaudio_embeddings.py" \
  "$ROOT/part1/session-diarization.json" \
  "$ROOT/part2/session-diarization.json" \
  "$ROOT/part3/session-diarization.json"
```

3. Identify same-voice clusters from strong cosine similarities.
4. Confirm the cluster mapping with dialogue anchors.
5. Apply a separate `--roles` mapping to each part.

Do not impose a universal cosine threshold. Compare the within-cluster and cross-cluster separation for the actual recordings.

## Comparing Parakeet and WhisperKit

For a fair comparison:

- use the same source audio stream, mono/16 kHz normalization, language, speaker count, and FluidAudio threshold;
- compare full coverage and end timestamps before judging readability;
- spot-check the beginning, middle, end, rapid exchanges, silence, proper names, and code-switching;
- distinguish ASR quality from diarization quality;
- call the conclusion qualitative unless a human-verified reference transcript exists;
- do not report WER without that reference.

## Outputs

### Shared

- `session-diarization.json` — FluidAudio output with speaker embeddings;
- `turns.json` — normalized turns, role mapping, and review flags;
- `transcript.md` — anonymous labels;
- `transcript_roles.md` — optional mapped role labels;
- `session.wav` — only with `--keep-wav`.

### Parakeet

- `session-asr.json` — raw Parakeet ASR output.

### WhisperKit

- `session.json` — raw WhisperKit ASR output;
- `session.srt` — WhisperKit word-timestamp report.

The normalized WAV is deleted after the run unless `--keep-wav` is passed.

## Caveats and troubleshooting

- **No Metal device available:** MLX and WhisperKit require host access to Apple acceleration. Retry in a suitable local environment.
- **MLX-Audio missing:** run `bootstrap_parakeet.sh` or set `PARAKEET_PYTHON`.
- **WhisperKit CLI missing:** install `whisperkit-cli` or set `WHISPERKIT_CLI`.
- **FluidAudio missing:** run the bootstrap or set `FLUID_AUDIO_PACKAGE`/`FLUID_AUDIO_CLI`.
- **First run is slow:** public model weights may download and Core ML/FluidAudio may compile.
- **Wrong audio stream:** the default uses `0:a:0`; pre-extract the intended track when it is not first.
- **Wrong speaker count:** rerun FluidAudio with the correct count, then rerun alignment. ASR does not need to run again.
- **Speaker swaps across files:** use `compare_fluidaudio_embeddings.py`; do not globally relabel before checking each file.
- **WhisperKit repeated windows:** ensure `--chunking-strategy none`; discard any result with shifted duplicate segments.
- **ASR errors:** names, technical/medical terms, code-switching, noise, and overlap require review.
- **Hallucinations on silence/noise:** verify against source playback. Energy alone does not prove speech.
- **Sensitive output:** raw ASR JSON contains transcript text even when no Markdown export is produced.

Do not calculate or report speaking proportions unless the user explicitly requests that separate analysis.
