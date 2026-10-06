"""Testes das proteções de travamento do listener viva-voz (R10).

Sem microfone: os helpers que dependem de arecord/aplay são substituídos por
fakes — o alvo é o laço de leitura (EOF, frame parcial, silenceamento) e não o
áudio real.
"""

import os
import subprocess
import time

import numpy as np
import pytest

from app.audio import listener
from app.audio.vad import EnergyVAD


class _Proc:
    """Dublê de subprocess.Popen: stdout controlled, poll() e terminate()."""

    def __init__(self, stdout, returncode=None):
        self.stdout = stdout
        self._returncode = returncode

    def poll(self):
        return self._returncode

    def terminate(self):
        self._returncode = -15

    def wait(self, timeout=None):
        return self._returncode

    def kill(self):
        self._returncode = -9


class _Chunked:
    """Leitor que entrega no máximo `limite` bytes por read().

    Reproduz o pipe delivering um frame pela metade (o arecord escreve o PCM
    conforme o kernel entrega, não alinhado ao frame do VAD). Mantém
    `fileno()` real para o `select` do listener.
    """

    def __init__(self, arquivo, limite: int):
        self._arquivo = arquivo
        self._limite = limite

    def fileno(self):
        return self._arquivo.fileno()

    def read(self, n=-1):
        return self._arquivo.read(min(n, self._limite) if n and n > 0 else n)


def _pipe(payload: bytes = b"", keep_open: bool = False, chunk: int | None = None) -> _Proc:
    """Processo com stdout num pipe real — `select` exige um fd de verdade."""
    r, w = os.pipe()
    if payload:
        os.write(w, payload)
    if not keep_open:
        os.close(w)  # EOF: simula arecord que morreu
    arquivo = os.fdopen(r, "rb", buffering=0)
    return _Proc(_Chunked(arquivo, chunk) if chunk else arquivo)


@pytest.fixture(autouse=True)
def _sem_ciclo_de_sono(monkeypatch):
    """Ciclo não deve dormir entre iterações nos testes."""
    monkeypatch.setattr(listener, "CYCLE_SLEEP_S", 0.0)


class TestOuvirEnunciado:
    def test_eof_do_arecord_nao_gira_em_loop(self, monkeypatch):
        """Pipe fechado (arecord morto) precisa encerrar, não ficar em busy-loop."""
        proc = _pipe(b"", keep_open=False)
        proc._returncode = 1
        monkeypatch.setattr(listener, "_abrir_microfone", lambda: proc)
        monkeypatch.setattr(listener, "_fechar_microfone", lambda: None)

        inicio = time.monotonic()
        resultado = listener.ouvir_enunciado(EnergyVAD(threshold_rms=500), limite_s=12.0)

        assert resultado is None
        assert time.monotonic() - inicio < 2.0, "deveria encerrar imediatamente no EOF"

    def test_timeout_de_leitura_recupera_captura(self, monkeypatch):
        """Sem áudio por mais de FRAME_TIMEOUT_S encerra o ciclo (não trava)."""
        proc = _pipe(b"", keep_open=True)  # pipe aberto e silencioso
        monkeypatch.setattr(listener, "_abrir_microfone", lambda: proc)
        monkeypatch.setattr(listener, "FRAME_TIMEOUT_S", 0.05)
        monkeypatch.setattr(listener, "_fechar_microfone", lambda: None)

        inicio = time.monotonic()
        assert listener.ouvir_enunciado(EnergyVAD(threshold_rms=500)) is None
        assert time.monotonic() - inicio < 2.0

    def test_frame_parcial_e_reagrupado(self, monkeypatch):
        """Frame partido em duas leituras ainda alimenta o VAD (sem perder áudio)."""
        do_vad = EnergyVAD(threshold_rms=1)
        loud = np.full(listener.FRAME_SAMPLES, 8000, dtype="<i2")
        silencio = np.zeros(listener.FRAME_SAMPLES, dtype="<i2")
        # 2 quadros de fala + ~1 s de silêncio (encerra o utterance no VAD)
        quadros = [loud, loud] + [silencio] * 32
        payload = np.concatenate(quadros).tobytes()

        # entregas de 700 bytes forçam frames partidos (frame = 960 bytes)
        proc = _pipe(payload, chunk=700)
        monkeypatch.setattr(listener, "_abrir_microfone", lambda: proc)
        monkeypatch.setattr(listener, "_fechar_microfone", lambda: None)

        resultado = listener.ouvir_enunciado(do_vad, limite_s=12.0)

        assert resultado is not None, "frames partidos não podem perder o utterance"
        assert len(resultado) >= listener.FRAME_SAMPLES * 2
        assert float(np.abs(resultado).max()) > 0, "frames de fala foram descartados"

    def test_fechar_microfone_marca_processo_terminado(self, monkeypatch):
        proc = _pipe(b"", keep_open=True)
        monkeypatch.setattr(listener, "_arecord", proc)
        listener._fechar_microfone()
        assert listener._arecord is None
        assert proc.poll() is not None


class TestFalar:
    def test_aplay_com_timeout_nao_levanta(self, monkeypatch):
        def _lento(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="aplay", timeout=1)

        monkeypatch.setattr(subprocess, "run", _lento)
        listener.falar(b"RIFF-fake")  # não deve propagar a exceção

    def test_aplay_recebe_o_wav(self, monkeypatch):
        chamadas = {}

        def _ok(cmd, input=None, **kwargs):
            chamadas["cmd"] = cmd
            chamadas["input"] = input
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", _ok)
        listener.falar(b"RIFF-fake")
        assert chamadas["cmd"] == ["aplay", "-q"]
        assert chamadas["input"] == b"RIFF-fake"


class TestMain:
    def test_sai_apos_tres_falhas_de_microfone(self, monkeypatch):
        monkeypatch.setattr(listener, "ciclo", lambda *a, **k: False)
        assert listener.main() == 1

    def test_nao_sai_quando_o_ciclo_passa(self, monkeypatch):
        """Um ciclo OK followed de falha não deve encerrar o serviço."""
        respostas = iter([True, False, True, False, True, False])

        def _ciclo(*args, **kwargs):
            try:
                return next(respostas)
            except StopIteration:
                raise KeyboardInterrupt from None

        monkeypatch.setattr(listener, "ciclo", _ciclo)
        monkeypatch.setattr(listener.time, "sleep", lambda *_a, **_k: None)
        with pytest.raises(KeyboardInterrupt):
            listener.main()
