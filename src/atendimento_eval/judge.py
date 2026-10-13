"""Juiz LLM: avalia os critérios que exigem interpretação (resolução, empatia, clareza).

O juiz recebe a rubrica e a transcrição e devolve, para cada critério, uma nota de 1 a 5,
uma justificativa e o trecho da conversa usado como evidência (saída em JSON Schema).
"""

import json
import os
import urllib.request
from typing import Callable, Protocol

from pydantic import BaseModel, ConfigDict

from .models import Conversation, Criterion, CriterionResult

MODEL = os.getenv("ATENDIMENTO_EVAL_MODEL", "claude-opus-5-5")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("ATENDIMENTO_EVAL_OLLAMA_MODEL", "qwen2.5:3b")
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
    def __init__(self, client=None, model: str = MODEL):
        if client is None:
            import anthropic  # import preguiçoso: o juiz aberto não precisa do SDK

            client = anthropic.Anthropic()
        self.client = client
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


def _post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.load(resp)


class OllamaJudge:
    """Juiz com modelo aberto rodando local ou no CI (Ollama): custo zero, sem chave de API.

    Usa a saída estruturada do Ollama (`format` = JSON Schema). Se o modelo devolver algo
    inválido, a conversa inteira conta como "não avaliada" (reprovada), sem nota inventada.
    """

    def __init__(self, model: str = OLLAMA_MODEL, url: str = OLLAMA_URL,
                 post: Callable[[str, dict], dict] = _post_json):
        self.model = model
        self.url = url.rstrip("/")
        self.post = post

    def __call__(self, conv: Conversation, criteria: list[Criterion]) -> list[CriterionResult]:
        response = self.post(f"{self.url}/api/chat", {
            "model": self.model,
            "stream": False,
            "format": JudgeOutput.model_json_schema(),
            "options": {"temperature": 0, "seed": 7},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_prompt(conv, criteria)},
            ],
        })
        try:
            output = JudgeOutput.model_validate(json.loads(response["message"]["content"]))
        except (KeyError, ValueError):  # JSON inválido ou fora do schema (ValidationError é ValueError)
            output = JudgeOutput(avaliacoes=[])
        return to_results(output, criteria)


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
