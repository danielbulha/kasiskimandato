"""Regressões do piloto; SQLite em memória, rede e IA simuladas explicitamente."""
import os
import sys
import json
import io
import zipfile
import unittest
from unittest.mock import patch, Mock
from sqlalchemy import text
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.update(DATABASE_URL='sqlite://', AMBIENTE='teste', VERIFICAR_EMAIL='nao',
                  ANTHROPIC_API_KEY='', OPENAI_API_KEY='', GEMINI_API_KEY='', SECRET_KEY='x'*40)
from app import app
from extensions import db, ErroAPI
from models import Conta, Usuario, Gabinete, Emenda, Minuta, Comunicado, EventoEmenda
from models_piloto import Acompanhamento, ConsentimentoWA, NotificacaoWA
from auth import gerar_token
from services import rag_piloto as rag, monitor_piloto as monitor, transferegov_piloto as tg, whatsapp
from services import convenios_piloto as cv


class Piloto(unittest.TestCase):
    def setUp(self):
        self.ctx=app.app_context(); self.ctx.push()
        db.session.execute(text('PRAGMA foreign_keys=OFF'));db.session.commit()
        db.drop_all(); db.create_all()
        db.session.execute(text('PRAGMA foreign_keys=ON'));db.session.commit()
        c=Conta(nome='Teste'); c2=Conta(nome='Outra');db.session.add_all([c,c2]);db.session.flush()
        self.u=Usuario(conta_id=c.id,nome='Equipe',email='teste@example.com',senha_hash='teste',verificado=True)
        self.u2=Usuario(conta_id=c2.id,nome='Outra',email='outra@example.com',senha_hash='teste',verificado=True)
        self.g=Gabinete(conta_id=c.id,parlamentar='Teste',cargo='vereador',casa='Câmara Teste',uf='SP',municipio='Teste')
        db.session.add_all([self.u,self.u2,self.g]);db.session.flush()
        self.e=Emenda(gabinete_id=self.g.id,esfera='federal',numero='202027070006',objeto='Unidade de saúde')
        db.session.add(self.e);db.session.commit()
        self.client=app.test_client(); self.h={'Authorization':'Bearer '+gerar_token(self.u)}
        self.h2={'Authorization':'Bearer '+gerar_token(self.u2)}
        app.config.update(TESTE=True, WA_ENVIO_ATIVO=False)

    def tearDown(self):
        db.session.remove();self.ctx.pop()

    def fonte(self,tipo='regimento'):
        return rag.cadastrar(self.g,self.u,{'tipo':tipo,'titulo':'Norma de teste','url':'https://camara.leg.br/norma',
            'versao':'fixture-1','texto':'Art. 1º A competência e iniciativa de proposições seguem as atribuições da Câmara. Art. 2º Requerimentos sobre saúde pública são examinados pela comissão competente.', 'conferido':True})

    def acompanhamento(self):
        a=Acompanhamento(emenda_id=self.e.id,plano_id=3221);db.session.add(a);db.session.commit();return a

    def registro(self,status='CIENTE'):
        return {'id_plano_acao':3221,'situacao_plano_acao':status,'numero_emenda_parlamentar_plano_acao':202027070006}

    def consentir(self):
        c=ConsentimentoWA(gabinete_id=self.g.id,usuario_id=self.u.id,telefone='5511999990000',evidencia='teste');db.session.add(c);db.session.commit();return c

    def test_fontes_isoladas_e_jurisdicao(self):
        self.fonte();self.assertTrue(rag.recuperar(self.g,'saúde'))
        self.g.municipio='Outra cidade';self.assertEqual(rag.recuperar(self.g,'saúde'),[])

    def test_fonte_rejeita_origem_nao_oficial(self):
        with self.assertRaises(ErroAPI):
            rag.cadastrar(self.g,self.u,{'tipo':'regimento','titulo':'x','url':'https://exemplo.com','versao':'1','texto':'a'*100,'conferido':True})

    def test_competencia_privativa_bloqueada(self):
        r=rag.avaliar(self.g,'projeto_lei','Criar crime e pena de prisão para vandalismo')
        self.assertEqual(r['estado'],'bloqueado');self.assertIn('planalto',r['riscos'][0]['url'])

    def test_indicacao_nao_confundida_com_pl(self):
        self.assertEqual(rag.avaliar(self.g,'indicacao','Sugerir criar crime ao Congresso')['estado'],'revisao_obrigatoria')

    def test_falta_base_nao_aprovada(self):
        self.assertIn('lei_organica',rag.avaliar(self.g,'projeto_lei','saúde')['fontes_ausentes'])

    def test_http_bloqueia_antes_ia(self):
        with patch('services.ia.gerar') as gerar:
            r=self.client.post(f'/api/gabinetes/{self.g.id}/minutas',headers=self.h,json={'tipo':'projeto_lei','demanda':'Criar crime e pena de prisão para vandalismo'})
        self.assertEqual(r.status_code,422);gerar.assert_not_called()

    def test_primeira_consulta_sem_alerta(self):
        a=self.acompanhamento();self.consentir();self.assertFalse(monitor.aplicar(a.id,self.registro()))
        self.assertEqual(EventoEmenda.query.count(),0);self.assertEqual(NotificacaoWA.query.count(),0)

    def test_mudanca_duplicacao_e_retorno(self):
        a=self.acompanhamento();self.consentir()
        for s in ('CIENTE','IMPEDIDO','IMPEDIDO','CIENTE'):monitor.aplicar(a.id,self.registro(s))
        self.assertEqual(EventoEmenda.query.count(),2);self.assertEqual(Comunicado.query.count(),2)
        self.assertEqual(NotificacaoWA.query.count(),2);self.assertEqual(self.e.fase,'indicada')

    def test_sem_consentimento_sem_fila(self):
        a=self.acompanhamento();monitor.aplicar(a.id,self.registro());monitor.aplicar(a.id,self.registro('IMPEDIDO'))
        self.assertEqual(NotificacaoWA.query.count(),0)

    def test_falha_preserva_snapshot(self):
        a=self.acompanhamento();monitor.aplicar(a.id,self.registro())
        with patch.object(tg,'plano',side_effect=ErroAPI('Indisponível',502)):
            r=monitor.sincronizar(self.g)
        db.session.refresh(a);self.assertEqual(r['erros'],1);self.assertEqual(a.situacao,'CIENTE');self.assertTrue(a.erro)

    def test_identidade_divergente(self):
        a=self.acompanhamento()
        with self.assertRaises(ErroAPI): monitor.aplicar(a.id,{'id_plano_acao':99,'situacao_plano_acao':'CIENTE'})

    def test_paginacao_contrato(self):
        responses=[Mock(status_code=200,json=lambda:{'data':[self.registro()],'total_pages':2,'page_number':1}),
                   Mock(status_code=200,json=lambda:{'data':[{**self.registro(),'id_plano_acao':3222}],'total_pages':2,'page_number':2})]
        with patch.object(tg.requests,'get',side_effect=responses) as get:
            self.assertEqual(len(tg.consultar(ano_plano_acao=2020)),2)
            self.assertEqual(get.call_args.kwargs['params']['pagina'],2)

    def test_esquema_invalido_nao_lista_vazia(self):
        with patch.object(tg.requests,'get',return_value=Mock(status_code=200,json=lambda:[])):
            with self.assertRaises(ErroAPI):tg.consultar()

    def test_erro_http(self):
        with patch.object(tg.requests,'get',return_value=Mock(status_code=429)):
            with self.assertRaises(ErroAPI):tg.consultar()

    def test_isolamento_contas(self):
        for url in (f'/api/gabinetes/{self.g.id}/fontes-legais',f'/api/emendas/{self.e.id}/acompanhamento',f'/api/gabinetes/{self.g.id}/whatsapp-consentimento',f'/api/gabinetes/{self.g.id}/servicos-territorio'):
            self.assertEqual(self.client.get(url,headers=self.h2).status_code,404)

    def test_vinculo_exige_numero_oficial(self):
        with patch.object(tg,'plano',return_value={**self.registro(),'numero_emenda_parlamentar_plano_acao':99}):
            r=self.client.put(f'/api/emendas/{self.e.id}/acompanhamento',headers=self.h,json={'plano_id':3221})
        self.assertEqual(r.status_code,409);self.assertEqual(Acompanhamento.query.count(),0)

    def test_revogacao_cancela_fila(self):
        a=self.acompanhamento();self.consentir();monitor.aplicar(a.id,self.registro());monitor.aplicar(a.id,self.registro('IMPEDIDO'))
        r=self.client.delete(f'/api/gabinetes/{self.g.id}/whatsapp-consentimento',headers=self.h)
        self.assertEqual(r.status_code,200);self.assertEqual(NotificacaoWA.query.first().estado,'cancelado')

    def test_opt_in_boolean_estrito(self):
        r=self.client.post(f'/api/gabinetes/{self.g.id}/whatsapp-consentimento',headers=self.h,json={'telefone':'5511999990000','aceito':'false'})
        self.assertEqual(r.status_code,400)

    def test_wa_desligado_nao_chama_rede(self):
        with patch.object(whatsapp.requests,'post') as post:self.assertEqual(monitor.enviar_pendentes(),0)
        post.assert_not_called()

    def test_wa_timeout_nao_reenvia(self):
        a=self.acompanhamento();self.consentir();monitor.aplicar(a.id,self.registro());monitor.aplicar(a.id,self.registro('IMPEDIDO'))
        app.config.update(TESTE=False,WA_ENVIO_ATIVO=True,WA_TOKEN='teste',WA_PHONE_ID='123',WA_TEMPLATE='teste')
        with patch.object(whatsapp.requests,'post',side_effect=whatsapp.requests.Timeout) as post:
            monitor.enviar_pendentes();monitor.enviar_pendentes();self.assertEqual(post.call_count,1)
        self.assertEqual(NotificacaoWA.query.first().estado,'incerto')

    def test_wa_aceito_nao_entregue(self):
        a=self.acompanhamento();self.consentir();monitor.aplicar(a.id,self.registro());monitor.aplicar(a.id,self.registro('IMPEDIDO'))
        app.config.update(TESTE=False,WA_ENVIO_ATIVO=True,WA_TOKEN='teste',WA_PHONE_ID='123',WA_TEMPLATE='teste')
        with patch.object(whatsapp.requests,'post',return_value=Mock(status_code=200,json=lambda:{'messages':[{'id':'wamid.fixture'}]})):
            self.assertEqual(monitor.enviar_pendentes(),1)
        self.assertEqual(NotificacaoWA.query.first().estado,'aceito')

    def test_revisao_e_invalidacao(self):
        self.fonte();self.fonte('lei_organica')
        m=Minuta(gabinete_id=self.g.id,tipo='requerimento',demanda='saúde',titulo='Requerimento',texto='Informações sobre saúde pública',modelo='fixture-real',analise=json.dumps({'triagem':rag.avaliar(self.g,'requerimento','saúde')}))
        db.session.add(m);db.session.commit()
        r=self.client.post(f'/api/minutas/{m.id}/revisao',headers=self.h,json={'hash':rag.hash_minuta(m,self.g),'decisao':'aprovado','parecer':'Conferência jurídica realizada nas fontes cadastradas.'})
        self.assertEqual(r.status_code,200,r.json);self.assertEqual(r.json['estado'],'aprovado')
        m.texto+=' alterado';db.session.commit();self.assertEqual(rag.revisao_atual(m,self.g)['estado'],'pendente')

    def test_revisao_hash_obsoleto(self):
        m=Minuta(gabinete_id=self.g.id,tipo='requerimento',demanda='saúde',texto='x');db.session.add(m);db.session.commit()
        r=self.client.post(f'/api/minutas/{m.id}/revisao',headers=self.h,json={'hash':'antigo','decisao':'aprovado','parecer':'Conferência nas fontes oficiais realizada.'})
        self.assertEqual(r.status_code,409)

    def test_demo_nao_aprovavel(self):
        m=Minuta(gabinete_id=self.g.id,tipo='requerimento',demanda='saúde',texto='x',modelo='demo');db.session.add(m);db.session.commit()
        r=self.client.post(f'/api/minutas/{m.id}/revisao',headers=self.h,json={'hash':rag.hash_minuta(m,self.g),'decisao':'aprovado','parecer':'Conferência nas fontes oficiais realizada.'})
        self.assertEqual(r.status_code,409)

    def csv_zip(self, text):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('siconv_convenio.csv',text)
        buf.seek(0);return buf

    def test_csv_convenio_utf8_e_selecao(self):
        d=cv.ler_zip(self.csv_zip('NR_CONVENIO;ID_PROPOSTA;SIT_CONVENIO\n123;456;Em execução\n789;555;Concluído\n'),[123])
        self.assertEqual(list(d),['123']);self.assertEqual(d['123']['situacao_plano_acao'],'Em execução')

    def test_csv_schema_invalido(self):
        with self.assertRaises(ErroAPI):cv.ler_zip(self.csv_zip('numero;status\n123;Pago'),[123])

    def test_csv_duplicado(self):
        with self.assertRaises(ErroAPI):cv.ler_zip(self.csv_zip('NR_CONVENIO;ID_PROPOSTA;SIT_CONVENIO\n123;456;A\n123;456;B'),[123])

    def test_convenio_proposta_divergente(self):
        a=Acompanhamento(emenda_id=self.e.id,plano_id=123,fonte='convenio',proposta_id='456');db.session.add(a);db.session.commit()
        with self.assertRaises(ErroAPI):monitor.aplicar(a.id,{'id_plano_acao':123,'situacao_plano_acao':'Em execução','proposta_id':'999'})

    def test_convenio_transicao_preserva_fase(self):
        a=Acompanhamento(emenda_id=self.e.id,plano_id=123,fonte='convenio',proposta_id='456');db.session.add(a);db.session.commit()
        for s in ('Em execução','Prestação de contas enviada'):
            monitor.aplicar(a.id,{'id_plano_acao':123,'situacao_plano_acao':s,'proposta_id':'456','url':cv.URL})
        self.assertEqual(EventoEmenda.query.count(),1);self.assertEqual(self.e.fase,'indicada')
        self.assertIn('Convênio',EventoEmenda.query.first().descricao)

    def test_fonte_nova_invalida_revisao(self):
        self.fonte();self.fonte('lei_organica')
        m=Minuta(gabinete_id=self.g.id,tipo='requerimento',demanda='saúde',texto='Informações');db.session.add(m);db.session.commit()
        antigo=rag.hash_minuta(m,self.g);self.fonte();self.assertNotEqual(antigo,rag.hash_minuta(m,self.g))

    def test_excluir_emenda_com_fila(self):
        a=self.acompanhamento();self.consentir();monitor.aplicar(a.id,self.registro());monitor.aplicar(a.id,self.registro('IMPEDIDO'))
        r=self.client.delete(f'/api/emendas/{self.e.id}',headers=self.h)
        self.assertEqual(r.status_code,200,r.json);self.assertEqual(NotificacaoWA.query.count(),0)

    def test_excluir_gabinete_com_fontes(self):
        self.fonte();self.consentir();self.acompanhamento()
        r=self.client.delete(f'/api/gabinetes/{self.g.id}',headers=self.h)
        self.assertEqual(r.status_code,200,r.json)

    def test_revisao_isolada_por_conta(self):
        m=Minuta(gabinete_id=self.g.id,tipo='requerimento',demanda='saúde',texto='Informações');db.session.add(m);db.session.commit()
        self.assertEqual(self.client.get(f'/api/minutas/{m.id}/revisao',headers=self.h2).status_code,404)

    def test_formulario_quatro_campos(self):
        with patch('services.legislativo_fontes.leis_parecidas',return_value=[]):
            r=self.client.post(f'/api/gabinetes/{self.g.id}/minutas',headers=self.h,json={'tipo':'requerimento','tema':'Saúde','objetivo':'Obter dados dos horários de atendimento das unidades','publico':'Todos os residentes'})
        self.assertEqual(r.status_code,201,r.json)
        self.assertIn('Todos os residentes',r.json['demanda']);self.assertIn('triagem',r.json['analise'])


if __name__=='__main__':unittest.main(verbosity=2)
