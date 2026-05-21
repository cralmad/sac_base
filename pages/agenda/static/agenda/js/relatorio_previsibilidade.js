import {
  getCsrfToken,
  clearMessages,
  definirMensagem,
} from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';

const form = document.getElementById('ag-prev-form');
const inpIni = document.getElementById('ag-prev-ini');
const inpFim = document.getElementById('ag-prev-fim');
const timeline = document.getElementById('ag-prev-timeline');
const vazio = document.getElementById('ag-prev-vazio');
const resumo = document.getElementById('ag-prev-resumo');

const URL_BUSCAR = '/app/agenda/relatorio/previsibilidade/';
const URL_CONFIRMAR = '/app/agenda/manual/confirmar-ocorrencia/';
const URL_MATERIALIZAR = '/app/agenda/manual/materializar/';

function formatarDataBr(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

function textoTotais(bloco) {
  const qtd = bloco?.total_registros ?? 0;
  const partes = [`${qtd} registro${qtd === 1 ? '' : 's'}`];
  if (bloco?.total_valor) {
    partes.push(`valor ${bloco.total_valor}`);
  } else if (Array.isArray(bloco?.totais_valor_subgrupos) && bloco.totais_valor_subgrupos.length) {
    const detalhe = bloco.totais_valor_subgrupos
      .map((s) => `${s.label}: ${s.total_valor}`)
      .join(' | ');
    partes.push(detalhe);
  }
  return partes.join(' · ');
}

function criarBadge(texto, cls) {
  const span = document.createElement('span');
  span.className = `badge ${cls} me-1`;
  span.textContent = texto;
  return span;
}

function criarCelula(texto, cls = '') {
  const td = document.createElement('td');
  if (cls) td.className = cls;
  td.textContent = texto ?? '';
  return td;
}

function renderLinhaEvento(ev) {
  const tr = document.createElement('tr');
  if (ev.status === 'concluido') tr.classList.add('table-secondary');

  const tdTipo = document.createElement('td');
  tdTipo.className = 'text-nowrap';
  const tipoCls = ev.tipo_dado === 'concreto' ? 'badge-tipo-concreto' : 'badge-tipo-flutuante';
  tdTipo.appendChild(
    criarBadge(ev.tipo_dado === 'concreto' ? 'Concreto' : 'Flutuante', tipoCls),
  );
  if (ev.status) {
    const stCls = ev.status === 'concluido' ? 'badge-status-concluido' : 'badge-status-pendente';
    tdTipo.appendChild(
      criarBadge(ev.status === 'concluido' ? 'Concluído' : 'Pendente', stCls),
    );
  }
  tr.appendChild(tdTipo);

  tr.appendChild(criarCelula(ev.titulo || ''));
  tr.appendChild(criarCelula(ev.valor || '—', 'text-end text-nowrap'));
  tr.appendChild(criarCelula(ev.observacao || '—', 'small'));

  const tdAcoes = document.createElement('td');
  tdAcoes.className = 'text-nowrap text-end';
  const acoes = ev.acoes || {};

  if (ev.url) {
    const a = document.createElement('a');
    a.href = ev.url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.className = 'btn btn-sm btn-outline-primary me-1';
    a.textContent = 'Abrir';
    tdAcoes.appendChild(a);
  }
  if (acoes.pode_confirmar) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-sm btn-success me-1';
    btn.textContent = 'Confirmar';
    btn.addEventListener('click', () => acaoConfirmar(ev));
    tdAcoes.appendChild(btn);
  }
  if (acoes.pode_materializar) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-sm btn-primary';
    btn.textContent = 'Materializar';
    btn.addEventListener('click', () => acaoMaterializar(ev));
    tdAcoes.appendChild(btn);
  }
  tr.appendChild(tdAcoes);
  return tr;
}

function criarTabelaEventos() {
  const table = document.createElement('table');
  table.className = 'table table-sm table-hover ag-prev-tabela mb-0';
  const thead = document.createElement('thead');
  thead.className = 'table-light';
  const hr = document.createElement('tr');
  ['Tipo', 'Título', 'Valor', 'Observação', 'Ações'].forEach((col) => {
    const th = document.createElement('th');
    th.textContent = col;
    if (col === 'Valor' || col === 'Ações') th.className = 'text-end';
    hr.appendChild(th);
  });
  thead.appendChild(hr);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  table.appendChild(tbody);
  return { table, tbody };
}

