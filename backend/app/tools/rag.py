"""RAG local: busca semântica nos documentos com embeddings do Ollama.

V2: embedding cache, reranking, metadata por chunk, filtros de busca.
"""

import hashlib
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

# ── Embedding cache ──────────────────────────────────────────────

_embedding_cache: dict[str, list[float]] = {}
_embedding_cache_lock = threading.Lock()
MAX_EMBED_CACHE = 500


def _text_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _get_cached_embedding(text: str) -> list[float] | None:
    h = _text_hash(text)
    with _embedding_cache_lock:
        return _embedding_cache.get(h)


def _set_cached_embedding(text: str, embedding: list[float]) -> None:
    h = _text_hash(text)
    with _embedding_cache_lock:
        if len(_embedding_cache) >= MAX_EMBED_CACHE:
            _embedding_cache.pop(next(iter(_embedding_cache)))
        _embedding_cache[h] = embedding


def chunk_document(text: str) -> list[dict]:
    """Divide por páginas e parágrafos, com sobreposição e metadata."""
    chunks: list[dict] = []
    pagina_atual = None
    buffer: list[str] = []
    tamanho = 0

    def flush():
        nonlocal buffer, tamanho
        conteudo = " ".join(buffer).strip()
        if len(conteudo) >= 40:
            chunk = {"page": pagina_atual, "text": conteudo}
            # Detectar headings para metadata
            first_line = buffer[0].strip() if buffer else ""
            if first_line.startswith("#") or (first_line.isupper() and len(first_line) < 80):
                chunk["heading"] = first_line.lstrip("#").strip()
            chunks.append(chunk)
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
            cauda = " ".join(buffer)[-CHUNK_OVERLAP:]
            flush()
            buffer = [cauda] if cauda.strip() else []
            tamanho = len(cauda) + 1 if cauda else 0
    flush()
    return chunks


def embed_texts(texts: list[str], embed_fn=None) -> np.ndarray:
    """Matriz normalizada n×d dos embeddings (com cache)."""
    if embed_fn is None:
        # Tentar cache individual
        cached = []
        to_embed = []
        indices = []
        for i, t in enumerate(texts):
            c = _get_cached_embedding(t)
            if c is not None:
                cached.append((i, c))
            else:
                to_embed.append(t)
                indices.append(i)

        if to_embed:
            new_embeddings = _embed_ollama_batch(to_embed)
            for idx, emb in zip(indices, new_embeddings, strict=True):
                _set_cached_embedding(texts[idx], emb)
                cached.append((idx, emb))

        # Reconstruir na ordem original
        emb_map = {i: e for i, e in cached}
        mat = np.array([emb_map[i] for i in range(len(texts))], dtype=np.float32)
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


def _rerank(query: str, results: list[dict], top_k: int = TOP_K) -> list[dict]:
    """Reranking simples: bônus para chunks com heading que combina com query."""
    query_lower = query.lower()
    for r in results:
        bonus = 0.0
        heading = r.get("heading", "").lower()
        if heading and any(w in heading for w in query_lower.split()):
            bonus = 0.15
        r["_score"] = r.get("_score", 0) + bonus
    results.sort(key=lambda x: x.get("_score", 0), reverse=True)
    return results[:top_k]


def search(
    doc_id: str,
    doc_text: str,
    query: str,
    embed_fn=None,
    k: int = TOP_K,
    page_range: tuple[int, int] | None = None,
) -> str | None:
    """Top-k trechos semânticos formatados, ou None se indisponível.

    Args:
        page_range: Filtrar por intervalo de páginas (inclusive).
    """
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
        ordem = np.argsort(scores)[::-1]

        # Coletar mais candidatos para reranking
        candidates = []
        for i in ordem[: k * 3]:
            c = dict(chunks[int(i)])
            c["_score"] = float(scores[i])
            c["_idx"] = int(i)
            # Filtrar por página
            if page_range and c.get("page") is not None:
                if not (page_range[0] <= c["page"] <= page_range[1]):
                    continue
            candidates.append(c)

        # Reranking
        reranked = _rerank(query, candidates, top_k=k)

        logging.getLogger("uvicorn.error").info(
            "RAG %s: top=%s", doc_id,
            [c.get("page") for c in reranked[:3]],
        )
        partes = []
        total = 0
        for c in reranked:
            trecho = f"[página {c['page']}] {c.get('heading', '')}\n{c['text']}" if c.get("page") else c["text"]
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
