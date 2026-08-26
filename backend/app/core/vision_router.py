"""Roteamento visual puro: objetos estruturados e prompt de visão.

Pipeline de visão dedicado (NÃO genérico):
  VisionRequest → ScreenManager → ScreenCaptureResult → OCRResult → VisionEngine → VisualContext

O ``context_manager`` usa ``build_vision_system_prompt`` para SUBSTITUIR
o system prompt genérico quando há imagem — o motivo raiz de "olá" em
vez de descrição visual.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

MIN_OCR_CHARS = 60
MAX_OCR_CHARS = 2500


# ── Objetos estruturados do pipeline de visão ─────────────────────


class VisionIntent(Enum):
    """Intenção do usuário ao pedir visão de tela."""

    SCREEN_QUESTION = "screen_question"
    SCREEN_READ = "screen_read"
    SCREEN_DESCRIBE = "screen_describe"
    SCREEN_ERROR = "screen_error"
    SCREEN_CODE = "screen_code"
    SCREEN_EXERCISE = "screen_exercise"
    SCREEN_EXPLICIT = "screen_explicit"
    CAMERA = "camera"


@dataclass
class VisionRequest:
    """Entrada estruturada para o pipeline de visão."""

    message: str
    monitor: int = 1
    region: dict | None = None
    camera_image_b64: str | None = None
    intent: VisionIntent = VisionIntent.SCREEN_QUESTION
    session_id: str | None = None

    @property
    def is_screen(self) -> bool:
        return self.intent != VisionIntent.CAMERA

    @property
    def is_camera(self) -> bool:
        return self.intent == VisionIntent.CAMERA


@dataclass
class ScreenCaptureResult:
    """Resultado de uma captura de tela validada."""

    image: Any  # PIL.Image.Image
    monitor: int
    width: int
    height: int
    is_valid: bool = True
    error: str | None = None

    @classmethod
    def from_image(cls, image, monitor: int) -> ScreenCaptureResult:
        return cls(
            image=image,
            monitor=monitor,
            width=image.width,
            height=image.height,
            is_valid=image.width > 0 and image.height > 0,
        )

    @classmethod
    def failed(cls, monitor: int, error: str) -> ScreenCaptureResult:
        return cls(
            image=None,
            monitor=monitor,
            width=0,
            height=0,
            is_valid=False,
            error=error,
        )


@dataclass
class OCRResult:
    """Resultado estruturado do OCR."""

    text: str
    char_count: int = 0
    is_useful: bool = False
    error: str | None = None

    @classmethod
    def from_text(cls, text: str | None) -> OCRResult:
        if not text:
            return cls(text="", char_count=0, is_useful=False)
        texto = text.strip()
        return cls(
            text=texto,
            char_count=len(texto),
            is_useful=len(texto) >= MIN_OCR_CHARS,
        )

    @classmethod
    def failed(cls, error: str) -> OCRResult:
        return cls(text="", char_count=0, is_useful=False, error=error)


@dataclass
class VisionContext:
    """Contexto visual estruturado que vai para o tutor.

    Substitui o fluxo genérico de image_note + ocr + window por um
    objeto que o tutor捧e e usa diretamente.
    """

    source: str  # "screen" | "camera"
    monitor_id: int | None = None
    resolution: tuple[int, int] | None = None
    ocr_text: str | None = None
    window_app: str | None = None
    window_title: str | None = None
    image_bytes: bytes = b""
    vision_confidence: float = 0.0
    pipeline_stages: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_ocr(self) -> bool:
        return bool(self.ocr_text and len(self.ocr_text.strip()) >= MIN_OCR_CHARS)

    @property
    def is_valid(self) -> bool:
        return bool(self.image_bytes) and not self.errors


# ── System prompt de visão (SUBSTITUI o genérico) ─────────────────


VISION_SYSTEM_PROMPT = """\
Você é um analista visual. Sua ÚNICA tarefa é analisar a imagem anexada.

REGRA ABSOLUTA: Descreva o que vê na imagem. NUNCA dê saudação.
Se houver texto, leia. Se houver exercício, resolva. Se houver erro, identifique.

 FORMATO DA RESPOSTA:
1. O QUE VEJO: descreva o conteúdo visual (aplicativo, janela, layout)
2. CONTEÚDO: texto, código, exercício, erro, gráfico — o que estiver visível
3. ANÁLISE: responda à pergunta do usuário sobre o conteúdo visual

 Seu papel é OLHAR a imagem e REPORTAR o que vê, não conversar.
