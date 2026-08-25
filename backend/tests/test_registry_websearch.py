from app.core.tool_registry import all_schemas, get, names, reset_registry, tool
from app.tools.web_search import _decode_bing_url, format_results, html_to_text

# ── Tool Registry ────────────────────────────────────────────────────────────


def test_registro_e_schema():
    reset_registry()

    @tool(
        name="dummy",
        description="ferramenta de teste",
        parameters={"x": {"type": "string"}},
        permission="internet",
        required=["x"],
    )
    def dummy(args):
        return "ok"

    assert "dummy" in names()
    t = get("dummy")
    schema = t.schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "dummy"
    assert t.permission == "internet"
    assert t.handler({"x": "1"}) == "ok"


def test_ferramentas_padrao_registradas():
    # registered_tools é importado pelo agent; garante que o import carrega tudo
    import app.core.registered_tools  # noqa: F401

    for nome in ("web_search", "open_url", "calculate"):
        assert get(nome) is not None, f"faltou registrar {nome}"
    schemas = all_schemas()
    assert len(schemas) >= 3


# ── web_search helpers ───────────────────────────────────────────────────────


def test_decode_bing_url():
    import base64

    real = "https://exemplo.com/pagina"
    b64 = base64.urlsafe_b64encode(real.encode()).decode().rstrip("=")
    assert _decode_bing_url(f"https://www.bing.com/ck/a?!&&p=x&u=a1{b64}") == real


def test_decode_bing_url_sem_redirect_devolve_original():
    assert _decode_bing_url("https://direto.com") == "https://direto.com"


def test_html_to_text_remove_script():
    html = "<html><head><style>.a{}</style><script>evil()</script></head><body><p>Olá mundo</p></body></html>"
    texto = html_to_text(html)
    assert "Olá" in texto
    assert "evil" not in texto
    assert ".a{}" not in texto


def test_format_results_numerado():
    out = format_results(
        [
            {"title": "A", "url": "https://a", "snippet": "sa"},
            {"title": "B", "url": "https://b", "snippet": "sb"},
        ]
    )
    assert "[1] A" in out and "[2] B" in out and "https://b" in out
