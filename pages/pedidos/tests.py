import io
from datetime import date, datetime
from decimal import Decimal

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

from .models import Pedido, TentativaEntrega, ESTADO_ENOVO_PARA_CANONICO
from .services.importador_csv import importar_csv
from .services.importador_xlsx import (
    importar_xlsx,
    parse_xlsx_artigos_sem_persistir,
    resolver_tipo,
    tipo_por_referencia_recolha,
)
from .services.normalizacao import normalizar_estado, normalizar_estado_enovo
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


class NormalizacaoEstadoEnovoTests(TestCase):
    def test_pendente_mapeia_para_orders_vonzu(self):
        self.assertEqual(normalizar_estado_enovo("Pendente"), "orders_vonzu")

    def test_entrada_armazem_mapeia_para_ea(self):
        self.assertEqual(normalizar_estado_enovo("Entrada Armazém"), "EA")

    def test_desconhecido_retorna_none(self):
        self.assertIsNone(normalizar_estado_enovo("Estado ainda nao mapeado"))

    def test_vazio_e_none_retornam_none(self):
        self.assertIsNone(normalizar_estado_enovo(""))
        self.assertIsNone(normalizar_estado_enovo("   "))
        self.assertIsNone(normalizar_estado_enovo(None))

    def test_mapa_so_contem_labels_explicitos(self):
        self.assertEqual(
            ESTADO_ENOVO_PARA_CANONICO,
            {"Entrada Armazém": "EA", "Pendente": "orders_vonzu"},
        )


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

    def test_vonzu_ignora_referencia_ja_existente_com_id_enovo(self):
        """Prioridade ENOVO: CSV VONZU não cria pedido se a Referência já tem outro id."""
        Pedido.objects.create(
            filial=self.filial,
            origem="IMPORTADO",
            id_vonzu=18002334541,
            pedido="REF001",
            tipo="ENTREGA",
            criado=timezone.now(),
            atualizacao=timezone.now(),
            prev_entrega=date(2026, 4, 13),
            estado="orders_vonzu",
            cliente_id=self.cliente.id,
        )
        csv_bytes = _make_csv(_csv_row(id="1001", referencia="REF001"))
        resultado = importar_csv(csv_bytes, self.filial, "vonzu.csv")
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        self.assertEqual(resultado["stats"]["criados"], 0)
        self.assertEqual(resultado["stats"]["ignorados_prioridade_enovo"], 1)
        self.assertEqual(Pedido.objects.filter(filial=self.filial).count(), 1)
        self.assertFalse(Pedido.objects.filter(id_vonzu=1001).exists())
        self.assertIn("PRIORIDADE ENOVO", resultado["relatorio"])

    def test_upsert_pedido_existente_sem_alteracao(self):
        csv_bytes = _make_csv(_csv_row())
        importar_csv(csv_bytes, self.filial, "test.csv")
        # Import the same file again — nothing should change
        resultado = importar_csv(csv_bytes, self.filial, "test.csv")
        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["stats"]["sem_alteracao"], 1)
        self.assertEqual(resultado["stats"]["atualizados"], 0)
        self.assertEqual(Pedido.objects.count(), 1)

    def test_forcar_atualizacao_mesmo_com_data_igual(self):
        csv_bytes = _make_csv(_csv_row(estado="created", embalagens="1"))
        importar_csv(csv_bytes, self.filial, "test.csv")
        csv_bytes2 = _make_csv(_csv_row(estado="completed", embalagens="5"))
        resultado = importar_csv(
            csv_bytes2, self.filial, "test.csv", forcar_atualizacao=True
        )
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        self.assertEqual(resultado["stats"]["atualizados"], 1)
        self.assertEqual(resultado["stats"]["sem_alteracao"], 0)
        p = Pedido.objects.get(id_vonzu=1001)
        self.assertEqual(p.estado, "completed")
        self.assertEqual(p.volume, 5)

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

    def test_analise_movimentacoes_exige_data_unica_no_csv(self):
        csv_bytes = _make_csv(
            _csv_row(id="7001", data="2026-04-13"),
            _csv_row(id="7002", data="2026-04-14"),
        )
        resultado = importar_csv(
            csv_bytes,
            self.filial,
            "test.csv",
            analisar_movimentacoes_dia=True,
        )
        self.assertFalse(resultado["sucesso"])
        self.assertIn("apenas uma data válida", resultado["erros"][0])

    def test_analise_movimentacoes_lista_pedido_ausente_no_arquivo(self):
        pedido_existente = Pedido.objects.create(
            filial=self.filial,
            origem="IMPORTADO",
            id_vonzu=8888,
            pedido="REF_EXISTENTE",
            tipo="ENTREGA",
            criado=timezone.make_aware(datetime(2026, 4, 10, 10, 0, 0)),
            atualizacao=timezone.make_aware(datetime(2026, 4, 10, 10, 0, 0)),
            prev_entrega=date(2026, 4, 13),
            dt_entrega=None,
            estado="created",
            volume=1,
            nome_dest="Destino",
        )
        TentativaEntrega.objects.create(
            pedido=pedido_existente,
            data_tentativa=date(2026, 4, 13),
            estado="assigned",
            periodo="TARDE",
        )

        csv_bytes = _make_csv(_csv_row(id="1001", data="2026-04-13"))
        resultado = importar_csv(
            csv_bytes,
            self.filial,
            "test.csv",
            analisar_movimentacoes_dia=True,
        )
        self.assertTrue(resultado["sucesso"])
        self.assertIn("MOVIMENTAÇÕES DO DIA AUSENTES NO ARQUIVO", resultado["relatorio"])
        self.assertIn("id_vonzu=      8888", resultado["relatorio"])


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


