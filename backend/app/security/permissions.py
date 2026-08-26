"""Gerenciamento de permissões — thread-safe com arquivo JSON.

Permissões padrão: todas as ações perigosas desabilitadas.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ..config import PERMISSIONS_PATH


class PermissionDeniedError(Exception):
    pass


DEFAULT_PERMISSIONS = {
    "microphone": False,
    "camera": False,
    "screen_capture": True,
    "file_access": True,
    "internet": True,
    "mouse_control": False,
    "keyboard_control": False,
    "command_execution": False,
}


class PermissionManager:
    def __init__(self, path: Path | str = PERMISSIONS_PATH):
        self._path = Path(path)
        self._lock = threading.Lock()
        self._permissions: dict[str, bool] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        merged = dict(DEFAULT_PERMISSIONS)
        merged.update({k: bool(v) for k, v in data.items()})
        self._permissions = merged

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(self._permissions, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def all(self) -> dict[str, bool]:
        with self._lock:
            return dict(self._permissions)

    def is_allowed(self, name: str) -> bool:
        with self._lock:
            return bool(self._permissions.get(name, False))

    def set(self, name: str, value: bool) -> None:
        with self._lock:
            if name not in self._permissions:
                raise KeyError(f"permissão desconhecida: {name}")
            self._permissions[name] = bool(value)
            self._save()

    def require(self, name: str) -> None:
        if not self.is_allowed(name):
            raise PermissionDeniedError(
                f"Permissão '{name}' está desativada. "
                f"Ative-a nas configurações para usar este recurso."
            )
