"""Download local ONNX models used by VAD and Smart Turn."""

from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"

MODELS = {
    "silero_vad.onnx": (
        "https://raw.githubusercontent.com/snakers4/silero-vad/master/"
        "src/silero_vad/data/silero_vad.onnx"
    ),
    "smart_turn_v3.onnx": (
        "https://huggingface.co/pipecat-ai/smart-turn-v3/resolve/main/"
        "smart-turn-v3.2-cpu.onnx"
    ),
}


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in MODELS.items():
        target = MODELS_DIR / filename
        if target.exists():
            print(f"exists {target}")
            continue
        print(f"download {filename}")
        urlretrieve(url, target)
        print(f"saved {target}")


if __name__ == "__main__":
    main()
