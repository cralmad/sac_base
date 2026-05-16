/**
 * Dashboard de avaliações: KPIs + Chart.js (funil, Likert, por pergunta).
 * Chart global a partir do script em base (jsDelivr).
 */
import {
  getCsrfToken,
  clearMessages,
  definirMensagem,
} from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';

const Chart = window.Chart;

if (window.ChartDataLabels && Chart?.register) {
  Chart.register(window.ChartDataLabels);
}

const root = document.getElementById('dash-root');
const URL_BUSCAR = root?.dataset?.urlBuscar ?? '';

const form = document.getElementById('dash-form');
const inpIni = document.getElementById('dash-data-ini');
const inpFim = document.getElementById('dash-data-fim');
const selMot = document.getElementById('dash-motorista');
const resumo = document.getElementById('dash-resumo');
const conteudo = document.getElementById('dash-conteudo');
const vazio = document.getElementById('dash-vazio');
const kpiFunil = document.getElementById('dash-kpi-funil');
const kpiExtra = document.getElementById('dash-kpi-extra');
const wrapPerguntas = document.getElementById('dash-perguntas');

const chartInstances = [];

function destroyCharts() {
  while (chartInstances.length) {
    const c = chartInstances.pop();
    try {
      c.destroy();
    } catch {
      /* ignore */
    }
  }
}

function metaDescricao(perguntasMeta, campo) {
  const m = (perguntasMeta || []).find((x) => x.campo === campo);
  return m?.descricao || campo;
}

function metaSigla(perguntasMeta, campo) {
  const m = (perguntasMeta || []).find((x) => x.campo === campo);
  return m?.sigla || campo.toUpperCase();
}

const LIKERT_GLOBAL_CAMPOS = ['p3', 'p4', 'p6', 'p9'];

function pctTexto(valor, total) {
  if (!total || total <= 0 || !valor) return '0%';
  return `${((Number(valor) / Number(total)) * 100).toFixed(1)}%`;
}

/** Rótulos visíveis em donut: contagem + percentual. */
function pluginDatalabelsDonut() {
  return {
    font: { weight: '600', size: 11 },
    textAlign: 'center',
    color(ctx) {
      const bg = ctx.dataset.backgroundColor?.[ctx.dataIndex];
      return bg === '#ffc107' ? '#212529' : '#fff';
    },
    formatter(value, ctx) {
      const sum = ctx.dataset.data.reduce((a, b) => a + Number(b), 0);
      if (!value) return '';
      return `${value}\n(${pctTexto(value, sum)})`;
    },
  };
}

/** Rótulos em barras verticais: contagem + % do total informado. */
function pluginDatalabelsBarCount(total) {
  return {
    anchor: 'end',
    align: 'top',
    color: '#212529',
    font: { size: 10, weight: '600' },
    formatter(value) {
      if (!value) return '';
      return `${value}\n(${pctTexto(value, total)})`;
    },
  };
}

function textoAjudaMediaGlobalLikert(perguntasMeta) {
  const linhas = [
    'Média ponderada pelas respostas das perguntas:',
    ...LIKERT_GLOBAL_CAMPOS.map((c) => {
      const sigla = metaSigla(perguntasMeta, c);
      const desc = metaDescricao(perguntasMeta, c);
      return `${sigla} — ${desc}`;
    }),
  ];
  return linhas.join('\n');
}

