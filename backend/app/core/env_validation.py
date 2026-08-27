"""Environment Validation — valida configurações na inicialização.

Verifica: Python version, dependências, Ollama, Tesseract, permissões, disk space.
Fallo Fatal se required deps faltam; Warning se optional deps faltam.
"""

from __future__ import annotations

import logging
import shutil
import sys

log = logging.getLogger("studyagent.env")

REQUIRED = {
    "python": (3, 10),
}


def check_python_version() -> bool:
    major, minor = sys.version_info[:2]
    req_major, req_minor = REQUIRED["python"]
    if (major, minor) < (req_major, req_minor):
        log.error("[ENV] Python %d.%d+ required, got %d.%d", req_major, req_minor, major, minor)
        return False
    log.info("[ENV] Python %d.%d ✓", major, minor)
    return True


def check_command(name: str) -> bool:
    found = shutil.which(name) is not None
    if found:
        log.info("[ENV] %s found ✓", name)
    else:
        log.warning("[ENV] %s not found (optional)", name)
    return found


def check_ollama() -> bool:
    try:
        from .model_manager import _run_ollama_cmd
        result = _run_ollama_cmd(["list"])
        if result:
            log.info("[ENV] Ollama running ✓")
            return True
        log.warning("[ENV] Ollama installed but not running")
        return False
    except Exception:
        log.warning("[ENV] Ollama not available (optional)")
        return False


def check_disk_space(path: str = ".", min_mb: int = 100) -> bool:
    try:
        usage = shutil.disk_usage(path)
        free_mb = usage.free / (1024 * 1024)
        if free_mb < min_mb:
            log.warning("[ENV] Low disk space: %.0f MB free (min: %d MB)", free_mb, min_mb)
            return False
        log.info("[ENV] Disk space: %.0f MB free ✓", free_mb)
        return True
    except Exception:
        log.warning("[ENV] Cannot check disk space")
        return True


def check_data_dirs() -> bool:
    from . import DATA_DIR, MEMORY_DB_PATH
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        MEMORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        log.info("[ENV] Data dirs ready ✓")
        return True
    except Exception as exc:
        log.error("[ENV] Cannot create data dirs: %s", exc)
        return False


def validate_environment() -> dict:
    """Roda todas as verificações e retorna resumo."""
    results = {}
    results["python"] = check_python_version()
    results["tesseract"] = check_command("tesseract")
    results["ollama"] = check_ollama()
    results["disk"] = check_disk_space()
    results["data_dirs"] = check_data_dirs()

    critical = [k for k, v in results.items() if not v and k in ("python", "data_dirs")]
    if critical:
        log.error("[ENV] CRITICAL failures: %s — system may not work", critical)

    return results
