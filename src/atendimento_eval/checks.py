"""Checagens determinísticas: rápidas, baratas e 100% reproduzíveis.

Ficam aqui os critérios que regex resolve bem. O que exige interpretação
(empatia, resolução do problema) vai para o juiz LLM.
"""

import re
import unicodedata
from collections.abc import Callable

from .models import Conversation, CriterionResult

CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
CARTAO = re.compile(r"\b(?:\d[ -]?){13,16}\b")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")

SAUDACOES = ("ola", "oi", "bom dia", "boa tarde", "boa noite", "seja bem-vindo", "seja bem vindo")
ENCERRAMENTOS = (
    "posso ajudar em algo mais", "algo mais", "mais alguma", "tenha um otimo", "tenha um bom",
    "obrigado pelo contato", "agradecemos o contato", "estamos a disposicao", "ate logo",
)
TERMOS_PROIBIDOS = ("nao e problema meu", "se vira", "isso e com voce", "nao sei e nao posso fazer nada")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _has_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    """Casa frases por palavra inteira ("oi" não pode casar dentro de "foi")."""
    norm = _norm(text)
    return any(re.search(rf"(?<!\w){re.escape(p)}(?!\w)", norm) for p in phrases)


def _result(criterio: str, ok: bool, justificativa: str) -> CriterionResult:
    return CriterionResult(criterio=criterio, nota=1.0 if ok else 0.0, aprovado=ok, justificativa=justificativa)


def check_saudacao(conv: Conversation) -> CriterionResult:
    agent = conv.agent_turns()
    ok = bool(agent) and _has_phrase(agent[0].text, SAUDACOES)
    return _result("saudacao", ok, "Primeira mensagem do atendente cumprimenta o cliente." if ok
                   else "O atendente não cumprimentou o cliente na primeira mensagem.")


def check_encerramento(conv: Conversation) -> CriterionResult:
    agent = conv.agent_turns()
    ok = bool(agent) and _has_phrase(agent[-1].text, ENCERRAMENTOS)
    return _result("encerramento", ok, "Encerramento cordial e oferta de ajuda adicional." if ok
                   else "A conversa termina sem encerramento cordial.")


def check_dados_pessoais(conv: Conversation) -> CriterionResult:
    """O ATENDENTE nunca deve escrever CPF, número de cartão ou e-mail completos (LGPD)."""
    for turn in conv.agent_turns():
        for nome, padrao in (("CPF", CPF), ("cartão", CARTAO), ("e-mail", EMAIL)):
            if padrao.search(turn.text):
                return _result("dados_pessoais", False, f"O atendente expôs um {nome} completo na conversa.")
    return _result("dados_pessoais", True, "Nenhum dado pessoal exposto pelo atendente.")


def check_linguagem(conv: Conversation) -> CriterionResult:
    for turn in conv.agent_turns():
        for termo in TERMOS_PROIBIDOS:
            if _has_phrase(turn.text, (termo,)):
                return _result("linguagem", False, f'Linguagem inadequada: "{termo}".')
    return _result("linguagem", True, "Nenhum termo inadequado encontrado.")


CHECKS: dict[str, Callable[[Conversation], CriterionResult]] = {
    "saudacao": check_saudacao,
    "encerramento": check_encerramento,
    "dados_pessoais": check_dados_pessoais,
    "linguagem": check_linguagem,
}
