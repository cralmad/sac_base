import logging
import re

from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from pages.pedidos.models import Pedido, TentativaEntrega

logger = logging.getLogger(__name__)

CAMPOS_ATUALIZAVEIS = [
    "id_vonzu",
    "atualizacao",
    "prev_entrega",
    "dt_entrega",
    "estado",
    "volume",
    "nome_dest",
    "email_dest",
    "fone_dest",
    "fone_dest2",
    "endereco_dest",
    "codpost_dest",
    "cidade_dest",
    "obs",
    "motorista_id",
    "peso",
    "expresso",
]

# Padrão: DESCRICAO (QTD) (COD_FORNECEDOR)
_RE_PRODUTO = re.compile(r"(.+?)\s+\((\d+)\)\s+\((\d+)\)")


def parse_description(desc):
    """Retorna lista de dicts {descricao, quantidade, cod_fornecedor}."""
    if not desc or not str(desc).strip():
        return []
    desc = str(desc).strip().lstrip("*")
    result = []
    for m in _RE_PRODUTO.finditer(desc):
        descricao = m.group(1).strip().strip(",").strip()
        if descricao:
            result.append({
                "descricao": descricao,
                "quantidade": int(m.group(2)),
                "cod_fornecedor": m.group(3),
            })
    return result


def validar_data_unica_para_analise(linhas_resolvidas):
    datas_prev_entrega = {dados.get("prev_entrega") for _, dados in linhas_resolvidas}
    if len(datas_prev_entrega) != 1 or None in datas_prev_entrega:
        return None
    return next(iter(datas_prev_entrega))


def coletar_pedidos_movimentacao_ausentes_no_arquivo(filial, data_base, id_vonzus_importados):
    ausentes = []
    pedidos_vistos = set()
    tentativas_dia = (
        TentativaEntrega.objects
        .filter(
            pedido__filial=filial,
            data_tentativa=data_base,
        )
        .select_related("pedido")
        .order_by("pedido_id", "id")
    )
    for tentativa in tentativas_dia:
        if tentativa.pedido_id in pedidos_vistos:
            continue
        pedidos_vistos.add(tentativa.pedido_id)

        pedido = tentativa.pedido
        if pedido.id_vonzu in id_vonzus_importados:
            continue

        ausentes.append({
            "pedido_id": pedido.id,
            "id_vonzu": pedido.id_vonzu,
            "pedido_ref": pedido.pedido or "",
            "estado_movimentacao": tentativa.estado or "",
        })
    return ausentes


def montar_dados_volumes_agrupados(linhas_norm):
    agrupados = {}
    ordem_ids = []
    detalhes = []

    for _num_linha, dados in linhas_norm:
        id_vonzu = dados["id_vonzu"]
        if id_vonzu not in agrupados:
            agrupados[id_vonzu] = {
                "referencia": dados.get("pedido") or str(id_vonzu),
                "peso": str(dados.get("peso") or ""),
                "volume": dados.get("volume"),
                "artigos": [],
            }
            ordem_ids.append(id_vonzu)
        else:
            if not agrupados[id_vonzu]["referencia"] and dados.get("pedido"):
                agrupados[id_vonzu]["referencia"] = dados["pedido"]
            if not agrupados[id_vonzu]["peso"] and dados.get("peso") is not None:
                agrupados[id_vonzu]["peso"] = str(dados["peso"])
            if agrupados[id_vonzu]["volume"] is None and dados.get("volume") is not None:
                agrupados[id_vonzu]["volume"] = dados["volume"]

        artigos_linha = parse_description(dados.get("description_raw", ""))
        if artigos_linha:
            agrupados[id_vonzu]["artigos"].extend(artigos_linha)

        detalhes.append({
            "id_vonzu": id_vonzu,
            "referencia": dados.get("pedido") or str(id_vonzu),
            "qtd_artigos_linha": len(artigos_linha),
            "description_vazia": not bool((dados.get("description_raw") or "").strip()),
        })

    dados_volumes = [
        {
            "id_vonzu": id_vonzu,
            "referencia": agrupados[id_vonzu]["referencia"],
            "peso": agrupados[id_vonzu]["peso"],
            "volume": agrupados[id_vonzu]["volume"],
            "artigos": agrupados[id_vonzu]["artigos"],
        }
        for id_vonzu in ordem_ids
        if agrupados[id_vonzu]["artigos"]
    ]
    return dados_volumes, detalhes


