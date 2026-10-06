"""Tela sob comando + leitura de questões na tela/imagem.

Cobre o pedido de identificar a tela que recebeu o comando (com 3 telas),
ler a tela, detectar as questões e responder item a item.
"""

from io import BytesIO
from unittest.mock import patch

from PIL import Image, ImageDraw

from app.agent.agent import StudyAgent
from app.core.planner import build_plan
from app.core.vision_router import OCRResult, VisionIntent
from app.vision import questions as q_mod
from app.vision import screen as screen_mod
from app.vision.window import _rect_from_window, active_window_rect

# ── Helpers ────────────────────────────────────────────────────────


def _imagem_questoes() -> Image.Image:
    """Imagem com enunciados desenhados (conteúdo visual, não preta)."""

    img = Image.new("RGB", (900, 700), color=(250, 250, 245))
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 860, 660], outline=(20, 20, 20), width=3)
    draw.text((70, 90), "Questao 1: 3 + 4 + 5 = ?", fill=(0, 0, 0))
    draw.text((70, 160), "Questao 2: capital do Brasil", fill=(0, 0, 0))
    return img


def _tres_monitores() -> list[dict]:
    """Três telas lado a lado, como na máquina do aluno."""

    return [
        {
            "index": i,
            "name": f"HDMI-{i}",
            "width": 1920,
            "height": 1080,
            "left": i * 1920,
            "top": 0,
            "right": (i + 1) * 1920,
            "bottom": 1080,
        }
        for i in range(3)
    ]


OCR_QUESTOES = """Exercícios

Questão 1
Quanto é 3 + 4 + 5?
a) 11
b) 12
c) 13

Questão 2
Qual a capital do Brasil?
a) São Paulo
b) Brasília
"""


# ── Tela sob comando ───────────────────────────────────────────────


class TestTelaSobComando:
    def test_janela_na_segunda_tela(self):
        with patch.object(screen_mod, "_discover_monitors", return_value=_tres_monitores()):
            posicao = screen_mod.ScreenManager.monitor_for_rect(
                {"left": 2000, "top": 100, "width": 1000, "height": 700}
            )
        assert posicao == 1

    def test_janela_na_terceira_tela(self):
        with patch.object(screen_mod, "_discover_monitors", return_value=_tres_monitores()):
            posicao = screen_mod.ScreenManager.monitor_for_rect(
                {"left": 4000, "top": 50, "width": 800, "height": 600}
            )
        assert posicao == 2

    def test_janela_entre_duas_telas_usa_o_maior_sobreposto(self):
        """Janela atravessando a emenda pertence à tela com maior área."""

        with patch.object(screen_mod, "_discover_monitors", return_value=_tres_monitores()):
            posicao = screen_mod.ScreenManager.monitor_for_rect(
                {"left": 1800, "top": 100, "width": 600, "height": 600}
            )
        # Tela 0: 1800..1920 = 120px | Tela 1: 1920..2400 = 480px
        assert posicao == 1

    def test_centro_da_janela_vence_a_area(self):
        """Com empatar em área, o monitor que contém o centro decide."""

        with patch.object(screen_mod, "_discover_monitors", return_value=_tres_monitores()):
            posicao = screen_mod.ScreenManager.monitor_for_rect(
                {"left": 0, "top": 0, "width": 3840, "height": 1080}
            )
        assert posicao == 1

    def test_rectangulo_invalido(self):
        assert screen_mod.ScreenManager.monitor_for_rect(None) is None
        assert screen_mod.ScreenManager.monitor_for_rect({"left": 0}) is None
        assert (
            screen_mod.ScreenManager.monitor_for_rect(
                {"left": 0, "top": 0, "width": 0, "height": 10}
            )
            is None
        )

    def test_resolve_monitor_usa_janela_ativa(self):
        with (
            patch.object(
                screen_mod,
                "_discover_monitors",
                return_value=_tres_monitores(),
            ),
            patch(
                "app.vision.window.active_window",
                return_value={
                    "title": "Firefox",
                    "app": "firefox",
                    "left": 4000,
                    "top": 0,
                    "width": 1000,
                    "height": 800,
                },
            ),
        ):
            monitor_id, ativo = screen_mod.ScreenManager.resolve_monitor(None)

        assert monitor_id == 2
        assert ativo["name"] == "HDMI-2"
        assert ativo["active_window"]["app"] == "firefox"

    def test_resolve_monitor_respeita_monitor_pedido(self):
        with patch("app.vision.window.active_window", return_value=None):
            monitor_id, ativo = screen_mod.ScreenManager.resolve_monitor(1)

        assert monitor_id == 1
        assert ativo is None

    def test_sem_janela_ativa_usa_primeiro_monitor(self):
        with patch("app.vision.window.active_window", return_value=None):
            monitor_id, _ = screen_mod.ScreenManager.resolve_monitor(None)

        assert monitor_id == 0

    def test_active_window_rect_exige_geometria(self):
        assert _rect_from_window({"title": "x", "app": "y"}) is None

        rect = _rect_from_window(
            {"title": "x", "app": "y", "left": 10, "top": 20, "width": 30, "height": 40}
        )
        assert rect == {
            "left": 10,
            "top": 20,
            "width": 30,
            "height": 40,
            "right": 40,
            "bottom": 60,
        }

    def test_active_window_rect_delega_para_active_window(self):
        with patch(
            "app.vision.window.active_window",
            return_value={
                "title": "t",
                "app": "a",
                "left": 1,
                "top": 2,
                "width": 3,
                "height": 4,
            },
        ):
            assert active_window_rect()["right"] == 4


