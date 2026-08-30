import chromadb
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from .vector_store import VectorStore
from ..config import DATA_DIR

class ChromaStore(VectorStore):
    """Implementação moderna usando ChromaDB."""
    
    def __init__(self):
        # Persistência local no diretório de dados
        self.client = chromadb.PersistentClient(path=str(DATA_DIR / "chroma_db"))
        
    def _get_collection(self, doc_id: str):
        # Usamos uma coleção por documento para manter a simplicidade da migração
        # ou poderíamos usar uma única coleção com metadados.
        # Para compatibilidade com a lógica atual, usaremos coleções nomeadas.
        return self.client.get_or_create_collection(name=f"doc_{doc_id}")

    def exists(self, doc_id: str) -> bool:
        try:
            self.client.get_collection(name=f"doc_{doc_id}")
            return True
        except:
            return False

    def add_documents(self, doc_id: str, vectors: np.ndarray, chunks: List[Dict[str, Any]]) -> None:
        collection = self._get_collection(doc_id)
        
        # ChromaDB espera IDs como strings
        ids = [f"chunk_{i}" for i in range(len(chunks))]
        metadatas = chunks
        documents = [c["text"] for c in chunks]
        
        collection.add(
            embeddings=vectors.tolist(),
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def search(self, doc_id: str, query_vec: np.ndarray, k: int = 4) -> Optional[Tuple[np.ndarray, List[Dict[str, Any]]]]:
        try:
            collection = self._get_collection(doc_id)
            results = collection.query(
                query_embeddings=[query_vec.tolist()],
                n_results=k
            )
            
            if not results["ids"][0]:
                return None
                
            # Chroma retorna distâncias (L2 por padrão), convertemos para scores aproximados
            # ou apenas retornamos a ordem.
            scores = np.array(results["distances"][0], dtype=np.float32)
            chunks = results["metadatas"][0]
            
            return scores, chunks
        except Exception:
            return None

    def delete(self, doc_id: str) -> None:
        try:
            self.client.delete_collection(name=f"doc_{doc_id}")
        except:
            pass
