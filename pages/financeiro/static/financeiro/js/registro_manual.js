import {
  updateFormField, getForm, updateState,
  clearMessages, definirMensagem,
  hidratarFormulario, setFormState, confirmar, getScreenPermissions, getDataBackEnd, getDataset,
} from '/static/js/sisVar.js';
import { fazerRequisicao } from '/static/js/base.js';
import { initSmartInputs } from '/static/js/input_rules.js';
import { initHierarchicalSelects } from '/static/js/conditional_select.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { AppLoader } from '/static/js/loader.js';
import { buttonVisibleByState, buttonAllowedByPermission, createActionChecker } from '/static/js/screen_permissions.js';

const nomeForm = 'cadRegistroFinanceiro';
const nomeFormCons = 'consRegistroFinanceiro';
const form = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);
let reconstruindoPlano = false;

getDataBackEnd();

const podeExecutarAcao = createActionChecker({
  screenKey: 'financeiro',
  getScreenPermissions,
  fallback: { acessar: false, consultar: false, incluir: false, editar: false, excluir: false },
});

function getFiliaisEscrita() {
  return getDataset('filiais_escrita', []);
}

function getPlanos() {
  return getDataset('planos_contas', []);
}

function getPlanosN4() {
  return getDataset('planos_nivel4', []);
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

function rotuloStatusRegistro(st) {
  const map = {
    aberto: 'Aberto',
    parcial: 'Parcial',
    liquidado: 'Liquidado',
    cancelado: 'Cancelado',
  };
  return map[String(st || '').toLowerCase()] || String(st || '—');
}

function classeBadgeStatusRegistro(st) {
  switch (String(st || '').toLowerCase()) {
    case 'aberto':
      return 'text-bg-primary';
    case 'parcial':
      return 'text-bg-warning text-dark';
    case 'liquidado':
      return 'text-bg-success';
    case 'cancelado':
      return 'text-bg-secondary';
    default:
      return 'text-bg-light text-dark';
  }
}

function atualizarExibicaoStatus() {
  const st = String(getForm(nomeForm)?.campos?.status ?? '');
  const badge = document.getElementById('status_badge');
  const hidden = document.getElementById('status');
  if (hidden) hidden.value = st;
  if (badge) {
    badge.textContent = rotuloStatusRegistro(st);
    badge.className = `badge ${classeBadgeStatusRegistro(st)}`;
  }
}

function renderizarSelectFiliais() {
  const valorPrincipal = String(getForm(nomeForm)?.campos?.filial_id ?? getFilialAtivaId());
  const valorPesquisa = String(getForm(nomeFormCons)?.campos?.filial_cons ?? '');
  const filiais = getFiliaisEscrita();
  const principal = document.getElementById('filial_id');
  const pesquisa = document.getElementById('filial_cons');

  principal.innerHTML = '<option value="">Selecione</option>';
  pesquisa.innerHTML = '<option value="">Todas</option>';
  filiais.forEach((filial) => {
    const label = `${filial.codigo} - ${filial.nome}`;
    const o1 = document.createElement('option');
    o1.value = String(filial.id);
    o1.textContent = label;
    principal.appendChild(o1);
    const o2 = document.createElement('option');
    o2.value = String(filial.id);
    o2.textContent = label;
    pesquisa.appendChild(o2);
  });
  principal.value = valorPrincipal;
  pesquisa.value = valorPesquisa;
  const bloqueado = isBloquearFilialSelect();
  principal.disabled = bloqueado;
  if (bloqueado && valorPrincipal) {
    principal.value = valorPrincipal;
    updateFormField(nomeForm, 'filial_id', valorPrincipal);
  }
}

function renderizarSelectTipos() {
  const tipos = getTipos();
  const selPrincipal = document.getElementById('tipo');
  const selPesquisa = document.getElementById('tipo_cons');
  const valorPrincipal = String(getForm(nomeForm)?.campos?.tipo ?? '');
  const valorPesquisa = String(getForm(nomeFormCons)?.campos?.tipo_cons ?? '');
  selPrincipal.innerHTML = '';
  selPesquisa.innerHTML = '<option value="">Todos</option>';
  tipos.forEach((item) => {
    const opMain = document.createElement('option');
    opMain.value = item.value;
    opMain.textContent = item.label;
    selPrincipal.appendChild(opMain);
    const opCons = document.createElement('option');
    opCons.value = item.value;
    opCons.textContent = item.label;
    selPesquisa.appendChild(opCons);
  });
  if (valorPrincipal) selPrincipal.value = valorPrincipal;
  if (valorPesquisa) selPesquisa.value = valorPesquisa;
}

function renderizarContraparteTiposCons() {
  const tipos = getContraparteTipos();
  const select = document.getElementById('contraparte_tipo_cons');
  const valor = String(getForm(nomeFormCons)?.campos?.contraparte_tipo_cons ?? '');
  select.innerHTML = '<option value="">Todos</option>';
  tipos.forEach((tipo) => {
    const op = document.createElement('option');
    op.value = tipo.value;
    op.textContent = tipo.label;
    select.appendChild(op);
  });
  select.value = valor;
}

function renderizarContrapartesCons() {
  const porTipo = getContrapartesPorTipo();
  const tipo = String(getForm(nomeFormCons)?.campos?.contraparte_tipo_cons ?? '');
  const valorAtual = String(getForm(nomeFormCons)?.campos?.contraparte_id_cons ?? '');
  const select = document.getElementById('contraparte_id_cons');
  const lista = porTipo[tipo] ?? [];
  select.innerHTML = '<option value="">Todas</option>';
  lista.forEach((item) => {
    const op = document.createElement('option');
    op.value = String(item.id);
    op.textContent = item.label;
    select.appendChild(op);
  });
  const existe = lista.some((x) => String(x.id) === valorAtual);
  select.value = existe ? valorAtual : '';
  if (!existe) updateFormField(nomeFormCons, 'contraparte_id_cons', '');
  select.disabled = !tipo;
}

function classTipoParaPlano(tipo) {
  if (tipo === 'ENTRADA') return 'receita';
  if (tipo === 'SAIDA') return 'despesa';
  return '';
}

function renderizarSelectPlanoCons() {
  const planos = getPlanosN4();
  const pesquisa = document.getElementById('plano_cons');
  const vPesquisa = String(getForm(nomeFormCons)?.campos?.plano_cons ?? '');
  pesquisa.innerHTML = '<option value="">Todos</option>';
  planos.forEach((plano) => {
    const op2 = document.createElement('option');
    op2.value = String(plano.id);
    op2.textContent = plano.nome;
    pesquisa.appendChild(op2);
  });
  pesquisa.value = vPesquisa;
}

function sincronizarPlanoContasId() {
  const planoN4 = String(getForm(nomeForm)?.campos?.plano_n4_id ?? '');
  updateFormField(nomeForm, 'plano_contas_id', planoN4 || '');
  document.getElementById('plano_contas_id').value = planoN4 || '';
}

function sincronizarCamposPlanoSelecionados() {
  updateFormField(nomeForm, 'plano_n2_id', document.getElementById('plano_n2_id').value || '');
  updateFormField(nomeForm, 'plano_n3_id', document.getElementById('plano_n3_id').value || '');
  updateFormField(nomeForm, 'plano_n4_id', document.getElementById('plano_n4_id').value || '');
  sincronizarPlanoContasId();
}

function buildPlanHierarchy(tipo) {
  const classe = classTipoParaPlano(tipo);
  const planos = getPlanos();
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

function rehidratarPlanoSelecionado() {
  const campos = getForm(nomeForm)?.campos ?? {};
  const s2 = document.getElementById('plano_n2_id');
  const s3 = document.getElementById('plano_n3_id');
  const s4 = document.getElementById('plano_n4_id');
  const n2 = String(campos.plano_n2_id ?? '');
  const n3 = String(campos.plano_n3_id ?? '');
  const n4 = String(campos.plano_n4_id ?? '');
  if (n2) {
    s2.value = n2;
    s2.dispatchEvent(new Event('change', { bubbles: true }));
  }
  if (n3) {
    s3.value = n3;
    s3.dispatchEvent(new Event('change', { bubbles: true }));
  }
  if (n4) s4.value = n4;
}

function renderizarPlanoCascata() {
  reconstruindoPlano = true;
  const tipo = String(getForm(nomeForm)?.campos?.tipo ?? '');
  const hierarchy = buildPlanHierarchy(tipo);
  initHierarchicalSelects(form, { planoConta: hierarchy });
  rehidratarPlanoSelecionado();
  sincronizarCamposPlanoSelecionados();
  reconstruindoPlano = false;
}

function preencherPlanoCascataPorFolha(planoContasId) {
  const planos = getPlanos();
  const byId = Object.fromEntries(planos.map((p) => [String(p.id), p]));
  let atual = byId[String(planoContasId)];
  if (!atual) return;
  const cadeia = [];
  while (atual) {
    cadeia.push(atual);
    atual = atual.pai_id ? byId[String(atual.pai_id)] : null;
  }
  cadeia.reverse();
  const n2 = cadeia.find((p) => Number(p.nivel) === 2);
  const n3 = cadeia.find((p) => Number(p.nivel) === 3);
  const n4 = cadeia.find((p) => Number(p.nivel) === 4);
  updateFormField(nomeForm, 'plano_n2_id', n2 ? String(n2.id) : '');
  updateFormField(nomeForm, 'plano_n3_id', n3 ? String(n3.id) : '');
  updateFormField(nomeForm, 'plano_n4_id', n4 ? String(n4.id) : '');
  renderizarPlanoCascata();
}

function renderizarContraparteTipos() {
  const tipos = getContraparteTipos();
  const select = document.getElementById('contraparte_tipo');
  const valor = String(getForm(nomeForm)?.campos?.contraparte_tipo ?? '');
  select.innerHTML = '<option value="">Selecione</option>';
  tipos.forEach((tipo) => {
    const op = document.createElement('option');
    op.value = tipo.value;
    op.textContent = tipo.label;
    select.appendChild(op);
  });
  select.value = valor;
}

function renderizarContrapartes() {
  const porTipo = getContrapartesPorTipo();
  const tipo = String(getForm(nomeForm)?.campos?.contraparte_tipo ?? '');
  const valorAtual = String(getForm(nomeForm)?.campos?.contraparte_id ?? '');
  const select = document.getElementById('contraparte_id');
  const lista = porTipo[tipo] ?? [];
  select.innerHTML = '<option value="">Selecione</option>';
  lista.forEach((item) => {
    const op = document.createElement('option');
    op.value = String(item.id);
    op.textContent = item.label;
    select.appendChild(op);
  });
  const existe = lista.some((x) => String(x.id) === valorAtual);
  select.value = existe ? valorAtual : '';
  if (!existe) updateFormField(nomeForm, 'contraparte_id', '');
  select.disabled = !tipo;
}

function normalizarValor(valorRaw) {
  const texto = String(valorRaw || '').trim();
  if (!texto) return NaN;
  const semMilhar = texto.replace(/\./g, '');
  const comPontoDecimal = semMilhar.replace(',', '.');
  return Number(comPontoDecimal);
}

function validarAtivoSelecionado() {
  const campos = getForm(nomeForm)?.campos ?? {};
  const ativoId = String(campos.plano_n4_id ?? '').trim();
  const planoContasId = String(campos.plano_contas_id ?? '').trim();
  if (!ativoId || !planoContasId || ativoId !== planoContasId) {
    definirMensagem('erro', 'Selecione o Ativo (nível final do plano de contas).', false);
    return false;
  }
  return true;
}

function aplicarDefaultsNovo() {
  const hoje = new Date().toISOString().slice(0, 10);
  updateFormField(nomeForm, 'tipo', 'ENTRADA');
  updateFormField(nomeForm, 'filial_id', getFilialAtivaId());
  updateFormField(nomeForm, 'contraparte_tipo', '');
  updateFormField(nomeForm, 'contraparte_id', '');
  updateFormField(nomeForm, 'plano_n2_id', '');
  updateFormField(nomeForm, 'plano_n3_id', '');
  updateFormField(nomeForm, 'plano_n4_id', '');
  updateFormField(nomeForm, 'plano_contas_id', '');
  updateFormField(nomeForm, 'data_emissao', hoje);
  updateFormField(nomeForm, 'data_vencimento', hoje);
  updateFormField(nomeForm, 'status', 'aberto');
  updateFormField(nomeForm, 'permite_editar', true);
  updateFormField(nomeForm, 'permite_cancelar', true);
  updateFormField(nomeForm, 'permite_excluir_permanente', false);
  updateFormField(nomeForm, 'valor', '');
  updateFormField(nomeForm, 'observacao', '');
  hidratarFormulario(nomeForm);
}

const updater = criarAtualizadorForm({ formId: nomeForm, setter: updateFormField, form });
form.addEventListener('input', updater);
form.addEventListener('change', updater);
const updater2 = criarAtualizadorForm({ formId: nomeFormCons, setter: updateFormField, form: form2 });
form2.addEventListener('input', updater2);
form2.addEventListener('change', updater2);
initSmartInputs((input, value) => { updateFormField(nomeForm, input.name, value); });

function renderizarTabela(registros) {
  const tbody = document.getElementById('tabela-registro-financeiro-corpo');
  tbody.innerHTML = '';
  registros.forEach((registro) => {
    const tr = document.createElement('tr');
    const colunas = [
      registro.id,
      registro.filial,
      registro.tipo,
      registro.plano,
      registro.valor,
      registro.valor_rest,
      registro.status,
    ];
    colunas.forEach((valor, idx) => {
      const td = document.createElement('td');
      if (idx === 6) {
        const sp = document.createElement('span');
        sp.className = `badge ${classeBadgeStatusRegistro(valor)}`;
        sp.textContent = rotuloStatusRegistro(valor);
        td.appendChild(sp);
      } else {
        td.textContent = String(valor ?? '');
      }
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

document.addEventListener('DOMContentLoaded', () => {
  AppLoader.show();
  const btnSalvar = document.getElementById('btn-salvar');
  const btnEditar = document.getElementById('btn-editar');
  const btnNovo = document.getElementById('btn-novo');
  const btnExcluir = document.getElementById('btn-excluir');
  const btnExcluirPermanente = document.getElementById('btn-excluir-permanente');
  const btnCancelar = document.getElementById('btn-cancelar');
  const btnAbrirPesquisa = document.getElementById('btn-abrir-pesquisa');
  const btnVoltar = document.getElementById('btn-voltar');
  const btnFechar = document.getElementById('btn-fechar');
  const divForm = document.getElementById(nomeForm);
  const divPesquisa = document.getElementById('div-pesquisa');

  function aplicarPermissoes() {
    const estado = getForm(nomeForm)?.estado ?? 'visualizar';
    const campos = getForm(nomeForm)?.campos ?? {};
    const podeEditarNegocio = campos.permite_editar !== false;
    const podeCancelarNegocio = campos.permite_cancelar !== false;
    const podeExcluirPermanenteNegocio = campos.permite_excluir_permanente === true;
    const botoes = [btnSalvar, btnEditar, btnNovo, btnExcluir, btnExcluirPermanente, btnCancelar];
    botoes.forEach((btn) => {
      const visivelEstado = buttonVisibleByState(btn, estado);
      const visivelPerm = buttonAllowedByPermission({ buttonId: btn.id, state: estado, canExecute: podeExecutarAcao });
      let ok = visivelEstado && visivelPerm;
      if (btn.id === 'btn-editar') ok = ok && podeEditarNegocio;
      if (btn.id === 'btn-excluir') ok = ok && podeCancelarNegocio;
      if (btn.id === 'btn-excluir-permanente') ok = ok && podeExcluirPermanenteNegocio;
      btn.classList.toggle('d-none', !ok);
    });
    btnAbrirPesquisa.classList.toggle('d-none', !podeExecutarAcao('consultar'));
    aplicarBloqueioCamposPorEstado(estado);
    atualizarExibicaoStatus();
  }

  function aplicarBloqueioCamposPorEstado(estado) {
    const bloqueado = estado === 'visualizar';
    const idsBloqueaveis = [
      'filial_id',
      'data_emissao',
      'data_vencimento',
      'tipo',
      'contraparte_tipo',
      'contraparte_id',
      'plano_n2_id',
      'plano_n3_id',
      'plano_n4_id',
      'valor',
      'observacao',
    ];
    idsBloqueaveis.forEach((idCampo) => {
      const el = document.getElementById(idCampo);
      if (el) el.disabled = bloqueado;
    });
    if (!bloqueado) {
      const bloqueioFilial = isBloquearFilialSelect();
      const filial = document.getElementById('filial_id');
      if (filial) filial.disabled = bloqueioFilial;
      const tipoContraparte = String(getForm(nomeForm)?.campos?.contraparte_tipo ?? '');
      const contraparte = document.getElementById('contraparte_id');
      if (contraparte) contraparte.disabled = !tipoContraparte;
    }
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
    sincronizarCamposPlanoSelecionados();
    if (!form.reportValidity()) return;
    if (!validarAtivoSelecionado()) return;
    const valorNumero = normalizarValor(getForm(nomeForm)?.campos?.valor);
    if (!Number.isFinite(valorNumero) || valorNumero <= 0) {
      definirMensagem('erro', 'Informe um valor maior que zero.', false);
      return;
    }
    confirmar({
      titulo: 'Confirmar salvamento',
      mensagem: 'Deseja salvar o registro financeiro?',
      onConfirmar: async () => {
        AppLoader.show();
        const result = await fazerRequisicao('/app/financeiro/registro/manual/', {
          form: { [nomeForm]: getForm(nomeForm) },
        });
        AppLoader.hide();
        if (!result.success) {
          if (result.data) updateState(result.data);
          else definirMensagem('erro', `Erro: ${result.error}`, false);
          return;
        }
        updateState(result.data);
        renderizarSelectFiliais();
        renderizarSelectTipos();
        preencherPlanoCascataPorFolha(getForm(nomeForm)?.campos?.plano_contas_id);
        renderizarSelectPlanoCons();
        renderizarContraparteTipos();
        renderizarContrapartes();
        hidratarFormulario(nomeForm);
        aplicarPermissoes();
      },
    });
  });

  btnEditar.addEventListener('click', () => {
    if (!podeExecutarAcao('editar')) return;
    if (getForm(nomeForm)?.campos?.permite_editar === false) return;
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
  btnExcluir.addEventListener('click', () => {
    if (getForm(nomeForm)?.campos?.permite_cancelar === false) return;
    confirmar({
      titulo: 'Confirmar cancelamento',
      mensagem: 'Deseja cancelar este título financeiro?',
      onConfirmar: async () => {
        AppLoader.show();
        const result = await fazerRequisicao('/app/financeiro/registro/manual/cancelar', {
          form: { [nomeForm]: getForm(nomeForm) },
        });
        AppLoader.hide();
        if (!result.success) {
          if (result.data) updateState(result.data);
          else definirMensagem('erro', `Erro: ${result.error}`, false);
          return;
        }
        updateState(result.data);
        renderizarSelectFiliais();
        renderizarSelectTipos();
        preencherPlanoCascataPorFolha(getForm(nomeForm)?.campos?.plano_contas_id);
        renderizarSelectPlanoCons();
        renderizarContraparteTipos();
        renderizarContrapartes();
        hidratarFormulario(nomeForm);
        setFormState(nomeForm, 'visualizar');
        aplicarPermissoes();
      },
    });
  });
  btnExcluirPermanente.addEventListener('click', () => {
    if (getForm(nomeForm)?.campos?.permite_excluir_permanente !== true) return;
    if (!podeExecutarAcao('excluir')) return;
    confirmar({
      titulo: 'Exclusão permanente',
      mensagem: 'Esta ação remove o registro do banco de dados. Confirma a exclusão permanente?',
      onConfirmar: async () => {
        AppLoader.show();
        const result = await fazerRequisicao('/app/financeiro/registro/manual/excluir-permanente', {
          form: { [nomeForm]: getForm(nomeForm) },
        });
        AppLoader.hide();
        if (!result.success) {
          if (result.data) updateState(result.data);
          else definirMensagem('erro', `Erro: ${result.error}`, false);
          return;
        }
        updateState(result.data);
        setFormState(nomeForm, 'novo');
        aplicarDefaultsNovo();
        aplicarPermissoes();
      },
    });
  });
  btnAbrirPesquisa.addEventListener('click', alternarTela);
  btnAbrirPesquisa.addEventListener('click', limparSelecaoPesquisa);
  btnVoltar.addEventListener('click', alternarTela);
  btnFechar.addEventListener('click', alternarTela);

  form2.addEventListener('submit', async (event) => {
    event.preventDefault();
    limparSelecaoPesquisa();
    AppLoader.show();
    const result = await fazerRequisicao('/app/financeiro/registro/manual/cons', {
      form: { [nomeFormCons]: getForm(nomeFormCons) },
    });
    AppLoader.hide();
    if (!result.success) {
      if (result.data) updateState(result.data);
      else definirMensagem('erro', `Erro: ${result.error}`, false);
      return;
    }
    const registros = result.data?.registros ?? [];
    renderizarTabela(registros);
  });

  document.getElementById('tabela-registro-financeiro-corpo').addEventListener('click', async (event) => {
    const botao = event.target.closest('.btn-selecionar');
    if (!botao) return;
    updateFormField(nomeFormCons, 'id_selecionado', Number(botao.dataset.id));
    AppLoader.show();
    const result = await fazerRequisicao('/app/financeiro/registro/manual/cons', {
      form: { [nomeFormCons]: getForm(nomeFormCons) },
    });
    AppLoader.hide();
    if (!result.success) {
      if (result.data) updateState(result.data);
      else definirMensagem('erro', `Erro: ${result.error}`, false);
      return;
    }
    updateState(result.data);
    renderizarSelectFiliais();
    renderizarSelectTipos();
    preencherPlanoCascataPorFolha(getForm(nomeForm)?.campos?.plano_contas_id);
    renderizarSelectPlanoCons();
    renderizarContraparteTipos();
    renderizarContrapartes();
    hidratarFormulario(nomeForm);
    alternarTela();
    aplicarPermissoes();
  });

  document.getElementById('tipo').addEventListener('change', () => {
    if (reconstruindoPlano) return;
    updateFormField(nomeForm, 'plano_n2_id', '');
    updateFormField(nomeForm, 'plano_n3_id', '');
    updateFormField(nomeForm, 'plano_n4_id', '');
    renderizarPlanoCascata();
  });
  document.getElementById('plano_n2_id').addEventListener('change', () => {
    if (reconstruindoPlano) return;
    sincronizarCamposPlanoSelecionados();
  });
  document.getElementById('plano_n3_id').addEventListener('change', () => {
    if (reconstruindoPlano) return;
    sincronizarCamposPlanoSelecionados();
  });
  document.getElementById('plano_n4_id').addEventListener('change', () => {
    if (reconstruindoPlano) return;
    sincronizarCamposPlanoSelecionados();
  });
  document.getElementById('contraparte_tipo').addEventListener('change', () => {
    updateFormField(nomeForm, 'contraparte_id', '');
    renderizarContrapartes();
  });
  document.getElementById('contraparte_tipo_cons').addEventListener('change', () => {
    updateFormField(nomeFormCons, 'contraparte_id_cons', '');
    renderizarContrapartesCons();
  });
  document.getElementById('data_emissao').addEventListener('change', (event) => {
    const dataEmissao = event.target.value || '';
    updateFormField(nomeForm, 'data_emissao', dataEmissao);
    updateFormField(nomeForm, 'data_vencimento', dataEmissao);
    document.getElementById('data_vencimento').value = dataEmissao;
  });

  renderizarSelectFiliais();
  renderizarSelectTipos();
  renderizarPlanoCascata();
  renderizarSelectPlanoCons();
  renderizarContraparteTipos();
  renderizarContrapartes();
  renderizarContraparteTiposCons();
  renderizarContrapartesCons();
  hidratarFormulario(nomeForm);
  if (getDataset('preload_registro_visualizar', false)) {
    renderizarPlanoCascata();
    renderizarContraparteTipos();
    renderizarContrapartes();
    hidratarFormulario(nomeForm);
    setFormState(nomeForm, 'visualizar');
    hidratarFormulario(nomeForm);
  }
  aplicarPermissoes();
  AppLoader.hide();
});
