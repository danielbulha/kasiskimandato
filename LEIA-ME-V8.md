# Kasiski Mandato 8.0 — inteligência legislativa e financeira

Evolução incremental da v7. Mantidos os módulos anteriores.

## Entregue
- Central de inteligência no menu: briefing de tarefas, demandas e agenda com prazos.
- Radar legislativo com cadastro manual de proposições, histórico de versões e comparação textual por diff.
- Auditoria aritmética de emendas (indicado/empenhado/liquidado/pago), prazos e origem dos dados.
- Visão das verificações cruzadas já armazenadas para minutas, sem chamar serviços externos ou inventar validações.
- APIs autenticadas e isoladas por gabinete.

## Não entregue / limites
- Não há captura automática de tramitação ou sincronização adicional com Câmara, Senado, Transferegov ou portais estaduais; exigem conectores e homologação.
- O radar compara textos cadastrados e não verifica sua autenticidade automaticamente.
- O Doublecheck apresenta resultados existentes, não faz nova análise jurídica nem valida jurisprudência em tempo real.
- O briefing é determinístico e não usa IA generativa.
- O módulo financeiro não confirma pagamentos em fontes oficiais; apenas sinaliza inconsistências dos dados armazenados.
- O sistema original usa db.create_all() e ALTER TABLE na inicialização. Para produção, adotar migrações versionadas.

## Implantação
1. Faça backup do banco de dados e da versão 7.
2. Publique o backend no Render com as variáveis já configuradas.
3. Publique o ZIP separado do frontend no Netlify.
4. Homologue permissões entre gabinetes, criação/edição de radar, comparações e relatórios financeiros.
5. Não publicar como fonte oficial sem verificar integrações e dados.
