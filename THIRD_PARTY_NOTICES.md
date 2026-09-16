# Third-party notices

The repository's original code and documentation are covered by [MIT](LICENSE). External programs, libraries, model weights, and services retain their own licenses and terms. Installing a skill does not install or relicense those dependencies.

## Transcription

The helpers integrate [MLX-Audio](https://github.com/Blaizzy/mlx-audio), [FluidAudio](https://github.com/FluidInference/FluidAudio), [WhisperKit](https://github.com/argmaxinc/WhisperKit), and [FFmpeg](https://ffmpeg.org/). Parakeet uses the [MLX community conversion](https://huggingface.co/mlx-community/parakeet-tdt-0.6b-v3) of [NVIDIA's Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3). Consult the selected release's license and model card before using or redistributing a runtime or model. Their source and model weights are not bundled here.

## Campaign production

The rendering and packaging helpers use [Playwright](https://github.com/microsoft/playwright), [Sharp](https://github.com/lovell/sharp), [Pillow](https://github.com/python-pillow/Pillow), and FFmpeg when those tools are available. These packages are not bundled here.

The bundled InTouch campaign overview is an example from Dominik Drąg's app campaign. Its typography uses [Caprasimo](https://github.com/docrepair-fonts/caprasimo-fonts) and [Figtree](https://github.com/erikdkennedy/figtree); no font files are included. The example demonstrates the workflow and does not grant trademark rights or imply endorsement of derivative campaigns.

## Installation and format

Installation examples use the independently maintained [skills CLI](https://github.com/vercel-labs/skills). Skill folders follow the [Agent Skills format](https://agentskills.io/). This repository is an independent project.
