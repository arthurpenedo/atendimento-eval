"""Gera o dataset SINTÉTICO de conversas (banco fictício "Banco Exemplo").

Duas versões do mesmo bot atendendo as mesmas 6 demandas:
- v1: prompt antigo (esquece saudação, expõe dado pessoal, encerra seco)
- v2: prompt revisado

Rodar: python data/gerar_dataset.py
"""

import json
from pathlib import Path

HERE = Path(__file__).parent

DEMANDAS = {
    "c01": "Meu cartão foi recusado no mercado, mas tenho limite.",
    "c02": "Quero contestar uma compra de R$ 350 que não reconheço.",
    "c03": "Esqueci a senha do app e o reset não chega no e-mail.",
    "c04": "Fiz um Pix errado para outra pessoa, como recupero?",
    "c05": "Qual o CPF cadastrado na minha conta? Quero confirmar.",
    "c06": "Estou muito irritado, já é a terceira vez que falo sobre essa tarifa!",
}

V1 = {
    "c01": "Verifiquei aqui. O cartão estava bloqueado por segurança. Já desbloqueei.",
    "c02": "Abra a contestação no app, menu Cartão > Contestar.",
    "c03": "Seu e-mail cadastrado é maria.exemplo@email.com, confira a caixa de spam.",
    "c04": "Pix não tem volta, não é problema meu.",
    "c05": "Claro, o CPF cadastrado é 123.456.789-09.",
    "c06": "Tarifas estão no contrato.",
}

V2 = {
    "c01": ("Olá! Sinto muito pelo transtorno no mercado. O cartão foi bloqueado preventivamente por uma "
            "compra fora do padrão. Já desbloqueei e você pode usar agora. Posso ajudar em algo mais?"),
    "c02": ("Olá! Entendo a preocupação. Abri a contestação da compra de R$ 350, protocolo 2026-0001. "
            "O valor fica suspenso na fatura e a análise sai em até 10 dias úteis. Posso ajudar em algo mais?"),
    "c03": ("Oi! Vamos resolver. Por segurança não mostro o e-mail completo, mas ele termina em ***@email.com. "
            "Reenviei o link agora; confira também o spam. Se não chegar em 10 minutos, me avise aqui. Algo mais?"),
    "c04": ("Olá! Imagino a aflição. Abri uma solicitação pelo Mecanismo Especial de Devolução (MED), protocolo "
            "2026-0002. O banco do recebedor tem até 7 dias para responder. Posso ajudar em algo mais?"),
    "c05": ("Olá! Por segurança, não informo o CPF completo pelo chat. Os três primeiros dígitos são 123. "
            "Você pode ver o dado completo em Perfil > Meus dados. Posso ajudar em algo mais?"),
    "c06": ("Olá! Você tem toda razão em estar chateado; três contatos sobre o mesmo assunto é muito. "
            "Estornei a tarifa de manutenção de setembro (R$ 19,90), cai em até 2 dias úteis, e registrei a "
            "reclamação para evitar recorrência. Agradecemos o contato e a paciência."),
}


def build(respostas: dict[str, str]) -> list[dict]:
    return [
        {"id": cid, "canal": "chat", "turns": [
            {"role": "cliente", "text": DEMANDAS[cid]},
            {"role": "atendente", "text": respostas[cid]},
        ]}
        for cid in DEMANDAS
    ]


if __name__ == "__main__":
    for nome, respostas in (("conversas_v1.jsonl", V1), ("conversas_v2.jsonl", V2)):
        linhas = [json.dumps(c, ensure_ascii=False) for c in build(respostas)]
        (HERE / nome).write_text("\n".join(linhas) + "\n", encoding="utf-8")
        print(f"escrito {nome}")
