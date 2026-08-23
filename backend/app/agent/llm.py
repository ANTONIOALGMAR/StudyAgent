import base64

import ollama

from ..config import OLLAMA_HOST, TEXT_MODEL, VISION_MODEL

_client = ollama.Client(host=OLLAMA_HOST)


def available_models():
    return [m.model for m in _client.list().models]


TEXT_CONTEXT_TOKENS = 16384
VISION_CONTEXT_TOKENS = 8192


def chat(messages, images=None):
    if images:
        messages = _attach_images(messages, images)
        model = VISION_MODEL
        num_ctx = VISION_CONTEXT_TOKENS
    else:
        model = TEXT_MODEL
        num_ctx = TEXT_CONTEXT_TOKENS
    try:
        response = _client.chat(
            model=model,
            messages=messages,
            options={"num_ctx": num_ctx},
        )
        return response["message"]["content"]
    except Exception as exc:
        msg = str(exc)
        if "context size" in msg or "exceed" in msg.lower():
            raise RuntimeError(
                "A conversa ficou longa demais para a memória do modelo. "
                "Inicie uma nova sessão ou continue com mensagens mais curtas."
            ) from exc
        raise


def _attach_images(messages, images):
    encoded = []
    for img in images:
        if isinstance(img, bytes):
            encoded.append(base64.b64encode(img).decode("utf-8"))
        elif isinstance(img, str):
            encoded.append(img)
    messages = [dict(m) for m in messages]
    messages[-1] = {**messages[-1], "images": encoded}
    return messages
