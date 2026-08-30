import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

from ..config import DATA_DIR
from .vector_store import VectorStore
from .numpy_store import NumPyStore
from .chroma_store import ChromaStore

class CognitiveMemory:
    """
    Sistema de Memória Episódica para o StudyAgent.
    Armazena fatos, preferências e dificuldades do aluno para personalização a longo prazo.
    """
    
    def __init__(self, engine: str = "chroma"):
        self.store: VectorStore = ChromaStore() if engine == "chroma" else NumPyStore()
        self.memory_id = "user_cognitive_memory"
        self.logger = logging.getLogger("cognitive_memory")

    def remember(self, fact: str, metadata: Dict[str, Any] = None) -> None:
        """
        Salva um fato sobre o usuário. 
        Ex: 'O aluno prefere exemplos de física usando esportes.'
        """
        try:
            # Para a memória cognitiva, usamos a mesma lógica de embedding do RAG
            # mas em uma coleção separada.
            from ..tools.rag import embed_texts
            
            vec = embed_texts([fact])[0]
            chunks = [{"text": fact, **(metadata or {})}]
            
            self.store.add_documents(self.memory_id, vec.reshape(1, -1), chunks)
            self.logger.info(f"Memória gravada: {fact}")
        except Exception as e:
            self.logger.error(f"Erro ao gravar memória: {e}")

    def recall(self, query: str, k: int = 3) -> List[str]:
        """
        Recupera fatos relevantes com base na conversa atual.
        """
        try:
            from ..tools.rag import embed_texts
            
            qvec = embed_texts([query])[0]
            res = self.store.search(self.memory_id, qvec, k=k)
            
            if res is None:
                return []
                
            _, chunks = res
            return [c["text"] for c in chunks]
        except Exception as e:
            self.logger.error(f"Erro ao recuperar memória: {e}")
            return []

    def forget(self):
        """Limpa a memória cognitiva do usuário."""
        self.store.delete(self.memory_id)
