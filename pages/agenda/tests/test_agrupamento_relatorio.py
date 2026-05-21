from decimal import Decimal

from django.test import SimpleTestCase

from pages.agenda.services.agrupamento_relatorio import (
    enriquecer_evento_relatorio,
    montar_agrupamentos_relatorio,
    resolver_subagrupamento,
)


class AgrupamentoRelatorioTest(SimpleTestCase):
    def test_financeiro_separa_entrada_saida(self):
        chave, rotulo = resolver_subagrupamento(
            {"categoria": "financeiro", "meta": {"tipo": "ENTRADA"}},
        )
        self.assertEqual(chave, "ENTRADA")
        self.assertEqual(rotulo, "Entrada")

    def test_montar_agrupamentos_por_data_categoria_subgrupo(self):
        eventos = [
            {
                "id": "c:1",
                "data": "2026-05-10",
                "categoria": "financeiro",
                "provider_key": "financeiro.registro_financeiro",
                "tipo_dado": "concreto",
                "titulo": "Entrada",
                "valor_decimal": "100.00",
                "meta": {"tipo": "ENTRADA", "observacao": "Obs A"},
            },
            {
                "id": "c:2",
                "data": "2026-05-10",
                "categoria": "financeiro",
                "provider_key": "financeiro.registro_financeiro",
                "tipo_dado": "concreto",
                "titulo": "Saída",
                "valor_decimal": "40.00",
                "meta": {"tipo": "SAIDA", "observacao": "Obs B"},
            },
        ]
        grupos = montar_agrupamentos_relatorio(eventos)
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]["total_registros"], 2)
        self.assertIsNone(grupos[0]["total_valor"])
        self.assertEqual(len(grupos[0]["totais_valor_subgrupos"]), 2)
        cat = grupos[0]["categorias"][0]
        self.assertIsNone(cat["total_valor"])
        self.assertEqual(len(cat["totais_valor_subgrupos"]), 2)
        subs = cat["subgrupos"]
        self.assertEqual(len(subs), 2)
        self.assertEqual(subs[0]["chave"], "ENTRADA")
        self.assertEqual(subs[0]["total_registros"], 1)
        self.assertEqual(subs[0]["total_valor"], "100,00")
        self.assertEqual(subs[1]["chave"], "SAIDA")
        self.assertEqual(subs[1]["total_valor"], "40,00")

    def test_enriquecer_observacao_financeira(self):
        ev = enriquecer_evento_relatorio(
            {
                "categoria": "financeiro",
                "meta": {"observacao": "  Teste  "},
                "valor_decimal": Decimal("10"),
            }
        )
        self.assertEqual(ev["observacao"], "Teste")
