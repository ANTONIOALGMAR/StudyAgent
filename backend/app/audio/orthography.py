"""Normalização ortográfica da transcrição (pós-STT) para PT-BR.

Melhora a ortografia/pontuação das perguntas faladas antes de virarem
comando ou mensagem de chat:
- Maiúscula inicial e pontuação final correta (pergunta termina com "?").
- Corrige formas informais/erros comuns de digitação do ASR.
- Sem dependências externas (regras leves sobre strings).

Uso:
    fix_orthography("o que é fotossíntese") → "O que é fotossíntese?"
"""

from __future__ import annotations

import re

# Início típico de pergunta em PT-BR → garante "?" no final.
QUESTION_STARTS = (
    "o que", "que é", "qual", "quais", "quem", "como", "onde", "quando",
    "quanto", "quantos", "quantas", "por que", "porquê", "pode", "poderia",
    "podemos", "será", "seria", "do que", "de que", "em que", "para que",
)

# Inícios "moles": só marcam pergunta se houver uma palavra interrogativa
# no restante da frase ("Você sabe o que é fotossíntese?").
SOFT_QUESTION_STARTS = (
    "será que", "sera que", "você sabe", "vc sabe", "você pode", "vc pode",
    "você poderia", "você consegue", "vc consegue", "consegue",
)

# Marcas interrogativas usadas dentro da frase (com o início mole acima).
INTERROGATIVE_MARKS = (
    "o que", "qual", "quais", "quem", "como", "onde", "quando",
    "quanto", "quantos", "quantas", "por que", "que é",
)

# Palavras/frases informais (comuns na fala) → forma escrita padrão.
SPOKEN_FORMS = {
    "pra": "para",
    "pro": "para o",
    "tbm": "também",
    "tb": "também",
    "vc": "você",
    "vcs": "vocês",
    "nao": "não",
    "oq": "o que",
    "pq": "por que",
    "pf": "por favor",
    "pfv": "por favor",
    "mt": "muito",
    "cmg": "comigo",
    "blz": "beleza",
    "dps": "depois",
    "q": "que",
}


def _comeca_com(texto: str, candidatos) -> bool:
    return any(
        texto == s or texto.startswith(s + " ")
        for s in candidatos
    )


def _parece_pergunta(texto: str) -> bool:
    inicio = texto.lower().rstrip(".!?")
    # Início interrogativo clássico → sempre pergunta.
    if _comeca_com(inicio, QUESTION_STARTS):
        return True
    # Início mole ("você sabe", "será que"…) → pergunta só se tiver uma
    # marca interrogativa no restante da frase.
    if _comeca_com(inicio, SOFT_QUESTION_STARTS):
        return any(marca in inicio for marca in INTERROGATIVE_MARKS)
    return False


def fix_orthography(texto: str, força_pergunta: bool = False) -> str:
    """Aplica correções ortográficas/heurísticas a uma transcrição PT-BR.

    ``força_pergunta=True`` (ex.: entonação ascendente detectada no áudio)
    garante "?" no final mesmo sem palavra interrogativa na frase.
    """
    if not texto or not texto.strip():
        return ""

    texto = texto.replace("aham", "sim").replace("uhum", "sim")

    # Formas informais → standard (palavra inteira, com fronteira).
    partes = texto.split()
    partes = [SPOKEN_FORMS.get(p.lower(), p) for p in partes]
    texto = " ".join(partes)

    # Espaços duplicados/estranhos.
    texto = re.sub(r"\s+", " ", texto).strip()

    # Maiúscula inicial.
    if texto and texto[0].islower():
        texto = texto[0].upper() + texto[1:]

    # Pontuação final: uma única, e "?" para perguntas.
    texto = re.sub(r"[?!.]+$", "", texto).rstrip()
    if força_pergunta or _parece_pergunta(texto):
        texto += "?"
    elif texto:
        texto += "."

    return texto


__all__ = ["fix_orthography"]