function appendKpi(container, titulo, valor, subtitulo, { tituloHelp } = {}) {
  const col = document.createElement('div');
  col.className = 'col';
  const card = document.createElement('div');
  card.className = 'card h-100 text-center';
  const body = document.createElement('div');
  body.className = 'card-body py-2';
  const t = document.createElement('div');
  t.className = 'small text-muted text-uppercase d-flex align-items-center justify-content-center gap-1 flex-wrap';
  t.appendChild(document.createTextNode(titulo));
  if (tituloHelp) {
    const hint = document.createElement('span');
    hint.className = 'dash-kpi-hint text-primary';
    hint.setAttribute('tabindex', '0');
    hint.setAttribute('role', 'img');
    hint.setAttribute('title', tituloHelp);
    hint.setAttribute('aria-label', tituloHelp);
    const icon = document.createElement('i');
    icon.className = 'bi bi-exclamation-circle-fill';
    icon.setAttribute('aria-hidden', 'true');
    hint.appendChild(icon);
    t.appendChild(hint);
  }
  const v = document.createElement('div');
  v.className = 'display-6';
  v.textContent = valor;
  body.appendChild(t);
  body.appendChild(v);
  if (subtitulo) {
    const s = document.createElement('div');
    s.className = 'small text-secondary mt-1';
    s.textContent = subtitulo;
    body.appendChild(s);
  }
  card.appendChild(body);
  col.appendChild(card);
  container.appendChild(col);
}

function renderFunilDonut(funil) {
  const canvas = document.getElementById('chart-funil');
  if (!canvas || !Chart) return;
  const nEmail = funil?.n_email_enviado ?? 0;
  const nOk = funil?.n_respondido_e_enviado ?? 0;
  const pend = Math.max(0, nEmail - nOk);
  const legendaComTotais = (nome, n) => {
    const pct = pctTexto(n, nEmail);
    return nEmail > 0 ? `${nome}: ${n} (${pct})` : `${nome}: ${n}`;
  };
  if (nEmail <= 0) {
    chartInstances.push(
      new Chart(canvas, {
        type: 'doughnut',
        data: { labels: ['Sem envios no período'], datasets: [{ data: [1], backgroundColor: ['#dee2e6'] }] },
        options: {
          plugins: {
            legend: { position: 'bottom' },
            datalabels: { display: false },
          },
        },
      }),
    );
    return;
  }
  chartInstances.push(
    new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: [legendaComTotais('Respondidos', nOk), legendaComTotais('Pendentes', pend)],
        datasets: [
          {
            data: [nOk, pend],
            backgroundColor: ['#198754', '#ffc107'],
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' },
          datalabels: pluginDatalabelsDonut(),
          tooltip: { enabled: true },
        },
      },
    }),
  );
}

/** Barras HTML (descrição completa à esquerda; Chart.js corta rótulos longos no eixo Y). */
function renderLikertCompare(likertComparativo, perguntasMeta) {
  const root = document.getElementById('dash-likert-compare');
  if (!root) return;
  root.replaceChildren();
  const list = likertComparativo || [];
  if (!list.length) {
    const vazio = document.createElement('p');
    vazio.className = 'text-muted small mb-0';
    vazio.textContent = 'Sem dados Likert no período.';
    root.appendChild(vazio);
    return;
  }

  list.forEach((item) => {
    const row = document.createElement('div');
    row.className = 'dash-likert-row';

    const label = document.createElement('div');
    label.className = 'dash-likert-label';
    const siglaEl = document.createElement('span');
    siglaEl.className = 'dash-likert-sigla';
    siglaEl.textContent = `${metaSigla(perguntasMeta, item.campo)} — `;
    label.appendChild(siglaEl);
    label.appendChild(document.createTextNode(metaDescricao(perguntasMeta, item.campo)));

    const barCol = document.createElement('div');
    barCol.className = 'dash-likert-bar-col';

    const track = document.createElement('div');
    track.className = 'dash-likert-track';
    const media = item.media != null ? Number(item.media) : 0;
    const pct = Math.min(100, Math.max(0, (media / 5) * 100));
    const bar = document.createElement('div');
    bar.className = 'dash-likert-bar';
    bar.style.width = `${pct}%`;
    track.appendChild(bar);

    const metaEl = document.createElement('span');
    metaEl.className = 'dash-likert-meta';
    const mediaTxt = item.media != null ? Number(item.media).toFixed(2) : '—';
    const n = item.n != null ? item.n : '—';
    metaEl.textContent = `${mediaTxt} (n=${n})`;

    barCol.appendChild(track);
    barCol.appendChild(metaEl);
    row.appendChild(label);
    row.appendChild(barCol);
    root.appendChild(row);
  });

  const scaleRow = document.createElement('div');
  scaleRow.className = 'dash-likert-row dash-likert-scale-row';
  scaleRow.appendChild(document.createElement('div'));
  const scaleWrap = document.createElement('div');
  scaleWrap.className = 'dash-likert-bar-col';
  const scale = document.createElement('div');
  scale.className = 'dash-likert-scale';
  [0, 1, 2, 3, 4, 5].forEach((n) => {
    const tick = document.createElement('span');
    tick.textContent = String(n);
    scale.appendChild(tick);
  });
  scaleWrap.appendChild(scale);
  scaleRow.appendChild(scaleWrap);
  root.appendChild(scaleRow);
}

