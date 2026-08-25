from app.agent.exercises import _normalize


def test_igualdade_exata():
    assert _normalize("1/2") == _normalize("1/2")


def test_espacos_e_pontuacao():
    assert _normalize("  3/4 . ") == _normalize("3/4")


def test_acentos_removidos():
    assert _normalize("não") == _normalize("nao")


def test_virgula_decimal():
    assert _normalize("0,5") == _normalize("0.5")


def test_prefixo_de_alternativa():
    assert _normalize("b) 42") == _normalize("42")


def test_maiusculas():
    assert _normalize("RESPOSTA") == _normalize("resposta")
