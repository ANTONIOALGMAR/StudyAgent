"""
Vision Router — pipeline visual estruturado do StudyAgent.

Responsabilidades:

    mensagem do usuário
        ↓
    detecção de intenção visual
        ↓
    identificação explícita do monitor
        ↓
    VisionRequest
        ↓
    captura de tela
        ↓
    OCR / contexto da janela
        ↓
    VisionContext
        ↓
    prompt multimodal

IMPORTANTE
----------
Este módulo NÃO executa o modelo de visão.

Ele é responsável por construir um contexto visual confiável
para o agente e para o orquestrador.

O pipeline deve ser determinístico sempre que possível.

Exemplos:

    "leia meu monitor 2"
        → SCREEN_READ
        → monitor_id=2

    "o que aparece na tela 1?"
        → SCREEN_QUESTION
        → monitor_id=1

    "analise o código do monitor 0"
        → SCREEN_CODE
        → monitor_id=0

    "tem algum erro no monitor 2?"
        → SCREEN_ERROR
        → monitor_id=2
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ============================================================================
# CONFIGURAÇÕES
# ============================================================================

MIN_OCR_CHARS = 60
MAX_OCR_CHARS = 2500

DEFAULT_MONITOR_ID = 0


# ============================================================================
# INTENÇÕES VISUAIS
# ============================================================================


class VisionIntent(Enum):
    """Intenção detectada para operações visuais."""

    SCREEN_QUESTION = "SCREEN_QUESTION"
    SCREEN_READ = "SCREEN_READ"
    SCREEN_DESCRIBE = "SCREEN_DESCRIBE"
    SCREEN_ERROR = "SCREEN_ERROR"
    SCREEN_CODE = "SCREEN_CODE"
    SCREEN_EXERCISE = "SCREEN_EXERCISE"
    CAMERA = "CAMERA"


# ============================================================================
# REQUEST
# ============================================================================


@dataclass
class VisionRequest:
    """
    Solicitação estruturada de visão.

    Este objeto representa a intenção antes da captura da imagem.
    """

    message: str

    # None significa:
    # "monitor ainda não especificado".
    #
    # Isso é proposital. Não devemos assumir silenciosamente monitor 1.
    monitor_id: int | None = None

    region: dict | None = None

    camera_image_b64: str | None = None

    intent: VisionIntent = VisionIntent.SCREEN_QUESTION

    session_id: str | None = None

    explicit_monitor: bool = False

    @property
    def is_screen(self) -> bool:
        """Indica se a requisição pertence ao pipeline de tela."""
        return self.intent != VisionIntent.CAMERA

    @property
    def is_camera(self) -> bool:
        """Indica se a requisição é originada da câmera."""
        return self.intent == VisionIntent.CAMERA

    @property
    def has_explicit_monitor(self) -> bool:
        """Indica se o usuário informou explicitamente o monitor."""
        return self.monitor_id is not None and self.explicit_monitor


# ============================================================================
# RESULTADO DA CAPTURA
# ============================================================================


@dataclass
class ScreenCaptureResult:
    """Resultado estruturado de uma captura de tela."""

    monitor_id: int

    image: Any = None

    width: int = 0

    height: int = 0

    is_valid: bool = True

    error: str | None = None

    backend: str | None = None

    @classmethod
    def from_image(
        cls,
        image,
        monitor_id: int,
        backend: str | None = None,
    ) -> ScreenCaptureResult:
        """Cria resultado a partir de uma imagem PIL válida."""

        if image is None:
            return cls.failed(
                monitor_id,
                "Captura retornou None.",
            )

        width = int(getattr(image, "width", 0))
        height = int(getattr(image, "height", 0))

        if width <= 0 or height <= 0:
            return cls.failed(
                monitor_id,
                f"Imagem inválida: {width}x{height}.",
            )

        return cls(
            monitor_id=monitor_id,
            image=image,
            width=width,
            height=height,
            is_valid=True,
            backend=backend,
        )

    @classmethod
    def failed(
        cls,
        monitor_id: int,
        error: str,
    ) -> ScreenCaptureResult:
        """Cria resultado de captura inválida."""

        return cls(
            monitor_id=monitor_id,
            width=0,
            height=0,
            is_valid=False,
            error=error,
        )


# ============================================================================
# OCR
# ============================================================================


@dataclass
class OCRResult:
    """Resultado estruturado do OCR."""

    text: str

    char_count: int = 0

    is_useful: bool = False

    error: str | None = None

    @classmethod
    def from_text(
        cls,
        text: str | None,
    ) -> OCRResult:
        """Normaliza o resultado do OCR."""

        if not text:
            return cls(
                text="",
                char_count=0,
                is_useful=False,
            )

        texto = str(text).strip()

        return cls(
            text=texto,
            char_count=len(texto),
            is_useful=len(texto) >= MIN_OCR_CHARS,
        )

    @classmethod
    def failed(
        cls,
        error: str,
    ) -> OCRResult:
        """Cria resultado de OCR com erro."""

        return cls(
            text="",
            char_count=0,
            is_useful=False,
            error=error,
        )


# ============================================================================
# CONTEXTO VISUAL
# ============================================================================


@dataclass
class VisionContext:
    """
    Contexto visual consolidado.

    É este objeto que deve ser entregue ao agente/orquestrador.
    """

    source: str

    monitor_id: int | None = None

    resolution: tuple[int, int] | None = None

    ocr_text: str | None = None

    window_app: str | None = None

    window_title: str | None = None

    image_bytes: bytes = b""

    user_question: str = ""

    intent: VisionIntent = VisionIntent.SCREEN_QUESTION

    vision_confidence: float = 0.0

    pipeline_stages: list[str] = field(default_factory=list)

    errors: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_ocr(self) -> bool:
        """Indica se existe OCR útil."""
        return bool(
            self.ocr_text
            and len(self.ocr_text.strip()) >= MIN_OCR_CHARS
        )

    @property
    def has_image(self) -> bool:
        """Indica se existe imagem efetivamente anexada."""
        return bool(self.image_bytes)

    @property
    def is_valid(self) -> bool:
        """
        Contexto é válido quando existe imagem e não há erros fatais.
        """
        return bool(self.image_bytes) and not self.errors

    def add_stage(self, stage: str) -> None:
        """Registra uma etapa do pipeline."""
        if stage not in self.pipeline_stages:
            self.pipeline_stages.append(stage)

    def add_error(self, error: str) -> None:
        """Registra erro do pipeline."""
        if error and error not in self.errors:
            self.errors.append(error)

    def prompt_context(self) -> str:
        """
        Constrói contexto textual para o modelo de visão.
        """

        resolution = "desconhecida"

        if self.resolution:
            resolution = (
                f"{self.resolution[0]}x{self.resolution[1]}"
            )

        monitor = (
            str(self.monitor_id)
            if self.monitor_id is not None
            else "não especificado"
        )

        return f"""
