import base64

import ollama

from ..config import OLLAMA_HOST, TEXT_MODEL, VISION_MODEL

_client = ollama.Client(host=OLLAMA_HOST)


def available_models():
    return [m.model for m in _client.list().models]


def chat(messages, images=None):
    if images:
        messages = _attach_images(messages, images)
        model = VISION_MODEL
    else:
        model = TEXT_MODEL
    response = _client.chat(model=model, messages=messages)
    return response["message"]["content"]


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
