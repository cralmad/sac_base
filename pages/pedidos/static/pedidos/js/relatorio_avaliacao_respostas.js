import {
  getCsrfToken,
  clearMessages,
  definirMensagem,
} from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';

const root = document.getElementById('rar-root');
const URL_BUSCAR = root?.dataset?.urlBuscar ?? '';

const form = document.getElementById('rar-form');
const inpIni = document.getElementById('rar-data-ini');
const inpFim = document.getElementById('rar-data-fim');
const selMot = document.getElementById('rar-motorista');
const chkAgrupar = document.getElementById('rar-agrupar');
const wrapFlat = document.getElementById('rar-wrap-flat');
const wrapGrupos = document.getElementById('rar-wrap-grupos');
const corpoFlat = document.getElementById('rar-corpo-flat');
const vazio = document.getElementById('rar-vazio');
const resumoPeriodo = document.getElementById('rar-resumo-periodo');
const btnImprimir = document.getElementById('rar-btn-imprimir');
const printMeta = document.getElementById('rar-print-meta');

const COL_MAIN = 15;

/** Estado dos comentários antes de expandir para impressão. */
let estadoComentariosAntesPrint = null;

const COLUNAS_FIXAS = [
  { label: 'Pedido', title: 'Número do pedido' },
  { label: 'Prev. entrega', title: 'Data de entrega prevista do pedido' },
  {
    label: 'Motorista',
    title: 'Motorista na tentativa cuja data coincide com a data de entrega prevista',
  },
  { label: 'Respondido', title: 'Data e hora em que o cliente respondeu à pesquisa' },
];

function txt(v) {
  if (v === null || v === undefined) return '';
  return String(v);
}

function appendCelText(tr, text) {
  const td = document.createElement('td');
  td.textContent = text;
  tr.appendChild(td);
}

function renderLinhaBase(linha) {
  const tr = document.createElement('tr');
  tr.className = 'rar-main';
  appendCelText(tr, linha.pedido ?? '');
  appendCelText(tr, linha.prev_entrega_fmt ?? '');
  appendCelText(tr, linha.motorista ?? '');
  appendCelText(tr, linha.respondido_em_fmt ?? '');
  for (let i = 1; i <= 10; i += 1) {
    appendCelText(tr, txt(linha[`p${i}`]));
  }
  const tdObs = document.createElement('td');
  tdObs.className = 'text-center text-nowrap';
  if (linha.tem_comentario) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-sm btn-outline-secondary rar-cmt-btn';
    btn.setAttribute('aria-expanded', 'false');
    btn.title = 'Expandir comentário';
    const icon = document.createElement('i');
    icon.className = 'bi bi-chevron-down';
    btn.appendChild(icon);
    btn.addEventListener('click', () => {
      const detail = tr.nextElementSibling;
      if (!detail || !detail.classList.contains('rar-detail')) return;
      const aberto = detail.classList.toggle('d-none') === false;
      btn.setAttribute('aria-expanded', aberto ? 'true' : 'false');
      icon.className = aberto ? 'bi bi-chevron-up' : 'bi bi-chevron-down';
    });
    tdObs.appendChild(btn);
    tr.appendChild(tdObs);

    const trDetail = document.createElement('tr');
    trDetail.className = 'rar-detail d-none';
    const tdDetail = document.createElement('td');
    tdDetail.colSpan = COL_MAIN;
    tdDetail.textContent = linha.comentario || '';
    trDetail.appendChild(tdDetail);

    return { main: tr, detail: trDetail };
  }
  tdObs.textContent = '—';
  tr.appendChild(tdObs);
  return { main: tr, detail: null };
}

function anexarLinha(container, linha) {
  const { main, detail } = renderLinhaBase(linha);
  container.appendChild(main);
  if (detail) container.appendChild(detail);
}

