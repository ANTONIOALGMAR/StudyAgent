from app.tools.documents import _split_slices, retrieve_relevant


def test_split_slices_respeita_paginas():
    texto = "".join(f"\n\n[página {i}]\nconteúdo da página {i} " + "x" * 50 for i in range(1, 8))
    fatias = _split_slices(texto, size=300)
    assert len(fatias) > 1
    # cada fatia começa com marcador de página (exceto talvez a primeira)
    for f in fatias[1:]:
        assert f.startswith("[página")


def test_texto_pequeno_uma_fatia():
    fatias = _split_slices("texto curto", size=9000)
    assert len(fatias) == 1


def test_recuperacao_ranqueia_por_palavras():
    enchimento = "conteúdo diverso e aleatório para ocupar espaço " * 4
    doc = (
        f"[página 1]\nA fotossíntese é o processo pelo qual plantas produzem energia. {enchimento}\n\n"
        f"[página 2]\nA equação de segundo grau tem a fórmula de Bhaskara. {enchimento}\n\n"
        f"[página 3]\nRevolução Francesa ocorreu em 1789 na França. {enchimento}"
    )
    trecho = retrieve_relevant("qual é a fórmula de Bhaskara?", doc, max_chars=200)
    primeira_parte = trecho.split("[…]")[0]
    assert "Bhaskara" in trecho
    assert "1789" not in primeira_parte


def test_documento_pequeno_retorna_tudo():
    doc = "conteúdo pequeno"
    assert retrieve_relevant("pergunta", doc, max_chars=100) == doc
