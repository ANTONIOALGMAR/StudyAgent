import base64
import html as _html
import logging
import re
import time
from html.parser import HTMLParser

import requests

logger = logging.getLogger(__name__)

WIKIPEDIA_API = "https://pt.wikipedia.org/w/api.php"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}

MAX_PAGE_CHARS = 6000


MIN_GOOD_RESULTS = 3


def search(query: str, max_results: int = 5) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []
    results: list[dict] = []
    for attempt in range(2):
        results = _ddg(query, max_results)
        if len(results) >= MIN_GOOD_RESULTS:
            return results
        time.sleep(1.5 * (attempt + 1))
    seen = {r["url"] for r in results}
    bing = _bing(query, max_results)
    results += [r for r in bing if r["url"] not in seen]
    if len(results) >= MIN_GOOD_RESULTS:
        return results
    logger.warning("DDG+Bing insuficientes para %r; usando Wikipedia", query)
    wiki = _wikipedia(query)
    results += [r for r in wiki if r["url"] not in seen]
    return results


def _decode_bing_url(raw: str) -> str:
    match = re.search(r"u=a1([A-Za-z0-9_-]+)", raw)
    if not match:
        return raw
    b64 = match.group(1) + "=" * (-len(match.group(1)) % 4)
    try:
        decoded = base64.urlsafe_b64decode(b64).decode("utf-8", "ignore")
    except Exception:
        return raw
    return decoded if decoded.startswith("http") else raw


def _strip_tags(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment)).strip()


def _bing(query: str, max_results: int) -> list[dict]:
    try:
        resp = requests.get(
            "https://www.bing.com/search",
            params={"q": query, "setlang": "pt-BR"},
            headers=_HEADERS,
            timeout=12,
        )
        resp.raise_for_status()
        blocks = re.findall(r'<li class="b_algo".*?</li>', resp.text, re.S)
        out = []
        for block in blocks[:max_results]:
            m = re.search(
                r'<h2[^>]*><a[^>]+href="(http[^"]+)"[^>]*>(.*?)</a>', block, re.S
            )
            if not m:
                continue
            url = _html.unescape(_decode_bing_url(m.group(1)))
            title = _html.unescape(_strip_tags(m.group(2)))
            p = re.findall(r"<p[^>]*>(.*?)</p>", block, re.S)
            snippet = _html.unescape(_strip_tags(p[0])) if p else ""
            if url.startswith("http") and title:
                out.append({"title": title, "url": url, "snippet": snippet})
        return out
    except Exception as exc:
        logger.warning("Erro no Bing para %r: %s", query, exc)
        return []


def _ddg(query: str, max_results: int) -> list[dict]:
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            raw = list(ddgs.text(query, region="br-pt", max_results=max_results))
        return [
            {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in raw
            if r.get("href")
        ]
    except Exception as exc:
        logger.warning("Erro no DuckDuckGo para %r: %s", query, exc)
        return []


def _wikipedia(query: str) -> list[dict]:
    try:
        resp = requests.get(
            WIKIPEDIA_API,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 3,
            },
            timeout=10,
        )
        data = resp.json()
        out = []
        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            url = f"https://pt.wikipedia.org/wiki/{title.replace(' ', '_')}"
            snippet = item.get("snippet", "")
            snippet = re.sub(r"<[^>]+>", "", snippet)
            extract = _wiki_extract(title)
            out.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": f"{snippet}\n{extract}" if extract else snippet,
                }
            )
        return out
    except Exception as exc:
        logger.warning("Erro na Wikipedia para %r: %s", query, exc)
        return []


def _wiki_extract(title: str, chars: int = 1200) -> str:
    try:
        resp = requests.get(
            WIKIPEDIA_API,
            params={
                "action": "query",
                "prop": "extracts",
                "explaintext": 1,
                "exchars": chars,
                "titles": title,
                "format": "json",
            },
            timeout=10,
        )
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            return (page.get("extract") or "").strip()
    except Exception as exc:
        logger.warning("Erro no extract da Wikipedia (%r): %s", title, exc)
    return ""


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "header", "footer", "nav", "aside"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in ("p", "br", "li", "tr", "h1", "h2", "h3", "div"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0 and data.strip():
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def fetch_page(url: str, chars: int = MAX_PAGE_CHARS) -> str:
    url = (url or "").strip()
    if not re.match(r"^https?://", url):
        raise ValueError(f"URL inválida: {url!r}")
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")
    if "html" not in content_type and "text" not in content_type:
        return f"(conteúdo não textual: {content_type})"
    text = html_to_text(resp.text)
    if len(text) > chars:
        text = text[:chars] + "\n…[texto truncado]"
    return text or "(página sem texto legível)"


def format_results(results: list[dict]) -> str:
    if not results:
        return ""
    blocks = [
        f"[{i + 1}] {r['title']}\nFonte: {r['url']}\n{r['snippet']}"
        for i, r in enumerate(results)
    ]
    return "\n\n".join(blocks)


_DISTILL_PROMPT = """Texto extraído de uma página da web (pode conter menus e navegação misturados):

{page}

TAREFA: copie APENAS os trechos que contenham FATOS OBJETIVOS — datas,
placares, nomes próprios, números, valores — exatamente como aparecem,
sem interpretar ou completar. Uma linha por fato. Se não houver nada
objetivo, responda apenas: NADA CLARO"""


def distill_page(page_text: str) -> str:
    from ..agent.llm import chat

    out = chat(
        [{"role": "user", "content": _DISTILL_PROMPT.format(page=page_text[:3500])}]
    )
    return out.strip()
