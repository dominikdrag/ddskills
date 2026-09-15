import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "align_parakeet_fluidaudio.py"


class AlignmentTests(unittest.TestCase):
    def run_alignment(self, asr, diarization, *extra_args):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        asr_path = root / "asr.json"
        diarization_path = root / "diarization.json"
        output_path = root / "output"
        asr_path.write_text(json.dumps(asr), encoding="utf-8")
        diarization_path.write_text(json.dumps(diarization), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(asr_path),
                str(diarization_path),
                "--outdir",
                str(output_path),
                *extra_args,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return output_path, result

    def test_aligns_tokens_maps_roles_and_marks_gap_fallback(self):
        asr = {
            "language": "pl",
            "sentences": [
                {
                    "tokens": [
                        {"id": 1, "text": " Cześć", "start": 0.1, "end": 0.4},
                        {"id": 2, "text": ".", "start": 0.4, "end": 0.45},
                    ]
                },
                {
                    "tokens": [
                        {"id": 3, "text": " Dzień dobry", "start": 1.0, "end": 1.4}
                    ]
                },
                {
                    "tokens": [
                        {"id": 4, "text": " Później", "start": 3.0, "end": 3.3}
                    ]
                },
            ],
        }
        diarization = {
            "durationSeconds": 4,
            "segments": [
                {"speakerId": "S1", "startTimeSeconds": 0.0, "endTimeSeconds": 0.8},
                {"speakerId": "S2", "startTimeSeconds": 0.9, "endTimeSeconds": 1.8},
            ],
        }

        output, result = self.run_alignment(
            asr, diarization, "--roles", "S1=Interviewer,S2=Guest"
        )
        generic = (output / "transcript.md").read_text(encoding="utf-8")
        mapped = (output / "transcript_roles.md").read_text(encoding="utf-8")
        turns = json.loads((output / "turns.json").read_text(encoding="utf-8"))

        self.assertIn("S1:", generic)
        self.assertIn("S2:", generic)
        self.assertIn("Interviewer:", mapped)
        self.assertIn("Guest:", mapped)
        self.assertEqual([turn["start"] for turn in turns["turns"]], sorted(turn["start"] for turn in turns["turns"]))
        self.assertTrue(turns["turns"][-1]["needsReview"])
        self.assertNotIn("Cześć", result.stdout)
        self.assertNotIn("talk-time", result.stdout)
        self.assertNotIn("talkTime", result.stdout)

    def test_uses_timestamped_sentence_when_tokens_are_absent(self):
        asr = {
            "language": "pl",
            "sentences": [{"text": " Zdanie.", "start": 0.2, "end": 0.9}],
        }
        diarization = {
            "segments": [
                {"speakerId": "S1", "startTimeSeconds": 0.0, "endTimeSeconds": 1.0}
            ]
        }

        output, _ = self.run_alignment(asr, diarization)
        transcript = (output / "transcript.md").read_text(encoding="utf-8")
        turns = json.loads((output / "turns.json").read_text(encoding="utf-8"))

        self.assertIn("Zdanie.", transcript)
        self.assertEqual("S1", turns["turns"][0]["speaker"])
        self.assertFalse((output / "transcript_roles.md").exists())

    def test_aligns_whisperkit_words_with_fluidaudio(self):
        asr = {
            "language": "pl",
            "segments": [
                {
                    "start": 0.1,
                    "end": 0.9,
                    "text": " Cześć świecie.",
                    "words": [
                        {"word": " Cześć", "start": 0.1, "end": 0.4},
                        {"word": " świecie.", "start": 0.4, "end": 0.9},
                    ],
                },
                {
                    "start": 1.1,
                    "end": 1.8,
                    "text": " Dzień dobry.",
                    "words": [
                        {"word": " Dzień", "start": 1.1, "end": 1.4},
                        {"word": " dobry.", "start": 1.4, "end": 1.8},
                    ],
                },
            ],
        }
        diarization = {
            "durationSeconds": 2,
            "segments": [
                {"speakerId": "S1", "startTimeSeconds": 0.0, "endTimeSeconds": 1.0},
                {"speakerId": "S2", "startTimeSeconds": 1.0, "endTimeSeconds": 2.0},
            ],
        }

        output, _ = self.run_alignment(
            asr, diarization, "--roles", "S1=Dominik,S2=Krzysiek"
        )
        transcript = (output / "transcript_roles.md").read_text(encoding="utf-8")
        turns = json.loads((output / "turns.json").read_text(encoding="utf-8"))

        self.assertIn("Dominik:** Cześć świecie.", transcript)
        self.assertIn("Krzysiek:** Dzień dobry.", transcript)
        self.assertEqual(["S1", "S2"], [turn["speaker"] for turn in turns["turns"]])


if __name__ == "__main__":
    unittest.main()
