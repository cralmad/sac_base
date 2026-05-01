import io
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.utils import timezone

from pages.cad_cliente.models import Cliente
from pages.cad_grupo_cli.models import GrupoCli
from pages.core.models import Pais
from pages.filial.models import Filial, UsuarioFilial
from pages.motorista.models import Motorista

from .models import Pedido, TentativaEntrega
from .services.importador_csv import importar_csv
from .services.normalizacao import normalizar_estado
from .views import pedidos_importar_view, pedidos_view

User = get_user_model()

CSV_HEADER = (
    '"Data criação";"Data actualização";"*Tipo (delivery|pickup)";"Id";'
    '"Referência";"*Data";"Data entrega";"Estado";"Embalagens";'
    '"*Nome destinatário";"Email destinatário";"Telefone destinatário";'
    '"Telefone destinatário 2";"*Rua entrega";"*Código postal entrega";'
    '"*Cidade entrega";"Comentários";"Nome cliente";"Nome utilizador condutor";"Peso"\n'
)


def _csv_row(**kwargs):
    defaults = {
        "criacao": "2026-04-10 10:00:00",
        "atualizacao": "2026-04-11 12:00:00",
        "tipo": "delivery",
        "id": "1001",
        "referencia": "REF001",
        "data": "2026-04-13",
        "dt_entrega": "",
        "estado": "created",
        "embalagens": "1",
        "nome_dest": "João Silva",
        "email": "joao@email.com",
        "tel": "+351910000001",
        "tel2": "",
        "rua": "Rua X",
        "codpost": "1000-001",
        "cidade": "Lisboa",
        "obs": "",
        "cliente": "LEROY MERLIN",
        "motorista": "JOAO_MOT",
        "peso": "10,500",
    }
    defaults.update(kwargs)
    return (
        f'"{defaults["criacao"]}";"{defaults["atualizacao"]}";"{defaults["tipo"]}";'
        f'"{defaults["id"]}";"{defaults["referencia"]}";"{defaults["data"]}";'
        f'"{defaults["dt_entrega"]}";"{defaults["estado"]}";"{defaults["embalagens"]}";'
        f'"{defaults["nome_dest"]}";"{defaults["email"]}";"{defaults["tel"]}";'
        f'"{defaults["tel2"]}";"{defaults["rua"]}";"{defaults["codpost"]}";'
        f'"{defaults["cidade"]}";"{defaults["obs"]}";"{defaults["cliente"]}";'
        f'"{defaults["motorista"]}";"{defaults["peso"]}"\n'
    )


def _make_csv(*rows):
    return (CSV_HEADER + "".join(rows)).encode("utf-8")


class NormalizacaoEstadoTests(TestCase):
    def test_cancelled_e_estado_proprio(self):
        self.assertEqual(normalizar_estado("cancelled"), "cancelled")

    def test_A_e_estado_proprio(self):
        self.assertEqual(normalizar_estado("A"), "A")

    def test_cancelled_diferente_de_A(self):
        self.assertNotEqual(normalizar_estado("cancelled"), normalizar_estado("A"))

    def test_alias_acento(self):
        self.assertEqual(normalizar_estado("danos_visíveis_embalagem"), "danos_visiveis_embalagem")

    def test_desconhecido_retorna_UNKNOWN(self):
        self.assertEqual(normalizar_estado("valor_nao_existe"), "UNKNOWN")

    def test_vazio_retorna_UNKNOWN(self):
        self.assertEqual(normalizar_estado(""), "UNKNOWN")

    def test_none_retorna_UNKNOWN(self):
        self.assertEqual(normalizar_estado(None), "UNKNOWN")

    def test_estados_canonicos(self):
        for estado in ("created", "assigned", "completed", "EA", "reschedule_client", "returned_to_sender"):
            with self.subTest(estado=estado):
                self.assertEqual(normalizar_estado(estado), estado)


