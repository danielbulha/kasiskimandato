"""Teste de ponta a ponta com as APIs públicas SIMULADAS (formato conforme a documentação de cada uma).

Uso: cd backend && python testes/teste_ponta_a_ponta.py
Roda em SQLite em memória, modo demonstração (sem chaves de IA) e sem rede.
"""
import io
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.update({"DATABASE_URL": "sqlite://", "ADMIN_EMAILS": "admin@teste.br", "PORTAL_TRANSPARENCIA_KEY": "x",
                   "VERIFICAR_EMAIL": "nao", "AMBIENTE": "teste", "MP_ACCESS_TOKEN": "TEST-123",
                   })

import requests  # noqa: E402

PAGO = {"v": "0,00"}


class R:
    def __init__(self, dados, status=200, texto=""):
        self._d, self.status_code, self.text = dados, status, texto
        self.content = texto.encode()

    def json(self):
        return self._d

    def raise_for_status(self):
        pass


def falso_get(url, params=None, headers=None, timeout=None):
    p = dict(params) if isinstance(params, dict) else {}
    if "api-de-dados/emendas" in url:
        if p.get("pagina") != 1 or p.get("ano") != date.today().year:
            return R([])
        return R([{"codigoEmenda": "202637150001", "ano": date.today().year, "tipoEmenda": "Emenda Individual - Transferências Especiais",
                   "nomeAutor": "FULANO DE TAL", "numeroEmenda": "37150001", "localidadeDoGasto": "JUQUITIBA - SP",
                   "funcao": "Saúde", "valorEmpenhado": "500.000,00", "valorLiquidado": "0,00", "valorPago": PAGO["v"],
                   "valorRestoPago": "0,00"}])
    if url.endswith("/gazettes"):
        return R({"total_gazettes": 1, "gazettes": [{"territory_id": "3525508", "territory_name": "Juquitiba", "state_code": "SP",
                  "date": date.today().isoformat(), "url": "https://exemplo/diario.pdf",
                  "excerpts": ["Nota de empenho referente à emenda 37150001 do Deputado Fulano de Tal, reforma da UBS."]}]})
    if url.endswith("/cities"):
        return R({"cities": [{"territory_id": "3525508", "territory_name": "Juquitiba", "state_code": "SP"}]})
    if "tce.sp.gov.br" in url:
        if url.endswith("/municipios"):
            return R([{"municipio": "juquitiba", "municipio_extenso": "Juquitiba"}])
        if "/receitas/juquitiba/" in url:
            return R([{"orgao": "PREFEITURA MUNICIPAL DE JUQUITIBA", "mes": "Julho", "ds_fonte_recurso": "02 - TRANSFERÊNCIAS E CONVÊNIOS ESTADUAIS-VINCULADOS",
                       "ds_alinea": "24210000 - TRANSFERÊNCIAS DE CONVÊNIOS DOS ESTADOS", "ds_subalinea": "24219900 - OUTRAS",
                       "vl_arrecadacao": "250.000,00"},
                      {"orgao": "PREFEITURA MUNICIPAL DE JUQUITIBA", "mes": "Julho", "ds_fonte_recurso": "01 - TESOURO",
                       "ds_alinea": "17220100 - ICMS", "ds_subalinea": "", "vl_arrecadacao": "900.000,00"}])
        return R([])
    if url.startswith("https://do-api-web-search.doe.sp.gov.br/v2/advanced-search/publications"):
        assert p.get("Terms[0]") and p.get("FromDate") and p.get("PageNumber")
        return R({"items": [{"isLegacy": False, "id": "ac73770b", "date": date.today().isoformat() + "T01:00:43",
                             "title": "DESPACHO Nº 843", "slug": "executivo/secretaria/despacho-n-843",
                             "excerpt": "Termo de Convênio nº 09/2026, proveniente de Emenda Parlamentar 37150001 do deputado Fulano de Tal, pagamento autorizado.",
                             "hierarchy": "Executivo > Atos Normativos", "totalTermsFound": 1,
                             "termsFound": [{"term": "Fulano de Tal", "matchesFound": 1}]}],
                  "currentPage": 1, "totalPages": 1, "totalItems": 1, "pageSize": 20, "hasPreviousPage": False, "hasNextPage": False})
    if "divulgacandcontas.tse.jus.br" in url:
        if url.endswith("/eleicao/ordinarias"):
            return R([{"id": 2045202024, "ano": 2024, "nomeEleicao": "Eleições Municipais 2024", "tipoAbrangencia": "M"},
                      {"id": 2040602022, "ano": 2022, "nomeEleicao": "Eleição Geral Federal 2022", "tipoAbrangencia": "F"}])
        if "/municipios" in url:
            return R({"municipios": [{"codigo": "66257", "nome": "JUQUITIBA"}]})
        if "/candidatura/listar/2022/SP/2040602022/6/" in url:
            return R({"candidatos": [
                {"id": 250001, "nomeUrna": "FULANO DE TAL", "nomeCompleto": "FULANO DE TAL DA SILVA", "numero": 1234,
                 "partido": {"sigla": "PDT"}, "descricaoTotalizacao": "Eleito por QP", "fotoUrl": "https://divulgacandcontas.tse.jus.br/foto.jpg",
                 "cpf": "NAO-PODE-SAIR", "descricaoCorRaca": "NAO-PODE-SAIR"},
                {"id": 250002, "nomeUrna": "BELTRANO", "nomeCompleto": "BELTRANO SOUZA", "numero": 5555,
                 "partido": {"sigla": "PL"}, "descricaoTotalizacao": "Não eleito"}]})
        if "/candidatura/listar/2024/66257/2045202024/13/" in url:
            return R({"candidatos": [{"id": 9001, "nomeUrna": "ADELIA DO JUSTINO", "nomeCompleto": "ADELIA", "numero": 10978,
                                      "partido": {"sigla": "REPUBLICANOS"}, "descricaoTotalizacao": "Eleito"}]})
        return R({"candidatos": []})
    if "dadosabertos.camara.leg.br/api/v2/proposicoes/2641232" in url:
        return R({"dados": {"id": 2641232, "siglaTipo": "PL", "numero": 4544, "ano": 2026, "ementa": "Institui a Política Nacional de Autonomia Digital da Pessoa Idosa.",
                            "statusProposicao": {"descricaoTramitacao": "Apresentação de Proposição", "siglaOrgao": "MESA"},
                            "urlInteiroTeor": "https://www.camara.leg.br/inteiro-teor/2641232"}})
    if "dadosabertos.camara.leg.br/api/v2/proposicoes" in url:
        return R({"dados": [{"id": 2641232, "siglaTipo": "PL", "numero": 4544, "ano": 2026, "dataApresentacao": "2026-07-17T20:02",
                             "ementa": "Institui a Política Nacional de Autonomia Digital da Pessoa Idosa."}]})
    if "camara.leg.br/inteiro-teor" in url:
        return R(None, texto="Art. 1º Fica instituída a Política Nacional de Autonomia Digital da Pessoa Idosa. " * 20)
    if "legis.senado.leg.br/dadosabertos/materia/pesquisa" in url:
        return R({"PesquisaBasicaMateria": {"Materias": {"Materia": {"Codigo": "173057", "DescricaoIdentificacao": "PL 1159/2026",
                  "Ementa": "Altera o Estatuto da Pessoa Idosa.", "Autor": "Senador X", "Data": "2026-03-13"}}}})
    if "api.transferegov.gestao.gov.br/transferenciasespeciais/plano_acao_especial" in url:
        return R([{"codigo_plano_acao": "0903-1", "numero_emenda_parlamentar_plano_acao": "202637150001", "situacao_plano_acao": "CIENTE",
                   "motivo_impedimento_plano_acao": None, "nome_beneficiario_plano_acao": "MUNICIPIO DE JUQUITIBA",
                   "uf_beneficiario_plano_acao": "SP", "valor_custeio_plano_acao": 0, "valor_investimento_plano_acao": 500000}])
    if url.startswith("https://news.google.com/rss/search"):
        rss = ("<rss><channel>"
               "<item><title>Deputado Fulano de Tal é alvo de denúncia de desvio e investigação - Jornal Regional</title><link>https://jr.com/1</link>"
               "<pubDate>" + datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT") + "</pubDate><source>Jornal Regional</source></item>"
               "<item><title>Fulano de Tal entrega reforma da UBS e garante investimento - Folha da Cidade</title><link>https://fc.com/2</link>"
               "<pubDate>" + datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT") + "</pubDate><source>Folha da Cidade</source></item>"
               "</channel></rss>")
        return R(None, texto=rss)
    if "servicodados.ibge" in url:
        return R([{"id": 3525508, "nome": "Juquitiba"}, {"id": 3550308, "nome": "São Paulo"}])
    raise AssertionError("URL inesperada: " + url)


