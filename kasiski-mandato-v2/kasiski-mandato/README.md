# Kasiski Mandato — copiloto do mandato parlamentar

Segunda solução da plataforma Kasiski (a primeira é o Kasiski Licitações, repositório `danielbulha/kasiski`).
Mesma arquitetura e mesma identidade visual: Flask + SQLAlchemy + JWT, frontend HTML/CSS/JS puro sem build,
Manual da Marca v1.0 (Inter, azul `#071D2D`, ciano `#11B8C8` só como destaque, carimbos de status).
Backend e banco **próprios** no Render — isolados do Kasiski Licitações.

- App: `https://mandato.kasiski.com.br` (pasta `frontend/`, site separado no Netlify)
- Página pública: `https://kasiski.com.br/mandato/` (gerada pelo `site/` do repositório do Kasiski Licitações)
- API: serviço `mandato-api` no Render (pasta `backend/`)

## O que faz

| Módulo | O que entrega | Fonte |
|---|---|---|
| Emendas | Ciclo de vida da verba: indicada → aprovada → empenhada → liquidada → paga (e impedida/cancelada), com linha do tempo, prazo e fonte | Federal: Portal da Transparência (automático). Estadual/municipal: cadastro + diários |
| Diários oficiais | Busca diária dos termos do gabinete nos diários municipais da base; classifica (empenho, licitação, contrato, pagamento) e vincula à emenda pelo número | API do Querido Diário |
| Minutas legislativas | PL, indicação, requerimento, moção, justificativa de emenda; análise de iniciativa (Tema 917) e competência; sugestão de financiamento; .docx | IA + LC 95 + Regimento Interno enviado pelo gabinete |
| Central de comunicação | Release, discurso, post, roteiro e prestação de contas; rascunhos automáticos quando a verba é empenhada/paga | IA com verificação cruzada; trava eleitoral (Lei 9.504/97, art. 73, VI, b, §3º) |
| Estado de São Paulo | Repasses estaduais por município da base (receitas na fonte 02 — transferências e convênios estaduais) e monitor do Diário Oficial do Estado | API pública do TCE-SP; API do DOE-SP via Integrador de APIs (credencial) |
| Contratação | Pedido on-line por Mercado Pago (cartão, Pix, boleto) ou faturamento para o Poder Público (órgão, CNPJ, modalidade, responsável, financeiro) | Liberação SÓ após aprovação pelo e-mail oficial do gabinete (.leg.br/.gov.br) |
| Administração | Contas, pedidos (aprovação, IP, empenho, NFS-e, pagamento), MRR, custo de IA e margem por conta | — |

## Regra de liberação dos planos

1. O gabinete faz o pedido on-line e informa o **e-mail oficial** (domínios em `DOMINIOS_OFICIAIS`, padrão `.leg.br,.gov.br`).
2. O sistema envia um link de aprovação de uso único (validade `APROVACAO_DIAS`, padrão 7 dias). Quem aprova digita o nome completo
   e marca a declaração; ficam registrados nome, data/hora e IP. Também é possível recusar.
3. **Faturamento:** a aprovação libera o plano; a fatura vence em `FATURA_DIAS` e o admin registra empenho, NFS-e e pagamento.
   **Mercado Pago:** libera quando houver aprovação E pagamento confirmado pela API do Mercado Pago, em qualquer ordem.
4. Não existe liberação manual pelo admin — a trilha de aprovação oficial é sempre exigida.

## Versão de teste

`render-teste.yaml` cria `mandato-api-teste` + banco próprio (planos free do Render). No Netlify, crie um segundo site com o
mesmo `frontend/` e o domínio `teste-mandato.kasiski.com.br` — o `config.js` reconhece o endereço e aponta para a API de teste.
Com `AMBIENTE=teste`: faixa "Versão de teste" em todas as telas, o link de aprovação aparece na própria tela do pedido
(dispensa e-mail real), botão "Simular pagamento aprovado" e Mercado Pago com credencial `TEST-...`.
`TESTE_QUALQUER_EMAIL=sim` aceita qualquer e-mail como oficial, só para demonstração.

## Rodando localmente

```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env   # coloque seu e-mail em ADMIN_EMAILS
python app.py                                             # http://127.0.0.1:5001
# outro terminal
cd frontend && python -m http.server 8090                 # http://localhost:8090
```
Sem chaves de IA, roda em modo demonstração (como o Kasiski). Teste de ponta a ponta, sem rede:
`cd backend && python testes/teste_ponta_a_ponta.py` (47 verificações).

## Deploy

1. **Render:** New → Blueprint → este repositório (o `render.yaml` cria `mandato-api`, o cron `mandato-rotina` e o banco `mandato-db`).
   Preencha `ADMIN_EMAILS`, as chaves de IA, `PORTAL_TRANSPARENCIA_KEY` (a mesma do Kasiski) e `RESEND_API_KEY`.
2. **Netlify:** novo site com *publish directory* `frontend`, sem build. Em Domain management, adicione `mandato.kasiski.com.br`
   e crie o CNAME no DNS de kasiski.com.br apontando para o endereço `.netlify.app` do site novo.
3. Em `frontend/js/config.js`, troque `API_URL` pela URL que o Render gerar para `mandato-api`.
   Se a URL não terminar em `.onrender.com`, ajuste o `connect-src` do `frontend/_headers`.

## Limitações conhecidas (ler antes de vender)

- **Nenhuma integração fez chamada real** no ambiente onde foi escrita (sem rede para essas APIs). Os formatos seguem a
  documentação oficial; o primeiro teste real pode exigir ajuste de nome de campo — mesma situação do Kasiski no início.
- **Transferegov (transferências especiais) está desligado** (`TRANSFEREGOV_ATIVO=nao`): os nomes de campo do plano de ação
  não foram confirmados. Ligue depois de conferir uma resposta real.
- **DOE-SP fica desligado até o credenciamento** no Integrador de APIs do Estado (integrador.sp.gov.br, login gov.br). Caminho e
  nomes de parâmetro estão em variáveis `DOE_SP_*` para ajustar à documentação que vier com a credencial.
- **TCE-SP:** a página da API cita os exercícios 2014–2019. Confirme na primeira chamada real se 2025–2026 respondem; se não,
  a tela mostra o aviso do TCE e o controle segue pelo DOE-SP e pelos diários municipais.
- Não há API pública de **execução** das emendas/indicações estaduais de SP; a ALESP publica só as indicações propostas.
- Diários de outros estados e o DOU não entram na busca automática. Municípios fora do Querido Diário aparecem marcados.
- **Emendas estaduais e municipais** não têm API padronizada: dependem do cadastro manual + monitor de diários.
- **Preços em `backend/planos.py` são rascunho.** Ajuste lá e em `site/mandato.py` (MANDATO_PLANOS) do repositório do site.
- A base jurídica em `backend/knowledge-base/` orienta a IA; revise antes de produção.
