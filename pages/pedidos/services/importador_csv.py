import csv
import io
import logging
import re

from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from pages.cad_cliente.models import Cliente
from pages.motorista.models import Motorista
from pages.pedidos.models import Pedido, TentativaEntrega
from sac_base.coercion import parse_date, parse_datetime, parse_decimal, parse_int

from .normalizacao import normalizar_estado

logger = logging.getLogger(__name__)

TIPO_MAP = {
    "delivery": "ENTREGA",
    "pickup": "RECOLHA",
}

# Padrão: DESCRICAO (QTD) (COD_FORNECEDOR)
_RE_PRODUTO = re.compile(r'(.+?)\s+\((\d+)\)\s+\((\d+)\)')


def _parse_description(desc):
    """Retorna lista de dicts {descricao, quantidade, cod_fornecedor} da Description VONZU."""
    if not desc or not desc.strip():
        return []
    desc = desc.strip().lstrip('*')
    result = []
    for m in _RE_PRODUTO.finditer(desc):
        descricao = m.group(1).strip().strip(',').strip()
        if descricao:
            result.append({
                'descricao': descricao,
                'quantidade': int(m.group(2)),
                'cod_fornecedor': m.group(3),
            })
    return result

CAMPOS_ATUALIZAVEIS = [
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


def _decode_csv(conteudo_bytes):
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return conteudo_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Não foi possível decodificar o arquivo CSV.")


def _parse_csv_bytes(conteudo_bytes):
    texto = _decode_csv(conteudo_bytes)
    reader = csv.DictReader(io.StringIO(texto), delimiter=";", quotechar='"')
    return [(i + 2, dict(row)) for i, row in enumerate(reader)]


def _normalizar_linha(num_linha, row):
    """Normaliza e valida uma linha do CSV.

    Retorna (dados_dict, erros_list). Se erros não estiver vazio, dados é None.
    """
    erros = []

    id_vonzu_raw = (row.get("Id") or "").strip()
    try:
        id_vonzu = int(id_vonzu_raw)
    except (ValueError, TypeError):
        erros.append(f"Linha {num_linha}: campo 'Id' inválido — '{id_vonzu_raw}'")
        return None, erros

    tipo_raw = (row.get("*Tipo (delivery|pickup)") or "").strip().lower()
    tipo = TIPO_MAP.get(tipo_raw)
    if not tipo:
        erros.append(f"Linha {num_linha}: tipo inválido — '{tipo_raw}' (esperado: delivery ou pickup)")
        return None, erros

    criado = parse_datetime(row.get("Data criação"), context="csv")
    if criado is None:
        erros.append(f"Linha {num_linha}: 'Data criação' inválida — '{row.get('Data criação')}'")
        return None, erros

    atualizacao = parse_datetime(row.get("Data actualização"), context="csv")
    if atualizacao is None:
        erros.append(f"Linha {num_linha}: 'Data actualização' inválida — '{row.get('Data actualização')}'")
        return None, erros

    return {
        "id_vonzu": id_vonzu,
        "pedido": (row.get("Referência") or "").strip() or None,
        "tipo": tipo,
        "criado": criado,
        "atualizacao": atualizacao,
        "prev_entrega": parse_date(row.get("*Data")),
        "dt_entrega": parse_date(row.get("Data entrega")),
        "estado": normalizar_estado(row.get("Estado")),
        "volume": parse_int(row.get("Embalagens"), context="csv"),
        "nome_dest": (row.get("*Nome destinatário") or "").strip() or None,
        "email_dest": (row.get("Email destinatário") or "").strip() or None,
        "fone_dest": (row.get("Telefone destinatário") or "").strip() or None,
        "fone_dest2": (row.get("Telefone destinatário 2") or "").strip() or None,
        "endereco_dest": (row.get("*Rua entrega") or "").strip() or None,
        "codpost_dest": (row.get("*Código postal entrega") or "").strip() or None,
        "cidade_dest": (row.get("*Cidade entrega") or "").strip() or None,
        "obs": (row.get("Comentários") or "").strip() or None,
        "nome_cliente_csv": (row.get("Nome cliente") or "").strip() or None,
        "nome_motorista_csv": (row.get("Nome utilizador condutor") or "").strip() or None,
        "peso": parse_decimal(row.get("Peso"), context="csv"),
        "expresso": str(row.get("Expresso") or "").strip().lower() in {"1", "true", "sim", "s", "yes", "y"},
        "description_raw": (row.get("Description") or "").strip(),
    }, []


def _deduplicar(linhas_norm):
    """Mantém apenas a primeira ocorrência de cada id_vonzu no arquivo."""
    vistos = set()
    dedup = []
    ignoradas = 0
    for num_linha, dados in linhas_norm:
        key = dados["id_vonzu"]
        if key not in vistos:
            vistos.add(key)
            dedup.append((num_linha, dados))
        else:
            ignoradas += 1
    return dedup, ignoradas


def _resolver_fks(filial, linhas_dedup, ids_sem_alteracao=None):
    """Resolve cliente e motorista pelo campo 'codigo' em lote.

    Retorna (linhas_com_ids, avisos). FKs não resolvidas são salvas como None.
    Avisos só são emitidos para linhas que serão efetivamente escritas; linhas
    cujo id_vonzu esteja em `ids_sem_alteracao` são ignoradas nos avisos.
    """
    codigos_cliente = {
        d["nome_cliente_csv"].upper()
        for _, d in linhas_dedup
        if d["nome_cliente_csv"]
    }
    codigos_motorista = {
        d["nome_motorista_csv"].upper()
        for _, d in linhas_dedup
        if d["nome_motorista_csv"]
    }

    clientes_map = {
        c.codigo.upper(): c.id
        for c in Cliente.objects.filter(
            codigo__in=codigos_cliente,
            is_deleted=False,
        )
        if c.codigo
    }
    motoristas_map = {
        m.codigo.upper(): m.id
        for m in Motorista.objects.filter(
            filial=filial,
            codigo__in=codigos_motorista,
            is_deleted=False,
        )
        if m.codigo
    }

    ids_sem_alteracao = ids_sem_alteracao or set()
    avisos = []
    resultado = []
    for num_linha, dados in linhas_dedup:
        dados = dict(dados)
        nome_cli = dados.pop("nome_cliente_csv", None)
        nome_mot = dados.pop("nome_motorista_csv", None)
        sera_escrito = dados["id_vonzu"] not in ids_sem_alteracao

        cliente_id = None
        if nome_cli:
            cliente_id = clientes_map.get(nome_cli.upper())
            if cliente_id is None and sera_escrito:
                avisos.append(
                    f"  Linha {num_linha:>4} | id_vonzu={dados['id_vonzu']:>10} | "
                    f"cliente \"{nome_cli}\" não localizado pelo código — salvo como null"
                )

        motorista_id = None
        if nome_mot:
            motorista_id = motoristas_map.get(nome_mot.upper())
            if motorista_id is None and sera_escrito:
                avisos.append(
                    f"  Linha {num_linha:>4} | id_vonzu={dados['id_vonzu']:>10} | "
                    f"motorista \"{nome_mot}\" não localizado pelo código — salvo como null"
                )

        dados["cliente_id"] = cliente_id
        dados["motorista_id"] = motorista_id
        resultado.append((num_linha, dados))

    return resultado, avisos


def _validar_data_unica_para_analise(linhas_resolvidas):
    datas_prev_entrega = {dados.get("prev_entrega") for _, dados in linhas_resolvidas}
    if len(datas_prev_entrega) != 1 or None in datas_prev_entrega:
        return None
    return next(iter(datas_prev_entrega))


def _coletar_pedidos_movimentacao_ausentes_no_arquivo(filial, data_base, id_vonzus_importados):
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


def _montar_dados_volumes_agrupados(linhas_norm):
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

        artigos_linha = _parse_description(dados.get("description_raw", ""))
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
            "referencia": agrupados[id_vonzu]["referencia"],
            "peso": agrupados[id_vonzu]["peso"],
            "volume": agrupados[id_vonzu]["volume"],
            "artigos": agrupados[id_vonzu]["artigos"],
        }
        for id_vonzu in ordem_ids
        if agrupados[id_vonzu]["artigos"]
    ]
    return dados_volumes, detalhes


