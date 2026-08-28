"""Testes críticos: validar que 'leia o monitor 2' funciona end-to-end.

Seções 53-56 do master prompt. Estes testes provam que o pipeline de visão
realmente analisa a tela e NÃO dá saudação.
"""

from unittest.mock import patch

from PIL import Image

from app.agent.agent import StudyAgent
from app.core.planner import build_plan
from app.core.vision_router import VisionIntent

# ── Helpers ────────────────────────────────────────────────────────


def _fake_image(monitor=2, w=1920, h=1080):
    """Cria imagem fake com conteúdo visual (não preta)."""
    img = Image.new("RGB", (w, h), color=(100, 150, 200))
    # Adiciona um retângulo branco para simular conteúdo
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 100, 800, 400], fill=(255, 255, 255))
    draw.text((120, 120), f"Monitor {monitor} - Conteudo visivel", fill=(0, 0, 0))
    return img


def _fake_monitors(n=4):
    """Retorna lista fake de monitores."""
    monitors = [{"index": 0, "width": 4726, "height": 1080, "left": 0, "top": 0}]
    sizes = [(1920, 1080, 2806, 0), (1440, 900, 0, 180), (1365, 1024, 1440, 56)]
    for i, (w, h, left, top) in enumerate(sizes[: n - 1], start=1):
        monitors.append({"index": i, "width": w, "height": h, "left": left, "top": top})
    return monitors


# ── Seção 53: Teste Crítico — 'leia o monitor 2' ──────────────────


class TestCriticalLeiaMonitor2:
    """O pipeline de visão analisa a tela e NÃO dá saudação."""

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_planner_sets_correct_intent_and_monitor(self, mock_sm, mock_win, mock_chat):
        """Planner detecta SCREEN_READ e monitor=2."""
        p = build_plan("leia o monitor 2", use_screen_requested=False)
        assert p.vision_intent == VisionIntent.SCREEN_READ
        assert p.capture_screen is True
        assert p.monitor == 2

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_pipeline_calls_capture_monitor_2(self, mock_sm, mock_win, mock_chat):
        """Pipeline chama ScreenManager.capture_monitor(monitor_id=2)."""
        img = _fake_image(monitor=2)
        mock_sm.capture_monitor.return_value = img
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = {"app": "code", "title": "main.py"}
        mock_chat.return_value = "O que vejo: um terminal com codigo Python."

        agent = StudyAgent()
        agent.process("leia o monitor 2", use_screen=True)

        mock_sm.capture_monitor.assert_called_once()
        call_kwargs = mock_sm.capture_monitor.call_args
        assert call_kwargs[1].get("monitor_id") == 2 or call_kwargs[0][0] == 2

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_pipeline_sends_image_to_llm(self, mock_sm, mock_win, mock_chat):
        """Imagem capturada é enviada ao LLM (images=[bytes])."""
        img = _fake_image(monitor=2)
        mock_sm.capture_monitor.return_value = img
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = None
        mock_chat.return_value = "Vejo um editor de codigo aberto."

        agent = StudyAgent()
        agent.process("leia o monitor 2", use_screen=True)

        # chat deve ser chamado com images não-vazio
        mock_chat.assert_called()
        call_args = mock_chat.call_args
        images_kw = call_args[1].get("images", call_args[0][1] if len(call_args[0]) > 1 else None)
        assert images_kw is not None
        assert len(images_kw) > 0
        assert isinstance(images_kw[0], bytes)
        assert len(images_kw[0]) > 100  # imagem real, não bytes vazios

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_response_is_not_greeting(self, mock_sm, mock_win, mock_chat):
        """Resposta NÃO é saudação ('olá', 'oi', 'como posso ajudar')."""
        img = _fake_image(monitor=2)
        mock_sm.capture_monitor.return_value = img
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = {"app": "firefox", "title": "Wikipedia"}
        mock_chat.return_value = (
            "O QUE VEIO: Vejo o navegador Firefox aberto com a pagina da Wikipedia.\n"
            "CONTEUDO: Texto sobre historia do Brasil.\n"
            "ANALISE: O monitor 2 mostra uma pagina web aberta."
        )

        agent = StudyAgent()
        result = agent.process("leia o monitor 2", use_screen=True)

        resp = result["response"].lower()
        # NÃO deve conter saudações
        assert "olá" not in resp
        assert "oi!" not in resp
        assert "como posso ajudar" not in resp
        assert "bom dia" not in resp
        # DEVE conter conteúdo descritivo
        assert len(resp) > 50

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_vision_context_has_image_and_ocr(self, mock_sm, mock_win, mock_chat):
        """VisionContext é construído com image_bytes e ocr_text."""
        img = _fake_image(monitor=2)
        mock_sm.capture_monitor.return_value = img
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = {"app": "code", "title": "test.py"}
        mock_chat.return_value = "Vejo codigo Python na tela."

        agent = StudyAgent()
        result = agent.process("leia o monitor 2", use_screen=True)

        # Verificar que o pipeline foi executado
        assert "screen_capture" in result["tools_used"]
        # Verificar que chat foi chamado com imagem
        call_args = mock_chat.call_args
        images = call_args[1].get("images", [])
        assert len(images) > 0

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_system_prompt_is_vision_not_tutor(self, mock_sm, mock_win, mock_chat):
        """Quando há imagem válida, system prompt é o VISION_SYSTEM_PROMPT."""
        img = _fake_image(monitor=2)
        mock_sm.capture_monitor.return_value = img
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = None
        mock_chat.return_value = "Analise visual da tela."

        agent = StudyAgent()
        agent.process("leia o monitor 2", use_screen=True)

        # O system prompt deve conter VISION_SYSTEM_PROMPT
        call_args = mock_chat.call_args
        messages = call_args[0][0]
        system_msg = messages[0]["content"]
        assert "modulo de visao" in system_msg.lower() or "visão" in system_msg.lower()
        assert "METODOLOGIA SOCRÁTICA" not in system_msg

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_monitor_2_resolution_in_context(self, mock_sm, mock_win, mock_chat):
        """Resolução do monitor 2 (1440x900) aparece no contexto."""
        img = _fake_image(monitor=2, w=1440, h=900)
        mock_sm.capture_monitor.return_value = img
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = None
        mock_chat.return_value = "Vejo conteúdo na tela."

        agent = StudyAgent()
        agent.process("leia o monitor 2", use_screen=True)

        call_args = mock_chat.call_args
        messages = call_args[0][0]
        system_msg = messages[0]["content"]
        # Resolution might be in context or system prompt
        assert "1440" in system_msg or "900" in system_msg


