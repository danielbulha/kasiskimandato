"""Tabelas do Kasiski Mandato (SQLAlchemy). Tudo é organizado por gabinete, como o Kasiski organiza por CNPJ."""
import json
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


def _json(valor, padrao):
    try:
        return json.loads(valor) if valor else padrao
    except (TypeError, ValueError):
        return padrao


class Conta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    plano = db.Column(db.String(30), default="free")
    pago_ate = db.Column(db.Date)                        # liberado pelo admin após pagamento/empenho
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    usuarios = db.relationship("Usuario", backref="conta", lazy=True)


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(300), nullable=False)
    funcao = db.Column(db.String(80))                    # chefe de gabinete, assessor legislativo...
    telefone = db.Column(db.String(40))
    verificado = db.Column(db.Boolean)                   # None = conta anterior à verificação (tratada como verificada)
    ultimo_acesso = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def conferir_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def dict(self):
        return {"id": self.id, "nome": self.nome, "email": self.email, "funcao": self.funcao}


class CodigoVerificacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False, index=True)
    codigo_hash = db.Column(db.String(128), nullable=False)
    expira_em = db.Column(db.DateTime, nullable=False)
    tentativas = db.Column(db.Integer, default=0)
    usado_em = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


CARGOS = {"vereador": "Vereador(a)", "deputado_estadual": "Deputado(a) estadual", "deputado_distrital": "Deputado(a) distrital",
          "deputado_federal": "Deputado(a) federal", "senador": "Senador(a)"}
ESFERA_DO_CARGO = {"vereador": "municipal", "deputado_estadual": "estadual", "deputado_distrital": "estadual",
                   "deputado_federal": "federal", "senador": "federal"}


class Gabinete(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=False, index=True)
    parlamentar = db.Column(db.String(200), nullable=False)        # nome civil
    nome_parlamentar = db.Column(db.String(200))                    # nome de urna / como aparece nas emendas
    cargo = db.Column(db.String(30), nullable=False)
    casa = db.Column(db.String(200))                                # Câmara Municipal de X, ALESP, Câmara dos Deputados...
    uf = db.Column(db.String(2))
    municipio = db.Column(db.String(120))
    codigo_ibge = db.Column(db.String(7))                           # município-sede (vereador)
    base_ibge = db.Column(db.Text)                                  # JSON: [{"id": "3525508", "nome": "Juquitiba", "uf": "SP"}]
    regimento_texto = db.Column(db.Text)                            # Regimento Interno + Lei Orgânica/Constituição Estadual
    regimento_nome = db.Column(db.String(300))
    comunicado_automatico = db.Column(db.Boolean, default=False)    # gerar rascunhos quando uma emenda muda de fase
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def esfera(self):
        return ESFERA_DO_CARGO.get(self.cargo, "municipal")

    @property
    def base(self):
        return _json(self.base_ibge, [])

    def dict(self):
        return {"id": self.id, "parlamentar": self.parlamentar, "nome_parlamentar": self.nome_parlamentar, "cargo": self.cargo,
                "cargo_nome": CARGOS.get(self.cargo, self.cargo), "esfera": self.esfera, "casa": self.casa, "uf": self.uf,
                "municipio": self.municipio, "codigo_ibge": self.codigo_ibge, "base": self.base,
                "regimento_nome": self.regimento_nome, "regimento_caracteres": len(self.regimento_texto or ""),
                "comunicado_automatico": bool(self.comunicado_automatico)}


# Fases do ciclo de vida de uma emenda (a ordem importa: é a linha do tempo exibida no app)
FASES = ["indicada", "aprovada", "impedida", "empenhada", "liquidada", "paga", "executada", "cancelada"]


class Emenda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    esfera = db.Column(db.String(12), nullable=False)               # federal / estadual / municipal
    ano = db.Column(db.Integer)
    numero = db.Column(db.String(60))                               # número da emenda na lei orçamentária
    codigo_externo = db.Column(db.String(80), index=True)           # código no Portal da Transparência / Transferegov
    modalidade = db.Column(db.String(40))                           # transferencia_especial, finalidade_definida, impositiva...
    objeto = db.Column(db.Text)
    beneficiario = db.Column(db.String(300))                        # prefeitura, entidade, fundo
    municipio = db.Column(db.String(120))
    codigo_ibge = db.Column(db.String(7))
    funcao = db.Column(db.String(120))                              # saúde, educação...
    valor_indicado = db.Column(db.Float)
    valor_empenhado = db.Column(db.Float)
    valor_liquidado = db.Column(db.Float)
    valor_pago = db.Column(db.Float)
    fase = db.Column(db.String(20), default="indicada")
    proximo_prazo = db.Column(db.Date)
    proximo_prazo_descricao = db.Column(db.String(300))
    origem = db.Column(db.String(20), default="manual")             # manual / transparencia / transferegov
    observacoes = db.Column(db.Text)
    sincronizado_em = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    eventos = db.relationship("EventoEmenda", backref="emenda", lazy=True, cascade="all, delete-orphan",
                              order_by="EventoEmenda.data.desc()")

    def dict(self, eventos=False):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        for k in ("proximo_prazo", "sincronizado_em", "criado_em"):
            d[k] = d[k].isoformat() if d[k] else None
        d["percentual_pago"] = (round(100 * (self.valor_pago or 0) / self.valor_indicado)
                                if self.valor_indicado else None)
        if eventos:
            d["eventos"] = [e.dict() for e in self.eventos]
        return d