requests.get = falso_get


def falso_request(metodo, url, json=None, headers=None, timeout=None):
    if url.endswith("/checkout/preferences"):
        return type("Resp", (), {"status_code": 201, "content": b"1", "text": "",
                                 "json": lambda self: {"id": "pref-1", "init_point": "https://mp.teste/checkout/pref-1"}})()
    raise AssertionError("Mercado Pago: chamada inesperada " + url)


requests.request = falso_request

from app import create_app  # noqa: E402

app = create_app()
c = app.test_client()
ok = lambda cond, msg: print(("OK   " if cond else "FALHA ") + msg) or (cond or sys.exit(1))  # noqa: E731


def chamar(metodo, url, token=None, **kw):
    h = {"Authorization": "Bearer " + token} if token else {}
    r = getattr(c, metodo)(url, headers=h, **kw)
    return r.status_code, (r.get_json(silent=True) if r.is_json else r)


s, d = chamar("post", "/api/auth/registro", json={"nome": "Ana Chefe", "email": "admin@teste.br", "senha": "12345678", "gabinete": "Gab. Fulano"})
ok(s == 200 and d.get("token"), "cadastro devolve token (verificação desligada no teste)")
T = d["token"]
s, d = chamar("get", "/api/conta", T)
ok(d["plano"]["codigo"] == "free" and d["usuario"]["admin"], "conta Free e usuário admin")

