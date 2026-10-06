"""Detecção de entonação de pergunta na fala (pitch final ascendente).

O Whisper transcreve as palavras mas quase nunca marca "?": perguntas de
"sim/não" (ex.: "vamos fazer um novo teste?") não têm palavra interrogativa
para a heurística do orthography pegar. Aqui medimos a frequência fundamental
(F0) do final do enunciado: em PT-BR, pergunta tem subida de pitch no fim.

Fluxo:
    question_hint(audio_bytes) → decode (PyAV) → pitch_contour → compara F0
    do trecho final com o trecho anterior → True se subiu X%.

Independência de modelo: só numpy + PyAV (dependency do faster-whisper).
"""

import io

import av
import numpy as np

SAMPLE_RATE = 16000
F0_MIN = 70.0
F0_MAX = 400.0
_RATIO_VOICED = 0.30
_REL_RISE = 0.15
_MIN_VOICED = 5


def decode_pcm16(audio_bytes: bytes) -> np.ndarray | None:
    """Decodifica bytes (wav/ogg/opus/webm) para PCM int16 mono 16 kHz."""
    try:
        container = av.open(io.BytesIO(audio_bytes))
        if not any(s.type == "audio" for s in container.streams):
            container.close()
            return None
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        chunks = []
        for frame in container.decode(audio=0):
            for rframe in resampler.resample(frame):
                chunks.append(rframe.to_ndarray())
        for rframe in resampler.resample(None):
            chunks.append(rframe.to_ndarray())
        container.close()
        if not chunks:
            return None
        return np.concatenate(chunks, axis=1).ravel().astype(np.int16)
    except Exception:
        return None


def pitch_contour(pcm: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Contorno de F0 (Hz) por janela de 30 ms (hop 10 ms); frames não
    vozeados são omitidos."""
    frame_len = int(0.030 * sample_rate)
    hop = int(0.010 * sample_rate)
    if len(pcm) < frame_len:
        return np.array([], dtype=float)
    janela = np.hanning(frame_len)
    f0s = []
    for start in range(0, len(pcm) - frame_len, hop):
        quadro = pcm[start : start + frame_len].astype(np.float32) * janela
        if np.sqrt((quadro * quadro).mean()) < 1e-4:
            continue
        f0 = _autocorrelacao(quadro, sample_rate)
        if f0 is not None:
            f0s.append(f0)
    return np.array(f0s, dtype=float)


def _autocorrelacao(quadro, sample_rate: int) -> float | None:
    """Autocorrelação com janela de vazio normalizado (style pYIN-lite)."""
    centro = quadro - quadro.mean()
    corr = np.correlate(centro, centro, "full")[centro.size - 1 :]
    if corr[0] <= 0:
        return None
    lag_min = max(1, int(sample_rate / F0_MAX))
    lag_max = min(int(sample_rate / F0_MIN), corr.size - 1)
    trecho = corr[lag_min : lag_max + 1]
    if trecho.size < 3:
        return None
    lag = int(np.argmax(trecho)) + lag_min
    razao = corr[lag] / corr[0]
    if razao < _RATIO_VOICED:
        return None
    f0 = sample_rate / lag
    if F0_MIN <= f0 <= F0_MAX:
        return f0
    return None


def is_question_intonation(
    pcm: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    rel_rise: float = _REL_RISE,
    min_voiced: int = _MIN_VOICED,
) -> bool:
    """True se a F0 do final do enunciado subiu (entonação de pergunta).

    Compara a média do último 40% dos frames vozeados com os primeiros 60%.
    Subida relativa > ``rel_rise`` (default 15%) → pergunta.
    """
    f0s = pitch_contour(pcm, sample_rate)
    if len(f0s) < min_voiced:
        return False
    corte = int(len(f0s) * 0.6)
    inicio, fim = f0s[:corte], f0s[corte:]
    if len(inicio) < 2 or len(fim) < 2:
        return False
    m_inicio, m_fim = float(inicio.mean()), float(fim.mean())
    if m_inicio <= 0:
        return False
    return (m_fim - m_inicio) / m_inicio > rel_rise


def question_hint(audio_bytes: bytes) -> bool:
    """Rota de integração: decode + entonação. Falha/áudio inválido → False."""
    pcm = decode_pcm16(audio_bytes)
    if pcm is None or len(pcm) < SAMPLE_RATE // 2:
        return False
    return is_question_intonation(pcm)


__all__ = [
    "decode_pcm16",
    "pitch_contour",
    "is_question_intonation",
    "question_hint",
]
