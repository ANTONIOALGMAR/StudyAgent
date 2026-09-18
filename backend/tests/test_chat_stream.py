"""Testes do streaming token-a-token (SSE) do StudyAgent.

Cobertura:
- `app.agent.llm.chat_stream`: gerador sobre o stream do client Ollama
  (peças vazias descartadas, erro de contexto mapeado p/ mensagem amigável);
- `StudyAgent.process_events` / `process`: ordem dos eventos
  (start → token* → done) e o shape do resultado (compatível com POST /api/chat);
- `POST /api/chat/stream`: endpoint SSE via TestClient
  (content-type, linhas `data:` JSON e sentinela `[DONE]`).

Todos os testes fazem mock do client LLM — não há rede/Ollama no ambiente.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agent import llm
from app.agent.agent import StudyAgent
from app.main import app
from app.routers import chat as chat_router

client = TestClient(app)


def _make_agent() -> StudyAgent:
    """Agent sem construção real (mesmo padrão de test_orchestrated_agent)."""
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


class TestLlmChatStream:
    def test_yields_content_pieces_in_order(self):
        fake = MagicMock()
        fake.chat.return_value = iter(
            [
                {"message": {"content": "Olá "}},
                {"message": {"content": "mundo"}},
                {"message": {"content": ""}},  # peça vazia: deve ser descartada
            ]
        )
        with patch.object(llm, "_client", fake):
            pieces = list(llm.chat_stream([{"role": "user", "content": "oi"}]))
        assert pieces == ["Olá ", "mundo"]
        assert fake.chat.call_args.kwargs["stream"] is True

    def test_context_overflow_becomes_friendly_error(self):
        fake = MagicMock()
        fake.chat.side_effect = RuntimeError("context size too small for request")
        with patch.object(llm, "_client", fake):
            with pytest.raises(RuntimeError, match="longa demais"):
                list(llm.chat_stream([{"role": "user", "content": "oi"}]))


class TestProcessEventsStreaming:
    @patch("app.agent.agent.chat_stream")
    def test_event_order_and_response(self, mock_stream):
        """Casual (saudação): start → token* → done, resposta = concatenação."""
        mock_stream.return_value = iter(["Olá! ", "Tudo bem?"])
        agent = _make_agent()

        events = list(agent.process_events("Oi, tudo bem?"))

        assert [e["type"] for e in events] == ["start", "token", "token", "done"]
        assert events[0]["session_id"] == "test-session"
        tokens = [e["text"] for e in events if e["type"] == "token"]
        assert "".join(tokens) == "Olá! Tudo bem?"

        done = events[-1]["result"]
        assert done["session_id"] == "test-session"
        assert done["response"] == "Olá! Tudo bem?"
        assert done["tools_used"] == []
        mock_stream.assert_called_once()

    @patch("app.agent.agent.chat_stream")
    def test_process_wrapper_returns_done_result(self, mock_stream):
        """`process()` mantém a API clássica (dict) sobre o mesmo motor."""
        mock_stream.return_value = iter(["Sim, ", "estou ouvindo."])
        agent = _make_agent()

        result = agent.process("Oi, tudo bem?")

        assert result["response"] == "Sim, estou ouvindo."
        assert result["session_id"] == "test-session"
        assert "tools_used" in result

    @patch("app.agent.agent.chat_stream")
    def test_stream_error_falls_back_to_friendly_message(self, mock_stream):
        """Indisponibilidade do modelo vira mensagem amigável (sem quebrar o stream)."""
        mock_stream.side_effect = RuntimeError("modelo indisponível")
        agent = _make_agent()

        result = agent.process("Oi, tudo bem?")

        assert "indisponível" in result["response"]
        assert "Tente novamente em instantes" in result["response"]


class TestSseEndpoint:
    @pytest.fixture(autouse=True)
    def _reset_limiters(self):
        """Isola o rate limiter (15/min) entre testes do endpoint."""
        app.state.limiter.reset()
        chat_router.limiter.reset()
        yield
        app.state.limiter.reset()
        chat_router.limiter.reset()

    def test_chat_stream_returns_sse_events(self):
        fake_agent = MagicMock()
        fake_agent.process_events.return_value = iter(
            [
                {"type": "start", "session_id": "s1"},
                {"type": "token", "text": "Olá "},
                {"type": "token", "text": "mundo"},
                {
                    "type": "done",
                    "result": {
                        "session_id": "s1",
                        "response": "Olá mundo",
                        "tools_used": [],
                    },
                },
            ]
        )
        with patch.object(chat_router, "agent", fake_agent):
            resp = client.post("/api/chat/stream", json={"message": "Oi"})

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        data_lines = [ln for ln in resp.text.splitlines() if ln.startswith("data: ")]
        assert data_lines[-1] == "data: [DONE]"
        events = [json.loads(ln[len("data: "):]) for ln in data_lines[:-1]]
        assert [e["type"] for e in events] == ["start", "token", "token", "done"]
        assert "".join(e["text"] for e in events if e["type"] == "token") == "Olá mundo"
        assert events[-1]["result"]["response"] == "Olá mundo"
        fake_agent.process_events.assert_called_once()