s, d = chamar("post", "/api/gabinetes", T, json={"parlamentar": "Fulano de Tal", "nome_parlamentar": "FULANO DE TAL",
               "cargo": "deputado_federal", "casa": "Câmara dos Deputados", "uf": "SP"})
ok(s == 201 and d["esfera"] == "federal", "gabinete federal criado")
G = d["id"]
s, d = chamar("get", "/api/municipios?uf=SP&q=juqui", T)
ok(len(d) == 1 and d[0]["id"] == "3525508", "busca de município no IBGE")
s, d = chamar("put", f"/api/gabinetes/{G}", T, json={"base": [{"id": "3525508", "nome": "Juquitiba", "uf": "SP", "querido_diario": True}]})
ok(d["base"][0]["nome"] == "Juquitiba", "base territorial salva")

s, d = chamar("post", f"/api/gabinetes/{G}/emendas/sincronizar", T)
ok(s == 402, "sincronização automática bloqueada no Free")
s, d = chamar("patch", "/api/admin/contas/1", T, json={"plano": "monitoramento"})
ok(s == 400, "admin NÃO consegue liberar plano pago sem a aprovação oficial")


def definir_plano(cod):
    with app.app_context():
        from extensions import db as _db
        from models import Conta as _C
        c = _db.session.get(_C, 1)
        c.plano, c.pago_ate = cod, date(2099, 12, 31)
        _db.session.commit()


definir_plano("monitoramento")
s, d = chamar("post", f"/api/gabinetes/{G}/emendas/sincronizar", T)
ok(s == 200 and d["novas"] == 1, "emenda federal importada do Portal da Transparência")
s, d = chamar("get", f"/api/gabinetes/{G}/emendas", T)
E = d["emendas"][0]
ok(E["fase"] == "empenhada" and E["valor_empenhado"] == 500000, "fase calculada pelos valores (empenhada)")

PAGO["v"] = "500.000,00"
chamar("put", f"/api/gabinetes/{G}", T, json={"comunicado_automatico": True})
s, d = chamar("post", f"/api/gabinetes/{G}/emendas/sincronizar", T)
ok(d["eventos"] >= 2 and d["comunicados"] == 2, "pagamento detectado + 2 rascunhos automáticos (release e post)")
s, d = chamar("get", f"/api/emendas/{E['id']}", T)
ok(d["fase"] == "paga" and len(d["eventos"]) >= 4, "linha do tempo com empenho e pagamento")

