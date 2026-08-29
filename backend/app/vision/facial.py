"""Reconhecimento facial de usuário via modelo de visão (qwen2.5vl).

Abordagem escolhida (sem dependência pesada de CV): o modelo de visão
local converte o rosto em uma "assinatura" textual estruturada e
normalizada. O matcher compara assinaturas por sobreposição de tokens.

Limitação conhecida: não é um embedding facial verdadeiro; a precisão
depende da consistência do modelo de visão. Usado para cadastro +
identificação leve de usuário, não para segurança/autenticação forte.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..agent import llm
from ..config import DATA_DIR

log = logging.getLogger("studyagent.facial")

FACES_PATH = DATA_DIR / "faces.json"

_DEFAULT_PROMPT = """Analise o rosto da pessoa na imagem (se houver) e responda EXATAMENTE nesse formato, sem texto extra:

SE NÃO HÁ rosto humano claro e reconhecível: {"present": false, "features": ""}

SE HÁ rosto: {"present": true, "features": "lista de ATRIBUTOS separados por ponto e vírgula, apenas com valores objetivos e estáveis"}

Os atributos devem ser escolhidos APENAS desta lista fixa de categorias, usando os valores indicados:
- genero: masculino OU feminino OU indeterminado
- idade_faixa: crianca OU jovem OU adulto OU idoso
- pele: muito_clara OU clara OU media OU morena OU escura
- cabelo..comprimento: careca OU curto OU medio OU longo
- cabelo..cor: preto OU castanho OU ruivo OU louro OU grisalho OU grisaho OU indeterminado
- occlos: sim OU nao  (usa óculos)
- barba: sim OU nao  (barba/bigode visivel)

Exemplo válido: {"present": true, "features": "genero: masculino; idade_faixa: adulto; pele: media; cabelo..comprimento: curto; cabelo..cor: preto; occlos: sim; barba: nao"}

Não responda NADA além do JSON. Se necessário, omita categorias que não puder determinar com certeza."""


def _extract_json(text: str) -> dict:
    """Extrai o primeiro objeto JSON de um texto do VL (robusto a ruído)."""
    if not text:
        return {"present": False, "features": ""}
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if not m:
        return {"present": False, "features": ""}
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"present": False, "features": ""}
    if not isinstance(parsed, dict):
        return {"present": False, "features": ""}
    return parsed


def _normalize_features(features: str) -> set[str]:
    """Normaliza a string de atributos em um conjunto de tokens canônicos."""
    tokens: set[str] = set()
    for part in (features or "").replace(";", ",").split(","):
        part = part.strip().lower()
        if not part or ":" not in part:
            continue
        key, _, value = part.partition(":")
        key = re.sub(r"[^a-z]", "", key).strip()
        value = re.sub(r"[^a-z]", "", value).strip()
        if key and value:
            tokens.add(f"{key}:{value}")
    return tokens


def _fallback_signature(analyzed: str) -> str:
    return "; ".join(sorted(_normalize_features(analyzed)))


@dataclass
class FaceProfile:
    name: str
    signature: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {"name": self.name, "signature": self.signature, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, data: dict) -> "FaceProfile":
        return cls(
            name=data.get("name", "desconhecido"),
            signature=data.get("signature", ""),
            created_at=data.get("created_at", ""),
        )


class FaceRecognition:
    """Cadastro e reconhecimento de usuário via modelo de visão.

    O chamador injeta ``analyze`` (que recebe os bytes da imagem e retorna a
    análise textual do VL) para permitir teste sem rede.
    """

    def __init__(
        self,
        path: Path = FACES_PATH,
        analyze: Callable[[bytes], str] | None = None,
    ) -> None:
        self._path = path
        self._analyze = analyze or self._default_analyze
        self._lock = threading.Lock()
        self._profiles: dict[str, FaceProfile] = {}
        self._load()

    # ── VL bridge ─────────────────────────────────────────────────
    def _default_analyze(self, image_bytes: bytes) -> str:
        return llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Você é um sistema de reconhecimento visual. Obedeça "
                        "estritamente ao formato solicitado pelo usuário."
                    ),
                },
                {"role": "user", "content": _DEFAULT_PROMPT},
            ],
            images=[image_bytes],
        )

    def extract_signature(self, image_bytes: bytes) -> str:
        raw = self._analyze(image_bytes)
        data = _extract_json(raw)
        if not data.get("present"):
            return ""
        return _fallback_signature(data.get("features", ""))

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
        signature = self.extract_signature(image_bytes)
        if not signature:
            raise ValueError("Não foi possível reconhecer um rosto claro na imagem.")
        with self._lock:
            self._profiles[name] = FaceProfile(name=name, signature=signature)
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
    def _similarity(a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / max(len(a | b), 1)

    def recognize(self, image_bytes: bytes, threshold: float = 0.3) -> dict:
        signature = self.extract_signature(image_bytes)
        if not signature:
            return {"present": False, "name": None, "confidence": 0.0, "signature": ""}
        probe = _normalize_features(signature)
        with self._lock:
            matches = [
                (name, self._similarity(probe, _normalize_features(p.signature)))
                for name, p in self._profiles.items()
            ]
        matches.sort(key=lambda x: x[1], reverse=True)
        best_name, best_conf = (matches[0] if matches else (None, 0.0))
        if best_name is None or best_conf < threshold:
            return {
                "present": True,
                "name": None,
                "confidence": round(best_conf, 3),
                "signature": signature,
            }
        return {
            "present": True,
            "name": best_name,
            "confidence": round(best_conf, 3),
            "signature": signature,
        }
