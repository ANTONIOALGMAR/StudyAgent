"""Reconhecimento facial do usuário via embedding facial real (InsightFace).

Abordagem: o modelo de reconhecimento (buffalo_l, ONNX/onnxruntime) extrai um
vetor de face de 512 dims L2-normalizado. O matcher compara por similaridade de
cosseno entre o embedding da imagem e os perfis cadastrados.

O chamador pode injetar ``embed`` (callable bytes -> np.ndarray|None) para
teste sem modelos/rede.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from ..config import DATA_DIR

log = logging.getLogger("studyagent.facial")

FACES_PATH = DATA_DIR / "faces.json"
EMBED_DIM = 512

# limiar de similaridade de cosseno p/ considerar mesmo usuário (InsightFace)
DEFAULT_THRESHOLD = 0.42
# limiar de detecção ("present" com confiança mínima)
DEFAULT_PRESENT_THRESHOLD = 0.5

_singleton_app = None
_singleton_lock = threading.Lock()


def _get_insightface_app():
    """Singleton do FaceAnalysis do InsightFace (lazy; baixa buffalo_l na 1ª vez)."""
    global _singleton_app
    if _singleton_app is None:
        with _singleton_lock:
            if _singleton_app is None:
                from insightface.app import FaceAnalysis  # import pesado/lazy

                app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
                app.prepare(ctx_id=0, det_size=(640, 640))
                _singleton_app = app
    return _singleton_app


def _default_embed(image_bytes: bytes) -> np.ndarray | None:
    """Extrai o embedding L2-normalizado do(s) rosto(s) da imagem, se houver face nítida."""
    from PIL import Image

    import io

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        log.warning("[FACIAL] imagem inválida: %s", exc)
        return None
    app = _get_insightface_app()
    try:
        faces = app.get(np.asarray(img))
    except Exception as exc:
        log.warning("[FACIAL] falha na deteccao: %s", exc)
        return None
    if not faces:
        return None
    best = max(faces, key=lambda f: float(getattr(f, "det_score", 0) or 0))
    det = float(getattr(best, "det_score", 0) or 0)
    if det < DEFAULT_PRESENT_THRESHOLD:
        return None
    emb = np.asarray(getattr(best, "normed_embedding", None))
    if emb is None or emb.size == 0:
        return None
    emb = emb.astype(np.float32).reshape(-1)
    norm = float(np.linalg.norm(emb))
    if norm > 0:
        emb = emb / norm
    return emb


@dataclass
class FaceProfile:
    name: str
    embedding: list[float]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "embedding": self.embedding,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FaceProfile":
        emb = data.get("embedding") or []
        try:
            emb = [float(x) for x in emb]
        except (TypeError, ValueError):
            emb = []
        return cls(
            name=data.get("name", "desconhecido"),
            embedding=emb,
            created_at=data.get("created_at", ""),
        )


class FaceRecognition:
    """Cadastro e reconhecimento facial por embedding. Sem estado global.

    ``embed`` é injetável: recebe bytes da imagem e devolve np.ndarray[512]
    L2-normalizado (ou None se não houver rosto nítido).
    """

    def __init__(
        self,
        path: Path = FACES_PATH,
        embed: Callable[[bytes], np.ndarray | None] | None = None,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self._path = path
        self._embed = embed or _default_embed
        self._threshold = threshold
        self._lock = threading.Lock()
        self._profiles: dict[str, FaceProfile] = {}
        self._load()

    def extract_embedding(self, image_bytes: bytes) -> np.ndarray | None:
        try:
            return self._embed(image_bytes)
        except Exception as exc:
            log.warning("[FACIAL] embed falhou: %s", exc)
            return None

    # ── Persistência ──────────────────────────────────────────────
    def _load(self) -> None:
        try:
            if self._path.exists():
                raw = json.loads(self._path.read_text("utf-8"))
                self._profiles = {
                    p["name"]: FaceProfile.from_dict(p)
                    for p in raw.get("faces", [])
                    if isinstance(p, dict) and p.get("name")
                }
        except Exception as exc:
            log.error("[FACIAL] falha ao carregar faces: %s", exc)
            self._profiles = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(
                {"faces": [p.to_dict() for p in self._profiles.values()]},
                ensure_ascii=False,
                indent=2,
            ),
            "utf-8",
        )

    def list_faces(self) -> list[dict]:
        with self._lock:
            return [
                {"name": p.name, "created_at": p.created_at}
                for p in sorted(self._profiles.values(), key=lambda x: x.name)
            ]

    def register(self, name: str, image_bytes: bytes) -> dict:
        name = (name or "").strip()
        if not name:
            raise ValueError("Nome do usuário é obrigatório.")
        emb = self.extract_embedding(image_bytes)
        if emb is None:
            raise ValueError("Não foi possível reconhecer um rosto claro na imagem.")
        emb_list = [float(x) for x in emb.tolist()]
        with self._lock:
            self._profiles[name] = FaceProfile(name=name, embedding=emb_list)
            self._save()
        log.info("[FACIAL] registrado usuario=%s", name)
        return {"name": name, "registered": True}

    def delete(self, name: str) -> bool:
        with self._lock:
            existed = self._profiles.pop(name, None) is not None
            if existed:
                self._save()
        return existed

    def clear(self) -> None:
        with self._lock:
            self._profiles.clear()
            self._save()

    # ── Reconhecimento ────────────────────────────────────────────
    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        if a is None or b is None or a.size == 0 or b.size == 0:
            return 0.0
        a = a.astype(np.float32)
        b = b.astype(np.float32)
        na = float(np.linalg.norm(a))
        nb = float(np.linalg.norm(b))
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def recognize(self, image_bytes: bytes, threshold: float | None = None) -> dict:
        threshold = self._threshold if threshold is None else threshold
        emb = self.extract_embedding(image_bytes)
        if emb is None:
            return {"present": False, "name": None, "confidence": 0.0}

        with self._lock:
            matches = [
                (name, self._cosine(emb, np.asarray(p.embedding, dtype=np.float32)))
                for name, p in self._profiles.items()
            ]
        matches.sort(key=lambda x: x[1], reverse=True)
        best_name, best_conf = (matches[0] if matches else (None, 0.0))

        if best_name is None or best_conf < threshold:
            return {
                "present": True,
                "name": None,
                "confidence": round(best_conf, 3),
            }
        return {
            "present": True,
            "name": best_name,
            "confidence": round(best_conf, 3),
        }
