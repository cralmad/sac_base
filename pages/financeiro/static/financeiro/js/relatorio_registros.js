import { getDataBackEnd, getDataset } from '/static/js/sisVar.js';
import { fazerRequisicao } from '/static/js/base.js';
import { AppLoader } from '/static/js/loader.js';

getDataBackEnd();

function getFiliaisEscrita() {
  return getDataset('filiais_escrita', []);
}

function getTipos() {
  return getDataset('tipos_registro_financeiro', []);
}

function getContraparteTipos() {
  return getDataset('contraparte_tipos', []);
}

function getContrapartesPorTipo() {
  return getDataset('contrapartes_por_tipo', {});
}

function getFilialAtivaId() {
  return String(getDataset('filial_ativa_id', '') || '');
}

function isBloquearFilialSelect() {
  return Boolean(getDataset('bloquear_filial_select', false));
}

function getUrlPost() {
  return String(getDataset('url_relatorio_post', '') || '/app/financeiro/relatorio/registros/');
}

const NIVEL_LABEL = {
  filial: 'Filial',
  tipo: 'Tipo',
  vencimento: 'Vencimento',
  contraparte: 'Contraparte',
  ativo: 'Ativo',
};

function fmtDataIsoBr(iso) {
  if (!iso || typeof iso !== 'string') return '';
  const p = iso.split('-');
  if (p.length !== 3) return iso;
  return `${p[2]}/${p[1]}/${p[0]}`;
}

function atualizarCabecalhoImpressao(filtros, agrupamento, stats) {
  const meta = document.getElementById('rel_fin_print_meta');
  if (!meta) return;
  const sel = document.getElementById('rel_fin_filial_id');
  const filialTxt = sel?.selectedOptions?.[0]?.textContent?.trim() || '—';
  const agParts = [];
  if (agrupamento.data_vencimento) agParts.push('Vencimento');
  if (agrupamento.contraparte) agParts.push('Contraparte');
  if (agrupamento.ativo) agParts.push('Ativo');
  const tipoSel = document.getElementById('rel_fin_tipo');
  const tipoTxt = tipoSel?.value
    ? (tipoSel.selectedOptions[0]?.textContent || '').trim()
    : 'Entrada e saída';
  let obs = (filtros.observacao || '').trim();
  if (obs.length > 56) obs = `${obs.slice(0, 53)}…`;
  const partes = [
    filialTxt,
    `${fmtDataIsoBr(filtros.data_emissao_ini)}–${fmtDataIsoBr(filtros.data_emissao_fim)}`,
    tipoTxt,
  ];
  if (agParts.length) partes.push(`Agrup.: ${agParts.join('+')}`);
  if (obs) partes.push(`Obs.: ${obs}`);
  partes.push(
    `Total ${stats.total} · Exibidos ${stats.exibidos}${stats.truncado ? ' (máx. 1000)' : ''}`,
  );
  meta.textContent = partes.join(' · ');
}