def _make_xlsx_enovo(rows_dicts):
    """Gera XLSX mínimo ENOVO Listagem de Envios (bytes) a partir de lista de dicts."""
    from openpyxl import Workbook

    headers = [
        "Tipo",
        "TRK",
        "Cod. Serviço",
        "Referência",
        "Cod. Cliente",
        "Remetente",
        "Morada Remetente",
        "CP Remetente",
        "Localidade Remetente",
        "Contacto Remetente",
        "Destinatário",
        "Morada Destinatário",
        "CP Destinatário",
        "Localidade Destinatário",
        "Contacto Destinatário",
        "E-mail Destinatário",
        "Volumes",
        "Peso (Kg)",
        "Descrição",
        "Último Estado",
        "Data Último Estado",
        "Data Descarga",
        "Data Entrega",
        "Data Criação",
        "Cód. Motorista",
        "Observações Estado",
        "Observações Carga",
        "Observações Descarga",
        "Obs. Internas",
    ]
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows_dicts:
        ws.append([row.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _row_enovo(**kwargs):
    defaults = {
        "Tipo": "ENVIO",
        "TRK": "001002240391",
        "Cod. Serviço": "DIST",
        "Referência": "40738_005",
        "Cod. Cliente": None,  # preenchido no setUp com pk real
        "Remetente": "LOJA SINTRA",
        "Morada Remetente": "Leroy Merlin, Estrada Nacional",
        "CP Remetente": "2710-088",
        "Localidade Remetente": "Sintra",
        "Contacto Remetente": "211944944",
        "Destinatário": "António Pinto",
        "Morada Destinatário": "Rua X 1",
        "CP Destinatário": "1350-025",
        "Localidade Destinatário": "LISBOA",
        "Contacto Destinatário": "351910218216",
        "E-mail Destinatário": "",
        "Volumes": 2,
        "Peso (Kg)": 1.5,
        "Descrição": "ARTIGO A (1) (111); ARTIGO B (1) (222)",
        "Último Estado": "Pendente",
        "Data Último Estado": "2026-07-21 14:38:22",
        "Data Descarga": "2026-07-23",
        "Data Entrega": "",
        "Data Criação": "2026-07-21 14:38:22",
        "Cód. Motorista": "",
        "Observações Estado": "",
        "Observações Carga": "",
        "Observações Descarga": "",
        "Obs. Internas": "",
    }
    defaults.update(kwargs)
    return defaults


class TipoEnovoTests(TestCase):
    def test_referencia_cd_forca_recolha(self):
        self.assertTrue(tipo_por_referencia_recolha("abcCDxyz"))
        self.assertTrue(tipo_por_referencia_recolha("pedido-lmpt-1"))
        self.assertFalse(tipo_por_referencia_recolha("40738_005"))

    def test_resolver_tipo_dist_e_override(self):
        self.assertEqual(resolver_tipo("DIST", "40738_005"), "ENTREGA")
        self.assertEqual(resolver_tipo("DIST", "REF_CD_01"), "RECOLHA")
        self.assertIsNone(resolver_tipo("XYZ", "sem token"))


class ImportadorXlsxTests(TestCase):
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
            codigo="MOT1",
            id_enovo="13",
            nome="AYLANA",
            telefone="+351900000001",
        )

    def test_importa_agrega_volume_por_trk(self):
        xlsx = _make_xlsx_enovo([
            _row_enovo(
                TRK="001002240391",
                **{"Cod. Cliente": self.cliente.pk, "Volumes": 2, "Peso (Kg)": 1.0},
            ),
            _row_enovo(
                TRK="001002240391",
                **{"Cod. Cliente": self.cliente.pk, "Volumes": 3, "Peso (Kg)": 2.5},
            ),
        ])
        resultado = importar_xlsx(xlsx, self.filial, "test.xlsx")
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        self.assertEqual(resultado["stats"]["criados"], 1)
        self.assertEqual(resultado["stats"]["ignoradas"], 1)
        pedido = Pedido.objects.get(filial=self.filial, id_vonzu=1002240391)
        self.assertEqual(pedido.volume, 5)
        self.assertEqual(float(pedido.peso), 3.5)
        self.assertEqual(pedido.estado, "orders_vonzu")
        self.assertEqual(pedido.prev_entrega, date(2026, 7, 23))
        self.assertEqual(pedido.cliente_id, self.cliente.pk)
        self.assertEqual(TentativaEntrega.objects.filter(pedido=pedido).count(), 1)

    def test_estado_desconhecido_aborta(self):
        xlsx = _make_xlsx_enovo([
            _row_enovo(**{"Cod. Cliente": self.cliente.pk, "Último Estado": "Estado Novo"}),
        ])
        resultado = importar_xlsx(xlsx, self.filial, "bad.xlsx")
        self.assertFalse(resultado["sucesso"])
        self.assertTrue(any("não mapeado" in e for e in resultado["erros"]))
        self.assertEqual(Pedido.objects.count(), 0)

    def test_cliente_inexistente_aborta(self):
        xlsx = _make_xlsx_enovo([_row_enovo(**{"Cod. Cliente": 999999})])
        resultado = importar_xlsx(xlsx, self.filial, "bad.xlsx")
        self.assertFalse(resultado["sucesso"])
        self.assertTrue(any("Cod. Cliente" in e for e in resultado["erros"]))
        self.assertEqual(Pedido.objects.count(), 0)

    def test_motorista_codigo_sem_match_aborta(self):
        xlsx = _make_xlsx_enovo([
            _row_enovo(**{"Cod. Cliente": self.cliente.pk, "Cód. Motorista": "999"}),
        ])
        resultado = importar_xlsx(xlsx, self.filial, "bad.xlsx")
        self.assertFalse(resultado["sucesso"])
        self.assertTrue(any("Cód. Motorista" in e for e in resultado["erros"]))
        self.assertEqual(Pedido.objects.count(), 0)

    def test_motorista_id_enovo_resolvido(self):
        xlsx = _make_xlsx_enovo([
            _row_enovo(**{"Cod. Cliente": self.cliente.pk, "Cód. Motorista": "13"}),
        ])
        resultado = importar_xlsx(xlsx, self.filial, "ok.xlsx")
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        pedido = Pedido.objects.get(filial=self.filial, id_vonzu=1002240391)
        self.assertEqual(pedido.motorista_id, self.motorista.id)

    def test_referencia_lmpt_tipo_recolha_usa_remetente(self):
        xlsx = _make_xlsx_enovo([
            _row_enovo(
                **{
                    "Cod. Cliente": self.cliente.pk,
                    "Referência": "pedido_LMPT_01",
                    "Remetente": "Cliente Recolha",
                    "Morada Remetente": "Rua Recolha 10",
                    "CP Remetente": "1000-001",
                    "Localidade Remetente": "LISBOA",
                    "Contacto Remetente": "912345678",
                    "Destinatário": "Loja Destino",
                    "Morada Destinatário": "Morada Loja",
                    "CP Destinatário": "2710-088",
                    "Localidade Destinatário": "Sintra",
                    "Contacto Destinatário": "211944944",
                    "E-mail Destinatário": "loja@example.com",
                }
            ),
        ])
        resultado = importar_xlsx(xlsx, self.filial, "rec.xlsx")
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        pedido = Pedido.objects.get(filial=self.filial, id_vonzu=1002240391)
        self.assertEqual(pedido.tipo, "RECOLHA")
        self.assertEqual(pedido.nome_dest, "Cliente Recolha")
        self.assertEqual(pedido.endereco_dest, "Rua Recolha 10")
        self.assertEqual(pedido.codpost_dest, "1000-001")
        self.assertEqual(pedido.cidade_dest, "LISBOA")
        self.assertEqual(pedido.fone_dest, "912345678")
        self.assertFalse(pedido.email_dest)

    def test_entrega_usa_destinatario(self):
        xlsx = _make_xlsx_enovo([
            _row_enovo(**{"Cod. Cliente": self.cliente.pk}),
        ])
        resultado = importar_xlsx(xlsx, self.filial, "ent.xlsx")
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        pedido = Pedido.objects.get(filial=self.filial, id_vonzu=1002240391)
        self.assertEqual(pedido.tipo, "ENTREGA")
        self.assertEqual(pedido.nome_dest, "António Pinto")
        self.assertEqual(pedido.endereco_dest, "Rua X 1")
        self.assertEqual(pedido.codpost_dest, "1350-025")
        self.assertEqual(pedido.cidade_dest, "LISBOA")
        self.assertEqual(pedido.fone_dest, "351910218216")

    def test_obs_mescla_colunas_ao_aw_ax_ba(self):
        xlsx = _make_xlsx_enovo([
            _row_enovo(**{
                "Cod. Cliente": self.cliente.pk,
                "Observações Estado": "Agendado para amanhã",
                "Observações Carga": "Carga frágil",
                "Observações Descarga": "Portão lateral",
                "Obs. Internas": "Prioridade loja",
            }),
        ])
        resultado = importar_xlsx(xlsx, self.filial, "obs.xlsx")
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        pedido = Pedido.objects.get(filial=self.filial, id_vonzu=1002240391)
        self.assertEqual(
            pedido.obs,
            "Agendado para amanhã | Carga frágil | Portão lateral | Prioridade loja",
        )

    def test_mesma_atualizacao_sem_forcar_ignora(self):
        xlsx = _make_xlsx_enovo([
            _row_enovo(**{
                "Cod. Cliente": self.cliente.pk,
                "Volumes": 2,
                "Destinatário": "Nome Original",
            }),
        ])
        self.assertTrue(importar_xlsx(xlsx, self.filial, "a.xlsx")["sucesso"])
        xlsx2 = _make_xlsx_enovo([
            _row_enovo(**{
                "Cod. Cliente": self.cliente.pk,
                "Volumes": 9,
                "Destinatário": "Nome Alterado",
                "Data Último Estado": "2026-07-21 14:38:22",
            }),
        ])
        resultado = importar_xlsx(xlsx2, self.filial, "b.xlsx")
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        self.assertEqual(resultado["stats"]["sem_alteracao"], 1)
        self.assertEqual(resultado["stats"]["atualizados"], 0)
        pedido = Pedido.objects.get(filial=self.filial, id_vonzu=1002240391)
        self.assertEqual(pedido.volume, 2)
        self.assertEqual(pedido.nome_dest, "Nome Original")

    def test_forcar_atualizacao_mesmo_com_data_igual(self):
        xlsx = _make_xlsx_enovo([
            _row_enovo(**{
                "Cod. Cliente": self.cliente.pk,
                "Volumes": 2,
                "Destinatário": "Nome Original",
            }),
        ])
        self.assertTrue(importar_xlsx(xlsx, self.filial, "a.xlsx")["sucesso"])
        xlsx2 = _make_xlsx_enovo([
            _row_enovo(**{
                "Cod. Cliente": self.cliente.pk,
                "Volumes": 9,
                "Peso (Kg)": 12.5,
                "Destinatário": "Nome Alterado",
                "Data Último Estado": "2026-07-21 14:38:22",
            }),
        ])
        resultado = importar_xlsx(
            xlsx2, self.filial, "b.xlsx", forcar_atualizacao=True
        )
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        self.assertEqual(resultado["stats"]["atualizados"], 1)
        self.assertEqual(resultado["stats"]["sem_alteracao"], 0)
        pedido = Pedido.objects.get(filial=self.filial, id_vonzu=1002240391)
        self.assertEqual(pedido.volume, 9)
        self.assertEqual(float(pedido.peso), 12.5)
        self.assertEqual(pedido.nome_dest, "Nome Alterado")

    def test_encargo_ignorado_nao_corrompe_agregacao(self):
        xlsx = _make_xlsx_enovo([
            _row_enovo(
                TRK="008002308349",
                **{
                    "Cod. Cliente": self.cliente.pk,
                    "Volumes": 1,
                    "Peso (Kg)": 48.5,
                },
            ),
            _row_enovo(
                Tipo="ENCARGO",
                TRK="008002308349",
                **{
                    "Cod. Serviço": "SBD",
                    "Referência": None,
                    "Cod. Cliente": self.cliente.pk,
                    "Último Estado": None,
                    "Data Último Estado": None,
                    "Data Descarga": None,
                    "Data Criação": None,
                    "Volumes": None,
                    "Peso (Kg)": None,
                },
            ),
        ])
        resultado = importar_xlsx(xlsx, self.filial, "enc.xlsx")
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        self.assertEqual(resultado["stats"]["ignorados_encargo"], 1)
        self.assertEqual(resultado["stats"]["criados"], 1)
        pedido = Pedido.objects.get(filial=self.filial, id_vonzu=8002308349)
        self.assertEqual(pedido.volume, 1)
        self.assertEqual(float(pedido.peso), 48.5)

    def test_match_por_referencia_remapeia_id_vonzu_e_preserva_tentativa(self):
        """Pedido legado VONZU (outro id_vonzu, mesma Referência) é actualizado, não duplicado."""
        legado = Pedido.objects.create(
            filial=self.filial,
            origem="IMPORTADO",
            id_vonzu=555001,
            pedido="40738_005",
            tipo="ENTREGA",
            criado=timezone.now(),
            atualizacao=timezone.now().replace(year=2026, month=1, day=1, hour=10, minute=0, second=0, microsecond=0),
            prev_entrega=date(2026, 1, 10),
            estado="created",
            volume=1,
            cliente_id=self.cliente.pk,
        )
        tent = TentativaEntrega.objects.create(
            pedido=legado,
            data_tentativa=date(2026, 1, 10),
            estado="created",
            periodo="TARDE",
        )
        pk_legado = legado.pk
        pk_tent = tent.pk

        xlsx = _make_xlsx_enovo([
            _row_enovo(
                TRK="001002240391",
                **{
                    "Cod. Cliente": self.cliente.pk,
                    "Referência": "40738_005",
                    "Data Último Estado": "2026-07-21 14:38:22",
                    "Data Descarga": "2026-07-23",
                },
            ),
        ])
        resultado = importar_xlsx(xlsx, self.filial, "remap.xlsx")
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        self.assertEqual(resultado["stats"]["criados"], 0)
        self.assertEqual(resultado["stats"]["atualizados"], 1)
        self.assertEqual(resultado["stats"]["ids_remapeados"], 1)
        self.assertEqual(Pedido.objects.filter(filial=self.filial).count(), 1)

        pedido = Pedido.objects.get(pk=pk_legado)
        self.assertEqual(pedido.id_vonzu, 1002240391)
        self.assertEqual(pedido.pedido, "40738_005")
        self.assertEqual(pedido.estado, "orders_vonzu")
        # Tentativa antiga preservada (FK por pedido_id / PK)
        self.assertTrue(TentativaEntrega.objects.filter(pk=pk_tent, pedido_id=pk_legado).exists())
        self.assertIn("555001 → 1002240391", resultado["relatorio"])

    def test_mesma_referencia_trks_distintos_enovo_cria_dois(self):
        """Duplicidade de Referência só no ENOVO (TRKs diferentes) é permitida."""
        xlsx = _make_xlsx_enovo([
            _row_enovo(
                TRK="18002334541",
                **{"Cod. Cliente": self.cliente.pk, "Referência": "571221-CD48090", "Volumes": 1},
            ),
            _row_enovo(
                TRK="18002352656",
                **{"Cod. Cliente": self.cliente.pk, "Referência": "571221-CD48090", "Volumes": 2},
            ),
        ])
        resultado = importar_xlsx(xlsx, self.filial, "dup_ref.xlsx")
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        self.assertEqual(resultado["stats"]["criados"], 2)
        self.assertEqual(Pedido.objects.filter(filial=self.filial, pedido="571221-CD48090").count(), 2)
        self.assertTrue(Pedido.objects.filter(id_vonzu=18002334541).exists())
        self.assertTrue(Pedido.objects.filter(id_vonzu=18002352656).exists())

    def test_vonzu_legado_mais_dois_trks_mesma_ref_remapeia_um_e_cria_outro(self):
        """Um legado VONZU com a ref: 1.º TRK remapeia; 2.º TRK cria pedido novo."""
        legado = Pedido.objects.create(
            filial=self.filial,
            origem="IMPORTADO",
            id_vonzu=555001,
            pedido="571221-CD48090",
            tipo="ENTREGA",
            criado=timezone.now(),
            atualizacao=timezone.now().replace(
                year=2026, month=1, day=1, hour=10, minute=0, second=0, microsecond=0
            ),
            prev_entrega=date(2026, 1, 10),
            estado="created",
            volume=1,
            cliente_id=self.cliente.pk,
        )
        pk_legado = legado.pk
        xlsx = _make_xlsx_enovo([
            _row_enovo(
                TRK="18002334541",
                **{"Cod. Cliente": self.cliente.pk, "Referência": "571221-CD48090"},
            ),
            _row_enovo(
                TRK="18002352656",
                **{"Cod. Cliente": self.cliente.pk, "Referência": "571221-CD48090"},
            ),
        ])
        resultado = importar_xlsx(xlsx, self.filial, "vonzu_dup.xlsx")
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        self.assertEqual(resultado["stats"]["criados"], 1)
        self.assertEqual(resultado["stats"]["atualizados"], 1)
        self.assertEqual(resultado["stats"]["ids_remapeados"], 1)
        self.assertEqual(Pedido.objects.filter(filial=self.filial).count(), 2)
        legado.refresh_from_db()
        self.assertEqual(legado.pk, pk_legado)
        self.assertEqual(legado.id_vonzu, 18002334541)
        self.assertTrue(Pedido.objects.filter(id_vonzu=18002352656).exists())

    def test_parse_xlsx_artigos_sem_persistir_le_descricao(self):
        xlsx = _make_xlsx_enovo([
            _row_enovo(**{
                "TRK": "013002201157",
                "Referência": "REF_ART",
                "Descrição": "MESA TESTE (2) (12345678); CADEIRA (1) (87654321)",
                "Cod. Cliente": self.cliente.pk,
            }),
            _row_enovo(**{
                "TRK": "013002201157",
                "Referência": "REF_ART",
                "Descrição": "",
                "Cod. Cliente": self.cliente.pk,
            }),
        ])
        resultado = parse_xlsx_artigos_sem_persistir(xlsx)
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        self.assertEqual(len(resultado["pedidos"]), 1)
        pedido = resultado["pedidos"][0]
        self.assertEqual(pedido["id_vonzu"], 13002201157)
        self.assertEqual(pedido["referencia"], "REF_ART")
        self.assertEqual(len(pedido["artigos"]), 2)
        self.assertEqual(pedido["artigos"][0]["cod_fornecedor"], "12345678")
        self.assertEqual(pedido["artigos"][0]["quantidade"], 2)

    def test_parse_xlsx_artigos_sem_descricao_retorna_vazio(self):
        xlsx = _make_xlsx_enovo([
            _row_enovo(**{
                "Cod. Cliente": self.cliente.pk,
                "Descrição": "",
            }),
            _row_enovo(
                Tipo="ENCARGO",
                TRK="999999999001",
                **{"Cod. Cliente": self.cliente.pk, "Descrição": "IGNORAR (1) (1)"},
            ),
        ])
        resultado = parse_xlsx_artigos_sem_persistir(xlsx)
        self.assertTrue(resultado["sucesso"], resultado["erros"])
        # Sem Descrição parseável, montar_dados_volumes_agrupados omite o TRK;
        # ENCARGO é ignorado (não gera artigo a partir da linha de encargo).
        self.assertEqual(resultado["pedidos"], [])


class PedidosImportarXlsxViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.usuario = User.objects.create_user(username="imp_xlsx", password="x")
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
        UsuarioFilial.objects.create(
            usuario=self.usuario,
            filial=self.filial,
            ativo=True,
            pode_consultar=True,
            pode_escrever=True,
        )
        self.perm_view = Permission.objects.get(codename="view_pedido")
        self.perm_add = Permission.objects.get(codename="add_pedido")

    def test_importar_xlsx_valido_retorna_200(self):
        self.usuario.user_permissions.add(self.perm_view, self.perm_add)
        xlsx = _make_xlsx_enovo([_row_enovo(**{"Cod. Cliente": self.cliente.pk})])
        arquivo = io.BytesIO(xlsx)
        arquivo.name = "enovo.xlsx"
        req = self.factory.post(
            "/app/logistica/pedidos/importar",
            data={"filial_id": self.filial.id, "arquivo": arquivo},
            format="multipart",
        )
        req.user = self.usuario
        response = pedidos_importar_view(req)
        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_extensao_invalida_retorna_400(self):
        self.usuario.user_permissions.add(self.perm_view, self.perm_add)
        arquivo = io.BytesIO(b"x")
        arquivo.name = "x.txt"
        req = self.factory.post(
            "/app/logistica/pedidos/importar",
            data={"filial_id": self.filial.id, "arquivo": arquivo},
            format="multipart",
        )
        req.user = self.usuario
        response = pedidos_importar_view(req)
        self.assertEqual(response.status_code, 400)
