# Testes executados em 02/10/2026

## test_piloto.py
test_competencia_privativa_bloqueada (__main__.Piloto.test_competencia_privativa_bloqueada) ... ok
test_convenio_proposta_divergente (__main__.Piloto.test_convenio_proposta_divergente) ... ok
test_convenio_transicao_preserva_fase (__main__.Piloto.test_convenio_transicao_preserva_fase) ... ok
test_csv_convenio_utf8_e_selecao (__main__.Piloto.test_csv_convenio_utf8_e_selecao) ... ok
test_csv_duplicado (__main__.Piloto.test_csv_duplicado) ... ok
test_csv_schema_invalido (__main__.Piloto.test_csv_schema_invalido) ... ok
test_demo_nao_aprovavel (__main__.Piloto.test_demo_nao_aprovavel) ... ok
test_erro_http (__main__.Piloto.test_erro_http) ... ok
test_esquema_invalido_nao_lista_vazia (__main__.Piloto.test_esquema_invalido_nao_lista_vazia) ... ok
test_excluir_emenda_com_fila (__main__.Piloto.test_excluir_emenda_com_fila) ... ok
test_excluir_gabinete_com_fontes (__main__.Piloto.test_excluir_gabinete_com_fontes) ... ok
test_falha_preserva_snapshot (__main__.Piloto.test_falha_preserva_snapshot) ... ok
test_falta_base_nao_aprovada (__main__.Piloto.test_falta_base_nao_aprovada) ... ok
test_fonte_nova_invalida_revisao (__main__.Piloto.test_fonte_nova_invalida_revisao) ... ok
test_fonte_rejeita_origem_nao_oficial (__main__.Piloto.test_fonte_rejeita_origem_nao_oficial) ... ok
test_fontes_isoladas_e_jurisdicao (__main__.Piloto.test_fontes_isoladas_e_jurisdicao) ... ok
test_formulario_quatro_campos (__main__.Piloto.test_formulario_quatro_campos) ... ok
test_http_bloqueia_antes_ia (__main__.Piloto.test_http_bloqueia_antes_ia) ... ok
test_identidade_divergente (__main__.Piloto.test_identidade_divergente) ... ok
test_indicacao_nao_confundida_com_pl (__main__.Piloto.test_indicacao_nao_confundida_com_pl) ... ok
test_isolamento_contas (__main__.Piloto.test_isolamento_contas) ... ok
test_mudanca_duplicacao_e_retorno (__main__.Piloto.test_mudanca_duplicacao_e_retorno) ... ok
test_opt_in_boolean_estrito (__main__.Piloto.test_opt_in_boolean_estrito) ... ok
test_paginacao_contrato (__main__.Piloto.test_paginacao_contrato) ... ok
test_primeira_consulta_sem_alerta (__main__.Piloto.test_primeira_consulta_sem_alerta) ... ok
test_revisao_e_invalidacao (__main__.Piloto.test_revisao_e_invalidacao) ... ok
test_revisao_hash_obsoleto (__main__.Piloto.test_revisao_hash_obsoleto) ... ok
test_revisao_isolada_por_conta (__main__.Piloto.test_revisao_isolada_por_conta) ... ok
test_revogacao_cancela_fila (__main__.Piloto.test_revogacao_cancela_fila) ... ok
test_sem_consentimento_sem_fila (__main__.Piloto.test_sem_consentimento_sem_fila) ... ok
test_vinculo_exige_numero_oficial (__main__.Piloto.test_vinculo_exige_numero_oficial) ... ok
test_wa_aceito_nao_entregue (__main__.Piloto.test_wa_aceito_nao_entregue) ... ok
test_wa_desligado_nao_chama_rede (__main__.Piloto.test_wa_desligado_nao_chama_rede) ... ok
test_wa_timeout_nao_reenvia (__main__.Piloto.test_wa_timeout_nao_reenvia) ... ok
Ran 34 tests in 0.934s
OK

