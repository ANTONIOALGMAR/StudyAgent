"""Testes do detector de entonação de pergunta (app/audio/intonation.py).

Usa sinais sintéticos (chirps) — puras funções numpy, sem modelo STT.
"""

import io
import wave

import numpy as np

from app.audio import intonation

SR = intonation.SAMPLE_RATE


def _chirp(f0: float, f1: float, dur: float = 1.2) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    fase = 2 * np.pi * (f0 * t + 0.5 * (f1 - f0) * t * t / dur)
    return (0.3 * 32767 * np.sin(fase)).astype(np.int16)


def _wav_bytes(pcm: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


class TestQuestionIntonation:
    def test_rising_pitch_is_question(self):
        assert intonation.is_question_intonation(_chirp(120, 220))

    def test_falling_pitch_is_not_question(self):
        assert not intonation.is_question_intonation(_chirp(220, 120))

    def test_flat_pitch_is_not_question(self):
        assert not intonation.is_question_intonation(_chirp(150, 155))

    def test_too_short_is_not_question(self):
        pcm = np.zeros(SR // 4, dtype=np.int16)
        assert not intonation.is_question_intonation(pcm)

    def test_silence_is_not_question(self):
        pcm = np.zeros(2 * SR, dtype=np.int16)
        assert not intonation.is_question_intonation(pcm)


class TestDecodeAndHint:
    def test_decode_wav_mono(self):
        pcm = _chirp(120, 220)
        decoded = intonation.decode_pcm16(_wav_bytes(pcm))
        assert decoded is not None
        assert decoded.dtype == np.int16
        assert decoded.ndim == 1
        assert decoded.shape[0] == pcm.shape[0]

    def test_question_hint_rising(self):
        assert intonation.question_hint(_wav_bytes(_chirp(120, 220)))

    def test_question_hint_falling(self):
        assert not intonation.question_hint(_wav_bytes(_chirp(220, 120)))

    def test_question_hint_invalid_bytes(self):
        assert not intonation.question_hint(b"nao sou audio")

    def test_question_hint_empty(self):
        assert not intonation.question_hint(b"")
