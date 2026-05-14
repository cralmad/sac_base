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

function appendKpi(container, titulo, valor, subtitulo) {
  const col = document.createElement('div');
  col.className = 'col';
  const card = document.createElement('div');
  card.className = 'card h-100 text-center';
  const body = document.createElement('div');
  body.className = 'card-body py-2';
  const t = document.createElement('div');
  t.className = 'small text-muted text-uppercase';
  t.textContent = titulo;
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
  if (nEmail <= 0) {
    chartInstances.push(
      new Chart(canvas, {
        type: 'doughnut',
        data: { labels: ['Sem envios no período'], datasets: [{ data: [1], backgroundColor: ['#dee2e6'] }] },
        options: { plugins: { legend: { position: 'bottom' } } },
      }),
    );
    return;
  }
  chartInstances.push(
    new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: ['Respondidos (após envio)', 'Pendentes'],
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
          tooltip: {
            callbacks: {
              label(ctx) {
                const t = ctx.dataset.data.reduce((a, b) => a + b, 0);
                const n = ctx.raw;
                const p = t ? ((n / t) * 100).toFixed(1) : '0';
                return `${ctx.label}: ${n} (${p}%)`;
              },
            },
          },
        },
      },
    }),
  );
}

function renderLikertCompare(likertComparativo, perguntasMeta) {
  const canvas = document.getElementById('chart-likert-compare');
  if (!canvas || !Chart) return;
  const list = likertComparativo || [];
  const labels = list.map((x) => `${metaSigla(perguntasMeta, x.campo)} (${x.campo})`);
  const data = list.map((x) => (x.media != null ? Number(x.media) : 0));
  if (!list.length) {
    chartInstances.push(
      new Chart(canvas, {
        type: 'bar',
        data: { labels: ['—'], datasets: [{ data: [0], backgroundColor: ['#dee2e6'] }] },
        options: { indexAxis: 'y', plugins: { legend: { display: false } } },
      }),
    );
    return;
  }
  chartInstances.push(
    new Chart(canvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Média (1–5)',
            data,
            backgroundColor: '#0d6efd',
            borderRadius: 4,
          },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { min: 0, max: 5, ticks: { stepSize: 1 } },
        },
        plugins: { legend: { display: false } },
      },
    }),
  );
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
          plugins: {
            title: {
              display: true,
              text: item.media != null ? `Média: ${item.media} (n=${item.n})` : `n=${item.n}`,
            },
            legend: { display: false },
          },
          scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
        },
      }),
    );
    return;
  }

  const abs = item.distribuicao_abs || {};
  const labels = Object.keys(abs);
  const vals = labels.map((k) => abs[k]);
  const colors = ['#198754', '#dc3545', '#6c757d', '#fd7e14', '#0dcaf0', '#6f42c1'];
  const bg = labels.map((_, i) => colors[i % colors.length]);
  chartInstances.push(
    new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{ data: vals, backgroundColor: bg, borderWidth: 1 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: { display: true, text: `n=${item.n}` },
          legend: { position: 'bottom' },
        },
      },
    }),
  );
}

function renderDashboard(data) {
  destroyCharts();
  kpiFunil.replaceChildren();
  kpiExtra.replaceChildren();
  wrapPerguntas.replaceChildren();

  const f = data.funil || {};
  appendKpi(kpiFunil, 'E-mails enviados', String(f.n_email_enviado ?? 0), 'No período (prev. entrega)');
  appendKpi(kpiFunil, 'Respondidos (após envio)', String(f.n_respondido_e_enviado ?? 0), '');
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

  appendKpi(kpiExtra, 'Total respostas', String(data.total_respondidas ?? 0), 'Com respondido_em');
  appendKpi(
    kpiExtra,
    'Com comentário',
    String(data.com_comentario ?? 0),
    data.pct_comentario != null ? `${data.pct_comentario}%` : '',
  );
  appendKpi(kpiExtra, 'Sem motorista (tentativa)', String(data.n_sem_motorista ?? 0), 'Na data prevista');
  appendKpi(
    kpiExtra,
    'Média global Likert',
    data.media_global_likert != null ? String(data.media_global_likert) : '—',
    'P3,P4,P6,P9 ponderada',
  );

  const meta = data.perguntas_meta || [];
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
