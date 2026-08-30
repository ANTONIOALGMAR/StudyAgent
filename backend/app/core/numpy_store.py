import numpy as np
import json
from typing import List, Dict, Any, Optional, Tuple
from .vector_store import VectorStore
from ..config import DATA_DIR

class NumPyStore(VectorStore):
    """Implementação original baseada em arquivos .npz."""
    
    def __init__(self):
        self.index_dir = DATA_DIR / "rag"
        self.index_dir.mkdir(parents=True, exist_ok=True)

    def _index_path(self, doc_id: str):
        return self.index_dir / f"{doc_id}.npz"

    def exists(self, doc_id: str) -> bool:
        return self._index_path(doc_id).exists()

    def add_documents(self, doc_id: str, vectors: np.ndarray, chunks: List[Dict[str, Any]]) -> None:
        np.savez_compressed(
            self._index_path(doc_id),
            vectors=vectors,
            chunks=np.array(json.dumps(chunks, ensure_ascii=False)),
        )

    def search(self, doc_id: str, query_vec: np.ndarray, k: int = 4) -> Optional[Tuple[np.ndarray, List[Dict[str, Any]]]]:
        path = self._index_path(doc_id)
        if not path.exists():
            return None
        
        dados = np.load(path, allow_pickle=False)
        vectors = dados["vectors"].astype(np.float32)
        chunks = json.loads(str(dados["chunks"]))
        
        scores = vectors @ query_vec
        ordem = np.argsort(scores)[::-1]
        
        top_indices = ordem[:k]
        top_vectors = vectors[top_indices]
        top_chunks = [chunks[int(i)] for i in top_indices]
        top_scores = scores[top_indices]
        
        return top_scores, top_chunks

    def delete(self, doc_id: str) -> None:
        path = self._index_path(doc_id)
        if path.exists():
            path.unlink()
