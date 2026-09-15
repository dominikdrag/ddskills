---
name: transcribe-diarize
description: Transcribe and diarize a local audio or video file fully on-device with either Parakeet TDT 0.6B v3 or WhisperKit large-v3-turbo plus FluidAudio, producing a timestamped speaker-labelled transcript. Use when the user wants transcription or diarization, mentions transkrypcja or diaryzacja, or points to an audio/video file such as .qta, .m4a, .mov, .mp3, or .wav. Select Parakeet when the user mentions Parakeet, and WhisperKit large-v3-turbo when the user mentions WhisperKit. Defaults to Parakeet and Polish when neither is specified.
---

# Transcribe + diarize a completed file locally

Turn an audio or video file into a speaker-labelled transcript without uploading the recording.

## Engine selection

Choose the ASR engine from the user's wording. Do not silently substitute one engine for the other.

- If the user mentions **Parakeet**, run `--engine parakeet` with `mlx-community/parakeet-tdt-0.6b-v3`.
- If the user mentions **WhisperKit**, run `--engine whisperkit` with `large-v3-v20240930_626MB`, the verified WhisperKit Core ML artifact for **large-v3-turbo**.
- If the user names neither engine, default to Parakeet.
- If the user names both but does not ask for a comparison, ask which engine to use.
- If the user asks to compare them, run both against the same normalized source and use the same FluidAudio diarization settings.

Both verified pipelines keep diarization constant:

```text
input -> ffmpeg mono 16 kHz PCM -> selected ASR -> FluidAudio -> source-time alignment
```

Engine-specific ASR:

- Parakeet: NVIDIA Parakeet TDT 0.6B v3 through MLX-Audio, 120-second chunks with 15-second overlap.
- WhisperKit: `large-v3-v20240930_626MB`, word timestamps, `chunking-strategy none`.

Do not use WhisperKit CLI 1.0.0's default VAD for long completed files. It was observed repeating whole transcript windows at shifted timestamps. The verified path uses `chunking-strategy none` and validates monotonic timestamps and duplicate-free long segments.

## Before running

1. Confirm the exact input file and language. Default to `pl` only when the user did not specify one.
2. Ask for the expected speaker count when it is known. For a known one-to-one conversation, use `--speakers 2`; do not assume two for every recording.
3. Confirm that processing the recording is authorized. Keep sensitive audio, intermediate files, and transcripts local.
4. Before a first-time bootstrap or model download, tell the user that public dependencies/model weights will be downloaded. Audio is never uploaded.

## Prerequisites

- Apple Silicon Mac.
- `ffmpeg`, Python 3, Git, and Swift.
- For WhisperKit: `brew install whisperkit-cli`.
- Run the bootstrap once to prepare FluidAudio and the Parakeet runtime:

```bash
bash ~/.agents/skills/transcribe-diarize/scripts/bootstrap_parakeet.sh
```

The bootstrap creates a dedicated MLX-Audio environment and FluidAudio checkout under `~/.cache/transcribe-diarize/`. It does not process audio. Model weights download on the first run of the selected engine.

## Quick start

Parakeet:

```bash
bash ~/.agents/skills/transcribe-diarize/scripts/transcribe_diarize.sh \
  "/path/to/recording.qta" \
  --engine parakeet \
  --lang pl \
  --speakers 2
```

WhisperKit large-v3-turbo:

```bash
bash ~/.agents/skills/transcribe-diarize/scripts/transcribe_diarize.sh \
  "/path/to/recording.qta" \
  --engine whisperkit \
  --lang pl \
  --speakers 2
```

Output defaults to `<recording-dir>/<basename>-transcript/` and can be changed with `--outdir DIR`. The normalized WAV is transient and deleted after the run unless `--keep-wav` is passed.

## Workflow

1. Run the selected engine without role names first. FluidAudio emits anonymous labels such as `S1` and `S2`.
2. Inspect representative turns and identify roles from dialogue content and context. Never infer identity from the label itself.
3. For multiple files from the same conversation, assume anonymous labels may swap between files. Compare FluidAudio speaker embeddings before applying names:

```bash
python3 ~/.agents/skills/transcribe-diarize/scripts/compare_fluidaudio_embeddings.py \
  /path/to/part1/session-diarization.json \
  /path/to/part2/session-diarization.json \
  /path/to/part3/session-diarization.json
```

4. Use the similarity matrix plus dialogue anchors to establish a mapping per file. Same-voice similarities should form visibly stronger clusters than cross-voice similarities; do not rely on a fixed `S1` or `S2` across recordings.
5. Apply role names without rerunning inference. The aligner accepts either Parakeet `session-asr.json` or WhisperKit `session.json`:

```bash
python3 ~/.agents/skills/transcribe-diarize/scripts/align_parakeet_fluidaudio.py \
  "/path/to/output/session-asr.json" \
  "/path/to/output/session-diarization.json" \
  --outdir "/path/to/output" \
  --roles "S1=Interviewer,S2=Guest"
```

For WhisperKit, replace `session-asr.json` with `session.json`.

6. Spot-check the beginning, several speaker changes, overlaps, names, specialist terms, and the final minutes.
7. For WhisperKit, verify segment start times never move backwards and that long exact segments are not duplicated.
8. Treat the result as a working transcript, not a verbatim stenogram. Preserve literal spoken wording when using the transcript as source material; keep editorial corrections separate.

Do not calculate, report, or interpret speaking proportions unless the user explicitly asks for that analysis.

## Outputs

Shared outputs:

- `session-diarization.json` — FluidAudio speaker timeline with embeddings;
- `turns.json` — structured source-time turns and optional role mapping;
- `transcript.md` — transcript with anonymous speaker labels;
- `transcript_roles.md` — generated only when `--roles` is supplied;
- `session.wav` — present only with `--keep-wav`.

ASR-specific outputs:

- Parakeet: `session-asr.json`.
- WhisperKit: `session.json` and `session.srt`.

## Accuracy and failure boundaries

- Names, Polish/English code-switching, specialist terms, noise, and overlapping speech are common error areas.
- Diarization labels are anonymous and can misassign short interjections or rapid exchanges.
- Anonymous speaker IDs are local to one file. They can swap between consecutive recordings of the same people.
- Forced speaker count improves known one-to-one recordings but damages output when the count is wrong or a third person is audible.
- Chunk overlap can duplicate Parakeet text; WhisperKit VAD can repeat shifted windows. Outputs must remain ordered by source-audio timestamps rather than completion order.
- Silence or noise can produce fluent hallucinations. Do not treat energy detection alone as proof of speech.
- A loaded model can still stall. Useful progress means advancing through the source-audio timeline.

See [REFERENCE.md](REFERENCE.md) for all flags, exact commands, setup, alignment rules, engine-specific outputs, comparison guidance, and troubleshooting.

## Privacy

- Audio and transcript inference stay on the Mac.
- Public model weights and dependencies may be downloaded; recording content is not sent with those requests.
- Do not put raw audio, transcript text, participant names, or source filenames in logs or external diagnostics.
- Delete transient WAV files and temporary transcript artifacts after success or cancellation unless the user explicitly wants to retain them.
