"""Orquestra a avaliação: carrega rubrica e conversas, roda checagens e juiz, agrega resultados."""

import json
from pathlib import Path

import yaml

from .checks import CHECKS
from .judge import Judge
from .models import Conversation, ConversationResult, Criterion, CriterionResult


def load_rubric(path: str | Path) -> list[Criterion]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    criteria = [Criterion(**c) for c in data["criterios"]]
    unknown = [c.id for c in criteria if c.tipo == "deterministico" and c.id not in CHECKS]
    if unknown:
        raise ValueError(f"Critérios determinísticos sem checagem implementada: {unknown}")
    return criteria


def load_conversations(path: str | Path) -> list[Conversation]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [Conversation.model_validate(json.loads(line)) for line in lines if line.strip()]


def evaluate(conv: Conversation, criteria: list[Criterion], judge: Judge | None = None) -> ConversationResult:
    results: list[CriterionResult] = [CHECKS[c.id](conv) for c in criteria if c.tipo == "deterministico"]
    llm_criteria = [c for c in criteria if c.tipo == "llm"]
    if llm_criteria and judge is not None:
        results += judge(conv, llm_criteria)

    weights = {c.id: c.peso for c in criteria}
    total = sum(weights[r.criterio] for r in results)
    nota = sum(weights[r.criterio] * r.nota for r in results) / total if total else 0.0

    criticos = {c.id for c in criteria if c.critico}
    reprovada = any(r.criterio in criticos and not r.aprovado for r in results)
    return ConversationResult(
        conversation_id=conv.id,
        nota_final=0.0 if reprovada else round(nota, 3),
        reprovada_por_critico=reprovada,
        resultados=results,
    )


def evaluate_all(convs: list[Conversation], criteria: list[Criterion], judge: Judge | None = None) -> list[ConversationResult]:
    return [evaluate(c, criteria, judge) for c in convs]


def summarize(results: list[ConversationResult]) -> dict:
    """Taxa de aprovação por critério, nota média e piores conversas."""
    by_criterion: dict[str, list[bool]] = {}
    for r in results:
        for cr in r.resultados:
            by_criterion.setdefault(cr.criterio, []).append(cr.aprovado)
    return {
        "conversas": len(results),
        "nota_media": round(sum(r.nota_final for r in results) / len(results), 3) if results else 0.0,
        "reprovadas_por_critico": sum(r.reprovada_por_critico for r in results),
        "aprovacao_por_criterio": {k: round(sum(v) / len(v), 3) for k, v in sorted(by_criterion.items())},
        "piores": [r.conversation_id for r in sorted(results, key=lambda r: r.nota_final) if r.nota_final < 1][:3],
    }


def compare(before: dict, after: dict) -> dict:
    """Compara dois resumos (ex.: bot com prompt v1 × v2) e aponta melhoras e regressões."""
    deltas = {}
    for crit in sorted(set(before["aprovacao_por_criterio"]) | set(after["aprovacao_por_criterio"])):
        a = before["aprovacao_por_criterio"].get(crit, 0.0)
        b = after["aprovacao_por_criterio"].get(crit, 0.0)
        deltas[crit] = round(b - a, 3)
    return {
        "delta_nota_media": round(after["nota_media"] - before["nota_media"], 3),
        "delta_por_criterio": deltas,
        "regressoes": [c for c, d in deltas.items() if d < 0],
    }
