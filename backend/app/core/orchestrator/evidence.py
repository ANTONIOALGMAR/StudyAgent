"""Evidence Store — armazenamento estruturado de evidências.

Cada execução de ferramenta gera evidências rastreáveis.
O Response Validator usa essas evidências para validar a resposta final.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvidenceType(Enum):
    SCREEN = "SCREEN"
    OCR = "OCR"
    VISION = "VISION"
    DOCUMENT = "DOCUMENT"
    RAG = "RAG"
    WEB = "WEB"
    USER = "USER"
    TOOL = "TOOL"
    WINDOW = "WINDOW"
    INTENT = "INTENT"


@dataclass
class Evidence:
    """Uma evidência individual coletada durante a execução."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: str = ""  # ferramenta que gerou
    evidence_type: EvidenceType = EvidenceType.TOOL
    content: str = ""
    confidence: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "type": self.evidence_type.value,
            "content": self.content[:200] + "…" if len(self.content) > 200 else self.content,
            "confidence": self.confidence,
            "data_keys": list(self.data.keys()),
            "timestamp": self.timestamp,
            "duration_ms": round(self.duration_ms, 1),
        }


class EvidenceStore:
    """Armazena todas as evidências de uma execução."""

    def __init__(self, execution_id: str = ""):
        self.execution_id = execution_id or uuid.uuid4().hex[:8]
        self._evidence: list[Evidence] = []
        self._started = time.time()

    def add(
        self,
        source: str,
        evidence_type: EvidenceType,
        content: str = "",
        confidence: float = 1.0,
        data: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
        **metadata: Any,
    ) -> Evidence:
        ev = Evidence(
            source=source,
            evidence_type=evidence_type,
            content=content,
            confidence=confidence,
            data=data or {},
            duration_ms=duration_ms,
            metadata=metadata,
        )
        self._evidence.append(ev)
        return ev

    def add_screen(
        self,
        monitor: int,
        width: int,
        height: int,
        *,
        duration_ms: float = 0.0,
        backend: str = "mss",
    ) -> Evidence:
        return self.add(
            source="screen.capture",
            evidence_type=EvidenceType.SCREEN,
            content=f"Captura do monitor {monitor} ({width}x{height})",
            confidence=1.0,
            data={"monitor": monitor, "width": width, "height": height, "backend": backend},
            duration_ms=duration_ms,
        )

    def add_ocr(
        self,
        text: str,
        *,
        confidence: float = 0.8,
        duration_ms: float = 0.0,
    ) -> Evidence:
        return self.add(
            source="ocr.read",
            evidence_type=EvidenceType.OCR,
            content=text,
            confidence=confidence,
            data={"char_count": len(text)},
            duration_ms=duration_ms,
        )

    def add_vision(
        self,
        description: str,
        *,
        confidence: float = 0.9,
        duration_ms: float = 0.0,
    ) -> Evidence:
        return self.add(
            source="vision.analyze",
            evidence_type=EvidenceType.VISION,
            content=description,
            confidence=confidence,
            duration_ms=duration_ms,
        )

    def add_intent(
        self,
        intent: str,
        monitor: int | None = None,
    ) -> Evidence:
        return self.add(
            source="planner",
            evidence_type=EvidenceType.INTENT,
            content=f"Intent={intent}" + (f" monitor={monitor}" if monitor else ""),
            confidence=1.0,
            data={"intent": intent, "monitor": monitor},
        )

    def add_window(
        self,
        app: str | None = None,
        title: str | None = None,
    ) -> Evidence:
        return self.add(
            source="window.active",
            evidence_type=EvidenceType.WINDOW,
            content=f"{app or '?'} — {title or '?'}",
            confidence=0.7,
            data={"app": app, "title": title},
        )

    def get_by_type(self, evidence_type: EvidenceType) -> list[Evidence]:
        return [e for e in self._evidence if e.evidence_type == evidence_type]

    @property
    def screen_evidence(self) -> list[Evidence]:
        return self.get_by_type(EvidenceType.SCREEN)

    @property
    def ocr_evidence(self) -> list[Evidence]:
        return self.get_by_type(EvidenceType.OCR)

    @property
    def vision_evidence(self) -> list[Evidence]:
        return self.get_by_type(EvidenceType.VISION)

    @property
    def has_screen(self) -> bool:
        return len(self.screen_evidence) > 0

    @property
    def has_ocr(self) -> bool:
        return any(e.content.strip() for e in self.ocr_evidence)

    @property
    def has_vision(self) -> bool:
        return len(self.vision_evidence) > 0

    @property
    def min_confidence(self) -> float:
        if not self._evidence:
            return 0.0
        return min(e.confidence for e in self._evidence)

    @property
    def total_duration_ms(self) -> float:
        return sum(e.duration_ms for e in self._evidence)

    @property
    def all_evidence(self) -> list[Evidence]:
        return list(self._evidence)

    def summary(self) -> dict:
        elapsed = (time.time() - self._started) * 1000
        return {
            "execution_id": self.execution_id,
            "evidence_count": len(self._evidence),
            "types": [e.evidence_type.value for e in self._evidence],
            "min_confidence": self.min_confidence,
            "total_tool_ms": round(self.total_duration_ms, 1),
            "elapsed_ms": round(elapsed, 1),
            "has_screen": self.has_screen,
            "has_ocr": self.has_ocr,
            "has_vision": self.has_vision,
        }

    def __len__(self) -> int:
        return len(self._evidence)

    def __iter__(self):
        return iter(self._evidence)