# ── Planner ────────────────────────────────────────────────────────


class TestPlannerTelaSobComando:
    def test_essa_tela_usa_monitor_da_janela_ativa(self):
        p = build_plan("o que tem nessa tela?", use_screen_requested=False)
        assert p.capture_screen
        assert p.active_screen
        assert not p.monitor_explicit
        assert p.monitor is None
        assert p.needs_active_monitor

    def test_resolva_aqui_marca_exercicio(self):
        p = build_plan("resolva as questões aqui na minha frente", use_screen_requested=False)
        assert p.capture_screen
        assert p.want_answers
        assert p.vision_intent == VisionIntent.SCREEN_EXERCISE
        assert p.needs_active_monitor

    def test_numero_explicito_dispensa_descoberta(self):
        p = build_plan("resolva as questões da tela 3", use_screen_requested=False)
        assert p.monitor == 2
        assert p.monitor_explicit
        assert not p.needs_active_monitor

    def test_monitor_zero_e_respeitado(self):
        p = build_plan("leia o monitor 0", use_screen_requested=False)
        assert p.monitor == 0
        assert p.monitor_explicit

    def test_conversa_casual_nao_captura(self):
        p = build_plan("bom dia, tudo bem com você?", use_screen_requested=False)
        assert not p.capture_screen
        assert not p.active_screen
        assert not p.want_answers


# ── Detecção de questões ───────────────────────────────────────────


