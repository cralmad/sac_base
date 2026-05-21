/**
 * Subformulário de payload para materialização financeiro.registro_financeiro_manual.
 * Reutiliza hierarquia de plano e padrão de contraparte do cadastro manual (sem duplicar persistência).
 */
import { initHierarchicalSelects } from '/static/js/conditional_select.js';
import { initSmartInputs } from '/static/js/input_rules.js';

const PREFIX = 'payload-fin-';

function classTipoParaPlano(tipo) {
  if (tipo === 'ENTRADA') return 'receita';
  if (tipo === 'SAIDA') return 'despesa';
  return '';
}

function buildPlanHierarchy(tipo, planos) {
  const classe = classTipoParaPlano(tipo);
  const nivel2 = planos.filter((p) => Number(p.nivel) === 2 && p.tipo_classificacao === classe);
  const nivel3 = planos.filter((p) => Number(p.nivel) === 3 && p.tipo_classificacao === classe);
  const nivel4 = planos.filter((p) => Number(p.nivel) === 4 && p.tipo_classificacao === classe);
  const byPai3 = nivel3.reduce((acc, item) => {
    const key = String(item.pai_id || '');
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});
  const byPai4 = nivel4.reduce((acc, item) => {
    const key = String(item.pai_id || '');
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});
  const hierarchy = {};
  nivel2.forEach((n2) => {
    const nodeN2 = { label: n2.nome, children: {} };
    (byPai3[String(n2.id)] || []).forEach((n3) => {
      const nodeN3 = { label: n3.nome, children: {} };
      (byPai4[String(n3.id)] || []).forEach((n4) => {
        nodeN3.children[String(n4.id)] = { label: n4.nome };
      });
      nodeN2.children[String(n3.id)] = nodeN3;
    });
    hierarchy[String(n2.id)] = nodeN2;
  });
  return hierarchy;
}

function resolverPlanoCascataPorFolha(planoContasId, planos) {
  const byId = Object.fromEntries(planos.map((p) => [String(p.id), p]));
  let atual = byId[String(planoContasId)];
  if (!atual) return { plano_n2_id: '', plano_n3_id: '', plano_n4_id: '' };
  const n4 = atual.nivel === 4 ? atual : null;
  if (!n4) return { plano_n2_id: '', plano_n3_id: '', plano_n4_id: '' };
  const n3 = byId[String(n4.pai_id)];
  const n2 = n3 ? byId[String(n3.pai_id)] : null;
  return {
    plano_n2_id: n2 ? String(n2.id) : '',
    plano_n3_id: n3 ? String(n3.id) : '',
    plano_n4_id: String(n4.id),
  };
}

function criarCampoSelect(root, { col, label, name, required }) {
  const wrap = document.createElement('div');
  wrap.className = col;
  const lbl = document.createElement('label');
  lbl.className = 'form-label mb-0';
  lbl.htmlFor = `${PREFIX}${name}`;
  lbl.textContent = label;
  const sel = document.createElement('select');
  sel.className = 'form-select form-select-sm';
  sel.name = name;
  sel.id = `${PREFIX}${name}`;
  if (required) sel.required = true;
  wrap.appendChild(lbl);
  wrap.appendChild(sel);
  root.appendChild(wrap);
  return sel;
}

function lerPayloadDoSubform(root) {
  const get = (name) => root.querySelector(`[name="${name}"]`)?.value ?? '';
  const valorRaw = get('valor').trim();
  const valorFlutuante = valorRaw === '' || valorRaw === '0' || valorRaw === '0,00' || valorRaw === '0,0';
  return {
    tipo: get('tipo'),
    valor: valorFlutuante ? '' : valorRaw,
    valor_flutuante: valorFlutuante,
    plano_n2_id: get('plano_n2_id') || null,
    plano_n3_id: get('plano_n3_id') || null,
    plano_n4_id: get('plano_n4_id') || null,
    plano_contas_id: get('plano_n4_id') || null,
    contraparte_tipo: get('contraparte_tipo'),
    contraparte_id: get('contraparte_id') || null,
    observacao: get('observacao'),
  };
}