def gerar_relatorio_importacao(
    nome_arquivo,
    filial,
    total_lidas,
    ignoradas,
    criados,
    atualizados,
    sem_alteracao,
    tentativas,
    avisos,
    analise_movimentacao_ativada=False,
    data_analise=None,
    pedidos_mov_ausentes_no_arquivo=None,
    remapeamentos=None,
    ignorados_prioridade_enovo=None,
):
    agora = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S")
    linhas = [
        "=== RELATÓRIO DE IMPORTAÇÃO DE PEDIDOS ===",
        f"Arquivo:                        {nome_arquivo}",
        f"Data/hora:                      {agora}",
        f"Filial:                         {filial.codigo} - {filial.nome}",
        "",
        "--- RESUMO ---",
        f"Total de linhas lidas:          {total_lidas}",
        f"Linhas duplicadas (ignoradas):  {ignoradas}",
        f"Pedidos novos criados:          {criados}",
        f"Pedidos atualizados:            {atualizados}",
        f"Pedidos sem alteração:          {sem_alteracao}",
        f"Tentativas criadas:             {tentativas}",
        "",
        "--- AVISOS: FKs NÃO RESOLVIDAS ---",
    ]
    if avisos:
        linhas.append(f"({len(avisos)} registro(s) com FK salva como null)")
        linhas.extend(avisos)
    else:
        linhas.append("(nenhum)")
    linhas.append("")
    remapeamentos = remapeamentos or []
    if remapeamentos:
        linhas.append("--- ID EXTERNO REMAPEADO (VONZU → ENOVO via Referência) ---")
        linhas.append(f"({len(remapeamentos)} pedido(s))")
        for item in remapeamentos:
            linhas.append(
                f"  ref={item.get('ref') or '-'} | "
                f"id_vonzu {item['id_anterior']} → {item['id_novo']}"
            )
        linhas.append("")
    ignorados_prioridade_enovo = ignorados_prioridade_enovo or []
    if ignorados_prioridade_enovo:
        linhas.append("--- IGNORADOS: REFERÊNCIA JÁ EXISTE (PRIORIDADE ENOVO) ---")
        linhas.append(f"({len(ignorados_prioridade_enovo)} linha(s))")
        for item in ignorados_prioridade_enovo:
            linhas.append(
                f"  ref={item.get('ref') or '-'} | "
                f"id_vonzu_csv={item.get('id_vonzu')} | "
                f"já existe id_vonzu={item.get('id_existente')}"
            )
        linhas.append("")
    if analise_movimentacao_ativada:
        linhas.append("--- ANÁLISE: MOVIMENTAÇÕES DO DIA AUSENTES NO ARQUIVO ---")
        linhas.append(f"Data analisada:                  {data_analise.isoformat() if data_analise else '-'}")
        pedidos_mov_ausentes_no_arquivo = pedidos_mov_ausentes_no_arquivo or []
        if pedidos_mov_ausentes_no_arquivo:
            linhas.append(f"({len(pedidos_mov_ausentes_no_arquivo)} pedido(s) encontrado(s))")
            for item in pedidos_mov_ausentes_no_arquivo:
                referencia = item["pedido_ref"] or "-"
                linhas.append(
                    f"  pedido_id={item['pedido_id']:>8} | "
                    f"id_vonzu={item['id_vonzu']:>10} | "
                    f"referência={referencia} | "
                    f"estado_mov={item['estado_movimentacao'] or '-'}"
                )
        else:
            linhas.append("(nenhum pedido com movimentação no dia ficou fora do arquivo)")
    linhas.append("")
    return "\n".join(linhas)


def _indexar_existentes_por_referencia(filial, referencias):
    """Mapa referencia -> lista de Pedidos (ENOVO permite várias refs iguais)."""
    refs = [r for r in referencias if r]
    if not refs:
        return {}

    por_ref = {}
    qs = Pedido.objects.filter(filial=filial, pedido__in=refs)
    for p in qs:
        ref = (p.pedido or "").strip()
        if not ref:
            continue
        por_ref.setdefault(ref, []).append(p)
    return por_ref