## teste_ponta_a_ponta.py
OK   cadastro devolve token (verificação desligada no teste)
OK   cliente começa no Free
OK   conta do admin tem acesso total (Institucional)
OK   gabinete federal criado
OK   busca de município no IBGE
OK   base territorial salva
OK   sincronização automática bloqueada no Free
OK   cliente comum não acessa a administração
OK   admin muda plano, validade e preço contratado
OK   ajuste do admin fica no histórico da conta
OK   emenda federal importada do Portal da Transparência
OK   fase calculada pelos valores (empenhada)
OK   pagamento detectado + 2 rascunhos automáticos (release e post)
OK   linha do tempo com empenho e pagamento
OK   monitor de diário oficial criado
OK   publicação encontrada no Querido Diário
OK   achado classificado como empenho e vinculado à emenda pelo número
OK   minuta de PL com análise de iniciativa (demonstração)
OK   minuta exportada em .docx
OK   regimento interno enviado
OK   canal institucional bloqueado conforme o período eleitoral de hoje
OK   discurso gerado no canal pessoal
OK   eleição geral não trava a esfera municipal
OK   vedação começa 3 meses antes (04/07/2026)
OK   e não antes disso
OK   painel consolida totais, achados e rascunhos
OK   e-mail fora de .leg.br/.gov.br é recusado como e-mail oficial
OK   faturamento exige contato do setor financeiro
OK   pedido de faturamento criado, aguardando aprovação
OK   plano NÃO é liberado antes da aprovação oficial
OK   não permite dois pedidos abertos
OK   página pública de aprovação mostra o resumo
OK   aprovação exige nome completo
OK   aprovação pelo e-mail oficial libera o faturamento
OK   plano Legislativo ativo com validade
OK   link de aprovação é de uso único
OK   admin registra empenho, nota fiscal e pagamento
OK   pedido Mercado Pago anual (10 meses) com link de checkout
OK   pago, mas ainda NÃO liberado sem a aprovação oficial
OK   plano segue o anterior enquanto não aprovado
OK   aprovado + pago = liberado
OK   plano Monitoramento liberado
OK   e-mail oficial pode recusar o pedido
OK   recusa não altera o plano
OK   TCE-SP: só a fonte estadual entra no repasse
OK   monitor do Diário Oficial do Estado criado
OK   publicação encontrada no DOE-SP
OK   achado do DOE-SP classificado, vinculado à emenda e com link da publicação
OK   painel de fontes mostra DOE-SP e TCE-SP ativos
OK   TSE: avisa quando a base ainda não foi importada
OK   TSE: importa só eleitos de cargos legislativos (sem prefeito, sem não eleitos, sem o arquivo BRASIL)
OK   TSE: tabela não tem colunas de CPF, e-mail ou cor/raça
OK   TSE: situação da importação no admin
OK   TSE: só eleitos, com nome, partido, número e Casa
OK   TSE: CPF e cor/raça não saem do servidor (minimização)
OK   TSE: vereador por município, acentos preservados
OK   gabinete preenchido com dados do TSE
OK   pesquisa na Câmara dos Deputados
OK   pesquisa no Senado (item único vira lista)
OK   análise com texto integral baixado da Câmara
OK   análise traz leis parecidas de outros entes
OK   histórico de análises
OK   página pública ativada com endereço amigável
OK   prestação de contas pública (sem login)
OK   risco alto: LOA anterior sem empenho
OK   painel lista as emendas em risco
OK   tema do próprio mandato criado
OK   notícias coletadas do Google Notícias (+ diários)
OK   sentimento e crise classificados
OK   título limpo, veículo separado
OK   alerta de crise registrado (e-mail; WhatsApp desligado no teste)
OK   coleta não duplica menções
OK   painel de sentimento de 14 dias
OK   pauta do dia gerada (texto)
OK   admin: CRM com MRR (sem a conta do admin) e etapas
OK   admin: funil até a liberação
OK   admin: receitas
OK   admin: planos e margem
OK   admin: prospecção importa eleitos do TSE
OK   admin: logs recebem erros do navegador
OK   admin: armazenamento
OK   admin: exportação das notas fiscais
OK   admin concede 7 dias de teste (não conta como receita)
OK   cliente vê o plano de teste
OK   conta suspensa perde o acesso
OK   acesso reativado
OK   exclusão exige digitar o nome da conta
OK   admin exclui a conta e os dados dela
OK   usuário da conta excluída não entra mais
OK   admin não exclui a própria conta
OK   exclusão registrada no histórico geral
Todos os testes passaram.


JavaScript: todos os arquivos passaram por verificação sintática.
Navegador Edge headless: 5 capturas, nenhum pageerror; mobile 390px sem overflow.
