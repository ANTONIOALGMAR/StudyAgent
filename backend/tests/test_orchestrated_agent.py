"""Testes da integração de orquestração multi-step no StudyAgent."""

from unittest.mock import MagicMock, patch

from app.agent.agent import StudyAgent
from app.core.plan_builder import BuildResult, PlanStep
from app.core.tool_registry import get, reset_registry, tool


def _make_agent():
    agent = StudyAgent.__new__(StudyAgent)
    agent.memory = MagicMock()
    agent.memory.get_or_create_session.return_value = "test-session"
    agent.memory.add_message = MagicMock()
    agent.ctx = MagicMock()
    agent.ctx.assemble.return_value = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "pedido"},
    ]
    agent._session_docs = {}
    return agent


class TestOrchestratedMultiStep:
    def setup_method(self):
        reset_registry()

        @tool(
            name="web_search",
            description="Pesquisa na web",
            parameters={"query": {"type": "string"}},
            permission="internet",
            required=["query"],
        )
        def web_search(args):
            return "RESULTADO_BUSCA"

        @tool(
            name="open_url",
            description="Abre uma página",
            parameters={"url": {"type": "string"}},
            permission="internet",
            required=["url"],
        )
        def open_url(args):
            return "CONTEUDO_PAGINA"

    @patch("app.agent.agent.chat_with_tools")
    @patch("app.agent.agent.chat")
    @patch("app.core.plan_builder.build_plan")
    def test_distributes_multiple_tasks(self, mock_build, mock_chat, mock_ct):
        """Pedido gera múltiplas ações executadas em cadeia (com dependência)."""
        mock_build.return_value = BuildResult(
            steps=[
                PlanStep(tool="web_search", arguments={"query": "palmeiras"}),
                PlanStep(
                    tool="open_url",
                    arguments={"url": "https://x.com"},
                    depends_on=["0"],
                ),
            ],
            raw="",
        )
        mock_chat.return_value = "A resposta com base nos resultados."

        get("web_search").handler = lambda args: "RESULTADO_BUSCA"
        get("open_url").handler = lambda args: "CONTEUDO_PAGINA"

        agent = _make_agent()
        result = agent.process("busque algo na web")

        assert "web_search" in result["tools_used"]
        assert "open_url" in result["tools_used"]
        assert result["response"] == "A resposta com base nos resultados."
        assert mock_ct.call_count == 0  # não usou o loop reativo

    @patch("app.agent.agent.chat_with_tools")
    @patch("app.agent.agent.chat")
    @patch("app.core.plan_builder.build_plan")
    def test_empty_plan_falls_back_to_loop(self, mock_build, mock_chat, mock_ct):
        """Plano vazio (sem tools necessárias) cai no loop tradicional."""
        mock_build.return_value = BuildResult(steps=[], raw="")
        mock_ct.return_value = {"content": "resposta simples", "tool_calls": []}
        mock_chat.return_value = "resposta simples"

        agent = _make_agent()
        result = agent.process("busque algo")

        assert result["response"] == "resposta simples"

    @patch("app.agent.agent.chat_with_tools")
    @patch("app.agent.agent.chat")
    @patch("app.core.plan_builder.build_plan")
    def test_plan_with_only_failures_falls_back(self, mock_build, mock_chat, mock_ct):
        """Se nenhum passo do plano executa com sucesso, cai no loop."""
        mock_build.return_value = BuildResult(
            steps=[PlanStep(tool="web_search", arguments={"query": "x"})],
            raw="",
        )
        get("web_search").handler = lambda args: (_ for _ in ()).throw(
            RuntimeError("falhou")
        )
        mock_ct.return_value = {"content": "fallback", "tool_calls": []}
        mock_chat.return_value = "fallback"

        agent = _make_agent()
        result = agent.process("busque algo")

        assert result["response"] == "fallback"

    @patch("app.agent.agent.chat_with_tools")
    @patch("app.agent.agent.chat")
    def test_greeting_goes_through_simple_chat(self, mock_chat, mock_ct):
        """'Oi, tá me ouvindo?' deve usar chat simples (sem tool-calling)."""
        mock_chat.return_value = "Oi! Sim, estou te ouvindo. Como posso ajudar?"

        agent = _make_agent()
        result = agent.process("Oi, tá me ouvindo?")

        assert mock_ct.call_count == 0  # não caiu no tool-calling
        assert result["response"] == "Oi! Sim, estou te ouvindo. Como posso ajudar?"

    @patch("app.agent.agent.chat_with_tools")
    @patch("app.agent.agent.chat")
    def test_casual_question_uses_simple_chat(self, mock_chat, mock_ct):
        """Pergunta casual CHAT (não-saudação) NÃO usa tool-calling.

        Regressão: 'O que está faltando para você falar comigo?' confabulava
        'Não há resposta JSON necessária...' no modelo tool-calling.
        """
        mock_chat.return_value = "Tudo pronto! Fale o que precisar."

        agent = _make_agent()
        result = agent.process("O que está faltando para você falar comigo?")

        assert mock_ct.call_count == 0
        assert result["response"] == "Tudo pronto! Fale o que precisar."

    @patch("app.agent.agent.chat_with_tools")
    @patch("app.agent.agent.chat")
    def test_named_greeting_uses_simple_chat(self, mock_chat, mock_ct):
        """'Estude, tá me ouvindo?' (nome + checagem) usa chat simples."""
        mock_chat.return_value = "Sim, estou ouvindo!"

        agent = _make_agent()
        result = agent.process("Estude, tá me ouvindo?")

        assert mock_ct.call_count == 0
        assert result["response"] == "Sim, estou ouvindo!"

    @patch("app.agent.agent.chat_with_tools")
    @patch("app.agent.agent.chat")
    def test_casual_uses_clean_chat_prompt(self, mock_chat, mock_ct):
        """Pergunta casual usa chat_mode=True (prompt limpo, sem visão/tools)."""
        from unittest.mock import ANY

        mock_chat.return_value = "Olá! Em que posso ajudar?"

        agent = _make_agent()
        agent.process("Oi, boa tarde.")

        agent.ctx.assemble.assert_called_with(ANY, ANY, chat_mode=True)
