"""Rotina de hora em hora (cron do Render): coleta o clipping, detecta crises e, às 7h de Brasília, gera a pauta do dia.

Uso: python jobs/clipping_hora.py
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("KASISKI_JOB", "1")

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models import Conta, Gabinete, ResumoDiario  # noqa: E402
import planos  # noqa: E402
from services import clipping  # noqa: E402


def rodar():
    app = create_app()
    with app.app_context():
        hora_brasilia = (datetime.utcnow().hour - 3) % 24
        for gab in Gabinete.query.all():
            conta = db.session.get(Conta, gab.conta_id)
            if not planos.tem_modulo(conta, "clipping"):
                continue
            social = planos.tem_modulo(conta, "social")
            for t in clipping.temas_ativos(gab):
                try:
                    clipping.coletar(t, gab, social)
                except Exception:  # noqa: BLE001 — um tema com problema não para os demais
                    app.logger.exception("Clipping do tema %s falhou", t.id)
            if planos.tem_modulo(conta, "alertas"):
                clipping.detectar_crise(gab)
                ja = ResumoDiario.query.filter_by(gabinete_id=gab.id, data=datetime.utcnow().date()).first()
                if hora_brasilia == 7 and not ja:
                    clipping.gerar_resumo(gab)


if __name__ == "__main__":
    rodar()
