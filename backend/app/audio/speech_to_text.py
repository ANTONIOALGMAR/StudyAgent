import tempfile
import threading
from pathlib import Path

from faster_whisper import WhisperModel

MODEL_SIZE = "small"
_lock = threading.Lock()
_model = None


def _get_model():
    global _model
    with _lock:
        if _model is None:
            _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def preload():
    _get_model()


def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    suffix = Path(filename).suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        model = _get_model()
        segments, info = model.transcribe(tmp_path, language="pt")
        return " ".join(s.text.strip() for s in segments).strip()
    finally:
        Path(tmp_path).unlink(missing_ok=True)