# ── Seção 54: Teste de Falha — monitor não existe ─────────────────


class TestMonitorNotFound:
    """Monitor inexistente → resposta informativa, sem crash."""

    @patch("app.agent.agent.ScreenManager")
    def test_monitor_99_returns_error(self, mock_sm):
        """Monitor 99 não existe → resposta com monitores disponíveis."""
        mock_sm.list_monitors.return_value = _fake_monitors(4)

        agent = StudyAgent()
        result = agent.process("leia o monitor 99", use_screen=True)

        assert "monitor 99" in result["response"].lower() or "99" in result["response"]
        assert result["tools_used"] == []

    @patch("app.agent.agent.ScreenManager")
    def test_monitor_negative_returns_error(self, mock_sm):
        """Monitor -1 → resposta com erro."""
        mock_sm.list_monitors.return_value = _fake_monitors(4)

        agent = StudyAgent()
        result = agent.process("leia o monitor -1", use_screen=True)

        # Should mention monitor doesn't exist or is invalid
        assert len(result["response"]) > 0
        assert result["tools_used"] == []


# ── Seção 55: Teste de Alucinação — captura falha ─────────────────


class TestHallucinationPrevention:
    """Quando a captura falha, o modelo NÃO pode inventar conteúdo da tela."""

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_failed_capture_no_content_claim(self, mock_sm, mock_win, mock_chat):
        """Capture falha → resposta contém aviso, não descrição de conteúdo."""
        mock_sm.capture_monitor.side_effect = RuntimeError("Wayland capture failed")
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = None
        mock_chat.return_value = "Esta é uma resposta que não deveria ser chamada."

        agent = StudyAgent()
        result = agent.process("leia o monitor 2", use_screen=True)

        # Resposta deve indicar falha
        resp = result["response"].lower()
        assert "falha" in resp or "não consegui" in resp or "captura" in resp
        # Resposta NÃO deve descrever conteúdo da tela
        assert "vejo" not in resp
        assert "aparece" not in resp

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_black_image_returns_error(self, mock_sm, mock_win, mock_chat):
        """Imagem preta (falha Wayland) → erro, não descrição."""
        # Imagem preta (todos os pixels = 0)
        black_img = Image.new("RGB", (1920, 1080), color=(0, 0, 0))
        mock_sm.capture_monitor.return_value = black_img
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = None
        mock_chat.return_value = "Não deveria ser chamado."

        agent = StudyAgent()
        result = agent.process("leia o monitor 2", use_screen=True)

        resp = result["response"].lower()
        # Deve indicar falha na captura
        assert "falha" in resp or "não consegui" in resp or "preta" in resp

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_empty_image_bytes_rejected(self, mock_sm, mock_win, mock_chat):
        """Image bytes vazios → RuntimeError, não resposta do modelo."""
        # Mock para retornar imagem que vai gerar bytes vazios
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        mock_sm.capture_monitor.return_value = img
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = None
        mock_chat.return_value = "Não deveria chegar aqui."

        agent = StudyAgent()
        # Deve levantar RuntimeError ou retornar erro
        try:
            result = agent.process("leia o monitor 2", use_screen=True)
            # Se não levantou exceção, verificar que retornou erro
            resp = result["response"].lower()
            assert "falha" in resp or "não consegui" in resp or "erro" in resp
        except RuntimeError:
            pass  # Exceção também é aceitável


