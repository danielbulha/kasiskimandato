"""Mandato 8: radar versionado, auditoria de recursos e briefing baseado em registros."""
from datetime import date, datetime, timedelta
from difflib import unified_diff
from flask import Blueprint, jsonify, request
from auth import login_requerido
from extensions import db, ErroAPI
from models import RadarProposicao, RadarVersao, Emenda, Minuta, Demanda, TarefaGabinete, CompromissoGabinete
from routes import gabinete_da_conta

bp=Blueprint("inteligencia8",__name__,url_prefix="/api/gabinetes/<int:gid>/inteligencia")

def radar_item(gid,rid):
    item=RadarProposicao.query.filter_by(id=rid,gabinete_id=gid).first()
    if not item: raise ErroAPI("Proposição não encontrada.",404)
    return item

@bp.route("/radar",methods=["GET","POST"])
@login_requerido
def radar(gid):
    gabinete_da_conta(gid)
    if request.method=="GET":
        return jsonify([r.dict() for r in RadarProposicao.query.filter_by(gabinete_id=gid).order_by(RadarProposicao.id.desc()).limit(500)])
    d=request.get_json(silent=True) or {}
    ident=str(d.get("identificacao") or "").strip()[:160]
    if not ident: raise ErroAPI("Informe a identificação da proposição.",400)
    item=RadarProposicao(gabinete_id=gid,identificacao=ident)
    for key,lim in (("fonte",100),("url",900),("ementa",12000),("situacao",300),("texto",100000)):
        if key in d: setattr(item,key,str(d[key] or "")[:lim])
    db.session.add(item);db.session.flush()
    db.session.add(RadarVersao(radar_id=item.id,versao=1,texto=item.texto,situacao=item.situacao))
    db.session.commit()
    return jsonify(item.dict()),201

@bp.route("/radar/<int:rid>",methods=["GET","PUT","DELETE"])
@login_requerido
def radar_detalhe(gid,rid):
    gabinete_da_conta(gid); item=radar_item(gid,rid)
    if request.method=="GET":
        d=item.dict();d["historico"]=[{"versao":v.versao,"registrado_em":v.registrado_em.isoformat() if v.registrado_em else None} for v in RadarVersao.query.filter_by(radar_id=rid).order_by(RadarVersao.versao.desc())]
        return jsonify(d)
    if request.method=="DELETE":
        RadarVersao.query.filter_by(radar_id=rid).delete();db.session.delete(item);db.session.commit();return jsonify({"ok":True})
    d=request.get_json(silent=True) or {}
    anterior=item.texto or ""; situacao_anterior=item.situacao or ""
    for key,lim in (("identificacao",160),("fonte",100),("url",900),("ementa",12000),("situacao",300),("texto",100000)):
        if key in d: setattr(item,key,str(d[key] or "")[:lim])
    mudou=anterior!=(item.texto or "") or situacao_anterior!=(item.situacao or "")
    if mudou:
        item.versao+=1;db.session.add(RadarVersao(radar_id=rid,versao=item.versao,texto=item.texto,situacao=item.situacao))
    item.atualizado_em=datetime.utcnow();db.session.commit()
    result=item.dict();result["alterou_versao"]=mudou
    return jsonify(result)

@bp.get("/radar/<int:rid>/comparar")
@login_requerido
def comparar(gid,rid):
    gabinete_da_conta(gid);item=radar_item(gid,rid)
    versoes=RadarVersao.query.filter_by(radar_id=item.id).order_by(RadarVersao.versao.desc()).limit(2).all()
    if len(versoes)<2:return jsonify({"diferencas":[],"mensagem":"Cadastre uma nova versão do texto para comparar."})
    novo,antigo=versoes
    diff=list(unified_diff((antigo.texto or "").splitlines(),(novo.texto or "").splitlines(),fromfile=f"Versão {antigo.versao}",tofile=f"Versão {novo.versao}",lineterm=""))
    return jsonify({"versao_anterior":antigo.versao,"versao_atual":novo.versao,"diferencas":diff[:2000],"situacao_anterior":antigo.situacao,"situacao_atual":novo.situacao})

