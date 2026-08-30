import os
from pathlib import Path
from typing import List, Optional
import logging

log = logging.getLogger("studyagent.fs")

class FSManager:
    """
    Gerencia o acesso ao sistema de arquivos com foco em segurança.
    Garante que o agente opere apenas dentro de diretórios permitidos.
    """
    
    def __init__(self):
        # Por padrão, permitimos a pasta do usuário e a pasta do projeto
        # Em produção, isso viria de uma configuração no .env ou banco de dados
        self.safe_zones: List[Path] = [
            Path(os.getenv("STUDY_PROJECT_ROOT", "/home/gma/StudyAgent")).expanduser(),
            Path(os.getenv("STUDY_USER_HOME", "/home/gma")).expanduser(),
        ]

    def is_safe(self, path: str) -> bool:
        """Verifica se o caminho está dentro de uma das zonas seguras."""
        try:
            target = Path(path).resolve()
            for zone in self.safe_zones:
                if target.is_relative_to(zone.resolve()):
                    return True
            return False
        except Exception:
            return False

    def get_safe_path(self, path: str) -> Path:
        """Retorna o caminho resolvido se for seguro, caso contrário levanta erro."""
        if not self.is_safe(path):
            log.warning(f"Tentativa de acesso a caminho inseguro: {path}")
            raise PermissionError(f"Acesso negado ao caminho: {path}. O arquivo está fora da zona segura.")
        return Path(path).resolve()

# Singleton para uso global
fs_manager = FSManager()
