import base64

import ollama

from ..config import OLLAMA_HOST
from ..core.model_manager import context_tokens, resolve

_client = ollama.Client(host=OLLAMA_HOST)


def available_models():
    return [m.model for m in _client.list().models]


def chat(messages, images=None):
    if images:
        messages = _attach_images(messages, images)
        role = "vision"
    else:
        role = "text"
    try:
        response = _client.chat(
            model=resolve(role),
            messages=messages,
            options={"num_ctx": context_tokens(role)},
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


def chat_with_tools(messages, tools):
    response = _client.chat(
        model=resolve("text"),
        messages=messages,
        tools=tools,
        options={"num_ctx": context_tokens("text")},
    )
    message = response["message"]
    tool_calls = [
        {
            "function": {
                "name": tc.function.name,
                "arguments": dict(tc.function.arguments or {}),
            }
        }
        for tc in (message.tool_calls or [])
    ]
    return {"content": message.content or "", "tool_calls": tool_calls}


SYNTH_SYSTEM = (
    "Você responde perguntas em português usando APENAS o material pesquisado "
    "fornecido pelo usuário. Cite as fontes usadas no formato [fonte: URL]. "
    "ATENÇÃO à desambiguação: se houver clubes, pessoas ou empresas com nomes "
    "parecidos no material, use somente as fontes que corresponderem "
    "exatamente à entidade da pergunta (contexto, tamanho, liga conhecidas). "
    "Ignore clubes pequenos homônimos. Prefira sempre os dados mais recentes "
    "e confira se a data é coerente com hoje. "
    "Se o material não contiver a resposta confiável, diga claramente que não "
    "encontrou. Nunca invente fatos."
)


def synthesize(question: str, material: str) -> str:
    response = _client.chat(
        model=resolve("synthesis"),
        messages=[
            {"role": "system", "content": SYNTH_SYSTEM},
            {
                "role": "user",
                "content": f"Pergunta: {question}\n\nMaterial da pesquisa:\n{material}",
            },
        ],
        options={"num_ctx": context_tokens("text")},
    )
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
