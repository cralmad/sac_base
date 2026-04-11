import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from pages.filial.models import Filial, UsuarioFilial
from pages.filial.services import ACTIVE_FILIAL_COOKIE


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
