import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from pages.core.models import Pais
from pages.filial.models import Filial, UsuarioFilial
from .models import ZonaEntrega, ZonaEntregaExcecaoPostal, ZonaEntregaFaixaPostal
from .views import cadastro_zona_entrega_cons_view, cadastro_zona_entrega_del_view, cadastro_zona_entrega_view


User = get_user_model()


class ZonaEntregaViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.pais_pt = Pais.objects.create(nome='PORTUGAL', sigla='PRT', codigo_tel='+351')
        self.pais_br = Pais.objects.create(nome='BRASIL', sigla='BRA', codigo_tel='+55')
        self.filial_pt = Filial.objects.create(codigo='MAT', nome='MATRIZ', pais_endereco=self.pais_pt, pais_atuacao=self.pais_pt, is_matriz=True)
        self.filial_sem_atuacao = Filial.objects.create(codigo='FIL01', nome='FILIAL SEM PAIS', pais_endereco=self.pais_br, pais_atuacao=None, is_matriz=False)
        self.filial_pt_sem_escrita = Filial.objects.create(codigo='FIL02', nome='FILIAL SEM ESCRITA', pais_endereco=self.pais_pt, pais_atuacao=self.pais_pt, is_matriz=False)
        self.operador = User.objects.create_user(username='logistica', password='teste123', is_active=True)
        self.perm_view = Permission.objects.get(content_type__app_label='zona_entrega', codename='view_zonaentrega')
        self.perm_add = Permission.objects.get(content_type__app_label='zona_entrega', codename='add_zonaentrega')
        self.perm_change = Permission.objects.get(content_type__app_label='zona_entrega', codename='change_zonaentrega')
        self.perm_delete = Permission.objects.get(content_type__app_label='zona_entrega', codename='delete_zonaentrega')
        UsuarioFilial.objects.create(
            usuario=self.operador,
            filial=self.filial_pt,
            ativo=True,
            pode_consultar=True,
            pode_escrever=True,
        )
        UsuarioFilial.objects.create(
            usuario=self.operador,
            filial=self.filial_pt_sem_escrita,
            ativo=True,
            pode_consultar=True,
            pode_escrever=False,
        )

    def build_get_request(self, path, user=None):
        request = self.factory.get(path)
        request.sisvar_extra = {}
        request.user = user or self.operador
        return request

    def build_post_request(self, path, payload, user=None):
        request = self.factory.post(path, data=json.dumps(payload), content_type='application/json')
        request.sisvar_front = payload
        request.user = user or self.operador
        return request

    def payload_zona(self, estado='novo', zona_id=None, filial_id=None, faixas=None, excecoes=None):
        return {
            'form': {
                'cadZonaEntrega': {
                    'estado': estado,
                    'campos': {
                        'id': zona_id,
                        'filial_id': filial_id or self.filial_pt.id,
                        'codigo': 'ZNPT',
                        'descricao': 'ZONA PORTO',
                        'prioridade': '1',
                        'valor_cobranca_unitario_pedido': '2.50',
                        'valor_pagamento_unitario_entrega': '1.20',
                        'valor_pagamento_fixo_rota': '15.00',
                        'observacao': 'Teste',
                        'ativa': True,
                        'faixas': faixas if faixas is not None else [
                            {
                                'tipo_intervalo': 'CP7',
                                'codigo_postal_inicial': '4000-000',
                                'codigo_postal_final': '4999-999',
                                'ativa': True,
                            }
                        ],
                        'excecoes': excecoes if excecoes is not None else [
                            {
                                'tipo_excecao': 'EXCLUIR',
                                'codigo_postal': '4000-123',
                                'ativa': True,
                                'observacao': 'Difícil acesso',
                            }
                        ],
                    }
                }
            }
        }

    def test_get_sem_permissao_levanta_permission_denied(self):
        request = self.build_get_request('/app/logistica/zona-entrega/')

        with self.assertRaises(PermissionDenied):
            cadastro_zona_entrega_view(request)

    def test_get_injeta_filiais_com_pais_atuacao(self):
        self.operador.user_permissions.set([self.perm_view])
        request = self.build_get_request('/app/logistica/zona-entrega/')

        response = cadastro_zona_entrega_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(request.sisvar_extra['others']['filiais_atuacao']), 1)
        self.assertEqual(request.sisvar_extra['others']['filiais_atuacao'][0]['id'], self.filial_pt.id)

    def test_post_novo_salva_zona_faixa_e_excecao(self):
        self.operador.user_permissions.set([self.perm_view, self.perm_add])
        request = self.build_post_request('/app/logistica/zona-entrega/', self.payload_zona())

        response = cadastro_zona_entrega_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        zona = ZonaEntrega.objects.get(codigo='ZNPT')
        self.assertEqual(zona.filial, self.filial_pt)
        self.assertEqual(ZonaEntregaFaixaPostal.objects.filter(zona_entrega=zona).count(), 1)
        self.assertEqual(ZonaEntregaExcecaoPostal.objects.filter(zona_entrega=zona).count(), 1)

    def test_post_rejeita_filial_sem_pais_atuacao(self):
        self.operador.user_permissions.set([self.perm_view, self.perm_add])
        request = self.build_post_request('/app/logistica/zona-entrega/', self.payload_zona(filial_id=self.filial_sem_atuacao.id))

        response = cadastro_zona_entrega_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 403)
        self.assertIn('sem vínculo de escrita', data['mensagens']['erro']['conteudo'][0])

    def test_post_rejeita_filial_sem_vinculo_de_escrita(self):
        self.operador.user_permissions.set([self.perm_view, self.perm_add])
        request = self.build_post_request('/app/logistica/zona-entrega/', self.payload_zona(filial_id=self.filial_pt_sem_escrita.id))

        response = cadastro_zona_entrega_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 403)
        self.assertIn('sem vínculo de escrita', data['mensagens']['erro']['conteudo'][0])

    def test_post_rejeita_codigo_postal_portugal_invalido(self):
        self.operador.user_permissions.set([self.perm_view, self.perm_add])
        request = self.build_post_request(
            '/app/logistica/zona-entrega/',
            self.payload_zona(faixas=[{'tipo_intervalo': 'CP7', 'codigo_postal_inicial': '4000000', 'codigo_postal_final': '4999-999', 'ativa': True}], excecoes=[]),
        )

        response = cadastro_zona_entrega_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 422)
        self.assertIn('Código postal inválido para Portugal', data['mensagens']['erro']['conteudo'][0])

    def test_consulta_carrega_zona_com_faixas_e_excecoes(self):
        self.operador.user_permissions.set([self.perm_view, self.perm_add])
        cadastro_zona_entrega_view(self.build_post_request('/app/logistica/zona-entrega/', self.payload_zona()))
        zona = ZonaEntrega.objects.get(codigo='ZNPT')
        payload = {'form': {'consZonaEntrega': {'campos': {'filial_cons': '', 'codigo_cons': '', 'descricao_cons': '', 'id_selecionado': zona.id}}}}

        response = cadastro_zona_entrega_cons_view(self.build_post_request('/app/logistica/zona-entrega/cons', payload))
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['form']['cadZonaEntrega']['campos']['codigo'], 'ZNPT')
        self.assertEqual(len(data['form']['cadZonaEntrega']['campos']['faixas']), 1)
        self.assertEqual(len(data['form']['cadZonaEntrega']['campos']['excecoes']), 1)

    def test_delete_soft_delete_exige_permissao(self):
        self.operador.user_permissions.set([self.perm_view, self.perm_add])
        cadastro_zona_entrega_view(self.build_post_request('/app/logistica/zona-entrega/', self.payload_zona()))
        zona = ZonaEntrega.objects.get(codigo='ZNPT')

        response = cadastro_zona_entrega_del_view(self.build_post_request('/app/logistica/zona-entrega/del', self.payload_zona(estado='visualizar', zona_id=zona.id)))
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 403)
        self.assertIn('excluir zona de entrega', data['mensagens']['erro']['conteudo'][0].lower())

    def test_delete_rejeita_sem_vinculo_escrita_na_filial_da_zona(self):
        self.operador.user_permissions.set([self.perm_view, self.perm_add])
        sem_vinculo = User.objects.create_user(username='semvinculo', password='teste123', is_active=True)
        sem_vinculo.user_permissions.set([self.perm_view, self.perm_add, self.perm_delete])
        cadastro_zona_entrega_view(self.build_post_request('/app/logistica/zona-entrega/', self.payload_zona()))
        zona = ZonaEntrega.objects.get(codigo='ZNPT')

        response = cadastro_zona_entrega_del_view(
            self.build_post_request('/app/logistica/zona-entrega/del', self.payload_zona(estado='visualizar', zona_id=zona.id), user=sem_vinculo)
        )
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 403)
        self.assertIn('vínculo de escrita', data['mensagens']['erro']['conteudo'][0])
