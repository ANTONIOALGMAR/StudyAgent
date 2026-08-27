"""Registro das ferramentas padrão no Tool Registry V2.

Handlers são puros (recebem args, devolvem texto). A checagem de permissão
fica no loop do agente — assim o erro de permissão é formatado num lugar só.
"""

from ..tools.calculator import calculate
from ..tools.web_search import distill_page, fetch_page, search
from .tool_registry import tool

_SEARCH_PAGE_CHARS = 4500


@tool(
    name="web_search",
    description=(
        "Pesquisa na internet informações atuais, fatos verificáveis, "
        "notícias, dados e respostas que o modelo pode não conhecer. "
        "Use SEMPRE que precisar de precisão (resultados esportivos, "
        "cotações, eventos recentes). Monte a query com termos "
        "diferenciadores: nome completo, contexto e ano "
        "(ex.: 'Palmeiras futebol São Paulo resultado Brasileirão 2026' "
        "em vez de só 'Palmeiras')."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "Termos de busca em português, específicos e objetivos",
        }
    },
    permission="internet",
    required=["query"],
    version="1.0.0",
    tags=["search", "internet", "info"],
)
def web_search_tool(args: dict) -> str:
    results = search(str(args.get("query", "")))
    parts = []
    for r in results[:5]:
        part = f"[{r['title']}]({r['url']})\n{r['snippet'][:250]}"
        try:
            page = fetch_page(r["url"], chars=_SEARCH_PAGE_CHARS)
            if len(page) < 350:
                continue  # página JS sem texto útil
            distilled = distill_page(page)
            if distilled and "NADA CLARO" not in distilled:
                part += f"\nTrechos objetivos da página:\n{distilled}"
            else:
                part += f"\nTrechos da página:\n{page[:1200]}"
        except Exception:
            pass
        parts.append(part)
    return (
        "\n\n---\n\n".join(parts)
        or "Nenhum resultado encontrado na pesquisa. "
        "Tente outros termos ou admita que não sabe."
    )


@tool(
    name="open_url",
    description=(
        "Abre uma página da internet e retorna o texto completo. "
        "Use depois do web_search quando os resumos forem insuficientes "
        "(placar de jogos, valores atuais, detalhes de notícias)."
    ),
    parameters={
        "url": {
            "type": "string",
            "description": "URL completa da página, começando com http(s)://",
        }
    },
    permission="internet",
    required=["url"],
    version="1.0.0",
    tags=["web", "internet", "fetch"],
)
def open_url_tool(args: dict) -> str:
    return fetch_page(str(args.get("url", "")))


@tool(
    name="calculate",
    description=(
        "Calcula uma expressão matemática com precisão "
        "(+, -, *, /, //, %, **, parênteses). Use em vez de calcular de cabeça."
    ),
    parameters={
        "expression": {"type": "string", "description": "Expressão, ex.: (3/4)*100"}
    },
    required=["expression"],
    version="1.0.0",
    tags=["math", "calculate"],
)
def calculate_tool(args: dict) -> str:
    return str(calculate(str(args.get("expression", ""))))
