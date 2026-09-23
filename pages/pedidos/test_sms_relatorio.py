"""Testes de elegibilidade SMS (relatório + automático partilham `sms_relatorio`)."""

from datetime import date

from django.test import TestCase
from django.utils import timezone

from pages.core.models import Pais
from pages.filial.models import Filial, FilialConfig
from pages.pedidos.models import Pedido, TentativaEntrega
from pages.pedidos.services import sms_envio_automatico
from sac_base.sms_service import montar_mensagem
from pages.pedidos.services.sms_relatorio import (
    ddi_padrao_operacao_filial,
    ler_templates_sms_filial,
    montar_preview_sms_por_tipo,
    qs_tentativas_sms_pendentes_envio,
    queryset_tentativas_envio_manual_por_ids,
    sigla_pais_operacao_filial,
)


class SmsRelatorioQuerysetTests(TestCase):
    """Regras de `qs_tentativas_sms_pendentes_envio` e envio manual por ids + data."""

    dt = date(2026, 5, 1)
    dt_other = date(2026, 5, 2)

    def setUp(self):
        self.pais = Pais.objects.create(nome="PT-SMS", sigla="PT", codigo_tel="+351")
        self.filial = Filial.objects.create(
            codigo="SMS1", nome="FIL SMS 1", pais_atuacao=self.pais, is_matriz=True
        )
        FilialConfig.objects.create(
            filial=self.filial,
            sms_padrao_1="Manhã {referencia}",
            sms_padrao_2="Tarde {referencia}",
        )
        self.filial_b = Filial.objects.create(
            codigo="SMS2", nome="FIL SMS 2", pais_atuacao=self.pais, is_matriz=False
        )
        FilialConfig.objects.create(filial=self.filial_b)

    def _pedido(self, id_vonzu: int, filial=None, fone: str = "912345678") -> Pedido:
        filial = filial or self.filial
        now = timezone.now()
        return Pedido.objects.create(
            filial=filial,
            id_vonzu=id_vonzu,
            tipo="ENTREGA",
            criado=now,
            atualizacao=now,
            prev_entrega=self.dt,
            fone_dest=fone,
        )

    def _tentativa(self, pedido: Pedido, data_tentativa=None, **kwargs) -> TentativaEntrega:
        data_tentativa = data_tentativa or self.dt
        defaults = {
            "data_tentativa": data_tentativa,
            "estado": "created",
            "periodo": "MANHA",
            "sms_enviado": False,
        }
        defaults.update(kwargs)
        return TentativaEntrega.objects.create(pedido=pedido, **defaults)

    def test_pendentes_inclui_elegivel(self):
        p = self._pedido(10001)
        t = self._tentativa(p)
        ids = set(qs_tentativas_sms_pendentes_envio(self.filial, self.dt).values_list("id", flat=True))
        self.assertIn(t.id, ids)

    def test_pendentes_exclui_sms_ja_enviado(self):
        p = self._pedido(10002)
        t = self._tentativa(p, sms_enviado=True)
        ids = set(qs_tentativas_sms_pendentes_envio(self.filial, self.dt).values_list("id", flat=True))
        self.assertNotIn(t.id, ids)

    def test_pendentes_exclui_estado_fora_de_segue_entrega(self):
        p = self._pedido(10003)
        t = self._tentativa(p, estado="completed")
        ids = set(qs_tentativas_sms_pendentes_envio(self.filial, self.dt).values_list("id", flat=True))
        self.assertNotIn(t.id, ids)

    def test_pendentes_exclui_sem_periodo(self):
        p = self._pedido(10004)
        t = self._tentativa(p, periodo="")
        ids = set(qs_tentativas_sms_pendentes_envio(self.filial, self.dt).values_list("id", flat=True))
        self.assertNotIn(t.id, ids)

    def test_pendentes_exclui_outra_filial(self):
        p = self._pedido(10005, filial=self.filial_b)
        t = self._tentativa(p)
        ids = set(qs_tentativas_sms_pendentes_envio(self.filial, self.dt).values_list("id", flat=True))
        self.assertNotIn(t.id, ids)

    def test_pendentes_exclui_tentativa_obsoleta_com_posterior(self):
        """Linha do dia D excluída se existir outra tentativa do mesmo pedido em data > D."""
        p = self._pedido(10006)
        t_old = self._tentativa(p, data_tentativa=self.dt, estado="created", periodo="MANHA")
        self._tentativa(
            p,
            data_tentativa=date(2026, 5, 10),
            estado="assigned",
            periodo="MANHA",
        )
        ids = set(qs_tentativas_sms_pendentes_envio(self.filial, self.dt).values_list("id", flat=True))
        self.assertNotIn(t_old.id, ids)

    def test_pendentes_exclui_incidencia_com_motivo_bloqueante(self):
        p = self._pedido(10061)
        t = self._tentativa(p, estado="Incidência", motivo_incidencia="Fora da zona")
        ids = set(qs_tentativas_sms_pendentes_envio(self.filial, self.dt).values_list("id", flat=True))
        self.assertNotIn(t.id, ids)

    def test_pendentes_inclui_incidencia_com_motivo_nao_bloqueante(self):
        p = self._pedido(10062)
        t = self._tentativa(p, estado="Incidência", motivo_incidencia="Cliente ausente")
        ids = set(qs_tentativas_sms_pendentes_envio(self.filial, self.dt).values_list("id", flat=True))
        self.assertIn(t.id, ids)

    def test_pendentes_exclui_motivo_no_pedido_quando_tentativa_vazia(self):
        p = self._pedido(10063)
        p.motivo_incidencia = "Entrega recusada"
        p.save(update_fields=["motivo_incidencia"])
        t = self._tentativa(p, estado="Incidência", motivo_incidencia="")
        ids = set(qs_tentativas_sms_pendentes_envio(self.filial, self.dt).values_list("id", flat=True))
        self.assertNotIn(t.id, ids)

    def test_pendentes_exclui_estado_que_nao_segue_mesmo_sem_motivo(self):
        p = self._pedido(10064)
        t = self._tentativa(p, estado="cancelled", motivo_incidencia="")
        ids = set(qs_tentativas_sms_pendentes_envio(self.filial, self.dt).values_list("id", flat=True))
        self.assertNotIn(t.id, ids)

    def test_manual_por_ids_respeita_data_do_post(self):
        p1 = self._pedido(10007)
        p2 = self._pedido(10008)
        t_dia = self._tentativa(p1, data_tentativa=self.dt)
        t_outro_dia = self._tentativa(p2, data_tentativa=self.dt_other, estado="created", periodo="TARDE")
        qs_ok = queryset_tentativas_envio_manual_por_ids(
            self.filial, self.dt, [t_dia.id, t_outro_dia.id]
        )
        self.assertEqual(set(qs_ok.values_list("id", flat=True)), {t_dia.id})

    def test_manual_ids_vazio_retorna_none(self):
        self.assertFalse(queryset_tentativas_envio_manual_por_ids(self.filial, self.dt, []).exists())

    def test_invalidar_sms_quando_data_tentativa_muda(self):
        p = self._pedido(20004)
        t = self._tentativa(p, data_tentativa=date(2026, 7, 24), sms_enviado=True, periodo="TARDE")
        t.invalidar_sms_se_janela_mudou(date(2026, 8, 18), "TARDE")
        self.assertFalse(t.sms_enviado)

    def test_invalidar_sms_quando_periodo_muda(self):
        p = self._pedido(20005)
        t = self._tentativa(p, sms_enviado=True, periodo="MANHA")
        t.invalidar_sms_se_janela_mudou(self.dt, "TARDE")
        self.assertFalse(t.sms_enviado)

    def test_manter_sms_quando_janela_nao_muda(self):
        p = self._pedido(20006)
        t = self._tentativa(p, sms_enviado=True, periodo="TARDE")
        t.invalidar_sms_se_janela_mudou(self.dt, "TARDE")
        self.assertTrue(t.sms_enviado)


