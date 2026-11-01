"""Cada checagem determinística com um caso que passa e um que falha."""

from atendimento_eval.checks import (
    CHECKS,
    check_dados_pessoais,
    check_encerramento,
    check_linguagem,
    check_saudacao,
)
from atendimento_eval.models import Conversation


def conv(*falas: tuple[str, str]) -> Conversation:
    return Conversation(id="t", turns=[{"role": r, "text": t} for r, t in falas])


def test_saudacao_passa_e_falha():
    assert check_saudacao(conv(("cliente", "oi"), ("atendente", "Olá, tudo bem?"))).aprovado
    assert not check_saudacao(conv(("cliente", "oi"), ("atendente", "Qual o seu problema?"))).aprovado


def test_saudacao_nao_casa_dentro_de_outra_palavra():
    # "oi" não pode casar dentro de "foi"
    assert not check_saudacao(conv(("cliente", "oi"), ("atendente", "Isso foi resolvido."))).aprovado


def test_saudacao_sem_atendente_reprova():
    assert not check_saudacao(conv(("cliente", "alguém aí?"))).aprovado


def test_encerramento_passa_e_falha():
    assert check_encerramento(conv(("atendente", "Posso ajudar em algo mais?"))).aprovado
    assert not check_encerramento(conv(("atendente", "Certo."))).aprovado


def test_encerramento_olha_so_a_ultima_fala_do_atendente():
    c = conv(("atendente", "Posso ajudar em algo mais?"), ("cliente", "sim"), ("atendente", "Certo."))
    assert not check_encerramento(c).aprovado


def test_dados_pessoais_detecta_cpf_cartao_e_email():
    for texto in ("Seu CPF é 123.456.789-09", "Cartão 4111 1111 1111 1111", "Escreva para ana@exemplo.com.br"):
        r = check_dados_pessoais(conv(("atendente", texto)))
        assert not r.aprovado and r.nota == 0.0


def test_dados_pessoais_ignora_o_que_o_cliente_escreve():
    assert check_dados_pessoais(conv(("cliente", "meu CPF é 123.456.789-09"), ("atendente", "Obrigado."))).aprovado


def test_linguagem_passa_e_falha():
    assert check_linguagem(conv(("atendente", "Vou verificar para você."))).aprovado
    r = check_linguagem(conv(("atendente", "Isso é com você, não é problema meu.")))
    assert not r.aprovado and "linguagem" in r.criterio


def test_linguagem_ignora_acentos_e_caixa():
    assert not check_linguagem(conv(("atendente", "Não é problema meu"))).aprovado


def test_registro_tem_as_quatro_checagens():
    assert set(CHECKS) == {"saudacao", "encerramento", "dados_pessoais", "linguagem"}
