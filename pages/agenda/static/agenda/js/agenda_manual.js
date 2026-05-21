import {
  updateFormField,
  getForm,
  updateState,
  clearMessages,
  definirMensagem,
  hidratarFormulario,
  setFormState,
  getScreenPermissions,
  getDataBackEnd,
  getDataset,
} from '/static/js/sisVar.js';
import { fazerRequisicao } from '/static/js/base.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { AppLoader } from '/static/js/loader.js';
import { buttonVisibleByState, buttonAllowedByPermission, createActionChecker } from '/static/js/screen_permissions.js';
import { renderAgendaPayloadFinanceiro } from '/static/agenda/js/agenda_payload_financeiro.js';

const TIPO_MAT_FINANCEIRO = 'financeiro.registro_financeiro_manual';

const nomeForm = 'cadAgendaManual';
const nomeFormCons = 'consAgendaManual';
const URL_MANUAL = '/app/agenda/manual/';
const URL_CONS = '/app/agenda/manual/cons';
const URL_SCHEMA = '/app/agenda/manual/schema-materializacao/';

const form = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

getDataBackEnd();

const podeExecutarAcao = createActionChecker({
  screenKey: 'agenda',
  getScreenPermissions,
  fallback: { acessar: false, consultar: false, incluir: false, editar: false, excluir: false },
});

const MODO_MATERIALIZAVEL = 'materializavel';
const CATEGORIA_LEMBRETE = 'lembrete';

const IDS_BLOQUEAVEIS = [
  'titulo',
  'descricao',
  'categoria',
  'modo_evento',
  'recorrencia',
  'intervalo',
  'data_ancora',
  'data_fim_serie',
  'dia_semana',
  'dia_mes_fixo',
  'antecipar_fim_semana',
  'tipo_materializacao',
  'ativa',
];

function preencherSelect(select, opcoes, placeholder) {
  if (!select) return;
  const valorAtual = select.value;
  select.replaceChildren();
  if (placeholder) {
    const o = document.createElement('option');
    o.value = '';
    o.textContent = placeholder;
    select.appendChild(o);
  }
  opcoes.forEach(({ value, label }) => {
    const o = document.createElement('option');
    o.value = String(value);
    o.textContent = label;
    select.appendChild(o);
  });
  if (valorAtual) select.value = valorAtual;
}

function getCategoriaAtual() {
  const el = document.getElementById('categoria');
  if (el) return String(el.value ?? '');
  return String(getForm(nomeForm)?.campos?.categoria ?? '');
}

function getTiposMaterializacaoParaCategoria(categoria) {
  const cat = String(categoria ?? '');
  return getDataset('tipos_materializacao', []).filter(
    (item) => String(item.categoria || '') === cat,
  );
}

function categoriaPermiteLancamentoVinculado(categoria) {
  if (String(categoria) === CATEGORIA_LEMBRETE) return false;
  return getTiposMaterializacaoParaCategoria(categoria).length > 0;
}

function getModosEventoParaCategoria(categoria) {
  const todos = getDataset('modos_evento', []);
  if (!categoriaPermiteLancamentoVinculado(categoria)) {
    return todos.filter((m) => m.value !== MODO_MATERIALIZAVEL);
  }
  return todos;
}

function renderizarSelectModoEvento() {
  const campos = getForm(nomeForm)?.campos ?? {};
  const categoria = getCategoriaAtual();
  const modos = getModosEventoParaCategoria(categoria);
  preencherSelect(document.getElementById('modo_evento'), modos);
  let modo = String(campos.modo_evento ?? '');
  if (!modos.some((m) => m.value === modo)) {
    modo = modos[0]?.value || 'aviso';
    updateFormField(nomeForm, 'modo_evento', modo);
  }
  document.getElementById('modo_evento').value = modo;
}