s, d = chamar("post", f"/api/gabinetes/{G}/monitores", T, json={"termos": ['"Fulano de Tal"', "37150001"]})
ok(s == 201, "monitor de diário oficial criado")
s, d = chamar("post", f"/api/monitores/{d['id']}/buscar", T)
ok(d["novos"] == 1, "publicação encontrada no Querido Diário")
s, d = chamar("get", f"/api/gabinetes/{G}/achados?status=todos", T)
ok(d[0]["classificacao"] == "empenho" and d[0]["emenda_id"] == E["id"], "achado classificado como empenho e vinculado à emenda pelo número")

s, d = chamar("post", f"/api/gabinetes/{G}/minutas", T, json={"tipo": "projeto_lei", "demanda": "Criar programa de combate ao analfabetismo funcional na zona rural"})
ok(s == 201 and "Art. 1º" in d["texto"] and d["analise"]["iniciativa"]["risco"], "minuta de PL com análise de iniciativa (demonstração)")
M = d["id"]
r = c.get(f"/api/minutas/{M}/docx", headers={"Authorization": "Bearer " + T})
ok(r.status_code == 200 and r.data[:2] == b"PK", "minuta exportada em .docx")

f = io.BytesIO(("Art. 1º Este Regimento disciplina a Câmara.\nArt. 150. A iniciativa dos projetos de lei cabe a qualquer vereador, "
                "salvo matéria reservada ao Prefeito. " * 20).encode())
r = c.post(f"/api/gabinetes/{G}/regimento", headers={"Authorization": "Bearer " + T},
           data={"arquivo": (f, "regimento.txt")}, content_type="multipart/form-data")
ok(r.status_code == 200 and r.get_json()["regimento_caracteres"] > 200, "regimento interno enviado")

s, d = chamar("post", f"/api/gabinetes/{G}/comunicados", T, json={"formato": "release", "canal": "institucional", "emenda_id": E["id"]})
periodo = s == 409
from services import eleitoral  # noqa: E402
with app.app_context():
    vedado = eleitoral.situacao("federal")["vedado"]
ok(periodo == vedado, f"canal institucional {'bloqueado' if vedado else 'liberado'} conforme o período eleitoral de hoje")
s, d = chamar("post", f"/api/gabinetes/{G}/comunicados", T, json={"formato": "discurso", "canal": "pessoal", "emenda_id": E["id"]})
ok(s == 201 and d["texto"], "discurso gerado no canal pessoal")
with app.app_context():
    ok(eleitoral.situacao("municipal", date(2026, 9, 1))["vedado"] is False, "eleição geral não trava a esfera municipal")
    ok(eleitoral.situacao("estadual", date(2026, 7, 4))["vedado"] is True, "vedação começa 3 meses antes (04/07/2026)")
    ok(eleitoral.situacao("estadual", date(2026, 7, 3))["vedado"] is False, "e não antes disso")

s, d = chamar("get", f"/api/gabinetes/{G}/painel", T)
ok(d["totais"]["pago"] == 500000 and d["achados_novos"] == 0 and d["rascunhos"] >= 3, "painel consolida totais, achados e rascunhos")
# ---------------------------------------------------------------- contratação com aprovação pelo e-mail oficial
chamar("patch", "/api/admin/contas/1", T, json={"plano": "free", "pago_ate": ""})
base_pedido = {"plano": "legislativo", "periodicidade": "mensal", "responsavel_nome": "Ana Chefe", "responsavel_cargo": "Chefe de gabinete",
               "responsavel_email": "ana@gmail.com", "responsavel_telefone": "11 99999-0000"}
s, d = chamar("post", "/api/conta/pedidos", T, json={**base_pedido, "forma": "faturamento", "email_oficial": "ana@gmail.com"})
ok(s == 400 and d["codigo"] == "email_nao_oficial", "e-mail fora de .leg.br/.gov.br é recusado como e-mail oficial")
fat = {**base_pedido, "forma": "faturamento", "email_oficial": "gab.fulano@camara.leg.br", "orgao_nome": "Câmara dos Deputados",
       "orgao_cnpj": "00.530.352/0001-59", "orgao_endereco": "Praça dos Três Poderes", "orgao_municipio": "Brasília", "orgao_uf": "DF",
       "modalidade_contratacao": "dispensa", "financeiro_nome": "Setor financeiro", "financeiro_email": "financeiro@camara.leg.br"}
