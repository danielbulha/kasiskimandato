"""Geração de comunicados (release, discurso, post, roteiro, prestação de contas) com travas de conformidade."""
import json

from extensions import ErroAPI, db
from models import FORMATOS, Comunicado
from services import eleitoral, ia, kb, prompts


def gerar(gab, conta_id, formato, canal, emenda=None, evento=None, tema=None, automatico=False):
    if formato not in FORMATOS:
        raise ErroAPI("Formato inválido.")
    if canal not in ("pessoal", "institucional"):
        raise ErroAPI("Escolha o canal: perfis do parlamentar (pessoal) ou comunicação da Casa (institucional).")
    if not (emenda or evento or (tema and tema.strip())):
        raise ErroAPI("Escolha uma emenda ou descreva o tema do comunicado.")
    periodo = eleitoral.situacao(gab.esfera)
    alertas = []
    if periodo["vedado"]:
        if canal == "institucional":
            raise ErroAPI(f"Período de vedação de publicidade institucional ({periodo['inicio']} a {periodo['fim']}, "
                          "Lei 9.504/97, art. 73, VI, b). Peças institucionais ficam bloqueadas até o fim do período.",
                          409, "periodo_eleitoral")
        alertas.append("Período eleitoral: não use verba de gabinete/cota parlamentar para produzir ou impulsionar esta "
                       "peça sem conferir o ato da sua Casa, e não inclua pedido de voto.")
    fatos = prompts.fatos_comunicado(gab, emenda, evento, tema)
    sistema = prompts.SISTEMA_COMUNICADO + "\n\n=== LIMITES ===\n" + kb.base_fixa("04")
    usuario = prompts.usuario_comunicado(formato, canal, fatos)
    dados, resp = ia.gerar(conta_id, "comunicado", "redacao", sistema, usuario, prompts.demo_comunicado(formato, fatos),
                           max_tokens=2500)
    verif = ia.verificar(conta_id, "comunicado", prompts.SISTEMA_VERIF_COMUNICADO,
                         usuario + "\n\n=== TEXTO ===\n" + json.dumps(dados, ensure_ascii=False), resp, prompts.DEMO_VERIF)
    alertas += [a for a in (dados.get("alertas") or []) if a]
    alertas += [f"Verificação cruzada ({x.get('gravidade', 'media')}): {x.get('texto')}" for x in verif.get("apontamentos") or []]
    texto = dados.get("texto") or ""
    if dados.get("titulo") and formato == "release":
        texto = dados["titulo"].strip() + "\n\n" + texto
    c = Comunicado(gabinete_id=gab.id, emenda_id=emenda.id if emenda else None, evento_id=evento.id if evento else None,
                   formato=formato, canal=canal, tema=tema, texto=texto, alertas=json.dumps(alertas, ensure_ascii=False),
                   automatico=automatico)
    db.session.add(c)
    db.session.commit()
    return c