function renderPerguntaCard(item, perguntasMeta) {
  const col = document.createElement('div');
  col.className = 'col-12 col-md-6 col-xl-4';
  const card = document.createElement('div');
  card.className = 'card h-100 dash-pergunta-card';
  const head = document.createElement('div');
  head.className = 'card-header';
  head.textContent = `${metaSigla(perguntasMeta, item.campo)} — ${metaDescricao(perguntasMeta, item.campo)}`;
  const body = document.createElement('div');
  body.className = 'card-body';
  const wrap = document.createElement('div');
  wrap.className = 'dash-chart-wrap';
  const canvas = document.createElement('canvas');
  canvas.id = `chart-${item.campo}`;
  wrap.appendChild(canvas);
  body.appendChild(wrap);
  card.appendChild(head);
  card.appendChild(body);
  col.appendChild(card);
  wrapPerguntas.appendChild(col);

  if (!Chart) return;

  if (item.tipo === 'likert_1_5') {
    const abs = item.distribuicao_abs || {};
    const labels = ['1', '2', '3', '4', '5'];
    const vals = labels.map((k) => abs[Number(k)] || 0);
    const totalN = item.n || vals.reduce((a, b) => a + b, 0);
    chartInstances.push(
      new Chart(canvas, {
        type: 'bar',
        data: {
          labels,
          datasets: [{ label: 'Respostas', data: vals, backgroundColor: '#6f42c1' }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 24 } },
          plugins: {
            title: {
              display: true,
              text: item.media != null ? `Média: ${item.media} (n=${item.n})` : `n=${item.n}`,
            },
            legend: { display: false },
            datalabels: pluginDatalabelsBarCount(totalN),
            tooltip: { enabled: true },
          },
          scales: {
            x: { title: { display: true, text: 'Nota' } },
            y: { beginAtZero: true, ticks: { precision: 0 } },
          },
        },
      }),
    );
    return;
  }

  renderDonutCategorico(item, canvas, body);
}

function renderDonutCategorico(item, canvas, body) {
  const abs = item.distribuicao_abs || {};
  const totalN = item.n || Object.values(abs).reduce((a, b) => a + Number(b), 0);
  const labels = Object.keys(abs);
  const vals = labels.map((k) => abs[k]);
  const legendaCateg = labels.map((nome, i) => `${nome}: ${vals[i]} (${pctTexto(vals[i], totalN)})`);
  const coresSimNao = { Sim: '#198754', Nao: '#dc3545', Não: '#dc3545' };
  const coresPadrao = ['#198754', '#dc3545', '#6c757d', '#fd7e14', '#0dcaf0', '#6f42c1'];
  const bg = labels.map((nome, i) => coresSimNao[nome] || coresPadrao[i % coresPadrao.length]);

  const tituloGrafico =
    item.tipo === 'sim_nao_na'
      ? `Análise Sim/Não (n=${totalN}; N/A excluído)`
      : `n=${totalN}`;

  if (!labels.length) {
    chartInstances.push(
      new Chart(canvas, {
        type: 'doughnut',
        data: {
          labels: ['Sem respostas Sim/Não'],
          datasets: [{ data: [1], backgroundColor: ['#dee2e6'] }],
        },
        options: {
          plugins: {
            legend: { position: 'bottom' },
            title: { display: true, text: tituloGrafico },
            datalabels: { display: false },
          },
        },
      }),
    );
  } else {
    chartInstances.push(
      new Chart(canvas, {
        type: 'doughnut',
        data: {
          labels: legendaCateg,
          datasets: [{ data: vals, backgroundColor: bg, borderWidth: 1 }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            title: { display: true, text: tituloGrafico },
            legend: { position: 'bottom' },
            datalabels: pluginDatalabelsDonut(),
            tooltip: { enabled: true },
          },
        },
      }),
    );
  }

  if (item.tipo === 'sim_nao_na' && item.na_informativo) {
    const info = document.createElement('p');
    info.className = 'small text-muted text-center mb-0 mt-2 px-1';
    const q = Number(item.na_informativo.quantidade ?? 0);
    const pct = item.na_informativo.pct_sobre_total_pergunta;
    const pctTxt = pct != null ? ` — ${pct}% das respostas à pergunta` : '';
    info.textContent = `N/A (informativo, fora da análise): ${q}${pctTxt}`;
    body.appendChild(info);
  }
}