function renderCabecalhoGrupo(tag, cls, titulo, totais) {
  const el = document.createElement(tag);
  el.className = cls;
  const strong = document.createElement('strong');
  strong.textContent = titulo;
  el.appendChild(strong);
  const meta = document.createElement('span');
  meta.className = 'ag-prev-totais ms-2';
  meta.textContent = textoTotais(totais);
  el.appendChild(meta);
  return el;
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    credentials: 'same-origin',
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}

async function acaoConfirmar(ev) {
  if (!window.confirm('Confirmar conclusão desta ocorrência?')) return;
  const { res, data } = await postJson(URL_CONFIRMAR, {
    agenda_manual_id: ev.agenda_manual_id,
    data_ocorrencia: ev.data,
  });
  if (!res.ok || data.success === false) {
    definirMensagem('erro', data.mensagem || data.erros || 'Falha ao confirmar.', false);
    return;
  }
  definirMensagem('sucesso', data.mensagem || 'Confirmado.');
  form.requestSubmit();
}

async function acaoMaterializar(ev) {
  if (!window.confirm('Materializar esta ocorrência (gerar lançamento)?')) return;
  const { res, data } = await postJson(URL_MATERIALIZAR, {
    agenda_manual_id: ev.agenda_manual_id,
    data_ocorrencia: ev.data,
  });
  if (!res.ok || data.success === false) {
    definirMensagem('erro', data.mensagem || data.erros || 'Falha ao materializar.', false);
    return;
  }
  definirMensagem('sucesso', data.mensagem || 'Materializado.');
  form.requestSubmit();
}

function renderTimeline(payload) {
  timeline.replaceChildren();
  const agrupamentos = payload.agrupamentos || [];
  if (!agrupamentos.length) {
    vazio.classList.remove('d-none');
    return;
  }
  vazio.classList.add('d-none');

  agrupamentos.forEach((dia) => {
    const secDia = document.createElement('section');
    secDia.className = 'ag-prev-dia';
    secDia.appendChild(
      renderCabecalhoGrupo('h3', '', formatarDataBr(dia.data), dia),
    );

    (dia.categorias || []).forEach((cat) => {
      const blocoCat = document.createElement('div');
      blocoCat.className = 'ag-prev-categoria';
      blocoCat.appendChild(
        renderCabecalhoGrupo('h4', '', cat.categoria_label || cat.categoria, cat),
      );

      (cat.subgrupos || []).forEach((sub) => {
        const blocoSub = document.createElement('div');
        blocoSub.className = 'ag-prev-subgrupo';
        blocoSub.appendChild(
          renderCabecalhoGrupo('h5', '', sub.label || sub.chave, sub),
        );
        const { table, tbody } = criarTabelaEventos();
        (sub.eventos || []).forEach((ev) => tbody.appendChild(renderLinhaEvento(ev)));
        blocoSub.appendChild(table);
        blocoCat.appendChild(blocoSub);
      });
      secDia.appendChild(blocoCat);
    });
    timeline.appendChild(secDia);
  });

  const r = payload.resumo || {};
  if (resumo) {
    resumo.textContent = `Total: ${r.total ?? 0} — Flutuantes: ${r.por_tipo_dado?.flutuante ?? 0} — Concretos: ${r.por_tipo_dado?.concreto ?? 0}`;
    resumo.classList.remove('d-none');
  }
}

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearMessages();
  AppLoader.show();
  try {
    const { res, data } = await postJson(URL_BUSCAR, {
      filtros: {
        data_inicio: inpIni?.value,
        data_fim: inpFim?.value,
      },
    });
    if (!res.ok || !data.success) {
      definirMensagem('erro', data.mensagem || data.erros || 'Não foi possível gerar o relatório.', false);
      return;
    }
    renderTimeline(data);
  } finally {
    AppLoader.hide();
  }
});
