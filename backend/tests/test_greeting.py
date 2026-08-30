"""Testes de saudação/social greeting — evita tool-calling em conversa casual.

Regressão: "Oi, tá me ouvindo?" deveria ir para o chat de texto simples (sem
tool-calling), evitando respostas confabulando sobre JSON.
"""

from app.core.planner import is_social_greeting

GREETINGS = [
    "Oi",
    "olá",
    "Oi, tá me ouvindo?",
    "Oi, tá me escutando?",
    "Olá, consegue me ouvir?",
    "oi me escuta?",
    "bom dia, está por aí?",
    "Oi, tá funcionando?",
    "oi tudo bem?",
    "oi, e aí?",
    "e aí, blz?",
]

NOT_GREETINGS = [
    "",
    "o que é python?",
    "busque sobre palmeiras",
    "quanto é 2+2?",
    "leia o monitor 2",
    "abre o navegador",
    "oi, me dá o resultado do jogo?",
    "oi me mostra o que tem no monitor",
    "resuma o documento",
]


class TestSocialGreeting:
    def test_greetings_are_social(self):
        for msg in GREETINGS:
            assert is_social_greeting(msg), f"deveria ser saudação: {msg!r}"

    def test_non_greetings_not_social(self):
        for msg in NOT_GREETINGS:
            assert not is_social_greeting(msg), f"não deveria ser saudação: {msg!r}"

    def test_reported_bug_case(self):
        """Bug reportado: 'Oi, tá me ouvindo?' respondia sobre JSON."""
        assert is_social_greeting("Oi, tá me ouvindo?") is True