class SmsRelatorioHelpersTests(TestCase):
    def setUp(self):
        self.pais = Pais.objects.create(nome="ES-SMS", sigla="ES", codigo_tel="+34")
        self.filial = Filial.objects.create(
            codigo="SMH1", nome="FIL HELPER 1", pais_atuacao=self.pais, is_matriz=True
        )
        FilialConfig.objects.create(
            filial=self.filial,
            sms_padrao_1="A",
            sms_padrao_2="B",
        )

    def test_ler_templates_sms_filial(self):
        m, t = ler_templates_sms_filial(self.filial)
        self.assertEqual(m, "A")
        self.assertEqual(t, "B")

    def test_ler_templates_fallback_tarde_igual_manha(self):
        self.filial.config.sms_padrao_2 = ""
        self.filial.config.save()
        filial = Filial.objects.get(pk=self.filial.pk)
        m, t = ler_templates_sms_filial(filial)
        self.assertEqual(m, "A")
        self.assertEqual(t, "A")

    def test_sigla_e_ddi_operacao_filial(self):
        self.assertEqual(sigla_pais_operacao_filial(self.filial), "ES")
        self.assertEqual(ddi_padrao_operacao_filial(self.filial), "34")

    def test_montagem_placeholder_entrega_por_tipo(self):
        dt = date(2026, 5, 1)
        template = "A sua #entrega# será em #dd/mm/aaaa# (#periodo#)."
        msg_entrega = montar_mensagem(template, dt, "MANHA", "PT", "ENTREGA")
        msg_recolha = montar_mensagem(template, dt, "MANHA", "PT", "RECOLHA")
        self.assertIn("A sua entrega", msg_entrega)
        self.assertIn("A sua recolha", msg_recolha)

    def test_preview_sms_por_tipo_traz_exemplos_reais(self):
        now = timezone.now()
        p_ent = Pedido.objects.create(
            filial=self.filial,
            id_vonzu=41001,
            tipo="ENTREGA",
            criado=now,
            atualizacao=now,
            prev_entrega=date(2026, 5, 1),
            pedido="REF-ENT-01",
        )
        p_rec = Pedido.objects.create(
            filial=self.filial,
            id_vonzu=41002,
            tipo="RECOLHA",
            criado=now,
            atualizacao=now,
            prev_entrega=date(2026, 5, 1),
            pedido="REF-REC-01",
        )
        TentativaEntrega.objects.create(
            pedido=p_ent,
            data_tentativa=date(2026, 5, 1),
            estado="created",
            periodo="MANHA",
        )
        TentativaEntrega.objects.create(
            pedido=p_rec,
            data_tentativa=date(2026, 5, 1),
            estado="created",
            periodo="TARDE",
        )

        self.filial.config.sms_padrao_1 = "A sua #entrega# MANHA #periodo#"
        self.filial.config.sms_padrao_2 = "A sua #entrega# TARDE #periodo#"
        self.filial.config.save()

        resultado = montar_preview_sms_por_tipo(self.filial, date(2026, 5, 1))
        self.assertTrue(resultado["ok"])
        prev = resultado["previews_por_tipo"]
        self.assertEqual(prev["ENTREGA"]["referencia"], "REF-ENT-01")
        self.assertEqual(prev["RECOLHA"]["referencia"], "REF-REC-01")
        self.assertIn("entrega", prev["ENTREGA"]["mensagens"]["MANHA"])
        self.assertIn("recolha", prev["RECOLHA"]["mensagens"]["MANHA"])

    def test_preview_sms_por_tipo_informa_ausencia(self):
        now = timezone.now()
        p_ent = Pedido.objects.create(
            filial=self.filial,
            id_vonzu=41003,
            tipo="ENTREGA",
            criado=now,
            atualizacao=now,
            prev_entrega=date(2026, 5, 1),
            pedido="REF-ENT-ONLY",
        )
        TentativaEntrega.objects.create(
            pedido=p_ent,
            data_tentativa=date(2026, 5, 1),
            estado="created",
            periodo="MANHA",
        )
        resultado = montar_preview_sms_por_tipo(self.filial, date(2026, 5, 1))
        self.assertTrue(resultado["ok"])
        self.assertIn("ENTREGA", resultado["previews_por_tipo"])
        self.assertNotIn("RECOLHA", resultado["previews_por_tipo"])
        self.assertTrue(
            any("RECOLHA" in m for m in resultado["mensagens_ausencia"])
        )


