import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "transcribe_diarize.sh"


class TranscriptionRoutingTests(unittest.TestCase):
    def make_executable(self, path: Path, source: str) -> Path:
        path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
        path.chmod(0o755)
        return path

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.input_path = self.root / "recording.qta"
        self.input_path.write_bytes(b"test")
        self.ffmpeg = self.make_executable(
            self.root / "ffmpeg",
            """
            #!/bin/sh
            for argument in "$@"; do output="$argument"; done
            : > "$output"
            """,
        )
        self.fluid_log = self.root / "fluid.log"
        self.fluid = self.make_executable(
            self.root / "fluidaudiocli",
            """
            #!/usr/bin/env python3
            import json
            import os
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            Path(os.environ["FLUID_LOG"]).write_text(" ".join(args), encoding="utf-8")
            output = Path(args[args.index("--output") + 1])
            output.write_text(json.dumps({
                "durationSeconds": 1.0,
                "segments": [{
                    "speakerId": "S1",
                    "startTimeSeconds": 0.0,
                    "endTimeSeconds": 1.0,
                    "embedding": [1.0, 0.0]
                }]
            }), encoding="utf-8")
            """,
        )

    def environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "FFMPEG_BIN": str(self.ffmpeg),
                "FLUID_AUDIO_CLI": str(self.fluid),
                "FLUID_LOG": str(self.fluid_log),
            }
        )
        return environment

    def run_script(self, engine: str, environment: dict[str, str]) -> Path:
        output = self.root / f"{engine}-output"
        subprocess.run(
            [
                "bash",
                str(SCRIPT),
                str(self.input_path),
                "--engine",
                engine,
                "--lang",
                "pl",
                "--speakers",
                "2",
                "--outdir",
                str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        return output

    def test_whisperkit_uses_large_v3_turbo_without_vad_and_fluidaudio(self):
        whisper_log = self.root / "whisper.log"
        whisper = self.make_executable(
            self.root / "whisperkit-cli",
            """
            #!/usr/bin/env python3
            import json
            import os
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            Path(os.environ["WHISPER_LOG"]).write_text(" ".join(args), encoding="utf-8")
            output = Path(args[args.index("--report-path") + 1])
            output.joinpath("session.json").write_text(json.dumps({
                "language": "pl",
                "segments": [{
                    "start": 0.0,
                    "end": 1.0,
                    "text": " Test.",
                    "words": [{"word": " Test.", "start": 0.0, "end": 1.0}]
                }]
            }), encoding="utf-8")
            """,
        )
        environment = self.environment()
        environment.update(
            {"WHISPERKIT_CLI": str(whisper), "WHISPER_LOG": str(whisper_log)}
        )

        output = self.run_script("whisperkit", environment)
        whisper_arguments = whisper_log.read_text(encoding="utf-8")
        fluid_arguments = self.fluid_log.read_text(encoding="utf-8")

        self.assertIn("--model large-v3-v20240930_626MB", whisper_arguments)
        self.assertIn("--chunking-strategy none", whisper_arguments)
        self.assertNotIn("--chunking-strategy vad", whisper_arguments)
        self.assertIn("--num-speakers 2", fluid_arguments)
        self.assertTrue((output / "session-diarization.json").exists())
        self.assertTrue((output / "transcript.md").exists())
        self.assertFalse((output / "session.wav").exists())

    def test_parakeet_uses_verified_model_and_fluidaudio(self):
        parakeet_log = self.root / "parakeet.log"
        parakeet = self.make_executable(
            self.root / "parakeet-python",
            """
            #!/usr/bin/env python3
            import json
            import os
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            if args and args[0] == "-c":
                raise SystemExit(0)
            Path(os.environ["PARAKEET_LOG"]).write_text(" ".join(args), encoding="utf-8")
            output = Path(args[args.index("--output-path") + 1] + ".json")
            output.write_text(json.dumps({
                "language": "pl",
                "sentences": [{
                    "tokens": [{"text": " Test.", "start": 0.0, "end": 1.0}]
                }]
            }), encoding="utf-8")
            """,
        )
        environment = self.environment()
        environment.update(
            {"PARAKEET_PYTHON": str(parakeet), "PARAKEET_LOG": str(parakeet_log)}
        )

        output = self.run_script("parakeet", environment)
        parakeet_arguments = parakeet_log.read_text(encoding="utf-8")

        self.assertIn(
            "--model mlx-community/parakeet-tdt-0.6b-v3", parakeet_arguments
        )
        self.assertIn("--num-speakers 2", self.fluid_log.read_text(encoding="utf-8"))
        self.assertTrue((output / "session-asr.json").exists())
        self.assertTrue((output / "session-diarization.json").exists())
        self.assertTrue((output / "transcript.md").exists())


if __name__ == "__main__":
    unittest.main()