CONTEXTO VISUAL REAL DO STUDYAGENT

FONTE:
{self.source}

MONITOR:
{monitor}

RESOLUÇÃO:
{resolution}

INTENÇÃO VISUAL:
{self.intent.value}

APLICATIVO DETECTADO:
{self.window_app or "não identificado"}

JANELA:
{self.window_title or "não identificada"}

OCR:
{self.ocr_text or "(nenhum texto detectado)"}

PERGUNTA ORIGINAL DO USUÁRIO:
{self.user_question}

ESTÁGIOS DO PIPELINE:
{", ".join(self.pipeline_stages) or "nenhum"}

A imagem anexada deve ser considerada a representação visual REAL
do monitor solicitado.

REGRAS OBRIGATÓRIAS:

1. Analise a imagem antes de responder.
2. Não invente informações que não estejam na imagem.
3. Não dê saudação.
4. Não responda com frases genéricas.
5. Responda diretamente à pergunta do usuário.
6. Se houver código, leia e analise o código.
7. Se houver erro, identifique o erro.
8. Se houver exercício, leia o enunciado.
9. Se houver gráfico, interprete os elementos visíveis.
10. Se houver texto, utilize o texto realmente visível.
11. Use OCR como apoio, não como substituto da imagem.
12. Caso OCR e imagem entrem em conflito, priorize a imagem.
13. Se a imagem não permitir concluir algo, diga claramente.
14. Nunca finja ter visto algo que não está na imagem.
""".strip()


# ============================================================================
# SYSTEM PROMPT DE VISÃO
# ============================================================================


VISION_SYSTEM_PROMPT = """
Você é o módulo de VISÃO do StudyAgent.