class EventoEmenda(db.Model):
    """Linha do tempo: cada mudança de fase ou de valor, com a fonte."""
    id = db.Column(db.Integer, primary_key=True)
    emenda_id = db.Column(db.Integer, db.ForeignKey("emenda.id"), nullable=False, index=True)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    tipo = db.Column(db.String(30))                                 # fase, valor, diario, nota
    fase = db.Column(db.String(20))
    descricao = db.Column(db.Text)
    valor = db.Column(db.Float)
    fonte = db.Column(db.String(60))                                # Portal da Transparência, Querido Diário, DOE-SP, TCE-SP, Gabinete
    url = db.Column(db.String(600))
    visto = db.Column(db.Boolean, default=False)

    def dict(self):
        return {"id": self.id, "emenda_id": self.emenda_id, "data": self.data.isoformat() if self.data else None,
                "tipo": self.tipo, "fase": self.fase, "descricao": self.descricao, "valor": self.valor,
                "fonte": self.fonte, "url": self.url, "visto": bool(self.visto)}


class MonitorDiario(db.Model):
    """Busca diária nos diários oficiais municipais (API do Querido Diário)."""
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    nome = db.Column(db.String(200))
    fonte = db.Column(db.String(20), default="querido_diario")      # querido_diario (municípios) / doe_sp (Estado de SP)
    termos = db.Column(db.Text)                                     # JSON: ["\"Maria Silva\"", "emenda impositiva"]
    territorios = db.Column(db.Text)                                # JSON: ["3525508", ...] — vazio = base do gabinete
    ativo = db.Column(db.Boolean, default=True)
    ultima_busca = db.Column(db.DateTime)
    ultimo_erro = db.Column(db.String(500))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def dict(self):
        return {"id": self.id, "nome": self.nome, "fonte": self.fonte or "querido_diario", "termos": _json(self.termos, []),
                "territorios": _json(self.territorios, []),
                "ativo": bool(self.ativo), "ultima_busca": self.ultima_busca.isoformat() if self.ultima_busca else None,
                "ultimo_erro": self.ultimo_erro}


class AchadoDiario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    monitor_id = db.Column(db.Integer, db.ForeignKey("monitor_diario.id"), index=True)
    emenda_id = db.Column(db.Integer, db.ForeignKey("emenda.id"))
    chave = db.Column(db.String(64), index=True)                    # hash(url + trecho) para não duplicar
    territorio = db.Column(db.String(160))
    uf = db.Column(db.String(2))
    data_publicacao = db.Column(db.Date)
    url = db.Column(db.String(600))
    termo = db.Column(db.String(200))
    trecho = db.Column(db.Text)
    classificacao = db.Column(db.String(40))                        # empenho, pagamento, licitacao, contrato, lei, outro
    resumo = db.Column(db.Text)
    relevancia = db.Column(db.String(10))                           # alta/media/baixa (IA barata)
    status = db.Column(db.String(20), default="novo")               # novo / vinculado / descartado
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def dict(self):
        return {"id": self.id, "monitor_id": self.monitor_id, "emenda_id": self.emenda_id, "territorio": self.territorio,
                "uf": self.uf, "data_publicacao": self.data_publicacao.isoformat() if self.data_publicacao else None,
                "url": self.url, "termo": self.termo, "trecho": self.trecho, "classificacao": self.classificacao,
                "resumo": self.resumo, "relevancia": self.relevancia, "status": self.status}


TIPOS_MINUTA = {"projeto_lei": "Projeto de lei", "indicacao": "Indicação", "requerimento": "Requerimento de informação",
                "mocao": "Moção", "emenda_orcamento": "Emenda ao orçamento (justificativa)"}


class Minuta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    tipo = db.Column(db.String(30), nullable=False)
    demanda = db.Column(db.Text, nullable=False)
    titulo = db.Column(db.String(400))
    texto = db.Column(db.Text)
    justificativa = db.Column(db.Text)
    analise = db.Column(db.Text)                                    # JSON: iniciativa, riscos, financiamento, fontes
    verificacao = db.Column(db.Text)                                # JSON da verificação cruzada
    modelo = db.Column(db.String(80))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def dict(self, completo=True):
        d = {"id": self.id, "tipo": self.tipo, "tipo_nome": TIPOS_MINUTA.get(self.tipo, self.tipo), "titulo": self.titulo,
             "demanda": self.demanda, "criado_em": self.criado_em.isoformat() if self.criado_em else None}
        if completo:
            d.update({"texto": self.texto, "justificativa": self.justificativa, "analise": _json(self.analise, {}),
                      "verificacao": _json(self.verificacao, None), "modelo": self.modelo})
        return d