function renderDashboard(data) {
  destroyCharts();
  kpiFunil.replaceChildren();
  kpiExtra.replaceChildren();
  wrapPerguntas.replaceChildren();

  const f = data.funil || {};
  const meta = data.perguntas_meta || [];

  appendKpi(kpiFunil, 'E-mails enviados', String(f.n_email_enviado ?? 0), '');
  appendKpi(
    kpiFunil,
    'Taxa resposta',
    f.taxa_resposta_sobre_enviadas_pct != null ? `${f.taxa_resposta_sobre_enviadas_pct}%` : '—',
    'Sobre enviados',
  );
  appendKpi(
    kpiFunil,
    'Não responderam',
    f.pct_nao_respondeu_sobre_enviadas != null ? `${f.pct_nao_respondeu_sobre_enviadas}%` : '—',
    'Pareto (cauda)',
  );

  appendKpi(kpiExtra, 'Total respostas', String(data.total_respondidas ?? 0), '');
  appendKpi(
    kpiExtra,
    'Com comentário',
    String(data.com_comentario ?? 0),
    data.pct_comentario != null ? `${data.pct_comentario}%` : '',
  );
  appendKpi(
    kpiExtra,
    'Média global Likert',
    data.media_global_likert != null ? String(data.media_global_likert) : '—',
    'Nível de Qualidade Percebida',
    { tituloHelp: textoAjudaMediaGlobalLikert(meta) },
  );
  renderFunilDonut(f);
  renderLikertCompare(data.likert_comparativo, meta);

  (data.perguntas_resumo || []).forEach((item) => {
    renderPerguntaCard(item, meta);
  });
}

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearMessages();
  if (!inpIni.value || !inpFim.value) {
    definirMensagem('erro', 'Informe data inicial e final.', false);
    return;
  }
  if (!Chart) {
    definirMensagem('erro', 'Chart.js não carregou.', false);
    return;
  }
  AppLoader.show();
  try {
    const filtros = {
      data_inicial: inpIni.value,
      data_final: inpFim.value,
    };
    if (selMot?.value) filtros.motorista_id = selMot.value;
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
      conteudo.classList.add('d-none');
      vazio.classList.add('d-none');
      destroyCharts();
      return;
    }
    const tem =
      (data.funil?.n_email_enviado > 0) ||
      (data.total_respondidas > 0) ||
      (data.perguntas_resumo || []).some((p) => p.n > 0);
    if (!tem) {
      conteudo.classList.add('d-none');
      vazio.classList.remove('d-none');
      resumo.textContent = data.periodo_texto || '';
      resumo.classList.remove('d-none');
      destroyCharts();
      return;
    }
    vazio.classList.add('d-none');
    conteudo.classList.remove('d-none');
    resumo.textContent = `Período (prev. entrega): ${data.periodo_texto || ''}`;
    resumo.classList.remove('d-none');
    renderDashboard(data);
  } catch {
    definirMensagem('erro', 'Falha de rede.', false);
    destroyCharts();
  } finally {
    AppLoader.hide();
  }
});
