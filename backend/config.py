"""Configurações do Kasiski Mandato. Tudo vem de variáveis de ambiente (arquivo .env em dev).

Mesmo padrão do Kasiski Licitações (repositório danielbulha/kasiski), com backend próprio no Render.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _lista(nome):
    return [x.strip().lower() for x in os.getenv(nome, "").split(",") if x.strip()]


class Config:
    PRODUCAO = os.getenv("RENDER", "").lower() == "true" or os.getenv("PRODUCAO", "").lower() in ("sim", "1", "true")
    CHAVE_PADRAO = "troque-esta-chave-em-producao"
    SECRET_KEY = os.getenv("SECRET_KEY", CHAVE_PADRAO)

    _db = os.getenv("DATABASE_URL", "sqlite:///mandato.db")
    if _db.startswith("postgres://"):  # Render entrega assim; SQLAlchemy exige postgresql://
        _db = _db.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    MAX_CONTENT_LENGTH = 30 * 1024 * 1024  # 30 MB (regimento interno / lei orgânica em PDF)

    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "https://mandato.kasiski.com.br")
    SITE_URL = os.getenv("SITE_URL", "https://kasiski.com.br")
    ADMIN_EMAILS = _lista("ADMIN_EMAILS")
    TOKEN_HORAS = int(os.getenv("TOKEN_HORAS", "72"))

    # IA (vazias = modo demonstração, como no Kasiski Licitações)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    MODELO_CLAUDE = os.getenv("MODELO_CLAUDE", "claude-sonnet-5")
    MODELO_CLAUDE_BARATO = os.getenv("MODELO_CLAUDE_BARATO", "claude-haiku-4-5-20251001")
    MODELO_OPENAI = os.getenv("MODELO_OPENAI", "gpt-4.1-mini")
    MODELO_GEMINI = os.getenv("MODELO_GEMINI", "gemini-2.5-flash")
    USD_BRL = float(os.getenv("USD_BRL", "5.5"))

    # Dados públicos
    PORTAL_TRANSPARENCIA_KEY = os.getenv("PORTAL_TRANSPARENCIA_KEY", "")      # a mesma chave grátis do Kasiski
    QUERIDO_DIARIO_URL = os.getenv("QUERIDO_DIARIO_URL", "https://api.queridodiario.ok.org.br").rstrip("/")
    TRANSFEREGOV_ESPECIAIS_URL = os.getenv("TRANSFEREGOV_ESPECIAIS_URL",
                                           "https://api.transferegov.gestao.gov.br/transferenciasespeciais").rstrip("/")
    TRANSFEREGOV_ATIVO = os.getenv("TRANSFEREGOV_ATIVO", "nao").lower() in ("sim", "1", "true")
    MAX_CHARS_REGIMENTO = int(os.getenv("MAX_CHARS_REGIMENTO", "400000"))

    # Período eleitoral (Lei 9.504/97, art. 73, VI, "b" e §3º): nos 3 meses antes do pleito, publicidade institucional
    # fica vedada para as esferas cujos cargos estão em disputa. Formato: data_do_1º_turno:tipo (geral ou municipal).
    # A janela vai até ELEICAO_DIAS_APOS dias depois do 1º turno, para cobrir um eventual 2º turno.
    ELEICOES = [tuple(x.strip().split(":")) for x in os.getenv("ELEICOES", "2026-10-04:geral,2028-10-01:municipal").split(",")
                if ":" in x]
    ELEICAO_DIAS_APOS = int(os.getenv("ELEICAO_DIAS_APOS", "21"))

    # E-mail (Resend) — mesmo provedor do Kasiski Licitações
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE", "Kasiski Mandato <nao-responda@kasiski.com.br>")
    VERIFICAR_EMAIL = os.getenv("VERIFICAR_EMAIL", "auto").lower()   # auto = exige se o Resend estiver configurado
    CONTATO_COMERCIAL = os.getenv("CONTATO_COMERCIAL", "contato@kasiski.com.br")

    # ------------------------------------------------------------ ambiente de teste
    # AMBIENTE=teste: faixa "Versão de teste" no app, link de aprovação devolvido na tela (dispensa e-mail real),
    # simulação de pagamento liberada e Mercado Pago em credenciais de teste (TEST-...).
    AMBIENTE = os.getenv("AMBIENTE", "producao").lower()
    TESTE = AMBIENTE == "teste"
    TESTE_QUALQUER_EMAIL = os.getenv("TESTE_QUALQUER_EMAIL", "nao").lower() in ("sim", "1", "true")

    # ------------------------------------------------------------ contratação
    # Domínios aceitos como "e-mail oficial do gabinete" (sufixo). A liberação do plano exige aprovação por um deles.
    DOMINIOS_OFICIAIS = [d.strip().lower() for d in os.getenv("DOMINIOS_OFICIAIS", ".leg.br,.gov.br").split(",") if d.strip()]
    APROVACAO_DIAS = int(os.getenv("APROVACAO_DIAS", "7"))
    FATURA_DIAS = int(os.getenv("FATURA_DIAS", "30"))          # prazo de pagamento da fatura ao Poder Público
    ANUAL_MESES_PAGOS = int(os.getenv("ANUAL_MESES_PAGOS", "10"))
    BACKEND_URL = os.getenv("BACKEND_URL", "").rstrip("/")
    MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
    MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
    MP_EMAIL_COMPRADOR_TESTE = os.getenv("MP_EMAIL_COMPRADOR_TESTE", "")
    NFSE_PRESTADOR_RAZAO = os.getenv("NFSE_PRESTADOR_RAZAO", "D.B.C. Consultoria e Serviços Ltda.")
    NFSE_PRESTADOR_CNPJ = os.getenv("NFSE_PRESTADOR_CNPJ", "01.152.886/0001-51")

    # ------------------------------------------------------------ Estado de São Paulo
    # TCE-SP: API pública do Portal da Transparência Municipal (receitas e despesas dos municípios paulistas).
    TCE_SP_URL = os.getenv("TCE_SP_URL", "https://transparencia.tce.sp.gov.br/api/json").rstrip("/")
    # DOE-SP: API oficial do Diário Oficial via Integrador de APIs do Estado (credencial obtida pelo gov.br).
    # Vazio = desligado. Os nomes de parâmetros ficam configuráveis até conferir a documentação do credenciamento.
    DOE_SP_API_URL = os.getenv("DOE_SP_API_URL", "").rstrip("/")
    DOE_SP_TOKEN = os.getenv("DOE_SP_TOKEN", "")
    DOE_SP_BUSCA_CAMINHO = os.getenv("DOE_SP_BUSCA_CAMINHO", "/publications/search")
    DOE_SP_PARAM_TERMO = os.getenv("DOE_SP_PARAM_TERMO", "terms")
    DOE_SP_PARAM_DE = os.getenv("DOE_SP_PARAM_DE", "fromDate")
    DOE_SP_PARAM_ATE = os.getenv("DOE_SP_PARAM_ATE", "toDate")
