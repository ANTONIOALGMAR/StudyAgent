import re
from pathlib import Path

from pypdf import PdfReader

WORD_RE = re.compile(r"\w{4,}", re.UNICODE)


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


def retrieve_relevant(question: str, text: str, max_chars=7000) -> str:
    if len(text) <= max_chars:
        return text
    chunks = [c for c in text.split("\n\n") if c.strip()]
    if not chunks:
        return text[:max_chars]
    qwords = _words(question)
    scored = sorted(
        enumerate(chunks),
        key=lambda item: -len(qwords & _words(item[1])),
    )
    chosen: list[tuple[int, str]] = []
    budget = max_chars
    for idx, chunk in scored:
        if budget <= 0:
            break
        take = chunk[:budget]
        chosen.append((idx, take))
        budget -= len(take)
    chosen.sort(key=lambda item: item[0])
    return "\n\n[...]\n\n".join(c for _, c in chosen)


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