function preencherContrapartes(root, datasets, payload, bloqueado) {
  const tipoSel = root.querySelector('[name="contraparte_tipo"]');
  const idSel = root.querySelector('[name="contraparte_id"]');
  if (!tipoSel || !idSel) return;
  const tipos = datasets.contraparte_tipos || [];
  const porTipo = datasets.contrapartes_por_tipo || {};
  tipoSel.innerHTML = '<option value="">Selecione</option>';
  tipos.forEach((t) => {
    const o = document.createElement('option');
    o.value = t.value;
    o.textContent = t.label;
    tipoSel.appendChild(o);
  });
  tipoSel.value = String(payload.contraparte_tipo ?? '');
  const lista = porTipo[String(payload.contraparte_tipo)] || [];
  idSel.innerHTML = '<option value="">Selecione</option>';
  lista.forEach((item) => {
    const o = document.createElement('option');
    o.value = String(item.id);
    o.textContent = item.label;
    idSel.appendChild(o);
  });
  const cid = String(payload.contraparte_id ?? '');
  idSel.value = lista.some((x) => String(x.id) === cid) ? cid : '';
  idSel.disabled = bloqueado || !payload.contraparte_tipo;
  tipoSel.disabled = bloqueado;
}

function rehidratarPlano(root, payload, planos) {
  const cascata = payload.plano_n4_id
    ? {
      plano_n2_id: payload.plano_n2_id,
      plano_n3_id: payload.plano_n3_id,
      plano_n4_id: payload.plano_n4_id,
    }
    : resolverPlanoCascataPorFolha(payload.plano_contas_id || payload.plano_n4_id, planos);
  const s2 = root.querySelector('[name="plano_n2_id"]');
  const s3 = root.querySelector('[name="plano_n3_id"]');
  const s4 = root.querySelector('[name="plano_n4_id"]');
  if (cascata.plano_n2_id && s2) {
    s2.value = cascata.plano_n2_id;
    s2.dispatchEvent(new Event('change', { bubbles: true }));
  }
  if (cascata.plano_n3_id && s3) {
    s3.value = cascata.plano_n3_id;
    s3.dispatchEvent(new Event('change', { bubbles: true }));
  }
  if (cascata.plano_n4_id && s4) s4.value = cascata.plano_n4_id;
}

/**
 * @param {HTMLElement} root - #payload-subform
 * @param {{ payload: object, datasets: object, bloqueado: boolean, onChange: (partial: object) => void }} opts
 */
