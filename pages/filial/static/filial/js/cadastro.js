import {
  updateFormField, getForm, updateState,
  clearMessages, definirMensagem,
  hidratarFormulario, setFormState, confirmar, getScreenPermissions, getDataBackEnd, getDataset
} from '/static/js/sisVar.js';
import { fazerRequisicao } from '/static/js/base.js';
import { initSmartInputs } from '/static/js/input_rules.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { AppLoader } from '/static/js/loader.js';

const nomeForm = 'cadFilial';
const nomeFormCons = 'consFilial';
const form = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

getDataBackEnd();

function obterPermissoesFilial() {
  return getScreenPermissions('filial', {
    acessar: false,
    consultar: false,
    incluir: false,
    editar: false,
    excluir: false,
  });
}

function podeExecutarAcao(acao) {
  return Boolean(obterPermissoesFilial()?.[acao]);
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

const updater = criarAtualizadorForm({ formId: nomeForm, setter: updateFormField, form });
form.addEventListener('input', updater);
initSmartInputs((input, value) => { updateFormField(nomeForm, input.name, value); });

const updater2 = criarAtualizadorForm({ formId: nomeFormCons, setter: updateFormField, form: form2 });
form2.addEventListener('input', updater2);

function marcarCampoErro(formEl, nomeCampo, ativo) {
  const input = formEl.querySelector(`[name="${nomeCampo}"]`);
  if (!input) return;
  input.classList.toggle('is-invalid', Boolean(ativo));
  if (ativo) {
    input.addEventListener('input', () => input.classList.remove('is-invalid'), { once: true });
  }
}

function validarPermissaoPorEstado(estado) {
  if (estado === 'novo' && !podeExecutarAcao('incluir')) {
    definirMensagem('erro', 'Você não possui permissão para incluir matriz/filial.', false);
    return false;
  }

  if (estado === 'editar' && !podeExecutarAcao('editar')) {
    definirMensagem('erro', 'Você não possui permissão para editar matriz/filial.', false);
    return false;
  }

  return true;
}

function aplicarDefaultsNovo() {
  const defaults = getDataset('filialDefaults', { is_matriz: false, ativa: true }) || {};
  updateFormField(nomeForm, 'is_matriz', Boolean(defaults.is_matriz));
  updateFormField(nomeForm, 'ativa', defaults.ativa !== false);
  hidratarFormulario(nomeForm);
}

function renderizarPaises() {
  const paises = getDataset('paises_cadastrados', []);
  ['pais_endereco_id', 'pais_atuacao_id'].forEach((campo) => {
    const select = document.getElementById(campo);
    if (!select) return;

    const valorAtual = String(getForm(nomeForm)?.campos?.[campo] ?? '');
    select.innerHTML = '<option value="">Selecione</option>';

    paises.forEach((pais) => {
      const option = document.createElement('option');
      option.value = String(pais.id);
      option.textContent = `${pais.nome} (${pais.sigla})`;
      select.appendChild(option);
    });

    select.value = valorAtual;
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearMessages();
  marcarCampoErro(form, 'codigo', false);
  marcarCampoErro(form, 'nome', false);

  const formData = getForm(nomeForm);
  if (!validarPermissaoPorEstado(formData?.estado)) {
    return;
  }

  confirmar({
    titulo: 'Confirmar Salvamento',
    mensagem: 'Deseja salvar a matriz/filial?',
    onConfirmar: async () => {
      AppLoader.show();

      const resultado = await fazerRequisicao('/app/filial/cadastro/', {
        form: { [nomeForm]: formData },
      });

      AppLoader.hide();

      if (!resultado.success) {
        if (resultado.data) updateState(resultado.data);
        else definirMensagem('erro', `Erro: ${resultado.error}`, false);

        if (resultado.status === 422) {
          const mensagens = resultado.data?.mensagens?.erro?.conteudo || [];
          if (mensagens.some((msg) => msg.includes('Código'))) marcarCampoErro(form, 'codigo', true);
          if (mensagens.some((msg) => msg.includes('Nome'))) marcarCampoErro(form, 'nome', true);
        }
        return;
      }

      updateState(resultado.data);
      renderizarPaises();
      hidratarFormulario(nomeForm);
    }
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
  const tabelaCorpo = document.getElementById('tabela-corpo');

  function aplicarPermissoesNaInterface() {
    const permissoes = obterPermissoesFilial();
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
        <td>${registro.codigo}</td>
        <td>${registro.nome}</td>
        <td>${registro.pais_atuacao || ''}</td>
        <td>${registro.tipo}</td>
        <td>${registro.ativa ? 'Sim' : 'Não'}</td>
        <td class="text-center">
          <button type="button" class="btn btn-sm btn-primary btn-selecionar" data-id="${registro.id}">Selecionar</button>
        </td>
      </tr>
    `).join('');
  }

  btnAbrirPesquisa.addEventListener('click', alternarTelas);
  btnVoltar.addEventListener('click', alternarTelas);
  btnFechar.addEventListener('click', alternarTelas);

  btnEditar.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('editar')) {
      definirMensagem('erro', 'Você não possui permissão para editar matriz/filial.', false);
      return;
    }
    setFormState(nomeForm, 'editar');
    aplicarPermissoesNaInterface();
  });

  btnNovo.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('incluir')) {
      definirMensagem('erro', 'Você não possui permissão para incluir matriz/filial.', false);
      return;
    }
    setFormState(nomeForm, 'novo');
    aplicarDefaultsNovo();
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
        aplicarPermissoesNaInterface();
      },
    });
  });

  btnExcluir.addEventListener('click', () => {
    const formData = getForm(nomeForm);
    const nome = formData?.campos?.nome || '';

    confirmar({
      titulo: 'Confirmar Exclusão',
      mensagem: `Deseja excluir a matriz/filial "${nome}"? Esta ação não pode ser desfeita.`,
      onConfirmar: async () => {
        clearMessages();
        if (!podeExecutarAcao('excluir')) {
          definirMensagem('erro', 'Você não possui permissão para excluir matriz/filial.', false);
          return;
        }

        AppLoader.show();
        const resultado = await fazerRequisicao('/app/filial/cadastro/del', {
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
        aplicarPermissoesNaInterface();
      }
    });
  });

  form2.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearMessages();

    if (!podeExecutarAcao('consultar')) {
      definirMensagem('erro', 'Você não possui permissão para consultar matriz/filial.', false);
      return;
    }

    AppLoader.show();
    const resultado = await fazerRequisicao('/app/filial/cadastro/cons', {
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
      definirMensagem('info', 'Nenhuma matriz/filial encontrada.');
    }
  });

  tabelaCorpo.addEventListener('click', async (event) => {
    if (!event.target.classList.contains('btn-selecionar')) return;

    const id = event.target.dataset.id;
    clearMessages();
    AppLoader.show();

    updateFormField(nomeFormCons, 'id_selecionado', id);
    const payload = { form: { [nomeFormCons]: structuredClone(getForm(nomeFormCons)) } };
    updateFormField(nomeFormCons, 'id_selecionado', null);

    const resultado = await fazerRequisicao('/app/filial/cadastro/cons', payload);
    AppLoader.hide();

    if (!resultado.success) {
      if (resultado.data) updateState(resultado.data);
      else definirMensagem('erro', `Erro: ${resultado.error}`, false);
      return;
    }

    updateState(resultado.data);
    renderizarPaises();
    hidratarFormulario(nomeForm);
    aplicarPermissoesNaInterface();
    alternarTelas();
  });

  renderizarPaises();
  hidratarFormulario(nomeForm);
  aplicarPermissoesNaInterface();
  AppLoader.hide();
});