"""One-time official pretrained model download; no downloads during application use."""
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen
import json

URL = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task"
EXPECTED_SHA256 = "97952348cf6a6a4915c2ea1496b4b37ebabc50cbbf80571435643c455f2b0482"
ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / "models" / "gesture_recognizer.task"
    target.parent.mkdir(exist_ok=True)
    if not target.exists():
        with urlopen(URL, timeout=120) as response:
            content = response.read()
        if len(content) < 1_000_000:
            raise RuntimeError("Model response is unexpectedly small; refusing to save it.")
        if sha256(content).hexdigest() != EXPECTED_SHA256:
            raise RuntimeError("Downloaded model checksum differs from the verified version-1 artifact.")
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
    digest = sha256(target.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError("Existing model checksum is invalid. Remove the corrupted model and rerun this script.")
    (target.parent / "model-manifest.json").write_text(json.dumps({"url":URL,"sha256":digest,
        "bytes":target.stat().st_size,"model_version":1},indent=2),encoding="utf-8")
    print(f"Model ready: {target.name}; SHA256 {digest}")


if __name__ == "__main__":
    main()
