import numpy as np

from app.audio.vad import FRAME_SAMPLES, EnergyVAD, pcm_to_wav_bytes, trim_silence_tail


def quadro(rms_amplitude: float, seed=0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(FRAME_SAMPLES) * rms_amplitude).astype("<i2")


def test_silencio_nao_gera_enunciado():
    vad = EnergyVAD(threshold_rms=500)
    for i in range(60):
        assert vad.feed(quadro(10, seed=i)) is None
    assert not vad.active


def test_fala_seguida_de_pausa_emite_enunciado():
    vad = EnergyVAD(threshold_rms=500)
    for i in range(20):  # ~0,6 s de fala alta
        assert vad.feed(quadro(3000, seed=i)) is None
    assert vad.active
    emitido = None
    for i in range(40):  # ~1,2 s de silêncio → fecha
        saida = vad.feed(quadro(10, seed=100 + i))
        if saida is not None:
            emitido = saida
            break
    assert emitido is not None
    assert len(emitido) > FRAME_SAMPLES * 5


def test_pre_roll_preserva_inicio_da_fala():
    vad = EnergyVAD()
    for _ in range(10):
        vad.feed(quadro(5))
    emitido = None
    for i in range(15):
        assert vad.feed(quadro(4000, seed=i)) is None
    for i in range(40):
        saida = vad.feed(quadro(5, seed=50 + i))
        if saida is not None:
            emitido = saida
            break
    assert emitido is not None
    # janela deslizante de 5 inclui o quadro-gatilho: 4 prévios + 15 falados;
    # garantia mínima: nenhum quadro de fala se perde
    assert len(emitido) >= 15 * FRAME_SAMPLES
    cauda = emitido[-3 * FRAME_SAMPLES:].astype(np.float32)
    assert float(np.sqrt(np.mean(cauda**2))) > 1000


def test_trim_remove_cauda_silenciosa():
    pcm = np.concatenate([quadro(3000, seed=1)] * 10 + [quadro(5, seed=2)] * 8)
    cortado = trim_silence_tail(pcm)
    assert len(cortado) < len(pcm)
    assert len(cortado) >= FRAME_SAMPLES * 9


def test_wav_tem_cabecalho_valido():
    pcm = np.concatenate([quadro(2000, seed=3)] * 5)
    wav = pcm_to_wav_bytes(pcm)
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    # 44 bytes de cabeçalho + dados int16 mono
    assert len(wav) == 44 + len(pcm) * 2
