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
            "[IMAGEM ANEXADA — FOTO DA CÂMERA]\n"
            "INSTRUÇÃO: Analise esta foto. O que você vê? Descreva o conteúdo.\n"
            "Responda sobre o conteúdo da imagem, não dê saudação."
        )
    origem = f"monitor {monitor}" if monitor else "tela"
    dim = f" ({size[0]}x{size[1]})" if size else ""
    return (
        f"[CONTEÚDO VISUAL DA TELA — ANALISE ANTES DE RESPONDER]\n"
        f"Tipo: Captura de {origem}{dim}\n"
        f"\n"
        f"INSTRUÇÕES OBRIGATÓRIAS:\n"
        f"1. PRIMEIRO: olhe a imagem e descreva o que vê\n"
        f"2. SEGUNDO: identifique aplicação, conteúdo, exercícios, erros, código, texto\n"
        f"3. TERCEIRO: responda à pergunta do usuário sobre o conteúdo da tela\n"
        f"\n"
        f"Se houver EXERCÍCIO ou QUESTÃO: leia o enunciado e resolva ou guie o aluno\n"
        f"Se houver ERRO: identifique e explique como resolver\n"
        f"Se houver CÓDIGO: leia e analise\n"
        f"Se houver TEXTO: descreva e responda sobre ele\n"
        f"\n"
        f"NÃO dê saudação. NÃO pergunte 'como posso ajudar'. APERTE O OLHAR NA IMAGEM.\n"
        f"[FIM DAS INSTRUÇÕES VISUAIS]"
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