FORMATOS = {"release": "Release para a imprensa", "discurso": "Discurso na tribuna", "post": "Post para redes sociais",
            "roteiro": "Roteiro de vídeo curto", "prestacao": "Prestação de contas ao eleitor"}


class Comunicado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    emenda_id = db.Column(db.Integer, db.ForeignKey("emenda.id"))
    evento_id = db.Column(db.Integer, db.ForeignKey("evento_emenda.id"))
    formato = db.Column(db.String(20), nullable=False)
    canal = db.Column(db.String(20), default="pessoal")             # pessoal (perfis do parlamentar) / institucional (Casa)
    tema = db.Column(db.Text)
    texto = db.Column(db.Text)
    alertas = db.Column(db.Text)                                    # JSON: avisos de conformidade
    status = db.Column(db.String(20), default="rascunho")           # rascunho / aprovado
    automatico = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def dict(self):
        return {"id": self.id, "emenda_id": self.emenda_id, "evento_id": self.evento_id, "formato": self.formato,
                "formato_nome": FORMATOS.get(self.formato, self.formato), "canal": self.canal, "tema": self.tema,
                "texto": self.texto, "alertas": _json(self.alertas, []), "status": self.status,
                "automatico": bool(self.automatico), "criado_em": self.criado_em.isoformat() if self.criado_em else None}


class UsoIA(db.Model):
    """Cada chamada de IA com custo — mesma base do módulo Custos de IA + Margem do Kasiski."""
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), index=True)
    tarefa = db.Column(db.String(40))
    provedor = db.Column(db.String(30))
    modelo = db.Column(db.String(80))
    tokens_entrada = db.Column(db.Integer, default=0)
    tokens_saida = db.Column(db.Integer, default=0)
    custo_usd = db.Column(db.Float, default=0)
    custo_brl = db.Column(db.Float, default=0)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)


STATUS_PEDIDO = {
    "aguardando_aprovacao": "Aguardando aprovação pelo e-mail oficial",
    "aguardando_pagamento": "Aprovado — aguardando pagamento",
    "liberado": "Liberado",
    "recusado": "Recusado pelo e-mail oficial",
    "expirado": "Link de aprovação expirado",
    "cancelado": "Cancelado",
}


class PedidoContratacao(db.Model):
    """Pedido de plano. Duas formas: Mercado Pago (cartão, Pix, boleto) ou faturamento para o Poder Público.
    Em ambas, o plano só é liberado depois da aprovação pelo e-mail OFICIAL do gabinete (link com validade)."""
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=False, index=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"))
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    plano = db.Column(db.String(30), nullable=False)
    periodicidade = db.Column(db.String(10), default="mensal")          # mensal / anual
    valor = db.Column(db.Float)
    forma = db.Column(db.String(20), nullable=False)                    # mercado_pago / faturamento
    # órgão contratante (faturamento) e responsável
    orgao_nome = db.Column(db.String(300))
    orgao_cnpj = db.Column(db.String(14))
    orgao_endereco = db.Column(db.String(400))
    orgao_municipio = db.Column(db.String(120))
    orgao_uf = db.Column(db.String(2))
    modalidade_contratacao = db.Column(db.String(40))                   # dispensa, inexigibilidade, adesao, reembolso, outra
    responsavel_nome = db.Column(db.String(200), nullable=False)
    responsavel_cargo = db.Column(db.String(120))
    responsavel_email = db.Column(db.String(200))
    responsavel_telefone = db.Column(db.String(40))
    financeiro_nome = db.Column(db.String(200))
    financeiro_email = db.Column(db.String(200))
    financeiro_telefone = db.Column(db.String(40))
    observacoes = db.Column(db.Text)
    # aprovação pelo e-mail oficial
    email_oficial = db.Column(db.String(200), nullable=False)
    aprovacao_hash = db.Column(db.String(64), index=True)
    aprovacao_enviada_em = db.Column(db.DateTime)
    aprovacao_expira_em = db.Column(db.DateTime)
    aprovado_em = db.Column(db.DateTime)
    aprovado_por = db.Column(db.String(200))                            # nome digitado por quem aprovou
    aprovado_ip = db.Column(db.String(64))
    recusado_em = db.Column(db.DateTime)
    # pagamento
    mp_preferencia_id = db.Column(db.String(80))
    mp_link = db.Column(db.String(600))
    mp_pagamento_id = db.Column(db.String(40))
    pago_em = db.Column(db.DateTime)
    nota_fiscal = db.Column(db.String(60))                              # faturamento: NFS-e emitida
    empenho = db.Column(db.String(60))                                  # faturamento: nota de empenho do órgão
    vencimento_fatura = db.Column(db.Date)
    liberado_em = db.Column(db.DateTime)
    status = db.Column(db.String(30), default="aguardando_aprovacao")
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def dict(self, admin=False):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns if c.name != "aprovacao_hash"}
        for k, v in list(d.items()):
            if isinstance(v, (datetime,)) or hasattr(v, "isoformat"):
                d[k] = v.isoformat() if v else None
        d["status_nome"] = STATUS_PEDIDO.get(self.status, self.status)
        if not admin:
            d.pop("aprovado_ip", None)
        return d
