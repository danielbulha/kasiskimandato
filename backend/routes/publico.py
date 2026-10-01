"""Página pública de prestação de contas do mandato (Gestor de Emendas). Sem login."""
from flask import Blueprint, jsonify

import planos
from extensions import ErroAPI, db
from models import CARGOS, Conta, Emenda, EventoEmenda, Gabinete

bp = Blueprint("publico", __name__, url_prefix="/api/public")


@bp.get("/prestacao/<slug>")
def prestacao(slug):
    gab = Gabinete.query.filter_by(slug_publico=slug, pagina_publica=True).first()
    if not gab or not planos.tem_modulo(db.session.get(Conta, gab.conta_id), "gestor"):
        raise ErroAPI("Página não encontrada.", 404)
    emendas = Emenda.query.filter_by(gabinete_id=gab.id, publicar=True).filter(Emenda.fase != "cancelada") \
        .order_by(Emenda.ano.desc().nullslast(), Emenda.id.desc()).all()
    por_municipio = {}
    for e in emendas:
        ultimos = EventoEmenda.query.filter(EventoEmenda.emenda_id == e.id, EventoEmenda.tipo.in_(("fase", "valor"))) \
            .order_by(EventoEmenda.data.desc()).limit(4).all()
        item = {"objeto": e.objeto, "ano": e.ano, "numero": e.numero, "funcao": e.funcao, "beneficiario": e.beneficiario,
                "valor_indicado": e.valor_indicado, "valor_empenhado": e.valor_empenhado, "valor_pago": e.valor_pago,
                "fase": e.fase, "linha_do_tempo": [{"data": ev.data.date().isoformat(), "descricao": ev.descricao} for ev in ultimos]}
        por_municipio.setdefault(e.municipio or "Outros", []).append(item)
    municipios = [{"municipio": m, "emendas": lst, "total_indicado": round(sum(x["valor_indicado"] or 0 for x in lst), 2),
                   "total_pago": round(sum(x["valor_pago"] or 0 for x in lst), 2)} for m, lst in por_municipio.items()]
    return jsonify({"parlamentar": gab.nome_parlamentar or gab.parlamentar, "cargo": CARGOS.get(gab.cargo), "casa": gab.casa,
                    "partido": gab.partido, "uf": gab.uf, "foto_url": gab.foto_url,
                    "municipios": sorted(municipios, key=lambda m: -m["total_indicado"]),
                    "total_indicado": round(sum(m["total_indicado"] for m in municipios), 2),
                    "total_pago": round(sum(m["total_pago"] for m in municipios), 2)})
