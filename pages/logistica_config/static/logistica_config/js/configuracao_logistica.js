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

const nomeForm = 'cadConfigLogistica';
const nomeFormCons = 'consConfigLogistica';
const form = document.getElementById(nomeForm);
const form2 = document.getElementById('consConfigLogistica');

const URL_BASE = '/app/logistica/configuracao-logistica/';

getDataBackEnd();

const podeExecutarAcao = createActionChecker({
  screenKey: 'logistica_config',
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

function obterPermissoes() {
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
  return getFiliaisAtuacao().find((f) => String(f.id) === filialId) || null;
}

function renderizarFiliais() {
  const selectPrincipal = document.getElementById('filial_id');
  const selectPesquisa = document.getElementById('filial_cons');
  const filiais = getFiliaisAtuacao();
  const valorPrincipal = String(getForm(nomeForm)?.campos?.filial_id ?? '');
  const valorPesquisa = String(getForm(nomeFormCons)?.campos?.filial_cons ?? '');

  if (selectPrincipal) {
    selectPrincipal.replaceChildren();
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
    selectPesquisa.replaceChildren();
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

function formEmVisualizacao() {
  return (getForm(nomeForm)?.estado ?? 'visualizar') === 'visualizar';
}

function atualizarExcecoesNoSisVar() {
  const excecoes = [];
  document.querySelectorAll('#tabela-excecoes-cfg tr[data-index]').forEach((row) => {
    excecoes.push({
      data: row.querySelector('.excecao-data')?.value || '',
      pesado_reservado: row.querySelector('.excecao-pesado')?.value || '0',
      ligeiro_reservado: row.querySelector('.excecao-ligeiro')?.value || '0',
    });
  });
  updateFormField(nomeForm, 'excecoes', excecoes);
}

function renderizarExcecoes() {
  const tbody = document.getElementById('tabela-excecoes-cfg');
  if (!tbody) return;
  const excecoes = getForm(nomeForm)?.campos?.excecoes || [];
  const bloqueado = formEmVisualizacao();

  tbody.replaceChildren();

  if (!excecoes.length) {
    const trVazio = document.createElement('tr');
    const tdVazio = document.createElement('td');
    tdVazio.colSpan = 4;
    tdVazio.className = 'text-center text-muted';
    tdVazio.textContent = 'Nenhuma data de exceção.';
    trVazio.appendChild(tdVazio);
    tbody.appendChild(trVazio);
    return;
  }

  excecoes.forEach((excecao, index) => {
    const tr = document.createElement('tr');
    tr.dataset.index = String(index);

    const tdData = document.createElement('td');
    const inputData = document.createElement('input');
    inputData.type = 'date';
    inputData.className = 'form-control excecao-data';
    inputData.value = excecao.data || '';
    inputData.disabled = bloqueado;
    tdData.appendChild(inputData);

    const tdPesado = document.createElement('td');
    const inputPesado = document.createElement('input');
    inputPesado.type = 'number';
    inputPesado.className = 'form-control excecao-pesado';
    inputPesado.min = '0';
    inputPesado.max = '32767';
    inputPesado.step = '1';
    inputPesado.value = excecao.pesado_reservado ?? '0';
    inputPesado.disabled = bloqueado;
    tdPesado.appendChild(inputPesado);

    const tdLigeiro = document.createElement('td');
    const inputLigeiro = document.createElement('input');
    inputLigeiro.type = 'number';
    inputLigeiro.className = 'form-control excecao-ligeiro';
    inputLigeiro.min = '0';
    inputLigeiro.max = '32767';
    inputLigeiro.step = '1';
    inputLigeiro.value = excecao.ligeiro_reservado ?? '0';
    inputLigeiro.disabled = bloqueado;
    tdLigeiro.appendChild(inputLigeiro);

    const tdAcao = document.createElement('td');
    tdAcao.className = 'text-center';
    const btnRemover = document.createElement('button');
    btnRemover.type = 'button';
    btnRemover.className = 'btn btn-sm btn-outline-danger btn-remover-excecao-cfg';
    btnRemover.disabled = bloqueado;
    btnRemover.textContent = 'Remover';
    tdAcao.appendChild(btnRemover);

    tr.appendChild(tdData);
    tr.appendChild(tdPesado);
    tr.appendChild(tdLigeiro);
    tr.appendChild(tdAcao);
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll('input').forEach((input) => {
    input.addEventListener('input', atualizarExcecoesNoSisVar);
    input.addEventListener('change', atualizarExcecoesNoSisVar);
  });
  tbody.querySelectorAll('.btn-remover-excecao-cfg').forEach((button) => {
    button.addEventListener('click', () => {
      const idx = Number(button.closest('tr')?.dataset.index);
      const proximas = (getForm(nomeForm)?.campos?.excecoes || []).filter((_, i) => i !== idx);
      updateFormField(nomeForm, 'excecoes', proximas);
      renderizarExcecoes();
    });
  });
}

function aplicarDefaultsNovo() {
  updateFormField(nomeForm, 'id', null);
  updateFormField(nomeForm, 'pedidos_pesado', '0');
  updateFormField(nomeForm, 'pesado_reservado', '0');
  updateFormField(nomeForm, 'valor_unitario_pesado', '0.00');
  updateFormField(nomeForm, 'pedidos_ligeiro', '0');
  updateFormField(nomeForm, 'ligeiro_reservado', '0');
  updateFormField(nomeForm, 'valor_unitario_ligeiro', '0.00');
  updateFormField(nomeForm, 'valor_excedente', '0.00');
  updateFormField(nomeForm, 'excecoes', []);
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
  atualizarExcecoesNoSisVar();
  const formData = getForm(nomeForm);
  confirmar({
    titulo: 'Confirmar Salvamento',
    mensagem: 'Deseja salvar a configuração de logística?',
    onConfirmar: async () => {
      AppLoader.show();
      const resultado = await fazerRequisicao(URL_BASE, {
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
  const tabelaCorpo = document.getElementById('tabela-cfg-corpo');
  const btnAddExcecao = document.getElementById('btn-add-excecao-cfg');
  const selectFilial = document.getElementById('filial_id');

  function aplicarPermissoesNaInterface() {
    const permissoes = obterPermissoes();
    const estadoAtual = getForm(nomeForm)?.estado ?? 'visualizar';
    const botoesControlados = [btnSalvar, btnEditar, btnNovo, btnExcluir, btnCancelar];
    const bloqueado = estadoAtual === 'visualizar';

    btnAbrirPesquisa.classList.toggle('d-none', !permissoes.consultar);
    if (btnAddExcecao) btnAddExcecao.disabled = bloqueado;

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
      updateFormField(nomeForm, 'excecoes', []);
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
    tabelaCorpo.replaceChildren();
    registros.forEach((registro) => {
      const tr = document.createElement('tr');
      [registro.id, registro.filial, registro.pedidos_pesado, registro.pedidos_ligeiro].forEach((valor) => {
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

  btnAddExcecao?.addEventListener('click', () => {
    if (formEmVisualizacao()) return;
    const excecoes = [...(getForm(nomeForm)?.campos?.excecoes || []), { data: '', pesado_reservado: '0', ligeiro_reservado: '0' }];
    updateFormField(nomeForm, 'excecoes', excecoes);
    renderizarExcecoes();
  });

  btnEditar.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('editar')) {
      definirMensagem('erro', 'Você não possui permissão para editar.', false);
      return;
    }
    setFormState(nomeForm, 'editar');
    renderizarExcecoes();
    aplicarPermissoesNaInterface();
  });

  btnNovo.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('incluir')) {
      definirMensagem('erro', 'Você não possui permissão para incluir.', false);
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
      mensagem: 'Deseja excluir esta configuração de logística?',
      onConfirmar: async () => {
        clearMessages();
        if (!podeExecutarAcao('excluir')) {
          definirMensagem('erro', 'Você não possui permissão para excluir.', false);
          return;
        }
        AppLoader.show();
        const resultado = await fazerRequisicao(`${URL_BASE}del`, {
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
      definirMensagem('erro', 'Você não possui permissão para consultar.', false);
      return;
    }
    AppLoader.show();
    const resultado = await fazerRequisicao(`${URL_BASE}cons`, {
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
      tabelaCorpo.replaceChildren();
      definirMensagem('info', 'Nenhuma configuração encontrada.');
    }
  });

  tabelaCorpo.addEventListener('click', async (event) => {
    if (!event.target.classList.contains('btn-selecionar')) return;
    const id = event.target.dataset.id;
    AppLoader.show();
    updateFormField(nomeFormCons, 'id_selecionado', id);
    const payload = { form: { [nomeFormCons]: structuredClone(getForm(nomeFormCons)) } };
    updateFormField(nomeFormCons, 'id_selecionado', null);
    const resultado = await fazerRequisicao(`${URL_BASE}cons`, payload);
    AppLoader.hide();
    if (!resultado.success) {
      if (resultado.data) updateState(resultado.data);
      else definirMensagem('erro', `Erro: ${resultado.error}`, false);
      return;
    }
    updateState(resultado.data);
    renderizarFiliais();
    renderizarExcecoes();
    hidratarFormulario(nomeForm);
    aplicarPermissoesNaInterface();
    alternarTelas();
  });

  renderizarFiliais();
  renderizarExcecoes();
  hidratarFormulario(nomeForm);
  aplicarPermissoesNaInterface();
  AppLoader.hide();
});