Sua função é analisar visualmente a imagem recebida.

A imagem é a fonte primária da informação.

NUNCA responda como um chatbot genérico.

NUNCA comece com:
- Olá
- Oi
- Como posso ajudar?
- Estou aqui para ajudar
- Vamos começar

Quando uma imagem for recebida, OLHE A IMAGEM PRIMEIRO.

Você deve:

1. Identificar o aplicativo ou ambiente visível.
2. Identificar a janela ou conteúdo principal.
3. Ler textos visíveis.
4. Identificar código quando existir.
5. Identificar erros quando existirem.
6. Identificar exercícios quando existirem.
7. Identificar gráficos, tabelas e elementos relevantes.
8. Responder à pergunta específica do usuário.
9. Informar quando algo não puder ser identificado.

FORMATO:

O QUE VEJO:
Descrição objetiva do conteúdo visual.

CONTEÚDO:
Texto, código, erro, exercício, gráfico ou outros elementos relevantes.

ANÁLISE:
Resposta direta à pergunta do usuário.

IMPORTANTE:

Se o usuário perguntou sobre um monitor específico,
analise somente a imagem daquele monitor.

Não invente conteúdo.

Não diga que analisou uma tela se nenhuma imagem foi realmente recebida.

Se a imagem não estiver disponível ou estiver ilegível,
responda:

