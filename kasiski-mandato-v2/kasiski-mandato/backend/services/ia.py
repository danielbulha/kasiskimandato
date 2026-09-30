"""Chamada de IA com registro de custo e verificação cruzada por um modelo de outro fornecedor."""
import json

from flask import current_app

from extensions import ErroAPI, db
from models import UsoIA
from services import llm


def _registrar(conta_id, tarefa, r):
    if r.demonstracao:
        return
    db.session.add(UsoIA(conta_id=conta_id, tarefa=tarefa, provedor=r.provedor, modelo=r.modelo,
                         tokens_entrada=r.tokens_entrada, tokens_saida=r.tokens_saida, custo_usd=r.custo_usd,
                         custo_brl=round(r.custo_usd * current_app.config["USD_BRL"], 4)))


def gerar(conta_id, tarefa, rota, sistema, usuario, demo, max_tokens=6000):
    try:
        r = llm.chamar(rota, sistema, usuario, max_tokens=max_tokens, json_saida=True, demo=demo)
    except RuntimeError as e:
        current_app.logger.error("IA falhou (%s): %s", tarefa, e)
        raise ErroAPI("As IAs não responderam agora. Tente de novo em alguns minutos.", 502, "ia_indisponivel")
    _registrar(conta_id, tarefa, r)
    return json.loads(r.texto), r


def verificar(conta_id, tarefa, sistema, usuario, resposta, demo):
    """Segunda opinião de outro fornecedor. Devolve {confirmado, comentario, apontamentos, modelo}."""
    try:
        r = llm.chamar("verificacao", sistema, usuario, max_tokens=2500, json_saida=True, demo=demo,
                       evitar_familia=resposta.familia)
    except RuntimeError:
        return {"confirmado": None, "comentario": "Verificação cruzada indisponível agora.", "apontamentos": [], "modelo": None}
    _registrar(conta_id, tarefa + "_verificacao", r)
    v = json.loads(r.texto)
    mesma = r.familia == resposta.familia and not r.demonstracao
    v["modelo"] = r.modelo + (" (mesmo fornecedor: só há uma chave de IA configurada)" if mesma else "")
    return v
