"""
Planner V2 — roteamento de intenções antes do LLM.

Centraliza as decisões que hoje vivem espalhadas por regex no agente:

- a mensagem pede leitura de tela?
- de qual monitor?
- refere-se a um documento anexado?
- quer o conteúdo inteiro?
- pede informação atualizada?

Mantido puro (sem I/O) para ser trivialmente testável.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .vision_router import VisionIntent, detect_vision_intent

# ============================================================================
# REGEX — TELA / MONITOR
# ============================================================================

SCREEN_EXPLICIT_RE = re.compile(
    r"\b(tela|monitor|screen)\b",
    re.IGNORECASE | re.UNICODE,
)


MONITOR_NUM_RE = re.compile(
    r"\b(?:tela|monitor)"
    r"\s*(?:n[ºo°]?|número|numero)?"
    r"\s*([0-9]+)\b",
    re.IGNORECASE | re.UNICODE,
)


# ============================================================================
# REGEX — DOCUMENTOS
# ============================================================================

DOC_INTENT_RE = re.compile(
    r"\b("
    r"pdf|"
    r"documento|"
    r"apostila|"
    r"arquivo|"
    r"material|"
    r"leia|"
    r"ler|"
    r"resum\w*|"
    r"text\w*"
    r")\b",
    re.IGNORECASE | re.UNICODE,
)


# ============================================================================
# REGEX — LEITURA INTEGRAL DO DOCUMENTO
# ============================================================================

WHOLE_DOC_RE = re.compile(
    r"\b("
    r"resum\w*|"
    r"todo|"
    r"toda|"
    r"tudo|"
    r"inteir\w*|"
    r"complet\w*|"
    r"geral|"
    r"visão\s+geral|"
    r"lista\w*|"
    r"todas?\s+as?\s+páginas?|"
    r"leia|"
    r"ler"
    r")\b",
    re.IGNORECASE | re.UNICODE,
)


# ============================================================================
# REGEX — INFORMAÇÃO VOLÁTIL / ATUALIZADA
# ============================================================================

FRESH_INFO_RE = re.compile(
    r"\b("
    r"hoje|"
    r"ontem|"
    r"agora|"
    r"últim\w*|"
    r"atual\w*|"
    r"resultado|"
    r"placar|"
    r"cotação|"
    r"preço|"
    r"notícia\w*|"
    r"quem\s+ganhou|"
    r"quem\s+venceu"
    r")\b",
    re.IGNORECASE | re.UNICODE,
)


# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

WHOLE_DOC_MAX_CHARS = 15000


# ============================================================================
# PLANO
# ============================================================================

@dataclass
class Plan:
    """Plano de execução produzido pelo Planner."""

    message: str

    explicit_screen: bool = False
    capture_screen: bool = False

    monitor: int | None = None

    vision_required: bool = False
    vision_intent: VisionIntent = VisionIntent.SCREEN_QUESTION

    doc_id: str | None = None
    whole_doc: bool = False

    @property
    def wants_document(self) -> bool:
        """Indica se existe um documento associado ao plano."""

        return self.doc_id is not None


# ============================================================================
# BUILD PLAN
# ============================================================================

def build_plan(
    message: str,
    *,
    use_screen_requested: bool,
    live_panel_open: bool = False,
    camera_image: bool = False,
    requested_doc_id: str | None = None,
    session_doc_id: str | None = None,
    doc_text_len: int | None = None,
) -> Plan:
    """Decide o que a mensagem pede, combinando flags e texto.

    Regras:
    - Documento tem prioridade sobre captura de tela, exceto se a pessoa
      falar explicitamente de tela/monitor.
    - Painel ao vivo habilita captura quando não há documento/câmera.
    - "tela N" usa numeração humana: tela 1, tela 2, tela 3...
    - "monitor N" usa índice técnico: monitor 0, monitor 1, monitor 2...
    """

    plan = Plan(message=message)

    lower = message.lower()

    # ================================================================
    # TELA / MONITOR
    # ================================================================

    plan.explicit_screen = bool(
        SCREEN_EXPLICIT_RE.search(lower)
    )

    num = MONITOR_NUM_RE.search(lower)

    if num:
        requested_number = int(num.group(1))

        # "tela 1" = monitor interno 0
        # "tela 2" = monitor interno 1
        # "tela 3" = monitor interno 2
        if re.search(r"\btela\b", lower):
            plan.monitor = requested_number - 1

        # "monitor 0" = monitor interno 0
        # "monitor 1" = monitor interno 1
        # "monitor 2" = monitor interno 2
        else:
            plan.monitor = requested_number

    # ================================================================
    # DOCUMENTO
    # ================================================================

    if requested_doc_id:
        plan.doc_id = requested_doc_id

    elif session_doc_id and DOC_INTENT_RE.search(lower):
        plan.doc_id = session_doc_id

    # ================================================================
    # DECISÃO DE CAPTURA
    # ================================================================

    if plan.wants_document and not plan.explicit_screen:
        plan.capture_screen = False

    elif use_screen_requested or plan.explicit_screen:
        plan.capture_screen = True

    elif (
        live_panel_open
        and not camera_image
        and not plan.wants_document
    ):
        plan.capture_screen = True

    else:
        plan.capture_screen = False

    # ================================================================
    # INTENÇÃO VISUAL
    # ================================================================

    if plan.capture_screen:
        plan.vision_required = True
        plan.vision_intent = detect_vision_intent(message)

    elif camera_image:
        plan.vision_required = True
        plan.vision_intent = VisionIntent.CAMERA

    # ================================================================
    # LEITURA INTEGRAL DO DOCUMENTO
    # ================================================================

    if plan.wants_document:

        if doc_text_len is not None:
            plan.whole_doc = (
                (
                    len(message) > 0
                    and bool(WHOLE_DOC_RE.search(lower))
                )
                or doc_text_len <= WHOLE_DOC_MAX_CHARS
            )

        else:
            plan.whole_doc = bool(
                WHOLE_DOC_RE.search(lower)
            )

    return plan