"Não consegui analisar a imagem recebida."
""".strip()


# ============================================================================
# EXPRESSÕES
# ============================================================================


_SCREEN_ERROR_RE = re.compile(
    r"\b("
    r"erro|bug|exception|traceback|error|crash|falha|"
    r"mensagem de erro|erro do sistema"
    r")\b",
    re.IGNORECASE,
)


_SCREEN_CODE_RE = re.compile(
    r"\b("
    r"código|codigo|code|programa|script|"
    r"função|funcao|class|def|import|from|"
    r"programação|programacao|fonte"
    r")\b",
    re.IGNORECASE,
)


_SCREEN_EXERCISE_RE = re.compile(
    r"\b("
    r"exerc\w*|questão|questao|problema|atividade|"
    r"prova|lista|resolva|responder|enunciado"
    r")\b",
    re.IGNORECASE,
)


_SCREEN_VERBS_RE = re.compile(
    r"\b("
    r"leia|ler|leitura|"
    r"descreva|descrever|"
    r"explique|explicar|"
    r"analise|analisar|"
    r"olhe|olhar|"
    r"observe|observar|"
    r"verifique|verificar|"
    r"veja|ver|"
    r"mostre|mostrar|"
    r"identifique|identificar|"
    r"interprete|interpretar"
    r")\b",
    re.IGNORECASE,
)


_SCREEN_REFERENCE_RE = re.compile(
    r"\b("
    r"tela|telas|"
    r"monitor|monitores|"
    r"desktop|"
    r"área de trabalho|area de trabalho|"
    r"screen"
    r")\b",
    re.IGNORECASE,
)


# ============================================================================
# EXTRAÇÃO DE MONITOR
# ============================================================================


def _normalize_message(message: str) -> str:
    """Normaliza texto para análise."""

    if not message:
        return ""

    return " ".join(
        str(message)
        .strip()
        .lower()
        .split()
    )


def extract_monitor_id(message: str) -> int | None:
    """
    Extrai explicitamente o monitor solicitado.

    Exemplos aceitos:

        monitor 0
        monitor 1
        monitor 2
        monitor número 2
        monitor numero 2
        tela 0
        tela 1
        tela 2
        monitor nº 2
        monitor n 2
        segundo monitor
        terceiro monitor
        primeira tela
        segunda tela
        terceira tela

    Retorna None quando o usuário não especificou monitor.
    """

    text = _normalize_message(message)

    if not text:
        return None

    # ------------------------------------------------------------------
    # Forma numérica
    # ------------------------------------------------------------------

    numeric_patterns = (
        r"\bmonitor\s*(?:n[ºo°]?\s*)?(\d+)\b",
        r"\bmonitores\s*(?:n[ºo°]?\s*)?(\d+)\b",
        r"\btela\s*(?:n[ºo°]?\s*)?(\d+)\b",
        r"\btelas\s*(?:n[ºo°]?\s*)?(\d+)\b",
        r"\bscreen\s*(?:n[ºo°]?\s*)?(\d+)\b",
    )

    for pattern in numeric_patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            try:
                return int(match.group(1))
            except (TypeError, ValueError):
                pass

    # ------------------------------------------------------------------
    # Forma "monitor número 2"
    # ------------------------------------------------------------------

    match = re.search(
        r"\b(?:monitor|tela)\s+"
        r"(?:de\s+)?"
        r"(?:número|numero|n[ºo°]?)\s*"
        r"(\d+)\b",
        text,
        re.IGNORECASE,
    )

    if match:
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            pass

    # ------------------------------------------------------------------
    # Números ordinais
    # ------------------------------------------------------------------

    ordinal_map = {
        "primeiro": 0,
        "primeira": 0,
        "segundo": 1,
        "segunda": 1,
        "terceiro": 2,
        "terceira": 2,
        "quarto": 3,
        "quarta": 3,
        "quinto": 4,
        "quinta": 4,
        "sexto": 5,
        "sexta": 5,
    }

    ordinal_pattern = (
        r"\b(primeiro|primeira|segundo|segunda|"
        r"terceiro|terceira|quarto|quarta|"
        r"quinto|quinta|sexto|sexta)"
        r"\s+(?:monitor|monitores|tela|telas)\b"
    )

    match = re.search(
        ordinal_pattern,
        text,
        re.IGNORECASE,
    )

    if match:
        return ordinal_map.get(match.group(1).lower())

    # ------------------------------------------------------------------
    # Forma "monitor é o segundo"
    # ------------------------------------------------------------------

    reverse_ordinal_pattern = (
        r"\b(?:monitor|tela)\b.*?\b"
        r"(primeiro|primeira|segundo|segunda|"
        r"terceiro|terceira|quarto|quarta|"
        r"quinto|quinta|sexto|sexta)\b"
    )

    match = re.search(
        reverse_ordinal_pattern,
        text,
        re.IGNORECASE,
    )

    if match:
        return ordinal_map.get(match.group(1).lower())

    return None


# ============================================================================
# DETECÇÃO DE INTENÇÃO
# ============================================================================


def detect_vision_intent(
    message: str,
) -> VisionIntent:
    """
    Detecta a intenção visual da mensagem.

    A ordem é deliberada:
        erro
        código
        exercício
        leitura/análise
        pergunta sobre tela
        descrição
    """

    text = _normalize_message(message)

    if not text:
        return VisionIntent.SCREEN_DESCRIBE

    # Erro tem prioridade.
    if _SCREEN_ERROR_RE.search(text):
        return VisionIntent.SCREEN_ERROR

    # Código.
    if _SCREEN_CODE_RE.search(text):
        return VisionIntent.SCREEN_CODE

    # Exercício.
    if _SCREEN_EXERCISE_RE.search(text):
        return VisionIntent.SCREEN_EXERCISE

    # Pedido explícito de leitura/análise.
    if _SCREEN_VERBS_RE.search(text):
        return VisionIntent.SCREEN_READ

    # Perguntas explícitas sobre tela/monitor.
    if (
        "o que" in text
        and _SCREEN_REFERENCE_RE.search(text)
    ):
        return VisionIntent.SCREEN_QUESTION

    # Referência direta à tela.
    if _SCREEN_REFERENCE_RE.search(text):
        return VisionIntent.SCREEN_QUESTION

    return VisionIntent.SCREEN_DESCRIBE


# ============================================================================
# CLASSIFICAÇÃO COMPLETA
# ============================================================================


def build_vision_request(
    message: str,
    *,
    session_id: str | None = None,
    monitor_id: int | None = None,
    region: dict | None = None,
    camera_image_b64: str | None = None,
) -> VisionRequest:
    """
    Constrói uma VisionRequest completa.

    Se monitor_id for informado explicitamente pelo chamador,
    ele tem prioridade.

    Caso contrário, tentamos extrair da mensagem.
    """

    text = _normalize_message(message)

    # Câmera explicitamente informada.
    if camera_image_b64:
        return VisionRequest(
            message=message,
            monitor_id=None,
            region=region,
            camera_image_b64=camera_image_b64,
            intent=VisionIntent.CAMERA,
            session_id=session_id,
            explicit_monitor=False,
        )

    detected_monitor = extract_monitor_id(text)

    explicit_monitor = detected_monitor is not None

    final_monitor = (
        monitor_id
        if monitor_id is not None
        else detected_monitor
    )

    # Se o chamador passou monitor_id, consideramos explícito.
    if monitor_id is not None:
        explicit_monitor = True

    intent = detect_vision_intent(text)

    return VisionRequest(
        message=message,
        monitor_id=final_monitor,
        region=region,
        camera_image_b64=None,
        intent=intent,
        session_id=session_id,
        explicit_monitor=explicit_monitor,
    )


# ============================================================================
# NOTAS DE IMAGEM
# ============================================================================


def build_image_note(
    camera: bool,
    monitor=None,
    size=None,
) -> str:
    """
    Nota explicativa sobre a origem da imagem.
    """

    if camera:
        return (
            "[IMAGEM ANEXADA — CÂMERA]\n"
            "\n"
            "A imagem foi capturada pela câmera.\n"
            "Analise visualmente a imagem antes de responder.\n"
            "Não dê saudação.\n"
        )

    monitor_text = (
        f"monitor {monitor}"
        if monitor is not None
        else "monitor não especificado"
    )

    dimension_text = ""

    if size:
        dimension_text = (
            f" ({size[0]}x{size[1]})"
        )

    return (
        "[IMAGEM ANEXADA — CAPTURA REAL DE TELA]\n"
        f"Origem: {monitor_text}{dimension_text}\n"
        "\n"
        "INSTRUÇÕES OBRIGATÓRIAS:\n"
        "1. Analise a imagem antes de responder.\n"
        "2. Identifique o conteúdo realmente visível.\n"
        "3. Leia textos, código, exercícios e erros.\n"
        "4. Responda à pergunta original.\n"
        "5. Não dê saudação.\n"
        "6. Não invente conteúdo.\n"
    )


# ============================================================================
# OCR
# ============================================================================


def decide_ocr_block(
    ocr_text: str | None,
) -> str | None:
    """
    Retorna OCR somente quando houver conteúdo suficiente.
    """

    if not ocr_text:
        return None

    texto = str(ocr_text).strip()

    if len(texto) < MIN_OCR_CHARS:
        return None

    if len(texto) > MAX_OCR_CHARS:
        texto = (
            texto[:MAX_OCR_CHARS]
            + "\n[…] OCR truncado"
        )

    return (
        "TEXTO DETECTADO POR OCR\n"
        "\n"
        "O OCR é uma evidência auxiliar da imagem.\n"
        "Verifique visualmente antes de confiar em conteúdo ambíguo.\n"
        "\n"
        f"{texto}"
    )


# ============================================================================
# JANELA ATIVA
# ============================================================================


def format_window_note(
    window: dict | None,
) -> str | None:
    """
    Formata informações da janela ativa.
    """

    if not window:
        return None

    app = window.get("app")

    title = window.get("title")

    partes = []

    if app:
        partes.append(
            f"aplicativo: {app}"
        )

    if title:
        partes.append(
            f"janela: {title}"
        )

    if not partes:
        return None

    return (
        "(Janela ativa no momento da captura — "
        + "; ".join(partes)
        + ".)"
    )


# ============================================================================
# VALIDAÇÃO
# ============================================================================


def validate_monitor_id(
    monitor_id: int | None,
) -> bool:
    """
    Validação básica do identificador.

    A existência real do monitor deve ser validada pelo ScreenManager.
    """

    if monitor_id is None:
        return False

    try:
        value = int(monitor_id)
    except (TypeError, ValueError):
        return False

    return value >= 0


# ============================================================================
# DEBUG
# ============================================================================


def describe_vision_request(
    request: VisionRequest,
) -> dict[str, Any]:
    """
    Representação segura da solicitação visual para logs/debug.

    Não inclui imagem nem base64.
    """

    return {
        "intent": request.intent.value,
        "monitor_id": request.monitor_id,
        "explicit_monitor": request.explicit_monitor,
        "has_region": request.region is not None,
        "has_camera_image": bool(
            request.camera_image_b64
        ),
        "session_id": request.session_id,
        "message": request.message,
    }
