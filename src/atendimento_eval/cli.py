"""CLI.

    atendimento-eval avaliar data/conversas_v1.jsonl [--rubrica rubricas/padrao.yaml] [--juiz] [--saida r.json]
                             [--html relatorio.html] [--base resumo_v1.json]
    atendimento-eval comparar resumo_v1.json resumo_v2.json
"""

import argparse
import json
import sys
from pathlib import Path

from .evaluator import compare, evaluate_all, load_conversations, load_rubric, summarize
from .report import render_html

DEFAULT_RUBRIC = Path(__file__).parent / "rubricas" / "padrao.yaml"


def _print_summary(summary: dict) -> None:
    print(f"\nConversas avaliadas: {summary['conversas']}")
    print(f"Nota média: {summary['nota_media']:.0%}")
    print(f"Reprovadas por critério crítico: {summary['reprovadas_por_critico']}\n")
    print("Aprovação por critério:")
    for crit, rate in summary["aprovacao_por_criterio"].items():
        bar = "█" * round(rate * 20)
        print(f"  {crit:<16} {bar:<20} {rate:.0%}")
    print(f"\nPiores conversas: {', '.join(summary['piores']) or 'nenhuma'}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="atendimento-eval")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_eval = sub.add_parser("avaliar", help="avalia um arquivo JSONL de conversas")
    p_eval.add_argument("conversas", type=Path)
    p_eval.add_argument("--rubrica", type=Path, default=DEFAULT_RUBRIC)
    p_eval.add_argument("--juiz", action="store_true", help="usa o Claude para os critérios do tipo 'llm'")
    p_eval.add_argument("--saida", type=Path, help="salva resultados e resumo em JSON")
    p_eval.add_argument("--html", type=Path, help="gera relatório HTML com as piores conversas")
    p_eval.add_argument("--base", type=Path, help="JSON de outra execução (--saida) para comparar no relatório")

    p_cmp = sub.add_parser("comparar", help="compara dois resumos salvos com --saida")
    p_cmp.add_argument("antes", type=Path)
    p_cmp.add_argument("depois", type=Path)

    args = parser.parse_args(argv)

    if args.cmd == "avaliar":
        criteria = load_rubric(args.rubrica)
        judge = None
        if args.juiz:
            from .judge import ClaudeJudge

            judge = ClaudeJudge()
        conversations = load_conversations(args.conversas)
        results = evaluate_all(conversations, criteria, judge)
        summary = summarize(results)
        _print_summary(summary)
        if args.saida:
            args.saida.write_text(json.dumps({
                "resumo": summary,
                "resultados": [r.model_dump() for r in results],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.html:
            base = json.loads(args.base.read_text(encoding="utf-8"))["resumo"] if args.base else None
            args.html.write_text(render_html(summary, results, conversations, base), encoding="utf-8")
            print(f"Relatório salvo em {args.html}")
        return 0

    before = json.loads(args.antes.read_text(encoding="utf-8"))["resumo"]
    after = json.loads(args.depois.read_text(encoding="utf-8"))["resumo"]
    diff = compare(before, after)
    print(f"\nVariação da nota média: {diff['delta_nota_media']:+.1%}")
    for crit, delta in diff["delta_por_criterio"].items():
        print(f"  {crit:<16} {delta:+.0%}")
    if diff["regressoes"]:
        print(f"\n⚠ Regressões: {', '.join(diff['regressoes'])}")
        return 1
    print("\nSem regressões.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
