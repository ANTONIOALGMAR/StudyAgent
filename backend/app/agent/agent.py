import base64

from ..security.permissions import PermissionDeniedError
from ..tools import calculator
from ..vision import ocr, screen
from .llm import available_models, chat
from .memory import Memory

SYSTEM_PROMPT = """Você é o StudyAgent, um tutor pessoal de estudos que roda localmente no computador do usuário.

Diretrizes:
- Responda SEMPRE em português do Brasil, de forma clara e didática.
- Modo padrão é TUTOR: guie o aluno passo a passo com perguntas e pistas, em vez de entregar a resposta final pronta.
- Se o usuário pedir explicitamente ("me dê a resposta", "resolva direto"), aí sim entregue a solução completa.
- Quando receber uma imagem da tela, descreva primeiro o que você identificou (matéria, tipo de conteúdo) antes de explicar.
- Use cálculos exatos quando possível e mostre o raciocínio.
- Se não tiver certeza sobre algo que viu na tela, diga o que vê e peça confirmação.
- Seja encorajador, mas honesto: aponte erros com clareza.

Modos disponíveis (o usuário pode pedir):
- professor: explicação detalhada do zero
- tutor: pistas e condução sem dar a resposta
- exercicios: gerar exercícios parecidos
- revisao: fazer perguntas para checar aprendizado
- resumo: condensar material
- simples: explicar como para um iniciante"""


class StudyAgent:
    def __init__(self):
        self.memory = Memory()

    def process(
        self,
        message,
        session_id=None,
        use_screen=False,
        region=None,
        monitor=1,
        image_b64=None,
    ):
        session_id = self.memory.get_or_create_session(session_id)
        tools_used = []
        images = []

        if use_screen:
            self._require("screen_capture")
            shot = screen.capture(monitor=monitor, region=region)
            images.append(screen.image_to_base64(shot))
            tools_used.append("screen_capture")

        if image_b64:
            if isinstance(image_b64, str):
                image_b64 = base64.b64decode(image_b64)
            images.append(image_b64)
            tools_used.append("image_input")

        enriched_message = message
        if use_screen and not any(
            kw in message.lower() for kw in ("tela", "questão", "questao", "imagem", "vê", "ve")
        ):
            enriched_message = f"{message}\n\n(A imagem anexada é uma captura da minha tela.)"

        history = self.memory.history(session_id, limit=8)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
        messages.append({"role": "user", "content": enriched_message})

        response_text = chat(messages, images=images or None)

        self.memory.add_message(session_id, "user", message)
        self.memory.add_message(session_id, "assistant", response_text)

        return {
            "session_id": session_id,
            "response": response_text,
            "tools_used": tools_used,
        }

    def capture_and_read_screen(self, region=None, monitor=1):
        self._require("screen_capture")
        shot = screen.capture(monitor=monitor, region=region)
        result = {"ocr_available": ocr.available()}
        if ocr.available():
            try:
                result["text"] = ocr.read_text(shot)
            except Exception as exc:
                result["text"] = ""
                result["ocr_error"] = str(exc)
        else:
            result["text"] = ""
        return shot, result

    def analyze_screen(self, question, session_id=None, region=None, monitor=1):
        self._require("screen_capture")
        shot, _ = self.capture_and_read_screen(region=region, monitor=monitor)
        image_bytes = screen.image_to_base64(shot)
        prompt = question or (
            "Analise esta captura de tela. Identifique a matéria e o conteúdo "
            "(exercício, texto, gráfico, código...) e explique de forma didática."
        )
        return self.process(prompt, session_id=session_id, image_b64=image_bytes)

    def calculate(self, expression):
        return calculator.calculate(expression)

    def status(self):
        return {
            "models": available_models(),
            "ocr_available": ocr.available(),
        }

    @staticmethod
    def _require(name):
        from ..security.permissions import PermissionManager

        PermissionManager().require(name)


__all__ = ["StudyAgent", "PermissionDeniedError"]
