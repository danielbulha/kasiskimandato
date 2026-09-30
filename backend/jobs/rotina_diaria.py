"""Rotina diária (cron do Render): sincroniza emendas federais, roda os monitores de diários oficiais,
gera rascunhos automáticos e manda o resumo do dia por e-mail.

Uso: python jobs/rotina_diaria.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("KASISKI_JOB", "1")

from app import create_app  # noqa: E402
from extensions import ErroAPI, db  # noqa: E402
from models import Conta, Gabinete  # noqa: E402
import planos  # noqa: E402
from services import automacoes, sincronizacao  # noqa: E402


def rodar():
    app = create_app()
    with app.app_context():
        for gab in Gabinete.query.all():
            conta = db.session.get(Conta, gab.conta_id)
            p = planos.PLANOS[planos.plano_atual(conta)]
            novidades = {"eventos": 0, "achados": 0, "comunicados": 0}
            if p["sincronizacao"] and gab.esfera == "federal":
                try:
                    livres = None if p["emendas"] is None else max(0, p["emendas"] - planos.uso(conta)["emendas"])
                    r = sincronizacao.sincronizar_federal(gab, limite_novas=livres)
                    novidades["eventos"] = r["eventos"]
                    novidades["comunicados"] = automacoes.rascunhos_para_eventos(gab, r["eventos_ids"])
                except ErroAPI as e:
                    app.logger.warning("Sincronização federal do gabinete %s: %s", gab.id, e.mensagem)
            if p["sincronizacao"] or planos.plano_atual(conta) == "free":
                for m in sincronizacao.monitores_ativos(gab):
                    novidades["achados"] += sincronizacao.rodar_monitor(m, gab)
            automacoes.resumo_diario(gab, novidades)
            app.logger.info("Gabinete %s: %s", gab.id, novidades)


if __name__ == "__main__":
    rodar()
