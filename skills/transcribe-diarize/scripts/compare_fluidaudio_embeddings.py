#!/usr/bin/env python3
"""Compare duration-weighted FluidAudio speaker embeddings across files.

Anonymous speaker IDs are local to each diarization run. This helper prints a
cosine-similarity matrix so the same voices can be matched across consecutive
recordings before role names are applied.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def duration(segment: dict[str, Any]) -> float:
    try:
        start = float(segment["startTimeSeconds"])
        end = float(segment["endTimeSeconds"])
    except (KeyError, TypeError, ValueError):
        return 0.01
    return max(0.01, end - start)


def normalized_speaker_means(path: Path) -> dict[str, list[float]]:
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: FluidAudio JSON must be an object")

    accumulators: dict[str, tuple[list[float], float]] = {}
    segments = data.get("segments", [])
    if not isinstance(segments, list):
        segments = []

    for segment in segments:
        if not isinstance(segment, dict):
            continue
        speaker = segment.get("speakerId")
        embedding = segment.get("embedding")
        if speaker is None or not isinstance(embedding, list) or not embedding:
            continue
        try:
            vector = [float(value) for value in embedding]
        except (TypeError, ValueError):
            continue

        key = str(speaker)
        weight = duration(segment)
        if key not in accumulators:
            accumulators[key] = ([0.0] * len(vector), 0.0)
        total, total_weight = accumulators[key]
        if len(total) != len(vector):
            raise ValueError(f"{path}: inconsistent embedding dimensions for {key}")
        for index, value in enumerate(vector):
            total[index] += value * weight
        accumulators[key] = (total, total_weight + weight)

    means: dict[str, list[float]] = {}
    for speaker, (total, total_weight) in accumulators.items():
        mean = [value / total_weight for value in total]
        norm = math.sqrt(sum(value * value for value in mean))
        if norm > 0:
            means[speaker] = [value / norm for value in mean]

    if not means:
        raise ValueError(f"{path}: no speaker embeddings found")
    return means


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("cannot compare embeddings with different dimensions")
    return sum(a * b for a, b in zip(left, right))


def unique_file_labels(paths: list[Path]) -> list[str]:
    candidates = [path.parent.name or path.stem for path in paths]
    counts = {label: candidates.count(label) for label in candidates}
    return [
        label if counts[label] == 1 else f"{label}/{path.stem}"
        for path, label in zip(paths, candidates)
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("diarization_json", nargs="+", type=Path)
    args = parser.parse_args()

    try:
        file_labels = unique_file_labels(args.diarization_json)
        vectors: dict[str, list[float]] = {}
        for file_label, path in zip(file_labels, args.diarization_json):
            for speaker, vector in normalized_speaker_means(path).items():
                vectors[f"{file_label}:{speaker}"] = vector
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))

    labels = sorted(vectors)
    width = max(7, max(len(label) for label in labels))
    print(" " * (width + 1) + " ".join(f"{label:>{width}}" for label in labels))
    for left in labels:
        values = " ".join(
            f"{cosine(vectors[left], vectors[right]):>{width}.3f}"
            for right in labels
        )
        print(f"{left:>{width}} {values}")


if __name__ == "__main__":
    main()