class SmsEnvioAutomaticoListaTests(TestCase):
    """`listar_pendentes_com_telefone` / `contar_pendentes_sem_telefone` alinhados ao mesmo qs."""

    dt = date(2026, 6, 1)

    def setUp(self):
        self.pais = Pais.objects.create(nome="PT-LIST", sigla="PT", codigo_tel="+351")
        self.filial = Filial.objects.create(
            codigo="SML1", nome="FIL LIST 1", pais_atuacao=self.pais, is_matriz=True
        )
        FilialConfig.objects.create(filial=self.filial)

    def _pedido(self, id_vonzu: int, fone: str = "", fone2: str = "") -> Pedido:
        now = timezone.now()
        return Pedido.objects.create(
            filial=self.filial,
            id_vonzu=id_vonzu,
            tipo="ENTREGA",
            criado=now,
            atualizacao=now,
            prev_entrega=self.dt,
            fone_dest=fone,
            fone_dest2=fone2,
        )

    def test_listar_so_com_telefone(self):
        p1 = self._pedido(20001, fone="911")
        p2 = self._pedido(20002, fone="")
        TentativaEntrega.objects.create(
            pedido=p1,
            data_tentativa=self.dt,
            estado="created",
            periodo="MANHA",
            sms_enviado=False,
        )
        TentativaEntrega.objects.create(
            pedido=p2,
            data_tentativa=self.dt,
            estado="created",
            periodo="MANHA",
            sms_enviado=False,
        )
        lista = sms_envio_automatico.listar_pendentes_com_telefone(self.filial, self.dt)
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0].pedido_id, p1.id)

    def test_contar_sem_telefone(self):
        p = self._pedido(20003, fone="  ")
        TentativaEntrega.objects.create(
            pedido=p,
            data_tentativa=self.dt,
            estado="created",
            periodo="MANHA",
            sms_enviado=False,
        )
        self.assertEqual(sms_envio_automatico.contar_pendentes_sem_telefone(self.filial, self.dt), 1)