class TestDeteccaoQuestoes:
    def test_multipla_escolha(self):
        achadas = q_mod.detect_questions(OCR_QUESTOES)
        assert len(achadas) == 2
        assert achadas[0].label == "1"
        assert achadas[0].stem == "Quanto é 3 + 4 + 5?"
        assert achadas[0].options == {"a": "11", "b": "12", "c": "13"}
        assert achadas[0].is_multiple_choice

    def test_alternativas_com_parenteses(self):
        achadas = q_mod.detect_questions(
            "1) Qual o maior?\n( a ) 3\n( b ) 7\n( c ) 5\n"
        )
        assert achadas[0].options == {"a": "3", "b": "7", "c": "5"}

    def test_opcoes_no_formato_opcao_a(self):
        """Ambiente de avaliação online marca as opções como 'Opção A' etc."""
        achadas = q_mod.detect_questions(
            "Questão 1\nCom relação às ações oculares, assinale a correta:\n"
            "Opção A\nCada ação secundária é executada por um único músculo.\n"
            "Selecionado\n"
            "Opção B\nCada músculo executa pelo menos uma ação.\n"
            "Opção C\nNenhum músculo executa ações secundárias ou terciárias.\n"
        )
        assert len(achadas) == 1
        questao = achadas[0]
        assert questao.label == "1"
        assert questao.is_multiple_choice
        assert questao.options["a"] == "Cada ação secundária é executada por um único músculo."
        assert questao.options["b"] == "Cada músculo executa pelo menos uma ação."
        assert questao.options["c"] == "Nenhum músculo executa ações secundárias ou terciárias."

    def test_alternativa_com_texto_na_mesma_linha(self):
        achadas = q_mod.detect_questions(
            "Questão 1\nQual o maior?\nAlternativa A: 3\nAlternativa B: 7\n"
        )
        assert achadas[0].options == {"a": "3", "b": "7"}

    def test_verdadeiro_ou_falso(self):
        achadas = q_mod.detect_questions(
            "Questão 1\nA água ferve a 100 °C.\n( ) Verdadeiro\n( ) Falso\n"
        )
        assert achadas[0].kind == "verdadeiro_falso"

    def test_texto_corrido_nao_e_questao(self):
        assert q_mod.detect_questions("Arquivo Editar Exibir Ajuda\nDocumento salvo") == []

    def test_sem_texto(self):
        assert q_mod.detect_questions(None) == []
        assert q_mod.detect_questions("") == []

    def test_rotulos_unicos_quando_nao_numerado(self):
        achadas = q_mod.detect_questions(
            "Qual a capital do Brasil?\na) São Paulo\nb) Brasília\n\n"
            "Qual o maior?\na) 1\nb) 2\n"
        )
        assert [q.label for q in achadas] == ["1", "2"]

    def test_prompt_lista_as_questoes(self):
        achadas = q_mod.detect_questions(OCR_QUESTOES)
        bloco = q_mod.format_questions(achadas)
        assert "QUESTÕES DETECTADAS" in bloco
        assert "1) Quanto é 3 + 4 + 5?" in bloco
        assert "   b) 12" in bloco

        instrucao = q_mod.answer_instruction(achadas)
        assert "TODAS as questões" in instrucao

    def test_leitura_das_respostas(self):
        achadas = q_mod.detect_questions(OCR_QUESTOES)
        respostas = q_mod.parse_answers(
            "1) B) 12 — porque 3 + 4 + 5 = 12.\n"
            "2) B) Brasília — é a capital federal.\n",
            achadas,
        )
        assert [r["label"] for r in respostas] == ["1", "2"]
        assert respostas[0]["answer"] == "B"
        assert "12" in respostas[0]["answer_text"]
        assert respostas[1]["answer"] == "B"

    def test_resposta_fora_da_lista_e_ignorada(self):
        achadas = q_mod.detect_questions(OCR_QUESTOES)
        respostas = q_mod.parse_answers("7) D) nada disso", achadas)
        assert respostas == []

    def test_justificativa_generica_nao_vira_resposta(self):
        """'A resposta está correta, conforme o enunciado' não é resposta —
        derruba a letra e marca como incerta, em vez de chutar."""
        achadas = q_mod.detect_questions(OCR_QUESTOES)
        respostas = q_mod.parse_answers(
            "1) A) 12 — A resposta está correta, conforme o enunciado.\n",
            achadas,
        )
        assert respostas[0]["answer"] == ""
        assert "incerta" in respostas[0]["answer_text"]

    def test_sem_questoes_nao_monta_prompt(self):
        assert q_mod.format_questions([]) == ""
        assert q_mod.answer_instruction([]) == ""


# ── Agente: leitura da tela e respostas ────────────────────────────


