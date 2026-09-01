"""Gerenciamento de permissões — thread-safe com arquivo JSON.

V2: audit log, grupos de permissão, permissões temporárias, hierarquia.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path

from ..config import PERMISSIONS_PATH

AUDIT_LOG_PATH = PERMISSIONS_PATH.parent / "permission_audit.json"


class PermissionDeniedError(Exception):
    pass


DEFAULT_PERMISSIONS = {
    "microphone": True,
    "camera": False,
    "screen_capture": False,
    "file_access": True,
    "internet": True,
    "mouse_control": False,
    "keyboard_control": False,
    "command_execution": False,
}

FORCED_PERMISSIONS: dict[str, bool] = {}

# Grupos de permissão (uma ação pode exigir múltiplas)
PERMISSION_GROUPS = {
    "vision": ["screen_capture", "camera"],
    "automation": ["mouse_control", "keyboard_control", "command_execution"],
    "communication": ["microphone", "camera"],
    "full_access": list(DEFAULT_PERMISSIONS.keys()),
}

# Hierarquia: ativar X ativa automaticamente Y
PERMISSION_HIERARCHY = {
    "camera": ["screen_capture"],
    "mouse_control": ["screen_capture"],
    "keyboard_control": ["screen_capture"],
    "command_execution": ["file_access"],
}


class PermissionManager:
    def __init__(self, path: Path | str = PERMISSIONS_PATH):
        self._path = Path(path)
        self._lock = threading.Lock()
        self._permissions: dict[str, bool] = {}
        self._temporary: dict[str, float] = {}  # name → expiry timestamp
        self._audit_log: list[dict] = []
        self._load()
        self._load_audit()

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

    def _load_audit(self) -> None:
        try:
            self._audit_log = json.loads(AUDIT_LOG_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self._audit_log = []

    def _save_audit(self) -> None:
        # Mantém apenas últimos 200 registros
        self._audit_log = self._audit_log[-200:]
        AUDIT_LOG_PATH.write_text(
            json.dumps(self._audit_log, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _audit(self, action: str, name: str, value: bool | None = None, reason: str = "") -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "permission": name,
        }
        if value is not None:
            entry["value"] = value
        if reason:
            entry["reason"] = reason
        self._audit_log.append(entry)
        self._save_audit()

    def all(self) -> dict[str, bool]:
        with self._lock:
            return dict(self._permissions)

    def is_allowed(self, name: str) -> bool:
        with self._lock:
            # Verificar permissão temporária
            if name in self._temporary:
                if time.time() < self._temporary[name]:
                    return True
                else:
                    del self._temporary[name]
            return bool(self._permissions.get(name, False))

    def set(self, name: str, value: bool, reason: str = "") -> None:
        with self._lock:
            if name not in self._permissions:
                raise KeyError(f"permissão desconhecida: {name}")
            self._permissions[name] = bool(value)
            self._save()
            self._audit("set", name, value, reason)

            # Aplicar hierarquia: ativar X ativa Y
            if value and name in PERMISSION_HIERARCHY:
                for dep in PERMISSION_HIERARCHY[name]:
                    if not self._permissions.get(dep):
                        self._permissions[dep] = True
                        self._audit("hierarchy", dep, True, f"ativado por {name}")

    def set_group(self, group: str, value: bool, reason: str = "") -> None:
        """Ativa/desativa todas as permissões de um grupo."""
        perms = PERMISSION_GROUPS.get(group, [])
        for name in perms:
            if name in self._permissions:
                self.set(name, value, reason=reason)

    def grant_temporary(self, name: str, duration_seconds: float, reason: str = "") -> None:
        """Concede permissão temporária."""
        with self._lock:
            if name not in self._permissions:
                raise KeyError(f"permissão desconhecida: {name}")
            self._temporary[name] = time.time() + duration_seconds
            self._audit("temporary", name, True, f"{duration_seconds}s — {reason}")

    def require(self, name: str) -> None:
        if not self.is_allowed(name):
            raise PermissionDeniedError(
                f"Permissão '{name}' está desativada. "
                f"Ative-a nas configurações para usar este recurso."
            )

    def require_group(self, group: str) -> None:
        """Exige que todas as permissões do grupo estejam ativas."""
        perms = PERMISSION_GROUPS.get(group, [])
        denied = [p for p in perms if not self.is_allowed(p)]
        if denied:
            raise PermissionDeniedError(
                f"Permissões do grupo '{group}' insuficientes. "
                f"Faltam: {', '.join(denied)}"
            )

    def audit_log(self, limit: int = 50) -> list[dict]:
        """Retorna os últimos registros de auditoria."""
        with self._lock:
            return list(self._audit_log[-limit:])