s, d = chamar("post", "/api/conta/pedidos", T, json={k: v for k, v in fat.items() if k != "financeiro_email"})
ok(s == 400, "faturamento exige contato do setor financeiro")
s, d = chamar("post", "/api/conta/pedidos", T, json=fat)
ok(s == 201 and d["status"] == "aguardando_aprovacao" and d["valor"] == 4900 and "link_aprovacao_teste" in d, "pedido de faturamento criado, aguardando aprovação")
P1, tok1 = d["id"], d["link_aprovacao_teste"].split("t=")[1]
s, d = chamar("get", "/api/conta", T)
ok(d["plano"]["codigo"] == "free", "plano NÃO é liberado antes da aprovação oficial")
s, d = chamar("post", "/api/conta/pedidos", T, json=fat)
ok(s == 409, "não permite dois pedidos abertos")
s, d = chamar("get", "/api/public/aprovacao?t=" + tok1)
ok(s == 200 and d["orgao_nome"] == "Câmara dos Deputados" and "mp_link" not in d, "página pública de aprovação mostra o resumo")
s, d = chamar("post", "/api/public/aprovacao", json={"t": tok1, "decisao": "aprovar", "nome": "x"})
ok(s == 400, "aprovação exige nome completo")
s, d = chamar("post", "/api/public/aprovacao", json={"t": tok1, "decisao": "aprovar", "nome": "Fulano de Tal Deputado"})
ok(s == 200 and d["status"] == "liberado", "aprovação pelo e-mail oficial libera o faturamento")
s, d = chamar("get", "/api/conta", T)
ok(d["plano"]["codigo"] == "legislativo" and d["plano"]["pago_ate"], "plano Legislativo ativo com validade")
s, d = chamar("post", "/api/public/aprovacao", json={"t": tok1, "decisao": "aprovar", "nome": "Fulano de Tal Deputado"})
ok(s == 404, "link de aprovação é de uso único")
s, d = chamar("patch", f"/api/admin/pedidos/{P1}", T, json={"empenho": "2026NE000123", "nota_fiscal": "NFS-e 457", "pago": True})
ok(d["empenho"] == "2026NE000123" and d["pago_em"], "admin registra empenho, nota fiscal e pagamento")

s, d = chamar("post", "/api/conta/pedidos", T, json={**base_pedido, "plano": "monitoramento", "forma": "mercado_pago", "periodicidade": "anual",
                                                      "email_oficial": "dep.fulano@camara.leg.br"})
ok(s == 201 and d["mp_link"].startswith("https://mp.teste") and d["valor"] == 99000, "pedido Mercado Pago anual (10 meses) com link de checkout")
P2, tok2 = d["id"], d["link_aprovacao_teste"].split("t=")[1]
s, d = chamar("post", f"/api/teste/pedidos/{P2}/simular-pagamento", T)
ok(d["pago_em"] and d["status"] == "aguardando_aprovacao", "pago, mas ainda NÃO liberado sem a aprovação oficial")
s, d = chamar("get", "/api/conta", T)
ok(d["plano"]["codigo"] == "legislativo", "plano segue o anterior enquanto não aprovado")
s, d = chamar("post", "/api/public/aprovacao", json={"t": tok2, "decisao": "aprovar", "nome": "Fulano de Tal Deputado"})
ok(d["status"] == "liberado", "aprovado + pago = liberado")
s, d = chamar("get", "/api/conta", T)
ok(d["plano"]["codigo"] == "monitoramento", "plano Monitoramento liberado")

s, d = chamar("post", "/api/conta/pedidos", T, json={**fat, "plano": "essencial"})
tok3 = d["link_aprovacao_teste"].split("t=")[1]
s, d = chamar("post", "/api/public/aprovacao", json={"t": tok3, "decisao": "recusar"})
ok(d["status"] == "recusado", "e-mail oficial pode recusar o pedido")
s, d = chamar("get", "/api/conta", T)
ok(d["plano"]["codigo"] == "monitoramento", "recusa não altera o plano")