def financeiro(e):
    indicado=float(e.valor_indicado or 0); empenhado=float(e.valor_empenhado or 0);liquidado=float(e.valor_liquidado or 0);pago=float(e.valor_pago or 0)
    alertas=[]
    if pago>liquidado+0.01:alertas.append("Pago superior ao liquidado: conferir classificação e fonte.")
    if liquidado>empenhado+0.01:alertas.append("Liquidado superior ao empenhado: conferir dados.")
    if indicado>0 and empenhado>indicado+0.01:alertas.append("Empenhado superior ao indicado: verificar alterações de dotação.")
    if e.proximo_prazo and e.proximo_prazo<date.today():alertas.append("Prazo cadastrado vencido.")
    if not e.sincronizado_em:alertas.append("Sem sincronização confirmada com fonte externa.")
    return {"id":e.id,"numero":e.numero,"objeto":e.objeto,"municipio":e.municipio,"fase":e.fase,"valores":{"indicado":indicado,"empenhado":empenhado,"liquidado":liquidado,"pago":pago,"saldo_indicado_menos_pago":round(indicado-pago,2)},"alertas":alertas,"origem":e.origem,"sincronizado_em":e.sincronizado_em.isoformat() if e.sincronizado_em else None}

@bp.get("/financeiro")
@login_requerido
def financeiro_lista(gid):
    gabinete_da_conta(gid)
    registros=[financeiro(e) for e in Emenda.query.filter_by(gabinete_id=gid).order_by(Emenda.id.desc()).limit(500)]
    return jsonify({"registros":registros,"quantidade":len(registros),"com_alertas":sum(bool(r["alertas"]) for r in registros),"total_pago":round(sum(r["valores"]["pago"] for r in registros),2),"aviso":"Conferência aritmética de dados armazenados; não substitui validação em fonte oficial."})

@bp.get("/doublecheck")
@login_requerido
def doublecheck(gid):
    gabinete_da_conta(gid)
    itens=Minuta.query.filter_by(gabinete_id=gid).order_by(Minuta.id.desc()).limit(100).all()
    import json
    resultado=[]
    for m in itens:
        try: verificacao=json.loads(m.verificacao or "null")
        except (ValueError,TypeError): verificacao=None
        resultado.append({"id":m.id,"titulo":m.titulo,"tipo":m.tipo,"verificacao":verificacao,"verificado":bool(verificacao and verificacao.get("confirmado") is not None),"modelo":m.modelo})
    return jsonify({"minutas":resultado,"aviso":"A verificação por IA não equivale a validação jurídica ou conferência independente de fontes oficiais."})

@bp.get("/briefing")
@login_requerido
def briefing(gid):
    gabinete_da_conta(gid);hoje=date.today();limite=hoje+timedelta(days=7)
    tarefas=TarefaGabinete.query.filter(TarefaGabinete.gabinete_id==gid,TarefaGabinete.status!="concluida",TarefaGabinete.prazo!=None,TarefaGabinete.prazo<=limite).order_by(TarefaGabinete.prazo.asc()).limit(30).all()
    demandas=Demanda.query.filter(Demanda.gabinete_id==gid,Demanda.status!="concluida",Demanda.prazo!=None,Demanda.prazo<=limite).order_by(Demanda.prazo.asc()).limit(30).all()
    agenda=CompromissoGabinete.query.filter(CompromissoGabinete.gabinete_id==gid,CompromissoGabinete.inicio>=datetime.utcnow(),CompromissoGabinete.inicio<=datetime.utcnow()+timedelta(days=7)).order_by(CompromissoGabinete.inicio.asc()).limit(30).all()
    return jsonify({"gerado_em":datetime.utcnow().isoformat(),"tarefas":[x.dict() for x in tarefas],"demandas":[x.dict() for x in demandas],"agenda":[x.dict() for x in agenda],"radar_total":RadarProposicao.query.filter_by(gabinete_id=gid).count(),"financeiro_com_alertas":sum(bool(financeiro(e)["alertas"]) for e in Emenda.query.filter_by(gabinete_id=gid).limit(500)),"aviso":"Briefing determinístico dos registros internos; não representa monitoramento automático em tempo real."})