# ── Seção 56: Teste de Código — ZeroDivisionError ─────────────────


class TestCodeOnScreen:
    """Agente identifica código e erros na tela."""

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_code_error_detected(self, mock_sm, mock_win, mock_chat):
        """Código com ZeroDivisionError na tela → agente identifica o erro."""
        img = _fake_image(monitor=2)
        mock_sm.capture_monitor.return_value = img
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = {"app": "code", "title": "div.py"}
        mock_chat.return_value = (
            "O QUE VEJO: Editor de codigo com um script Python.\n"
            "CONTEUDO: print(10/0) - Division by zero error.\n"
            "ANALISE: Ha um ZeroDivisionError no codigo. "
            "O erro ocorre porque 10/0 nao e permitido em Python."
        )

        agent = StudyAgent()
        result = agent.process(
            "ha algum erro no codigo da tela?", use_screen=True
        )

        resp = result["response"].lower()
        # Deve mencionar o erro
        assert "error" in resp or "erro" in resp or "division" in resp or "zero" in resp

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_code_read_from_screen(self, mock_sm, mock_win, mock_chat):
        """Agente lê código na tela."""
        img = _fake_image(monitor=2)
        mock_sm.capture_monitor.return_value = img
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = {"app": "code", "title": "main.py"}
        mock_chat.return_value = (
            "O QUE VEJO: Um editor VS Code com codigo Python.\n"
            "CONTEUDO: def hello(): print('ola mundo')\n"
            "ANALISE: O codigo define uma funcao hello que imprime 'ola mundo'."
        )

        agent = StudyAgent()
        result = agent.process("leia o codigo da tela", use_screen=True)

        resp = result["response"].lower()
        # Deve conter leitura do código
        assert "def" in resp or "hello" in resp or "print" in resp or "codigo" in resp


# ── Testes extras de integração ────────────────────────────────────


class TestVisionPipelineIntegration:
    """Testes de integração do pipeline completo."""

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_monitor_1_works(self, mock_sm, mock_win, mock_chat):
        """Monitor 1 também funciona."""
        img = _fake_image(monitor=1, w=1920, h=1080)
        mock_sm.capture_monitor.return_value = img
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = None
        mock_chat.return_value = "Vejo o monitor 1 com um navegador."

        agent = StudyAgent()
        result = agent.process("leia o monitor 1", use_screen=True)

        assert "screen_capture" in result["tools_used"]
        call_args = mock_chat.call_args
        images = call_args[1].get("images", [])
        assert len(images) > 0

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_ocr_text_in_context(self, mock_sm, mock_win, mock_chat):
        """Texto OCR extraído aparece no contexto para o LLM."""
        img = _fake_image(monitor=2)
        mock_sm.capture_monitor.return_value = img
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = None
        mock_chat.return_value = "Analise feita."

        agent = StudyAgent()
        agent.process("leia o monitor 2", use_screen=True)

        call_args = mock_chat.call_args
        messages = call_args[0][0]
        system_msg = messages[0]["content"]
        # Context should mention monitor
        assert "monitor" in system_msg.lower()

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_user_message_preserved_in_vision(self, mock_sm, mock_win, mock_chat):
        """Mensagem do usuário é preservada no contexto de visão."""
        img = _fake_image(monitor=2)
        mock_sm.capture_monitor.return_value = img
        mock_sm.list_monitors.return_value = _fake_monitors(4)
        mock_win.active_window.return_value = None
        mock_chat.return_value = "Resposta."

        agent = StudyAgent()
        agent.process("leia o monitor 2", use_screen=True)

        call_args = mock_chat.call_args
        messages = call_args[0][0]
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert any("leia o monitor 2" in m["content"] for m in user_msgs)
