import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from pages.cad_cliente.models import Cliente
from pages.motorista.models import Motorista
from pages.pedidos.models import Pedido, TentativaEntrega

from .normalizacao import normalizar_estado

TIPO_MAP = {
    "delivery": "ENTREGA",
    "pickup": "RECOLHA",
}

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


def _parse_datetime(valor):
    if not valor or not valor.strip():
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            naive = datetime.strptime(valor.strip(), fmt)
            return timezone.make_aware(naive)
        except ValueError:
            continue
    return None


def _parse_date(valor):
    if not valor or not valor.strip():
        return None
    try:
        return datetime.strptime(valor.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_decimal(valor):
    if not valor or not valor.strip():
        return None
    try:
        return Decimal(valor.strip().replace(",", "."))
    except InvalidOperation:
        return None


def _parse_int(valor):
    if not valor or not valor.strip():
        return None
    try:
        return int(float(valor.strip().replace(",", ".")))
    except (ValueError, TypeError):
        return None


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

    criado = _parse_datetime(row.get("Data criação"))
    if criado is None:
        erros.append(f"Linha {num_linha}: 'Data criação' inválida — '{row.get('Data criação')}'")
        return None, erros

    atualizacao = _parse_datetime(row.get("Data actualização"))
    if atualizacao is None:
        erros.append(f"Linha {num_linha}: 'Data actualização' inválida — '{row.get('Data actualização')}'")
        return None, erros

    return {
        "id_vonzu": id_vonzu,
        "pedido": (row.get("Referência") or "").strip() or None,
        "tipo": tipo,
        "criado": criado,
        "atualizacao": atualizacao,
        "prev_entrega": _parse_date(row.get("*Data")),
        "dt_entrega": _parse_date(row.get("Data entrega")),
        "estado": normalizar_estado(row.get("Estado")),
        "volume": _parse_int(row.get("Embalagens")),
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
        "peso": _parse_decimal(row.get("Peso")),
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


def _resolver_fks(filial, linhas_dedup):
    """Resolve cliente e motorista pelo campo 'codigo' em lote.

    Retorna (linhas_com_ids, avisos). FKs não resolvidas são salvas como None.
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

    avisos = []
    resultado = []
    for num_linha, dados in linhas_dedup:
        dados = dict(dados)
        nome_cli = dados.pop("nome_cliente_csv", None)
        nome_mot = dados.pop("nome_motorista_csv", None)

        cliente_id = None
        if nome_cli:
            cliente_id = clientes_map.get(nome_cli.upper())
            if cliente_id is None:
                avisos.append(
                    f"  Linha {num_linha:>4} | id_vonzu={dados['id_vonzu']:>10} | "
                    f"cliente \"{nome_cli}\" não localizado pelo código — salvo como null"
                )

        motorista_id = None
        if nome_mot:
            motorista_id = motoristas_map.get(nome_mot.upper())
            if motorista_id is None:
                avisos.append(
                    f"  Linha {num_linha:>4} | id_vonzu={dados['id_vonzu']:>10} | "
                    f"motorista \"{nome_mot}\" não localizado pelo código — salvo como null"
                )

        dados["cliente_id"] = cliente_id
        dados["motorista_id"] = motorista_id
        resultado.append((num_linha, dados))

    return resultado, avisos


def _gerar_relatorio(nome_arquivo, filial, total_lidas, ignoradas,
                     criados, atualizados, sem_alteracao, tentativas, avisos):
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
    return "\n".join(linhas)


def importar_csv(conteudo_bytes, filial, nome_arquivo):
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
    except Exception as exc:
        return {"sucesso": False, "erros": [f"Erro ao ler CSV: {exc}"], "relatorio": "", "stats": {}}

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
    linhas_resolvidas, avisos_fk = _resolver_fks(filial, linhas_dedup)

    criados = atualizados = sem_alteracao = tentativas = 0

    try:
        with transaction.atomic():
            id_vonzus = [d["id_vonzu"] for _, d in linhas_resolvidas]
            existentes = {
                p.id_vonzu: p
                for p in Pedido.objects.filter(filial=filial, id_vonzu__in=id_vonzus)
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
                    pedidos_para_atualizar.append(existente)
                    atualizados += 1

                    if nova_prev_entrega:
                        tentativa_existente = TentativaEntrega.objects.filter(
                            pedido=existente,
                            data_tentativa=nova_prev_entrega,
                        ).first()

                        if tentativa_existente:
                            tentativa_existente.estado = dados["estado"]
                            tentativa_existente.dt_entrega = dados["dt_entrega"]
                            tentativas_para_atualizar.append(tentativa_existente)
                        elif nova_prev_entrega != prev_entrega_anterior:
                            novas_tentativas.append(
                                TentativaEntrega(
                                    pedido=existente,
                                    data_tentativa=nova_prev_entrega,
                                    estado=dados["estado"],
                                    dt_entrega=dados["dt_entrega"],
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
                                dt_entrega=p.dt_entrega,
                            )
                        )
                        tentativas += 1

            if pedidos_para_atualizar:
                Pedido.objects.bulk_update(pedidos_para_atualizar, CAMPOS_ATUALIZAVEIS)

            if tentativas_para_atualizar:
                TentativaEntrega.objects.bulk_update(tentativas_para_atualizar, ["estado", "dt_entrega"])

            if novas_tentativas:
                TentativaEntrega.objects.bulk_create(novas_tentativas)

    except Exception as exc:
        return {"sucesso": False, "erros": [f"Erro ao salvar dados: {exc}"], "relatorio": "", "stats": {}}

    relatorio = _gerar_relatorio(
        nome_arquivo=nome_arquivo,
        filial=filial,
        total_lidas=total_lidas,
        ignoradas=ignoradas,
        criados=criados,
        atualizados=atualizados,
        sem_alteracao=sem_alteracao,
        tentativas=tentativas,
        avisos=avisos_fk,
    )

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
        },
    }
