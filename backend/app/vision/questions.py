"""Detecção de questões em texto lido por OCR (tela, foto ou imagem).

O objetivo é transformar o texto solto que vem do OCR em uma lista
estruturada de questões — com enunciado e alternativas quando existirem —
para que o modelo de visão responda exatamente o que foi pedido, e para
que a resposta possa ser apresentada item a item.

A heurística é deliberadamente conservadora: só vira questão o que tem
numeração de item ou pergunta explícita, com enunciado com tamanho
mínimo. Texto corrido (parágrafos de aula, menus, logs) não é tratado
como questão.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

# ============================================================================
# LIMITES
# ============================================================================

MAX_QUESTIONS = 20
MAX_STEM_CHARS = 400
MAX_OPTION_CHARS = 200

MIN_STEM_CHARS = 8
MIN_OPTION_TEXT = 1


# ============================================================================
# EXPRESSÕES
# ============================================================================

_QUESTION_START_RE = re.compile(
    r"^\s*(?:"
    r"quest[ãa]o\s*(?:n[ºo°]?\s*)?(?P<q1>[0-9]{1,3})"  # Questão 3 / Questao nº3
    r"|q\s*\.?\s*(?P<q2>[0-9]{1,3})"  # Q3 / Q.3
    r"|item\s*(?P<q3>[0-9]{1,3})"  # Item 3
    r"|exerc[íi]cio\s*(?P<q4>[0-9]{1,3})"  # Exercício 3
    r"|(?P<q5>[0-9]{1,3})\s*[)\.\-–:]"  # 3) / 3. / 3- / 3:
    r")\s*(?P<resto>.*)$",
    re.IGNORECASE | re.UNICODE,
)

_OPTION_RE = re.compile(
    r"^\s*(?:"
    r"\(\s*(?P<p1>[a-eA-E])\s*\)\s*"  # ( a )
    r"|\[\s*(?P<p2>[a-eA-E])\s*\]\s*"  # [ a ]
    r"|(?P<p3>[a-eA-E])\s*[)\.\:\-–]\s*"  # a) a. a- a:
    r")(?P<texto>.+)$",
    re.UNICODE,
)

# Formato usado por ambientes de avaliação online: "Opção A" (ou
# "Alternativa A") seguido do texto da opção na mesma linha ou na próxima.
_OPTION_LABEL_RE = re.compile(
    r"^\s*(?:op[çc][ãa]o|alternativa)\s+"
    r"(?P<letra>[a-eA-E])\s*[:\-.)]?\s*(?P<texto>.*)$",
    re.IGNORECASE | re.UNICODE,
)

_QUESTION_WORD_RE = re.compile(
    r"\b(qual|quais|quanto|quanta|quando|onde|quem|como|por que|porque|"
    r"conforme|determine|calcule|assinale|marque|escolha|"
    r"verdadeiro|falso|julgue|justifique|indique|analise|descreva)\b",
    re.IGNORECASE | re.UNICODE,
)

_TRUE_FALSE_RE = re.compile(
    r"\(\s*\)\s*(verdadeiro|falso)|"
    r"\b(v|f)\s*(ou|e)\s*(v|f)\b|"
    r"justifique\s+(o\s+)?(verdadeiro|falso)",
    re.IGNORECASE | re.UNICODE,
)

_JUNK_LINE_RE = re.compile(
    r"^[\s\W_]*$|^page\s+\d+|^--+\s*\d+\s*--+$",
    re.IGNORECASE | re.UNICODE,
)


# ============================================================================
# MODELO
# ============================================================================


def _normalize(text: str) -> str:
    """Minúsculas + espaços colapsados — base do fingerprint."""

    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def text_fingerprint(text: str | None) -> str:
    """Identidade estável do texto da tela (dedupe do loop ao vivo)."""

    return hashlib.sha1(_normalize(text).encode("utf-8", "ignore")).hexdigest()


@dataclass
class DetectedQuestion:
    """Uma questão lida do texto (ou da imagem via OCR)."""

    label: str = ""

    stem: str = ""

    options: dict[str, str] = field(default_factory=dict)

    kind: str = "aberta"

    source_line: int = 0

    @property
    def fingerprint(self) -> str:
        """Identidade estável da questão (rótulo + enunciado).

        Usada pelo cliente do loop ao vivo para resolver cada questão
        apenas uma vez, mesmo que ela continue na tela entre varreduras.

        A normalização ignora pontuação além de caixa/espaços: assim um
        ruído pequeno do OCR (vírgula extra, quebra de linha) não faz a
        mesma questão parecer nova.
        """

        base = re.sub(r"[^\w]+", "", f"{self.label}|{self.stem}".lower())[:120]
        return hashlib.sha1(base.encode("utf-8", "ignore")).hexdigest()

    @property
    def is_multiple_choice(self) -> bool:
        """Indica se há alternativas para marcar."""

        return len(self.options) >= 2

    @property
    def is_true_false(self) -> bool:
        """Indica questão de verdadeiro ou falso."""

        return self.kind == "verdadeiro_falso"

    def option_lines(self) -> str:
        """Alternativas formatadas para o prompt."""

        return "\n".join(
            f"   {letra}) {texto}" for letra, texto in self.options.items()
        )

    def to_dict(self) -> dict:
        """Serializa para JSON."""

        return {
            "label": self.label,
            "stem": self.stem,
            "options": dict(self.options),
            "kind": self.kind,
            "multiple_choice": self.is_multiple_choice,
            "fingerprint": self.fingerprint,
        }


# ============================================================================
# DETECÇÃO
# ============================================================================


def detect_questions(
    text: str | None,
    *,
    max_questions: int = MAX_QUESTIONS,
) -> list[DetectedQuestion]:
    """Encontra questões no texto vindo do OCR.

    Reconhece três formatos:
    - numeradas: "Questão 3", "3)", "3.", "Item 3";
    - com alternativas: "a) ...", "(b) ...", "c. ...";
    - sem numeração: enunciado terminado em interrogação.

    Devolve lista vazia quando o texto não parece conter questões.
    """

    if not text:
        return []

    linhas = _linhas_utilis(text)

    if len(linhas) < 2:
        return []

    blocos: list[tuple[str, list[str], int]] = []
    atual: tuple[str, list[str], int] | None = None

    for numero, linha in enumerate(linhas):
        match = _QUESTION_START_RE.match(linha)

        if match:
            numero_item = (
                match.group("q1")
                or match.group("q2")
                or match.group("q3")
                or match.group("q4")
                or match.group("q5")
            )
            resto = match.group("resto").strip().lstrip("-–—:;. ")
            if atual is not None:
                blocos.append(atual)
            atual = (numero_item or "", [resto] if resto else [], numero)
            continue

        # Enunciado novo sem numeração: "Qual a capital do Brasil?"
        if (
            atual is not None
            and not atual[0]
            and linha.rstrip().endswith("?")
            and _QUESTION_WORD_RE.search(linha)
        ):
            blocos.append(atual)
            atual = ("", [linha], numero)
            continue

        if atual is not None:
            atual[1].append(linha)
        else:
            atual = ("", [linha], numero)

    if atual is not None:
        blocos.append(atual)

    questoes: list[DetectedQuestion] = []
    vistos: set[str] = set()

    for rotulo, corpo, numero in blocos:
        questao = _montar_questao(rotulo, corpo, numero)

        if not questao:
            continue

        # Sem numeração, só aceitamos o bloco se ele realmente for uma
        # pergunta — texto corrido de aula não entra como questão.
        if not rotulo and not _parece_questao(questao):
            continue

        chave = re.sub(r"\W+", "", questao.stem.lower())[:80]
        if chave in vistos:
            continue

        vistos.add(chave)
        questoes.append(questao)

        if len(questoes) >= max_questions:
            break

    return _desambiguar_rotulos(questoes)


def _linhas_utilis(text: str) -> list[str]:
    """Normaliza quebras de linha e remove linhas vazias/ruído."""

    texto = text.replace("\r\n", "\n").replace("\r", "\n")

    return [
        linha.strip()
        for linha in texto.split("\n")
        if linha.strip() and not _JUNK_LINE_RE.match(linha)
    ]


def _montar_questao(
    rotulo: str,
    corpo: list[str],
    numero: int,
) -> DetectedQuestion | None:
    """Constrói uma questão a partir das linhas do bloco."""

    alternativas: dict[str, str] = {}
    enunciado: list[str] = []

    # No formato "Opção A" (ambientes de avaliação online) o rótulo pode
    # vir sozinho com o texto da opção na linha seguinte.
    letra_pendente: str | None = None

    for linha in corpo:
        m_label = _OPTION_LABEL_RE.match(linha)
        if m_label is not None:
            letra = m_label.group("letra").lower()
            texto = m_label.group("texto").strip()[:MAX_OPTION_CHARS]
            if texto:
                if letra not in alternativas:
                    alternativas[letra] = texto
                letra_pendente = None
            else:
                letra_pendente = letra
            continue

        if letra_pendente is not None:
            texto = linha[:MAX_OPTION_CHARS]
            if texto and letra_pendente not in alternativas:
                alternativas[letra_pendente] = texto
            letra_pendente = None
            continue

        match = _OPTION_RE.match(linha)
        if match:
            letra = (
                match.group("p1")
                or match.group("p2")
                or match.group("p3")
            ).lower()
            texto = match.group("texto").strip()[:MAX_OPTION_CHARS]
            if texto and letra not in alternativas:
                alternativas[letra] = texto
            continue
        enunciado.append(linha)

    stem = " ".join(enunciado).strip()

    # Alternativas detectadas deixam o resto como continuação do enunciado
    # quando o OCR embaralhou a ordem (ex.: "a) 1" antes do enunciado).
    if alternativas and stem:
        match = _OPTION_RE.match(stem)
        if match:
            stem = match.group("texto").strip()

    if not stem:
        if len(alternativas) >= 2:
            stem = _stem_de_alternativas(alternativas)
        else:
            return None

    stem = stem[:MAX_STEM_CHARS]

    if len(stem) < MIN_STEM_CHARS and len(alternativas) < 2:
        return None

    if _sao_verdadeiro_falso(stem, alternativas):
        tipo = "verdadeiro_falso"
    elif len(alternativas) >= 2:
        tipo = "multipla_escolha"
    else:
        tipo = "aberta"

    return DetectedQuestion(
        label=rotulo,
        stem=stem,
        options=alternativas,
        kind=tipo,
        source_line=numero,
    )


def _parece_questao(questao: DetectedQuestion) -> bool:
    """Diz se um bloco sem numeração ainda assim é uma pergunta."""

    if questao.is_multiple_choice:
        return True

    if questao.stem.rstrip().endswith("?"):
        return True

    return bool(_QUESTION_WORD_RE.search(questao.stem))


def _stem_de_alternativas(alternativas: dict[str, str]) -> str:
    """Reconstrói um enunciado mínimo quando só há alternativas."""

    return " ".join(alternativas.values())[:MAX_STEM_CHARS]


def _sao_verdadeiro_falso(stem: str, alternativas: dict[str, str]) -> bool:
    """Detecta questão de verdadeiro/falso."""

    if _TRUE_FALSE_RE.search(stem):
        return True

    letras = set(alternativas)
    textos = [t.lower() for t in alternativas.values()]

    if letras and letras <= {"v", "f"}:
        return True

    return (
        len(textos) >= 2
        and any("verdadeiro" in t for t in textos)
        and any("falso" in t for t in textos)
    )


def _desambiguar_rotulos(questoes: list[DetectedQuestion]) -> list[DetectedQuestion]:
    """Garante rótulos únicos e sequenciais para o aluno identificar."""

    usados: set[str] = set()
    proximo = 1

    for questao in questoes:
        rotulo = questao.label.strip()

        if not rotulo or rotulo in usados:
            while str(proximo) in usados:
                proximo += 1
            rotulo = str(proximo)
            proximo += 1

        usados.add(rotulo)
        questao.label = rotulo

    return questoes


# ============================================================================
# PROMPT
# ============================================================================

ANSWER_FORMAT = """
Responda no formato, uma linha por questão:

<rótulo>) <letra da alternativa, se houver> — <resposta curta> — <justificativa em 1 frase>

Exemplo:
1) B) 12 — porque 3 + 4 + 5 = 12.

Regras:
- Use o rótulo exatamente como aparece acima (1, 2, 3...).
- Se houver alternativas, comece pela LETRA maiúscula seguida de ")".
- Seja acertivo: marque UMA alternativa e diga a resposta com segurança.
- Não chute: antes de decidir, avalie cada alternativa e verifique por que
  as demais estão erradas; só marque uma letra quando tiver certeza.
- NUNCA use justificativa vazia como "a resposta está correta, conforme o
  enunciado" — a justificativa deve citar o conteúdo específico da questão.
- Nunca inverter/autorizar a marcação por pura eliminação sem justificativa.
- Se a questão estiver ilegível ou ambígua, escreva "incerta" no lugar da
  letra e da resposta — não adivinhe.
- Não repita o enunciado inteiro.
- Não invente questões que não estão na lista.
""".strip()


def format_questions(questions: list[DetectedQuestion]) -> str:
    """Monta o bloco de questões para o prompt."""

    if not questions:
        return ""

    partes = []

    for questao in questions:
        linha = f"{questao.label}) {questao.stem}"
        if questao.options:
            linha += "\n" + questao.option_lines()
        partes.append(linha)

    return (
        f"[QUESTÕES DETECTADAS NA IMAGEM — {len(questions)}]\n"
        + "\n\n".join(partes)
    )


def answer_instruction(questions: list[DetectedQuestion]) -> str:
    """Instrução de resposta usada quando o aluno quer as respostas."""

    if not questions:
        return ""

    return (
        "Resolva TODAS as questões listadas acima, uma por vez, "
        "identificando a resposta de cada item.\n\n"
        "Leia o enunciado e as alternativas de CADA questão e responda "
        "conforme esse contexto específico — não aplique resposta genérica. "
        "Aponte a alternativa correta com firmeza, indicando claramente a "
        "letra, e só a marque se tiver certeza; avalie por que as demais "
        "estão erradas. Se não conseguir determinar a resposta com "
        "segurança (questão ilegível ou ambígua), diga 'incerta' em vez de "
        "adivinhar.\n"
        + ANSWER_FORMAT
    )


# ============================================================================
# LEITURA DAS RESPOSTAS DO MODELO
# ============================================================================

_ANSWER_LINE_RE = re.compile(
    r"^\s*\(?([0-9]{1,3})\)?\s*(?:[)\.\-–:]\s*)?(?P<resto>.+)$",
    re.UNICODE,
)

_LETTER_ANSWER_RE = re.compile(
    r"^\s*\(?([a-eA-E])\)?\s*(?:[)\.\-–:]\s*|\s+)(?P<resto>.+)$",
    re.UNICODE,
)

_TAUTOLOGICO_RE = re.compile(
    r"resposta\s+(est[áa]?\s+)?correta\s*,?\s*"
    r"(conforme|segundo|de\s+acordo\s+com)\s+o\s+enunciado",
    re.IGNORECASE | re.UNICODE,
)


def parse_answers(
    text: str | None,
    questions: list[DetectedQuestion],
) -> list[dict]:
    """Lê a resposta do modelo e casa com as questões detectadas.

    Aceita tanto o formato combinado (rótulo, letra, justificativa) quanto
    texto corrido: o que não casar com um item é ignorado, sem inventar.
    """

    if not text or not questions:
        return []

    por_rotulo = {q.label: q for q in questions}
    respostas: dict[str, dict] = {}

    for linha in text.splitlines():
        match = _ANSWER_LINE_RE.match(linha)
        if not match:
            continue

        rotulo = match.group(1)
        resto = match.group("resto").strip()

        if not resto:
            continue

        questao = por_rotulo.get(rotulo)
        if questao is None or rotulo in respostas:
            continue

        letra = ""
        justificativa = resto

        if questao.is_multiple_choice:
            letra_match = _LETTER_ANSWER_RE.match(resto)
            if letra_match:
                letra = letra_match.group(1).upper()
                justificativa = letra_match.group("resto").strip()

        if _TAUTOLOGICO_RE.search(justificativa):
            letra = ""
            justificativa = (
                "incerta — justificativa genérica não confirma a alternativa."
            )

        respostas[rotulo] = {
            "label": rotulo,
            "answer": letra,
            "answer_text": justificativa,
        }

    return [respostas[q.label] for q in questions if q.label in respostas]


__all__ = [
    "ANSWER_FORMAT",
    "DetectedQuestion",
    "answer_instruction",
    "detect_questions",
    "format_questions",
    "parse_answers",
]
