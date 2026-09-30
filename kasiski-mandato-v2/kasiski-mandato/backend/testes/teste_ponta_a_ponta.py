"""Teste de ponta a ponta com as APIs públicas SIMULADAS (formato conforme a documentação de cada uma).

Uso: cd backend && python testes/teste_ponta_a_ponta.py
Roda em SQLite em memória, modo demonstração (sem chaves de IA) e sem rede.
"""
import io
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.update({"DATABASE_URL": "sqlite://", "ADMIN_EMAILS": "admin@teste.br", "PORTAL_TRANSPARENCIA_KEY": "x",
                   "VERIFICAR_EMAIL": "nao", "AMBIENTE": "teste", "MP_ACCESS_TOKEN": "TEST-123",
                   "DOE_SP_API_URL": "https://doe.teste/api", "DOE_SP_TOKEN": "tok"})

import requests  # noqa: E402

PAGO = {"v": "0,00"}


class R:
    def __init__(self, dados, status=200):
        self._d, self.status_code, self.text = dados, status, ""

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
    if url.startswith("https://doe.teste/api"):
        assert headers.get("Authorization") == "Bearer tok"
        return R({"items": [{"date": date.today().isoformat(), "url": "https://doe.sp.gov.br/x", "section": "Executivo - Atos de Gestão",
                             "excerpt": "Convênio para repasse referente à emenda 37150001 do deputado Fulano de Tal, pagamento autorizado."}]})
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
s, _ = chamar("patch", "/api/admin/contas/1", T, json={"plano": "federal", "pago_ate": "2099-12-31"})
ok(s == 200, "admin libera o plano Federal")
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
base_pedido = {"plano": "estadual", "periodicidade": "mensal", "responsavel_nome": "Ana Chefe", "responsavel_cargo": "Chefe de gabinete",
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
ok(d["plano"]["codigo"] == "estadual" and d["plano"]["pago_ate"], "plano Estadual ativo com validade")
s, d = chamar("post", "/api/public/aprovacao", json={"t": tok1, "decisao": "aprovar", "nome": "Fulano de Tal Deputado"})
ok(s == 404, "link de aprovação é de uso único")
s, d = chamar("patch", f"/api/admin/pedidos/{P1}", T, json={"empenho": "2026NE000123", "nota_fiscal": "NFS-e 457", "pago": True})
ok(d["empenho"] == "2026NE000123" and d["pago_em"], "admin registra empenho, nota fiscal e pagamento")

s, d = chamar("post", "/api/conta/pedidos", T, json={**base_pedido, "plano": "federal", "forma": "mercado_pago", "periodicidade": "anual",
                                                      "email_oficial": "dep.fulano@camara.leg.br"})
ok(s == 201 and d["mp_link"].startswith("https://mp.teste") and d["valor"] == 99000, "pedido Mercado Pago anual (10 meses) com link de checkout")
P2, tok2 = d["id"], d["link_aprovacao_teste"].split("t=")[1]
s, d = chamar("post", f"/api/teste/pedidos/{P2}/simular-pagamento", T)
ok(d["pago_em"] and d["status"] == "aguardando_aprovacao", "pago, mas ainda NÃO liberado sem a aprovação oficial")
s, d = chamar("get", "/api/conta", T)
ok(d["plano"]["codigo"] == "estadual", "plano segue o anterior enquanto não aprovado")
s, d = chamar("post", "/api/public/aprovacao", json={"t": tok2, "decisao": "aprovar", "nome": "Fulano de Tal Deputado"})
ok(d["status"] == "liberado", "aprovado + pago = liberado")
s, d = chamar("get", "/api/conta", T)
ok(d["plano"]["codigo"] == "federal", "plano Federal liberado")

s, d = chamar("post", "/api/conta/pedidos", T, json={**fat, "plano": "municipal"})
tok3 = d["link_aprovacao_teste"].split("t=")[1]
s, d = chamar("post", "/api/public/aprovacao", json={"t": tok3, "decisao": "recusar"})
ok(d["status"] == "recusado", "e-mail oficial pode recusar o pedido")
s, d = chamar("get", "/api/conta", T)
ok(d["plano"]["codigo"] == "federal", "recusa não altera o plano")

# ---------------------------------------------------------------- Estado de São Paulo
s, d = chamar("get", f"/api/gabinetes/{G}/repasses-sp?ano=2026&mes=7", T)
ok(s == 200 and d["total"] == 250000 and d["municipios"][0]["linhas"][0]["fonte"].startswith("02"), "TCE-SP: só a fonte estadual entra no repasse")
s, d = chamar("post", f"/api/gabinetes/{G}/monitores", T, json={"fonte": "doe_sp", "nome": "DOE-SP", "termos": ['"Fulano de Tal"']})
ok(s == 201 and d["fonte"] == "doe_sp", "monitor do Diário Oficial do Estado criado")
s, d = chamar("post", f"/api/monitores/{d['id']}/buscar", T)
ok(d["novos"] == 1, "publicação encontrada no DOE-SP")
s, d = chamar("get", f"/api/gabinetes/{G}/achados?status=todos", T)
doe = [a for a in d if a["territorio"] == "Estado de São Paulo"][0]
ok(doe["classificacao"] == "pagamento" and doe["emenda_id"] == E["id"], "achado do DOE-SP classificado e vinculado à emenda")
s, d = chamar("get", "/api/fontes", T)
ok(d["doe_sp"] and d["tce_sp"] and d["teste"], "painel de fontes mostra DOE-SP e TCE-SP ativos")
s, d = chamar("get", "/api/admin/resumo", T)
ok(d["mrr"] == 9900 and len(d["pedidos"]) == 3, "admin vê MRR e os pedidos")

with app.app_context():
    from jobs.rotina_diaria import rodar  # noqa: F401 — importa sem erro
print("\nTodos os testes passaram.")
