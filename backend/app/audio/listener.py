"""Modo viva-voz local: "ei Study, <pergunta>" → resposta falada.

Pipeline: arecord (PCM 16 kHz mono) → EnergyVAD → faster-whisper →
wake_word.extract_command → /api/chat → Piper → aplay.

Meio-duplex: enquanto fala, ignora o microfone para não se auto-disparar.
Requisitos de sistema: alsa-utils (arecord/aplay), já presentes no
Pop!_OS. Uso:

    cd backend && .venv/bin/python -m app.audio.listener
"""

import logging
import os
import re
import signal
import subprocess
import sys

import numpy as np
import requests

from . import speech_to_text, text_to_speech
from .vad import FRAME_SAMPLES, SAMPLE_RATE, EnergyVAD, pcm_to_wav_bytes
from .wake_word import extract_command

API_URL = os.getenv("STUDY_API_URL", "http://127.0.0.1:8000")
THRESHOLD_RMS = float(os.getenv("STUDY_VAD_THRESHOLD", "500"))

log = logging.getLogger("studyagent.listener")

_arecord: subprocess.Popen | None = None


def _abrir_microfone() -> subprocess.Popen:
    global _arecord
    if _arecord is None or _arecord.poll() is not None:
        _arecord = subprocess.Popen(
            [
                "arecord", "-q", "-t", "raw",
                "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    return _arecord


def ouvir_enunciado(vad: EnergyVAD, limite_s: float = 12.0) -> np.ndarray | None:
    """Bloqueia até captar um enunciado completo (ou timeout)."""
    proc = _abrir_microfone()
    assert proc.stdout is not None
    quadro_bytes = FRAME_SAMPLES * 2
    max_quadros = int(limite_s * SAMPLE_RATE / (FRAME_SAMPLES))
    lidos = 0
    while lidos < max_quadros:
        bruto = proc.stdout.read(quadro_bytes)
        if not bruto or len(bruto) < quadro_bytes:
            continue
        quadro = np.frombuffer(bruto, dtype="<i2")
        lidos += 1
        enunciado = vad.feed(quadro)
        if enunciado is not None:
            return enunciado
    return None


def limpar_para_fala(texto: str) -> str:
    """Remove fontes/markdown antes de sintetizar."""
    texto = re.sub(r"\[fonte:[^\]]*\]", "", texto)
    texto = re.sub(r"`{1,3}[^`]*`{1,3}", " trecho de código ", texto)
    texto = re.sub(r"\[(\d+)\]\([^)]*\)", r"\1", texto)
    texto = re.sub(r"\]\([^)]*\)", "", texto)
    texto = re.sub(r"[#*_>|]+", " ", texto)
    texto = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def falar(wav_bytes: bytes) -> None:
    subprocess.run(["aplay", "-q"], input=wav_bytes, check=False)


def enviar_comando(comando: str) -> str | None:
    try:
        resp = requests.post(
            f"{API_URL}/api/chat",
            json={"message": comando, "session_id": "voz-livre"},
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()["response"]
    except Exception as exc:
        log.warning("falha ao consultar a API: %s", exc)
        return None


def ciclo(ouvir_resposta: bool = True) -> bool:
    """Um ciclo completo. Retorna False se o microfone indisponível."""
    vad = EnergyVAD(threshold_rms=THRESHOLD_RMS)
    try:
        pcm = ouvir_enunciado(vad)
    except FileNotFoundError:
        print("arecord não encontrado — instale alsa-utils.", file=sys.stderr)
        return False
    if pcm is None or len(pcm) < SAMPLE_RATE // 2:
        return True
    wav = pcm_to_wav_bytes(pcm)
    texto = speech_to_text.transcribe(wav, "utterance.wav")
    log.info("ouvi: %r", texto)
    comando = extract_command(texto or "")
    if not comando:
        return True  # não era para o agente
    log.info("comando: %r", comando)
    resposta = enviar_comando(comando)
    if resposta and ouvir_resposta:
        falar(text_to_speech.synthesize(limpar_para_fala(resposta)[:1500]))
    elif resposta:
        print("StudyAgent:", resposta[:400])
    return True


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print('🎧 Modo viva-voz ativo. Diga "ei study, <sua pergunta>" (Ctrl+C sai).')
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    while True:
        if not ciclo():
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
