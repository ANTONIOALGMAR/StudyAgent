"""Transcrição fala → texto com faster-whisper.

Configurável por variáveis de ambiente (backend/.env):
- STUDY_STT_MODEL   modelo (default: "small")
- STUDY_STT_DEVICE  device (default: "cpu")
- STUDY_STT_COMPUTE compute type (default: "int8")
- STUDY_STT_BEAM    beam size (default: 1 = greedy, ~5x mais rápido que beam 5
                    na CPU; aumente para 5 se a precisão do PT-BR cair)
"""

import os
import tempfile
import threading
from pathlib import Path

from faster_whisper import WhisperModel

from . import intonation, orthography

MODEL_SIZE = os.getenv("STUDY_STT_MODEL", "small")
_DEVICE = os.getenv("STUDY_STT_DEVICE", "cpu")
_COMPUTE_TYPE = os.getenv("STUDY_STT_COMPUTE", "int8")
_BEAM_SIZE = int(os.getenv("STUDY_STT_BEAM", "1"))
# Anti-alucinação (whisper "ouve" texto onde só há ruído/silêncio): descarta
# segmentos com baixa probabilidade de ser fala e repetição suspeita.
# Defaults = recomendações oficiais do OpenAI Whisper.
_NO_SPEECH_THRESHOLD = float(os.getenv("STUDY_STT_NO_SPEECH", "0.6"))
_LOGPROB_THRESHOLD = float(os.getenv("STUDY_STT_LOGPROB", "-1.0"))
_COMPRESSION_RATIO_THRESHOLD = float(os.getenv("STUDY_STT_COMPRESSION", "2.4"))
# Corta "alucinação" que o Whisper produz em silêncio/fundo após a fala.
_HALLUCINATION_SILENCE = float(os.getenv("STUDY_STT_HALLUC_SILENCE", "2.0"))
# Guiar a pontuação final pela entonação (pitch subindo no fim = "?").
_USE_INTONATION = os.getenv("STUDY_STT_INTONATION", "1") not in ("0", "false", "no")

_lock = threading.Lock()
_model = None
_pergunta_hint = False


def _get_model():
    global _model
    with _lock:
        if _model is None:
            _model = WhisperModel(MODEL_SIZE, device=_DEVICE, compute_type=_COMPUTE_TYPE)
    return _model


def preload():
    _get_model()


INITIAL_PROMPT = (
    "Transcrição em português do Brasil com ortografia, acentuação e "
    "pontuação corretas. As perguntas do aluno começam com letra maiúscula "
    "e terminam com '?'. "
    "Exemplos: 'O que é fotossíntese?', 'Como resolvo essa equação?', "
    "'Me explica a regra de três, por favor.' "
    "Palavras comuns: equação, fração, capítulo, exercício, história."
)


def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    # Entonação de pergunta (F0 subindo no fim) roda em paralelo ao Whisper:
    # é o único jeito de pegar "vamos fazer um novo teste?" sem palavra
    # interrogativa. Falha de decode → False → heurística padrão.
    hint = threading.Thread(target=_face_pergunta, args=(audio_bytes,))
    hint.start()

    suffix = Path(filename).suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        model = _get_model()
        segments, info = model.transcribe(
            tmp_path,
            language="pt",
            beam_size=_BEAM_SIZE,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
            condition_on_previous_text=False,
            initial_prompt=INITIAL_PROMPT,
            no_speech_threshold=_NO_SPEECH_THRESHOLD,
            log_prob_threshold=_LOGPROB_THRESHOLD,
            compression_ratio_threshold=_COMPRESSION_RATIO_THRESHOLD,
            hallucination_silence_threshold=_HALLUCINATION_SILENCE,
        )
        # O faster-whisper já descarta segmentos de silêncio/ruído pelos
        # thresholds acima; se nada sobrou, o enunciado era só ruído.
        texto = " ".join(s.text.strip() for s in segments).strip()
        hint.join(timeout=10)
        return orthography.fix_orthography(texto, força_pergunta=_pergunta_hint) if texto else ""
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _face_pergunta(audio_bytes: bytes) -> None:
    """Calcula a entonação em uma thread (não bloqueia o STT)."""
    global _pergunta_hint
    if not _USE_INTONATION:
        return
    try:
        _pergunta_hint = intonation.question_hint(audio_bytes)
    except Exception:
        _pergunta_hint = False