def _resolver_existente_linha(
    dados,
    por_trk,
    por_ref,
    *,
    match_por_referencia,
    trks_no_ficheiro,
    pks_ja_reclamados,
):
    """Resolve pedido existente por TRK; opcionalmente remapeia legado VONZU por Referência.

    Remapeamento por Referência só quando:
    - o TRK da linha ainda não existe;
    - existe pedido com a mesma Referência cujo id_vonzu NÃO está neste ficheiro
      (legado VONZU / ainda não migrado);
    - esse pedido ainda não foi reclamado por outra linha do lote.

    Duplicidade de Referência entre TRKs distintos no ENOVO é permitida (cria/actualiza
    por TRK). Retorna (pedido_ou_None, erro_ou_None, id_vonzu_anterior_ou_None).
    """
    id_novo = dados["id_vonzu"]
    ref = (dados.get("pedido") or "").strip() or None
    by_trk = por_trk.get(id_novo)
    if by_trk is not None:
        return by_trk, None, None

    if not match_por_referencia or not ref:
        return None, None, None

    candidatos = [
        p
        for p in por_ref.get(ref, [])
        if p.id_vonzu not in trks_no_ficheiro and p.pk not in pks_ja_reclamados
    ]
    if not candidatos:
        return None, None, None
    if len(candidatos) > 1:
        ids = ", ".join(str(p.id_vonzu) for p in candidatos)
        return None, (
            f"Referência '{ref}' tem vários pedidos legados (id_vonzu={ids}) "
            "sem TRK neste ficheiro. Resolva antes de importar."
        ), None

    legado = candidatos[0]
    ocupante = por_trk.get(id_novo)
    if ocupante is not None and ocupante.pk != legado.pk:
        return None, (
            f"Não é possível remapear id_vonzu {legado.id_vonzu} → {id_novo} "
            f"(ref='{ref}'): o TRK já pertence a outro pedido (pk={ocupante.pk})."
        ), None
    return legado, None, legado.id_vonzu


