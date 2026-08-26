"""Planner V2 — roteamento de intenções antes do LLM.

Centraliza as decisões que hoje vivem espalhadas por regex no agente:
- a mensagem pede leitura de tela? de qual monitor?
- refere-se a um documento anexado? quer o conteúdo inteiro?
Mantido puro (sem I/O) para ser trivialmente testável.
"""

import re
from dataclasses import dataclass

from .vision_router import VisionIntent, detect_vision_intent

SCREEN_EXPLICIT_RE = re.compile(r"\b(tela|monitor|screen)\b", re.UNICODE)
MONITOR_NUM_RE = re.compile(
    r"\b(?:tela|monitor)\s*(?:n?[ºo°]?\s*)?([0-9]+)\b", re.UNICODE
)
DOC_INTENT_RE = re.compile(
    r"\b(pdf|documento|apostila|arquivo|material|leia|ler|resum\w*|texto)\b",
    re.UNICODE,
)
WHOLE_DOC_RE = re.compile(
    r"\b(resum\w*|todo|toda|tudo|intei\w+|complet\w+|geral"
    r"|visão geral|lista\w*|todas as páginas|leia|ler)\b",
    re.UNICODE,
)
# Perguntas sobre fatos voláteis → reforça uso da busca
FRESH_INFO_RE = re.compile(
    r"\b(hoje|ontem|agora|últim\w+|atual\w*|resultado|placar|cotação|preço"
    r"|notícia\w*|quem ganhou|quem venceu)\b",
    re.UNICODE,
)
WHOLE_DOC_MAX_CHARS = 15000


@dataclass
class Plan:
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
        return self.doc_id is not None


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
    - "tela N"/"monitor N" fixa o monitor exato (None = não especificado).
    """
    plan = Plan(message=message)
    lower = message.lower()

    plan.explicit_screen = bool(SCREEN_EXPLICIT_RE.search(lower))
    num = MONITOR_NUM_RE.search(lower)
    if num:
        plan.monitor = int(num.group(1))

    # resolução do documento (ANTES das decisões de captura)
    if requested_doc_id:
        plan.doc_id = requested_doc_id
    elif session_doc_id and DOC_INTENT_RE.search(lower):
        plan.doc_id = session_doc_id

    # decisão de captura
    if plan.wants_document and not plan.explicit_screen:
        plan.capture_screen = False
    elif use_screen_requested or plan.explicit_screen:
        plan.capture_screen = True
    elif live_panel_open and not camera_image and not plan.wants_document:
        plan.capture_screen = True
    else:
        plan.capture_screen = False

    # intenção visual
    if plan.capture_screen:
        plan.vision_required = True
        plan.vision_intent = detect_vision_intent(message)
    elif camera_image:
        plan.vision_required = True
        plan.vision_intent = VisionIntent.CAMERA

    # leitura integral?
    if plan.wants_document:
        if doc_text_len is not None:
            plan.whole_doc = (
                len(message) > 0 and bool(WHOLE_DOC_RE.search(lower))
            ) or doc_text_len <= WHOLE_DOC_MAX_CHARS
        else:
            plan.whole_doc = bool(WHOLE_DOC_RE.search(lower))

    return plan