class TestAgenteQuestoesDaTela:
    def test_resolve_questoes_da_tela_sob_comando(self):
        """A janela em foco decide qual das 3 telas é capturada e lida."""

        capturado = {}

        def fake_capture(monitor_id, region=None):
            capturado["monitor_id"] = monitor_id
            return _imagem_questoes()

        with (
            patch(
                "app.vision.screen.ScreenManager.capture_monitor",
                side_effect=fake_capture,
            ),
            patch("app.vision.screen._discover_monitors", return_value=_tres_monitores()),
            patch(
                "app.vision.window.active_window",
                return_value={
                    "title": "Exercícios",
                    "app": "chrome",
                    "left": 4000,
                    "top": 0,
                    "width": 1200,
                    "height": 900,
                },
            ),
            patch("app.vision.engine.ocr") as mock_ocr,
            patch("app.agent.agent.chat") as mock_chat,
        ):
            mock_ocr.available.return_value = True
            mock_ocr.read_text_structured.return_value = OCRResult.from_text(
                OCR_QUESTOES
            )
            mock_chat.return_value = "1) B) 12"

            agent = StudyAgent()
            result = agent.process(
                "resolva as questões da minha tela",
                use_screen=True,
                monitor=None,
            )

        # A tela sob comando (janela em foco na 3a tela) foi capturada.
        assert capturado["monitor_id"] == 2
        assert result["response"] == "1) B) 12"

        enviada = "\n".join(m["content"] for m in mock_chat.call_args[0][0])
        assert "QUESTÕES DETECTADAS" in enviada
        assert "TODAS as questões" in enviada
        assert "screen_capture" in result["tools_used"]

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_monitor_zero_nao_vira_monitor_um(self, mock_sm, mock_win, mock_chat):
        mock_sm.list_monitors.return_value = _tres_monitores()
        mock_sm.get_monitor.side_effect = lambda m: _tres_monitores()[m]
        mock_sm.capture_monitor.return_value = _imagem_questoes()
        mock_win.active_window.return_value = None
        mock_chat.return_value = "resposta"

        with (
            patch("app.agent.agent.ocr") as mock_ocr,
            patch(
                "app.agent.agent.questions_mod.detect_questions",
                return_value=[],
            ),
        ):
            mock_ocr.available.return_value = True
            mock_ocr.read_text_structured.return_value = None
            mock_ocr.read_text.return_value = ""

            agent = StudyAgent()
            agent.process("leia o monitor 0", use_screen=True, monitor=0)

        assert mock_sm.capture_monitor.call_args.kwargs["monitor_id"] == 0

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_resolve_monitor_quebrado_nao_derruba_o_chat(
        self, mock_sm, mock_win, mock_chat
    ):
        mock_sm.list_monitors.return_value = _tres_monitores()
        mock_sm.get_monitor.side_effect = lambda m: _tres_monitores()[m]
        mock_sm.capture_monitor.return_value = _imagem_questoes()
        mock_sm.resolve_monitor.side_effect = RuntimeError("xdotool ausente")
        mock_win.active_window.return_value = None
        mock_chat.return_value = "resposta"

        with (
            patch("app.agent.agent.ocr") as mock_ocr,
            patch(
                "app.agent.agent.questions_mod.detect_questions",
                return_value=[],
            ),
        ):
            mock_ocr.available.return_value = True
            mock_ocr.read_text_structured.return_value = None
            mock_ocr.read_text.return_value = ""

            agent = StudyAgent()
            result = agent.process("o que tem aí?", use_screen=True)

        assert mock_sm.capture_monitor.call_args.kwargs["monitor_id"] == 0
        assert result["response"] == "resposta"


# ── Agente: endpoint de questões ───────────────────────────────────


class TestAnswerScreenQuestions:
    def test_respostas_estruturadas(self):
        with (
            patch(
                "app.vision.screen.ScreenManager.capture_monitor",
                return_value=_imagem_questoes(),
            ),
            patch("app.vision.screen._discover_monitors", return_value=_tres_monitores()),
            patch(
                "app.vision.window.active_window",
                return_value={
                    "title": "Exercícios",
                    "app": "chrome",
                    "left": 2000,
                    "top": 0,
                    "width": 1000,
                    "height": 800,
                },
            ),
            patch("app.agent.agent.ocr") as mock_ocr,
            patch("app.agent.agent.chat") as mock_chat,
        ):
            mock_ocr.available.return_value = True
            mock_ocr.read_text.return_value = OCR_QUESTOES
            mock_chat.return_value = (
                "1) B) 12 — 3 + 4 + 5 = 12.\n2) B) Brasília — capital do Brasil.\n"
            )

            agent = StudyAgent()
            result = agent.answer_screen_questions()

        assert result["monitor"] == 1
        assert result["screen_detected"] is True
        assert len(result["questions"]) == 2
        assert [a["label"] for a in result["answers"]] == ["1", "2"]
        assert result["answers"][0]["answer"] == "B"

    def test_justificativa_generica_vira_incerta(self):
        """Resposta com 'correto, conforme o enunciado' não é exibida como
        certa no auto-solve: vira 'incerta', sem letra."""

        with (
            patch(
                "app.vision.screen.ScreenManager.capture_monitor",
                return_value=_imagem_questoes(),
            ),
            patch("app.vision.screen._discover_monitors", return_value=_tres_monitores()),
            patch("app.vision.window.active_window", return_value=None),
            patch("app.agent.agent.ocr") as mock_ocr,
            patch("app.agent.agent.chat") as mock_chat,
        ):
            mock_ocr.available.return_value = True
            mock_ocr.read_text.return_value = OCR_QUESTOES
            mock_chat.return_value = (
                "1) B) 12 — A resposta está correta, conforme o enunciado."
            )

            agent = StudyAgent()
            result = agent.answer_screen_questions()

        assert result["answers"][0]["answer"] == ""
        assert result["answer_text"] == (
            "1) incerta — justificativa genérica não confirma a alternativa."
        )

    def test_sem_questoes_nao_chama_o_modelo(self):
        with (
            patch(
                "app.vision.screen.ScreenManager.capture_monitor",
                return_value=_imagem_questoes(),
            ),
            patch("app.vision.screen._discover_monitors", return_value=_tres_monitores()),
            patch("app.vision.window.active_window", return_value=None),
            patch("app.agent.agent.ocr") as mock_ocr,
            patch("app.agent.agent.chat") as mock_chat,
        ):
            mock_ocr.available.return_value = True
            mock_ocr.read_text.return_value = "Arquivo Editar Exibir Ajuda"

            agent = StudyAgent()
            result = agent.answer_screen_questions()

        assert result["questions"] == []
        assert result["answers"] == []
        assert "Não encontrei questões" in result["answer_text"]
        mock_chat.assert_not_called()


