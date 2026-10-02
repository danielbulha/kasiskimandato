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
    pago_ate = db.Column(db.Date)                        # validade do plano pago
    preco_contratado = db.Column(db.Float)               # preço negociado (vazio = preço de tabela)
    ciclo = db.Column(db.String(10))                     # mensal / anual
    trial_plano = db.Column(db.String(30))               # teste concedido pelo admin
    trial_fim = db.Column(db.Date)
    notas_crm = db.Column(db.Text)
    etiqueta_crm = db.Column(db.String(30))
    telefone = db.Column(db.String(30))
    bloqueada = db.Column(db.Boolean, default=False)     # acesso suspenso pelo admin
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
    # dados públicos do TSE (preenchimento automático)
    partido = db.Column(db.String(30))
    numero_urna = db.Column(db.String(10))
    foto_url = db.Column(db.String(400))
    tse_candidato_id = db.Column(db.String(30))
    tse_ano = db.Column(db.Integer)
    # integrações e página pública
    sapl_url = db.Column(db.String(300))                            # SAPL da Casa (câmaras municipais que usam o Interlegis)
    slug_publico = db.Column(db.String(80), unique=True)
    pagina_publica = db.Column(db.Boolean, default=False)
    whatsapp_alertas = db.Column(db.String(20))                     # telefone do chefe de gabinete (E.164, só dígitos)
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
                "comunicado_automatico": bool(self.comunicado_automatico), "partido": self.partido,
                "numero_urna": self.numero_urna, "foto_url": self.foto_url, "tse_ano": self.tse_ano, "sapl_url": self.sapl_url,
                "slug_publico": self.slug_publico, "pagina_publica": bool(self.pagina_publica),
                "whatsapp_alertas": self.whatsapp_alertas}


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
    publicar = db.Column(db.Boolean, default=False)                 # aparece na página pública de prestação de contas
    situacao_plano_acao = db.Column(db.String(60))                  # Transferegov (transferências especiais)
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
        from services import risco
        d["riscos"] = risco.avaliar(self)
        d["risco"] = risco.nivel(d["riscos"])
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


class LogErro(db.Model):
    """Erros do sistema (servidor, tarefas e navegador) para a aba Logs do admin — mesmo modelo do Kasiski."""
    id = db.Column(db.Integer, primary_key=True)
    origem = db.Column(db.String(20), index=True)
    nivel = db.Column(db.String(10), default="erro")
    mensagem = db.Column(db.Text)
    detalhe = db.Column(db.Text)
    rota = db.Column(db.String(300))
    metodo = db.Column(db.String(10))
    status = db.Column(db.Integer)
    usuario_email = db.Column(db.String(200))
    conta_id = db.Column(db.Integer, index=True)
    navegador = db.Column(db.String(300))
    assinatura = db.Column(db.String(64), index=True)
    ocorrencias = db.Column(db.Integer, default=1)
    resolvido = db.Column(db.Boolean, default=False, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ultimo_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def dict(self, completo=False):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns if completo or c.name != "detalhe"}
        for k in ("criado_em", "ultimo_em"):
            d[k] = d[k].isoformat() if d.get(k) else None
        return d


class Lead(db.Model):
    """Prospecção comercial: gabinetes eleitos (dados públicos do TSE) acompanhados pelo admin."""
    id = db.Column(db.Integer, primary_key=True)
    tse_candidato_id = db.Column(db.String(30), unique=True)
    nome_urna = db.Column(db.String(200))
    cargo = db.Column(db.String(30))
    partido = db.Column(db.String(30))
    uf = db.Column(db.String(2))
    municipio = db.Column(db.String(120))
    ano = db.Column(db.Integer)
    status = db.Column(db.String(20), default="novo")              # novo, contatado, reuniao, proposta, cliente, descartado
    notas = db.Column(db.Text)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def dict(self):
        return {c.name: (getattr(self, c.name).isoformat() if isinstance(getattr(self, c.name), datetime) else getattr(self, c.name))
                for c in self.__table__.columns}


class AnaliseProposicao(db.Model):
    """Copiloto Legislativo: proposição de uma base pública (ou texto enviado) analisada pela IA."""
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    fonte = db.Column(db.String(20))                                # camara, senado, sapl, texto
    id_externo = db.Column(db.String(60))
    identificacao = db.Column(db.String(120))                       # PL 4544/2026
    ementa = db.Column(db.Text)
    url = db.Column(db.String(600))
    situacao = db.Column(db.String(300))
    resultado = db.Column(db.Text)                                  # JSON: resumo, pontos, riscos, comparacao, posicao
    verificacao = db.Column(db.Text)
    comparacoes = db.Column(db.Text)                                # JSON: leis/propostas parecidas encontradas
    modelo = db.Column(db.String(80))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def dict(self, completo=True):
        d = {"id": self.id, "fonte": self.fonte, "id_externo": self.id_externo, "identificacao": self.identificacao,
             "ementa": self.ementa, "url": self.url, "situacao": self.situacao,
             "criado_em": self.criado_em.isoformat() if self.criado_em else None}
        if completo:
            d.update({"resultado": _json(self.resultado, {}), "verificacao": _json(self.verificacao, None),
                      "comparacoes": _json(self.comparacoes, []), "modelo": self.modelo})
        return d


