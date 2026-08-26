"""RAG local: busca semântica nos documentos com embeddings do Ollama.

Índice por documento em ``data/rag/<doc_id>.npz`` (vetores + metadados),
construído na primeira consulta. Sem dependências novas: numpy +
requisição HTTP para /api/embeddings. Qualquer falha devolve None e o
agente cai no recuperador léxico.
"""

import json
import logging
import threading

import numpy as np
import requests

from ..config import DATA_DIR, OLLAMA_HOST
from ..core.model_manager import model as role_model

INDEX_DIR = DATA_DIR / "rag"
CHUNK_CHARS = 800
CHUNK_OVERLAP = 120
TOP_K = 4
MAX_CONTEXT_CHARS = 8000
EMBED_TIMEOUT = 60

_lock = threading.Lock()
_cache: dict[str, tuple[np.ndarray, list[dict]]] = {}
_cache_lock = threading.Lock()


def chunk_document(text: str) -> list[dict]:
    """Divide por páginas e parágrafos, com sobreposição entre pedaços."""
    chunks: list[dict] = []
    pagina_atual = None
    buffer: list[str] = []
    tamanho = 0

    def flush():
        nonlocal buffer, tamanho
        conteudo = " ".join(buffer).strip()
        if len(conteudo) >= 40:
            chunks.append({"page": pagina_atual, "text": conteudo})
        buffer = []
        tamanho = 0

    for linha in text.splitlines():
        marcador = linha.strip()
        if marcador.startswith("[página") and marcador.endswith("]"):
            flush()
            try:
                pagina_atual = int(marcador.removeprefix("[página").removesuffix("]").strip())
            except ValueError:
                pass
            continue
        buffer.append(linha)
        tamanho += len(linha) + 1
        if tamanho >= CHUNK_CHARS:
            # sobrepõe mantendo a cauda do pedaço atual
            cauda = " ".join(buffer)[-CHUNK_OVERLAP:]
            flush()
            buffer = [cauda] if cauda.strip() else []
            tamanho = len(cauda) + 1 if cauda else 0
    flush()
    return chunks


def embed_texts(texts: list[str], embed_fn=None) -> np.ndarray:
    """Matriz normalizada n×d dos embeddings (em lote quando possível)."""
    if embed_fn is None:
        mat = np.array(_embed_ollama_batch(texts), dtype=np.float32)
    else:
        mat = np.array([embed_fn(t) for t in texts], dtype=np.float32)
    if mat.ndim != 2 or mat.shape[0] == 0:
        raise ValueError("embeddings vazios")
    normas = np.linalg.norm(mat, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    return mat / normas


def _embed_ollama(text: str) -> list[float]:
    return _embed_ollama_batch([text])[0]


def _embed_ollama_batch(texts: list[str]) -> list[list[float]]:
    resp = requests.post(
        f"{OLLAMA_HOST}/api/embed",
        json={
            "model": role_model("embedding"),
            "input": [t[:4000] for t in texts],
        },
        timeout=EMBED_TIMEOUT * max(1, len(texts) // 16),
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


def _index_path(doc_id: str):
    return INDEX_DIR / f"{doc_id}.npz"


def has_index(doc_id: str) -> bool:
    return _index_path(doc_id).exists()


def build_index(doc_id: str, doc_text: str, embed_fn=None, force=False) -> bool:
    """Constrói e persiste o índice do documento. True se construído agora."""
    if not force and has_index(doc_id):
        return False
    chunks = chunk_document(doc_text)
    if not chunks:
        return False
    vectors = embed_texts([c["text"] for c in chunks], embed_fn)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        _index_path(doc_id),
        vectors=vectors,
        chunks=np.array(json.dumps(chunks, ensure_ascii=False)),
    )
    return True


def load_index(doc_id: str):
    with _cache_lock:
        if doc_id in _cache:
            return _cache[doc_id]
    path = _index_path(doc_id)
    if not path.exists():
        return None
    dados = np.load(path, allow_pickle=False)
    vectors = dados["vectors"].astype(np.float32)
    chunks = json.loads(str(dados["chunks"]))
    with _cache_lock:
        if len(_cache) > 6:
            _cache.pop(next(iter(_cache)))
        _cache[doc_id] = (vectors, chunks)
    return vectors, chunks


def search(doc_id: str, doc_text: str, query: str, embed_fn=None, k: int = TOP_K):
    """Top-k trechos semânticos formatados, ou None se indisponível."""
    try:
        indice = load_index(doc_id)
        if indice is None:
            build_index(doc_id, doc_text, embed_fn)
            indice = load_index(doc_id)
        if indice is None:
            return None
        vectors, chunks = indice
        qvec = embed_texts([query], embed_fn)[0]
        scores = vectors @ qvec
        ordem = np.argsort(scores)[::-1][: max(1, min(k, len(chunks)))]
        logging.getLogger("uvicorn.error").info(
            "RAG %s: top=%s", doc_id,
            [chunks[int(i)].get("page") for i in ordem[:3]],
        )
        partes = []
        total = 0
        for i in ordem:
            c = chunks[int(i)]
            trecho = f"[página {c['page']}]\n{c['text']}" if c["page"] else c["text"]
            if total + len(trecho) > MAX_CONTEXT_CHARS:
                break
            partes.append(trecho)
            total += len(trecho)
        return "\n\n[…]\n\n".join(partes) or None
    except Exception as exc:
        logging.getLogger("uvicorn.error").warning(
            "RAG indisponível para %s: %s", doc_id, exc
        )
        return None
