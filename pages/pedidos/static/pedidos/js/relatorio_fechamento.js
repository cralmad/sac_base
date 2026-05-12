import {
  getCsrfToken,
  clearMessages,
  definirMensagem,
} from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';

const root = document.getElementById('rf-root');
const URL_BUSCAR = root?.dataset?.urlBuscar ?? '';

const form = document.getElementById('rf-form');
const inpIni = document.getElementById('rf-data-ini');
const inpFim = document.getElementById('rf-data-fim');
const corpo = document.getElementById('rf-corpo');
const tfoot = document.getElementById('rf-tfoot');
const wrap = document.getElementById('rf-tabela-wrapper');
const vazio = document.getElementById('rf-vazio');
const btnImprimir = document.getElementById('rf-btn-imprimir');

/** Separador entre quantidade e valor (Ligeiro/Pesado) e entre lançamentos (Expresso). */
const RF_SEP = ' | ';
/** Entre observação e valor num mesmo lançamento Expresso. */
const RF_SEP_OBS_VALOR = ' — ';

function juntarQuantidadeValor(quantidade, valor) {
  const q = quantidade != null && quantidade !== '' ? String(quantidade) : '';
  const v = valor != null && valor !== '' ? String(valor) : '';
  if (!q && !v) return '';
  if (!q) return v;
  if (!v) return q;
  return `${q}${RF_SEP}${v}`;
}

function formatarLancamentoExpresso(item) {
  const obs = (item.observacao || '').trim();
  const val = item.valor != null ? String(item.valor) : '';
  if (obs) return `${obs}${RF_SEP_OBS_VALOR}${val}`;
  return val || '';
}

function juntarListaExpresso(lista) {
  if (!lista || !lista.length) return '';
  return lista.map(formatarLancamentoExpresso).filter(Boolean).join(RF_SEP);
}

function renderCelulaExpresso(lista) {
  const cell = document.createElement('td');
  cell.className = 'rf-cel-mista';
  if (!lista || !lista.length) {
    cell.textContent = '—';
    return cell;
  }
  cell.textContent = juntarListaExpresso(lista);
  return cell;
}

function renderLinha(linha) {
  const tr = document.createElement('tr');

  const tdData = document.createElement('td');
  tdData.textContent = linha.data || '';
  tr.appendChild(tdData);

  const tdQtd = document.createElement('td');
  tdQtd.textContent = String(linha.qtd_pedidos ?? '');
  tr.appendChild(tdQtd);

  const tdL = document.createElement('td');
  tdL.className = 'rf-cel-mista';
  tdL.textContent = juntarQuantidadeValor(linha.ligeiro_quantidade, linha.ligeiro_valor);
  tr.appendChild(tdL);

  const tdP = document.createElement('td');
  tdP.className = 'rf-cel-mista';
  tdP.textContent = juntarQuantidadeValor(linha.pesado_quantidade, linha.pesado_valor);
  tr.appendChild(tdP);

  const tdRes = document.createElement('td');
  tdRes.textContent = String(linha.pedidos_reservados ?? '');
  tr.appendChild(tdRes);

  const tdExc = document.createElement('td');
  tdExc.textContent = String(linha.pedidos_excedentes ?? '');
  tr.appendChild(tdExc);

  tr.appendChild(renderCelulaExpresso(linha.expresso));

  return tr;
}

function renderRodape(totais) {
  if (!tfoot) return;
  tfoot.replaceChildren();
  if (!totais) {
    tfoot.classList.add('d-none');
    return;
  }
  tfoot.classList.remove('d-none');
  const tr = document.createElement('tr');

  const tdLabel = document.createElement('td');
  tdLabel.textContent = 'Totais';
  tr.appendChild(tdLabel);

  const tdQtd = document.createElement('td');
  tdQtd.textContent = String(totais.qtd_pedidos ?? '');
  tr.appendChild(tdQtd);

  const tdL = document.createElement('td');
  tdL.className = 'rf-cel-mista';
  tdL.textContent = juntarQuantidadeValor(totais.ligeiro_quantidade, totais.ligeiro_valor);
  tr.appendChild(tdL);

  const tdP = document.createElement('td');
  tdP.className = 'rf-cel-mista';
  tdP.textContent = juntarQuantidadeValor(totais.pesado_quantidade, totais.pesado_valor);
  tr.appendChild(tdP);

  const tdRes = document.createElement('td');
  tdRes.textContent = String(totais.pedidos_reservados ?? '');
  tr.appendChild(tdRes);

  const tdExc = document.createElement('td');
  tdExc.className = 'rf-cel-mista';
  tdExc.textContent = juntarQuantidadeValor(totais.pedidos_excedentes, totais.pedidos_excedentes_valor);
  tr.appendChild(tdExc);

  const tdExp = document.createElement('td');
  tdExp.className = 'rf-cel-mista';
  tdExp.textContent = String(totais.expresso_valor ?? '');
  tr.appendChild(tdExp);

  tfoot.appendChild(tr);
}

function renderTabela(linhas, totais) {
  corpo.replaceChildren();
  if (!linhas || !linhas.length) {
    wrap.classList.add('d-none');
    vazio.classList.remove('d-none');
    renderRodape(null);
    btnImprimir?.classList.add('d-none');
    return;
  }
  vazio.classList.add('d-none');
  wrap.classList.remove('d-none');
  linhas.forEach((l) => corpo.appendChild(renderLinha(l)));
  renderRodape(totais || null);
  btnImprimir?.classList.remove('d-none');
}

btnImprimir?.addEventListener('click', () => {
  window.print();
});

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearMessages();
  if (!inpIni.value || !inpFim.value) {
    definirMensagem('erro', 'Informe data inicial e final.', false);
    return;
  }
  AppLoader.show();
  try {
    const resp = await fetch(URL_BUSCAR, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({
        filtros: {
          data_inicial: inpIni.value,
          data_final: inpFim.value,
        },
      }),
    });
    const data = await resp.json();
    if (!data.success) {
      definirMensagem('erro', data.mensagem || 'Erro ao buscar.', false);
      wrap.classList.add('d-none');
      vazio.classList.add('d-none');
      renderRodape(null);
      btnImprimir?.classList.add('d-none');
      return;
    }
    renderTabela(data.linhas, data.totais);
  } catch {
    definirMensagem('erro', 'Falha de rede ao buscar o relatório.', false);
    renderRodape(null);
    btnImprimir?.classList.add('d-none');
  } finally {
    AppLoader.hide();
  }
});
