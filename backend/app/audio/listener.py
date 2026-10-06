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
import select
import signal
import subprocess
import sys
import time

import numpy as np
import requests

from . import speech_to_text, text_to_speech
from .vad import FRAME_SAMPLES, SAMPLE_RATE, EnergyVAD, pcm_to_wav_bytes
from .wake_word import extract_command

API_URL = os.getenv("STUDY_API_URL", "http://127.0.0.1:8000")
THRESHOLD_RMS = float(os.getenv("STUDY_VAD_THRESHOLD", "500"))
# Timeout de leitura de um frame do arecord. Sem isso, um microfone que trava
# (device ocupada por outro app, USB removido) deixa `read()` bloqueado para
# sempre e o serviço fica "vivo" porém surdo — sem restart, porque o processo
# não sai. Ver R10 no risk-register.
FRAME_TIMEOUT_S = float(os.getenv("STUDY_AUDIO_TIMEOUT", "5"))
# Teto do playback antes de desistir da resposta falada.
TTS_TIMEOUT_S = float(os.getenv("STUDY_TTS_TIMEOUT", "120"))
# Pausa entre ciclos: evita spin de 100% de CPU quando o microfone está morto.
CYCLE_SLEEP_S = float(os.getenv("STUDY_CYCLE_SLEEP", "0.5"))

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


def _fechar_microfone() -> None:
    """Interrompe a captura e descarta os frames acumulados.

    Garante o meio-duplex: o microfone fica aberto APENAS durante a escuta
    ativa. Sem isso, o áudio da própria fala (aplay) e o tempo do modelo
    seriam capturados no buffer do arecord, transcritos na rodada seguinte e
    o agent ficaria respondendo à própria voz.
    """
    global _arecord
    proc, _arecord = _arecord, None
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        proc.kill()


def ouvir_enunciado(vad: EnergyVAD, limite_s: float = 12.0) -> np.ndarray | None:
    """Bloqueia até captar um enunciado completo (ou timeout).

    Duas saídas de segurança contra travamento (R10): se o arecord morre
    (EOF no pipe) ou fica sem produzir áudio por `FRAME_TIMEOUT_S`, o ciclo
    encerra em vez de girar para sempre.
    """
    proc = _abrir_microfone()
    assert proc.stdout is not None
    quadro_bytes = FRAME_SAMPLES * 2
    max_quadros = int(limite_s * SAMPLE_RATE / (FRAME_SAMPLES))
    lidos = 0
    while lidos < max_quadros:
        try:
            pronto, _, _ = select.select([proc.stdout], [], [], FRAME_TIMEOUT_S)
        except (OSError, ValueError) as exc:
            log.warning("microfone ilegível: %s", exc)
            _fechar_microfone()
            return None
        if not pronto:
            log.warning("arecord sem áudio por %.1fs — reiniciando captura", FRAME_TIMEOUT_S)
            _fechar_microfone()
            return None
        bruto = proc.stdout.read(quadro_bytes)
        if not bruto:
            # Pipe fechado: o arecord morreu. Sem este `break` o laço girava
            # indefinidamente com `continue` (EOF devolve b"" para sempre).
            log.warning("arecord encerrado (código %s) — recapturando", proc.poll())
            _fechar_microfone()
            return None
        if len(bruto) < quadro_bytes:
            # Frame parcial (pipe não alinhado ao frame) — mantém o resto.
            bruto = bruto + proc.stdout.read(quadro_bytes - len(bruto))
            if len(bruto) < quadro_bytes:
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
    # Timeout: um dispositivo de saída travado deixaria o aplay bloqueado para
    # sempre e o listener pararia de responder ao wake word (R10).
    try:
        subprocess.run(["aplay", "-q"], input=wav_bytes, check=False, timeout=TTS_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        log.warning("aplay expirou após %.1fs — descartando a fala", TTS_TIMEOUT_S)


def enviar_comando(comando: str) -> str | None:
    import re as _re

    use_screen = bool(_re.search(r"\b(tela|monitor|screen|ler|exercício|questão|problema|resolva|resolve|calculate|math|matemática|física|química|biologia|história|geografia|português|inglês)\b", comando, _re.UNICODE))
    try:
        resp = requests.post(
            f"{API_URL}/api/chat",
            json={
                "message": comando,
                "session_id": "voz-livre",
                "use_screen": use_screen,
            },
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
        _fechar_microfone()
        return True
    # Meio-duplex: fecha o microfone assim que o enunciado desta rodada foi
    # capturado — model/chat/TTS rodam com captura desligada.
    _fechar_microfone()
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
    falhas = 0
    while True:
        if not ciclo():
            falhas += 1
            # Microfone indisponível de forma persistente: sair deixa o
            # systemd reiniciar (Restart=always) em vez de girar em loop.
            if falhas >= 3:
                log.error("microfone indisponível em %d ciclos seguidos — saindo", falhas)
                return 1
            time.sleep(CYCLE_SLEEP_S)
            continue
        falhas = 0
        time.sleep(CYCLE_SLEEP_S)


if __name__ == "__main__":
    raise SystemExit(main())
