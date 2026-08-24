import requests

WIKIPEDIA_API = "https://pt.wikipedia.org/w/api.php"


def search(query: str, max_results: int = 5) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []
    results = _ddg(query, max_results)
    if not results:
        results = _wikipedia(query)
    return results


def _ddg(query: str, max_results: int) -> list[dict]:
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            raw = list(
                ddgs.text(query, region="br-pt", max_results=max_results)
            )
        return [
            {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in raw
            if r.get("href")
        ]
    except Exception:
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
            snippet = item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")
            url = f"https://pt.wikipedia.org/wiki/{title.replace(' ', '_')}"
            out.append({"title": title, "url": url, "snippet": snippet})
        return out
    except Exception:
        return []


def format_results(results: list[dict]) -> str:
    if not results:
        return ""
    blocks = [
        f"[{i + 1}] {r['title']}\nFonte: {r['url']}\n{r['snippet']}"
        for i, r in enumerate(results)
    ]
    return "\n\n".join(blocks)