# ---------------------------------------------------------------- Estado de São Paulo
s, d = chamar("get", f"/api/gabinetes/{G}/repasses-sp?ano=2026&mes=7", T)
ok(s == 200 and d["total"] == 250000 and d["municipios"][0]["linhas"][0]["fonte"].startswith("02"), "TCE-SP: só a fonte estadual entra no repasse")
s, d = chamar("post", f"/api/gabinetes/{G}/monitores", T, json={"fonte": "doe_sp", "nome": "DOE-SP", "termos": ['"Fulano de Tal"']})
ok(s == 201 and d["fonte"] == "doe_sp", "monitor do Diário Oficial do Estado criado")
s, d = chamar("post", f"/api/monitores/{d['id']}/buscar", T)
ok(d["novos"] == 1, "publicação encontrada no DOE-SP")
s, d = chamar("get", f"/api/gabinetes/{G}/achados?status=todos", T)
doe = [a for a in d if a["territorio"] == "Estado de São Paulo"][0]
ok(doe["classificacao"] == "pagamento" and doe["emenda_id"] == E["id"] and doe["url"] == "https://doe.sp.gov.br/executivo/secretaria/despacho-n-843",
   "achado do DOE-SP classificado, vinculado à emenda e com link da publicação")
s, d = chamar("get", "/api/fontes", T)
ok(d["doe_sp"] and d["tce_sp"] and d["teste"], "painel de fontes mostra DOE-SP e TCE-SP ativos")
# ---------------------------------------------------------------- TSE
s, d = chamar("get", "/api/tse/eleitos?cargo=deputado_federal&uf=SP&q=fulano", T)
ok(s == 200 and len(d) == 1 and d[0]["partido"] == "PDT" and d[0]["numero"] == "1234" and d[0]["casa"] == "Câmara dos Deputados",
   "TSE: só eleitos, com nome, partido, número e Casa")
ok("cpf" not in str(d) and "NAO-PODE-SAIR" not in str(d), "TSE: CPF e cor/raça não saem do servidor (minimização)")
s, d = chamar("get", "/api/tse/eleitos?cargo=vereador&uf=SP&municipio=Juquitiba", T)
ok(len(d) == 1 and d[0]["nome_urna"] == "ADELIA DO JUSTINO", "TSE: vereador pelo código TSE do município (≠ IBGE)")
s, d = chamar("put", f"/api/gabinetes/{G}", T, json={"partido": "PDT", "numero_urna": "1234", "foto_url": "https://divulgacandcontas.tse.jus.br/foto.jpg", "tse_ano": 2022})
ok(d["partido"] == "PDT" and d["tse_ano"] == 2022, "gabinete preenchido com dados do TSE")

# ---------------------------------------------------------------- Copiloto Legislativo
s, d = chamar("get", f"/api/gabinetes/{G}/legislativo/pesquisa?q=idoso&fonte=camara", T)
ok(s == 200 and d[0]["identificacao"] == "PL 4544/2026", "pesquisa na Câmara dos Deputados")
s, d = chamar("get", f"/api/gabinetes/{G}/legislativo/pesquisa?q=idoso&fonte=senado", T)
ok(d[0]["identificacao"] == "PL 1159/2026", "pesquisa no Senado (item único vira lista)")
s, d = chamar("post", f"/api/gabinetes/{G}/analises", T, json={"fonte": "camara", "id_externo": "2641232"})
ok(s == 201 and d["identificacao"] == "PL 4544/2026" and d["resultado"]["texto_integral"] and d["resultado"]["resumo"],
   "análise com texto integral baixado da Câmara")
ok(isinstance(d["comparacoes"], list) and d["comparacoes"], "análise traz leis parecidas de outros entes")
s, d = chamar("get", f"/api/gabinetes/{G}/analises", T)
ok(len(d) == 1, "histórico de análises")

# ---------------------------------------------------------------- Gestor de emendas
s, d = chamar("put", f"/api/emendas/{E['id']}", T, json={"publicar": True})
s, d = chamar("put", f"/api/gabinetes/{G}", T, json={"pagina_publica": True})
ok(d["pagina_publica"] and d["slug_publico"] == "fulano-de-tal", "página pública ativada com endereço amigável")
s, d = chamar("get", "/api/public/prestacao/fulano-de-tal")
ok(s == 200 and d["total_pago"] == 500000 and d["municipios"][0]["emendas"][0]["fase"] == "paga", "prestação de contas pública (sem login)")
s, d = chamar("post", f"/api/gabinetes/{G}/emendas", T, json={"numero": "RISCO1", "objeto": "Creche", "ano": date.today().year - 1,
                                                             "valor_indicado": "100000", "fase": "aprovada"})
