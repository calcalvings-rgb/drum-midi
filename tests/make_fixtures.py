"""Generate deterministic synthetic WAV fixtures used by the tests and README."""

import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from tests.test_detect import make_drum_only, make_drum_plus_sine


def write_wav(path: Path, samples: np.ndarray, sample_rate: int = 44100) -> None:
    pcm = np.round(np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def main() -> None:
    fixtures = ROOT / "fixtures"
    fixtures.mkdir(exist_ok=True)
    write_wav(fixtures / "drum_stem.wav", make_drum_only())
    write_wav(fixtures / "drum_full.wav", make_drum_plus_sine())


if __name__ == "__main__":
    main()