def persistir_pedidos_importados(
    filial,
    linhas_resolvidas,
    *,
    match_por_referencia=False,
    ignorar_criacao_se_referencia_alheia=False,
    forcar_atualizacao=False,
):
    """Upsert Pedido + TentativaEntrega a partir de linhas já normalizadas/resolvidas.

    Cada item de linhas_resolvidas: (num_linha, dados) com chaves alinhadas ao CSV/ENOVO.

    match_por_referencia (ENOVO): upsert por TRK; se o TRK não existir, pode actualizar
    um pedido legado (Referência igual e id_vonzu fora deste ficheiro), remapeando o ID.
    Várias linhas ENOVO com a mesma Referência e TRKs distintos são permitidas.

    ignorar_criacao_se_referencia_alheia (VONZU): se o Id VONZU não existir mas a
    Referência já estiver noutro pedido (ex.: importado pelo ENOVO), a linha é ignorada
    — prioridade ENOVO.

    forcar_atualizacao: se True, actualiza mesmo quando a data de actualização do
    ficheiro é igual à do pedido existente (útil quando o ENOVO não altera essa data).

    Retorna (criados, atualizados, sem_alteracao, tentativas, remapeamentos, ignorados_prio)
    """
    criados = atualizados = sem_alteracao = tentativas = 0
    remapeamentos = []
    ignorados_prioridade_enovo = []

    with transaction.atomic():
        id_vonzus = [d["id_vonzu"] for _, d in linhas_resolvidas]
        trks_no_ficheiro = set(id_vonzus)
        por_trk = {
            p.id_vonzu: p
            for p in Pedido.objects.filter(filial=filial, id_vonzu__in=id_vonzus)
        }

        por_ref = {}
        if match_por_referencia:
            refs = [(d.get("pedido") or "").strip() for _, d in linhas_resolvidas]
            por_ref = _indexar_existentes_por_referencia(filial, refs)

        refs_ocupadas_por_outro_id = {}
        if ignorar_criacao_se_referencia_alheia:
            refs = [
                (d.get("pedido") or "").strip()
                for _, d in linhas_resolvidas
                if (d.get("pedido") or "").strip()
            ]
            if refs:
                for p in Pedido.objects.filter(filial=filial, pedido__in=refs).only(
                    "id_vonzu", "pedido"
                ):
                    ref = (p.pedido or "").strip()
                    if not ref:
                        continue
                    # Mantém um id existente (ENOVO ou outro) distinto dos Ids deste CSV
                    if p.id_vonzu not in trks_no_ficheiro:
                        refs_ocupadas_por_outro_id.setdefault(ref, p.id_vonzu)

        resolvidos = []  # (num_linha, dados, existente|None, id_anterior|None)
        erros_resolve = []
        pks_ja_reclamados = set()
        for num_linha, dados in linhas_resolvidas:
            existente, erro, id_anterior = _resolver_existente_linha(
                dados,
                por_trk,
                por_ref,
                match_por_referencia=match_por_referencia,
                trks_no_ficheiro=trks_no_ficheiro,
                pks_ja_reclamados=pks_ja_reclamados,
            )
            if erro:
                erros_resolve.append(f"Linha {num_linha}: {erro}")
                continue
            if existente is not None:
                pks_ja_reclamados.add(existente.pk)
            resolvidos.append((num_linha, dados, existente, id_anterior))
        if erros_resolve:
            raise ValidationError(erros_resolve)

        datas_prev_por_pedido_id = {}
        for _num_linha, dados, existente, _id_ant in resolvidos:
            data_prev = dados.get("prev_entrega")
            if existente and data_prev:
                datas_prev_por_pedido_id.setdefault(existente.id, set()).add(data_prev)

        tentativas_existentes_map = {}
        if datas_prev_por_pedido_id:
            pedido_ids = list(datas_prev_por_pedido_id.keys())
            todas_datas_prev = {
                data_prev
                for datas in datas_prev_por_pedido_id.values()
                for data_prev in datas
            }
            tentativas_existentes_qs = TentativaEntrega.objects.filter(
                pedido_id__in=pedido_ids,
                data_tentativa__in=todas_datas_prev,
            ).only("id", "pedido_id", "data_tentativa", "estado", "motorista_id", "dt_entrega")
            tentativas_existentes_map = {
                (t.pedido_id, t.data_tentativa): t
                for t in tentativas_existentes_qs
            }

        novos_pedidos = []
        novos_dados = []
        pedidos_para_atualizar = []
        novas_tentativas = []
        tentativas_para_atualizar = []

        for num_linha, dados, existente, id_anterior in resolvidos:
            id_vonzu = dados["id_vonzu"]

            if existente is None:
                ref = (dados.get("pedido") or "").strip()
                if (
                    ignorar_criacao_se_referencia_alheia
                    and ref
                    and ref in refs_ocupadas_por_outro_id
                ):
                    ignorados_prioridade_enovo.append({
                        "ref": ref,
                        "id_vonzu": id_vonzu,
                        "id_existente": refs_ocupadas_por_outro_id[ref],
                        "num_linha": num_linha,
                    })
                    continue

                p = Pedido(
                    filial=filial,
                    origem="IMPORTADO",
                    id_vonzu=id_vonzu,
                    pedido=dados["pedido"],
                    tipo=dados["tipo"],
                    criado=dados["criado"],
                    atualizacao=dados["atualizacao"],
                    prev_entrega=dados["prev_entrega"],
                    dt_entrega=dados["dt_entrega"],
                    estado=dados["estado"],
                    volume=dados["volume"],
                    nome_dest=dados["nome_dest"],
                    email_dest=dados["email_dest"],
                    fone_dest=dados["fone_dest"],
                    fone_dest2=dados["fone_dest2"],
                    endereco_dest=dados["endereco_dest"],
                    codpost_dest=dados["codpost_dest"],
                    cidade_dest=dados["cidade_dest"],
                    obs=dados["obs"],
                    cliente_id=dados["cliente_id"],
                    motorista_id=dados["motorista_id"],
                    peso=dados["peso"],
                    expresso=dados["expresso"],
                )
                novos_pedidos.append(p)
                novos_dados.append(dados)
                criados += 1
            else:
                atualizacao_existente = existente.atualizacao
                if atualizacao_existente and atualizacao_existente.tzinfo is None:
                    atualizacao_existente = timezone.make_aware(atualizacao_existente)

                precisa_remapear = id_anterior is not None and id_anterior != id_vonzu
                if (
                    not forcar_atualizacao
                    and dados["atualizacao"] == atualizacao_existente
                    and not precisa_remapear
                ):
                    sem_alteracao += 1
                    continue

                prev_entrega_anterior = existente.prev_entrega
                nova_prev_entrega = dados["prev_entrega"]

                if precisa_remapear:
                    remapeamentos.append({
                        "ref": dados.get("pedido") or "",
                        "id_anterior": id_anterior,
                        "id_novo": id_vonzu,
                    })
                    por_trk.pop(id_anterior, None)
                    por_trk[id_vonzu] = existente

                existente.id_vonzu = id_vonzu
                existente.atualizacao = dados["atualizacao"]
                existente.prev_entrega = nova_prev_entrega
                existente.dt_entrega = dados["dt_entrega"]
                existente.estado = dados["estado"]
                existente.volume = dados["volume"]
                existente.nome_dest = dados["nome_dest"]
                existente.email_dest = dados["email_dest"]
                existente.fone_dest = dados["fone_dest"]
                existente.fone_dest2 = dados["fone_dest2"]
                existente.endereco_dest = dados["endereco_dest"]
                existente.codpost_dest = dados["codpost_dest"]
                existente.cidade_dest = dados["cidade_dest"]
                existente.obs = dados["obs"]
                existente.motorista_id = dados["motorista_id"]
                existente.peso = dados["peso"]
                existente.expresso = dados["expresso"]
                pedidos_para_atualizar.append(existente)
                atualizados += 1

                if nova_prev_entrega:
                    tentativa_existente = tentativas_existentes_map.get(
                        (existente.id, nova_prev_entrega)
                    )

                    if tentativa_existente:
                        tentativa_existente.estado = dados["estado"]
                        tentativa_existente.motorista_id = dados["motorista_id"]
                        tentativa_existente.dt_entrega = dados["dt_entrega"]
                        tentativas_para_atualizar.append(tentativa_existente)
                    elif nova_prev_entrega != prev_entrega_anterior:
                        novas_tentativas.append(
                            TentativaEntrega(
                                pedido=existente,
                                data_tentativa=nova_prev_entrega,
                                estado=dados["estado"],
                                motorista_id=dados["motorista_id"],
                                dt_entrega=dados["dt_entrega"],
                                periodo="TARDE",
                            )
                        )
                        tentativas += 1

        if novos_pedidos:
            Pedido.objects.bulk_create(novos_pedidos)
            for p, dados in zip(novos_pedidos, novos_dados):
                if p.prev_entrega:
                    novas_tentativas.append(
                        TentativaEntrega(
                            pedido=p,
                            data_tentativa=p.prev_entrega,
                            estado=p.estado,
                            motorista_id=p.motorista_id,
                            dt_entrega=p.dt_entrega,
                            periodo="TARDE",
                        )
                    )
                    tentativas += 1

        if pedidos_para_atualizar:
            Pedido.objects.bulk_update(pedidos_para_atualizar, CAMPOS_ATUALIZAVEIS)

        if tentativas_para_atualizar:
            TentativaEntrega.objects.bulk_update(
                tentativas_para_atualizar,
                ["estado", "motorista_id", "dt_entrega"],
            )

        if novas_tentativas:
            TentativaEntrega.objects.bulk_create(novas_tentativas)

    return (
        criados,
        atualizados,
        sem_alteracao,
        tentativas,
        remapeamentos,
        ignorados_prioridade_enovo,
    )


