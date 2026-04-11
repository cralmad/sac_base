import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from pages.auditoria.models import AuditEvent
from .views import auditoria_cons_view, auditoria_view

User = get_user_model()


class AuditoriaViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.operador = User.objects.create_user(
            username="auditor",
            password="12345678",
            first_name="Auditor",
            is_active=True,
        )
        self.outro_usuario = User.objects.create_user(
            username="executante",
            password="12345678",
            first_name="Executante",
            is_active=True,
        )
        self.perm_acesso_auditoria = Permission.objects.get(
            content_type__app_label="auditoria",
            codename="acessar_consulta_auditoria",
        )
        self.content_type_usuario = ContentType.objects.get(app_label="usuario", model="usuarios")

    def build_get_request(self, path, user=None):
        request = self.factory.get(path)
        request.sisvar_extra = {}
        request.user = user or self.operador
        return request

    def build_post_request(self, path, payload, user=None):
        request = self.factory.post(
            path,
            data=json.dumps(payload),
            content_type="application/json",
        )
        request.sisvar_front = payload
        request.user = user or self.operador
        return request

    def criar_evento(self, *, actor=None, action="update", object_id="10", changed_fields=None, extra_data=None):
        return AuditEvent.objects.create(
            actor=actor,
            action=action,
            content_type=self.content_type_usuario,
            object_id=object_id,
            object_repr=f"USUARIO {object_id}",
            changed_fields=changed_fields or {"email": {"old": "a@a.com", "new": "b@b.com"}},
            extra_data=extra_data or {},
        )

    def test_get_sem_permissao_levanta_permission_denied(self):
        request = self.build_get_request("/app/auditoria/consulta/")

        with self.assertRaises(PermissionDenied):
            auditoria_view(request)

    def test_get_com_permissao_injeta_schema_e_opcoes(self):
        self.operador.user_permissions.set([self.perm_acesso_auditoria])
        self.criar_evento(actor=self.outro_usuario, action=AuditEvent.ACTION_UPDATE)
        request = self.build_get_request("/app/auditoria/consulta/")

        response = auditoria_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("schema", request.sisvar_extra)
        self.assertIn("auditoria", request.sisvar_extra["others"])
        self.assertEqual(request.sisvar_extra["others"]["permissoes"]["auditoria"]["consultar"], True)
        self.assertEqual(request.sisvar_extra["others"]["auditoria"]["paginacao"]["page"], 1)
        conteudo = response.content.decode("utf-8")
        self.assertIn('id="consAuditoria"', conteudo)
        self.assertIn('id="tabela-auditoria-corpo"', conteudo)
        self.assertIn('id="btn-pagina-anterior"', conteudo)

    def test_consulta_sem_permissao_levanta_permission_denied(self):
        payload = {"form": {"consAuditoria": {"campos": {}}}}
        request = self.build_post_request("/app/auditoria/consulta/cons", payload)

        with self.assertRaises(PermissionDenied):
            auditoria_cons_view(request)

    def test_consulta_filtra_por_acao_e_usuario(self):
        self.operador.user_permissions.set([self.perm_acesso_auditoria])
        self.criar_evento(actor=self.outro_usuario, action=AuditEvent.ACTION_CREATE, object_id="11")
        self.criar_evento(actor=self.outro_usuario, action=AuditEvent.ACTION_UPDATE, object_id="12")
        self.criar_evento(actor=self.operador, action=AuditEvent.ACTION_CREATE, object_id="13")

        payload = {
            "form": {
                "consAuditoria": {
                    "campos": {
                        "actor_id": self.outro_usuario.id,
                        "action": AuditEvent.ACTION_CREATE,
                        "app_label": "",
                        "model": "",
                        "object_id": "",
                        "data_inicio": "",
                        "data_fim": "",
                    }
                }
            }
        }
        request = self.build_post_request("/app/auditoria/consulta/cons", payload)

        response = auditoria_cons_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(len(data["others"]["auditoria"]["registros"]), 1)
        self.assertEqual(data["others"]["auditoria"]["registros"][0]["object_id"], "11")

    def test_consulta_rejeita_data_invalida(self):
        self.operador.user_permissions.set([self.perm_acesso_auditoria])
        payload = {
            "form": {
                "consAuditoria": {
                    "campos": {
                        "actor_id": None,
                        "action": "",
                        "app_label": "",
                        "model": "",
                        "object_id": "",
                        "data_inicio": "2026-99-01",
                        "data_fim": "",
                    }
                }
            }
        }
        request = self.build_post_request("/app/auditoria/consulta/cons", payload)

        response = auditoria_cons_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 422)
        self.assertIn("Data inválida", data["mensagens"]["erro"]["conteudo"][0])

    def test_consulta_retorna_metadados_de_paginacao(self):
        self.operador.user_permissions.set([self.perm_acesso_auditoria])
        for indice in range(25):
            self.criar_evento(actor=self.outro_usuario, action=AuditEvent.ACTION_UPDATE, object_id=str(indice + 1))

        payload = {
            "form": {
                "consAuditoria": {
                    "campos": {
                        "actor_id": None,
                        "action": "",
                        "app_label": "",
                        "model": "",
                        "object_id": "",
                        "data_inicio": "",
                        "data_fim": "",
                        "page": 2,
                        "per_page": 10,
                    }
                }
            }
        }
        request = self.build_post_request("/app/auditoria/consulta/cons", payload)

        response = auditoria_cons_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data["others"]["auditoria"]["registros"]), 10)
        self.assertEqual(data["others"]["auditoria"]["paginacao"]["page"], 2)
        self.assertEqual(data["others"]["auditoria"]["paginacao"]["total_paginas"], 3)
        self.assertEqual(data["others"]["auditoria"]["paginacao"]["total_registros"], 25)
        self.assertTrue(data["others"]["auditoria"]["paginacao"]["has_previous"])
        self.assertTrue(data["others"]["auditoria"]["paginacao"]["has_next"])