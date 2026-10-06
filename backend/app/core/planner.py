"""
Planner V3 — roteamento de intenções antes do LLM.

Centraliza as decisões que hoje vivem espalhadas por regex no agente:

- qual a CATEGORIA de intenção (chat, documento, tela, câmera,
  busca na web, cálculo, ação de sistema)?
- a mensagem pede leitura de tela?
- de qual monitor?
- refere-se a um documento anexado?
- quer o conteúdo inteiro?
- pede informação atualizada?

V3 adiciona a classificação ampla de intenção (IntentCategory) e o
monitor no formato humano (human_monitor) usado pelo usuário.

Mantido puro (sem I/O) para ser trivialmente testável.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .vision_router import VisionIntent, detect_vision_intent


class IntentCategory(Enum):
    """Categoria ampla de intenção do usuário."""

    CHAT = "CHAT"
    DOCUMENT = "DOCUMENT"
    SCREEN = "SCREEN"
    CAMERA = "CAMERA"
    WEB_SEARCH = "WEB_SEARCH"
    CALCULATE = "CALCULATE"
    SYSTEM_ACTION = "SYSTEM_ACTION"

# ============================================================================
# REGEX — TELA / MONITOR
# ============================================================================

SCREEN_EXPLICIT_RE = re.compile(
    r"\b(?:telas?|monitor(?:es)?|screen(?:s)?)\b",
    re.IGNORECASE | re.UNICODE,
)


MONITOR_NUM_RE = re.compile(
    r"\b(?:telas?|monitor(?:es)?)"
    r"\s*(?:n[ºo°]?|número|numero)?"
    r"\s*([0-9]+)\b",
    re.IGNORECASE | re.UNICODE,
)


# "essa tela", "aqui", "na minha frente", "tela atual" → tela sob comando.
ACTIVE_SCREEN_RE = re.compile(
    r"(?:"
    r"\b(?:n[ae]sta|n[ae]ssa|essa|esta|aquela)\s+tela\b|"
    r"\btela\s+(?:atual|da\s+frente|em\s+destaque|do\s+aluno)\b|"
    r"\bminha\s+tela\b|"
    r"\bminha\s+frente\b|"
    r"\bna\s+frente\b|"
    r"\bdiante\s+dela\b|"
    r"\bque\s+(?:est[áa]o?s?|aparece[m]?|tem)\s+aqui\b|"
    r"\b(?:est[áa]|aparece|aparece[m]?)\s+(?:aqui|na\s+tela)\b"
    r")",
    re.IGNORECASE | re.UNICODE,
)


# ============================================================================
# REGEX — RESOLVER QUESTÕES
# ============================================================================

ANSWER_INTENT_RE = re.compile(
    r"\b("
    r"resolv\w+|"
    r"responda|responder|respostas?|"
    r"gabarit\w*|"
    r"soluc\w+|"
    r"corretas?\b|"
    r"alternativas?\s+corretas?|"
    r"qual\s+(?:é\s+)?(?:a\s+)?(?:resposta|alternativa|gabarito)|"
    r"identific\w*\s+(?:as\s+)?respostas?"
    r")\b",
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
# REGEX — CATEGORIA AMPLA
# ============================================================================

WEB_SEARCH_RE = re.compile(
    r"\b("
    r"busque|buscar|busca|"
    r"pesquise|pesquisar|pesquisa|"
    r"procure|procurar|"
    r"notícia\w*|noticia\w*|"
    r"preço\w*?|preco\w*?|cota\w*?|"
    r"resultad\w*|placar|"
    r"clima|tempo hoje|"
    r"quem (?:ganhou|venceu)|"
    r"últim\w*"
    r")\b",
    re.IGNORECASE | re.UNICODE,
)


CALCULATE_RE = re.compile(
    r"\b("
    r"quanto é|quanto e|quanto dá|quanto da|"
    r"calcule|calcular|cálculo|calculo|"
    r"soma\w*|some|subtrai\w*|"
    r"multiplic\w*|divide|dividi|"
    r"raiz|potência\w*|potencia\w*|[+\-*/^=]"
    r")\b",
    re.IGNORECASE | re.UNICODE,
)


SYSTEM_ACTION_RE = re.compile(
    r"\b("
    r"abra |abrir |abra o |"
    r"feche|fechar|"
    r"minimize|minimizar|"
    r"maximize|maximizar|"
    r"execute|executar|rodar|"
    r"abre o|abre a|"
    r"open |start |launch "
    r")\b",
    re.IGNORECASE,
)


# ============================================================================
# CATEGORIA AMPLA
# ============================================================================


def detect_category(
    message: str,
    *,
    capture_screen: bool,
    camera_image: bool,
    wants_document: bool,
) -> IntentCategory:
    """Classifica a intenção ampla do usuário.

    Prioridade:
        documento > câmera > tela > busca web > cálculo >
        ação de sistema > chat
    """

    lower = (message or "").lower()

    if wants_document:
        return IntentCategory.DOCUMENT

    if camera_image:
        return IntentCategory.CAMERA

    if capture_screen:
        return IntentCategory.SCREEN

    if WEB_SEARCH_RE.search(lower):
        return IntentCategory.WEB_SEARCH

    if CALCULATE_RE.search(lower):
        return IntentCategory.CALCULATE

    if SYSTEM_ACTION_RE.search(lower):
        return IntentCategory.SYSTEM_ACTION

    return IntentCategory.CHAT


# ============================================================================
# SAUDAÇÕES / CONVERSA CASUAL
# ============================================================================

GREETING_RE = re.compile(
    r"^\s*("
    r"oi|olá|ola|oii|oiii|e\s*aí|eai|salve|opa|fala|"
    r"bom\s+dia|boa\s+tarde|boa\s+noite|"
    r"hello|hi|hey|hem|hmm"
    r")\s*"
    r"("
    r"tudo\s+bem|tudo\s+blz|blz|beleza|"
    r"como\s+vai|como\s+voc[eê]\s+est[aá]|"
    r"como\s+est[aá]|td\s+bem|est[aá]\s+a[ií]|e\s*a[ií]|"
    r"t[aá]\s+me\s+ouvind\w*|t[aá]\s+me\s+escutand\w*|"
    r"consegue\s+me\s+(?:ouvir|escutar)|"
    r"me\s+(?:ouve|escuta)|"
    r"t[aá]\s+por\s+a[ií]|est[aá]\s+por\s+a[ií]|"
    r"t[aá]\s+funcionand\w*|funcionand\w*|"
    r"[.,;!?ç\s]*"
    r")*"
    r"\s*$",
    re.IGNORECASE | re.UNICODE,
)


def is_social_greeting(message: str) -> bool:
    """Indica se a mensagem é essencialmente uma saudação/social.

    Usado para desviar de saudações para o chat de texto simples
    (sem tool-calling), evitando que modelos de tool-calling
    confabulem respostas sobre 'função JSON' em vez de saudar.
    """
    if not message or not message.strip():
        return False
    return bool(GREETING_RE.search(message.strip()))


# ============================================================================
# PLANO
# ============================================================================

@dataclass
class Plan:
    """Plano de execução produzido pelo Planner."""

    message: str

    category: IntentCategory = IntentCategory.CHAT

    explicit_screen: bool = False
    capture_screen: bool = False

    monitor: int | None = None

    human_monitor: int | None = None

    monitor_explicit: bool = False

    active_screen: bool = False

    want_answers: bool = False

    vision_required: bool = False
    vision_intent: VisionIntent = VisionIntent.SCREEN_QUESTION

    doc_id: str | None = None
    whole_doc: bool = False

    @property
    def wants_document(self) -> bool:
        """Indica que existe um documento associado ao plano."""

        return self.doc_id is not None

    @property
    def needs_active_monitor(self) -> bool:
        """Indica que o monitor deve ser descoberto pela janela ativa.

        Só acontece quando o usuário não citou um número de tela/monitor:
        "essa tela" precisa virar o monitor onde a janela em foco está.
        """

        return self.capture_screen and not self.monitor_explicit


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
    - Sem número explícito, a tela sob comando é a que tem a janela
      em foco (monitor_explicit=False → needs_active_monitor=True).
    - Pedido de resolução de questões força a intenção SCREEN_EXERCISE.
    """

    plan = Plan(message=message)

    lower = message.lower()

    # ================================================================
    # TELA / MONITOR
    # ================================================================

    plan.explicit_screen = bool(
        SCREEN_EXPLICIT_RE.search(lower)
    )

    num = None
    matches = list(MONITOR_NUM_RE.finditer(lower))
    if matches:
        num = matches[-1]

    plan.active_screen = bool(ACTIVE_SCREEN_RE.search(lower))

    plan.want_answers = bool(ANSWER_INTENT_RE.search(lower))

    if num:
        requested_number = int(num.group(1))

        plan.monitor_explicit = True

        # Número humano informado pelo usuário (tela 1 / monitor 2).
        plan.human_monitor = requested_number

        # "tela 1" = monitor interno 0
        # "tela 2" = monitor interno 1
        # "tela 3" = monitor interno 2
        if re.search(r"\btelas?\b", num.group(0)):
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

    if plan.wants_document and not plan.explicit_screen and not plan.active_screen:
        plan.capture_screen = False

    elif use_screen_requested or plan.explicit_screen or plan.active_screen:
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

        # "resolva as questões da tela" precisa da intenção de exercício,
        # mesmo quando o usuário não escreveu a palavra "exercício".
        if plan.want_answers and plan.vision_intent != VisionIntent.SCREEN_ERROR:
            plan.vision_intent = VisionIntent.SCREEN_EXERCISE

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

    # ================================================================
    # CATEGORIA AMPLA DE INTENÇÃO (V3)
    # ================================================================

    plan.category = detect_category(
        message,
        capture_screen=plan.capture_screen,
        camera_image=camera_image,
        wants_document=plan.wants_document,
    )

    return plan
