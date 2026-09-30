"""Fontes do Estado de São Paulo e painel de fontes disponíveis."""
from datetime import date

from flask import Blueprint, current_app, jsonify, request

from auth import login_requerido
from extensions import ErroAPI
from routes import gabinete_da_conta
from services import mercadopago, sao_paulo

bp = Blueprint("sao_paulo", __name__, url_prefix="/api")


@bp.get("/fontes")
@login_requerido
def fontes():
    cfg = current_app.config
    return jsonify({"portal_transparencia": bool(cfg["PORTAL_TRANSPARENCIA_KEY"]), "querido_diario": True,
                    "tce_sp": True, "doe_sp": sao_paulo.doe_configurado(), "transferegov": cfg["TRANSFEREGOV_ATIVO"],
                    "mercado_pago": mercadopago.configurado(), "teste": cfg["TESTE"]})


@bp.get("/gabinetes/<int:gid>/repasses-sp")
@login_requerido
def repasses(gid):
    """Receitas de transferências/convênios estaduais nos municípios paulistas da base (TCE-SP), num mês."""
    gab = gabinete_da_conta(gid)
    hoje = date.today()
    ano = int(request.args.get("ano") or hoje.year)
    mes = int(request.args.get("mes") or (hoje.month - 2) % 12 + 1)   # padrão: 2 meses atrás (o TCE recebe com atraso)
    if mes < 1 or mes > 12:
        raise ErroAPI("Mês inválido.")
    municipios = [m for m in gab.base if (m.get("uf") or "").upper() == "SP"][:15]
    if not municipios and gab.uf == "SP" and gab.municipio:
        municipios = [{"nome": gab.municipio, "uf": "SP"}]
    if not municipios:
        raise ErroAPI("Inclua municípios paulistas na base territorial do gabinete para ver os repasses do Estado.")
    saida = []
    for m in municipios:
        try:
            saida.append(sao_paulo.repasses_estaduais(m["nome"], ano, mes))
        except ErroAPI as e:
            saida.append({"municipio": m["nome"], "total": None, "linhas": [], "aviso": e.mensagem})
    return jsonify({"ano": ano, "mes": mes, "municipios": saida,
                    "total": round(sum(x["total"] or 0 for x in saida), 2)})


@bp.get("/gabinetes/<int:gid>/empenhos-sp")
@login_requerido
def empenhos(gid):
    """Despesas de um município paulista da base no mês, filtradas por fornecedor (ex.: construtora da obra da emenda)."""
    gab = gabinete_da_conta(gid)
    nome = request.args.get("municipio", "")
    if not any(m["nome"] == nome for m in gab.base):
        raise ErroAPI("Escolha um município da base territorial.")
    hoje = date.today()
    return jsonify(sao_paulo.empenhos_municipio(nome, int(request.args.get("ano") or hoje.year),
                                                int(request.args.get("mes") or hoje.month), request.args.get("fornecedor")))
