#!/usr/bin/env python3
"""Align Parakeet or WhisperKit timestamps with FluidAudio speaker intervals.

Usage:
  align_parakeet_fluidaudio.py ASR_JSON DIARIZATION_JSON --outdir DIR
      [--roles "S1=Interviewer,S2=Guest"] [--pause-split 2.5]

The script keeps transcript ordering on the source-audio timeline. It writes
anonymous labels unconditionally and writes a role-labelled copy only when an
explicit mapping is supplied.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def timestamp(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_time(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def clean_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def load_asr(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError("ASR JSON must be an object")

    units: list[dict[str, Any]] = []
    sentences = data.get("sentences", [])
    if not isinstance(sentences, list):
        sentences = []

    for sentence_index, sentence in enumerate(sentences):
        if not isinstance(sentence, dict):
            continue
        tokens = sentence.get("tokens")
        added_token = False
        if isinstance(tokens, list):
            for token_index, token in enumerate(tokens):
                if not isinstance(token, dict):
                    continue
                text = clean_text(
                    token.get("text", token.get("token", token.get("word")))
                )
                start = as_time(token.get("start"))
                end = as_time(token.get("end"))
                if not text or start is None or end is None or end < start:
                    continue
                units.append(
                    {
                        "text": text,
                        "start": start,
                        "end": end,
                        "id": token.get("id", f"{sentence_index}:{token_index}"),
                    }
                )
                added_token = True

        if added_token:
            continue

        text = clean_text(sentence.get("text"))
        start = as_time(sentence.get("start"))
        end = as_time(sentence.get("end"))
        if text and start is not None and end is not None and end >= start:
            units.append(
                {
                    "text": text,
                    "start": start,
                    "end": end,
                    "id": f"sentence:{sentence_index}",
                }
            )

    # WhisperKit reports timestamped words under segments[].words[]. Its word
    # strings retain leading whitespace, matching the concatenation contract
    # used by Parakeet token pieces.
    if not units:
        segments = data.get("segments", [])
        if not isinstance(segments, list):
            segments = []
        for segment_index, segment in enumerate(segments):
            if not isinstance(segment, dict):
                continue
            words = segment.get("words")
            added_word = False
            if isinstance(words, list):
                for word_index, word in enumerate(words):
                    if not isinstance(word, dict):
                        continue
                    text = clean_text(
                        word.get("word", word.get("text", word.get("token")))
                    )
                    start = as_time(word.get("start"))
                    end = as_time(word.get("end"))
                    if not text or start is None or end is None or end < start:
                        continue
                    units.append(
                        {
                            "text": text,
                            "start": start,
                            "end": end,
                            "id": word.get("id", f"{segment_index}:{word_index}"),
                        }
                    )
                    added_word = True

            if added_word:
                continue

            text = clean_text(segment.get("text"))
            start = as_time(segment.get("start"))
            end = as_time(segment.get("end"))
            if text and start is not None and end is not None and end >= start:
                units.append(
                    {
                        "text": text,
                        "start": start,
                        "end": end,
                        "id": f"segment:{segment_index}",
                    }
                )

    # Chunk overlap can repeat already timestamped tokens. Keep the first exact
    # source-time/text occurrence, then restore strict source-time order.
    seen: set[tuple[float, float, str]] = set()
    unique: list[dict[str, Any]] = []
    for unit in sorted(units, key=lambda item: (item["start"], item["end"])):
        key = (round(unit["start"], 3), round(unit["end"], 3), unit["text"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(unit)

    if not unique:
        raise ValueError(
            "ASR JSON contains no timestamped Parakeet tokens/sentences "
            "or WhisperKit words/segments"
        )
    return data, unique


def load_diarization(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError("FluidAudio JSON must be an object")

    intervals: list[dict[str, Any]] = []
    segments = data.get("segments", [])
    if not isinstance(segments, list):
        segments = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        speaker = segment.get("speakerId")
        start = as_time(segment.get("startTimeSeconds"))
        end = as_time(segment.get("endTimeSeconds"))
        if speaker is None or start is None or end is None or end < start:
            continue
        intervals.append({"speaker": str(speaker), "start": start, "end": end})
    intervals.sort(key=lambda item: (item["start"], item["end"], item["speaker"]))
    return data, intervals


def interval_distance(unit: dict[str, Any], interval: dict[str, Any]) -> float:
    if unit["end"] < interval["start"]:
        return interval["start"] - unit["end"]
    if unit["start"] > interval["end"]:
        return unit["start"] - interval["end"]
    return 0.0


def assign_speakers(
    units: list[dict[str, Any]], intervals: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    previous_speaker: str | None = None

    for index, unit in enumerate(units):
        scores: dict[str, float] = {}
        for interval in intervals:
            overlap = max(
                0.0,
                min(unit["end"], interval["end"])
                - max(unit["start"], interval["start"]),
            )
            if overlap > 0:
                speaker = interval["speaker"]
                scores[speaker] = scores.get(speaker, 0.0) + overlap

        needs_review = False
        if scores:
            best_score = max(scores.values())
            candidates = sorted(
                speaker
                for speaker, score in scores.items()
                if abs(score - best_score) < 1e-9
            )
            if previous_speaker in candidates:
                speaker = previous_speaker
            else:
                speaker = candidates[0]
            needs_review = len(candidates) > 1
        elif intervals:
            distances = [interval_distance(unit, interval) for interval in intervals]
            best_distance = min(distances)
            candidates = sorted(
                {
                    interval["speaker"]
                    for interval, distance in zip(intervals, distances)
                    if abs(distance - best_distance) < 1e-9
                }
            )
            if best_distance > 1.5 and previous_speaker is not None:
                speaker = previous_speaker
            elif previous_speaker in candidates:
                speaker = previous_speaker
            else:
                speaker = candidates[0]
            needs_review = True
        else:
            speaker = "SPEAKER_?"
            needs_review = True

        # ASR engines can emit punctuation/subword fragments as separate units.
        # A tightly attached fragment belongs with its lexical predecessor.
        if index > 0:
            previous = units[index - 1]
            gap = unit["start"] - previous["end"]
            if (
                unit["text"]
                and not unit["text"][0].isspace()
                and -0.08 <= gap <= 0.08
            ):
                if speaker != previous["speaker"]:
                    needs_review = True
                speaker = previous["speaker"]

        unit["speaker"] = speaker
        unit["needsReview"] = needs_review
        previous_speaker = speaker

    return units


def smooth_short_flips(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Smooth only short speaker runs surrounded by the same speaker."""
    if len(units) < 3:
        return units

    runs: list[tuple[int, int]] = []
    start = 0
    for index in range(1, len(units) + 1):
        if index == len(units) or units[index]["speaker"] != units[start]["speaker"]:
            runs.append((start, index))
            start = index

    original_speakers = [unit["speaker"] for unit in units]
    replacements: list[tuple[int, int, str]] = []
    for run_index in range(1, len(runs) - 1):
        start, end = runs[run_index]
        previous_start, _ = runs[run_index - 1]
        next_start, _ = runs[run_index + 1]
        surrounding_speaker = original_speakers[previous_start]
        if original_speakers[next_start] != surrounding_speaker:
            continue
        duration = units[end - 1]["end"] - units[start]["start"]
        if duration >= 0.8 or end - start > 8:
            continue
        replacements.append((start, end, surrounding_speaker))

    for start, end, surrounding_speaker in replacements:
        for unit in units[start:end]:
            unit["speaker"] = surrounding_speaker
            unit["needsReview"] = True
    return units


