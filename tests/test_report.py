from pathlib import Path

from atendimento_eval import evaluate_all, load_conversations, load_rubric, summarize
from atendimento_eval.cli import DEFAULT_RUBRIC, main
from atendimento_eval.models import Conversation
from atendimento_eval.report import render_html

DATA = Path(__file__).parent.parent / "data"


def run(path: Path):
    convs = load_conversations(path)
    results = evaluate_all(convs, load_rubric(DEFAULT_RUBRIC))
    return convs, results, summarize(results)


def test_report_shows_worst_conversations_with_transcript_and_reasons():
    convs, results, summary = run(DATA / "conversas_v1.jsonl")
    html = render_html(summary, results, convs)
    assert "Piores conversas" in html
    assert "maria.exemplo@email.com" in html  # transcrição da conversa que vazou e-mail
    assert "expôs um e-mail completo" in html  # motivo da reprovação
    assert "reprovada (crítico)" in html


def test_report_escapes_conversation_text():
    evil = Conversation(id="x<script>", turns=[
        {"role": "cliente", "text": "<script>alert(1)</script>"},
        {"role": "atendente", "text": "ok"},
    ])
    results = evaluate_all([evil], load_rubric(DEFAULT_RUBRIC))
    html = render_html(summarize(results), results, [evil])
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_report_marks_regressions_against_base():
    _, _, v1 = run(DATA / "conversas_v1.jsonl")
    convs2, results2, v2 = run(DATA / "conversas_v2.jsonl")
    assert "Sem regressões" in render_html(v2, results2, convs2, base=v1)
    # invertendo a comparação, a v1 regride em relação à v2
    convs1, results1, _ = run(DATA / "conversas_v1.jsonl")
    assert "Regressão em" in render_html(v1, results1, convs1, base=v2)


def test_cli_writes_html(tmp_path):
    base = tmp_path / "v1.json"
    out = tmp_path / "relatorio.html"
    assert main(["avaliar", str(DATA / "conversas_v1.jsonl"), "--saida", str(base)]) == 0
    assert main(["avaliar", str(DATA / "conversas_v2.jsonl"), "--html", str(out), "--base", str(base)]) == 0
    html = out.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert "comparado com a versão base" in html