class ImportadorCSVTests(TestCase):
    def setUp(self):
        self.pais = Pais.objects.create(nome="PORTUGAL", sigla="PRT", codigo_tel="+351")
        self.filial = Filial.objects.create(
            codigo="MAT", nome="MATRIZ", pais_atuacao=self.pais, is_matriz=True
        )
        self.grupo = GrupoCli.objects.create(descricao="GRP1")
        self.cliente = Cliente.objects.create(
            codigo="LEROY",
            nome="LEROY MERLIN",
            rsocial="LEROY MERLIN SA",
            grupo=self.grupo,
            pais=self.pais,
        )
        self.motorista = Motorista.objects.create(
            filial=self.filial,
            codigo="JOAO_MOT",
            nome="JOÃO MOTORISTA",
            telefone="+351900000001",
        )

    def test_importa_novo_pedido(self):
        csv_bytes = _make_csv(_csv_row())
        resultado = importar_csv(csv_bytes, self.filial, "test.csv")
        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["stats"]["criados"], 1)
        self.assertEqual(Pedido.objects.count(), 1)

    def test_novo_pedido_cria_tentativa(self):
        csv_bytes = _make_csv(_csv_row())
        importar_csv(csv_bytes, self.filial, "test.csv")
        self.assertEqual(TentativaEntrega.objects.count(), 1)
        t = TentativaEntrega.objects.first()
        self.assertEqual(t.data_tentativa, date(2026, 4, 13))
        self.assertEqual(t.estado, "created")
        self.assertEqual(t.periodo, "TARDE")

    def test_deduplicacao_por_id_vonzu(self):
        # Same id_vonzu twice in file — only first is imported
        csv_bytes = _make_csv(
            _csv_row(id="2001"),
            _csv_row(id="2001", referencia="REF_DUP"),
        )
        resultado = importar_csv(csv_bytes, self.filial, "test.csv")
        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["stats"]["criados"], 1)
        self.assertEqual(resultado["stats"]["ignoradas"], 1)
        self.assertEqual(Pedido.objects.count(), 1)

    def test_upsert_pedido_existente_sem_alteracao(self):
        csv_bytes = _make_csv(_csv_row())
        importar_csv(csv_bytes, self.filial, "test.csv")
        # Import the same file again — nothing should change
        resultado = importar_csv(csv_bytes, self.filial, "test.csv")
        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["stats"]["sem_alteracao"], 1)
        self.assertEqual(resultado["stats"]["atualizados"], 0)
        self.assertEqual(Pedido.objects.count(), 1)

    def test_upsert_atualiza_quando_atualizacao_muda(self):
        csv_bytes = _make_csv(_csv_row())
        importar_csv(csv_bytes, self.filial, "test.csv")
        # Same id_vonzu, newer atualizacao
        csv_bytes2 = _make_csv(_csv_row(atualizacao="2026-04-12 09:00:00", estado="completed"))
        resultado = importar_csv(csv_bytes2, self.filial, "test.csv")
        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["stats"]["atualizados"], 1)
        p = Pedido.objects.get(id_vonzu=1001)
        self.assertEqual(p.estado, "completed")

    def test_nao_cria_tentativa_ao_mudar_estado(self):
        csv_bytes = _make_csv(_csv_row())
        importar_csv(csv_bytes, self.filial, "test.csv")
        self.assertEqual(TentativaEntrega.objects.count(), 1)
        # Update with new atualizacao but same prev_entrega (*Data) — no new tentativa
        csv_bytes2 = _make_csv(_csv_row(atualizacao="2026-04-12 09:00:00", estado="completed"))
        importar_csv(csv_bytes2, self.filial, "test.csv")
        self.assertEqual(TentativaEntrega.objects.count(), 1)
        tentativa = TentativaEntrega.objects.first()
        self.assertEqual(tentativa.estado, "completed")

    def test_cria_tentativa_ao_mudar_prev_entrega(self):
        csv_bytes = _make_csv(_csv_row())
        importar_csv(csv_bytes, self.filial, "test.csv")
        self.assertEqual(TentativaEntrega.objects.count(), 1)
        # New atualizacao AND new *Data → creates new tentativa
        csv_bytes2 = _make_csv(
            _csv_row(atualizacao="2026-04-12 09:00:00", data="2026-04-15")
        )
        resultado = importar_csv(csv_bytes2, self.filial, "test.csv")
        self.assertTrue(resultado["sucesso"])
        self.assertEqual(TentativaEntrega.objects.count(), 2)
        self.assertEqual(resultado["stats"]["tentativas"], 1)
        t_nova = TentativaEntrega.objects.get(data_tentativa=date(2026, 4, 15))
        self.assertEqual(t_nova.periodo, "TARDE")

    def test_atualiza_estado_mov_existente_na_data_prev_entrega(self):
        csv_bytes = _make_csv(_csv_row())
        importar_csv(csv_bytes, self.filial, "test.csv")

        pedido = Pedido.objects.get(id_vonzu=1001)
        TentativaEntrega.objects.create(
            pedido=pedido,
            data_tentativa=date(2026, 4, 15),
            estado="assigned",
        )

        csv_bytes2 = _make_csv(_csv_row(atualizacao="2026-04-12 09:00:00", data="2026-04-15", estado="completed"))
        resultado = importar_csv(csv_bytes2, self.filial, "test.csv")

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(TentativaEntrega.objects.filter(data_tentativa=date(2026, 4, 15)).count(), 1)
        tentativa = TentativaEntrega.objects.get(pedido=pedido, data_tentativa=date(2026, 4, 15))
        self.assertEqual(tentativa.estado, "completed")

    def test_fk_cliente_resolvida_por_codigo(self):
        csv_bytes = _make_csv(_csv_row(cliente="LEROY"))
        importar_csv(csv_bytes, self.filial, "test.csv")
        p = Pedido.objects.first()
        self.assertEqual(p.cliente_id, self.cliente.id)

    def test_fk_motorista_resolvida_por_codigo(self):
        csv_bytes = _make_csv(_csv_row(motorista="JOAO_MOT"))
        importar_csv(csv_bytes, self.filial, "test.csv")
        p = Pedido.objects.first()
        self.assertEqual(p.motorista_id, self.motorista.id)

    def test_fk_nao_resolvida_salva_como_null_e_gera_aviso(self):
        csv_bytes = _make_csv(_csv_row(cliente="NAOEXISTE", motorista="NAOEXISTE"))
        resultado = importar_csv(csv_bytes, self.filial, "test.csv")
        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["stats"]["avisos_fk"], 2)
        p = Pedido.objects.first()
        self.assertIsNone(p.cliente_id)
        self.assertIsNone(p.motorista_id)
        # Report should mention both unresolved FKs
        self.assertIn("NAOEXISTE", resultado["relatorio"])

    def test_atomic_aborta_tudo_se_linha_invalida(self):
        csv_bytes = _make_csv(
            _csv_row(id="3001"),
            _csv_row(id="INVALIDO"),  # invalid id_vonzu
        )
        resultado = importar_csv(csv_bytes, self.filial, "test.csv")
        self.assertFalse(resultado["sucesso"])
        self.assertTrue(len(resultado["erros"]) > 0)
        # Nothing was saved
        self.assertEqual(Pedido.objects.count(), 0)

    def test_csv_vazio_retorna_erro(self):
        resultado = importar_csv(b"", self.filial, "vazio.csv")
        self.assertFalse(resultado["sucesso"])

    def test_relatorio_contem_resumo(self):
        csv_bytes = _make_csv(_csv_row())
        resultado = importar_csv(csv_bytes, self.filial, "test.csv")
        self.assertTrue(resultado["sucesso"])
        relatorio = resultado["relatorio"]
        self.assertIn("RELATÓRIO DE IMPORTAÇÃO", relatorio)
        self.assertIn("Pedidos novos criados", relatorio)
        self.assertIn("test.csv", relatorio)

    def test_tipo_delivery_mapeado_para_ENTREGA(self):
        csv_bytes = _make_csv(_csv_row(tipo="delivery"))
        importar_csv(csv_bytes, self.filial, "test.csv")
        p = Pedido.objects.first()
        self.assertEqual(p.tipo, "ENTREGA")

    def test_tipo_pickup_mapeado_para_RECOLHA(self):
        csv_bytes = _make_csv(_csv_row(id="4001", tipo="pickup"))
        importar_csv(csv_bytes, self.filial, "test.csv")
        p = Pedido.objects.get(id_vonzu=4001)
        self.assertEqual(p.tipo, "RECOLHA")

    def test_cancelled_importado_como_cancelled_nao_A(self):
        csv_bytes = _make_csv(_csv_row(id="5001", estado="cancelled"))
        importar_csv(csv_bytes, self.filial, "test.csv")
        p = Pedido.objects.get(id_vonzu=5001)
        self.assertEqual(p.estado, "cancelled")
        self.assertNotEqual(p.estado, "A")

    def test_decimal_com_virgula(self):
        csv_bytes = _make_csv(_csv_row(id="6001", peso="920,150"))
        importar_csv(csv_bytes, self.filial, "test.csv")
        p = Pedido.objects.get(id_vonzu=6001)
        from decimal import Decimal
        self.assertEqual(p.peso, Decimal("920.150"))


class PedidosViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.pais = Pais.objects.create(nome="PORTUGAL2", sigla="PT2", codigo_tel="+351")
        self.filial = Filial.objects.create(
              codigo="FIL2", nome="FILIAL2", pais_atuacao=self.pais, is_matriz=True
        )
        self.usuario = User.objects.create_user(
            username="op_pedidos", password="test", is_active=True
        )
        self.perm_view = Permission.objects.get(content_type__app_label="pedidos", codename="view_pedido")
        self.perm_add = Permission.objects.get(content_type__app_label="pedidos", codename="add_pedido")
        UsuarioFilial.objects.create(
            usuario=self.usuario,
            filial=self.filial,
            ativo=True,
            pode_consultar=True,
            pode_escrever=True,
        )

    def _get(self, path="/app/logistica/pedidos/"):
        req = self.factory.get(path)
        req.sisvar_extra = {}
        req.user = self.usuario
        return req

    def test_get_sem_permissao_levanta_permission_denied(self):
        req = self._get()
        with self.assertRaises(PermissionDenied):
            pedidos_view(req)

    def test_get_com_permissao_retorna_200(self):
        self.usuario.user_permissions.add(self.perm_view)
        req = self._get()
        response = pedidos_view(req)
        self.assertEqual(response.status_code, 200)

    def test_importar_sem_permissao_levanta_permission_denied(self):
        self.usuario.user_permissions.add(self.perm_view)
        req = self.factory.post(
            "/app/logistica/pedidos/importar",
            data={},
            content_type="multipart/form-data",
        )
        req.user = self.usuario
        with self.assertRaises(PermissionDenied):
            pedidos_importar_view(req)

    def test_importar_sem_arquivo_retorna_400(self):
        self.usuario.user_permissions.add(self.perm_view, self.perm_add)
        req = self.factory.post(
            "/app/logistica/pedidos/importar",
            data={"filial_id": self.filial.id},
        )
        req.user = self.usuario
        response = pedidos_importar_view(req)
        self.assertEqual(response.status_code, 400)

    def test_importar_csv_valido_retorna_200_e_relatorio(self):
        self.usuario.user_permissions.add(self.perm_view, self.perm_add)
        csv_bytes = _make_csv(_csv_row(id="9001"))
        arquivo = io.BytesIO(csv_bytes)
        arquivo.name = "test.csv"
        req = self.factory.post(
            "/app/logistica/pedidos/importar",
            data={"filial_id": self.filial.id, "arquivo_csv": arquivo},
            format="multipart",
        )
        req.user = self.usuario
        response = pedidos_importar_view(req)
        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertIn("relatorio", data)
        self.assertIn("stats", data)

    def test_importar_csv_invalido_retorna_422(self):
        self.usuario.user_permissions.add(self.perm_view, self.perm_add)
        csv_invalido = _make_csv(_csv_row(id="INVALIDO"))
        arquivo = io.BytesIO(csv_invalido)
        arquivo.name = "bad.csv"
        req = self.factory.post(
            "/app/logistica/pedidos/importar",
            data={"filial_id": self.filial.id, "arquivo_csv": arquivo},
            format="multipart",
        )
        req.user = self.usuario
        response = pedidos_importar_view(req)
        self.assertEqual(response.status_code, 422)
        import json
        data = json.loads(response.content)
        self.assertFalse(data["success"])
