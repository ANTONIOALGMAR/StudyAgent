"""Palavra de acordar por transcrição: normaliza o texto e separa o
comando depois do gatilho ("ei study, o que é fotossíntese?" →
"o que é fotossíntese?").

Funciona sobre a saída do STT — sem modelo extra de wake word.
"""

import re
import unicodedata

WAKE_PREFIXES = (
    "ei study",
    "ei studi",
    "ei studie",
    "hey study",
    "ok study",
    "estude agente",
    "study agent",
)

WAKE_TOKENS = ("study", "studie", "studi")


def normalize(texto: str) -> str:
    valor = unicodedata.normalize("NFKD", texto)
    valor = "".join(c for c in valor if not unicodedata.combining(c))
    return " ".join(valor.lower().split())


def _acordou(norm: str) -> bool:
    if any(norm.startswith(p) for p in WAKE_PREFIXES):
        return True
    primeira = norm.split(",", 1)[0]
    return any(primeira == tok or primeira.startswith(tok + " ") for tok in WAKE_TOKENS)


def extract_command(texto: str) -> str | None:
    """Comando após a palavra de acordar (com acentos originais), ou None."""
    if not texto or not _acordou(normalize(texto)):
        return None
    # corta no primeiro separador do texto ORIGINAL para não perder acentos
    m = re.search(r"[,.!?;:]\s*(.+)", texto, flags=re.S)
    if m:
        return m.group(1).strip() or None
    # sem pontuação: descarta as mesmas palavras do gatilho na frase crua
    n_gatilho = len(normalize(texto).split(",", 1)[0].split())
    partes = texto.split(None, n_gatilho)
    if len(partes) != n_gatilho + 1:
        return None  # só o gatilho, sem comando
    return partes[-1].strip(" ,.!?;:") or None


__all__ = ["normalize", "extract_command", "WAKE_PREFIXES", "WAKE_TOKENS"]
