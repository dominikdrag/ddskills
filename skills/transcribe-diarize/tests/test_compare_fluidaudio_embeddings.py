import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "scripts"
    / "compare_fluidaudio_embeddings.py"
)


class EmbeddingComparisonTests(unittest.TestCase):
    def test_reveals_speaker_label_swap_across_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = []
            payloads = [
                [("S1", [1.0, 0.0]), ("S2", [0.0, 1.0])],
                [("S1", [0.0, 1.0]), ("S2", [1.0, 0.0])],
            ]
            for index, payload in enumerate(payloads, start=1):
                directory = root / f"part{index}"
                directory.mkdir()
                path = directory / "session-diarization.json"
                path.write_text(
                    json.dumps(
                        {
                            "segments": [
                                {
                                    "speakerId": speaker,
                                    "startTimeSeconds": 0.0,
                                    "endTimeSeconds": 1.0,
                                    "embedding": embedding,
                                }
                                for speaker, embedding in payload
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                paths.append(path)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), *(str(path) for path in paths)],
                check=True,
                capture_output=True,
                text=True,
            )

        lines = result.stdout.splitlines()
        columns = lines[0].split()
        matrix = {
            fields[0]: dict(zip(columns, map(float, fields[1:])))
            for line in lines[1:]
            if (fields := line.split())
        }

        self.assertAlmostEqual(1.0, matrix["part1:S1"]["part2:S2"], places=3)
        self.assertAlmostEqual(1.0, matrix["part1:S2"]["part2:S1"], places=3)
        self.assertAlmostEqual(0.0, matrix["part1:S1"]["part2:S1"], places=3)


if __name__ == "__main__":
    unittest.main()
