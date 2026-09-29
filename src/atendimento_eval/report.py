"""Relatório HTML autocontido (um arquivo, sem dependências externas).

Mostra o resumo, a aprovação por critério (com variação contra uma versão base,
quando informada) e as piores conversas com a transcrição e o motivo de cada
reprovação — o suficiente para alguém revisar sem abrir o JSON.
"""

from datetime import datetime
from html import escape

from .models import Conversation, ConversationResult

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#e4e4e0;
--ok:#1f8a4c;--bad:#c2372e;--warn:#b7791f;--bar:#3a6ff7;--bar-bg:#e9edf8}
@media (prefers-color-scheme:dark){:root{--bg:#131316;--card:#1c1c20;--fg:#ececf0;--muted:#9a9aa3;
--line:#2c2c33;--ok:#4cc38a;--bad:#ff6b61;--warn:#e0a84a;--bar:#6f93ff;--bar-bg:#262a3a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:960px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:36px 0 12px}
.muted{color:var(--muted)}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-top:20px}
.kpi b{display:block;font-size:28px;font-variant-numeric:tabular-nums}
.delta{font-size:13px;font-weight:600;margin-left:6px}.up{color:var(--ok)}.down{color:var(--bad)}
table{width:100%;border-collapse:collapse}td,th{padding:8px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.bar{height:10px;border-radius:5px;background:var(--bar-bg);overflow:hidden;min-width:120px}
.bar span{display:block;height:100%;background:var(--bar)}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.tag{display:inline-block;font-size:12px;font-weight:600;padding:1px 8px;border-radius:999px;border:1px solid currentColor}
.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}
.conv{margin-bottom:14px}.conv header{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;justify-content:space-between}
.turn{margin:6px 0;padding:8px 10px;border-radius:8px;background:var(--bg);white-space:pre-wrap;overflow-wrap:anywhere}
.turn small{display:block;font-weight:600;color:var(--muted);font-size:11px;letter-spacing:.05em}
ul.fails{margin:10px 0 0;padding-left:18px}ul.fails li{margin:2px 0}
.wrap{overflow-x:auto}footer{margin-top:40px;font-size:13px}
"""


def _pct(x: float) -> str:
    return f"{x:.0%}"


def _delta(d: float | None) -> str:
    if d is None or abs(d) < 0.0005:
        return ""
    cls = "up" if d > 0 else "down"
    return f'<span class="delta {cls}">{d:+.0%}</span>'


def _nota_tag(r: ConversationResult) -> str:
    if r.reprovada_por_critico:
        return '<span class="tag bad">reprovada (crítico)</span>'
    cls = "ok" if r.nota_final >= 0.8 else "warn" if r.nota_final >= 0.5 else "bad"
    return f'<span class="tag {cls}">{_pct(r.nota_final)}</span>'


def _conversation_card(r: ConversationResult, conv: Conversation | None) -> str:
    fails = [cr for cr in r.resultados if not cr.aprovado]
    parts = [f'<article class="card conv"><header><strong>{escape(r.conversation_id)}</strong>{_nota_tag(r)}</header>']
    if conv is not None:
        parts += [f'<div class="turn"><small>{escape(t.role.upper())}</small>{escape(t.text)}</div>' for t in conv.turns]
    if fails:
        items = "".join(f"<li><strong>{escape(cr.criterio)}</strong>: {escape(cr.justificativa)}</li>" for cr in fails)
        parts.append(f'<ul class="fails">{items}</ul>')
    parts.append("</article>")
    return "".join(parts)


def render_html(
    summary: dict,
    results: list[ConversationResult],
    conversations: list[Conversation] | None = None,
    base: dict | None = None,
    titulo: str = "Relatório de qualidade de atendimento",
    top: int = 5,
) -> str:
    """Gera o HTML. `base` é o resumo de outra execução (ex.: prompt v1) para mostrar variações."""
    convs = {c.id: c for c in conversations or []}
    base_rates = (base or {}).get("aprovacao_por_criterio", {})

    def d(key: str) -> float | None:
        return summary[key] - base[key] if base else None

    kpis = f"""
<div class="kpis">
  <div class="card kpi"><span class="muted">Nota média</span><b>{_pct(summary['nota_media'])}{_delta(d('nota_media'))}</b></div>
  <div class="card kpi"><span class="muted">Conversas avaliadas</span><b>{summary['conversas']}</b></div>
  <div class="card kpi"><span class="muted">Reprovadas por critério crítico</span><b>{summary['reprovadas_por_critico']}</b></div>
</div>"""

    rows = []
    regressoes = []
    for crit, rate in summary["aprovacao_por_criterio"].items():
        delta = rate - base_rates[crit] if crit in base_rates else None
        if delta is not None and delta < 0:
            regressoes.append(crit)
        rows.append(
            f'<tr><td>{escape(crit)}</td><td><div class="bar"><span style="width:{rate * 100:.0f}%"></span></div></td>'
            f'<td class="num">{_pct(rate)}{_delta(delta)}</td></tr>'
        )
    criterios = f"""<h2>Aprovação por critério</h2>
<div class="card wrap"><table><thead><tr><th>Critério</th><th>Aprovação</th><th></th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>"""

    if base is not None:
        status = (f'<p class="card bad">⚠ Regressão em: {escape(", ".join(regressoes))}</p>' if regressoes
                  else '<p class="card ok">✓ Sem regressões em relação à versão base.</p>')
        criterios = status + criterios

    ranked = sorted(results, key=lambda r: (r.nota_final, r.conversation_id))
    piores = [r for r in ranked if r.nota_final < 1][:top]
    piores_html = ("".join(_conversation_card(r, convs.get(r.conversation_id)) for r in piores)
                   or '<p class="card ok">Nenhuma conversa abaixo de 100%.</p>')

    todas = "".join(
        f'<tr><td>{escape(r.conversation_id)}</td><td>{_nota_tag(r)}</td>'
        f'<td>{escape(", ".join(cr.criterio for cr in r.resultados if not cr.aprovado) or "—")}</td></tr>'
        for r in ranked
    )

    gerado = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(titulo)}</title><style>{CSS}</style></head>
<body><main>
<h1>{escape(titulo)}</h1>
<p class="muted">Gerado por atendimento-eval em {gerado}{' · comparado com a versão base' if base else ''}</p>
{kpis}
{criterios}
<h2>Piores conversas</h2>
{piores_html}
<h2>Todas as conversas</h2>
<div class="card wrap"><table><thead><tr><th>ID</th><th>Nota</th><th>Critérios reprovados</th></tr></thead>
<tbody>{todas}</tbody></table></div>
<footer class="muted">Dados sintéticos. <a href="https://github.com/arthurpenedo/atendimento-eval">github.com/arthurpenedo/atendimento-eval</a></footer>
</main></body></html>
"""
