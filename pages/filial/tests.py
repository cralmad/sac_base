import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.test import Client, TestCase

from pages.core.models import Pais
from pages.filial.models import Filial, UsuarioFilial
from pages.filial.services import ACTIVE_FILIAL_COOKIE
from pages.filial.views import cadastro_filial_cons_view, cadastro_filial_del_view, cadastro_filial_view


User = get_user_model()


class FilialFlowTests(TestCase):
    def setUp(self):
        self.client = Client()

    def criar_usuario(self, username, **kwargs):
        return User.objects.create_user(username=username, password="teste123", **kwargs)

    def login_json(self, username, password="teste123"):
        return self.client.post(
            "/app/usuario/login/",
            data=json.dumps({
                "form": {
                    "loginForm": {
                        "campos": {
                            "username": username,
                            "password": password,
                        }
                    }
                }
            }),
            content_type="application/json",
        )

    def test_login_sem_filial_redireciona_para_tela_sem_acesso(self):
        self.criar_usuario("semfilial")

        response = self.login_json("semfilial")
        data = json.loads(response.content)

        self.assertTrue(data["success"])
        self.assertEqual(data["redirect"], "/app/usuario/filial/sem-acesso/")
        self.assertNotIn(ACTIVE_FILIAL_COOKIE, response.cookies)

    def test_login_com_uma_filial_ativa_cookie_automaticamente(self):
        usuario = self.criar_usuario("umafilial")
        filial = Filial.objects.create(codigo="MAT", nome="MATRIZ", is_matriz=True)
        UsuarioFilial.objects.create(usuario=usuario, filial=filial, pode_consultar=True, pode_escrever=True)

        response = self.login_json("umafilial")
        data = json.loads(response.content)

        self.assertEqual(data["redirect"], "/app/home/")
        self.assertEqual(response.cookies[ACTIVE_FILIAL_COOKIE].value, str(filial.id))

    def test_login_com_multiplas_filiais_exige_selecao(self):
        usuario = self.criar_usuario("duasfiliais")
        matriz = Filial.objects.create(codigo="MAT", nome="MATRIZ", is_matriz=True)
        filial = Filial.objects.create(codigo="FIL1", nome="FILIAL 1", is_matriz=False)
        UsuarioFilial.objects.create(usuario=usuario, filial=matriz, pode_consultar=True)
        UsuarioFilial.objects.create(usuario=usuario, filial=filial, pode_consultar=True)

        response = self.login_json("duasfiliais")
        data = json.loads(response.content)

        self.assertEqual(data["redirect"], "/app/usuario/filial/selecionar/")
        self.assertNotIn(ACTIVE_FILIAL_COOKIE, response.cookies)

    def test_superusuario_tem_todas_as_filiais_permitidas(self):
        User.objects.create_superuser(username="root", password="teste123", email="root@example.com")
        Filial.objects.create(codigo="MAT", nome="MATRIZ", is_matriz=True)
        Filial.objects.create(codigo="FIL1", nome="FILIAL 1", is_matriz=False)

        response = self.login_json("root")
        data = json.loads(response.content)

        self.assertEqual(data["redirect"], "/app/usuario/filial/selecionar/")

    def test_selecao_de_filial_define_cookie(self):
        usuario = self.criar_usuario("selecionador")
        matriz = Filial.objects.create(codigo="MAT", nome="MATRIZ", is_matriz=True)
        filial = Filial.objects.create(codigo="FIL1", nome="FILIAL 1", is_matriz=False)
        UsuarioFilial.objects.create(usuario=usuario, filial=matriz, pode_consultar=True)
        UsuarioFilial.objects.create(usuario=usuario, filial=filial, pode_consultar=True)

        self.login_json("selecionador")
        response = self.client.post(
            "/app/usuario/filial/ativar/",
            data=json.dumps({
                "form": {
                    "selecionarFilialForm": {
                        "campos": {"filial_id": filial.id}
                    }
                }
            }),
            content_type="application/json",
        )
        data = json.loads(response.content)

        self.assertTrue(data["success"])
        self.assertEqual(data["redirect"], "/app/home/")
        self.assertEqual(response.cookies[ACTIVE_FILIAL_COOKIE].value, str(filial.id))

    def test_home_redireciona_para_selecao_quando_usuario_tem_multiplas_filiais_sem_contexto(self):
        usuario = self.criar_usuario("multihome")
        matriz = Filial.objects.create(codigo="MAT", nome="MATRIZ", is_matriz=True)
        filial = Filial.objects.create(codigo="FIL1", nome="FILIAL 1", is_matriz=False)
        UsuarioFilial.objects.create(usuario=usuario, filial=matriz, pode_consultar=True)
        UsuarioFilial.objects.create(usuario=usuario, filial=filial, pode_consultar=True)

        self.login_json("multihome")
        response = self.client.get("/app/home/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/app/usuario/filial/selecionar/")

    def test_rota_de_selecao_nao_permite_troca_quando_filial_ja_esta_ativa(self):
        usuario = self.criar_usuario("semtroca")
        matriz = Filial.objects.create(codigo="MAT", nome="MATRIZ", is_matriz=True)
        UsuarioFilial.objects.create(usuario=usuario, filial=matriz, pode_consultar=True)

        self.login_json("semtroca")
        response = self.client.get("/app/usuario/filial/selecionar/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/app/home/")


class CadastroFilialPermissaoTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.pais_pt = Pais.objects.create(nome='PORTUGAL', sigla='PRT', codigo_tel='+351')
        self.pais_br = Pais.objects.create(nome='BRASIL', sigla='BRA', codigo_tel='+55')
        self.perm_view = Permission.objects.get(content_type__app_label='filial', codename='view_filial')
        self.perm_add = Permission.objects.get(content_type__app_label='filial', codename='add_filial')
        self.perm_change = Permission.objects.get(content_type__app_label='filial', codename='change_filial')
        self.perm_delete = Permission.objects.get(content_type__app_label='filial', codename='delete_filial')

    def criar_usuario(self, username, permissoes=None, **kwargs):
        usuario = User.objects.create_user(username=username, password='teste123', **kwargs)
        if permissoes:
            usuario.user_permissions.set(permissoes)
        return usuario

    def build_get_request(self, path, user):
        request = self.factory.get(path)
        request.sisvar_extra = {}
        request.user = user
        request.filial_ativa = Filial.objects.first()
        return request

    def build_post_request(self, path, payload, user):
        request = self.factory.post(path, data=json.dumps(payload), content_type='application/json')
        request.sisvar_front = payload
        request.user = user
        request.filial_ativa = Filial.objects.first()
        return request

    def payload_filial(self, estado='novo', filial_id=None, codigo='FIL01', nome='FILIAL 01', pais_endereco_id=None, pais_atuacao_id=None, is_matriz=False, ativa=True):
        return {
            'form': {
                'cadFilial': {
                    'estado': estado,
                    'campos': {
                        'id': filial_id,
                        'codigo': codigo,
                        'nome': nome,
                        'pais_endereco_id': pais_endereco_id or self.pais_pt.id,
                        'pais_atuacao_id': pais_atuacao_id or self.pais_pt.id,
                        'is_matriz': is_matriz,
                        'ativa': ativa,
                    }
                }
            }
        }

    def test_get_sem_permissao_view_levanta_permission_denied(self):
        usuario = self.criar_usuario('semview')
        request = self.build_get_request('/app/filial/cadastro/', usuario)

        with self.assertRaises(PermissionDenied):
            cadastro_filial_view(request)

    def test_get_sem_inclusao_inicializa_em_visualizar(self):
        Filial.objects.create(codigo='MAT', nome='MATRIZ', pais_endereco=self.pais_pt, pais_atuacao=self.pais_pt, is_matriz=True)
        usuario = self.criar_usuario('viewer', [self.perm_view])
        request = self.build_get_request('/app/filial/cadastro/', usuario)

        response = cadastro_filial_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.sisvar_extra['form']['cadFilial']['estado'], 'visualizar')
        self.assertEqual(request.sisvar_extra['others']['permissoes']['filial'], {
            'acessar': True,
            'consultar': True,
            'incluir': False,
            'editar': False,
            'excluir': False,
        })
        self.assertEqual(len(request.sisvar_extra['others']['paises_cadastrados']), 2)

    def test_post_novo_com_add_salva_filial(self):
        Filial.objects.create(codigo='MAT', nome='MATRIZ', pais_endereco=self.pais_pt, pais_atuacao=self.pais_pt, is_matriz=True)
        usuario = self.criar_usuario('comadd', [self.perm_view, self.perm_add])
        request = self.build_post_request('/app/filial/cadastro/', self.payload_filial(), usuario)

        response = cadastro_filial_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertTrue(Filial.objects.filter(codigo='FIL01').exists())
        self.assertEqual(Filial.objects.get(codigo='FIL01').pais_atuacao, self.pais_pt)

    def test_post_novo_rejeita_pais_de_atuacao_invalido(self):
        Filial.objects.create(codigo='MAT', nome='MATRIZ', pais_endereco=self.pais_pt, pais_atuacao=self.pais_pt, is_matriz=True)
        usuario = self.criar_usuario('comadd', [self.perm_view, self.perm_add])
        request = self.build_post_request('/app/filial/cadastro/', self.payload_filial(pais_atuacao_id=999999), usuario)

        response = cadastro_filial_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 422)
        self.assertIn('País de atuação inválido', data['mensagens']['erro']['conteudo'][0])

    def test_primeiro_cadastro_exige_matriz(self):
        usuario = self.criar_usuario('comadd', [self.perm_view, self.perm_add])
        request = self.build_post_request('/app/filial/cadastro/', self.payload_filial(is_matriz=False), usuario)

        response = cadastro_filial_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 422)
        self.assertIn('primeiro cadastro', data['mensagens']['erro']['conteudo'][0].lower())

    def test_consulta_exige_permissao_view(self):
        usuario = self.criar_usuario('semconsulta')
        payload = {'form': {'consFilial': {'campos': {'codigo_cons': '', 'nome_cons': '', 'id_selecionado': None}}}}
        request = self.build_post_request('/app/filial/cadastro/cons', payload, usuario)

        with self.assertRaises(PermissionDenied):
            cadastro_filial_cons_view(request)

    def test_delete_exige_permissao_delete(self):
        matriz = Filial.objects.create(codigo='MAT', nome='MATRIZ', pais_endereco=self.pais_pt, pais_atuacao=self.pais_pt, is_matriz=True)
        filial = Filial.objects.create(codigo='FIL01', nome='FILIAL 01', pais_endereco=self.pais_pt, pais_atuacao=self.pais_br, is_matriz=False)
        usuario = self.criar_usuario('semdelete', [self.perm_view])
        request = self.build_post_request('/app/filial/cadastro/del', self.payload_filial(filial_id=filial.id), usuario)

        response = cadastro_filial_del_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 403)
        self.assertIn('excluir matriz/filial', data['mensagens']['erro']['conteudo'][0].lower())

    def test_delete_bloqueia_exclusao_da_unica_unidade(self):
        matriz = Filial.objects.create(codigo='MAT', nome='MATRIZ', pais_endereco=self.pais_pt, pais_atuacao=self.pais_pt, is_matriz=True)
        usuario = self.criar_usuario('comdelete', [self.perm_view, self.perm_delete])
        request = self.build_post_request('/app/filial/cadastro/del', self.payload_filial(filial_id=matriz.id), usuario)

        response = cadastro_filial_del_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 409)
        self.assertIn('única matriz/filial', data['mensagens']['erro']['conteudo'][0].lower())

    def test_delete_filial_sem_vinculos_exclui(self):
        Filial.objects.create(codigo='MAT', nome='MATRIZ', pais_endereco=self.pais_pt, pais_atuacao=self.pais_pt, is_matriz=True)
        filial = Filial.objects.create(codigo='FIL01', nome='FILIAL 01', pais_endereco=self.pais_pt, pais_atuacao=self.pais_br, is_matriz=False)
        usuario = self.criar_usuario('comdelete', [self.perm_view, self.perm_delete])
        request = self.build_post_request('/app/filial/cadastro/del', self.payload_filial(filial_id=filial.id), usuario)

        response = cadastro_filial_del_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertFalse(Filial.objects.filter(id=filial.id).exists())
