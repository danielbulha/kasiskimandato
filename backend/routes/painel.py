"""Painel do gabinete: o que exige atenção hoje."""
from datetime import date, timedelta

from flask import Blueprint, jsonify

from auth import login_requerido
from models import AchadoDiario, Comunicado, Emenda, EventoEmenda
from routes import gabinete_da_conta
from services import eleitoral, risco
import planos
from flask import g

bp = Blueprint("painel", __name__, url_prefix="/api")


@bp.get("/gabinetes/<int:gid>/painel")
@login_requerido
def painel(gid):
    gab = gabinete_da_conta(gid)
    emendas = Emenda.query.filter_by(gabinete_id=gab.id).all()
    ids = [e.id for e in emendas] or [0]
    soma = lambda c: round(sum(getattr(e, c) or 0 for e in emendas if e.fase != "cancelada"), 2)  # noqa: E731
    limite = date.today() + timedelta(days=15)
    prazos = sorted([e for e in emendas if e.proximo_prazo and e.proximo_prazo <= limite and e.fase not in ("paga", "executada", "cancelada")],
                    key=lambda e: e.proximo_prazo)
    eventos = EventoEmenda.query.filter(EventoEmenda.emenda_id.in_(ids)).order_by(EventoEmenda.data.desc()).limit(12).all()
    por_id = {e.id: e for e in emendas}
    return jsonify({
        "totais": {"indicado": soma("valor_indicado"), "empenhado": soma("valor_empenhado"), "pago": soma("valor_pago"),
                   "emendas": len(emendas)},
        "por_fase": {f: sum(1 for e in emendas if e.fase == f) for f in {e.fase for e in emendas}},
        "impedidas": [e.dict() for e in emendas if e.fase == "impedida"][:10],
        "prazos": [e.dict() for e in prazos][:10],
        "eventos": [{**ev.dict(), "emenda": (por_id[ev.emenda_id].numero or por_id[ev.emenda_id].objeto or "")[:80]} for ev in eventos],
        "eventos_nao_vistos": EventoEmenda.query.filter(EventoEmenda.emenda_id.in_(ids), EventoEmenda.visto.is_(False)).count(),
        "achados_novos": AchadoDiario.query.filter_by(gabinete_id=gab.id, status="novo").count(),
        "rascunhos": Comunicado.query.filter_by(gabinete_id=gab.id, status="rascunho").count(),
        "periodo_eleitoral": eleitoral.situacao(gab.esfera),
        "regimento": bool(gab.regimento_texto), "base": len(gab.base),
        "riscos": sorted([{"emenda_id": e.id, "emenda": (e.numero or e.objeto or "")[:80], **r}
                          for e in emendas for r in risco.avaliar(e)], key=lambda x: risco.ORDEM[x["nivel"]])[:12],
        "modulos": planos.PLANOS[planos.plano_atual(g.conta)]["modulos"],
    })
