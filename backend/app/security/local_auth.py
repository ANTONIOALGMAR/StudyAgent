"""Autenticação local (token/PIN) para operações privilegiadas.

StudyAgent é um app single-user local. Ainda assim, os endpoints que ativam
permissões perigosas (controle do mouse/teclado, execução de comandos) e os
que aprovam/rejeitam propostas de automação devem exigir um PIN local,
evitando que um processo ou página maliciosa na mesma rede/máquina
ative esses recursos sem o consentimento do usuário.

O PIN é configurado via env `STUDYAGENT_PIN`. Se não estiver definido,
as operações privilegiadas retornam 401 (falta de configuração) de forma
que o operador saiba que precisa definir o PIN.
"""

from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request

PIN_ENV = "STUDYAGENT_PIN"
PIN_HEADER = "X-StudyAgent-Pin"

# Permissões consideradas perigosas: exigem consentimento adicional (PIN).
DANGEROUS_PERMISSIONS = {
    "mouse_control",
    "keyboard_control",
    "command_execution",
}


def configured() -> bool:
    return bool(os.getenv(PIN_ENV))


def _constant_time(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def verify_pin(pin: str | None) -> bool:
    expected = os.getenv(PIN_ENV)
    if not expected:
        return False
    if not pin:
        return False
    return _constant_time(pin, expected)


def require_pin(request: Request) -> None:
    """Exige header `X-StudyAgent-Pin` válido em operações privilegiadas."""
    if not verify_pin(request.headers.get(PIN_HEADER)):
        raise HTTPException(
            status_code=401,
            detail=(
                "Operação privilegiada exige PIN local. "
                "Defina STUDYAGENT_PIN no ambiente e envie o header "
                f"{PIN_HEADER}."
            ),
        )