# ── Imagem anexada ─────────────────────────────────────────────────


def _imagem_questoes_png() -> bytes:
    buffer = BytesIO()
    _imagem_questoes().save(buffer, format="PNG")
    return buffer.getvalue()


class TestImagemAnexadaComoDocumento:
    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.ocr")
    def test_imagem_anexada_vai_para_o_modelo_de_visao(self, mock_ocr, mock_chat):
        mock_ocr.available.return_value = True
        mock_ocr.read_text.return_value = OCR_QUESTOES
        mock_ocr.read_text_structured.return_value = None
        mock_chat.return_value = "1) B) 12"

        agent = StudyAgent()
        caminho = Path_of_image()
        doc_id = agent.memory.add_document(
            "questao.png", str(caminho), 1, len(OCR_QUESTOES)
        )
        caminho.with_suffix(".txt").write_text(OCR_QUESTOES, encoding="utf-8")

        result = agent.process(
            "resolva as questões da foto",
            use_screen=False,
            doc_id=doc_id,
        )

        assert result["response"]
        assert "image_input" in result["tools_used"]

        imagens = mock_chat.call_args.kwargs["images"]
        assert imagens and isinstance(imagens[0], bytes)
        assert imagens[0][:8] == b"\x89PNG\r\n\x1a\n"

        enviada = "\n".join(m["content"] for m in mock_chat.call_args[0][0])
        assert "QUESTÕES DETECTADAS" in enviada

    def test_formatos_de_anexo_aceitos(self):
        from app.tools.documents import IMAGE_SUFFIXES, TEXT_SUFFIXES

        assert {".pdf", ".txt", ".md"} <= TEXT_SUFFIXES
        assert {".png", ".jpg", ".jpeg", ".webp"} <= IMAGE_SUFFIXES

    def test_is_image_path(self):
        from app.tools.documents import is_image_path

        assert is_image_path("/tmp/foto.png")
        assert not is_image_path("/tmp/aula.pdf")


def Path_of_image():
    """Cria um PNG de questão em disco e devolve o caminho."""

    import tempfile
    from pathlib import Path

    destino = Path(tempfile.mkdtemp()) / "questao.png"
    destino.write_bytes(_imagem_questoes_png())
    return destino


# ── Fingerprints (dedupe do loop ao vivo) ──────────────────────────


class TestFingerprints:
    def test_estavel_ignora_caso_e_espacos(self):
        q1 = q_mod.DetectedQuestion(label="1", stem="Quanto é 3 + 4 + 5?")
        q2 = q_mod.DetectedQuestion(label="1", stem="  quanto é  3 + 4 + 5? ")
        assert q1.fingerprint == q2.fingerprint

    def test_estavel_apesar_de_pontuacao_do_ocr(self):
        """Vírgula/reticências que o OCR injota não mudam a identidade."""
        q1 = q_mod.DetectedQuestion(label="1", stem="Quanto é 3 + 4 + 5?")
        q2 = q_mod.DetectedQuestion(label="1", stem="Quanto é 3 + 4 + 5?!")
        q3 = q_mod.DetectedQuestion(label="1", stem="Quanto é 3 + 4, + 5?")
        assert q1.fingerprint == q2.fingerprint
        assert q1.fingerprint == q3.fingerprint

    def test_muda_com_questao_diferente(self):
        q1 = q_mod.DetectedQuestion(label="1", stem="Quanto é 3 + 4 + 5?")
        q2 = q_mod.DetectedQuestion(label="2", stem="Quanto é 3 + 4 + 5?")
        q3 = q_mod.DetectedQuestion(label="1", stem="Qual a capital do Brasil?")
        assert q1.fingerprint != q2.fingerprint
        assert q1.fingerprint != q3.fingerprint

    def test_to_dict_leva_fingerprint(self):
        q = q_mod.DetectedQuestion(label="1", stem="Quanto é 3 + 4 + 5?")
        assert q.to_dict()["fingerprint"] == q.fingerprint

    def test_text_fingerprint_estavel(self):
        a = q_mod.text_fingerprint("Questão 1\nQuanto é 3 + 4 + 5?")
        b = q_mod.text_fingerprint("questão  1 quanto é 3 + 4 + 5?")
        c = q_mod.text_fingerprint("outro texto")
        assert a == b
        assert a != c


