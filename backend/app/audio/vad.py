"""VAD por energia — segmentação de fala em fluxo PCM 16 kHz mono.

Lógica pura sobre numpy (sem hardware): o coletor real (arecord) alimenta
``EnergyVAD.feed`` com quadros de ~30 ms e recebe a fala completa quando
há uma pausa longa o suficiente.
"""

import numpy as np

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 480

# silêncio de ~0,8 s encerra a fala; guarda ~150 ms antes do início
SILENCE_FRAMES_TO_END = int(800 / FRAME_MS)
PREROLL_FRAMES = 5


class EnergyVAD:
    def __init__(self, threshold_rms: float = 500.0):
        self.threshold = threshold_rms
        self._preroll: list[np.ndarray] = []
        self._speech: list[np.ndarray] = []
        self._silence_run = SILENCE_FRAMES_TO_END
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def reset(self) -> None:
        self._preroll.clear()
        self._speech.clear()
        self._silence_run = SILENCE_FRAMES_TO_END
        self._active = False

    def feed(self, frame: np.ndarray) -> np.ndarray | None:
        """Consome um quadro; devolve o enunciado completo ou None."""
        if frame.ndim != 1 or len(frame) == 0:
            return None
        rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
        loud = rms >= self.threshold

        if not self._active:
            self._preroll.append(frame)
            if len(self._preroll) > PREROLL_FRAMES:
                self._preroll.pop(0)
            if loud:
                self._active = True
                self._speech = list(self._preroll)
                self._preroll.clear()
                self._silence_run = 0
            return None

        self._speech.append(frame)
        if loud:
            self._silence_run = 0
        else:
            self._silence_run += 1
            if self._silence_run >= SILENCE_FRAMES_TO_END:
                utterance = np.concatenate(self._speech)
                self.reset()
                # cauda silenciosa não precisa ir para o STT (~0,8 s de sobra)
                return trim_silence_tail(utterance)
        return None


def trim_silence_tail(pcm: np.ndarray, threshold: float = 300.0,
                      frame_samples: int = FRAME_SAMPLES) -> np.ndarray:
    """Corta quadros silenciosos do fim (mantém no mínimo 1)."""
    fim = len(pcm)
    while fim > frame_samples:
        quadro = pcm[fim - frame_samples:fim]
        rms = float(np.sqrt(np.mean(quadro.astype(np.float32) ** 2)))
        if rms >= threshold:
            break
        fim -= frame_samples
    return pcm[:fim]


def pcm_to_wav_bytes(pcm16: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    """PCM int16 mono → bytes WAV completos (para STT e TTS-playback)."""
    import io
    import struct
    import wave

    dados = pcm16.astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(struct.calcsize("<h"))
        wav.setframerate(sample_rate)
        wav.writeframes(dados)
    return buf.getvalue()


__all__ = [
    "SAMPLE_RATE",
    "FRAME_SAMPLES",
    "EnergyVAD",
    "trim_silence_tail",
    "pcm_to_wav_bytes",
]
