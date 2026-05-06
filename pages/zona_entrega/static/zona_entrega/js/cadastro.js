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

const nomeForm = 'cadZonaEntrega';
const nomeFormCons = 'consZonaEntrega';
const form = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

getDataBackEnd();

const podeExecutarAcao = createActionChecker({
  screenKey: 'zona_entrega',
  getScreenPermissions,
  fallback: {
    acessar: false,
    consultar: false,
    incluir: false,
    editar: false,
    excluir: false,
  },
});

function botaoDeveFicarVisivel(botao, estado) {
  return buttonVisibleByState(botao, estado);
}

function podeExibirBotaoPorPermissao(botaoId, estado) {
  return buttonAllowedByPermission({ buttonId: botaoId, state: estado, canExecute: podeExecutarAcao });
}

function obterPermissoesZona() {
  return {
    acessar: podeExecutarAcao('acessar'),
    consultar: podeExecutarAcao('consultar'),
    incluir: podeExecutarAcao('incluir'),
    editar: podeExecutarAcao('editar'),
    excluir: podeExecutarAcao('excluir'),
  };
}

function getFiliaisAtuacao() {
  return getDataset('filiais_atuacao', []);
}

function getFilialSelecionada() {
  const filialId = String(getForm(nomeForm)?.campos?.filial_id ?? '');
  return getFiliaisAtuacao().find((filial) => String(filial.id) === filialId) || null;
}

function renderizarFiliais() {
  const selectPrincipal = document.getElementById('filial_id');
  const selectPesquisa = document.getElementById('filial_cons');
  const filiais = getFiliaisAtuacao();
  const valorPrincipal = String(getForm(nomeForm)?.campos?.filial_id ?? '');
  const valorPesquisa = String(getForm(nomeFormCons)?.campos?.filial_cons ?? '');

  if (selectPrincipal) {
    selectPrincipal.innerHTML = '';
    const optionPadraoPrincipal = document.createElement('option');
    optionPadraoPrincipal.value = '';
    optionPadraoPrincipal.textContent = 'Selecione';
    selectPrincipal.appendChild(optionPadraoPrincipal);
    filiais.forEach((filial) => {
      const option = document.createElement('option');
      option.value = String(filial.id);
      option.textContent = `${filial.codigo} - ${filial.nome}`;
      selectPrincipal.appendChild(option);
    });
    selectPrincipal.value = valorPrincipal;
  }

  if (selectPesquisa) {
    selectPesquisa.innerHTML = '';
    const optionPadraoPesquisa = document.createElement('option');
    optionPadraoPesquisa.value = '';
    optionPadraoPesquisa.textContent = 'Todas';
    selectPesquisa.appendChild(optionPadraoPesquisa);
    filiais.forEach((filial) => {
      const option = document.createElement('option');
      option.value = String(filial.id);
      option.textContent = `${filial.codigo} - ${filial.nome}`;
      selectPesquisa.appendChild(option);
    });
    selectPesquisa.value = valorPesquisa;
  }

  const paisInfo = document.getElementById('pais_atuacao_info');
  if (paisInfo) {
    const filial = getFilialSelecionada();
    paisInfo.textContent = filial ? `${filial.pais_atuacao_nome} (${filial.pais_atuacao_sigla})` : 'Selecione uma matriz/filial';
  }
}

function getPaisAtuacaoSigla() {
  return getFilialSelecionada()?.pais_atuacao_sigla || '';
}

function formEmVisualizacao() {
  return (getForm(nomeForm)?.estado ?? 'visualizar') === 'visualizar';
}

function atualizarFaixasNoSisVar() {
  const faixas = [];
  document.querySelectorAll('#tabela-faixas-zona tr[data-index]').forEach((row) => {
    faixas.push({
      tipo_intervalo: row.querySelector('.faixa-tipo')?.value || 'CP7',
      codigo_postal_inicial: row.querySelector('.faixa-inicial')?.value || '',
      codigo_postal_final: row.querySelector('.faixa-final')?.value || '',
      ativa: Boolean(row.querySelector('.faixa-ativa')?.checked),
    });
  });
  updateFormField(nomeForm, 'faixas', faixas);
}

