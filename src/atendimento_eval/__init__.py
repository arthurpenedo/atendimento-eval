"""atendimento-eval: avaliação de qualidade de atendimento com checagens determinísticas e LLM-as-judge."""

from .evaluator import compare, evaluate, evaluate_all, load_conversations, load_rubric, summarize

__all__ = ["compare", "evaluate", "evaluate_all", "load_conversations", "load_rubric", "summarize"]
__version__ = "0.1.0"
