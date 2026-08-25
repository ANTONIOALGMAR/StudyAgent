import re
from pathlib import Path

from pypdf import PdfReader

WORD_RE = re.compile(r"\w{4,}", re.UNICODE)

DIGEST_SLICE_CHARS = 9000

_DIGEST_PROMPT = """Trecho de um documento de estudo (parte {i} de {n}):

{chunk}

Faça um resumo estruturado deste trecho, preservando SEMPRE nomes,
números, fórmulas, datas e definições exatas:
- Tópicos abordados
- Definições e conceitos
- Fórmulas, números e exemplos
- Questões ou exercícios citados (se houver)

Seja completo mas conciso (máx. 12 linhas)."""


def extract_pdf(path) -> tuple[int, str]:
    reader = PdfReader(str(path))
    parts = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            parts.append(f"[página {i + 1}]\n{text.strip()}")
    return len(reader.pages), "\n\n".join(parts)


def _words(text: str) -> set:
    return set(w.lower() for w in WORD_RE.findall(text))


def _split_slices(text: str, size: int = DIGEST_SLICE_CHARS) -> list[str]:
    if len(text) <= size:
        return [text]
    pages = re.split(r"\n\n(?=\[página )", text)
    slices: list[str] = []
    current = ""
    for page in pages:
        if current and len(current) + len(page) > size:
            slices.append(current)
            current = page
        else:
            current = f"{current}\n\n{page}" if current else page
    if current.strip():
        slices.append(current)
    return slices


def build_digest(text: str, chat_fn, progress=None) -> str:
    """Resume o documento inteiro em passes (map-reduce).

    Retorna um dossiê compacto com tudo que há de relevante no documento,
    mesmo em PDFs grandes. `chat_fn` recebe uma string e devolve texto.
    """
    slices = _split_slices(text)
    partials = []
    for i, chunk in enumerate(slices):
        if progress:
            progress(i + 1, len(slices))
        out = chat_fn(
            _DIGEST_PROMPT.format(i=i + 1, n=len(slices), chunk=chunk[:9500])
        )
        partials.append(f"[Parte {i + 1}/{len(slices)}]\n{out.strip()}")
    return "\n\n".join(partials)


def retrieve_relevant(question: str, text: str, max_chars=16000) -> str:
    if len(text) <= max_chars:
        return text
    chunks = [c for c in re.split(r"\n\n(?=\[página )|\n\n", text) if c.strip()]
    if not chunks:
        return text[:max_chars]
    qwords = _words(question)
    scored = sorted(
        enumerate(chunks),
        key=lambda item: -len(qwords & _words(item[1])),
    )
    chosen: list[str] = []
    budget = max_chars
    for _, chunk in scored:
        if budget <= 0:
            break
        take = chunk[:budget]
        if budget < len(chunk):
            cut = take.rfind(". ")
            if cut > budget // 2:
                take = take[: cut + 1]
        chosen.append(take)
        budget -= len(take)
    return "\n\n[…]\n\n".join(chosen)


def load_document_text(path: Path) -> tuple[int, str]:
    suffix = path.suffix.lower()
    txt_path = path.with_suffix(".txt")
    if txt_path.exists():
        pages = 0
        text = txt_path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            try:
                pages = len(PdfReader(str(path)).pages)
            except Exception:
                pages = 0
        return pages, text
    if suffix == ".pdf":
        return extract_pdf(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    return 1, text
