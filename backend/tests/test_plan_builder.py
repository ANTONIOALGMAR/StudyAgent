"""Testes do Plan Builder — transforma pedido em plano multi-step."""

import pytest

from app.core.plan_builder import (
    PLAN_PROMPT,
    PlanStep,
    build_plan,
    extract_json,
    available_tools_prompt,
)
from app.core.tool_registry import reset_registry, tool


@pytest.fixture
def tools():
    """Registra ferramentas determinísticas para isolamento dos testes.

    O registry é global e outros testes chamam reset_registry(), então cada
    teste precisa garantir as ferramentas usadas pelo plan_builder.
    """
    reset_registry()

    @tool(name="web_search", description="Pesquisa", parameters={"query": {"type": "string"}}, required=["query"])
    def ws(args):
        return ""

    @tool(name="calculate", description="Calcula", parameters={"expression": {"type": "string"}}, required=["expression"])
    def calc(args):
        return ""

    @tool(name="open_url", description="Abre", parameters={"url": {"type": "string"}}, required=["url"])
    def ou(args):
        return ""

    yield
    reset_registry()


class TestExtractJson:
    def test_pure_json(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_json_with_noise(self):
        raw = "ok aqui vai: {\"steps\": [{\"tool\": \"x\"}]} fim"
        assert extract_json(raw) == {"steps": [{"tool": "x"}]}

    def test_invalid_returns_none(self):
        assert extract_json('{not json') is None

    def test_empty_returns_none(self):
        assert extract_json("") is None


class TestBuildPlanFromRaw:
    def test_multi_step_with_dependency(self, tools):
        r = build_plan(
            "busque e abra",
            raw='{"steps": ['
            '{"tool": "web_search", "arguments": {"query": "Palmeiras 2026"}},'
            '{"tool": "open_url", "arguments": {"url": "https://x.com"}, "depends_on": [0]}'
            "]}",
        )
        assert r.ok
        assert [s.tool for s in r.steps] == ["web_search", "open_url"]
        assert r.steps[0].depends_on == []
        assert r.steps[1].depends_on == ["0"]

    def test_unknown_tool_dropped(self, tools):
        r = build_plan(
            "x",
            raw='{"steps": [{"tool": "nao_existe", "arguments": {}},'
            '{"tool": "calculate", "arguments": {"expression": "2+2"}}]}',
        )
        assert r.ok
        assert [s.tool for s in r.steps] == ["calculate"]

    def test_missing_required_arg_dropped(self, tools):
        r = build_plan("x", raw='{"steps": [{"tool": "web_search", "arguments": {}}]}')
        assert not r.ok
        assert r.steps == []

    def test_empty_steps_means_no_tools(self, tools):
        r = build_plan("oi", raw='{"steps": []}')
        assert r.error is None
        assert not r.ok
        assert r.steps == []

    def test_invalid_json(self, tools):
        r = build_plan("x", raw="não é json")
        assert r.error is not None
        assert not r.ok

    def test_no_raw_no_llm(self, tools):
        r = build_plan("x")
        assert r.error == "Nenhuma fonte de plano fornecida"
        assert not r.ok

    def test_llm_fn_used_when_no_raw(self, tools):
        def fake_llm(prompt):
            assert "web_search" in prompt
            return '{"steps": [{"tool": "calculate", "arguments": {"expression": "3*3"}}]}'

        r = build_plan("quanto é 3*3", llm_fn=fake_llm)
        assert r.ok
        assert r.steps[0].tool == "calculate"

    def test_llm_fn_error_returns_error(self, tools):
        def broken(prompt):
            raise RuntimeError("boom")

        r = build_plan("x", llm_fn=broken)
        assert not r.ok
        assert r.error is not None


class TestHelpers:
    def test_available_tools_lists_registry(self, tools):
        prompt = available_tools_prompt()
        assert isinstance(prompt, str) and prompt

    def test_plan_prompt_has_tools_and_message_placeholders(self):
        assert "{tools}" in PLAN_PROMPT
        assert "{message}" in PLAN_PROMPT

    def test_step_to_dict(self):
        s = PlanStep(tool="calculate", arguments={"expression": "1+1"})
        d = s.to_dict()
        assert d["tool"] == "calculate"
        assert d["arguments"] == {"expression": "1+1"}
        assert d["required"] is True