# ── Varredura leve (loop ao vivo) ──────────────────────────────────


def _patches_tela(ocr_text=OCR_QUESTOES, janela=True):
    """Context manager com captura/monitores/janela/OCR patchados."""

    from contextlib import ExitStack, contextmanager

    @contextmanager
    def _cm():
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.vision.screen.ScreenManager.capture_monitor",
                    return_value=_imagem_questoes(),
                )
            )
            stack.enter_context(
                patch("app.vision.screen._discover_monitors", return_value=_tres_monitores())
            )
            stack.enter_context(
                patch(
                    "app.vision.window.active_window",
                    return_value={
                        "title": "Exercícios",
                        "app": "chrome",
                        "left": 2000,
                        "top": 0,
                        "width": 1000,
                        "height": 800,
                    }
                    if janela
                    else None,
                )
            )
            mock_ocr = stack.enter_context(patch("app.agent.agent.ocr"))
            mock_ocr.available.return_value = True
            mock_ocr.read_text.return_value = ocr_text
            mock_chat = stack.enter_context(patch("app.agent.agent.chat"))
            yield mock_chat

    return _cm()


class TestDetectScreenQuestions:
    def test_varredura_leve_sem_chamar_o_modelo(self):
        with _patches_tela() as mock_chat:
            agent = StudyAgent()
            result = agent.detect_screen_questions()

        assert len(result["questions"]) == 2
        assert all(q["fingerprint"] for q in result["questions"])
        assert result["fingerprint"]
        assert result["monitor"] == 1
        assert result["session_id"] is None  # varredura não cria sessão
        mock_chat.assert_not_called()

    def test_sem_questoes_devolve_lista_vazia(self):
        with _patches_tela(ocr_text="Arquivo Editar Exibir Ajuda", janela=False):
            agent = StudyAgent()
            result = agent.detect_screen_questions()

        assert result["questions"] == []
        assert result["fingerprint"]

    def test_fingerprint_das_questoes_e_estavel_entre_varreduras(self):
        with _patches_tela():
            agent = StudyAgent()
            primeira = agent.detect_screen_questions()
            segunda = agent.detect_screen_questions()

        assert [q["fingerprint"] for q in primeira["questions"]] == [
            q["fingerprint"] for q in segunda["questions"]
        ]
        assert primeira["fingerprint"] == segunda["fingerprint"]

    def test_fingerprint_da_tela_muda_quando_o_conteudo_muda(self):
        with _patches_tela(ocr_text=OCR_QUESTOES):
            primeira = StudyAgent().detect_screen_questions()
        with _patches_tela(ocr_text=OCR_QUESTOES + "\nQuestão 3\n1 + 1 = ?\na) 1\nb) 2"):
            segunda = StudyAgent().detect_screen_questions()

        assert primeira["fingerprint"] != segunda["fingerprint"]
        assert len(segunda["questions"]) == 3


# ── Rota POST /api/screen/detect ───────────────────────────────────


class TestRotaScreenDetect:
    def test_detect_responde_com_questoes_e_sem_modelo(self):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)

        with _patches_tela() as mock_chat:
            resp = client.post("/api/screen/detect", json={"monitor": None})

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["questions"]) == 2
        assert all(q["fingerprint"] for q in data["questions"])
        assert data["fingerprint"]
        mock_chat.assert_not_called()

    def test_detect_sem_permissao_retorna_403(self):
        from fastapi.testclient import TestClient

        from app.main import app
        from app.security.permissions import PermissionDeniedError

        client = TestClient(app)

        with (
            _patches_tela(),
            patch(
                "app.security.permissions.PermissionManager.require",
                side_effect=PermissionDeniedError("screen_capture negado"),
            ),
        ):
            resp = client.post("/api/screen/detect", json={})

        assert resp.status_code == 403