def persistir_ou_erro(
    filial,
    linhas_resolvidas,
    *,
    match_por_referencia=False,
    ignorar_criacao_se_referencia_alheia=False,
    forcar_atualizacao=False,
):
    """Wrapper que captura erros de BD/validação e devolve (ok, stats_ou_erros)."""
    try:
        (
            criados,
            atualizados,
            sem_alteracao,
            tentativas,
            remapeamentos,
            ignorados_prioridade_enovo,
        ) = persistir_pedidos_importados(
            filial,
            linhas_resolvidas,
            match_por_referencia=match_por_referencia,
            ignorar_criacao_se_referencia_alheia=ignorar_criacao_se_referencia_alheia,
            forcar_atualizacao=forcar_atualizacao,
        )
        return True, {
            "criados": criados,
            "atualizados": atualizados,
            "sem_alteracao": sem_alteracao,
            "tentativas": tentativas,
            "remapeamentos": remapeamentos,
            "ignorados_prioridade_enovo": ignorados_prioridade_enovo,
        }
    except ValidationError as exc:
        msgs = exc.messages if hasattr(exc, "messages") else [str(exc)]
        if isinstance(msgs, dict):
            flat = []
            for v in msgs.values():
                if isinstance(v, (list, tuple)):
                    flat.extend(str(x) for x in v)
                else:
                    flat.append(str(v))
            msgs = flat
        return False, [str(m) for m in msgs]
    except (IntegrityError, DatabaseError) as exc:
        logger.error(exc, exc_info=True)
        return False, ["Erro ao salvar dados da importação. Tente novamente."]
