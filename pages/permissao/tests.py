import json

from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from pages.auditoria.models import AuditEvent
from .views import (
	cadastro_grupo_cons_view,
	cadastro_grupo_view,
	permissao_usuario_cons_view,
	permissao_usuario_view,
)

User = get_user_model()


class CadastroGrupoViewTests(TestCase):
	def setUp(self):
		self.factory = RequestFactory()
		self.operador = User.objects.create_user(
			username="operador_grupo",
			password="12345678",
			first_name="Operador Grupo",
			is_active=True,
		)
		self.perm_view_group = Permission.objects.get(
			content_type__app_label="auth",
			codename="view_group",
		)
		self.perm_add_group = Permission.objects.get(
			content_type__app_label="auth",
			codename="add_group",
		)
		self.perm_change_group = Permission.objects.get(
			content_type__app_label="auth",
			codename="change_group",
		)
		self.perm_delete_group = Permission.objects.get(
			content_type__app_label="auth",
			codename="delete_group",
		)

	def build_request(self, path, payload, user=None):
		request = self.factory.post(
			path,
			data=json.dumps(payload),
			content_type="application/json"
		)
		request.sisvar_front = payload
		request.user = user or self.operador
		return request

	def build_get_request(self, path, user=None):
		request = self.factory.get(path)
		request.sisvar_extra = {}
		request.user = user or self.operador
		return request

	def test_get_inicializa_formulario_sem_campo_ativo(self):
		self.operador.user_permissions.set([self.perm_view_group])
		request = self.build_get_request("/app/permissao/grupos/")

		response = cadastro_grupo_view(request)

		self.assertEqual(response.status_code, 200)
		self.assertIn("form", request.sisvar_extra)

		campos = request.sisvar_extra["form"]["cadGrupo"]["campos"]
		schema = request.sisvar_extra["schema"]["cadGrupo"]

		self.assertNotIn("ativo", campos)
		self.assertNotIn("ativo", schema)
		self.assertEqual(campos["permissoes"], [])
		self.assertEqual(request.sisvar_extra["form"]["cadGrupo"]["estado"], "visualizar")

	def test_get_sem_permissao_view_levanta_permission_denied(self):
		request = self.build_get_request("/app/permissao/grupos/")

		with self.assertRaises(PermissionDenied):
			cadastro_grupo_view(request)

	def test_post_salva_permissao_auth_sem_erro_de_content_type(self):
		self.operador.user_permissions.set([self.perm_view_group, self.perm_add_group])
		payload = {
			"form": {
				"cadGrupo": {
					"estado": "novo",
					"campos": {
						"id": None,
						"nome": "Administradores",
						"permissoes": ["auth.view_group", "auth.change_group"],
					}
				}
			}
		}
		request = self.build_request("/app/permissao/grupos/", payload)

		response = cadastro_grupo_view(request)
		payload = json.loads(response.content)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(payload["success"])
		self.assertEqual(
			sorted(payload["form"]["cadGrupo"]["campos"]["permissoes"]),
			["auth.change_group", "auth.view_group"],
		)
		self.assertNotIn("ativo", payload["form"]["cadGrupo"]["campos"])
		self.assertTrue(AuditEvent.objects.filter(action="create").exists())

	def test_post_rejeita_permissao_invalida_sem_criar_grupo(self):
		self.operador.user_permissions.set([self.perm_view_group, self.perm_add_group])
		payload = {
			"form": {
				"cadGrupo": {
					"estado": "novo",
					"campos": {
						"id": None,
						"nome": "Operacao",
						"permissoes": ["auth.inexistente"],
					}
				}
			}
		}
		request = self.build_request("/app/permissao/grupos/", payload)

		response = cadastro_grupo_view(request)
		retorno = json.loads(response.content)

		self.assertEqual(response.status_code, 422)
		self.assertIn("Permissões inválidas", retorno["mensagens"]["erro"]["conteudo"][0])
		self.assertFalse(Group.objects.filter(name="OPERACAO").exists())

	def test_post_rejeita_exclusao_sem_delete_group(self):
		self.operador.user_permissions.set([self.perm_view_group, self.perm_add_group])
		grupo = Group.objects.create(name="EXCLUIR")
		payload = {
			"form": {
				"cadGrupo": {
					"estado": "excluir",
					"campos": {
						"id": grupo.id,
						"nome": grupo.name,
						"permissoes": [],
					}
				}
			}
		}
		request = self.build_request("/app/permissao/grupos/", payload)

		response = cadastro_grupo_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 403)
		self.assertIn("excluir grupos de permissão", data["mensagens"]["erro"]["conteudo"][0])

	def test_consulta_retorna_campos_sem_ativo(self):
		self.operador.user_permissions.set([self.perm_view_group, self.perm_add_group])
		create_payload = {
			"form": {
				"cadGrupo": {
					"estado": "novo",
					"campos": {
						"id": None,
						"nome": "Consulta",
						"permissoes": ["auth.view_group"],
					}
				}
			}
		}
		create_request = self.build_request("/app/permissao/grupos/", create_payload)
		create_response = cadastro_grupo_view(create_request)
		create_data = json.loads(create_response.content)
		grupo_id = create_data["form"]["cadGrupo"]["campos"]["id"]

		cons_payload = {
			"form": {
				"consGrupo": {
					"campos": {
						"id_selecionado": grupo_id,
						"nome_cons": "",
					}
				}
			}
		}
		cons_request = self.build_request("/app/permissao/grupos/cons", cons_payload)

		response = cadastro_grupo_cons_view(cons_request)
		payload = json.loads(response.content)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload["form"]["cadGrupo"]["campos"]["nome"], "CONSULTA")
		self.assertNotIn("ativo", payload["form"]["cadGrupo"]["campos"])


