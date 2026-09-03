import { getCsrfToken, clearMessages, definirMensagem, getOptions } from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';
import { getMultiSelectValues } from '/static/js/smart_filter.js';

const root = document.getElementById('rrz-root');
const URL_BUSCAR = root?.dataset?.urlBuscar ?? '';
const URL_EXPORTAR_XLSX = root?.dataset?.urlExportarXlsx ?? '';

const form = document.getElementById('rrz-form');
const inpIni = document.getElementById('rrz-data-ini');
const inpFim = document.getElementById('rrz-data-fim');
const selZonas = document.getElementById('rrz-zonas');
const btnSelTodos = document.getElementById('rrz-btn-sel-todos');
const btnDesTodos = document.getElementById('rrz-btn-des-todos');
const resultado = document.getElementById('rrz-resultado');
const loader = document.getElementById('rrz-loader');
const vazio = document.getElementById('rrz-vazio');
const tituloPeriodo = document.getElementById('rrz-titulo-periodo');
const btnImprimir = document.getElementById('rrz-btn-imprimir');
const btnExportarXlsx = document.getElementById('rrz-btn-exportar-xlsx');

const PERIODO_MAXIMO_DIAS = 365;
const SEM_ZONA_FILTRO = 'sem';

function dataLocalISO(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function preencherZonas() {
  if (!selZonas) return;
  selZonas.replaceChildren();
  const zonas = getOptions('zonas') || [];
  zonas.forEach((z) => {
    const opt = document.createElement('option');
    opt.value = String(z.value);
    opt.textContent = z.label || String(z.value);
    selZonas.appendChild(opt);
  });
  const optSem = document.createElement('option');
  optSem.value = SEM_ZONA_FILTRO;
  optSem.textContent = 'Sem zona';
  selZonas.appendChild(optSem);
}

function pesoParaNumero(valor) {
  const texto = String(valor ?? '').trim().replace(',', '.');
  if (!texto) return 0;
  const numero = Number.parseFloat(texto);
  return Number.isFinite(numero) ? numero : 0;
}

function formatarPeso(total) {
  return total.toLocaleString('pt-PT', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

function volumePedidoParaNumero(valorVolumes) {
  const texto = String(valorVolumes ?? '').trim();
  if (!texto) return 0;
  const partes = texto.split('/');
  const volumePedido = partes.length >= 2 ? partes[1] : partes[0];
  const numero = Number.parseInt(String(volumePedido).trim(), 10);
  return Number.isFinite(numero) ? numero : 0;
}

function montarFiltros() {
  return {
    data_inicial: inpIni?.value || '',
    data_final: inpFim?.value || '',
    zonas: selZonas ? getMultiSelectValues(selZonas) : [],
  };
}

function diasEntre(iniIso, fimIso) {
  const a = new Date(`${iniIso}T00:00:00`);
  const b = new Date(`${fimIso}T00:00:00`);
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return null;
  return Math.round((b - a) / 86400000);
}

function validarFiltros() {
  if (!inpIni?.value || !inpFim?.value) {
    definirMensagem('erro', 'Informe a data inicial e a data final.', false);
    return false;
  }
  if (inpIni.value > inpFim.value) {
    definirMensagem('erro', 'A data inicial não pode ser maior que a data final.', false);
    return false;
  }
  const dias = diasEntre(inpIni.value, inpFim.value);
  if (dias != null && dias > PERIODO_MAXIMO_DIAS) {
    definirMensagem('erro', `O período máximo é de ${PERIODO_MAXIMO_DIAS} dias.`, false);
    return false;
  }
  return true;
}

function anexarReferencia(td, linha) {
  if (linha.tem_devolucao) {
    const wrap = document.createElement('div');
    wrap.className = 'rrz-ref-wrap rrz-ref-dev';
    const span = document.createElement('span');
    span.textContent = linha.pedido ?? '';
    wrap.appendChild(span);
    const badge = document.createElement('span');
    badge.className = 'rrz-dev-ref';
    badge.textContent = '(Dev)';
    wrap.appendChild(badge);
    td.appendChild(wrap);
    return;
  }
  td.textContent = linha.pedido ?? '';
}

function textoResumoDia(dia, zona) {
  const carros = dia.carros || [];
  const carrosTxt = carros.length ? carros.join(', ') : '—';
  const peso = dia.peso != null
    ? formatarPeso(dia.peso)
    : formatarPeso((dia.linhas || []).reduce((acc, ln) => acc + pesoParaNumero(ln.peso), 0));
  const zonaTxt = zona ? ` • ${zona}` : '';
  return `${dia.data || ''}${zonaTxt} • ${dia.total || 0} pedido(s) • ${peso} kg • ${dia.volumes ?? 0} vol • Carros ${carrosTxt} • Total de carros ${dia.total_carros ?? 0}`;
}

function renderizarLinhaPedido(tbody, linha) {
  const tr = document.createElement('tr');
  if (linha.nao_segue_para_entrega ?? !linha.segue_para_entrega) {
    tr.classList.add('rrz-nao-segue');
  }

  const tdData = document.createElement('td');
  tdData.textContent = linha.data_tentativa ?? '';
  tr.appendChild(tdData);

  const tdCarro = document.createElement('td');
  tdCarro.textContent = linha.carro ?? '';
  tr.appendChild(tdCarro);

  const tdMot = document.createElement('td');
  tdMot.textContent = linha.motorista_nome ?? '';
  tr.appendChild(tdMot);

  const tdRef = document.createElement('td');
  anexarReferencia(tdRef, linha);
  tr.appendChild(tdRef);

  const campos = [
    { val: linha.tipo, cls: linha.tipo === 'R' ? 'rrz-tipo-r' : 'rrz-tipo-e' },
    { val: linha.nome_dest },
    { val: linha.fones },
    { val: linha.endereco_dest },
    { val: linha.cidade_dest },
    { val: linha.codpost_dest },
    {
      val: linha.volumes,
      bold: (() => {
        const p = (linha.volumes || '').split('/');
        return p.length === 2 && parseInt(p[0], 10) < parseInt(p[1], 10);
      })(),
    },
    { val: linha.peso, alertaPeso: !!linha.tem_incidencia_peso_pendente },
    { val: linha.periodo, cls: linha.periodo ? `rrz-periodo-${linha.periodo}` : '' },
    { val: linha.obs_rota, cls: 'rrz-obs' },
  ];

  campos.forEach(({ val, cls, bold, alertaPeso }) => {
    const td = document.createElement('td');
    if (alertaPeso) {
      const spanPeso = document.createElement('span');
      spanPeso.textContent = val ?? '';
      td.appendChild(spanPeso);
      const icon = document.createElement('i');
      icon.className = 'bi bi-exclamation-triangle-fill rrz-peso-alerta';
      icon.title = 'Incidência Peso/Volume não resolvida';
      td.appendChild(icon);
    } else {
      td.textContent = val ?? '';
    }
    if (cls) td.className = cls;
    if (bold) td.style.fontWeight = 'bold';
    tr.appendChild(td);
  });

  tbody.appendChild(tr);
}

function renderizarGrupos(grupos, periodoTexto) {
  resultado.replaceChildren();
  vazio.classList.add('d-none');
  btnImprimir.disabled = true;
  if (btnExportarXlsx) btnExportarXlsx.disabled = true;

  if (!grupos.length) {
    tituloPeriodo.textContent = periodoTexto ? `Período: ${periodoTexto}` : '';
    vazio.classList.remove('d-none');
    return;
  }

  tituloPeriodo.textContent = periodoTexto ? `Período: ${periodoTexto}` : '';

  const cabecalhos = [
    'Data', 'Carro', 'Motorista', 'Referência', 'T', 'Destinatário',
    'Telefone(s)', 'Endereço', 'Cidade', 'C. Postal', 'Vol', 'Peso', 'Per.', 'Obs. Rota',
  ];
  const colCount = cabecalhos.length;

  grupos.forEach((grupo) => {
    const header = document.createElement('div');
    header.className = 'rrz-grupo-header';

    const spanLabel = document.createElement('span');
    spanLabel.textContent = grupo.zona || 'Sem zona';

    const linhasGrupo = grupo.linhas || [];
    const pesoTotalGrupo = linhasGrupo.reduce((acc, linha) => acc + pesoParaNumero(linha.peso), 0);
    const volumeTotalGrupo = linhasGrupo.reduce((acc, linha) => acc + volumePedidoParaNumero(linha.volumes), 0);

    const spanTotal = document.createElement('span');
    spanTotal.className = 'rrz-badge ms-auto';
    spanTotal.textContent = `${grupo.total} pedido(s)`;

    const spanTotais = document.createElement('span');
    spanTotais.className = 'rrz-badge rrz-badge-totais';
    spanTotais.textContent = `${formatarPeso(pesoTotalGrupo)} kg • ${volumeTotalGrupo} vol`;

    header.appendChild(spanLabel);
    header.appendChild(spanTotal);
    header.appendChild(spanTotais);

    const table = document.createElement('table');
    table.className = 'rrz-tabela';
    const thead = document.createElement('thead');
    const trHead = document.createElement('tr');
    cabecalhos.forEach((h) => {
      const th = document.createElement('th');
      th.textContent = h;
      trHead.appendChild(th);
    });
    thead.appendChild(trHead);

    const tbody = document.createElement('tbody');
    const dias = (grupo.dias && grupo.dias.length) ? grupo.dias : [{
      data: '',
      total: linhasGrupo.length,
      peso: pesoTotalGrupo,
      volumes: volumeTotalGrupo,
      carros: [],
      total_carros: 0,
      linhas: linhasGrupo,
    }];

    dias.forEach((dia) => {
      const trSub = document.createElement('tr');
      trSub.className = 'rrz-subgrupo-data';
      const tdSub = document.createElement('td');
      tdSub.colSpan = colCount;
      tdSub.textContent = textoResumoDia(dia, grupo.zona || 'Sem zona');
      trSub.appendChild(tdSub);
      tbody.appendChild(trSub);
      (dia.linhas || []).forEach((linha) => renderizarLinhaPedido(tbody, linha));
    });

    table.appendChild(thead);
    table.appendChild(tbody);

    const tableScroll = document.createElement('div');
    tableScroll.className = 'rrz-tabela-scroll';
    tableScroll.appendChild(table);

    const wrapper = document.createElement('div');
    wrapper.className = 'rrz-grupo';
    wrapper.appendChild(header);
    wrapper.appendChild(tableScroll);
    resultado.appendChild(wrapper);
  });

  let totalPedidos = 0;
  let pesoTotal = 0;
  let volumeTotal = 0;
  grupos.forEach((grupo) => {
    const linhas = grupo.linhas || [];
    totalPedidos += linhas.length;
    linhas.forEach((linha) => {
      pesoTotal += pesoParaNumero(linha.peso);
      volumeTotal += volumePedidoParaNumero(linha.volumes);
    });
  });

  const rodape = document.createElement('div');
  rodape.className = 'rrz-rodape-totais';
  rodape.textContent = `Totais: ${totalPedidos} pedido(s) • ${formatarPeso(pesoTotal)} kg • ${volumeTotal} vol`;
  resultado.appendChild(rodape);

  btnImprimir.disabled = false;
  if (btnExportarXlsx) btnExportarXlsx.disabled = false;
}

async function exportarXlsx() {
  clearMessages();
  if (!validarFiltros()) return;
  if (!URL_EXPORTAR_XLSX) {
    definirMensagem('erro', 'Exportação Excel indisponível.', false);
    return;
  }
  AppLoader.show();
  try {
    const resp = await fetch(URL_EXPORTAR_XLSX, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({ filtros: montarFiltros() }),
    });
    const tipo = resp.headers.get('Content-Type') || '';
    if (!resp.ok || tipo.includes('application/json')) {
      let mensagem = 'Erro ao exportar Excel.';
      try {
        const data = await resp.json();
        mensagem = data.mensagem || mensagem;
      } catch {
        /* resposta não-JSON */
      }
      definirMensagem('erro', mensagem, false);
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rotas_por_zona_${inpIni.value}_${inpFim.value}.xlsx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch {
    definirMensagem('erro', 'Falha de rede ao exportar Excel.', false);
  } finally {
    AppLoader.hide();
  }
}

async function buscar() {
  clearMessages();
  if (!validarFiltros()) return;

  loader.classList.remove('d-none');
  resultado.replaceChildren();
  vazio.classList.add('d-none');
  if (tituloPeriodo) tituloPeriodo.textContent = '';
  btnImprimir.disabled = true;
  if (btnExportarXlsx) btnExportarXlsx.disabled = true;
  AppLoader.show();

  try {
    const resp = await fetch(URL_BUSCAR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ filtros: montarFiltros() }),
    });
    const json = await resp.json();
    if (!json.success) {
      definirMensagem('erro', json.mensagem || 'Erro ao buscar dados.', false);
      return;
    }
    renderizarGrupos(json.grupos || [], json.periodo_texto || '');
  } catch {
    definirMensagem('erro', 'Erro de comunicação com o servidor.', false);
  } finally {
    loader.classList.add('d-none');
    AppLoader.hide();
  }
}

form?.addEventListener('submit', (e) => { e.preventDefault(); buscar(); });
btnImprimir?.addEventListener('click', () => window.print());
btnExportarXlsx?.addEventListener('click', exportarXlsx);
btnSelTodos?.addEventListener('click', () => {
  Array.from(selZonas.options).forEach((o) => { o.selected = true; });
});
btnDesTodos?.addEventListener('click', () => {
  Array.from(selZonas.options).forEach((o) => { o.selected = false; });
});
preencherZonas();
if (inpIni && !inpIni.value) inpIni.value = dataLocalISO();
if (inpFim && !inpFim.value) inpFim.value = dataLocalISO();
