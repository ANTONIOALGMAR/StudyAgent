"""Response Guard — valida resposta do LLM contra evidências.

Nenhuma resposta multimodal deve ser produzida sem validação.
"""

from __future__ import annotations

import logging
import re

from .errors import HallucinationError, ValidationError
from .evidence import EvidenceStore, EvidenceType

log = logging.getLogger("studyagent.orchestrator")

# Padrões que indicam alucinação visual
_GREETING_PATTERNS = re.compile(
    r"(olá|ola|hello|hi|bom dia|boa tarde|boa noite|como posso ajudar|em que posso ajudar)",
    re.IGNORECASE,
)

# Padrões que indicam que o modelo NÃO viu a imagem
_NO_VISUAL_PATTERNS = re.compile(
    r"(não consegui (?:ver|analisar|acessar|capturar)|"
    r"não tenho acesso|"
    r"não posso ver|"
    r"imagem não (?:foi )?(?:disponível|enviada|recebida))",
    re.IGNORECASE,
)


class ResponseValidator:
    """Valida se a resposta do LLM é consistente com as evidências."""

    def __init__(self, evidence: EvidenceStore):
        self.evidence = evidence

    def validate(self, response: str, *, require_evidence: bool = True) -> list[str]:
        """Valida a resposta. Retorna lista de problemas (vazia = OK)."""
        issues: list[str] = []

        if not response or not response.strip():
            issues.append("Resposta vazia")
            return issues

        # Se há evidência de tela, verificar que a resposta não é genérica
        if self.evidence.has_screen:
            stripped = response.strip()

            # Verificar alucinação: modelo deu saudação quando havia tela
            if _GREETING_PATTERNS.match(stripped):
                first_sentence = stripped.split(".")[0][:100]
                if _GREETING_PATTERNS.match(first_sentence):
                    issues.append(
                        "ALUCINAÇÃO: modelo deu saudação quando deveria descrever conteúdo visual"
                    )

            # Verificar se o modelo disse que não viu
            if _NO_VISUAL_PATTERNS.search(stripped):
                issues.append(
                    "AVISO: modelo indica que não conseguiu processar a imagem"
                )

        # Verificar confiança mínima
        if require_evidence and self.evidence.has_screen:
            min_conf = self.evidence.min_confidence
            if min_conf < 0.3:
                issues.append(
                    f"Confiança muito baixa nas evidências: {min_conf:.2f}"
                )

        return issues

    def assert_valid(self, response: str, *, require_evidence: bool = True) -> None:
        """Levanta exceção se resposta inválida."""
        issues = self.validate(response, require_evidence=require_evidence)
        if issues:
            log.warning("[VALIDATOR] issues=%s", issues)
            # Se há alucinação, levanta HallucinationError
            hallucinations = [i for i in issues if i.startswith("ALUCINAÇÃO")]
            if hallucinations:
                raise HallucinationError("; ".join(hallucinations))
            # Outros problemas são ValidationError
            raise ValidationError("; ".join(issues))

    def response_matches_evidence(self, response: str) -> bool:
        """Verificação rápida: resposta contém algo das evidências."""
        if not self.evidence.has_screen:
            return True  # Sem evidência de tela, não validar

        response_lower = response.lower()

        # Verificar se OCR aparece na resposta
        for ev in self.evidence.ocr_evidence:
            ocr_words = [w for w in ev.content.split() if len(w) > 4]
            if ocr_words:
                matches = sum(1 for w in ocr_words if w.lower() in response_lower)
                if matches >= min(3, len(ocr_words) // 2):
                    return True

        # Verificar se monitor foi mencionado
        for ev in self.evidence.screen_evidence:
            monitor = ev.data.get("monitor")
            if monitor and f"monitor {monitor}" in response_lower:
                return True

        # Verificar se janela/aplicativo foi mencionado
        for ev in self.evidence.get_by_type(EvidenceType.WINDOW):
            app = ev.data.get("app", "")
            if app and app.lower() in response_lower:
                return True

        # Se nenhuma evidência foi cruzada, ainda pode ser válida
        # (resposta pode ser baseada em dados visuais do modelo)
        return True
