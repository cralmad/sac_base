import {
  updateFormField, getForm, updateState,
  clearMessages, definirMensagem,
  hidratarFormulario, setFormState, confirmar, getScreenPermissions, getDataBackEnd, getDataset,
} from '/static/js/sisVar.js';
import { fazerRequisicao } from '/static/js/base.js';
import { initSmartInputs } from '/static/js/input_rules.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { AppLoader } from '/static/js/loader.js';
import { buttonVisibleByState, buttonAllowedByPermission, createActionChecker } from '/static/js/screen_permissions.js';

const nomeForm = 'cadRegistroFinanceiro';
const nomeFormCons = 'consRegistroFinanceiro';
const form = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

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

function classTipoParaPlano(tipo) {
  if (tipo === 'ENTRADA') return 'receita';
  if (tipo === 'SAIDA') return 'despesa';
  return '';
}

function renderizarSelectPlanos() {
  const planos = getPlanos();
  const tipoAtual = String(getForm(nomeForm)?.campos?.tipo ?? '');
  const classe = classTipoParaPlano(tipoAtual);
  const planosFiltrados = classe ? planos.filter((p) => p.tipo_classificacao === classe) : planos;
  const principal = document.getElementById('plano_contas_id');
  const pesquisa = document.getElementById('plano_cons');
  const vPrincipal = String(getForm(nomeForm)?.campos?.plano_contas_id ?? '');
  const vPesquisa = String(getForm(nomeFormCons)?.campos?.plano_cons ?? '');
  principal.innerHTML = '<option value="">Selecione</option>';
  pesquisa.innerHTML = '<option value="">Todos</option>';
  planosFiltrados.forEach((plano) => {
    const label = `${plano.codigo} - ${plano.nome}`;
    const op1 = document.createElement('option');
    op1.value = String(plano.id);
    op1.textContent = label;
    principal.appendChild(op1);
    const op2 = document.createElement('option');
    op2.value = String(plano.id);
    op2.textContent = label;
    pesquisa.appendChild(op2);
  });
  const existePlano = planosFiltrados.some((p) => String(p.id) === vPrincipal);
  principal.value = existePlano ? vPrincipal : '';
  if (!existePlano) updateFormField(nomeForm, 'plano_contas_id', '');
  pesquisa.value = vPesquisa;
}

function renderizarContraparteTipos() {
  const tipos = getContraparteTipos();
  const select = document.getElementById('contraparte_tipo');
  const valor = String(getForm(nomeForm)?.campos?.contraparte_tipo ?? '');
  select.innerHTML = '<option value="">Sem contraparte</option>';
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

function aplicarDefaultsNovo() {
  updateFormField(nomeForm, 'tipo', 'ENTRADA');
  updateFormField(nomeForm, 'filial_id', getFilialAtivaId());
  updateFormField(nomeForm, 'contraparte_tipo', '');
  updateFormField(nomeForm, 'contraparte_id', '');
  updateFormField(nomeForm, 'status', 'aberto');
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
    [registro.id, registro.filial, registro.tipo, registro.plano, registro.valor, registro.valor_rest, registro.status]
      .forEach((valor) => {
        const td = document.createElement('td');
        td.textContent = String(valor ?? '');
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
  const btnCancelar = document.getElementById('btn-cancelar');
  const btnAbrirPesquisa = document.getElementById('btn-abrir-pesquisa');
  const btnVoltar = document.getElementById('btn-voltar');
  const btnFechar = document.getElementById('btn-fechar');
  const divForm = document.getElementById(nomeForm);
  const divPesquisa = document.getElementById('div-pesquisa');

  function aplicarPermissoes() {
    const estado = getForm(nomeForm)?.estado ?? 'visualizar';
    [btnSalvar, btnEditar, btnNovo, btnExcluir, btnCancelar].forEach((btn) => {
      const visivelEstado = buttonVisibleByState(btn, estado);
      const visivelPerm = buttonAllowedByPermission({ buttonId: btn.id, state: estado, canExecute: podeExecutarAcao });
      btn.classList.toggle('d-none', !(visivelEstado && visivelPerm));
    });
    btnAbrirPesquisa.classList.toggle('d-none', !podeExecutarAcao('consultar'));
  }

  function alternarTela() {
    divForm.classList.toggle('d-none');
    divPesquisa.classList.toggle('d-none');
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearMessages();
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
        renderizarSelectPlanos();
        renderizarSelectTipos();
        renderizarContraparteTipos();
        renderizarContrapartes();
        hidratarFormulario(nomeForm);
        aplicarPermissoes();
      },
    });
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
  btnExcluir.addEventListener('click', () => {
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
        setFormState(nomeForm, 'novo');
        aplicarDefaultsNovo();
        aplicarPermissoes();
      },
    });
  });
  btnAbrirPesquisa.addEventListener('click', alternarTela);
  btnVoltar.addEventListener('click', alternarTela);
  btnFechar.addEventListener('click', alternarTela);

  form2.addEventListener('submit', async (event) => {
    event.preventDefault();
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
    const registros = result.data?.records ?? [];
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
    renderizarSelectPlanos();
    renderizarSelectTipos();
    renderizarContraparteTipos();
    renderizarContrapartes();
    hidratarFormulario(nomeForm);
    alternarTela();
    aplicarPermissoes();
  });

  document.getElementById('tipo').addEventListener('change', () => {
    renderizarSelectPlanos();
  });
  document.getElementById('contraparte_tipo').addEventListener('change', () => {
    updateFormField(nomeForm, 'contraparte_id', '');
    renderizarContrapartes();
  });

  renderizarSelectFiliais();
  renderizarSelectTipos();
  renderizarSelectPlanos();
  renderizarContraparteTipos();
  renderizarContrapartes();
  hidratarFormulario(nomeForm);
  aplicarPermissoes();
  AppLoader.hide();
});