function formatarValorBr(num) {
  const n = Number(num);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Soma recursiva dos valores das linhas sob este grupo (filhos ou linhas diretas). */
function totalValorGrupo(node) {
  let t = 0;
  if (node.linhas && node.linhas.length) {
    node.linhas.forEach((row) => {
      const v = Number(row.valor_numero);
      if (Number.isFinite(v)) t += v;
    });
  }
  if (node.filhos && node.filhos.length) {
    node.filhos.forEach((ch) => {
      t += totalValorGrupo(ch);
    });
  }
  return t;
}

function rotuloStatus(st) {
  const map = {
    aberto: 'Aberto',
    parcial: 'Parcial',
    liquidado: 'Liquidado',
    cancelado: 'Cancelado',
  };
  return map[String(st || '').toLowerCase()] || String(st || '—');
}

function espelharDataFimComInicio() {
  const ini = document.getElementById('rel_fin_data_ini');
  const fim = document.getElementById('rel_fin_data_fim');
  if (!ini || !fim) return;
  fim.value = (ini.value || '').trim();
}

function renderizarFiliais() {
  const sel = document.getElementById('rel_fin_filial_id');
  const filiais = getFiliaisEscrita();
  const valor = getFilialAtivaId();
  sel.innerHTML = '<option value="">Selecione</option>';
  filiais.forEach((f) => {
    const o = document.createElement('option');
    o.value = String(f.id);
    o.textContent = `${f.codigo} - ${f.nome}`;
    sel.appendChild(o);
  });
  sel.value = valor || '';
  const bloqueado = isBloquearFilialSelect();
  sel.disabled = bloqueado;
  if (bloqueado && valor) sel.value = valor;
}

function renderizarTipos() {
  const sel = document.getElementById('rel_fin_tipo');
  const tipos = getTipos();
  sel.innerHTML = '<option value="">Entrada e saída</option>';
  tipos.forEach((t) => {
    const o = document.createElement('option');
    o.value = t.value;
    o.textContent = t.label;
    sel.appendChild(o);
  });
}

function renderizarContraparteTipos() {
  const sel = document.getElementById('rel_fin_ct_tipo');
  const tipos = getContraparteTipos();
  sel.innerHTML = '<option value="">Todos</option>';
  tipos.forEach((t) => {
    const o = document.createElement('option');
    o.value = t.value;
    o.textContent = t.label;
    sel.appendChild(o);
  });
}

function renderizarContrapartes() {
  const selTipo = document.getElementById('rel_fin_ct_tipo');
  const sel = document.getElementById('rel_fin_ct_id');
  const tipo = String(selTipo.value || '');
  const porTipo = getContrapartesPorTipo();
  const lista = porTipo[tipo] ?? [];
  sel.innerHTML = '<option value="">Todas</option>';
  lista.forEach((item) => {
    const o = document.createElement('option');
    o.value = String(item.id);
    o.textContent = item.label;
    sel.appendChild(o);
  });
  sel.disabled = !tipo;
}

function mostrarMensagem(tipo, texto) {
  const el = document.getElementById('rel_fin_mensagem');
  el.classList.remove('d-none', 'alert-danger', 'alert-success', 'alert-warning');
  if (tipo === 'erro') el.classList.add('alert-danger');
  else if (tipo === 'ok') el.classList.add('alert-success');
  else el.classList.add('alert-warning');
  el.textContent = texto;
}

function esconderMensagem() {
  const el = document.getElementById('rel_fin_mensagem');
  el.classList.add('d-none');
  el.textContent = '';
}

function montarTabelaLinhas(linhas) {
  const table = document.createElement('table');
  table.className = 'rfin-tabela';
  const thead = document.createElement('thead');
  const trh = document.createElement('tr');
  [
    'Filial',
    'Emissão',
    'ID',
    'Tipo',
    'Ativo',
    'Contraparte',
    'Valor',
    'Observação',
    'Status',
    'Origem',
  ].forEach((h) => {
    const th = document.createElement('th');
    th.textContent = h;
    trh.appendChild(th);
  });
  thead.appendChild(trh);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  linhas.forEach((row) => {
    const tr = document.createElement('tr');
    const tdOrigem = document.createElement('td');
    if (row.origem_tipo === 'manual' && row.url_visualizar_manual) {
      const a = document.createElement('a');
      a.href = row.url_visualizar_manual;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.textContent = 'MANUAL';
      tdOrigem.appendChild(a);
    } else {
      tdOrigem.textContent = row.origem_texto || '—';
    }
    const cells = [
      row.filial_label,
      row.data_emissao_fmt,
      String(row.id),
      row.tipo_label,
      row.ativo_label,
      row.contraparte_label,
      row.valor_fmt,
      row.observacao,
      rotuloStatus(row.status),
    ];
    cells.forEach((text) => {
      const td = document.createElement('td');
      td.textContent = text ?? '';
      tr.appendChild(td);
    });
    tr.appendChild(tdOrigem);
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  return table;
}

function renderGrupo(node, depth) {
  const wrap = document.createElement('div');
  const ehFolhaComTabela = Boolean(node.linhas && node.linhas.length);
  wrap.className = ehFolhaComTabela ? 'rfin-grupo rfin-grupo-folha' : 'rfin-grupo';

  const header = document.createElement('div');
  header.className = depth === 0 ? 'rfin-grupo-header' : 'rfin-grupo-subheader';
  header.classList.add('d-flex', 'flex-wrap', 'align-items-center', 'gap-2');

  const tit = document.createElement('span');
  tit.textContent = node.titulo || '—';
  header.appendChild(tit);

  const nivelKey = node.nivel && NIVEL_LABEL[node.nivel] ? node.nivel : '';
  if (nivelKey) {
    const badge = document.createElement('span');
    badge.className = 'rfin-badge';
    badge.textContent = NIVEL_LABEL[nivelKey];
    header.appendChild(badge);
  }

  if (node.linhas && node.linhas.length) {
    const b = document.createElement('span');
    b.className = 'rfin-badge';
    b.textContent = `${node.linhas.length} registro(s)`;
    header.appendChild(b);
  }

  const totalGrupo = totalValorGrupo(node);
  const badgeTotal = document.createElement('span');
  badgeTotal.className = 'rfin-badge';
  badgeTotal.textContent = `Total: ${formatarValorBr(totalGrupo)}`;
  badgeTotal.title = 'Soma dos valores dos títulos neste grupo';
  header.appendChild(badgeTotal);

  wrap.appendChild(header);

  if (node.linhas && node.linhas.length) {
    const scroll = document.createElement('div');
    scroll.style.overflowX = 'auto';
    scroll.appendChild(montarTabelaLinhas(node.linhas));
    wrap.appendChild(scroll);
  }

  if (node.filhos && node.filhos.length) {
    node.filhos.forEach((ch) => wrap.appendChild(renderGrupo(ch, depth + 1)));
  }

  return wrap;
}

function renderResultado(grupos) {
  const root = document.getElementById('rel_fin_resultado');
  root.innerHTML = '';
  if (!grupos || !grupos.length) {
    const p = document.createElement('p');
    p.className = 'text-muted';
    p.textContent = 'Nenhum registro encontrado para os filtros informados.';
    root.appendChild(p);
    return;
  }
  grupos.forEach((g) => root.appendChild(renderGrupo(g, 0)));
}

document.addEventListener('DOMContentLoaded', () => {
  const btnImprimir = document.getElementById('rel_fin_btn_imprimir');
  const inpDataIni = document.getElementById('rel_fin_data_ini');
  renderizarFiliais();
  renderizarTipos();
  renderizarContraparteTipos();
  renderizarContrapartes();

  inpDataIni?.addEventListener('change', () => {
    espelharDataFimComInicio();
  });

  btnImprimir.addEventListener('click', () => {
    window.print();
  });

  document.getElementById('rel_fin_ct_tipo').addEventListener('change', () => {
    document.getElementById('rel_fin_ct_id').value = '';
    renderizarContrapartes();
  });

  document.getElementById('filtroRelatorioFinanceiro').addEventListener('submit', async (e) => {
    e.preventDefault();
    esconderMensagem();
    const filialId = document.getElementById('rel_fin_filial_id').value.trim();
    if (!filialId) {
      mostrarMensagem('erro', 'Selecione a matriz/filial.');
      return;
    }
    const filtros = {
      filial_id: filialId,
      data_emissao_ini: document.getElementById('rel_fin_data_ini').value,
      data_emissao_fim: document.getElementById('rel_fin_data_fim').value,
      tipo: document.getElementById('rel_fin_tipo').value,
      contraparte_tipo: document.getElementById('rel_fin_ct_tipo').value,
      contraparte_id: document.getElementById('rel_fin_ct_id').value,
      observacao: document.getElementById('rel_fin_obs').value.trim(),
    };
    const agrupamento = {
      data_vencimento: document.getElementById('rel_fin_ag_venc').checked,
      contraparte: document.getElementById('rel_fin_ag_ct').checked,
      ativo: document.getElementById('rel_fin_ag_ativo').checked,
    };
    AppLoader.show();
    const result = await fazerRequisicao(getUrlPost(), { filtros, agrupamento });
    AppLoader.hide();
    const resumo = document.getElementById('rel_fin_resumo');
    if (!result.success) {
      const msg = result.data?.mensagem || result.error || 'Falha ao gerar relatório.';
      mostrarMensagem('erro', msg);
      resumo.classList.add('d-none');
      document.getElementById('rel_fin_resultado').innerHTML = '';
      btnImprimir.disabled = true;
      return;
    }
    const d = result.data;
    renderResultado(d.grupos);
    atualizarCabecalhoImpressao(filtros, agrupamento, {
      total: d.total,
      exibidos: d.exibidos,
      truncado: d.truncado,
    });
    resumo.classList.remove('d-none');
    let txt = `Total no período: ${d.total}. Exibidos: ${d.exibidos}.`;
    if (d.truncado) txt += ' Resultado limitado a 1000 linhas (refine os filtros).';
    resumo.textContent = txt;
    btnImprimir.disabled = false;
  });
});
