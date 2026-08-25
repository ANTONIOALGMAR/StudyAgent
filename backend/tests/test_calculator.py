import pytest

from app.tools.calculator import calculate


def test_operacoes_basicas():
    assert calculate("2+2") == 4
    assert calculate("10 - 4*2") == 2
    assert calculate("(3/4)*100") == 75
    assert calculate("2**10") == 1024


def test_divisao_inteira_e_modulo():
    assert calculate("7 // 2") == 3
    assert calculate("7 % 3") == 1


def test_numeros_negativos():
    assert calculate("-5 + 3") == -2


def test_divisao_por_zero_erro():
    with pytest.raises(ZeroDivisionError):
        calculate("1/0")


def test_injecao_rejeitada():
    with pytest.raises(ValueError):
        calculate("__import__('os').system('ls')")
