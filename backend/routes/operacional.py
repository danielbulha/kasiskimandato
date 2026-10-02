"""API operacional v7: dados sempre isolados pelo gabinete da conta autenticada."""
from datetime import date, datetime, timedelta
from uuid import uuid4
from flask import Blueprint, jsonify, g, request
from auth import login_requerido
from extensions import db, ErroAPI
from models import Demanda, TarefaGabinete, CompromissoGabinete, EventoOperacional, Usuario
from routes import gabinete_da_conta

bp = Blueprint("operacional", __name__, url_prefix="/api/gabinetes/<int:gid>")
CONFIG = {
 "demandas": (Demanda, {"recebida","em_analise","aguardando","em_execucao","concluida"}),
 "tarefas": (TarefaGabinete, {"a_fazer","em_andamento","aguardando","concluida"}),
 "agenda": (CompromissoGabinete, None),
}

def valor_data(v, hora=False):
    if not v: return None
    try: return datetime.fromisoformat(v) if hora else date.fromisoformat(v)
    except (ValueError, TypeError): raise ErroAPI("Data inválida.",400)

def validar_vinculos(gid, d):
    if d.get("responsavel_id") not in (None, ""):
        if not Usuario.query.filter_by(id=int(d["responsavel_id"]), conta_id=g.conta.id).first(): raise ErroAPI("Responsável inválido.",400)
    if d.get("demanda_id") not in (None, ""):
        if not Demanda.query.filter_by(id=int(d["demanda_id"]), gabinete_id=gid).first(): raise ErroAPI("Demanda vinculada inválida.",400)

def aplicar(obj, d, tipo, gid):
    permitidos = {"demandas": ("titulo","descricao","solicitante","contato","municipio","categoria","status","prioridade","responsavel_id","prazo"),
                  "tarefas": ("titulo","descricao","status","prioridade","responsavel_id","prazo","demanda_id"),
                  "agenda": ("titulo","local","pauta","inicio","fim","demanda_id")}[tipo]
    validar_vinculos(gid,d)
    for k in permitidos:
        if k not in d: continue
        v=d[k]
        if k in ("prazo","inicio","fim"): v=valor_data(v,k in ("inicio","fim"))
        elif k in ("responsavel_id","demanda_id"): v=int(v) if v not in (None,"") else None
        elif k in ("titulo","descricao","solicitante","contato","municipio","categoria","status","prioridade","local","pauta"):
            v=str(v or "").strip()[:(10000 if k in ("descricao","pauta") else 200)]
        setattr(obj,k,v)
    if not obj.titulo: raise ErroAPI("Informe o título.",400)
    estados=CONFIG[tipo][1]
    if estados and obj.status not in estados: raise ErroAPI("Status inválido.",400)
    if hasattr(obj,"prioridade") and obj.prioridade not in ("baixa","normal","alta","urgente"): raise ErroAPI("Prioridade inválida.",400)
    if tipo=="agenda" and (not obj.inicio or obj.fim and obj.fim < obj.inicio): raise ErroAPI("Horário inválido.",400)

def evento(gid,tipo,obj,acao):
    db.session.add(EventoOperacional(gabinete_id=gid,entidade=tipo,entidade_id=obj.id,usuario_id=g.usuario.id,descricao=f"{acao}: {obj.titulo[:180]}"))

@bp.get("/operacional/resumo")
@login_requerido
def resumo(gid):
    gabinete_da_conta(gid)
    hoje=date.today(); limite=hoje+timedelta(days=7)
    demandas=Demanda.query.filter_by(gabinete_id=gid)
    tarefas=TarefaGabinete.query.filter_by(gabinete_id=gid)
    return jsonify({"demandas_abertas":demandas.filter(Demanda.status!="concluida").count(),"tarefas_abertas":tarefas.filter(TarefaGabinete.status!="concluida").count(),"tarefas_vencidas":tarefas.filter(TarefaGabinete.status!="concluida",TarefaGabinete.prazo<hoje).count(),"agenda_proxima":CompromissoGabinete.query.filter(CompromissoGabinete.gabinete_id==gid,CompromissoGabinete.inicio>=datetime.utcnow(),CompromissoGabinete.inicio<=datetime.utcnow()+timedelta(days=7)).count(),"eventos":[x.dict() for x in EventoOperacional.query.filter_by(gabinete_id=gid).order_by(EventoOperacional.id.desc()).limit(8)]})

@bp.route("/operacional/<tipo>",methods=["GET","POST"])
@login_requerido
def colecao(gid,tipo):
    gabinete_da_conta(gid)
    if tipo not in CONFIG: raise ErroAPI("Recurso desconhecido.",404)
    modelo,_=CONFIG[tipo]
    if request.method=="GET":
        q=modelo.query.filter_by(gabinete_id=gid)
        if request.args.get("status") and hasattr(modelo,"status"): q=q.filter_by(status=request.args["status"])
        return jsonify([x.dict() for x in q.order_by(modelo.id.desc()).limit(500).all()])
    d=request.get_json(silent=True) or {}
    obj=modelo(gabinete_id=gid)
    aplicar(obj,d,tipo,gid)
    if tipo=="demandas": obj.protocolo=f"KM-{datetime.utcnow():%y%m%d}-{uuid4().hex[:8].upper()}"
    db.session.add(obj); db.session.flush(); evento(gid,tipo,obj,"Criado"); db.session.commit()
    return jsonify(obj.dict()),201

@bp.route("/operacional/<tipo>/<int:ident>",methods=["GET","PUT","DELETE"])
@login_requerido
def item(gid,tipo,ident):
    gabinete_da_conta(gid)
    if tipo not in CONFIG: raise ErroAPI("Recurso desconhecido.",404)
    modelo,_=CONFIG[tipo]
    obj=modelo.query.filter_by(id=ident,gabinete_id=gid).first()
    if not obj: raise ErroAPI("Registro não encontrado.",404)
    if request.method=="GET": return jsonify(obj.dict())
    if request.method=="DELETE":
        if tipo=="demandas" and (TarefaGabinete.query.filter_by(demanda_id=ident).first() or CompromissoGabinete.query.filter_by(demanda_id=ident).first()): raise ErroAPI("Desvincule tarefas e compromissos antes de excluir a demanda.",409)
        evento(gid,tipo,obj,"Excluído"); db.session.delete(obj); db.session.commit(); return jsonify({"ok":True})
    aplicar(obj,request.get_json(silent=True) or {},tipo,gid)
    evento(gid,tipo,obj,"Atualizado"); db.session.commit(); return jsonify(obj.dict())