class PermissaoUsuarioViewTests(TestCase):
	def setUp(self):
		self.factory = RequestFactory()
		self.operador = User.objects.create_user(
			username="operador",
			password="12345678",
			first_name="Operador",
			is_active=True,
		)
		self.usuario_alvo = User.objects.create_user(
			username="alvo",
			password="12345678",
			first_name="Usuario Alvo",
			is_active=True,
		)
		self.usuario_inativo = User.objects.create_user(
			username="inativo",
			password="12345678",
			first_name="Usuario Inativo",
			is_active=False,
		)
		self.superusuario = User.objects.create_superuser(
			username="root",
			password="12345678",
			first_name="Super Usuario",
		)
		self.grupo_a = Group.objects.create(name="GRUPO A")
		self.grupo_b = Group.objects.create(name="GRUPO B")
		self.perm_view_group = Permission.objects.get(
			content_type__app_label="auth",
			codename="view_group",
		)
		self.perm_view_usuario = Permission.objects.get(
			content_type__app_label="usuario",
			codename="view_usuarios",
		)
		self.perm_change_usuario = Permission.objects.get(
			content_type__app_label="usuario",
			codename="change_usuarios",
		)
		self.perm_change_group = Permission.objects.get(
			content_type__app_label="auth",
			codename="change_group",
		)
		self.grupo_a.permissions.set([self.perm_view_group])
		self.grupo_b.permissions.set([self.perm_change_group])
		self.operador.user_permissions.set([
			self.perm_view_group,
			self.perm_view_usuario,
			self.perm_change_usuario,
		])

	def build_request(self, path, payload, user=None):
		request = self.factory.post(
			path,
			data=json.dumps(payload),
			content_type="application/json"
		)
		request.sisvar_front = payload
		request.user = user or self.operador
		return request

	def test_get_injeta_apenas_usuarios_elegiveis_e_escopo_do_operador(self):
		request = self.factory.get("/app/permissao/usuario/")
		request.sisvar_extra = {}
		request.user = self.operador

		response = permissao_usuario_view(request)

		self.assertEqual(response.status_code, 200)
		others = request.sisvar_extra["others"]
		self.assertEqual(len(others["usuarios_ativos"]), 1)
		self.assertEqual(others["usuarios_ativos"][0]["id"], self.usuario_alvo.id)
		self.assertEqual(len(others["grupos_cadastrados"]), 2)
		self.assertEqual(others["grupos_gerenciaveis_ids"], [self.grupo_a.id])
		self.assertEqual(
			sorted(others["permissoes_gerenciaveis"]),
			["auth.view_group", "usuario.change_usuarios", "usuario.view_usuarios"],
		)
		self.assertEqual(others["permissoes"]["permissao_usuario"], {
			"acessar": True,
			"consultar": True,
			"editar": True,
		})

	def test_get_sem_view_usuario_levanta_permission_denied(self):
		request = self.factory.get("/app/permissao/usuario/")
		request.sisvar_extra = {}
		request.user = User.objects.create_user(username="semview", password="12345678")

		with self.assertRaises(PermissionDenied):
			permissao_usuario_view(request)

	def test_post_rejeita_atribuicao_fora_do_escopo_do_operador(self):
		payload = {
			"form": {
				"cadPermissaoUsuario": {
					"estado": "editar",
					"campos": {
						"usuario_id": self.usuario_alvo.id,
						"grupos": [self.grupo_b.id],
						"permissoes": ["auth.change_group"],
					}
				}
			}
		}

		request = self.build_request("/app/permissao/usuario/", payload)
		response = permissao_usuario_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 403)
		self.assertIn("só pode atribuir grupos", data["mensagens"]["erro"]["conteudo"][0])

	def test_post_rejeita_sem_change_usuarios(self):
		self.operador.user_permissions.set([self.perm_view_group, self.perm_view_usuario])
		payload = {
			"form": {
				"cadPermissaoUsuario": {
					"estado": "editar",
					"campos": {
						"usuario_id": self.usuario_alvo.id,
						"grupos": [self.grupo_a.id],
						"permissoes": ["auth.view_group"],
					}
				}
			}
		}

		request = self.build_request("/app/permissao/usuario/", payload)
		response = permissao_usuario_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 403)
		self.assertIn("alterar permissões de usuários", data["mensagens"]["erro"]["conteudo"][0])

	def test_post_preserva_vinculos_fora_do_escopo_e_atualiza_os_gerenciaveis(self):
		self.usuario_alvo.groups.set([self.grupo_b])
		self.usuario_alvo.user_permissions.set([self.perm_change_group])

		payload = {
			"form": {
				"cadPermissaoUsuario": {
					"estado": "editar",
					"campos": {
						"usuario_id": self.usuario_alvo.id,
						"grupos": [self.grupo_a.id],
						"permissoes": ["auth.view_group"],
					}
				}
			}
		}

		request = self.build_request("/app/permissao/usuario/", payload)
		response = permissao_usuario_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(data["success"])
		self.assertTrue(AuditEvent.objects.filter(action="permission_assign").exists())

		self.usuario_alvo.refresh_from_db()
		self.assertEqual(
			list(self.usuario_alvo.groups.order_by("name").values_list("id", flat=True)),
			[self.grupo_a.id, self.grupo_b.id],
		)
		self.assertEqual(
			sorted(self.usuario_alvo.user_permissions.values_list("codename", flat=True)),
			["change_group", "view_group"],
		)
		self.assertEqual(
			sorted(data["form"]["cadPermissaoUsuario"]["campos"]["permissoes"]),
			["auth.change_group", "auth.view_group"],
		)

	def test_post_rejeita_autoatribuicao_por_payload(self):
		payload = {
			"form": {
				"cadPermissaoUsuario": {
					"estado": "editar",
					"campos": {
						"usuario_id": self.operador.id,
						"grupos": [self.grupo_a.id],
						"permissoes": ["auth.view_group"],
					}
				}
			}
		}

		request = self.build_request("/app/permissao/usuario/", payload)
		response = permissao_usuario_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 404)
		self.assertEqual(data["mensagens"]["erro"]["conteudo"], ["Usuário elegível não encontrado"])

	def test_consulta_lista_apenas_usuarios_elegiveis(self):
		payload = {
			"form": {
				"consPermissaoUsuario": {
					"campos": {
						"first_name_cons": "",
						"username_cons": "",
						"id_selecionado": None,
					}
				}
			}
		}

		request = self.build_request("/app/permissao/usuario/cons", payload)
		response = permissao_usuario_cons_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(data["registros"]), 1)
		self.assertEqual(data["registros"][0]["id"], self.usuario_alvo.id)

	def test_consulta_sem_view_usuario_levanta_permission_denied(self):
		payload = {
			"form": {
				"consPermissaoUsuario": {
					"campos": {
						"first_name_cons": "",
						"username_cons": "",
						"id_selecionado": None,
					}
				}
			}
		}
		request = self.build_request(
			"/app/permissao/usuario/cons",
			payload,
			user=User.objects.create_user(username="semconsulta", password="12345678"),
		)

		with self.assertRaises(PermissionDenied):
			permissao_usuario_cons_view(request)

	def test_consulta_carrega_grupos_e_permissoes_do_usuario(self):
		self.usuario_alvo.groups.set([self.grupo_b])
		self.usuario_alvo.user_permissions.set([self.perm_change_group, self.perm_view_group])

		payload_cons = {
			"form": {
				"consPermissaoUsuario": {
					"campos": {
						"first_name_cons": "",
						"username_cons": "",
						"id_selecionado": self.usuario_alvo.id,
					}
				}
			}
		}

		request = self.build_request("/app/permissao/usuario/cons", payload_cons)
		response = permissao_usuario_cons_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(data["form"]["cadPermissaoUsuario"]["campos"]["usuario_id"], self.usuario_alvo.id)
		self.assertEqual(data["form"]["cadPermissaoUsuario"]["campos"]["grupos"], [self.grupo_b.id])
		self.assertEqual(
			sorted(data["form"]["cadPermissaoUsuario"]["campos"]["permissoes"]),
			["auth.change_group", "auth.view_group"],
		)

	def test_consulta_nao_carrega_superusuario_como_alvo(self):
		payload = {
			"form": {
				"consPermissaoUsuario": {
					"campos": {
						"first_name_cons": "",
						"username_cons": "",
						"id_selecionado": self.superusuario.id,
					}
				}
			}
		}

		request = self.build_request("/app/permissao/usuario/cons", payload)
		response = permissao_usuario_cons_view(request)
		data = json.loads(response.content)

		self.assertEqual(response.status_code, 404)
		self.assertEqual(data["mensagens"]["erro"]["conteudo"], ["Usuário elegível não encontrado"])

