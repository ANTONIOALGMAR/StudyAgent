"""Registro das ferramentas padrão no Tool Registry V2.

Handlers são puros (recebem args, devolvem texto). A checagem de permissão
fica no loop do agente — assim o erro de permissão é formatado num lugar só.
"""

from ..tools.calculator import calculate
from ..tools.web_search import distill_page, fetch_page, search
from ..tools.code_editor import read_file, write_file, edit_file, list_directory, search_in_files
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


@tool(
    name="read_code",
    description="Lê o conteúdo de um arquivo de código no sistema de arquivos do usuário.",
    parameters={
        "path": {"type": "string", "description": "Caminho absoluto ou relativo ao projeto do arquivo."}
    },
    permission="filesystem",
    required=["path"],
    version="1.0.0",
    tags=["code", "filesystem", "read"],
)
def read_code_tool(args: dict) -> str:
    return read_file(str(args.get("path", "")))


@tool(
    name="write_code",
    description="Cria ou sobrescreve um arquivo de código com o conteúdo fornecido.",
    parameters={
        "path": {"type": "string", "description": "Caminho do arquivo a ser escrito."},
        "content": {"type": "string", "description": "Conteúdo completo do arquivo."}
    },
    permission="filesystem",
    required=["path", "content"],
    version="1.0.0",
    tags=["code", "filesystem", "write"],
)
def write_code_tool(args: dict) -> str:
    return write_file(str(args.get("path", "")), str(args.get("content", "")))


@tool(
    name="edit_code",
    description="Edita um arquivo de código substituindo uma string específica por outra. Use para alterações pontuais.",
    parameters={
        "path": {"type": "string", "description": "Caminho do arquivo."},
        "old_string": {"type": "string", "description": "Texto exato a ser substituído."},
        "new_string": {"type": "string", "description": "Novo texto para inserir no lugar."}
    },
    permission="filesystem",
    required=["path", "old_string", "new_string"],
    version="1.0.0",
    tags=["code", "filesystem", "edit"],
)
def edit_code_tool(args: dict) -> str:
    return edit_file(str(args.get("path", "")), str(args.get("old_string", "")), str(args.get("new_string", "")))


@tool(
    name="list_files",
    description="Lista arquivos e pastas em um diretório específico.",
    parameters={
        "path": {"type": "string", "description": "Caminho do diretório para listar."}
    },
    permission="filesystem",
    required=["path"],
    version="1.0.0",
    tags=["code", "filesystem", "list"],
)
def list_files_tool(args: dict) -> str:
    files = list_directory(str(args.get("path", "")))
    return "\n".join(files) if files else "Diretório vazio ou erro ao listar."


@tool(
    name="search_code",
    description="Busca por uma string em todos os arquivos de um diretório recursivamente.",
    parameters={
        "query": {"type": "string", "description": "Texto a ser buscado."},
        "path": {"type": "string", "description": "Diretório raiz da busca."}
    },
    permission="filesystem",
    required=["query", "path"],
    version="1.0.0",
    tags=["code", "filesystem", "search"],
)
def search_code_tool(args: dict) -> str:
    results = search_in_files(str(args.get("query", "")), str(args.get("path", "")))
    if not results:
        return "Nenhuma ocorrência encontrada."
    return "\n".join([f"{r['path']} - {r['line']}" for r in results])
