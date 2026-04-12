import {
  updateFormField, getForm, updateState,
  clearMessages, definirMensagem,
  hidratarFormulario, setFormState, confirmar, getScreenPermissions, getDataBackEnd, getDataset,
} from '/static/js/sisVar.js';
import { fazerRequisicao } from '/static/js/base.js';
import { initSmartInputs } from '/static/js/input_rules.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { AppLoader } from '/static/js/loader.js';

const nomeForm = 'cadZonaEntrega';
const nomeFormCons = 'consZonaEntrega';
const form = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

getDataBackEnd();

function obterPermissoesZona() {
  return getScreenPermissions('zona_entrega', {
    acessar: false,
    consultar: false,
    incluir: false,
    editar: false,
    excluir: false,
  });
}

function podeExecutarAcao(acao) {
  return Boolean(obterPermissoesZona()?.[acao]);
}

function botaoDeveFicarVisivel(botao, estado) {
  return (botao.dataset.showOn || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .includes(estado);
}

function podeExibirBotaoPorPermissao(botaoId, estado) {
  if (botaoId === 'btn-novo') return podeExecutarAcao('incluir');
  if (botaoId === 'btn-editar') return podeExecutarAcao('editar');
  if (botaoId === 'btn-excluir') return podeExecutarAcao('excluir');
  if (botaoId === 'btn-salvar' || botaoId === 'btn-cancelar') {
    if (estado === 'novo') return podeExecutarAcao('incluir');
    if (estado === 'editar') return podeExecutarAcao('editar');
  }
  return true;
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
    selectPrincipal.innerHTML = '<option value="">Selecione</option>';
    filiais.forEach((filial) => {
      const option = document.createElement('option');
      option.value = String(filial.id);
      option.textContent = `${filial.codigo} - ${filial.nome}`;
      selectPrincipal.appendChild(option);
    });
    selectPrincipal.value = valorPrincipal;
  }

  if (selectPesquisa) {
    selectPesquisa.innerHTML = '<option value="">Todas</option>';
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

  if (!faixas.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Nenhuma faixa cadastrada.</td></tr>';
    return;
  }

  tbody.innerHTML = faixas.map((faixa, index) => `
    <tr data-index="${index}">
      <td>
        <select class="form-select faixa-tipo" ${bloqueado ? 'disabled' : ''}>
          <option value="CP4" ${faixa.tipo_intervalo === 'CP4' ? 'selected' : ''}>CP4</option>
          <option value="CP7" ${faixa.tipo_intervalo !== 'CP4' ? 'selected' : ''}>CP7</option>
        </select>
      </td>
      <td><input type="text" class="form-control faixa-inicial" maxlength="8" value="${faixa.codigo_postal_inicial || ''}" placeholder="0000-000" ${bloqueado ? 'disabled' : ''}></td>
      <td><input type="text" class="form-control faixa-final" maxlength="8" value="${faixa.codigo_postal_final || ''}" placeholder="0000-000" ${bloqueado ? 'disabled' : ''}></td>
      <td class="text-center"><input type="checkbox" class="form-check-input faixa-ativa" ${faixa.ativa !== false ? 'checked' : ''} ${bloqueado ? 'disabled' : ''}></td>
      <td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger btn-remover-faixa" ${bloqueado ? 'disabled' : ''}>Remover</button></td>
    </tr>
  `).join('');

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

  if (!excecoes.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Nenhuma exceção cadastrada.</td></tr>';
    return;
  }

  tbody.innerHTML = excecoes.map((excecao, index) => `
    <tr data-index="${index}">
      <td>
        <select class="form-select excecao-tipo" ${bloqueado ? 'disabled' : ''}>
          <option value="EXCLUIR" ${excecao.tipo_excecao !== 'INCLUIR' ? 'selected' : ''}>Excluir</option>
          <option value="INCLUIR" ${excecao.tipo_excecao === 'INCLUIR' ? 'selected' : ''}>Incluir</option>
        </select>
      </td>
      <td><input type="text" class="form-control excecao-codigo" maxlength="8" value="${excecao.codigo_postal || ''}" placeholder="0000-000" ${bloqueado ? 'disabled' : ''}></td>
      <td class="text-center"><input type="checkbox" class="form-check-input excecao-ativa" ${excecao.ativa !== false ? 'checked' : ''} ${bloqueado ? 'disabled' : ''}></td>
      <td><input type="text" class="form-control excecao-observacao" maxlength="200" value="${excecao.observacao || ''}" ${bloqueado ? 'disabled' : ''}></td>
      <td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger btn-remover-excecao" ${bloqueado ? 'disabled' : ''}>Remover</button></td>
    </tr>
  `).join('');

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
      hidratarFormulario(nomeForm);
      renderizarFaixas();
      renderizarExcecoes();
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
    tabelaCorpo.innerHTML = registros.map((registro) => `
      <tr>
        <td>${registro.id}</td>
        <td>${registro.filial}</td>
        <td>${registro.pais_atuacao || ''}</td>
        <td>${registro.codigo}</td>
        <td>${registro.descricao}</td>
        <td>${registro.ativa ? 'Sim' : 'Não'}</td>
        <td class="text-center"><button type="button" class="btn btn-sm btn-primary btn-selecionar" data-id="${registro.id}">Selecionar</button></td>
      </tr>
    `).join('');
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
    hidratarFormulario(nomeForm);
    renderizarFaixas();
    renderizarExcecoes();
    aplicarPermissoesNaInterface();
    alternarTelas();
  });

  renderizarFiliais();
  hidratarFormulario(nomeForm);
  renderizarFaixas();
  renderizarExcecoes();
  aplicarPermissoesNaInterface();
  AppLoader.hide();
});
