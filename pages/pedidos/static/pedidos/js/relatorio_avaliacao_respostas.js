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

const COL_MAIN = 15;

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

function renderFlat(linhas) {
  wrapGrupos.classList.add('d-none');
  wrapGrupos.replaceChildren();
  corpoFlat.replaceChildren();
  if (!linhas || !linhas.length) {
    wrapFlat.classList.add('d-none');
    vazio.classList.remove('d-none');
    return;
  }
  vazio.classList.add('d-none');
  wrapFlat.classList.remove('d-none');
  linhas.forEach((l) => anexarLinha(corpoFlat, l));
}

function renderGrupos(grupos) {
  wrapFlat.classList.add('d-none');
  corpoFlat.replaceChildren();
  wrapGrupos.replaceChildren();
  if (!grupos || !grupos.length) {
    wrapGrupos.classList.add('d-none');
    vazio.classList.remove('d-none');
    return;
  }
  vazio.classList.add('d-none');
  wrapGrupos.classList.remove('d-none');

  grupos.forEach((g) => {
    const box = document.createElement('div');
    box.className = 'rar-grupo';
    const head = document.createElement('div');
    head.className = 'rar-grupo-header';
    head.textContent = g.motorista_nome || '(sem motorista)';
    box.appendChild(head);

    const scroll = document.createElement('div');
    scroll.className = 'rar-tabela-scroll';
    const table = document.createElement('table');
    table.className = 'rar-tabela table-bordered mb-0';
    const thead = document.createElement('thead');
    const trh = document.createElement('tr');
    ['Pedido', 'Prev. entrega', 'Motorista', 'Respondido', 'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8', 'P9', 'P10', 'Obs.'].forEach((label) => {
      const th = document.createElement('th');
      th.scope = 'col';
      th.textContent = label;
      trh.appendChild(th);
    });
    thead.appendChild(trh);
    table.appendChild(thead);
    const tbody = document.createElement('tbody');
    (g.linhas || []).forEach((l) => anexarLinha(tbody, l));
    table.appendChild(tbody);
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
      return;
    }
    atualizarResumo({
      periodo_texto: data.periodo_texto,
      total_linhas: data.total_linhas,
    });
    if (data.agrupar_motorista && data.grupos) {
      renderGrupos(data.grupos);
    } else {
      renderFlat(data.linhas || []);
    }
  } catch {
    definirMensagem('erro', 'Falha de rede ao buscar o relatório.', false);
    atualizarResumo(null);
  } finally {
    AppLoader.hide();
  }
});
