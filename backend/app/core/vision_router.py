"""Roteamento visual puro: monta as notas de contexto que acompanham
imagens (tela/câmera) enviadas ao modelo.

Sem efeitos colaterais — a captura e o OCR acontecem fora (agent/vision);
aqui só se decide formato e se vale anexar o texto detectado.
"""

MIN_OCR_CHARS = 60
MAX_OCR_CHARS = 2500


def build_image_note(camera: bool, monitor=None, size=None) -> str:
    """Nota explicando a origem da(s) imagem(ns) anexada(s)."""
    if camera:
        return (
            "(A imagem anexada é uma foto tirada pela minha câmera. Se a "
            "pergunta for sobre o conteúdo dela, responda com base NA IMAGEM.)"
        )
    origem = f"captura do meu monitor {monitor}" if monitor else "captura da minha tela"
    dim = f" ({size[0]}x{size[1]} pixels)" if size else ""
    return (
        f"(A imagem anexada é uma {origem}{dim}. Se a pergunta for sobre a "
        "tela ou o que está visível nela, responda com base NA IMAGEM.)"
    )


def decide_ocr_block(ocr_text: str | None) -> str | None:
    """Retorna bloco com o texto do OCR quando ele agrega (texto denso)."""
    if not ocr_text:
        return None
    texto = ocr_text.strip()
    if len(texto) < MIN_OCR_CHARS:
        return None
    if len(texto) > MAX_OCR_CHARS:
        texto = texto[:MAX_OCR_CHARS] + "\n[…]"
    return (
        "TEXTO DETECTADO POR OCR NA IMAGEM (confiável para nomes, números "
        "e símbolos; ignore erros óbvios de leitura):\n\n"
        f"{texto}"
    )


def format_window_note(window: dict | None) -> str | None:
    """Contexto da janela ativa, quando o ambiente consegue informá-la."""
    if not window:
        return None
    app = window.get("app")
    title = window.get("title")
    partes = []
    if app:
        partes.append(f"aplicativo: {app}")
    if title:
        partes.append(f"janela: {title}")
    if not partes:
        return None
    return "(Janela ativa do usuário no momento da captura — " + "; ".join(partes) + ".)"
