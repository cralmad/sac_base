import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from pages.core.models import Pais
from pages.filial.models import Filial, UsuarioFilial
from .models import Motorista
from .views import cadastro_motorista_cons_view, cadastro_motorista_del_view, cadastro_motorista_view


User = get_user_model()


class MotoristaViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.pais_pt = Pais.objects.create(nome='PORTUGAL', sigla='PRT', codigo_tel='+351')
        self.filial_escrita = Filial.objects.create(codigo='MAT', nome='MATRIZ', pais_endereco=self.pais_pt, pais_atuacao=self.pais_pt, is_matriz=True)
        self.filial_sem_escrita = Filial.objects.create(codigo='FIL01', nome='FILIAL A', pais_endereco=self.pais_pt, pais_atuacao=self.pais_pt, is_matriz=False)

        self.operador = User.objects.create_user(username='operador_motorista', password='teste123', is_active=True)
        self.perm_view = Permission.objects.get(content_type__app_label='motorista', codename='view_motorista')
        self.perm_add = Permission.objects.get(content_type__app_label='motorista', codename='add_motorista')
        self.perm_change = Permission.objects.get(content_type__app_label='motorista', codename='change_motorista')
        self.perm_delete = Permission.objects.get(content_type__app_label='motorista', codename='delete_motorista')

        UsuarioFilial.objects.create(
            usuario=self.operador,
            filial=self.filial_escrita,
            ativo=True,
            pode_consultar=True,
            pode_escrever=True,
        )
        UsuarioFilial.objects.create(
            usuario=self.operador,
            filial=self.filial_sem_escrita,
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

    def payload_motorista(self, estado='novo', motorista_id=None, filial_id=None):
        return {
            'form': {
                'cadMotorista': {
                    'estado': estado,
                    'campos': {
                        'id': motorista_id,
                        'filial_id': filial_id or self.filial_escrita.id,
                        'codigo': 'MOT001',
                        'nome': 'JOAO MOTORISTA',
                        'telefone': '+351912345678',
                        'ativa': True,
                    }
                }
            }
        }

    def test_get_sem_permissao_levanta_permission_denied(self):
        request = self.build_get_request('/app/logistica/motorista/')

        with self.assertRaises(PermissionDenied):
            cadastro_motorista_view(request)

    def test_get_lista_apenas_filiais_com_escrita(self):
        self.operador.user_permissions.set([self.perm_view])
        request = self.build_get_request('/app/logistica/motorista/')

        response = cadastro_motorista_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(request.sisvar_extra['others']['filiais_escrita']), 1)
        self.assertEqual(request.sisvar_extra['others']['filiais_escrita'][0]['id'], self.filial_escrita.id)

    def test_post_novo_salva_motorista(self):
        self.operador.user_permissions.set([self.perm_view, self.perm_add])
        request = self.build_post_request('/app/logistica/motorista/', self.payload_motorista())

        response = cadastro_motorista_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertTrue(Motorista.objects.filter(nome='JOAO MOTORISTA').exists())

    def test_post_rejeita_filial_sem_escrita(self):
        self.operador.user_permissions.set([self.perm_view, self.perm_add])
        request = self.build_post_request('/app/logistica/motorista/', self.payload_motorista(filial_id=self.filial_sem_escrita.id))

        response = cadastro_motorista_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 403)
        self.assertIn('sem vínculo de escrita', data['mensagens']['erro']['conteudo'][0])

    def test_consulta_nao_carrega_motorista_fora_do_escopo(self):
        self.operador.user_permissions.set([self.perm_view, self.perm_add])
        outro = User.objects.create_user(username='outro', password='teste123', is_active=True)
        outro.user_permissions.set([self.perm_view, self.perm_add])
        UsuarioFilial.objects.create(usuario=outro, filial=self.filial_sem_escrita, ativo=True, pode_consultar=True, pode_escrever=True)
        cadastro_motorista_view(self.build_post_request('/app/logistica/motorista/', self.payload_motorista(filial_id=self.filial_sem_escrita.id), user=outro))
        motorista = Motorista.objects.get(filial=self.filial_sem_escrita)

        payload = {
            'form': {
                'consMotorista': {
                    'campos': {
                        'filial_cons': '',
                        'nome_cons': '',
                        'telefone_cons': '',
                        'id_selecionado': motorista.id,
                    }
                }
            }
        }
        response = cadastro_motorista_cons_view(self.build_post_request('/app/logistica/motorista/cons', payload))

        self.assertEqual(response.status_code, 404)

    def test_delete_exige_permissao_delete(self):
        self.operador.user_permissions.set([self.perm_view, self.perm_add])
        cadastro_motorista_view(self.build_post_request('/app/logistica/motorista/', self.payload_motorista()))
        motorista = Motorista.objects.get(nome='JOAO MOTORISTA')

        response = cadastro_motorista_del_view(self.build_post_request('/app/logistica/motorista/del', self.payload_motorista(estado='visualizar', motorista_id=motorista.id)))
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 403)
        self.assertIn('excluir motorista', data['mensagens']['erro']['conteudo'][0].lower())
