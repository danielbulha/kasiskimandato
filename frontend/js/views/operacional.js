// Kasiski Mandato 7.0 — gestão operacional integrada.
const OP = {
  demandas:{nome:'Demandas e protocolos',singular:'demanda',campos:['titulo','descricao','solicitante','contato','municipio','categoria','status','prioridade','responsavel_id','prazo'],estados:{recebida:'Recebida',em_analise:'Em análise',aguardando:'Aguardando',em_execucao:'Em execução',concluida:'Concluída'}},
  tarefas:{nome:'Tarefas e Kanban',singular:'tarefa',campos:['titulo','descricao','status','prioridade','responsavel_id','prazo','demanda_id'],estados:{a_fazer:'A fazer',em_andamento:'Em andamento',aguardando:'Aguardando',concluida:'Concluída'}},
  agenda:{nome:'Agenda do gabinete',singular:'compromisso',campos:['titulo','local','pauta','inicio','fim','demanda_id'],estados:null}
};
const opURL=(tipo,id='')=>`/api/gabinetes/${S.gabineteId}/operacional/${tipo}${id?'/'+id:''}`;
const opOptions=(items,selected)=>'<option value="">Não vinculado</option>'+items.map(x=>`<option value="${x.id}" ${String(selected||'')===String(x.id)?'selected':''}>${esc(x.nome||x.titulo)}</option>`).join('');
const opInput=(k,v,tipo,refs)=>{
 const labels={titulo:'Título',descricao:'Descrição',solicitante:'Solicitante',contato:'Contato',municipio:'Município',categoria:'Categoria',status:'Situação',prioridade:'Prioridade',responsavel_id:'Responsável',prazo:'Prazo',demanda_id:'Demanda relacionada',local:'Local',pauta:'Pauta',inicio:'Início',fim:'Fim'};
 let control;
 if(k==='status')control=`<select name="${k}">${Object.entries(OP[tipo].estados).map(([val,label])=>`<option value="${val}" ${v===val?'selected':''}>${label}</option>`).join('')}</select>`;
 else if(k==='prioridade')control=`<select name="${k}">${['baixa','normal','alta','urgente'].map(val=>`<option ${v===val?'selected':''}>${val}</option>`).join('')}</select>`;
 else if(k==='responsavel_id'||k==='demanda_id')control=`<select name="${k}">${opOptions(refs[k]||[],v)}</select>`;
 else if(k==='descricao'||k==='pauta')control=`<textarea name="${k}" rows="3">${esc(v||'')}</textarea>`;
 else control=`<input name="${k}" ${k==='titulo'?'required maxlength="200"':''} type="${k==='prazo'?'date':k==='inicio'||k==='fim'?'datetime-local':'text'}" value="${esc(v||'')}">`;
 return `<label class="op-field"><span>${labels[k]}</span>${control}</label>`;
};
async function opEditar(tipo,id){
 const obj=id?await api('GET',opURL(tipo,id)):{};
 const refs={responsavel_id:[],demanda_id:[]};
 try {const conta=await api('GET','/api/conta');refs.responsavel_id=conta.usuarios||[];}catch(e){}
 if(tipo!=='demandas')refs.demanda_id=await api('GET',opURL('demandas'));
 const overlay=document.createElement('div');overlay.className='op-overlay';
 overlay.innerHTML=`<section class="op-dialog" role="dialog" aria-modal="true" aria-label="Editar ${OP[tipo].singular}"><header><h2>${id?'Editar':'Novo(a)'} ${OP[tipo].singular}</h2><button type="button" class="op-fechar" aria-label="Fechar">×</button></header><form class="op-form">${OP[tipo].campos.map(k=>opInput(k,obj[k],tipo,refs)).join('')}<div class="op-actions"><button class="botao" type="submit">Salvar</button><button type="button" class="botao texto op-fechar">Cancelar</button>${id?'<button type="button" class="botao texto op-excluir">Excluir</button>':''}</div><p class="op-erro" role="alert"></p></form></section>`;
 document.body.append(overlay);overlay.querySelectorAll('.op-fechar').forEach(b=>b.onclick=()=>overlay.remove());
 overlay.addEventListener('click',e=>{if(e.target===overlay)overlay.remove()});
 overlay.querySelector('form').onsubmit=async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.target));try{await api(id?'PUT':'POST',opURL(tipo,id),d);overlay.remove();toast('Registro salvo.');navegar()}catch(err){overlay.querySelector('.op-erro').textContent=err.message||'Erro ao salvar.'}};
 if(id)overlay.querySelector('.op-excluir').onclick=async()=>{if(!confirm('Excluir este registro?'))return;try{await api('DELETE',opURL(tipo,id));overlay.remove();navegar()}catch(err){overlay.querySelector('.op-erro').textContent=err.message}};
}
async function opTela(el,tipo){
 const conf=OP[tipo],lista=await api('GET',opURL(tipo));
 const search=document.createElement('div');
 const cab=`<div class="cabecalho"><div><h1>${conf.nome}</h1><p>${lista.length} registro(s) · gabinete atual</p></div><div class="acoes"><button class="botao op-novo">+ Novo registro</button></div></div>`;
 const card=x=>`<article class="op-card" data-id="${x.id}" tabindex="0" role="button" aria-label="Editar ${esc(x.titulo)}"><b>${esc(x.titulo)}</b>${x.protocolo?`<small>${esc(x.protocolo)}</small>`:''}<p>${esc((x.descricao||x.pauta||x.solicitante||x.local||'').slice(0,160))}</p><small>${x.prazo?'Prazo: '+fmt.data(x.prazo):x.inicio?fmt.dataHora(x.inicio):''}${x.prioridade?' · '+esc(x.prioridade):''}</small></article>`;
 const render=(q='')=>{
 const dados=lista.filter(x=>JSON.stringify([x.titulo,x.descricao,x.protocolo,x.solicitante,x.municipio,x.local]).toLowerCase().includes(q.toLowerCase()));
 if(tipo==='tarefas')return `<div class="op-board">${Object.entries(conf.estados).map(([key,label])=>`<section class="op-column"><h3>${label} <small>${dados.filter(x=>x.status===key).length}</small></h3>${dados.filter(x=>x.status===key).map(card).join('')||'<p class="fraco">Sem tarefas</p>'}</section>`).join('')}</div>`;
 return `<div class="op-list">${dados.map(card).join('')||'<p class="fraco">Nenhum registro encontrado.</p>'}</div>`;
 };
 el.innerHTML=cab+`<div class="op-toolbar"><input type="search" class="op-search" placeholder="Pesquisar ${conf.nome.toLowerCase()}" aria-label="Pesquisar registros"></div><div class="op-results">${render()}</div>`;
 el.querySelector('.op-novo').onclick=()=>opEditar(tipo);
 el.querySelector('.op-search').oninput=e=>{el.querySelector('.op-results').innerHTML=render(e.target.value)};
 el.querySelector('.op-results').addEventListener('click',e=>{const card=e.target.closest('[data-id]');if(card)opEditar(tipo,Number(card.dataset.id))});
 el.querySelector('.op-results').addEventListener('keydown',e=>{if(e.key==='Enter'){const card=e.target.closest('[data-id]');if(card)opEditar(tipo,Number(card.dataset.id))}});
}
for(const tipo of Object.keys(OP))V[tipo]=el=>opTela(el,tipo);
// Resumo é consumido pelo painel original sem alterar seus indicadores financeiros.