function renderizarSelectTipoMaterializacao() {
  const campos = getForm(nomeForm)?.campos ?? {};
  const categoria = getCategoriaAtual();
  const tipos = getTiposMaterializacaoParaCategoria(categoria);
  preencherSelect(document.getElementById('tipo_materializacao'), tipos, '—');
  let tipo = String(campos.tipo_materializacao ?? '');
  if (tipo && !tipos.some((t) => t.value === tipo)) {
    tipo = '';
    updateFormField(nomeForm, 'tipo_materializacao', '');
    updateFormField(nomeForm, 'payload_template', {});
    document.getElementById('payload-subform')?.replaceChildren();
  }
  document.getElementById('tipo_materializacao').value = tipo;
}

function ajustarCamposDependentesDeCategoria() {
  const campos = getForm(nomeForm)?.campos ?? {};
  const categoria = getCategoriaAtual();
  updateFormField(nomeForm, 'categoria', categoria);
  if (
    categoria === CATEGORIA_LEMBRETE
    && campos.modo_evento === MODO_MATERIALIZAVEL
  ) {
    updateFormField(nomeForm, 'modo_evento', 'aviso');
    updateFormField(nomeForm, 'tipo_materializacao', '');
    updateFormField(nomeForm, 'payload_template', {});
  } else if (
    campos.modo_evento === MODO_MATERIALIZAVEL
    && !categoriaPermiteLancamentoVinculado(categoria)
  ) {
    updateFormField(nomeForm, 'modo_evento', 'aviso');
    updateFormField(nomeForm, 'tipo_materializacao', '');
    updateFormField(nomeForm, 'payload_template', {});
  }
  renderizarSelectModoEvento();
  renderizarSelectTipoMaterializacao();
  atualizarVisibilidadeModo();
  if (getForm(nomeForm)?.campos?.modo_evento !== MODO_MATERIALIZAVEL) {
    document.getElementById('payload-subform')?.replaceChildren();
  }
}

function renderizarSelectsCadastro() {
  const campos = getForm(nomeForm)?.campos ?? {};
  preencherSelect(document.getElementById('categoria'), getDataset('categorias', []));
  document.getElementById('categoria').value = String(campos.categoria ?? '');
  renderizarSelectModoEvento();
  preencherSelect(document.getElementById('recorrencia'), getDataset('recorrencias', []));
  preencherSelect(document.getElementById('dia_semana'), getDataset('dias_semana_agenda', []), '—');
  renderizarSelectTipoMaterializacao();
  document.getElementById('recorrencia').value = String(campos.recorrencia ?? '');
  document.getElementById('dia_semana').value = campos.dia_semana != null ? String(campos.dia_semana) : '';
}

function renderizarSelectsPesquisa() {
  const campos = getForm(nomeFormCons)?.campos ?? {};
  const cats = getDataset('categorias', []);
  const modos = getDataset('modos_evento', []);
  const catSel = document.getElementById('categoria_cons');
  const modoSel = document.getElementById('modo_evento_cons');
  catSel.innerHTML = '<option value="">Todas</option>';
  modoSel.innerHTML = '<option value="">Todos</option>';
  cats.forEach(({ value, label }) => {
    const o = document.createElement('option');
    o.value = String(value);
    o.textContent = label;
    catSel.appendChild(o);
  });
  modos.forEach(({ value, label }) => {
    const o = document.createElement('option');
    o.value = String(value);
    o.textContent = label;
    modoSel.appendChild(o);
  });
  catSel.value = String(campos.categoria_cons ?? '');
  modoSel.value = String(campos.modo_evento_cons ?? '');
  document.getElementById('ativa_cons').value = String(campos.ativa_cons ?? '');
  const tituloCons = document.getElementById('titulo_cons');
  if (tituloCons) tituloCons.value = String(campos.titulo_cons ?? '');
}

function atualizarVisibilidadeRecorrencia() {
  const rec = String(getForm(nomeForm)?.campos?.recorrencia ?? '');
  document.getElementById('wrap-dia-semana')?.classList.toggle('d-none', rec !== 'semanal');
  const mensal = rec === 'mensal';
  document.getElementById('wrap-dia-mes')?.classList.toggle('d-none', !mensal);
  document.getElementById('wrap-antecipar')?.classList.toggle('d-none', !mensal);
}