function criarCabecalhoTabela(perguntasMeta) {
  const trh = document.createElement('tr');
  COLUNAS_FIXAS.forEach(({ label, title }) => {
    const th = document.createElement('th');
    th.scope = 'col';
    th.title = title;
    th.textContent = label;
    trh.appendChild(th);
  });
  (perguntasMeta || []).forEach((p) => {
    const th = document.createElement('th');
    th.scope = 'col';
    if (p.descricao) th.title = p.descricao;
    th.appendChild(document.createTextNode(p.sigla || ''));
    if (p.titulo_curto) {
      const small = document.createElement('small');
      small.textContent = p.titulo_curto;
      th.appendChild(small);
    }
    trh.appendChild(th);
  });
  const thObs = document.createElement('th');
  thObs.scope = 'col';
  thObs.title = 'Comentário opcional do cliente';
  thObs.textContent = 'Obs.';
  trh.appendChild(thObs);
  return trh;
}

function textoTotalGrupo(total) {
  const n = Number(total) || 0;
  return n === 1 ? '1 registo' : `${n} registos`;
}

function renderFlat(linhas) {
  wrapGrupos.classList.add('d-none');
  wrapGrupos.replaceChildren();
  corpoFlat.replaceChildren();
  if (!linhas || !linhas.length) {
    wrapFlat.classList.add('d-none');
    vazio.classList.remove('d-none');
    setBtnImprimirVisivel(false);
    return;
  }
  vazio.classList.add('d-none');
  wrapFlat.classList.remove('d-none');
  linhas.forEach((l) => anexarLinha(corpoFlat, l));
}

function renderGrupos(grupos, perguntasMeta) {
  wrapFlat.classList.add('d-none');
  corpoFlat.replaceChildren();
  wrapGrupos.replaceChildren();
  if (!grupos || !grupos.length) {
    wrapGrupos.classList.add('d-none');
    vazio.classList.remove('d-none');
    setBtnImprimirVisivel(false);
    return;
  }
  vazio.classList.add('d-none');
  wrapGrupos.classList.remove('d-none');

  grupos.forEach((g) => {
    const box = document.createElement('div');
    box.className = 'rar-grupo';
    const head = document.createElement('div');
    head.className = 'rar-grupo-header';
    const totalN = Number(g.total ?? (g.linhas || []).length) || 0;
    const totalTxt = textoTotalGrupo(totalN);
    const nomeMot = g.motorista_nome || '(sem motorista)';
    head.appendChild(document.createTextNode(nomeMot));
    head.appendChild(document.createTextNode(' '));
    const badge = document.createElement('span');
    badge.className = 'rar-badge';
    badge.textContent = totalTxt;
    badge.setAttribute('title', totalTxt);
    head.appendChild(badge);
    box.appendChild(head);

    const scroll = document.createElement('div');
    scroll.className = 'rar-tabela-scroll';
    const table = document.createElement('table');
    table.className = 'rar-tabela table-bordered mb-0';
    const thead = document.createElement('thead');
    thead.appendChild(criarCabecalhoTabela(perguntasMeta));
    table.appendChild(thead);
    const tbody = document.createElement('tbody');
    (g.linhas || []).forEach((l) => anexarLinha(tbody, l));
    table.appendChild(tbody);
    const tfoot = document.createElement('tfoot');
    const trFoot = document.createElement('tr');
    const tdFoot = document.createElement('td');
    tdFoot.colSpan = COL_MAIN;
    tdFoot.textContent = `Total do motorista: ${totalTxt}`;
    trFoot.appendChild(tdFoot);
    tfoot.appendChild(trFoot);
    table.appendChild(tfoot);
    scroll.appendChild(table);
    box.appendChild(scroll);
    wrapGrupos.appendChild(box);
  });
}

function atualizarResumo(meta) {
  if (!resumoPeriodo) return;
  const p = meta?.periodo_texto;
  if (p) {
    resumoPeriodo.textContent = `Período (prev. entrega): ${p} — ${meta.total_linhas ?? 0} registo(s).`;
    resumoPeriodo.classList.remove('d-none');
    return;
  }
  resumoPeriodo.classList.add('d-none');
  resumoPeriodo.textContent = '';
}

