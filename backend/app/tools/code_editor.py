import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..core.fs_manager import fs_manager

log = logging.getLogger("studyagent.code_editor")

def read_file(path: str) -> str:
    """Lê o conteúdo de um arquivo de código."""
    try:
        safe_path = fs_manager.get_safe_path(path)
        return safe_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        log.error(f"Erro ao ler arquivo {path}: {e}")
        return f"Erro ao ler arquivo: {str(e)}"

def write_file(path: str, content: str) -> str:
    """Cria ou sobrescreve um arquivo com o conteúdo fornecido."""
    try:
        safe_path = fs_manager.get_safe_path(path)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content, encoding="utf-8")
        return f"Arquivo {path} escrito com sucesso."
    except Exception as e:
        log.error(f"Erro ao escrever arquivo {path}: {e}")
        return f"Erro ao escrever arquivo: {str(e)}"

def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Substitui uma string específica por outra em um arquivo (edição cirúrgica)."""
    try:
        safe_path = fs_manager.get_safe_path(path)
        content = safe_path.read_text(encoding="utf-8")
        if old_string not in content:
            return f"Erro: A string de busca não foi encontrada no arquivo {path}."
        
        new_content = content.replace(old_string, new_string)
        safe_path.write_text(new_content, encoding="utf-8")
        return f"Arquivo {path} editado com sucesso."
    except Exception as e:
        log.error(f"Erro ao editar arquivo {path}: {e}")
        return f"Erro ao editar arquivo: {str(e)}"

def list_directory(path: str) -> List[str]:
    """Lista arquivos e pastas em um diretório."""
    try:
        safe_path = fs_manager.get_safe_path(path)
        return [str(p.relative_to(safe_path.parent)) for p in safe_path.iterdir()]
    except Exception as e:
        log.error(f"Erro ao listar diretório {path}: {e}")
        return [f"Erro ao listar: {str(e)}"]

def search_in_files(query: str, root_path: str) -> List[Dict[str, Any]]:
    """Busca por uma string em todos os arquivos de um diretório recursivamente."""
    results = []
    try:
        safe_root = fs_manager.get_safe_path(root_path)
        for path in safe_root.rglob("*"):
            if path.is_file():
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    if query in content:
                        results.append({
                            "path": str(path.relative_to(safe_root)),
                            "line": "Encontrado" # Simplificado
                        })
                except:
                    continue
        return results
    except Exception as e:
        log.error(f"Erro na busca: {e}")
        return []
