import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from atendimento_eval import compare, evaluate, evaluate_all, load_conversations, load_rubric, summarize
from atendimento_eval.checks import check_dados_pessoais, check_saudacao
from atendimento_eval.cli import DEFAULT_RUBRIC
from atendimento_eval.judge import ClaudeJudge
from atendimento_eval.models import Conversation

DATA = Path(__file__).parent.parent / "data"


def conv(agent_text: str) -> Conversation:
    return Conversation(id="t", turns=[
        {"role": "cliente", "text": "Preciso de ajuda"},
        {"role": "atendente", "text": agent_text},
    ])


@pytest.mark.parametrize("texto", ["Seu CPF é 123.456.789-09", "cartão 4111 1111 1111 1111", "mande para ana@x.com"])
def test_pii_is_flagged(texto):
    assert not check_dados_pessoais(conv(texto)).aprovado


def test_masked_data_is_ok():
    assert check_dados_pessoais(conv("O e-mail termina em ***@email.com e o CPF começa com 123")).aprovado


def test_greeting_ignores_accents_and_case():
    assert check_saudacao(conv("BOM DIA! Tudo bem?")).aprovado
    assert not check_saudacao(conv("Verifiquei aqui.")).aprovado
    assert not check_saudacao(conv("O cartão foi desbloqueado.")).aprovado  # "oi" dentro de "foi"


def test_critical_failure_zeroes_score():
    result = evaluate(conv("Olá! Seu CPF é 123.456.789-09. Posso ajudar em algo mais?"), load_rubric(DEFAULT_RUBRIC))
    assert result.reprovada_por_critico and result.nota_final == 0.0


def test_v2_beats_v1_without_regressions():
    criteria = load_rubric(DEFAULT_RUBRIC)
    v1 = summarize(evaluate_all(load_conversations(DATA / "conversas_v1.jsonl"), criteria))
    v2 = summarize(evaluate_all(load_conversations(DATA / "conversas_v2.jsonl"), criteria))
    diff = compare(v1, v2)
    assert v1["reprovadas_por_critico"] == 3 and v2["reprovadas_por_critico"] == 0
    assert diff["delta_nota_media"] > 0 and diff["regressoes"] == []


def test_claude_judge_with_fake_client():
    payload = {"avaliacoes": [
        {"criterio": "resolucao", "nota": 5, "justificativa": "resolveu", "evidencia": "Já desbloqueei"},
        {"criterio": "empatia", "nota": 2, "justificativa": "seco", "evidencia": "Verifiquei aqui"},
    ]}
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(payload))])

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    criteria = [c for c in load_rubric(DEFAULT_RUBRIC) if c.tipo == "llm"]
    results = {r.criterio: r for r in ClaudeJudge(client=client)(conv("Olá! Já desbloqueei."), criteria)}

    assert results["resolucao"].aprovado and results["resolucao"].nota == 1.0
    assert not results["empatia"].aprovado
    assert results["clareza"].justificativa == "O juiz não avaliou este critério."
    assert calls[0]["fallbacks"] == "default"
