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
    QUERIDO_DIARIO_URL = os.getenv("QUERIDO_DIARIO_URL", "https://api.queridodiario.ok.org.br",
    "https://api.queridodiario.org.br",).rstrip("/")
    TRANSFEREGOV_ESPECIAIS_URL = os.getenv("TRANSFEREGOV_ESPECIAIS_URL",
                                           "https://api-publica.transferegov.gestao.gov.br/especiais").rstrip("/")
    TRANSFEREGOV_ATIVO = os.getenv("TRANSFEREGOV_ATIVO", "sim").lower() in ("sim", "1", "true")
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
    # DOE-SP: a mesma busca pública usada pelo site doe.sp.gov.br (sem token). Conferida com chamada real em 29/09/2026:
    # GET {DOE_SP_URL}/advanced-search/publications?Terms[0]=...&FromDate=AAAA-MM-DD&ToDate=...&PageNumber=1&PageSize=20
    # Não é uma API documentada: se o site mudar, a busca pode quebrar — o monitor mostra o erro e o resto do app segue.
    DOE_SP_URL = os.getenv("DOE_SP_URL", "https://do-api-web-search.doe.sp.gov.br/v2").rstrip("/")
    DOE_SP_ATIVO = os.getenv("DOE_SP_ATIVO", "sim").lower() in ("sim", "1", "true")
    DOE_SP_MAX_PAGINAS = int(os.getenv("DOE_SP_MAX_PAGINAS", "5"))

    # ------------------------------------------------------------ clipping e alertas (Fase B)
    GOOGLE_NEWS_ATIVO = os.getenv("GOOGLE_NEWS_ATIVO", "sim").lower() in ("sim", "1", "true")
    SOCIAL_API_URL = os.getenv("SOCIAL_API_URL", "")          # endpoint do fornecedor de social listening
    SOCIAL_API_TOKEN = os.getenv("SOCIAL_API_TOKEN", "")
    CRISE_LIMIAR = int(os.getenv("CRISE_LIMIAR", "5"))        # menções negativas em 6h que disparam alerta
    WA_ENVIO_ATIVO = os.getenv("WA_ENVIO_ATIVO", "nao").lower() in ("sim", "true", "1")
    WA_TOKEN = os.getenv("WA_TOKEN", "")
    WA_PHONE_ID = os.getenv("WA_PHONE_ID", "")
    WA_TEMPLATE = os.getenv("WA_TEMPLATE", "alerta_mandato")
    WA_API_VERSAO = os.getenv("WA_API_VERSAO", "v21.0")
    MODELO_VOZ = os.getenv("MODELO_VOZ", "gpt-4o-mini-tts")
    VOZ_RESUMO = os.getenv("VOZ_RESUMO", "alloy")