TIPOS_TEMA = {"mandato": "O próprio mandato", "tema": "Tema de interesse", "adversario": "Adversário / figura pública"}


class TemaMonitorado(db.Model):
    """Clipping: o que monitorar (o mandato, um tema, um adversário)."""
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    nome = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), default="tema")
    termos = db.Column(db.Text)                                     # JSON
    feeds = db.Column(db.Text)                                      # JSON: URLs de RSS de veículos regionais
    ativo = db.Column(db.Boolean, default=True)
    ultima_busca = db.Column(db.DateTime)
    ultimo_erro = db.Column(db.String(500))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def dict(self):
        return {"id": self.id, "nome": self.nome, "tipo": self.tipo, "tipo_nome": TIPOS_TEMA.get(self.tipo, self.tipo),
                "termos": _json(self.termos, []), "feeds": _json(self.feeds, []), "ativo": bool(self.ativo),
                "ultima_busca": self.ultima_busca.isoformat() if self.ultima_busca else None, "ultimo_erro": self.ultimo_erro}


class Mencao(db.Model):
    """Uma menção encontrada. Minimização (LGPD): de pessoas comuns não se guarda nome nem perfil — só texto público,
    link e sentimento. Autor só é guardado quando é veículo de imprensa ou conta pública verificada."""
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    tema_id = db.Column(db.Integer, db.ForeignKey("tema_monitorado.id"), index=True)
    chave = db.Column(db.String(64), index=True)
    canal = db.Column(db.String(20))                                # noticia, social, diario
    rede = db.Column(db.String(20))                                 # instagram, tiktok, x... (social)
    veiculo = db.Column(db.String(200))
    titulo = db.Column(db.Text)
    trecho = db.Column(db.Text)
    url = db.Column(db.String(800))
    publicado_em = db.Column(db.DateTime, index=True)
    sentimento = db.Column(db.String(10))                           # positivo, negativo, neutro
    crise = db.Column(db.Boolean, default=False)
    engajamento = db.Column(db.Integer)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def dict(self):
        return {"id": self.id, "tema_id": self.tema_id, "canal": self.canal, "rede": self.rede, "veiculo": self.veiculo,
                "titulo": self.titulo, "trecho": self.trecho, "url": self.url,
                "publicado_em": self.publicado_em.isoformat() if self.publicado_em else None, "sentimento": self.sentimento,
                "crise": bool(self.crise), "engajamento": self.engajamento}


class ResumoDiario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    data = db.Column(db.Date, index=True)
    texto = db.Column(db.Text)
    numeros = db.Column(db.Text)                                    # JSON: totais por sentimento/canal
    audio = db.Column(db.LargeBinary)                               # MP3 (TTS), opcional
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def dict(self):
        return {"id": self.id, "data": self.data.isoformat() if self.data else None, "texto": self.texto,
                "numeros": _json(self.numeros, {}), "tem_audio": bool(self.audio)}


class AlertaEnviado(db.Model):
    """Registro dos alertas de crise (WhatsApp/e-mail), para não repetir o mesmo alerta."""
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    chave = db.Column(db.String(64), index=True)
    canal = db.Column(db.String(20))
    texto = db.Column(db.Text)
    enviado = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class EleitoTSE(db.Model):
    """Eleitos importados do Portal de Dados Abertos do TSE (consulta_cand_{ano}.zip). Só identificação pública."""
    id = db.Column(db.Integer, primary_key=True)
    ano = db.Column(db.Integer, index=True)
    uf = db.Column(db.String(2), index=True)
    municipio = db.Column(db.String(120), index=True)              # NM_UE (eleição municipal); vazio na geral
    cargo = db.Column(db.String(30), index=True)                   # código do Kasiski (vereador, deputado_federal...)
    sq_candidato = db.Column(db.String(20), index=True)
    numero = db.Column(db.String(10))
    nome_urna = db.Column(db.String(200))
    nome_completo = db.Column(db.String(200))
    nome_busca = db.Column(db.String(400), index=True)             # sem acento, minúsculo (urna + civil)
    partido = db.Column(db.String(30))
    resultado = db.Column(db.String(60))


