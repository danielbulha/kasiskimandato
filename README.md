# Kasiski Mandato — copiloto do mandato parlamentar

Segunda solução da plataforma Kasiski (a primeira é o Kasiski Licitações, repositório `danielbulha/kasiski`).
Mesma arquitetura e mesma identidade visual: Flask + SQLAlchemy + JWT, frontend HTML/CSS/JS puro sem build,
Manual da Marca v1.0 (Inter, azul `#071D2D`, ciano `#11B8C8` só como destaque, carimbos de status).
Backend e banco **próprios** no Render — isolados do Kasiski Licitações.

- App: `https://mandato.kasiski.com.br` (pasta `frontend/`, site separado no Netlify)
- Página pública: `https://kasiski.com.br/mandato/` (gerada pelo `site/` do repositório do Kasiski Licitações)
- API: serviço `mandato-api` no Render (pasta `backend/`)

## Pacotes (backend/planos.py — preços em rascunho)

| Pacote | Preço/mês | Inclui |
|---|---|---|
| Free | — | Emendas (manual), minutas e comunicação com limites baixos |
| Essencial | R$ 2.000 | Rastreador de emendas, diários oficiais, repasses SP, minutas, central de comunicação |
| Legislativo | R$ 4.900 | + Copiloto Legislativo (pesquisa e análise de proposições) e Gestor de Emendas (riscos + página pública) |
| Monitoramento | R$ 9.900 | + Clipping com sentimento, alerta de crise no WhatsApp e pauta do dia em texto e áudio |
| Completo | R$ 15.900 | + Instagram, TikTok e X via fornecedor de social listening (custo do fornecedor à parte) |
| Institucional | sob consulta | Vários gabinetes (bancadas, lideranças, partidos, prefeituras) |

## Módulos e fontes

| Módulo | O que entrega | Fontes (conferidas em chamada real quando indicado ✓) |
|---|---|---|
| Cadastro pelo TSE | Nome civil, nome de urna, partido, número, cargo, Casa, UF e município dos eleitos | Portal de Dados Abertos do TSE ✓ (`consulta_cand_{ano}.zip`, importado uma vez por eleição; sem CPF, e-mail ou cor/raça) |
| Emendas | Ciclo da verba com linha do tempo e fonte | Portal da Transparência, Transferegov.br especiais ✓, TCE-SP, DOE-SP ✓, Querido Diário |
| Gestor de Emendas | Risco de perder o recurso (impedimento, prazos, fim de exercício, restos a pagar, plano de ação) e página pública de prestação de contas por município | Regras objetivas, sem IA |
| Copiloto Legislativo | Pesquisa, texto integral, resumo em tópicos, riscos de inconstitucionalidade (para revisão), comparação com leis de outros entes, verificação cruzada | Câmara ✓, Senado ✓, SAPL da Casa, Querido Diário (leis municipais), DOE-SP |
| Minutas | PL, indicação, requerimento, moção; com leis parecidas de outros entes no plano Legislativo | IA + Regimento Interno do gabinete |
| Clipping | Menções com sentimento, índice de 14 dias, crise, pauta do dia (texto e MP3) | Google Notícias RSS ✓, RSS de veículos regionais, diários, social listening |
| Alertas | Crise no WhatsApp (modelo aprovado pela Meta) e por e-mail; resumo diário | WhatsApp Business Cloud API |
| Administração | Clientes, Funil, Receitas, Notas fiscais e pedidos, Planos e margem, Prospecção (eleitos do TSE), Logs de erros (servidor, tarefas e navegador), Armazenamento | — |

**Base do TSE:** importe uma vez por eleição em Administração → Prospecção → Base do TSE (2018, 2022 e 2024; 2026 quando
o resultado sair), ou pelo Shell do Render: `python jobs/importar_tse.py 2018 2022 2024`. O DivulgaCandContas foi descartado:
responde ao navegador, mas devolve 403 para servidores.

Rotinas no Render: `mandato-rotina` (diária, 06h30) e `mandato-clipping` (de hora em hora).

## Regra de liberação dos planos

1. O gabinete faz o pedido on-line e informa o **e-mail oficial** (domínios em `DOMINIOS_OFICIAIS`, padrão `.leg.br,.gov.br`).
2. O sistema envia um link de aprovação de uso único (validade `APROVACAO_DIAS`, padrão 7 dias). Quem aprova digita o nome completo
   e marca a declaração; ficam registrados nome, data/hora e IP. Também é possível recusar.
3. **Faturamento:** a aprovação libera o plano; a fatura vence em `FATURA_DIAS` e o admin registra empenho, NFS-e e pagamento.
   **Mercado Pago:** libera quando houver aprovação E pagamento confirmado pela API do Mercado Pago, em qualquer ordem.
4. O admin pode ajustar manualmente (plano, validade, preço contratado, teste, suspensão, exclusão) em Administração →
   Clientes; cada ajuste fica no histórico da conta com o e-mail de quem fez. Contas de quem está em `ADMIN_EMAILS`
   têm acesso total (Institucional), sem limites.

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
`cd backend && python testes/teste_ponta_a_ponta.py` (91 verificações).

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
- **DOE-SP:** o Integrador de APIs do Estado não oferece busca de texto das publicações. O conector usa a mesma busca pública do
  site doe.sp.gov.br (`do-api-web-search.doe.sp.gov.br/v2/advanced-search/publications`), sem token, conferida com chamada real
  em 29/09/2026. Não é documentada: se o site mudar, o monitor mostra o erro e o restante do app segue funcionando.
- **TCE-SP:** a página da API cita os exercícios 2014–2019. Confirme na primeira chamada real se 2025–2026 respondem; se não,
  a tela mostra o aviso do TCE e o controle segue pelo DOE-SP e pelos diários municipais.
- Não há API pública de **execução** das emendas/indicações estaduais de SP; a ALESP publica só as indicações propostas.
- Diários de outros estados e o DOU não entram na busca automática. Municípios fora do Querido Diário aparecem marcados.
- **Redes sociais:** as APIs das próprias redes não permitem varredura (TikTok só para pesquisa acadêmica, Instagram limitado,
  X pago). O plano Completo depende do fornecedor de social listening contratado; o adaptador espera
  `GET {SOCIAL_API_URL}?q=...&since=...` → `{"items":[{"network","text","url","published_at","author","author_verified","engagement"}]}`.
  Se o fornecedor usar outro formato, ajusta-se só `services/clipping.py::social`.
- **Google Notícias RSS:** funciona e foi conferido, mas confira os termos de uso do Google para uso comercial
  (`GOOGLE_NEWS_ATIVO=nao` desliga; os RSS dos veículos regionais seguem funcionando).
- **GDELT** foi testado e descartado (1 consulta a cada 5 s). **LexML** não respondeu no endereço documentado (404).
- **SAPL:** a API das câmaras municipais não foi conferida em chamada real; falha com mensagem clara se a Casa usar outra versão.
- **LGPD:** opinião política é dado sensível. O clipping não guarda nome nem perfil de cidadãos comuns; adversários devem ser
  figuras públicas. A análise de sentimento é agregada.
- **WhatsApp:** exige conta Business verificada e modelo de mensagem aprovado pela Meta; cobrança por conversa.
- **Emendas estaduais e municipais** não têm API padronizada: dependem do cadastro manual + monitor de diários.
- **Preços em `backend/planos.py` são rascunho.** Ajuste lá e em `site/mandato.py` (MANDATO_PLANOS) do repositório do site.
- A base jurídica em `backend/knowledge-base/` orienta a IA; revise antes de produção.
