"""Testes do normalizador ortográfico pós-STT (app/audio/orthography.py)."""

from app.audio.orthography import _parece_pergunta, fix_orthography


class TestFixOrthography:
    def test_question_gets_question_mark_and_capital(self):
        assert fix_orthography("o que é fotossíntese") == "O que é fotossíntese?"
        assert fix_orthography("como resolvo essa equação") == "Como resolvo essa equação?"

    def test_existing_punctuation_is_kept_single(self):
        assert fix_orthography("o que é fotossíntese?") == "O que é fotossíntese?"
        assert fix_orthography("o que é fotossíntese ?") == "O que é fotossíntese?"

    def test_statement_gets_period(self):
        assert fix_orthography("me explica a regra de três por favor") == (
            "Me explica a regra de três por favor."
        )

    def test_informal_forms_are_normalized(self):
        assert fix_orthography("vc pode me ajudar com fração") == (
            "Você pode me ajudar com fração."
        )
        assert fix_orthography("nao entendi oq é fração") == "Não entendi o que é fração."

    def test_whitespace_collapsed(self):
        assert fix_orthography("  o   que   é    luz   ") == "O que é luz?"

    def test_pergunta_detection(self):
        assert _parece_pergunta("qual é a capital do brasil")
        assert _parece_pergunta("por que o céu é azul")
        assert _parece_pergunta("você sabe o que é fotossíntese")
        assert _parece_pergunta("será que chove amanhã")
        assert not _parece_pergunta("a fotossíntese ocorre de dia")
        assert not _parece_pergunta("por favor, me ajude")
        assert not _parece_pergunta("não entendi o que é fração")

    def test_vc_sabe_question_mark(self):
        assert fix_orthography("vc sabe oq é fotossíntese") == (
            "Você sabe o que é fotossíntese?"
        )

    def test_force_question_mark(self):
        assert fix_orthography("vamos fazer um novo teste", força_pergunta=True) == (
            "Vamos fazer um novo teste?"
        )

    def test_no_question_word_gets_period(self):
        assert fix_orthography("vamos fazer um novo teste") == (
            "Vamos fazer um novo teste."
        )

    def test_empty_returns_empty(self):
        assert fix_orthography("") == ""
        assert fix_orthography("   ") == ""

