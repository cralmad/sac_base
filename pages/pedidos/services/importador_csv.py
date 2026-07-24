import csv
import io

from django.utils import timezone

from pages.cad_cliente.models import Cliente
from pages.motorista.models import Motorista
from pages.pedidos.models import Pedido
from sac_base.coercion import parse_date, parse_datetime, parse_decimal, parse_int

from .importador_persistencia import (
    coletar_pedidos_movimentacao_ausentes_no_arquivo,
    gerar_relatorio_importacao,
    montar_dados_volumes_agrupados,
    persistir_ou_erro,
    validar_data_unica_para_analise,
)
from .normalizacao import normalizar_estado

TIPO_MAP = {
    "delivery": "ENTREGA",
    "pickup": "RECOLHA",
}

# Reexport para testes/compat
from .importador_persistencia import parse_description as _parse_description  # noqa: E402,F401


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


def parse_csv_artigos_sem_persistir(conteudo_bytes):
    """Parseia CSV VONZU e retorna artigos agrupados sem persistir em BD."""
    try:
        linhas_raw = _parse_csv_bytes(conteudo_bytes)
    except ValueError:
        return {
            "sucesso": False,
            "erros": ["Erro ao ler CSV: conteúdo inválido ou codificação não suportada."],
            "pedidos": [],
        }

    if not linhas_raw:
        return {
            "sucesso": False,
            "erros": ["O arquivo CSV está vazio ou sem dados."],
            "pedidos": [],
        }

    todos_erros = []
    linhas_norm = []
    for num_linha, row in linhas_raw:
        dados, erros = _normalizar_linha(num_linha, row)
        if erros:
            todos_erros.extend(erros)
        else:
            linhas_norm.append((num_linha, dados))

    if todos_erros:
        return {
            "sucesso": False,
            "erros": todos_erros,
            "pedidos": [],
        }

    dados_volumes, _detalhes = montar_dados_volumes_agrupados(linhas_norm)
    return {
        "sucesso": True,
        "erros": [],
        "pedidos": dados_volumes,
    }


def importar_csv(
    conteudo_bytes,
    filial,
    nome_arquivo,
    analisar_movimentacoes_dia=False,
    forcar_atualizacao=False,
):
    """Importa um arquivo CSV VONZU para a filial indicada.

    Regras:
    - Transação atômica: qualquer erro de validação aborta toda a importação.
    - Deduplicação por id_vonzu: mantém apenas a primeira ocorrência do arquivo.
    - Upsert: pedidos novos são inseridos; existentes são atualizados somente
      se 'Data actualização' do CSV diferir do valor já gravado (salvo
      ``forcar_atualizacao=True``).
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

    id_vonzus_all = [d["id_vonzu"] for _, d in linhas_dedup]
    dados_por_id_vonzu = {d["id_vonzu"]: d for _, d in linhas_dedup}
    ids_sem_alteracao = set()
    if not forcar_atualizacao:
        for p in Pedido.objects.filter(filial=filial, id_vonzu__in=id_vonzus_all).only(
            "id_vonzu", "atualizacao"
        ):
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
        data_analise_movimentacao = validar_data_unica_para_analise(linhas_resolvidas)
        if not data_analise_movimentacao:
            return {
                "sucesso": False,
                "erros": [
                    "Para analisar movimentações do dia, o arquivo deve conter pedidos com apenas uma data válida em '*Data'.",
                ],
                "relatorio": "",
                "stats": {},
            }

    ok, resultado = persistir_ou_erro(
        filial,
        linhas_resolvidas,
        ignorar_criacao_se_referencia_alheia=True,
        forcar_atualizacao=forcar_atualizacao,
    )
    if not ok:
        return {"sucesso": False, "erros": resultado, "relatorio": "", "stats": {}}

    criados = resultado["criados"]
    atualizados = resultado["atualizados"]
    sem_alteracao = resultado["sem_alteracao"]
    tentativas = resultado["tentativas"]
    ignorados_prio = resultado.get("ignorados_prioridade_enovo") or []

    if analisar_movimentacoes_dia:
        id_vonzus_importados = {dados["id_vonzu"] for _, dados in linhas_resolvidas}
        pedidos_mov_ausentes_no_arquivo = coletar_pedidos_movimentacao_ausentes_no_arquivo(
            filial=filial,
            data_base=data_analise_movimentacao,
            id_vonzus_importados=id_vonzus_importados,
        )

    relatorio = gerar_relatorio_importacao(
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
        ignorados_prioridade_enovo=ignorados_prio,
    )

    dados_volumes, _detalhes = montar_dados_volumes_agrupados(linhas_norm)

    return {
        "sucesso": True,
        "erros": [],
        "relatorio": relatorio,
        "stats": {
            "total_lidas": total_lidas,
            "ignoradas": ignoradas,
            "criados": criados,
            "atualizados": atualizados,
            "sem_alteracao": sem_alteracao,
            "tentativas": tentativas,
            "avisos_fk": len(avisos_fk),
            "ignorados_prioridade_enovo": len(ignorados_prio),
        },
        "dados_volumes": dados_volumes,
    }