export function renderAgendaPayloadFinanceiro(root, { payload, datasets, bloqueado, onChange }) {
  root.replaceChildren();
  const row = document.createElement('div');
  row.className = 'row g-2';
  root.appendChild(row);

  const planos = datasets.planos_contas || [];
  const tipos = datasets.tipos_registro_financeiro || [];

  const tipoSel = criarCampoSelect(row, {
    col: 'col-12 col-md-3',
    label: 'Tipo',
    name: 'tipo',
    required: true,
  });
  tipoSel.innerHTML = '<option value="">Selecione</option>';
  tipos.forEach((t) => {
    const o = document.createElement('option');
    o.value = t.value;
    o.textContent = t.label;
    tipoSel.appendChild(o);
  });
  tipoSel.value = String(payload.tipo ?? '');

  criarCampoSelect(row, {
    col: 'col-12 col-md-3',
    label: 'Tipo de contraparte',
    name: 'contraparte_tipo',
    required: true,
  });
  criarCampoSelect(row, {
    col: 'col-12 col-md-6',
    label: 'Contraparte',
    name: 'contraparte_id',
    required: true,
  });

  const planoN2 = criarCampoSelect(row, {
    col: 'col-12 col-md-4',
    label: 'Setor',
    name: 'plano_n2_id',
    required: true,
  });
  planoN2.dataset.hierarchy = 'planoConta';
  planoN2.dataset.hierarchyRoot = 'true';
  planoN2.innerHTML = '<option value="">Selecione</option>';

  const planoN3 = criarCampoSelect(row, {
    col: 'col-12 col-md-4',
    label: 'Subsetor',
    name: 'plano_n3_id',
    required: true,
  });
  planoN3.dataset.hierarchy = 'planoConta';
  planoN3.dataset.selectDepends = 'plano_n2_id';

  const planoN4 = criarCampoSelect(row, {
    col: 'col-12 col-md-4',
    label: 'Ativo',
    name: 'plano_n4_id',
    required: true,
  });
  planoN4.dataset.hierarchy = 'planoConta';
  planoN4.dataset.selectDepends = 'plano_n2_id,plano_n3_id';

  const wrapValor = document.createElement('div');
  wrapValor.className = 'col-12 col-md-3';
  const lblValor = document.createElement('label');
  lblValor.className = 'form-label mb-0';
  lblValor.htmlFor = `${PREFIX}valor`;
  lblValor.textContent = 'Valor';
  const hint = document.createElement('span');
  hint.className = 'text-muted small d-block';
  hint.textContent = 'Vazio ou 0 = valor flutuante na ocorrência';
  const inpValor = document.createElement('input');
  inpValor.type = 'text';
  inpValor.name = 'valor';
  inpValor.id = `${PREFIX}valor`;
  inpValor.className = 'form-control form-control-sm smart-input';
  inpValor.dataset.allow = '0-9,';
  if (payload.valor_flutuante || payload.valor === '' || payload.valor === null) {
    inpValor.value = '';
  } else {
    inpValor.value = String(payload.valor ?? '');
  }
  wrapValor.appendChild(lblValor);
  wrapValor.appendChild(hint);
  wrapValor.appendChild(inpValor);
  row.appendChild(wrapValor);

  const wrapObs = document.createElement('div');
  wrapObs.className = 'col-12';
  const lblObs = document.createElement('label');
  lblObs.className = 'form-label mb-0';
  lblObs.htmlFor = `${PREFIX}observacao`;
  lblObs.textContent = 'Observação';
  const taObs = document.createElement('textarea');
  taObs.name = 'observacao';
  taObs.id = `${PREFIX}observacao`;
  taObs.className = 'form-control form-control-sm';
  taObs.rows = 2;
  taObs.value = String(payload.observacao ?? '');
  wrapObs.appendChild(lblObs);
  wrapObs.appendChild(taObs);
  row.appendChild(wrapObs);

  let reconstruindoPlano = false;

  function emitirChange() {
    if (reconstruindoPlano) return;
    onChange(lerPayloadDoSubform(root));
  }

  function renderizarPlanoCascata(limparSelecao = false) {
    reconstruindoPlano = true;
    const tipo = root.querySelector('[name="tipo"]')?.value || '';
    initHierarchicalSelects(root, { planoConta: buildPlanHierarchy(tipo, planos) });
    const atual = limparSelecao
      ? { ...payload, plano_n2_id: '', plano_n3_id: '', plano_n4_id: '', plano_contas_id: '' }
      : lerPayloadDoSubform(root);
    rehidratarPlano(root, atual, planos);
    reconstruindoPlano = false;
    emitirChange();
  }

  preencherContrapartes(root, datasets, payload, bloqueado);
  renderizarPlanoCascata();

  root.querySelectorAll('select, textarea, input').forEach((el) => {
    el.disabled = bloqueado;
    el.addEventListener('change', emitirChange);
    el.addEventListener('input', emitirChange);
  });

  root.querySelector('[name="contraparte_tipo"]')?.addEventListener('change', () => {
    const p = lerPayloadDoSubform(root);
    p.contraparte_id = '';
    preencherContrapartes(root, datasets, p, bloqueado);
    emitirChange();
  });

  tipoSel.addEventListener('change', () => {
    renderizarPlanoCascata(true);
  });

  ['plano_n2_id', 'plano_n3_id', 'plano_n4_id'].forEach((name) => {
    root.querySelector(`[name="${name}"]`)?.addEventListener('change', emitirChange);
  });

  initSmartInputs(() => emitirChange());
}