Se não conseguir ver a imagem, diga: "Não consegui analisar a imagem." """

# ── Notas auxiliares (compatibilidade com fluxo legado) ────────────


def build_image_note(camera: bool, monitor=None, size=None) -> str:
    """Nota explicando a origem da(s) imagem(ns) anexada(s)."""
    if camera:
        return (
            "[IMAGEM ANEXADA — FOTO DA CÂMERA]\n"
            "INSTRUÇÃO: Analise esta foto. O que você vê? Descreva o conteúdo.\n"
            "Responda sobre o conteúdo da imagem, não dê saudação."
        )
    origem = f"monitor {monitor}" if monitor else "tela"
    dim = f" ({size[0]}x{size[1]})" if size else ""
    return (
        f"[CONTEÚDO VISUAL DA TELA — ANALISE ANTES DE RESPONDER]\n"
        f"Tipo: Captura de {origem}{dim}\n"
        f"\n"
        f"INSTRUÇÕES OBRIGATÓRIAS:\n"
        f"1. PRIMEIRO: olhe a imagem e descreva o que vê\n"
        f"2. SEGUNDO: identifique aplicação, conteúdo, exercícios, erros, código, texto\n"
        f"3. TERCEIRO: responda à pergunta do usuário sobre o conteúdo da tela\n"
        f"\n"
        f"Se houver EXERCÍCIO ou QUESTÃO: leia o enunciado e resolva ou guie o aluno\n"
        f"Se houver ERRO: identifique e explique como resolver\n"
        f"Se houver CÓDIGO: leia e analise\n"
        f"Se houver TEXTO: descreva e responda sobre ele\n"
        f"\n"
        f"NÃO dê saudação. NÃO pergunte 'como posso ajudar'. APERTE O OLHAR NA IMAGEM.\n"
        f"[FIM DAS INSTRUÇÕES VISUAIS]"
    )


def decide_ocr_block(ocr_text: str | None) -> str | None:
    """Retorna bloco com o texto do OCR quando ele agrega (texto denso)."""
    if not ocr_text:
        return None
    texto = ocr_text.strip()
    if len(texto) < MIN_OCR_CHARS:
        return None
    if len(texto) > MAX_OCR_CHARS:
        texto = texto[:MAX_OCR_CHARS] + "\n[…]"
    return (
        "TEXTO DETECTADO POR OCR NA IMAGEM (confiável para nomes, números "
        "e símbolos; ignore erros óbvios de leitura):\n\n"
        f"{texto}"
    )


def format_window_note(window: dict | None) -> str | None:
    """Contexto da janela ativa, quando o ambiente consegue informá-la."""
    if not window:
        return None
    app = window.get("app")
    title = window.get("title")
    partes = []
    if app:
        partes.append(f"aplicativo: {app}")
    if title:
        partes.append(f"janela: {title}")
    if not partes:
        return None
    return "(Janela ativa do usuário no momento da captura — " + "; ".join(partes) + ".)"


# ── Detecção de intenção visual ───────────────────────────────────

_SCREEN_VERBS_RE = re.compile(
    r"\b(leia|leia o|leia a|descreva|descrever|explique|o que (?:tem|está|há|viu|tem na)"
    r"|o que (?:você )?(?:vê|consegue ver|está vendo)"
    r"|analise|analisar|olhe|olhar|verifique|ver o que"
    r"|tem algo|tem exerc|tem código|tem erro|tem texto)\b",
    re.IGNORECASE,
)

_SCREEN_ERROR_RE = re.compile(
    r"\b(erro|bug|exception|traceback|error|crash|falha)\b", re.IGNORECASE
)

_SCREEN_CODE_RE = re.compile(
    r"\b(código|code|programa|script|função|class|def |import |from )\b",
    re.IGNORECASE,
)

_SCREEN_EXERCISE_RE = re.compile(
    r"\b(exerc\w*|questão|problema|atividade|prova|lista|resolva|responder)\b",
    re.IGNORECASE,
)


def detect_vision_intent(message: str) -> VisionIntent:
    """Detecta a intenção visual a partir da mensagem do usuário."""
    if _SCREEN_ERROR_RE.search(message):
        return VisionIntent.SCREEN_ERROR
    if _SCREEN_CODE_RE.search(message):
        return VisionIntent.SCREEN_CODE
    if _SCREEN_EXERCISE_RE.search(message):
        return VisionIntent.SCREEN_EXERCISE
    if _SCREEN_VERBS_RE.search(message):
        return VisionIntent.SCREEN_READ
    return VisionIntent.SCREEN_QUESTION
