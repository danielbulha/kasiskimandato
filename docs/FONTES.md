# Registro de fontes e contratos — 02/10/2026

## Transferegov

Aviso oficial de migração: https://www.gov.br/transferegov/pt-br/ferramentas-gestao/dados-abertos

Catálogo: https://api-publica.transferegov.gestao.gov.br/

Documentação Especiais: https://api-publica.transferegov.gestao.gov.br/especiais/docs

OpenAPI obtido: https://api-publica.transferegov.gestao.gov.br/especiais/openapi.json

Contrato utilizado: `GET /especiais/planos-acao-especiais`, filtros `id_plano_acao`, `nome_parlamentar_emenda_plano_acao`, `ano_emenda_parlamentar_plano_acao`; paginação `pagina` e `tamanho_da_pagina` (máximo documentado 200). Envelope `data`, `total_pages`, `total_items`, `page_number`, `page_size`. Campos de monitor: `id_plano_acao`, `situacao_plano_acao`, `numero_emenda_parlamentar_plano_acao`. Consulta real de uma linha confirmou o envelope e o plano ID 3221. Dados bancários da resposta não são armazenados pelo monitor nem incluídos no pacote.

CSV: https://api-publica.transferegov.gestao.gov.br/downloads

Índice usado pela página oficial: https://api-publica.transferegov.gestao.gov.br/downloads/dadosgov/?restype=container&comp=list

Arquivos confirmados no índice:

- https://api-publica.transferegov.gestao.gov.br/downloads/dadosgov/siconv_convenio.zip — baixado; 18.428.089 bytes no momento da checagem; membro `siconv_convenio.csv`, 70.760.841 bytes. UTF-8, delimitador `;`. Cabeçalho arquivado em `convenios-cabecalho.txt`. Implementado para status, não para atribuir valores financeiros a pagamentos ao beneficiário final.
- https://api-publica.transferegov.gestao.gov.br/downloads/dadosgov/siconv_proposta.zip — mapeado no catálogo; parser não implementado.
- https://api-publica.transferegov.gestao.gov.br/downloads/dadosgov/siconv_emenda.zip — mapeado no catálogo; parser não implementado.

Não foi assumida a existência de endpoints REST genéricos `/propostas`, `/convenios` ou `/emendas` no Transferegov. O conector de Especiais usa URL fixa verificada; a variável antiga `TRANSFEREGOV_ESPECIAIS_URL` permanece por compatibilidade, mas não altera esse novo conector.

## Assembleia Legislativa de São Paulo

https://www.al.sp.gov.br/dados-abertos/ — consultado. Catálogo lista conjuntos XML e anuncia futura mudança para CKAN. A documentação de andamentos lista arquivo XML/ZIP, não sustenta uma API REST genérica de emendas e execução financeira.

https://www.al.sp.gov.br/repositorioDados/docs/processo_legislativo/documento_andamentos.pdf — referência do formato de andamentos; não foi usada como endpoint de emendas.

Não foi validado contrato automático de emendas impositivas ALESP ou pagamentos estaduais. Nenhum scraper novo dessas fontes foi implementado. Não apresentar monitor de Especiais federais como cobertura estadual.

## Competência legislativa

https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm — referências para a triagem: arts. 22 (competência privativa da União e hipótese de delegação), 24 (concorrente), 30 (municipal) e 61, §1º (iniciativa). Os resumos no código são paráfrases, não transcrições certificadas. Regras locais, jurisprudência, iniciativa e validade da norma exigem análise humana. Técnica legislativa formal permanece orientada por LC 95/1998 no prompt legado; considerandos não são impostos a todos os projetos.

## WhatsApp

https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages — obtido diretamente via HTTPS. A busca web retornou 429, mas a página oficial foi lida pelo download. Referência confirmou `/{Version}/{Phone-Number-ID}/messages`, `messaging_product`, `recipient_type`, `to`, `type=template`, nome, idioma e componentes do template.

https://business.whatsapp.com/policy — consultado; redireciona ao domínio oficial https://whatsappbusiness.com/policy/. Política indica opt-in, respeito à revogação e uso de template aprovado para iniciar conversa. A elegibilidade e a versão da conta do usuário não foram verificadas.

O envio tem contrato implementado e testes com mocks, não homologação real com a Meta. Sem webhook, não há confirmação de entrega/leitura. Nenhuma chamada de envio foi feita nesta tarefa.
