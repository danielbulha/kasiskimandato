# Kasiski Mandato 7.0 — gestão operacional

Implementado sobre o pacote v6 recebido, sem remover módulos existentes:
- Demandas com protocolo gerado no servidor, status, prioridade, solicitante, contato, município, responsável e prazo.
- Tarefas com quadro Kanban por status, prioridade, responsável, prazo e vínculo opcional a demanda.
- Agenda com local, pauta, início/fim e vínculo opcional a demanda.
- Pesquisa textual no frontend, formulário de criação/edição, exclusão com confirmação.
- API CRUD autenticada, isolamento por conta/gabinete, histórico básico de alterações e resumo operacional.
- Menu e atalhos no painel.

## Implantação
1. Backup do PostgreSQL antes de substituir o backend.
2. Publicar backend no Render, mantendo as variáveis de ambiente e credenciais existentes.
3. A aplicação executa `db.create_all()` na inicialização para criar as novas tabelas. **Para produção com múltiplas instâncias, recomenda-se substituir essa inicialização por migração versionada antes de publicar.**
4. Publicar o pacote `kasiski-mandato-app-netlify-v7.zip` no site Netlify do app.
5. Testar criação/edição/exclusão de demandas, tarefas e agenda, incluindo dois gabinetes distintos.

## Limites conhecidos
- O vínculo entre registros é por ID; ainda não há upload documental, calendário externo, notificações ou permissões por função.
- O campo de responsável aceita usuários da mesma conta; a interface depende de a rota `/api/conta` devolver `usuarios` para apresentar opções. Caso contrário, o campo pode ficar sem opções.
- O Kanban é visual, sem arrastar e soltar. Os cartões permitem editar a situação.
- A agenda é uma lista de compromissos, sem sincronização Google/Microsoft.
- O histórico registra operações e usuário, não armazena o diff completo de cada campo.
- Testes de integração com PostgreSQL/Render/Netlify ainda devem ser realizados antes de produção.
