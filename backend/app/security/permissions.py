import json
import threading

from ..config import PERMISSIONS_PATH


class PermissionDeniedError(Exception):
    pass


class PermissionManager:
    def __init__(self, path=PERMISSIONS_PATH):
        self._path = path
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            self._permissions = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self._permissions = {}

    def _save(self):
        self._path.write_text(
            json.dumps(self._permissions, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def all(self):
        with self._lock:
            return dict(self._permissions)

    def is_allowed(self, name):
        return bool(self._permissions.get(name, False))

    def set(self, name, value):
        with self._lock:
            if name not in self._permissions:
                raise KeyError(f"permissão desconhecida: {name}")
            self._permissions[name] = bool(value)
            self._save()

    def require(self, name):
        if not self.is_allowed(name):
            raise PermissionDeniedError(
                f"Permissão '{name}' está desativada. "
                f"Ative-a nas configurações para usar este recurso."
            )
