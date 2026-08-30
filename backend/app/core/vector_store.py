from abc import ABC, abstractmethod
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

class VectorStore(ABC):
    """Interface abstrata para armazenamento de vetores."""
    
    @abstractmethod
    def add_documents(self, doc_id: str, vectors: np.ndarray, chunks: List[Dict[str, Any]]) -> None:
        """Adiciona vetores e chunks a um documento."""
        pass

    @abstractmethod
    def search(self, doc_id: str, query_vec: np.ndarray, k: int = 4) -> Optional[Tuple[np.ndarray, List[Dict[str, Any]]]]:
        """Busca os k trechos mais similares."""
        pass

    @abstractmethod
    def exists(self, doc_id: str) -> bool:
        """Verifica se o documento existe no índice."""
        pass

    @abstractmethod
    def delete(self, doc_id: str) -> None:
        """Remove um documento do índice."""
        pass