function atualizarPrintMeta(meta) {
  if (!printMeta) return;
  const p = meta?.periodo_texto;
  if (!p) {
    printMeta.textContent = '';
    return;
  }
  const mot = selMot?.selectedOptions?.[0]?.text?.trim() || 'Todos os motoristas';
  const agrupar = chkAgrupar?.checked ? 'Sim' : 'Não';
  printMeta.textContent =
    `Respostas à pesquisa — Período (prev. entrega): ${p} — ${meta.total_linhas ?? 0} registo(s) — Motorista: ${mot} — Agrupar: ${agrupar}`;
}

function setBtnImprimirVisivel(visivel) {
  if (!btnImprimir) return;
  btnImprimir.classList.toggle('d-none', !visivel);
}

function temResultadoVisivel() {
  if (vazio && !vazio.classList.contains('d-none')) return false;
  if (wrapFlat && !wrapFlat.classList.contains('d-none')) return true;
  if (wrapGrupos && !wrapGrupos.classList.contains('d-none')) return true;
  return false;
}

function prepararImpressao() {
  estadoComentariosAntesPrint = [];
  document.querySelectorAll('#rar-resultado tr.rar-detail').forEach((tr) => {
    estadoComentariosAntesPrint.push({
      tr,
      hidden: tr.classList.contains('d-none'),
    });
    tr.classList.remove('d-none');
  });
}

function restaurarAposImpressao() {
  if (!estadoComentariosAntesPrint) return;
  estadoComentariosAntesPrint.forEach(({ tr, hidden }) => {
    if (hidden) tr.classList.add('d-none');
  });
  estadoComentariosAntesPrint = null;
  document.querySelectorAll('#rar-resultado tr.rar-main .rar-cmt-btn').forEach((btn) => {
    const tr = btn.closest('tr');
    const detail = tr?.nextElementSibling;
    const aberto = detail && !detail.classList.contains('d-none');
    btn.setAttribute('aria-expanded', aberto ? 'true' : 'false');
    const icon = btn.querySelector('i');
    if (icon) icon.className = aberto ? 'bi bi-chevron-up' : 'bi bi-chevron-down';
  });
}

btnImprimir?.addEventListener('click', () => {
  if (!temResultadoVisivel()) return;
  prepararImpressao();
  window.print();
});

window.addEventListener('beforeprint', () => {
  if (temResultadoVisivel()) prepararImpressao();
});

window.addEventListener('afterprint', restaurarAposImpressao);

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearMessages();
  if (!inpIni.value || !inpFim.value) {
    definirMensagem('erro', 'Informe data inicial e final.', false);
    return;
  }
  AppLoader.show();
  try {
    const filtros = {
      data_inicial: inpIni.value,
      data_final: inpFim.value,
      agrupar_motorista: chkAgrupar?.checked === true,
    };
    if (selMot?.value) {
      filtros.motorista_id = selMot.value;
    }
    const resp = await fetch(URL_BUSCAR, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({ filtros }),
    });
    const data = await resp.json();
    if (!data.success) {
      definirMensagem('erro', data.mensagem || 'Erro ao buscar.', false);
      wrapFlat.classList.add('d-none');
      wrapGrupos.classList.add('d-none');
      vazio.classList.add('d-none');
      atualizarResumo(null);
      atualizarPrintMeta(null);
      setBtnImprimirVisivel(false);
      return;
    }
    const metaResumo = {
      periodo_texto: data.periodo_texto,
      total_linhas: data.total_linhas,
    };
    atualizarResumo(metaResumo);
    atualizarPrintMeta(metaResumo);
    if (data.agrupar_motorista && data.grupos) {
      renderGrupos(data.grupos, data.perguntas_meta);
    } else {
      renderFlat(data.linhas || []);
    }
    setBtnImprimirVisivel(temResultadoVisivel());
  } catch {
    definirMensagem('erro', 'Falha de rede ao buscar o relatório.', false);
    atualizarResumo(null);
    atualizarPrintMeta(null);
    setBtnImprimirVisivel(false);
  } finally {
    AppLoader.hide();
  }
});
