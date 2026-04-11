import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from pages.auditoria.models import AuditEvent
from .views import cadastro_cons_view, cadastro_view

User = get_user_model()


class CadastroUsuarioPermissaoTests(TestCase):
	def setUp(self):
		self.factory = RequestFactory()
		self.perm_view = Permission.objects.get(
			content_type__app_label='usuario',
			codename='view_usuarios',
		)
		self.perm_add = Permission.objects.get(
			content_type__app_label='usuario',
			codename='add_usuarios',
		)
		self.perm_change = Permission.objects.get(
			content_type__app_label='usuario',
			codename='change_usuarios',
		)

	def criar_usuario(self, username, permissoes=None, **kwargs):
		usuario = User.objects.create_user(username=username, password='teste123', **kwargs)
		if permissoes:
			usuario.user_permissions.set(permissoes)
		return usuario

	def build_get_request(self, path, user):
		request = self.factory.get(path)
		request.sisvar_extra = {}
		request.user = user
		return request

	def build_post_request(self, path, payload, user):
		request = self.factory.post(path, data=json.dumps(payload), content_type='application/json')
		request.sisvar_front = payload
		request.user = user
		return request

	def payload_usuario(self, estado='novo', user_id=None):
		return {
			'form': {
				'cadUsuario': {
					'estado': estado,
					'campos': {
						'id': user_id,
						'username': 'novo.usuario' if user_id is None else 'editado.usuario',
						'first_name': 'Novo Usuario',
						'email': 'novo@example.com',
						'password': 'Senha@123',
						'confirmpass': 'Senha@123',
						'ativo': True,
					}
				}
			}
		}

	def test_get_sem_view_levanta_permission_denied(self):
		usuario = self.criar_usuario('semview')
		request = self.build_get_request('/app/usuario/cadastro/', usuario)

		with self.assertRaises(PermissionDenied):
			cadastro_view(request)

	def test_get_sem_add_inicializa_visualizar(self):
		usuario = self.criar_usuario('viewer', [self.perm_view])
		request = self.build_get_request('/app/usuario/cadastro/', usuario)

		response = cadastro_view(request)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(request.sisvar_extra['form']['cadUsuario']['estado'], 'visualizar')
		self.assertEqual(
			request.sisvar_extra['others']['permissoes']['usuario'],
			{
				'acessar': True,
				'consultar': True,
				'incluir': False,
				'editar': False,
				'excluir': False,
			},
		)

	def test_post_novo_exige_add(self):
		usuario = self.criar_usuario('semadd', [self.perm_view])
		request = self.build_post_request('/app/usuario/cadastro/', self.payload_usuario('novo'), usuario)

		response = cadastro_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 403)
		self.assertIn('incluir usuários', data['mensagens']['erro']['conteudo'][0])

	def test_post_novo_com_add_cria_usuario(self):
		usuario = self.criar_usuario('comadd', [self.perm_view, self.perm_add])
		request = self.build_post_request('/app/usuario/cadastro/', self.payload_usuario('novo'), usuario)

		response = cadastro_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(data['success'])
		self.assertTrue(User.objects.filter(username='novo.usuario').exists())
		self.assertTrue(AuditEvent.objects.filter(action='create').exists())

	def test_post_editar_exige_change(self):
		usuario_operador = self.criar_usuario('semchange', [self.perm_view])
		alvo = self.criar_usuario('alvo', first_name='Alvo', email='alvo@example.com', is_active=True)
		payload = self.payload_usuario('editar', user_id=alvo.id)
		request = self.build_post_request('/app/usuario/cadastro/', payload, usuario_operador)

		response = cadastro_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 403)
		self.assertIn('editar usuários', data['mensagens']['erro']['conteudo'][0])

	def test_consulta_exige_view(self):
		usuario = self.criar_usuario('semconsulta')
		payload = {
			'form': {
				'consUsuario': {
					'campos': {
						'username_cons': '',
						'first_name_cons': '',
						'email_cons': '',
						'ativo_cons': False,
						'id_selecionado': None,
					}
				}
			}
		}
		request = self.build_post_request('/app/usuario/cadastro/cons', payload, usuario)

		with self.assertRaises(PermissionDenied):
			cadastro_cons_view(request)