function atualizarVisibilidadeModo() {
  const modo = String(getForm(nomeForm)?.campos?.modo_evento ?? '');
  document.getElementById('wrap-materializacao')?.classList.toggle('d-none', modo !== 'materializavel');
}

function sincronizarPayloadTemplate(partial) {
  const atual = { ...(getForm(nomeForm)?.campos?.payload_template || {}) };
  updateFormField(nomeForm, 'payload_template', { ...atual, ...partial });
}

function limitarDiaMesFixo(valor) {
  if (valor === '' || valor === null || valor === undefined) return null;
  const n = parseInt(String(valor), 10);
  if (!Number.isFinite(n)) return null;
  if (n < 1) return 1;
  if (n > 31) return 31;
  return n;
}

async function carregarSchemaMaterializacao() {
  const tipo = String(getForm(nomeForm)?.campos?.tipo_materializacao ?? '');
  const box = document.getElementById('payload-subform');
  if (!box) return;
  box.replaceChildren();
  if (!tipo) return;

  const { success, data } = await fazerRequisicao(URL_SCHEMA, { tipo_materializacao: tipo });
  if (!success || !data?.success) {
    definirMensagem('erro', data?.mensagem || 'Erro ao carregar formulário de materialização.', false);
    return;
  }

  const payload = getForm(nomeForm)?.campos?.payload_template || {};
  const estado = getForm(nomeForm)?.estado ?? 'visualizar';
  const bloqueado = estado === 'visualizar';

  if (tipo === TIPO_MAT_FINANCEIRO) {
    renderAgendaPayloadFinanceiro(box, {
      payload,
      datasets: data.datasets || {},
      bloqueado,
      onChange: (partial) => sincronizarPayloadTemplate(partial),
    });
    return;
  }

  const schema = data.schema || {};
  Object.entries(schema).forEach(([name, rules]) => {
    const wrap = document.createElement('div');
    wrap.className = 'mb-2';
    const label = document.createElement('label');
    label.className = 'form-label mb-0';
    label.textContent = `${name}${rules.required ? ' *' : ''}`;
    label.htmlFor = `payload-${name}`;
    let input;
    if (name === 'observacao') {
      input = document.createElement('textarea');
      input.rows = 2;
    } else {
      input = document.createElement('input');
      input.type = rules.type === 'integer' ? 'number' : 'text';
    }
    input.className = 'form-control form-control-sm';
    input.id = `payload-${name}`;
    input.name = name;
    input.disabled = bloqueado;
    input.value = payload[name] ?? '';
    input.addEventListener('change', () => {
      sincronizarPayloadTemplate({ [name]: input.value });
    });
    wrap.appendChild(label);
    wrap.appendChild(input);
    box.appendChild(wrap);
  });
}

function aplicarDefaultsNovo() {
  const filialId = String(getDataset('filial_ativa_id', '') || '');
  const hoje = new Date().toISOString().slice(0, 10);
  const defaults = {
    id: null,
    filial_id: filialId,
    titulo: '',
    descricao: '',
    categoria: 'lembrete',
    modo_evento: 'aviso',
    tipo_materializacao: '',
    payload_template: {},
    data_ancora: hoje,
    recorrencia: 'mensal',
    intervalo: 1,
    dia_semana: null,
    dia_mes_fixo: null,
    antecipar_fim_semana: false,
    data_fim_serie: '',
    ativa: true,
  };
  Object.entries(defaults).forEach(([k, v]) => updateFormField(nomeForm, k, v));
  renderizarSelectsCadastro();
  hidratarFormulario(nomeForm);
  atualizarVisibilidadeRecorrencia();
  atualizarVisibilidadeModo();
  document.getElementById('payload-subform')?.replaceChildren();
}

