from django.test import SimpleTestCase

from sac_base.sisvar_builders import (
    build_error_payload,
    build_form_response,
    build_form_state,
    build_forms_response,
    build_legacy_others,
    build_message_entry,
    build_messages,
    build_meta,
    build_records_response,
    build_sisvar_payload,
    build_sisvar_response,
    build_success_payload,
)


class SisvarBuildersTests(SimpleTestCase):
    def test_build_meta_and_legacy_others_keep_compatibility_shape(self):
        meta = build_meta(
            security={"csrfTokenValue": "abc123"},
            permissions={"usuario": {"acessar": True}},
            options={"grupos": [{"id": 1, "nome": "PADRAO"}]},
            datasets={"usuarios_ativos": [{"id": 9, "nome": "Operador"}]},
        )

        others = build_legacy_others(meta)

        self.assertEqual(others["csrf_token_value"], "abc123")
        self.assertEqual(others["permissoes"], {"usuario": {"acessar": True}})
        self.assertEqual(others["opcoes"], {"grupos": [{"id": 1, "nome": "PADRAO"}]})
        self.assertEqual(others["usuarios_ativos"], [{"id": 9, "nome": "Operador"}])

    def test_build_sisvar_payload_includes_meta_and_compatibility_others(self):
        payload = build_sisvar_payload(
            schema={"cadUsuario": {"username": {"type": "string"}}},
            forms={"cadUsuario": build_form_state(campos={"username": "joao"})},
            mensagens=build_messages(info="Carregado"),
            permissions={"usuario": {"consultar": True}},
            options={"grupos": []},
            datasets={"usuarios_ativos": []},
        )

        self.assertIn("meta", payload)
        self.assertIn("others", payload)
        self.assertEqual(payload["meta"]["permissions"]["usuario"]["consultar"], True)
        self.assertEqual(payload["others"]["permissoes"]["usuario"]["consultar"], True)
        self.assertEqual(payload["others"]["opcoes"]["grupos"], [])
        self.assertEqual(payload["others"]["usuarios_ativos"], [])

    def test_build_message_entry_normalizes_string_and_list(self):
        self.assertEqual(
            build_message_entry("Falha", ignorar=False),
            {"conteudo": ["Falha"], "ignorar": False},
        )
        self.assertEqual(
            build_message_entry(["A", "B"]),
            {"conteudo": ["A", "B"], "ignorar": True},
        )

    def test_build_form_response_serializes_single_form(self):
        payload = build_form_response(
            form_id="cadCliente",
            estado="visualizar",
            update="2026-04-10T10:00:00",
            campos={"id": 1, "nome": "CLIENTE"},
            mensagem_sucesso="Registro salvo com sucesso!",
        )

        self.assertTrue(payload["success"])
        self.assertEqual(payload["form"]["cadCliente"]["estado"], "visualizar")
        self.assertEqual(payload["form"]["cadCliente"]["campos"]["nome"], "CLIENTE")
        self.assertEqual(
            payload["mensagens"]["sucesso"]["conteudo"],
            ["Registro salvo com sucesso!"],
        )

    def test_build_forms_response_accepts_prebuilt_forms(self):
        payload = build_forms_response(
            forms={
                "cadPermissaoUsuario": {
                    "estado": "visualizar",
                    "update": None,
                    "campos": {"usuario_id": 7},
                }
            },
            mensagem_sucesso="Atualizado com sucesso!",
        )

        self.assertTrue(payload["success"])
        self.assertEqual(payload["form"]["cadPermissaoUsuario"]["campos"]["usuario_id"], 7)
        self.assertEqual(payload["mensagens"]["sucesso"]["conteudo"], ["Atualizado com sucesso!"])

    def test_build_records_response_and_success_payload_allow_extra_data(self):
        records_payload = build_records_response(
            [{"id": 1}, {"id": 2}],
            extra_payload={"paginacao": {"page": 1, "total_paginas": 3}},
        )
        success_payload = build_success_payload(
            "Excluído com sucesso!",
            extra_payload={"redirect": "/app/home/"},
        )

        self.assertEqual(len(records_payload["registros"]), 2)
        self.assertEqual(records_payload["paginacao"]["total_paginas"], 3)
        self.assertEqual(success_payload["mensagens"]["sucesso"]["conteudo"], ["Excluído com sucesso!"])
        self.assertEqual(success_payload["redirect"], "/app/home/")

    def test_build_error_payload_marks_request_as_unsuccessful(self):
        payload = build_error_payload(["Erro A", "Erro B"])

        self.assertFalse(payload["success"])
        self.assertEqual(payload["mensagens"]["erro"]["conteudo"], ["Erro A", "Erro B"])
        self.assertFalse(payload["mensagens"]["erro"]["ignorar"])

    def test_build_sisvar_response_wraps_payload_with_success_flag(self):
        payload = build_sisvar_response(
            datasets={"auditoria": {"registros": [], "paginacao": {"page": 1}}},
            mensagens=build_messages(info="Consulta pronta"),
        )

        self.assertTrue(payload["success"])
        self.assertEqual(payload["meta"]["datasets"]["auditoria"]["paginacao"]["page"], 1)
        self.assertEqual(payload["mensagens"]["info"]["conteudo"], ["Consulta pronta"])