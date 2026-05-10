"""Resolução de zona de entrega a partir do código postal do pedido (regras por filial)."""

from pages.zona_entrega.models import ZonaEntrega


def normalizar_cp7_num(codigo_postal):
    digitos = "".join(c for c in str(codigo_postal or "") if c.isdigit())
    if len(digitos) < 4:
        return None, None
    cp4 = int(digitos[:4])
    cp7 = int(digitos[:7] if len(digitos) >= 7 else digitos)
    return cp4, cp7


def carregar_regras_zona_por_filial(filial):
    if not filial:
        return []
    zonas = (
        ZonaEntrega.objects.filter(filial=filial, is_deleted=False, ativa=True)
        .prefetch_related("faixas_postais", "excecoes_postais")
        .order_by("-prioridade", "descricao")
    )
    regras = []
    for zona in zonas:
        faixas = [f for f in zona.faixas_postais.all() if f.ativa]
        excecoes = [e for e in zona.excecoes_postais.all() if e.ativa]
        regras.append({
            "zona": zona,
            "faixas": faixas,
            "excecoes": excecoes,
        })
    return regras


def resolver_zona_e_faixa_entrega(codigo_postal, regras_zona):
    cp4, cp7 = normalizar_cp7_num(codigo_postal)
    if cp4 is None or cp7 is None:
        return "", ""

    for regra in regras_zona:
        inclui_excecao = False
        exclui_excecao = False
        codigo_excecao_incluir = ""
        for exc in regra["excecoes"]:
            if exc.cp7_num == cp7:
                if exc.tipo_excecao == "INCLUIR":
                    inclui_excecao = True
                    codigo_excecao_incluir = exc.codigo_postal
                elif exc.tipo_excecao == "EXCLUIR":
                    exclui_excecao = True
        if inclui_excecao:
            faixa_exc = f"EXC {codigo_excecao_incluir}"
            return regra["zona"].descricao, faixa_exc
        if exclui_excecao:
            continue

        for faixa in regra["faixas"]:
            if faixa.tipo_intervalo == "CP4":
                if faixa.cp4_inicial and faixa.cp4_final and int(faixa.cp4_inicial) <= cp4 <= int(faixa.cp4_final):
                    faixa_desc = f"CP4 {faixa.codigo_postal_inicial}-{faixa.codigo_postal_final}"
                    return regra["zona"].descricao, faixa_desc
            else:
                if faixa.cp7_inicial_num <= cp7 <= faixa.cp7_final_num:
                    faixa_desc = f"CP7 {faixa.codigo_postal_inicial}-{faixa.codigo_postal_final}"
                    return regra["zona"].descricao, faixa_desc
    return "", ""