function renderizarTabela(registros) {
  const tbody = document.getElementById('tabela-agenda-manual-corpo');
  if (!tbody) return;
  tbody.replaceChildren();
  registros.forEach((registro) => {
    const tr = document.createElement('tr');
    ['id', 'titulo', 'categoria', 'modo_evento', 'recorrencia', 'data_ancora', 'ativa'].forEach((col) => {
      const td = document.createElement('td');
      td.textContent = String(registro[col] ?? '');
      tr.appendChild(td);
    });
    const tdAcao = document.createElement('td');
    tdAcao.className = 'text-center';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-sm btn-primary btn-selecionar';
    btn.dataset.id = String(registro.id);
    btn.textContent = 'Selecionar';
    tdAcao.appendChild(btn);
    tr.appendChild(tdAcao);
    tbody.appendChild(tr);
  });
}

const updater = criarAtualizadorForm({ formId: nomeForm, setter: updateFormField, form });
form.addEventListener('input', updater);
form.addEventListener('change', updater);
const updater2 = criarAtualizadorForm({ formId: nomeFormCons, setter: updateFormField, form: form2 });
form2.addEventListener('input', updater2);
form2.addEventListener('change', updater2);

document.addEventListener('DOMContentLoaded', () => {
  AppLoader.show();
  const btnSalvar = document.getElementById('btn-salvar');
  const btnEditar = document.getElementById('btn-editar');
  const btnNovo = document.getElementById('btn-novo');
  const btnCancelar = document.getElementById('btn-cancelar');
  const btnAbrirPesquisa = document.getElementById('btn-abrir-pesquisa');
  const btnVoltar = document.getElementById('btn-voltar');
  const btnFechar = document.getElementById('btn-fechar');
  const divForm = document.getElementById(nomeForm);
  const divPesquisa = document.getElementById('div-pesquisa');

  function aplicarPermissoes() {
    const estado = getForm(nomeForm)?.estado ?? 'visualizar';
    [btnSalvar, btnEditar, btnNovo, btnCancelar].forEach((btn) => {
      const visivelEstado = buttonVisibleByState(btn, estado);
      const visivelPerm = buttonAllowedByPermission({
        buttonId: btn.id,
        state: estado,
        canExecute: podeExecutarAcao,
      });
      btn.classList.toggle('d-none', !(visivelEstado && visivelPerm));
    });
    btnAbrirPesquisa.classList.toggle('d-none', !podeExecutarAcao('consultar'));
    aplicarBloqueioCamposPorEstado(estado);
  }

  function aplicarBloqueioCamposPorEstado(estado) {
    const bloqueado = estado === 'visualizar';
    IDS_BLOQUEAVEIS.forEach((idCampo) => {
      const el = document.getElementById(idCampo);
      if (el) el.disabled = bloqueado;
    });
    document.querySelectorAll('#payload-subform input, #payload-subform textarea').forEach((el) => {
      el.disabled = bloqueado;
    });
  }

  function alternarTela() {
    divForm.classList.toggle('d-none');
    divPesquisa.classList.toggle('d-none');
  }

  function limparSelecaoPesquisa() {
    updateFormField(nomeFormCons, 'id_selecionado', '');
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearMessages();
    if (!form.reportValidity()) return;
    AppLoader.show();
    const result = await fazerRequisicao(URL_MANUAL, {
      form: { [nomeForm]: getForm(nomeForm) },
    });
    AppLoader.hide();
    if (!result.success) {
      if (result.data) updateState(result.data);
      else definirMensagem('erro', `Erro: ${result.error}`, false);
      return;
    }
    updateState(result.data);
    renderizarSelectsCadastro();
    hidratarFormulario(nomeForm);
    ajustarCamposDependentesDeCategoria();
    atualizarVisibilidadeRecorrencia();
    if (getForm(nomeForm)?.campos?.modo_evento === MODO_MATERIALIZAVEL) {
      await carregarSchemaMaterializacao();
    }
    aplicarPermissoes();
  });

  btnEditar.addEventListener('click', () => {
    if (!podeExecutarAcao('editar')) return;
    setFormState(nomeForm, 'editar');
    aplicarPermissoes();
  });

  btnNovo.addEventListener('click', () => {
    if (!podeExecutarAcao('incluir')) return;
    setFormState(nomeForm, 'novo');
    aplicarDefaultsNovo();
    aplicarPermissoes();
  });

  btnCancelar.addEventListener('click', () => {
    setFormState(nomeForm, 'novo');
    aplicarDefaultsNovo();
    aplicarPermissoes();
  });

  btnAbrirPesquisa.addEventListener('click', alternarTela);
  btnAbrirPesquisa.addEventListener('click', limparSelecaoPesquisa);
  btnVoltar.addEventListener('click', alternarTela);
  btnFechar.addEventListener('click', alternarTela);

  form2.addEventListener('submit', async (event) => {
    event.preventDefault();
    limparSelecaoPesquisa();
    AppLoader.show();
    const result = await fazerRequisicao(URL_CONS, {
      form: { [nomeFormCons]: getForm(nomeFormCons) },
    });
    AppLoader.hide();
    if (!result.success) {
      if (result.data) updateState(result.data);
      else definirMensagem('erro', `Erro: ${result.error}`, false);
      return;
    }
    renderizarTabela(result.data?.registros ?? []);
  });

  document.getElementById('tabela-agenda-manual-corpo').addEventListener('click', async (event) => {
    const botao = event.target.closest('.btn-selecionar');
    if (!botao) return;
    updateFormField(nomeFormCons, 'id_selecionado', Number(botao.dataset.id));
    AppLoader.show();
    const result = await fazerRequisicao(URL_CONS, {
      form: { [nomeFormCons]: getForm(nomeFormCons) },
    });
    AppLoader.hide();
    if (!result.success) {
      if (result.data) updateState(result.data);
      else definirMensagem('erro', `Erro: ${result.error}`, false);
      return;
    }
    updateState(result.data);
    renderizarSelectsCadastro();
    hidratarFormulario(nomeForm);
    ajustarCamposDependentesDeCategoria();
    atualizarVisibilidadeRecorrencia();
    if (getForm(nomeForm)?.campos?.modo_evento === MODO_MATERIALIZAVEL) {
      await carregarSchemaMaterializacao();
    }
    alternarTela();
    aplicarPermissoes();
  });

  document.getElementById('categoria').addEventListener('change', () => {
    ajustarCamposDependentesDeCategoria();
  });
  const inpDiaMes = document.getElementById('dia_mes_fixo');
  const aplicarLimiteDiaMes = () => {
    const limitado = limitarDiaMesFixo(inpDiaMes?.value);
    if (limitado === null) {
      updateFormField(nomeForm, 'dia_mes_fixo', null);
      return;
    }
    const txt = String(limitado);
    if (inpDiaMes && inpDiaMes.value !== txt) inpDiaMes.value = txt;
    updateFormField(nomeForm, 'dia_mes_fixo', limitado);
  };
  inpDiaMes?.addEventListener('input', aplicarLimiteDiaMes);
  inpDiaMes?.addEventListener('change', aplicarLimiteDiaMes);
  document.getElementById('recorrencia').addEventListener('change', () => {
    atualizarVisibilidadeRecorrencia();
  });
  document.getElementById('modo_evento').addEventListener('change', async () => {
    atualizarVisibilidadeModo();
    if (getForm(nomeForm)?.campos?.modo_evento === 'materializavel') {
      await carregarSchemaMaterializacao();
    } else {
      document.getElementById('payload-subform')?.replaceChildren();
    }
  });
  document.getElementById('tipo_materializacao').addEventListener('change', () => {
    updateFormField(nomeForm, 'payload_template', {});
    carregarSchemaMaterializacao();
  });

  renderizarSelectsCadastro();
  renderizarSelectsPesquisa();
  hidratarFormulario(nomeForm);
  ajustarCamposDependentesDeCategoria();
  atualizarVisibilidadeRecorrencia();
  if (getForm(nomeForm)?.campos?.modo_evento === MODO_MATERIALIZAVEL) {
    carregarSchemaMaterializacao();
  }
  aplicarPermissoes();
  AppLoader.hide();
});
