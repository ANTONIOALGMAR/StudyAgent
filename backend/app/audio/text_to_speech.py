import io
import threading
import wave
from pathlib import Path

from piper import PiperVoice

VOICE_PATH = Path(__file__).resolve().parents[2] / "models" / "piper" / "pt_BR-faber-medium.onnx"

_lock = threading.Lock()
_voice = None


def _get_voice():
    global _voice
    with _lock:
        if _voice is None:
            _voice = PiperVoice.load(str(VOICE_PATH))
    return _voice


def preload():
    _get_voice()


def synthesize(text: str) -> bytes:
    voice = _get_voice()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setframerate(voice.config.sample_rate)
        wav.setsampwidth(2)
        wav.setnchannels(1)
        voice.synthesize_wav(text, wav)
    return buffer.getvalue()


def available():
    return VOICE_PATH.exists()