function atualizarExcecoesNoSisVar() {
  const excecoes = [];
  document.querySelectorAll('#tabela-excecoes-zona tr[data-index]').forEach((row) => {
    excecoes.push({
      tipo_excecao: row.querySelector('.excecao-tipo')?.value || 'EXCLUIR',
      codigo_postal: row.querySelector('.excecao-codigo')?.value || '',
      ativa: Boolean(row.querySelector('.excecao-ativa')?.checked),
      observacao: row.querySelector('.excecao-observacao')?.value || '',
    });
  });
  updateFormField(nomeForm, 'excecoes', excecoes);
}

function renderizarFaixas() {
  const tbody = document.getElementById('tabela-faixas-zona');
  if (!tbody) return;
  const faixas = getForm(nomeForm)?.campos?.faixas || [];
  const bloqueado = formEmVisualizacao();

  tbody.innerHTML = '';

  if (!faixas.length) {
    const trVazio = document.createElement('tr');
    const tdVazio = document.createElement('td');
    tdVazio.colSpan = 5;
    tdVazio.className = 'text-center text-muted';
    tdVazio.textContent = 'Nenhuma faixa cadastrada.';
    trVazio.appendChild(tdVazio);
    tbody.appendChild(trVazio);
    return;
  }

  faixas.forEach((faixa, index) => {
    const tr = document.createElement('tr');
    tr.dataset.index = String(index);

    const tdTipo = document.createElement('td');
    const selectTipo = document.createElement('select');
    selectTipo.className = 'form-select faixa-tipo';
    selectTipo.disabled = bloqueado;
    ['CP4', 'CP7'].forEach((tipo) => {
      const opt = document.createElement('option');
      opt.value = tipo;
      opt.textContent = tipo;
      opt.selected = (faixa.tipo_intervalo === 'CP4' && tipo === 'CP4') || (faixa.tipo_intervalo !== 'CP4' && tipo === 'CP7');
      selectTipo.appendChild(opt);
    });
    tdTipo.appendChild(selectTipo);

    const tdInicial = document.createElement('td');
    const inputInicial = document.createElement('input');
    inputInicial.type = 'text';
    inputInicial.className = 'form-control faixa-inicial';
    inputInicial.maxLength = 8;
    inputInicial.value = faixa.codigo_postal_inicial || '';
    inputInicial.placeholder = '0000-000';
    inputInicial.disabled = bloqueado;
    tdInicial.appendChild(inputInicial);

    const tdFinal = document.createElement('td');
    const inputFinal = document.createElement('input');
    inputFinal.type = 'text';
    inputFinal.className = 'form-control faixa-final';
    inputFinal.maxLength = 8;
    inputFinal.value = faixa.codigo_postal_final || '';
    inputFinal.placeholder = '0000-000';
    inputFinal.disabled = bloqueado;
    tdFinal.appendChild(inputFinal);

    const tdAtiva = document.createElement('td');
    tdAtiva.className = 'text-center';
    const inputAtiva = document.createElement('input');
    inputAtiva.type = 'checkbox';
    inputAtiva.className = 'form-check-input faixa-ativa';
    inputAtiva.checked = faixa.ativa !== false;
    inputAtiva.disabled = bloqueado;
    tdAtiva.appendChild(inputAtiva);

    const tdAcao = document.createElement('td');
    tdAcao.className = 'text-center';
    const btnRemover = document.createElement('button');
    btnRemover.type = 'button';
    btnRemover.className = 'btn btn-sm btn-outline-danger btn-remover-faixa';
    btnRemover.disabled = bloqueado;
    btnRemover.textContent = 'Remover';
    tdAcao.appendChild(btnRemover);

    tr.appendChild(tdTipo);
    tr.appendChild(tdInicial);
    tr.appendChild(tdFinal);
    tr.appendChild(tdAtiva);
    tr.appendChild(tdAcao);
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll('input, select').forEach((input) => {
    input.addEventListener('input', atualizarFaixasNoSisVar);
    input.addEventListener('change', atualizarFaixasNoSisVar);
  });
  tbody.querySelectorAll('.btn-remover-faixa').forEach((button) => {
    button.addEventListener('click', () => {
      const proximasFaixas = (getForm(nomeForm)?.campos?.faixas || []).filter((_, idx) => idx !== Number(button.closest('tr')?.dataset.index));
      updateFormField(nomeForm, 'faixas', proximasFaixas);
      renderizarFaixas();
    });
  });
}

function renderizarExcecoes() {
  const tbody = document.getElementById('tabela-excecoes-zona');
  if (!tbody) return;
  const excecoes = getForm(nomeForm)?.campos?.excecoes || [];
  const bloqueado = formEmVisualizacao();

  tbody.innerHTML = '';

  if (!excecoes.length) {
    const trVazio = document.createElement('tr');
    const tdVazio = document.createElement('td');
    tdVazio.colSpan = 5;
    tdVazio.className = 'text-center text-muted';
    tdVazio.textContent = 'Nenhuma exceção cadastrada.';
    trVazio.appendChild(tdVazio);
    tbody.appendChild(trVazio);
    return;
  }

  excecoes.forEach((excecao, index) => {
    const tr = document.createElement('tr');
    tr.dataset.index = String(index);

    const tdTipo = document.createElement('td');
    const selectTipo = document.createElement('select');
    selectTipo.className = 'form-select excecao-tipo';
    selectTipo.disabled = bloqueado;
    const optExcluir = document.createElement('option');
    optExcluir.value = 'EXCLUIR';
    optExcluir.textContent = 'Excluir';
    optExcluir.selected = excecao.tipo_excecao !== 'INCLUIR';
    const optIncluir = document.createElement('option');
    optIncluir.value = 'INCLUIR';
    optIncluir.textContent = 'Incluir';
    optIncluir.selected = excecao.tipo_excecao === 'INCLUIR';
    selectTipo.appendChild(optExcluir);
    selectTipo.appendChild(optIncluir);
    tdTipo.appendChild(selectTipo);

    const tdCodigo = document.createElement('td');
    const inputCodigo = document.createElement('input');
    inputCodigo.type = 'text';
    inputCodigo.className = 'form-control excecao-codigo';
    inputCodigo.maxLength = 8;
    inputCodigo.value = excecao.codigo_postal || '';
    inputCodigo.placeholder = '0000-000';
    inputCodigo.disabled = bloqueado;
    tdCodigo.appendChild(inputCodigo);

    const tdAtiva = document.createElement('td');
    tdAtiva.className = 'text-center';
    const inputAtiva = document.createElement('input');
    inputAtiva.type = 'checkbox';
    inputAtiva.className = 'form-check-input excecao-ativa';
    inputAtiva.checked = excecao.ativa !== false;
    inputAtiva.disabled = bloqueado;
    tdAtiva.appendChild(inputAtiva);

    const tdObs = document.createElement('td');
    const inputObs = document.createElement('input');
    inputObs.type = 'text';
    inputObs.className = 'form-control excecao-observacao';
    inputObs.maxLength = 200;
    inputObs.value = excecao.observacao || '';
    inputObs.disabled = bloqueado;
    tdObs.appendChild(inputObs);

    const tdAcao = document.createElement('td');
    tdAcao.className = 'text-center';
    const btnRemover = document.createElement('button');
    btnRemover.type = 'button';
    btnRemover.className = 'btn btn-sm btn-outline-danger btn-remover-excecao';
    btnRemover.disabled = bloqueado;
    btnRemover.textContent = 'Remover';
    tdAcao.appendChild(btnRemover);

    tr.appendChild(tdTipo);
    tr.appendChild(tdCodigo);
    tr.appendChild(tdAtiva);
    tr.appendChild(tdObs);
    tr.appendChild(tdAcao);
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll('input, select').forEach((input) => {
    input.addEventListener('input', atualizarExcecoesNoSisVar);
    input.addEventListener('change', atualizarExcecoesNoSisVar);
  });
  tbody.querySelectorAll('.btn-remover-excecao').forEach((button) => {
    button.addEventListener('click', () => {
      const proximasExcecoes = (getForm(nomeForm)?.campos?.excecoes || []).filter((_, idx) => idx !== Number(button.closest('tr')?.dataset.index));
      updateFormField(nomeForm, 'excecoes', proximasExcecoes);
      renderizarExcecoes();
    });
  });
}

function validarCodigosPostaisPortugal() {
  if (getPaisAtuacaoSigla() !== 'PRT') return true;

  const regex = /^\d{4}-\d{3}$/;
  const faixas = getForm(nomeForm)?.campos?.faixas || [];
  const excecoes = getForm(nomeForm)?.campos?.excecoes || [];

  for (const faixa of faixas) {
    if (!regex.test(faixa.codigo_postal_inicial || '') || !regex.test(faixa.codigo_postal_final || '')) {
      definirMensagem('erro', 'Para Portugal, todas as faixas devem usar o formato XXXX-XXX.', false);
      return false;
    }
  }

  for (const excecao of excecoes) {
    if (!regex.test(excecao.codigo_postal || '')) {
      definirMensagem('erro', 'Para Portugal, todas as exceções devem usar o formato XXXX-XXX.', false);
      return false;
    }
  }

  return true;
}

function aplicarDefaultsNovo() {
  updateFormField(nomeForm, 'ativa', true);
  updateFormField(nomeForm, 'prioridade', 0);
  updateFormField(nomeForm, 'valor_cobranca_unitario_pedido', '0.00');
  updateFormField(nomeForm, 'valor_pagamento_unitario_entrega', '0.00');
  updateFormField(nomeForm, 'valor_pagamento_fixo_rota', '0.00');
  updateFormField(nomeForm, 'valor_pagamento_unitario_entrega_pesado', '0.00');
  updateFormField(nomeForm, 'valor_pagamento_fixo_rota_pesado', '0.00');
  updateFormField(nomeForm, 'faixas', []);
  updateFormField(nomeForm, 'excecoes', []);
  renderizarFaixas();
  renderizarExcecoes();
  hidratarFormulario(nomeForm);
}

const updater = criarAtualizadorForm({ formId: nomeForm, setter: updateFormField, form });
form.addEventListener('input', updater);
form.addEventListener('change', updater);
initSmartInputs((input, value) => { updateFormField(nomeForm, input.name, value); });

const updater2 = criarAtualizadorForm({ formId: nomeFormCons, setter: updateFormField, form: form2 });
form2.addEventListener('input', updater2);
form2.addEventListener('change', updater2);

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearMessages();
  atualizarFaixasNoSisVar();
  atualizarExcecoesNoSisVar();

  if (!validarCodigosPostaisPortugal()) {
    return;
  }

  const formData = getForm(nomeForm);
  confirmar({
    titulo: 'Confirmar Salvamento',
    mensagem: 'Deseja salvar a zona de entrega?',
    onConfirmar: async () => {
      AppLoader.show();
      const resultado = await fazerRequisicao('/app/logistica/zona-entrega/', {
        form: { [nomeForm]: formData },
      });
      AppLoader.hide();

      if (!resultado.success) {
        if (resultado.data) updateState(resultado.data);
        else definirMensagem('erro', `Erro: ${resultado.error}`, false);
        return;
      }

      updateState(resultado.data);
      renderizarFiliais();
      renderizarFaixas();
      renderizarExcecoes();
      hidratarFormulario(nomeForm);
    },
  });
});

document.addEventListener('DOMContentLoaded', () => {
  AppLoader.show();

  const divPrincipal = document.getElementById(nomeForm);
  const divPesquisa = document.getElementById('div-pesquisa');
  const btnAbrirPesquisa = document.getElementById('btn-abrir-pesquisa');
  const btnVoltar = document.getElementById('btn-voltar');
  const btnFechar = document.getElementById('btn-fechar');
  const btnEditar = document.getElementById('btn-editar');
  const btnNovo = document.getElementById('btn-novo');
  const btnExcluir = document.getElementById('btn-excluir');
  const btnCancelar = document.getElementById('btn-cancelar');
  const btnSalvar = document.getElementById('btn-salvar');
  const tabelaCorpo = document.getElementById('tabela-zona-corpo');
  const btnAddFaixa = document.getElementById('btn-add-faixa');
  const btnAddExcecao = document.getElementById('btn-add-excecao');
  const selectFilial = document.getElementById('filial_id');

  function aplicarPermissoesNaInterface() {
    const permissoes = obterPermissoesZona();
    const estadoAtual = getForm(nomeForm)?.estado ?? 'visualizar';
    const botoesControlados = [btnSalvar, btnEditar, btnNovo, btnExcluir, btnCancelar];
    const bloqueado = estadoAtual === 'visualizar';

    btnAbrirPesquisa.classList.toggle('d-none', !permissoes.consultar);
    btnAddFaixa.disabled = bloqueado;
    btnAddExcecao.disabled = bloqueado;

    botoesControlados.forEach((botao) => {
      const visivelNoEstado = botaoDeveFicarVisivel(botao, estadoAtual);
      const visivelNaPermissao = podeExibirBotaoPorPermissao(botao.id, estadoAtual);
      botao.classList.toggle('d-none', !(visivelNoEstado && visivelNaPermissao));
    });
  }

  function resetarFormularioAposCancelamento() {
    setFormState(nomeForm, podeExecutarAcao('incluir') ? 'novo' : 'visualizar');

    if (podeExecutarAcao('incluir')) {
      aplicarDefaultsNovo();
    } else {
      updateFormField(nomeForm, 'faixas', []);
      updateFormField(nomeForm, 'excecoes', []);
      renderizarFaixas();
      renderizarExcecoes();
      hidratarFormulario(nomeForm);
    }

    renderizarFiliais();
    aplicarPermissoesNaInterface();
  }

  function alternarTelas() {
    divPrincipal.classList.toggle('d-none');
    divPesquisa.classList.toggle('d-none');
  }

  function renderizarTabela(registros) {
    tabelaCorpo.innerHTML = '';
    registros.forEach((registro) => {
      const tr = document.createElement('tr');

      [
        registro.id,
        registro.filial,
        registro.pais_atuacao || '',
        registro.codigo,
        registro.descricao,
        registro.ativa ? 'Sim' : 'Não',
      ].forEach((valor) => {
        const td = document.createElement('td');
        td.textContent = String(valor ?? '');
        tr.appendChild(td);
      });

      const tdAcao = document.createElement('td');
      tdAcao.className = 'text-center';
      const btnSelecionar = document.createElement('button');
      btnSelecionar.type = 'button';
      btnSelecionar.className = 'btn btn-sm btn-primary btn-selecionar';
      btnSelecionar.dataset.id = String(registro.id ?? '');
      btnSelecionar.textContent = 'Selecionar';
      tdAcao.appendChild(btnSelecionar);
      tr.appendChild(tdAcao);

      tabelaCorpo.appendChild(tr);
    });
  }

  btnAbrirPesquisa.addEventListener('click', alternarTelas);
  btnVoltar.addEventListener('click', alternarTelas);
  btnFechar.addEventListener('click', alternarTelas);

  selectFilial?.addEventListener('change', renderizarFiliais);

  btnAddFaixa.addEventListener('click', () => {
    if (formEmVisualizacao()) return;
    const faixas = [...(getForm(nomeForm)?.campos?.faixas || []), { tipo_intervalo: 'CP7', codigo_postal_inicial: '', codigo_postal_final: '', ativa: true }];
    updateFormField(nomeForm, 'faixas', faixas);
    renderizarFaixas();
  });

  btnAddExcecao.addEventListener('click', () => {
    if (formEmVisualizacao()) return;
    const excecoes = [...(getForm(nomeForm)?.campos?.excecoes || []), { tipo_excecao: 'EXCLUIR', codigo_postal: '', ativa: true, observacao: '' }];
    updateFormField(nomeForm, 'excecoes', excecoes);
    renderizarExcecoes();
  });

  btnEditar.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('editar')) {
      definirMensagem('erro', 'Você não possui permissão para editar zona de entrega.', false);
      return;
    }
    setFormState(nomeForm, 'editar');
    renderizarFaixas();
    renderizarExcecoes();
    aplicarPermissoesNaInterface();
  });

  btnNovo.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('incluir')) {
      definirMensagem('erro', 'Você não possui permissão para incluir zona de entrega.', false);
      return;
    }
    setFormState(nomeForm, 'novo');
    aplicarDefaultsNovo();
    renderizarFiliais();
    aplicarPermissoesNaInterface();
  });

  btnCancelar.addEventListener('click', () => {
    confirmar({
      titulo: 'Confirmar Cancelamento',
      mensagem: 'Deseja cancelar? Os dados não salvos serão perdidos.',
      onConfirmar: () => resetarFormularioAposCancelamento(),
    });
  });

  btnExcluir.addEventListener('click', () => {
    const formData = getForm(nomeForm);
    confirmar({
      titulo: 'Confirmar Exclusão',
      mensagem: `Deseja excluir a zona de entrega "${formData?.campos?.descricao || ''}"?`,
      onConfirmar: async () => {
        clearMessages();
        if (!podeExecutarAcao('excluir')) {
          definirMensagem('erro', 'Você não possui permissão para excluir zona de entrega.', false);
          return;
        }
        AppLoader.show();
        const resultado = await fazerRequisicao('/app/logistica/zona-entrega/del', {
          form: { [nomeForm]: formData },
        });
        AppLoader.hide();
        if (!resultado.success) {
          if (resultado.data) updateState(resultado.data);
          else definirMensagem('erro', `Erro: ${resultado.error}`, false);
          return;
        }
        updateState(resultado.data);
        setFormState(nomeForm, podeExecutarAcao('incluir') ? 'novo' : 'visualizar');
        aplicarDefaultsNovo();
        renderizarFiliais();
        aplicarPermissoesNaInterface();
      },
    });
  });

  form2.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearMessages();
    if (!podeExecutarAcao('consultar')) {
      definirMensagem('erro', 'Você não possui permissão para consultar zona de entrega.', false);
      return;
    }
    AppLoader.show();
    const resultado = await fazerRequisicao('/app/logistica/zona-entrega/cons', {
      form: { [nomeFormCons]: getForm(nomeFormCons) },
    });
    AppLoader.hide();
    if (!resultado.success) {
      if (resultado.data) updateState(resultado.data);
      else definirMensagem('erro', `Erro: ${resultado.error}`, false);
      return;
    }
    updateState(resultado.data);
    aplicarPermissoesNaInterface();
    if (resultado.data?.registros?.length) {
      renderizarTabela(resultado.data.registros);
    } else {
      tabelaCorpo.innerHTML = '';
      definirMensagem('info', 'Nenhuma zona de entrega encontrada.');
    }
  });

  tabelaCorpo.addEventListener('click', async (event) => {
    if (!event.target.classList.contains('btn-selecionar')) return;

    const id = event.target.dataset.id;
    AppLoader.show();
    updateFormField(nomeFormCons, 'id_selecionado', id);
    const payload = { form: { [nomeFormCons]: structuredClone(getForm(nomeFormCons)) } };
    updateFormField(nomeFormCons, 'id_selecionado', null);

    const resultado = await fazerRequisicao('/app/logistica/zona-entrega/cons', payload);
    AppLoader.hide();
    if (!resultado.success) {
      if (resultado.data) updateState(resultado.data);
      else definirMensagem('erro', `Erro: ${resultado.error}`, false);
      return;
    }
    updateState(resultado.data);
    renderizarFiliais();
    renderizarFaixas();
    renderizarExcecoes();
    hidratarFormulario(nomeForm);
    aplicarPermissoesNaInterface();
    alternarTelas();
  });

  renderizarFiliais();
  renderizarFaixas();
  renderizarExcecoes();
  hidratarFormulario(nomeForm);
  aplicarPermissoesNaInterface();
  AppLoader.hide();
});