class ImportacaoTSE(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ano = db.Column(db.Integer, unique=True)
    status = db.Column(db.String(20))                              # rodando / ok / erro
    eleitos = db.Column(db.Integer, default=0)
    erro = db.Column(db.String(500))
    iniciado_em = db.Column(db.DateTime)
    terminado_em = db.Column(db.DateTime)

    def dict(self):
        return {"ano": self.ano, "status": self.status, "eleitos": self.eleitos, "erro": self.erro,
                "iniciado_em": self.iniciado_em.isoformat() if self.iniciado_em else None,
                "terminado_em": self.terminado_em.isoformat() if self.terminado_em else None}


class HistoricoConta(db.Model):
    """Trilha das ações do admin sobre contas (mudança de plano, teste, exclusão...). Sem FK: sobrevive à exclusão."""
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, index=True)
    conta_nome = db.Column(db.String(200))
    admin_email = db.Column(db.String(200))
    acao = db.Column(db.String(60))
    detalhe = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def dict(self):
        return {"id": self.id, "conta_id": self.conta_id, "conta_nome": self.conta_nome, "admin_email": self.admin_email,
                "acao": self.acao, "detalhe": self.detalhe, "criado_em": self.criado_em.isoformat() if self.criado_em else None}


# v7: registros operacionais separados por gabinete.
class Demanda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    protocolo = db.Column(db.String(35), unique=True, nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    solicitante = db.Column(db.String(200))
    contato = db.Column(db.String(200))
    municipio = db.Column(db.String(120))
    categoria = db.Column(db.String(80))
    status = db.Column(db.String(35), default="recebida", nullable=False)
    prioridade = db.Column(db.String(20), default="normal")
    responsavel_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    prazo = db.Column(db.Date)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def dict(self):
        return {k: (getattr(self,k).isoformat() if getattr(self,k) is not None and k in ("prazo","criado_em","atualizado_em") else getattr(self,k)) for k in ("id","gabinete_id","protocolo","titulo","descricao","solicitante","contato","municipio","categoria","status","prioridade","responsavel_id","prazo","criado_em","atualizado_em")}

class TarefaGabinete(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    demanda_id = db.Column(db.Integer, db.ForeignKey("demanda.id"), index=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    status = db.Column(db.String(35), default="a_fazer", nullable=False)
    prioridade = db.Column(db.String(20), default="normal")
    responsavel_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    prazo = db.Column(db.Date)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    def dict(self):
        return {k: (getattr(self,k).isoformat() if getattr(self,k) is not None and k in ("prazo","criado_em") else getattr(self,k)) for k in ("id","gabinete_id","demanda_id","titulo","descricao","status","prioridade","responsavel_id","prazo","criado_em")}

class CompromissoGabinete(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    demanda_id = db.Column(db.Integer, db.ForeignKey("demanda.id"), index=True)
    titulo = db.Column(db.String(200), nullable=False)
    local = db.Column(db.String(200))
    pauta = db.Column(db.Text)
    inicio = db.Column(db.DateTime, nullable=False)
    fim = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    def dict(self):
        return {k: (getattr(self,k).isoformat() if getattr(self,k) is not None and k in ("inicio","fim","criado_em") else getattr(self,k)) for k in ("id","gabinete_id","demanda_id","titulo","local","pauta","inicio","fim","criado_em")}

class EventoOperacional(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    entidade = db.Column(db.String(30), nullable=False)
    entidade_id = db.Column(db.Integer, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    descricao = db.Column(db.String(500), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    def dict(self):
        return {"id":self.id,"entidade":self.entidade,"entidade_id":self.entidade_id,"descricao":self.descricao,"usuario_id":self.usuario_id,"criado_em":self.criado_em.isoformat()}


class RadarProposicao(db.Model):
    __tablename__ = "radar_proposicao"
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey("gabinete.id"), nullable=False, index=True)
    identificacao = db.Column(db.String(160), nullable=False)
    fonte = db.Column(db.String(100), nullable=False, default="manual")
    url = db.Column(db.String(900))
    ementa = db.Column(db.Text)
    situacao = db.Column(db.String(300))
    texto = db.Column(db.Text)
    versao = db.Column(db.Integer, nullable=False, default=1)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow)
    def dict(self):
        return {"id":self.id,"identificacao":self.identificacao,"fonte":self.fonte,"url":self.url,"ementa":self.ementa,"situacao":self.situacao,"texto":self.texto,"versao":self.versao,"atualizado_em":self.atualizado_em.isoformat() if self.atualizado_em else None}

class RadarVersao(db.Model):
    __tablename__ = "radar_versao"
    id = db.Column(db.Integer, primary_key=True)
    radar_id = db.Column(db.Integer, db.ForeignKey("radar_proposicao.id"), nullable=False, index=True)
    versao = db.Column(db.Integer, nullable=False)
    texto = db.Column(db.Text)
    situacao = db.Column(db.String(300))
    registrado_em = db.Column(db.DateTime, default=datetime.utcnow)