ok(d["risco"] == "alto" and any("sem empenho" in r["motivo"] for r in d["riscos"]), "risco alto: LOA anterior sem empenho")
s, d = chamar("get", f"/api/gabinetes/{G}/painel", T)
ok(any(r["emenda"] == "RISCO1" for r in d["riscos"]), "painel lista as emendas em risco")

# ---------------------------------------------------------------- Clipping (Fase B)
s, d = chamar("post", f"/api/gabinetes/{G}/temas", T, json={})
ok(s == 201 and d["tipo"] == "mandato", "tema do próprio mandato criado")
TID = d["id"]
with app.app_context():
    app.config["CRISE_LIMIAR"] = 1
s, d = chamar("post", f"/api/temas/{TID}/coletar", T)
ok(d["novas"] >= 2, "notícias coletadas do Google Notícias (+ diários)")
s, d = chamar("get", f"/api/gabinetes/{G}/mencoes", T)
neg = [m for m in d if m["veiculo"] == "Jornal Regional"][0]
pos = [m for m in d if m["veiculo"] == "Folha da Cidade"][0]
ok(neg["sentimento"] == "negativo" and neg["crise"] and pos["sentimento"] == "positivo", "sentimento e crise classificados")
ok(neg["titulo"].startswith("Deputado Fulano") and not neg["titulo"].endswith("Jornal Regional"), "título limpo, veículo separado")
with app.app_context():
    from models import AlertaEnviado
    ok(AlertaEnviado.query.count() >= 1, "alerta de crise registrado (e-mail; WhatsApp desligado no teste)")
s, d = chamar("post", f"/api/temas/{TID}/coletar", T)
ok(d["novas"] == 0, "coleta não duplica menções")
s, d = chamar("get", f"/api/gabinetes/{G}/sentimento", T)
ok(len(d["dias"]) == 14 and d["crises"] >= 1, "painel de sentimento de 14 dias")
s, d = chamar("post", f"/api/gabinetes/{G}/resumos", T)
ok(s == 201 and "menções" in d["texto"] and d["numeros"]["total"] >= 2, "pauta do dia gerada (texto)")

# ---------------------------------------------------------------- Admin
s, d = chamar("get", "/api/admin/crm", T)
ok(d["mrr"] == 9900 and d["contas"][0]["etapa"] == "assinante", "admin: CRM com MRR e etapa")
s, d = chamar("get", "/api/admin/funil", T)
ok(d["etapas"][0]["contas"] == 1 and d["etapas"][-1]["contas"] == 1, "admin: funil até a liberação")
s, d = chamar("get", "/api/admin/receitas", T)
ok(d["recebido"] > 0, "admin: receitas")
s, d = chamar("get", "/api/admin/planos/margem", T)
ok(any(p["plano"] == "monitoramento" and p["contas"] == 1 for p in d["planos"]), "admin: planos e margem")
s, d = chamar("post", "/api/admin/prospeccao/importar", T, json={"cargo": "deputado_federal", "uf": "SP"})
ok(d["novos"] == 1, "admin: prospecção importa eleitos do TSE")
chamar("post", "/api/logs/navegador", json={"mensagem": "TypeError: x is undefined", "tela": "#/emendas"})
s, d = chamar("get", "/api/admin/logs", T)
ok(any(l["origem"] == "navegador" for l in d["logs"]), "admin: logs recebem erros do navegador")
s, d = chamar("get", "/api/admin/armazenamento", T)
ok(any(t["tabela"] == "Menções (clipping)" and t["registros"] >= 2 for t in d["tabelas"]), "admin: armazenamento")
r = c.get("/api/admin/notas.csv", headers={"Authorization": "Bearer " + T})
ok(r.status_code == 200 and b"2026NE000123" in r.data, "admin: exportação das notas fiscais")

with app.app_context():
    from jobs.rotina_diaria import rodar  # noqa: F401 — importa sem erro
print("\nTodos os testes passaram.")
