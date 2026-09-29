"""Juiz LLM: avalia os critérios que exigem interpretação (resolução, empatia, clareza).

O juiz recebe a rubrica e a transcrição e devolve, para cada critério, uma nota de 1 a 5,
uma justificativa e o trecho da conversa usado como evidência (saída em JSON Schema).
"""

import json
import os
from typing import Protocol

import anthropic
from pydantic import BaseModel, ConfigDict

from .models import Conversation, Criterion, CriterionResult

MODEL = os.getenv("ATENDIMENTO_EVAL_MODEL", "claude-opus-5-5")
PASS_THRESHOLD = 4  # nota >= 4 (de 1 a 5) conta como aprovado

SYSTEM_PROMPT = """Você é um auditor de qualidade de atendimento ao cliente de um banco digital. \
Avalie a conversa APENAS pelos critérios fornecidos, com notas de 1 (péssimo) a 5 (excelente).

Seja rigoroso e consistente:
- Baseie cada nota em evidências da transcrição e cite o trecho exato usado.
- Não premie tamanho de resposta; premie resolução, clareza e empatia genuína.
- Se o atendente prometeu algo que não pode cumprir ou deu informação incorreta, penalize."""


class JudgeScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterio: str
    nota: int
    justificativa: str
    evidencia: str


class JudgeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    avaliacoes: list[JudgeScore]


class Judge(Protocol):
    def __call__(self, conv: Conversation, criteria: list[Criterion]) -> list[CriterionResult]: ...


class RefusalError(RuntimeError):
    pass


def build_prompt(conv: Conversation, criteria: list[Criterion]) -> str:
    rubrica = "\n".join(f"- {c.id}: {c.descricao}" for c in criteria)
    return f"<rubrica>\n{rubrica}\n</rubrica>\n\n<conversa canal=\"{conv.canal}\">\n{conv.as_transcript()}\n</conversa>"


class ClaudeJudge:
    def __init__(self, client: anthropic.Anthropic | None = None, model: str = MODEL):
        self.client = client or anthropic.Anthropic()
        self.model = model

    def __call__(self, conv: Conversation, criteria: list[Criterion]) -> list[CriterionResult]:
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": JudgeOutput.model_json_schema()},
            },
            messages=[{"role": "user", "content": build_prompt(conv, criteria)}],
        )
        if response.stop_reason == "refusal":
            raise RefusalError(f"O juiz recusou avaliar a conversa {conv.id}.")
        text = next(block.text for block in response.content if block.type == "text")
        return to_results(JudgeOutput.model_validate(json.loads(text)), criteria)


def to_results(output: JudgeOutput, criteria: list[Criterion]) -> list[CriterionResult]:
    """Converte notas 1-5 em 0-1 e garante um resultado por critério pedido."""
    by_id = {s.criterio: s for s in output.avaliacoes}
    results = []
    for c in criteria:
        score = by_id.get(c.id)
        if score is None:
            results.append(CriterionResult(criterio=c.id, nota=0.0, aprovado=False,
                                           justificativa="O juiz não avaliou este critério."))
            continue
        nota = min(max(score.nota, 1), 5)
        results.append(CriterionResult(
            criterio=c.id,
            nota=round((nota - 1) / 4, 2),
            aprovado=nota >= PASS_THRESHOLD,
            justificativa=f"{score.justificativa} (evidência: \"{score.evidencia}\")",
        ))
    return results
