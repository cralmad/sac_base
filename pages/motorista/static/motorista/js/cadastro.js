import {
  updateFormField, getForm, updateState,
  clearMessages, definirMensagem,
  hidratarFormulario, setFormState, confirmar, getScreenPermissions, getDataBackEnd, getDataset,
} from '/static/js/sisVar.js';
import { fazerRequisicao } from '/static/js/base.js';
import { initSmartInputs } from '/static/js/input_rules.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { AppLoader } from '/static/js/loader.js';

const nomeForm = 'cadMotorista';
const nomeFormCons = 'consMotorista';
const form = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

getDataBackEnd();

function obterPermissoes() {
  return getScreenPermissions('motorista', {
    acessar: false,
    consultar: false,
    incluir: false,
    editar: false,
    excluir: false,
  });
}

function podeExecutarAcao(acao) {
  return Boolean(obterPermissoes()?.[acao]);
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

function getFiliaisEscrita() {
  return getDataset('filiais_escrita', []);
}

function renderizarFiliais() {
  const selectPrincipal = document.getElementById('filial_id');
  const selectPesquisa = document.getElementById('filial_cons');
  const filiais = getFiliaisEscrita();
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
}

function aplicarDefaultsNovo() {
  updateFormField(nomeForm, 'ativa', true);
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

  const formData = getForm(nomeForm);
  confirmar({
    titulo: 'Confirmar Salvamento',
    mensagem: 'Deseja salvar o motorista?',
    onConfirmar: async () => {
      AppLoader.show();
      const resultado = await fazerRequisicao('/app/logistica/motorista/', {
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
  const tabelaCorpo = document.getElementById('tabela-motorista-corpo');

  function aplicarPermissoesNaInterface() {
    const permissoes = obterPermissoes();
    const estadoAtual = getForm(nomeForm)?.estado ?? 'visualizar';
    const botoesControlados = [btnSalvar, btnEditar, btnNovo, btnExcluir, btnCancelar];

    btnAbrirPesquisa.classList.toggle('d-none', !permissoes.consultar);

    botoesControlados.forEach((botao) => {
      const visivelNoEstado = botaoDeveFicarVisivel(botao, estadoAtual);
      const visivelNaPermissao = podeExibirBotaoPorPermissao(botao.id, estadoAtual);
      botao.classList.toggle('d-none', !(visivelNoEstado && visivelNaPermissao));
    });
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
        <td>${registro.codigo || ''}</td>
        <td>${registro.nome}</td>
        <td>${registro.telefone}</td>
        <td>${registro.ativa ? 'Sim' : 'Não'}</td>
        <td class="text-center"><button type="button" class="btn btn-sm btn-primary btn-selecionar" data-id="${registro.id}">Selecionar</button></td>
      </tr>
    `).join('');
  }

  btnAbrirPesquisa.addEventListener('click', alternarTelas);
  btnVoltar.addEventListener('click', alternarTelas);
  btnFechar.addEventListener('click', alternarTelas);

  btnEditar.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('editar')) {
      definirMensagem('erro', 'Você não possui permissão para editar motorista.', false);
      return;
    }
    setFormState(nomeForm, 'editar');
    aplicarPermissoesNaInterface();
  });

  btnNovo.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('incluir')) {
      definirMensagem('erro', 'Você não possui permissão para incluir motorista.', false);
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
      onConfirmar: () => {
        setFormState(nomeForm, podeExecutarAcao('incluir') ? 'novo' : 'visualizar');
        if (podeExecutarAcao('incluir')) {
          aplicarDefaultsNovo();
        }
        renderizarFiliais();
        aplicarPermissoesNaInterface();
      },
    });
  });

  btnExcluir.addEventListener('click', () => {
    const formData = getForm(nomeForm);
    confirmar({
      titulo: 'Confirmar Exclusão',
      mensagem: `Deseja excluir o motorista "${formData?.campos?.nome || ''}"?`,
      onConfirmar: async () => {
        clearMessages();
        if (!podeExecutarAcao('excluir')) {
          definirMensagem('erro', 'Você não possui permissão para excluir motorista.', false);
          return;
        }
        AppLoader.show();
        const resultado = await fazerRequisicao('/app/logistica/motorista/del', {
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
      definirMensagem('erro', 'Você não possui permissão para consultar motorista.', false);
      return;
    }
    AppLoader.show();
    const resultado = await fazerRequisicao('/app/logistica/motorista/cons', {
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
      definirMensagem('info', 'Nenhum motorista encontrado.');
    }
  });

  tabelaCorpo.addEventListener('click', async (event) => {
    if (!event.target.classList.contains('btn-selecionar')) return;
    const id = event.target.dataset.id;

    AppLoader.show();
    updateFormField(nomeFormCons, 'id_selecionado', id);
    const payload = { form: { [nomeFormCons]: structuredClone(getForm(nomeFormCons)) } };
    updateFormField(nomeFormCons, 'id_selecionado', null);

    const resultado = await fazerRequisicao('/app/logistica/motorista/cons', payload);
    AppLoader.hide();

    if (!resultado.success) {
      if (resultado.data) updateState(resultado.data);
      else definirMensagem('erro', `Erro: ${resultado.error}`, false);
      return;
    }

    updateState(resultado.data);
    renderizarFiliais();
    hidratarFormulario(nomeForm);
    aplicarPermissoesNaInterface();
    alternarTelas();
  });

  renderizarFiliais();
  hidratarFormulario(nomeForm);
  aplicarPermissoesNaInterface();
  AppLoader.hide();
});
