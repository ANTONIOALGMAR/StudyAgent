"""Model Manager V2 — seleção e descoberta de modelos.

Todos os modelos são configuráveis por variáveis de ambiente (backend/.env),
sem tocar no código. Detecta o que está disponível no Ollama e faz fallback
inteligente quando um modelo configurado não existe.
"""

import os

import ollama

from ..config import OLLAMA_HOST

_client = ollama.Client(host=OLLAMA_HOST)

# Ambiente -> finalidade. Fallbacks mantêm compatibilidade com a V1.
MODEL_ROLES = {
    "text": ("STUDY_TEXT_MODEL", "llama3.1"),
    "vision": ("STUDY_VISION_MODEL", "qwen2.5vl:7b"),
    "synthesis": ("STUDY_SYNTH_MODEL", "qwen2.5vl:7b"),
    "embedding": ("STUDY_EMBEDDING_MODEL", "nomic-embed-text"),
    "stt": ("STUDY_STT_MODEL", "small"),
    "tts": ("STUDY_TTS_MODEL", "pt_BR-faber-medium"),
}

_context_tokens = {
    "text": int(os.getenv("STUDY_TEXT_CTX", "16384")),
    "vision": int(os.getenv("STUDY_VISION_CTX", "16384")),
    "synthesis": int(os.getenv("STUDY_SYNTH_CTX", "16384")),
}


def num_predict() -> int:
    """Teto de tokens gerados por resposta (evita cortes no meio)."""
    return int(os.getenv("STUDY_NUM_PREDICT", "2048"))


def model(role: str) -> str:
    """Nome do modelo para uma finalidade (configurável por env)."""
    try:
        env_name, default = MODEL_ROLES[role]
    except KeyError as exc:
        raise ValueError(f"Função de modelo desconhecida: {role!r}") from exc
    return os.getenv(env_name, default)


def context_tokens(role: str) -> int:
    return _context_tokens.get(role, 8192)


def available_models() -> list[str]:
    """Modelos presentes no Ollama neste momento."""
    try:
        return [m.model for m in _client.list().models]
    except Exception:
        return []


def resolve(role: str) -> str:
    """Modelo da função; se não existir no Ollama, tenta fallback útil."""
    wanted = model(role)
    avail = available_models()
    if not avail or any(a.startswith(wanted) for a in avail):
        return wanted
    if role == "synthesis":
        # síntese aceita qualquer modelo visão ou texto disponível
        vision = model("vision")
        text = model("text")
        for candidate in (vision, text):
            if any(a.startswith(candidate) for a in avail):
                return candidate
    return wanted


def hardware_summary() -> dict:
    """Resumo leve do ambiente para diagnóstico (/api/models)."""
    import platform
    import shutil

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "ollama_host": OLLAMA_HOST,
        "ollama_reachable": bool(available_models()),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "roles": {role: resolve(role) for role in MODEL_ROLES},
    }