def _gerar_relatorio(nome_arquivo, filial, total_lidas, ignoradas,
                     criados, atualizados, sem_alteracao, tentativas, avisos,
                     analise_movimentacao_ativada=False,
                     data_analise=None,
                     pedidos_mov_ausentes_no_arquivo=None):
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


def importar_csv(conteudo_bytes, filial, nome_arquivo, analisar_movimentacoes_dia=False):
    """Importa um arquivo CSV VONZU para a filial indicada.

    Regras:
    - Transação atômica: qualquer erro de validação aborta toda a importação.
    - Deduplicação por id_vonzu: mantém apenas a primeira ocorrência do arquivo.
    - Upsert: pedidos novos são inseridos; existentes são atualizados somente
      se 'Data actualização' do CSV diferir do valor já gravado.
        - Tentativas criadas apenas para: novo pedido OU alteração de '*Data'.
        - Ao atualizar pedido, se já existir movimentação na data de Prev. Entrega,
            o estado da movimentação também é atualizado.
    - FKs (cliente/motorista) resolvidas pelo campo 'codigo'; não resolvidas
      são salvas como null e registradas no relatório.

    Retorna dict com chaves: sucesso, erros, relatorio, stats.
    """
    try:
        linhas_raw = _parse_csv_bytes(conteudo_bytes)
    except ValueError:
        return {
            "sucesso": False,
            "erros": ["Erro ao ler CSV: conteúdo inválido ou codificação não suportada."],
            "relatorio": "",
            "stats": {},
        }

    if not linhas_raw:
        return {"sucesso": False, "erros": ["O arquivo CSV está vazio ou sem dados."], "relatorio": "", "stats": {}}

    total_lidas = len(linhas_raw)

    # Validar todas as linhas — qualquer erro aborta a importação
    todos_erros = []
    linhas_norm = []
    for num_linha, row in linhas_raw:
        dados, erros = _normalizar_linha(num_linha, row)
        if erros:
            todos_erros.extend(erros)
        else:
            linhas_norm.append((num_linha, dados))

    if todos_erros:
        return {"sucesso": False, "erros": todos_erros, "relatorio": "", "stats": {}}

    linhas_dedup, ignoradas = _deduplicar(linhas_norm)

    # Pré-identifica pedidos já existentes com mesmo atualizacao (sem_alteracao)
    # para suprimir avisos de FK em linhas que não serão escritas.
    id_vonzus_all = [d["id_vonzu"] for _, d in linhas_dedup]
    dados_por_id_vonzu = {d["id_vonzu"]: d for _, d in linhas_dedup}
    ids_sem_alteracao = set()
    for p in Pedido.objects.filter(filial=filial, id_vonzu__in=id_vonzus_all).only("id_vonzu", "atualizacao"):
        atz = p.atualizacao
        if atz is not None and atz.tzinfo is None:
            atz = timezone.make_aware(atz)
        dados_csv = dados_por_id_vonzu.get(p.id_vonzu)
        if dados_csv and dados_csv["atualizacao"] == atz:
            ids_sem_alteracao.add(p.id_vonzu)

    linhas_resolvidas, avisos_fk = _resolver_fks(filial, linhas_dedup, ids_sem_alteracao)
    data_analise_movimentacao = None
    pedidos_mov_ausentes_no_arquivo = []
    if analisar_movimentacoes_dia:
        data_analise_movimentacao = _validar_data_unica_para_analise(linhas_resolvidas)
        if not data_analise_movimentacao:
            return {
                "sucesso": False,
                "erros": [
                    "Para analisar movimentações do dia, o arquivo deve conter pedidos com apenas uma data válida em '*Data'.",
                ],
                "relatorio": "",
                "stats": {},
            }

    criados = atualizados = sem_alteracao = tentativas = 0

    try:
        with transaction.atomic():
            id_vonzus = [d["id_vonzu"] for _, d in linhas_resolvidas]
            existentes = {
                p.id_vonzu: p
                for p in Pedido.objects.filter(filial=filial, id_vonzu__in=id_vonzus)
            }
            datas_prev_por_pedido_id = {}
            for _num_linha, dados in linhas_resolvidas:
                pedido_existente = existentes.get(dados["id_vonzu"])
                data_prev = dados.get("prev_entrega")
                if pedido_existente and data_prev:
                    datas_prev_por_pedido_id.setdefault(pedido_existente.id, set()).add(data_prev)

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

            for _num_linha, dados in linhas_resolvidas:
                id_vonzu = dados["id_vonzu"]
                existente = existentes.get(id_vonzu)

                if existente is None:
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

                    if dados["atualizacao"] == atualizacao_existente:
                        sem_alteracao += 1
                        continue

                    prev_entrega_anterior = existente.prev_entrega
                    nova_prev_entrega = dados["prev_entrega"]

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
                TentativaEntrega.objects.bulk_update(tentativas_para_atualizar, ["estado", "motorista_id", "dt_entrega"])

            if novas_tentativas:
                TentativaEntrega.objects.bulk_create(novas_tentativas)

    except (ValidationError, IntegrityError, DatabaseError) as exc:
        logger.error(exc, exc_info=True)
        return {
            "sucesso": False,
            "erros": ["Erro ao salvar dados da importação. Tente novamente."],
            "relatorio": "",
            "stats": {},
        }

    if analisar_movimentacoes_dia:
        id_vonzus_importados = {dados["id_vonzu"] for _, dados in linhas_resolvidas}
        pedidos_mov_ausentes_no_arquivo = _coletar_pedidos_movimentacao_ausentes_no_arquivo(
            filial=filial,
            data_base=data_analise_movimentacao,
            id_vonzus_importados=id_vonzus_importados,
        )

    relatorio_volumes = _gerar_relatorio(
        nome_arquivo=nome_arquivo,
        filial=filial,
        total_lidas=total_lidas,
        ignoradas=ignoradas,
        criados=criados,
        atualizados=atualizados,
        sem_alteracao=sem_alteracao,
        tentativas=tentativas,
        avisos=avisos_fk,
        analise_movimentacao_ativada=analisar_movimentacoes_dia,
        data_analise=data_analise_movimentacao,
        pedidos_mov_ausentes_no_arquivo=pedidos_mov_ausentes_no_arquivo,
    )

    # Relatório de volumes: todos os pedidos que têm Description no CSV
    dados_volumes, _detalhes_linhas_volumes = _montar_dados_volumes_agrupados(linhas_norm)

    return {
        "sucesso": True,
        "erros": [],
        "relatorio": relatorio_volumes,
        "stats": {
            "total_lidas": total_lidas,
            "ignoradas": ignoradas,
            "criados": criados,
            "atualizados": atualizados,
            "sem_alteracao": sem_alteracao,
            "tentativas": tentativas,
            "avisos_fk": len(avisos_fk),
        },
        "dados_volumes": dados_volumes,
    }
