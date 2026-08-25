from app.audio.wake_word import extract_command, normalize


def test_normaliza_acentos_e_espacos():
    assert normalize("  Ei   STÚDY! ") == "ei study!"


def test_comando_apos_gatilho():
    assert extract_command("Ei Study, quanto é 2+2?") == "quanto é 2+2?"


def test_gatilho_sozinho_nao_envia_comando():
    assert extract_command("study") is None
    assert extract_command("ei study") is None


def test_frase_sem_gatilho():
    assert extract_command("bom dia, tudo bem?") is None
    assert extract_command("") is None
    assert extract_command("quanto é dois mais dois") is None


def test_variantes_do_gatilho():
    assert extract_command("ok study, resuma o capítulo").startswith("resuma")
    assert extract_command("hey study, o que é fotossíntese?").startswith("o que")


def test_studi_reconhecido(stt_variacao="studi"):
    # STT às vezes escreve variações fonéticas
    assert extract_command(f"ei {stt_variacao}, ajude-me com frações") is not None


def test_texto_antes_do_gatilho_ignorado():
    # "study" no meio da frase não acorda — só no início/comando direto
    assert extract_command("eu gosto de estudar study hall") is None
