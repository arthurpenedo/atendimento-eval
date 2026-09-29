"""Estruturas de dados: conversas, critérios e resultados."""

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["cliente", "atendente"]


class Turn(BaseModel):
    role: Role
    text: str


class Conversation(BaseModel):
    id: str
    canal: str = "chat"
    turns: list[Turn] = Field(min_length=1)

    def agent_turns(self) -> list[Turn]:
        return [t for t in self.turns if t.role == "atendente"]

    def as_transcript(self) -> str:
        return "\n".join(f"[{t.role.upper()}] {t.text}" for t in self.turns)


class Criterion(BaseModel):
    id: str
    descricao: str
    peso: float = 1.0
    tipo: Literal["deterministico", "llm"]
    critico: bool = False
    """Se reprovado, a conversa inteira é reprovada (ex.: vazamento de dado pessoal)."""


class CriterionResult(BaseModel):
    criterio: str
    nota: float
    """De 0 a 1."""
    aprovado: bool
    justificativa: str


class ConversationResult(BaseModel):
    conversation_id: str
    nota_final: float
    reprovada_por_critico: bool
    resultados: list[CriterionResult]
