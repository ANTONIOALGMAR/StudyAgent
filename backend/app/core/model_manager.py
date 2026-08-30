"""Model Manager V2 — seleção e descoberta de modelos.

Todos os modelos são configuráveis por variáveis de ambiente (backend/.env),
sem tocar no código. Detecta o que está disponível no Ollama e faz fallback
inteligente quando um modelo configurado não existe.
"""

import os
import psutil
import platform
import shutil

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

# Sugestões de modelos baseadas em RAM (GB)
HARDWARE_RECOMMENDATIONS = {
    "text": {
        "low": "phi3",        # < 8GB
        "medium": "llama3.1", # 8GB - 16GB
        "high": "llama3.1:70b" # > 16GB
    },
    "vision": {
        "low": "moondream",    # < 8GB
        "medium": "qwen2.5vl:7b", # 8GB - 16GB
        "high": "llava-v1.6"   # > 16GB
    }
}

_context_tokens = {
    "text": int(os.getenv("STUDY_TEXT_CTX", "16384")),
    "vision": int(os.getenv("STUDY_VISION_CTX", "16384")),
    "synthesis": int(os.getenv("STUDY_SYNTH_CTX", "16384")),
}


def num_predict() -> int:
    """Teto de tokens gerados por resposta (evita cortes no meio)."""
    return int(os.getenv("STUDY_NUM_PREDICT", "2048"))


def vision_temperature() -> float:
    """Temperatura para o modelo de visão.

    Valor baixo reduz alucinação e confabulação. Configurável por env
    (STUDY_VISION_TEMPERATURE). Ollama usa 0.8 por padrão.
    """
    return float(os.getenv("STUDY_VISION_TEMPERATURE", "0.2"))


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


def _matching_available(wanted: str, avail: list[str]) -> str | None:
    """Retorna o nome (com tag) do modelo disponível que corresponde ao
    configurado (ex.: 'llama3.1' → 'llama3.1:latest')."""
    if wanted in avail:
        return wanted
    for a in avail:
        if a.startswith(wanted + ":"):
            return a
    return None


def resolve(role: str) -> str:
    """Modelo da função; se não existir no Ollama, tenta fallback útil.

    Retorna o nome EXATO disponível no Ollama (incluindo a tag,
    ex.: 'llama3.1:latest'), evitando erro 404 do modelo sem tag.
    """
    # Hardware-aware selection: se não houver override no .env, sugere modelo por RAM
    wanted = model(role)
    
    # Se o modelo for o default e for de texto/visão, checamos a RAM
    if wanted in [r[1] for r in MODEL_ROLES.values()] and role in HARDWARE_RECOMMENDATIONS:
        ram_gb = psutil.virtual_memory().total / (1024**3)
        if ram_gb < 8:
            wanted = HARDWARE_RECOMMENDATIONS[role]["low"]
        elif ram_gb < 16:
            wanted = HARDWARE_RECOMMENDATIONS[role]["medium"]
        else:
            wanted = HARDWARE_RECOMMENDATIONS[role]["high"]

    avail = available_models()
    if not avail:
        return wanted
    matched = _matching_available(wanted, avail)
    if matched is not None:
        return matched
    if role == "synthesis":
        # síntese aceita qualquer modelo visão ou texto disponível
        vision = model("vision")
        text = model("text")
        for candidate in (vision, text):
            hit = _matching_available(candidate, avail)
            if hit is not None:
                return hit
    return wanted


def hardware_summary() -> dict:
    """Resumo leve do ambiente para diagnóstico (/api/models)."""
    import platform
    import shutil

    ram_gb = psutil.virtual_memory().total / (1024**3)
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "ram_gb": round(ram_gb, 2),
        "ollama_host": OLLAMA_HOST,
        "ollama_reachable": bool(available_models()),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "roles": {role: resolve(role) for role in MODEL_ROLES},
    }