def normalize_turn_text(parts: list[str]) -> str:
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def build_turns(
    units: list[dict[str, Any]], roles: dict[str, str], pause_split: float
) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for unit in units:
        gap = unit["start"] - current["end"] if current is not None else 0.0
        starts_new_turn = (
            current is None
            or unit["speaker"] != current["speaker"]
            or gap >= pause_split
        )
        if starts_new_turn:
            if current is not None:
                current["text"] = normalize_turn_text(current.pop("parts"))
                if current["text"]:
                    turns.append(current)
            current = {
                "speaker": unit["speaker"],
                "role": roles.get(unit["speaker"]),
                "start": unit["start"],
                "end": unit["end"],
                "parts": [unit["text"]],
                "needsReview": unit["needsReview"],
            }
        else:
            current["end"] = unit["end"]
            current["parts"].append(unit["text"])
            current["needsReview"] = current["needsReview"] or unit["needsReview"]

    if current is not None:
        current["text"] = normalize_turn_text(current.pop("parts"))
        if current["text"]:
            turns.append(current)
    return turns


def parse_roles(value: str) -> dict[str, str]:
    roles: dict[str, str] = {}
    if not value:
        return roles
    for entry in value.split(","):
        if "=" not in entry:
            raise ValueError(f"invalid role mapping: {entry!r}")
        speaker, role = (part.strip() for part in entry.split("=", 1))
        if not speaker or not role:
            raise ValueError(f"invalid role mapping: {entry!r}")
        roles[speaker] = role
    return roles


def render_markdown(turns: list[dict[str, Any]], roles: dict[str, str]) -> str:
    entries = []
    for turn in turns:
        label = roles.get(turn["speaker"], turn["speaker"])
        entries.append(
            f"**[{timestamp(turn['start'])}] {label}:** {turn['text']}"
        )
    return "\n\n".join(entries) + ("\n" if entries else "")


def duration_from(data: dict[str, Any], units: list[dict[str, Any]]) -> float:
    declared = as_time(data.get("durationSeconds"))
    observed = max((unit["end"] for unit in units), default=0.0)
    return max(declared or 0.0, observed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("asr_json", type=Path)
    parser.add_argument("diarization_json", type=Path)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--roles", default="", help='e.g. "S1=Interviewer,S2=Guest"')
    parser.add_argument("--pause-split", type=float, default=2.5)
    args = parser.parse_args()

    if args.pause_split <= 0:
        parser.error("--pause-split must be positive")

    try:
        roles = parse_roles(args.roles)
        asr_data, units = load_asr(args.asr_json)
        diarization_data, intervals = load_diarization(args.diarization_json)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))

    units = smooth_short_flips(assign_speakers(units, intervals))
    turns = build_turns(units, roles, args.pause_split)
    speakers = sorted({interval["speaker"] for interval in intervals} | {turn["speaker"] for turn in turns})
    duration = max(
        duration_from(asr_data, units),
        duration_from(diarization_data, intervals),
    )

    args.outdir.mkdir(parents=True, exist_ok=True)
    payload = {
        "language": asr_data.get("language"),
        "durationSeconds": duration,
        "roles": roles,
        "speakers": speakers,
        "turns": turns,
    }
    (args.outdir / "turns.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.outdir / "transcript.md").write_text(
        render_markdown(turns, {}), encoding="utf-8"
    )

    roles_path = args.outdir / "transcript_roles.md"
    if roles:
        roles_path.write_text(render_markdown(turns, roles), encoding="utf-8")
    elif roles_path.exists():
        roles_path.unlink()

    review_turns = sum(1 for turn in turns if turn["needsReview"])
    print(
        f"units={len(units)} turns={len(turns)} "
        f"speakers={len(speakers)} review_turns={review_turns}"
    )


if __name__ == "__main__":
    main()
