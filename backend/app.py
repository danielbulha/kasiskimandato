"""Kasiski Mandato — copiloto do mandato parlamentar. Ponto de entrada do backend (Flask).

Mesmo padrão do Kasiski Licitações: Flask + SQLAlchemy + JWT, Postgres no Render, frontend estático no Netlify.
"""
import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from config import Config
from extensions import ErroAPI, db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)
    app.json.sort_keys = False
    checar_seguranca(app)
    CORS(app, resources={r"/api/*": {"origins": origens_cors(app)}}, expose_headers=["Content-Disposition"])
    db.init_app(app)

    from routes import registrar
    registrar(app)
    from services import logs
    logs.instalar(app)

    @app.get("/api/saude")
    def saude():
        from services.llm import modo_demonstracao
        return jsonify({"ok": True, "produto": "kasiski-mandato", "modo_demonstracao": modo_demonstracao()})

    @app.after_request
    def _cabecalhos(resp):
        h = resp.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        if app.config.get("PRODUCAO"):
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return resp

    @app.errorhandler(ErroAPI)
    def erro_api(e):
        if e.status >= 500:   # falhas de integração (502) viram aviso na aba Logs; erros de validação (4xx), não
            logs.registrar("servidor", e.mensagem, status=e.status, nivel="aviso")
        return jsonify({"erro": e.mensagem, "codigo": e.codigo}), e.status

    @app.errorhandler(HTTPException)
    def erro_http(e):
        msgs = {404: "Não encontrado.", 405: "Operação não permitida.", 413: "Arquivo grande demais (máximo 30 MB)."}
        return jsonify({"erro": msgs.get(e.code, e.description)}), e.code

    @app.errorhandler(Exception)
    def erro_geral(e):
        db.session.rollback()
        app.logger.exception("Erro inesperado: %s", e)
        return jsonify({"erro": "Erro inesperado no servidor. Tente novamente."}), 500

    with app.app_context():
        db.create_all()
        _migrar_colunas_novas(app)
    return app


def checar_seguranca(app):
    cfg = app.config
    fraca = not cfg.get("SECRET_KEY") or cfg["SECRET_KEY"] == cfg["CHAVE_PADRAO"] or len(cfg["SECRET_KEY"]) < 32
    if cfg.get("PRODUCAO") and fraca and not os.getenv("KASISKI_JOB"):
        raise RuntimeError("SECRET_KEY ausente, padrão ou curta (mínimo 32 caracteres). Defina-a no Render.")


def origens_cors(app):
    bruto = (app.config.get("CORS_ORIGINS") or "").strip()
    lista = [o.strip().rstrip("/") for o in bruto.split(",") if o.strip() and o.strip() != "*"]
    if app.config.get("PRODUCAO") and not lista:
        lista = [app.config["FRONTEND_URL"]]
    return lista or "*"


def _migrar_colunas_novas(app):
    """Mesmo helper do Kasiski: adiciona colunas novas em tabelas existentes (sem Alembic)."""
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    for tabela in db.metadata.tables.values():
        if not insp.has_table(tabela.name):
            continue
        existentes = {c["name"] for c in insp.get_columns(tabela.name)}
        for coluna in tabela.columns:
            if coluna.name not in existentes:
                tipo = coluna.type.compile(db.engine.dialect)
                with db.engine.begin() as conn:
                    conn.execute(text(f'ALTER TABLE "{tabela.name}" ADD COLUMN "{coluna.name}" {tipo}'))
                app.logger.info("Migração: coluna %s.%s adicionada", tabela.name, coluna.name)


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", "5001")))
