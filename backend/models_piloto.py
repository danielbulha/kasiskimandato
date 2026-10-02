"""Tabelas aditivas do piloto; compatíveis com SQLite e PostgreSQL."""
from datetime import datetime
from extensions import db


class FonteLegal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey('gabinete.id'), nullable=False, index=True)
    tipo = db.Column(db.String(40), nullable=False)
    titulo = db.Column(db.String(300), nullable=False)
    url = db.Column(db.String(900), nullable=False)
    jurisdicao = db.Column(db.String(300), nullable=False)
    versao = db.Column(db.String(100), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    vetores = db.Column(db.Text, nullable=False)
    conferido_por = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    conferido_em = db.Column(db.DateTime, default=datetime.utcnow)
    ativo = db.Column(db.Boolean, default=True)


class RevisaoMinuta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    minuta_id = db.Column(db.Integer, db.ForeignKey('minuta.id'), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    conteudo_hash = db.Column(db.String(64), nullable=False)
    decisao = db.Column(db.String(20), nullable=False)
    parecer = db.Column(db.Text, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class Acompanhamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emenda_id = db.Column(db.Integer, db.ForeignKey('emenda.id'), unique=True, nullable=False)
    plano_id = db.Column(db.Integer, nullable=False)
    fonte = db.Column(db.String(20), default='especiais')
    proposta_id = db.Column(db.String(40))
    situacao = db.Column(db.String(300))
    revisao = db.Column(db.Integer, default=0, nullable=False)
    consultado_em = db.Column(db.DateTime)
    erro = db.Column(db.String(500))


class ConsentimentoWA(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gabinete_id = db.Column(db.Integer, db.ForeignKey('gabinete.id'), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    finalidade = db.Column(db.String(40), default='emendas', nullable=False)
    evidencia = db.Column(db.Text, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    revogado_em = db.Column(db.DateTime)


class NotificacaoWA(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    evento_id = db.Column(db.Integer, db.ForeignKey('evento_emenda.id'), nullable=False)
    consentimento_id = db.Column(db.Integer, db.ForeignKey('consentimento_wa.id'), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(30), default='pendente', nullable=False)
    tentativas = db.Column(db.Integer, default=0)
    provider_id = db.Column(db.String(300))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('evento_id', 'consentimento_id'),)
