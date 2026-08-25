import numpy as np
import pytest
import zlib

from app.tools import rag


def fake_embed_factory(dim=64, calls=None):
    """Embedding determinístico estável entre processos (hash() varia)."""

    def embed(texto: str) -> list[float]:
        if calls is not None:
            calls.append(texto)
        vec = np.zeros(dim, dtype=np.float32)
        for palavra in texto.lower().split():
            vec[zlib.crc32(palavra.encode()) % dim] += 1.0
        return vec.tolist()

    return embed


@pytest.fixture()
def rag_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(rag, "INDEX_DIR", tmp_path / "rag")
    monkeypatch.setattr(rag, "_cache", {})
    return tmp_path


DOC = (
    "[página 1]\n" + "Receita de bolo: farinha, ovos e açúcar. " * 20 + "\n\n"
    "[página 2]\n" + "A fórmula de Bhaskara resolve equações do segundo grau. " * 20 + "\n\n"
    "[página 3]\n" + "A Revolução Francesa começou em 1789 na França. " * 20 + "\n\n"
    "[página 7]\n" + "O capítulo sete mede exatamente 777 metros de extensão. " * 20
)


def test_chunking_respeita_paginas(rag_tmp):
    chunks = rag.chunk_document(DOC)
    paginas = [c["page"] for c in chunks]
    assert 7 in paginas and 2 in paginas
    assert all(len(c["text"]) >= 40 for c in chunks)


def test_busca_semantica_acha_pagina_certa(rag_tmp):
    calls = []
    fn = fake_embed_factory(calls=calls)
    trechos = rag.search("docX", DOC, "qual o valor do capítulo sete?", embed_fn=fn)
    assert trechos is not None
    assert "777 metros" in trechos
    assert "Bhaskara" not in trechos.split("[…]")[0]
    # índice foi construído uma vez e persistido em disco
    assert (rag_tmp / "rag" / "docX.npz").exists()


def test_indice_reutilizado_do_disco(rag_tmp):
    calls = []
    fn = fake_embed_factory(calls=calls)
    rag.build_index("docY", DOC, embed_fn=fn)
    n_apos_build = len(calls)
    trechos = rag.search("docY", DOC, "revolução francesa 1789", embed_fn=fn)
    assert "1789" in trechos
    # só o embedding da QUERY depois (índice não reconstruído)
    assert len(calls) == n_apos_build + 1


def test_embedding_com_falha_retorna_none(rag_tmp):
    def quebra(texto):
        raise RuntimeError("ollama fora do ar")

    assert rag.search("docZ", DOC, "pergunta", embed_fn=quebra) is None


def test_documento_vazio_nao_indexa(rag_tmp):
    calls = []
    assert rag.build_index("vazio", "", embed_fn=fake_embed_factory(calls=calls)) is False
    assert calls == []


def test_split_narracao_paginas():
    from app.tools.documents import split_narration

    texto = "[página 1]\nPrimeira página com conteúdo.\n\n[página 2]\nSegunda página aqui."
    partes = split_narration(texto)
    assert len(partes) == 2
    assert partes[0].startswith("Primeira")
    assert "[página" not in partes[0]
    assert "[página" not in partes[1]


def test_split_narracao_texto_longo_em_partes():
    from app.tools.documents import NARRATION_MAX_CHARS, split_narration

    texto = ("Esta é uma frase completa de teste. " * 120).strip()
    partes = split_narration(texto)
    assert len(partes) > 1
    assert all(len(p) <= NARRATION_MAX_CHARS + 50 for p in partes)
