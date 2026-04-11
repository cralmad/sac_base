import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase

from pages.auditoria.models import AuditEvent
from .models import GrupoCli
from .views import cad_grupo_cli_cons_view, cad_grupo_cli_del_view, cad_grupo_cli_view

User = get_user_model()


class CadGrupoCliPermissaoViewTests(TestCase):
	def setUp(self):
		self.factory = RequestFactory()
		self.perm_view = Permission.objects.get(
			content_type__app_label='cad_grupo_cli',
			codename='view_grupocli',
		)
		self.perm_add = Permission.objects.get(
			content_type__app_label='cad_grupo_cli',
			codename='add_grupocli',
		)
		self.perm_change = Permission.objects.get(
			content_type__app_label='cad_grupo_cli',
			codename='change_grupocli',
		)
		self.perm_delete = Permission.objects.get(
			content_type__app_label='cad_grupo_cli',
			codename='delete_grupocli',
		)

	def criar_usuario(self, username, permissoes=None):
		usuario = User.objects.create_user(username=username, password='teste123')
		if permissoes:
			usuario.user_permissions.set(permissoes)
		return usuario

	def build_get_request(self, path, user):
		request = self.factory.get(path)
		request.sisvar_extra = {}
		request.user = user
		return request

	def build_post_request(self, path, payload, user):
		request = self.factory.post(
			path,
			data=json.dumps(payload),
			content_type='application/json',
		)
		request.sisvar_front = payload
		request.user = user
		return request

	def payload_form(self, estado='novo', grupo_id=None, descricao='Atacado'):
		return {
			'form': {
				'cadGrupoCli': {
					'estado': estado,
					'campos': {
						'id': grupo_id,
						'descricao': descricao,
					}
				}
			}
		}

	def test_get_sem_permissao_view_levanta_permission_denied(self):
		usuario = self.criar_usuario('semview')
		request = self.build_get_request('/app/cad/grupocli/', usuario)

		with self.assertRaises(PermissionDenied):
			cad_grupo_cli_view(request)

	def test_get_sem_permissao_de_inclusao_inicializa_em_visualizar(self):
		usuario = self.criar_usuario('viewer', [self.perm_view])
		request = self.build_get_request('/app/cad/grupocli/', usuario)

		response = cad_grupo_cli_view(request)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(request.sisvar_extra['form']['cadGrupoCli']['estado'], 'visualizar')
		self.assertEqual(
			request.sisvar_extra['others']['permissoes']['cad_grupo_cli'],
			{
				'acessar': True,
				'consultar': True,
				'incluir': False,
				'editar': False,
				'excluir': False,
			},
		)
		conteudo = response.content.decode('utf-8')
		self.assertIn('id="btn-salvar"', conteudo)
		self.assertIn('btn btn-primary d-none', conteudo)
		self.assertIn('id="btn-abrir-pesquisa"', conteudo)
		self.assertIn('btn btn-secondary d-none', conteudo)

	def test_post_novo_exige_permissao_add(self):
		usuario = self.criar_usuario('semadd', [self.perm_view])
		request = self.build_post_request('/app/cad/grupocli/', self.payload_form('novo'), usuario)

		response = cad_grupo_cli_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 403)
		self.assertIn('incluir grupos de cliente', data['mensagens']['erro']['conteudo'][0])
		self.assertFalse(GrupoCli.objects.filter(descricao='ATACADO').exists())

	def test_post_novo_com_permissao_add_salva_registro(self):
		usuario = self.criar_usuario('comadd', [self.perm_view, self.perm_add])
		request = self.build_post_request('/app/cad/grupocli/', self.payload_form('novo'), usuario)

		response = cad_grupo_cli_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(data['success'])
		self.assertTrue(GrupoCli.objects.filter(descricao='ATACADO').exists())
		self.assertTrue(AuditEvent.objects.filter(action='create').exists())

	def test_post_editar_exige_permissao_change(self):
		usuario = self.criar_usuario('semchange', [self.perm_view])
		grupo = GrupoCli.objects.create(descricao='VAREJO')
		request = self.build_post_request(
			'/app/cad/grupocli/',
			self.payload_form('editar', grupo_id=grupo.id, descricao='Novo nome'),
			usuario,
		)

		response = cad_grupo_cli_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 403)
		self.assertIn('editar grupos de cliente', data['mensagens']['erro']['conteudo'][0])

	def test_consulta_exige_permissao_view(self):
		usuario = self.criar_usuario('semview')
		payload = {
			'form': {
				'consGrupoCli': {
					'campos': {
						'descricao': 'ATA',
						'id_selecionado': None,
					}
				}
			}
		}
		request = self.build_post_request('/app/cad/grupocli/cons', payload, usuario)

		with self.assertRaises(PermissionDenied):
			cad_grupo_cli_cons_view(request)

	def test_delete_exige_permissao_delete(self):
		usuario = self.criar_usuario('semdelete', [self.perm_view])
		grupo = GrupoCli.objects.create(descricao='INDUSTRIA')
		request = self.build_post_request(
			'/app/cad/grupocli/del',
			self.payload_form(grupo_id=grupo.id),
			usuario,
		)

		response = cad_grupo_cli_del_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 403)
		self.assertIn('excluir grupos de cliente', data['mensagens']['erro']['conteudo'][0])
		self.assertTrue(GrupoCli.objects.filter(id=grupo.id).exists())

	def test_delete_realiza_soft_delete_e_auditoria(self):
		usuario = self.criar_usuario('comdelete', [self.perm_view, self.perm_delete])
		grupo = GrupoCli.objects.create(descricao='SOFTDELETE')
		request = self.build_post_request(
			'/app/cad/grupocli/del',
			self.payload_form(grupo_id=grupo.id, descricao=grupo.descricao),
			usuario,
		)

		response = cad_grupo_cli_del_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(data['success'])
		self.assertFalse(GrupoCli.objects.filter(id=grupo.id).exists())
		grupo_soft = GrupoCli.all_objects.get(id=grupo.id)
		self.assertTrue(grupo_soft.is_deleted)
		self.assertTrue(AuditEvent.objects.filter(action='soft_delete', object_id=str(grupo.id)).exists())

	def test_descricao_ativa_permanece_unica(self):
		GrupoCli.objects.create(descricao='VAREJO')

		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				GrupoCli.objects.create(descricao='varejo')

	def test_descricao_pode_ser_reutilizada_apos_soft_delete(self):
		grupo = GrupoCli.objects.create(descricao='VAREJO')
		grupo.soft_delete(reason='teste')
		grupo.save()

		novo_grupo = GrupoCli.objects.create(descricao='varejo')

		self.assertNotEqual(grupo.id, novo_grupo.id)
		self.assertEqual(novo_grupo.descricao, 'VAREJO')
