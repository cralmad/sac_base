import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from pages.cad_grupo_cli.models import GrupoCli
from pages.core.models import Cidade, Pais, Regiao

from .models import Cliente
from .views import cad_cliente_cons_view, cad_cliente_view

User = get_user_model()


class CadClientePermissaoViewTests(TestCase):
	def setUp(self):
		self.factory = RequestFactory()
		self.grupo = GrupoCli.objects.create(descricao='VAREJO')
		self.pais = Pais.objects.create(nome='Brasil', sigla='BRA', codigo_tel='+55')
		self.regiao = Regiao.objects.create(id_uf=35, nome='Sao Paulo', sigla='SP', pais=self.pais)
		self.cidade = Cidade.objects.create(id_cid=3550308, nome='Sao Paulo', regiao=self.regiao)

		self.perm_view = Permission.objects.get(
			content_type__app_label='cad_cliente',
			codename='view_cliente',
		)
		self.perm_add = Permission.objects.get(
			content_type__app_label='cad_cliente',
			codename='add_cliente',
		)
		self.perm_change = Permission.objects.get(
			content_type__app_label='cad_cliente',
			codename='change_cliente',
		)
		self.perm_delete = Permission.objects.get(
			content_type__app_label='cad_cliente',
			codename='delete_cliente',
		)

	def criar_usuario(self, username, permissoes=None):
		usuario = User.objects.create_user(username=username, password='teste123')
		if permissoes:
			usuario.user_permissions.set(permissoes)
		return usuario

	def build_post_request(self, path, payload, user):
		request = self.factory.post(
			path,
			data=json.dumps(payload),
			content_type='application/json',
		)
		request.sisvar_front = payload
		request.user = user
		return request

	def build_get_request(self, path, user):
		request = self.factory.get(path)
		request.sisvar_extra = {}
		request.user = user
		return request

	def payload_cliente(self, estado='novo', cliente_id=None):
		return {
			'form': {
				'cadCliente': {
					'estado': estado,
					'campos': {
						'id': cliente_id,
						'grupo': self.grupo.id,
						'nome': 'Cliente Teste',
						'rsocial': 'Cliente Teste LTDA',
						'logradouro': 'Rua',
						'endereco': 'Central',
						'numero': '100',
						'complemento': '',
						'bairro': 'Centro',
						'pais': self.pais.id,
						'regiao': self.regiao.id,
						'cidade': self.cidade.id,
						'codpostal': '01000-000',
						'identificador': 'DOC-001' if cliente_id is None else f'DOC-{cliente_id:03d}',
						'observacao': 'Observacao',
					}
				}
			}
		}

	def criar_cliente(self):
		return Cliente.objects.create(
			grupo=self.grupo,
			nome='Cliente Existente',
			rsocial='Cliente Existente LTDA',
			logradouro='Rua',
			endereco='Ja Existe',
			numero='10',
			complemento='',
			bairro='Centro',
			pais=self.pais,
			regiao=self.regiao,
			cidade=self.cidade,
			codpostal='01000-000',
			identificador='DOC-EXISTENTE',
			observacao='Registro base',
		)

	def test_get_sem_permissao_de_inclusao_inicializa_em_visualizar(self):
		usuario = self.criar_usuario('viewer', [self.perm_view])
		request = self.build_get_request('/app/cad/cliente/', usuario)

		response = cad_cliente_view(request)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(request.sisvar_extra['form']['cadCliente']['estado'], 'visualizar')
		self.assertEqual(
			request.sisvar_extra['others']['permissoes']['cad_cliente'],
			{
				'acessar': True,
				'consultar': True,
				'incluir': False,
				'editar': False,
				'excluir': False,
			},
		)

	def test_get_com_permissao_de_inclusao_inicializa_em_novo(self):
		usuario = self.criar_usuario('editor', [self.perm_view, self.perm_add])
		request = self.build_get_request('/app/cad/cliente/', usuario)

		response = cad_cliente_view(request)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(request.sisvar_extra['form']['cadCliente']['estado'], 'novo')

	def test_get_sem_permissao_view_levanta_permission_denied(self):
		usuario = self.criar_usuario('semview')
		request = self.build_get_request('/app/cad/cliente/', usuario)

		with self.assertRaises(PermissionDenied):
			cad_cliente_view(request)

	def test_post_novo_exige_permissao_add(self):
		usuario = self.criar_usuario('semadd', [self.perm_view])
		payload = self.payload_cliente(estado='novo')
		request = self.build_post_request('/app/cad/cliente/', payload, usuario)

		response = cad_cliente_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 403)
		self.assertIn('incluir clientes', data['mensagens']['erro']['conteudo'][0])
		self.assertEqual(Cliente.objects.count(), 0)

	def test_post_novo_com_permissao_add_salva_cliente(self):
		usuario = self.criar_usuario('comadd', [self.perm_view, self.perm_add])
		payload = self.payload_cliente(estado='novo')
		request = self.build_post_request('/app/cad/cliente/', payload, usuario)

		response = cad_cliente_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(data['success'])
		self.assertEqual(Cliente.objects.count(), 1)
		self.assertEqual(data['form']['cadCliente']['estado'], 'visualizar')

	def test_post_editar_exige_permissao_change(self):
		usuario = self.criar_usuario('semchange', [self.perm_view])
		cliente = self.criar_cliente()
		payload = self.payload_cliente(estado='editar', cliente_id=cliente.id)
		request = self.build_post_request('/app/cad/cliente/', payload, usuario)

		response = cad_cliente_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 403)
		self.assertIn('editar clientes', data['mensagens']['erro']['conteudo'][0])

	def test_post_excluir_exige_permissao_delete(self):
		usuario = self.criar_usuario('semdelete', [self.perm_view])
		cliente = self.criar_cliente()
		payload = self.payload_cliente(estado='excluir', cliente_id=cliente.id)
		request = self.build_post_request('/app/cad/cliente/', payload, usuario)

		response = cad_cliente_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 403)
		self.assertIn('excluir clientes', data['mensagens']['erro']['conteudo'][0])
		self.assertTrue(Cliente.objects.filter(id=cliente.id).exists())

	def test_consulta_exige_permissao_view(self):
		usuario = self.criar_usuario('semview')
		payload = {
			'form': {
				'consCliente': {
					'campos': {
						'nome_cons': 'CLIENTE',
						'id_selecionado': None,
					}
				}
			}
		}
		request = self.build_post_request('/app/cad/cliente/cons/', payload, usuario)

		with self.assertRaises(PermissionDenied):
			cad_cliente_cons_view(request)
