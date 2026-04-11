import { 
  updateFormField, 
  getForm, 
  updateState,
  clearMessages,
  definirMensagem,
  hidratarFormulario,
  setFormState,
  confirmar,
  getScreenPermissions,
  getDataBackEnd
} from "/static/js/sisVar.js";
import { fazerRequisicao } from "/static/js/base.js";
import { initSmartInputs } from "/static/js/input_rules.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";
import { AppLoader } from "/static/js/loader.js";

const nomeForm = "cadUsuario";
const nomeFormCons = "consUsuario";
const form = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

getDataBackEnd();

function obterPermissoesUsuario() {
  return getScreenPermissions('usuario', {
    acessar: false,
    consultar: false,
    incluir: false,
    editar: false,
    excluir: false,
  });
}

function podeExecutarAcao(acao) {
  return Boolean(obterPermissoesUsuario()?.[acao]);
}

function botaoDeveFicarVisivel(botao, estado) {
  const estadosPermitidos = (botao.dataset.showOn || '')
    .split(',')
    .map(item => item.trim())
    .filter(Boolean);

  return estadosPermitidos.includes(estado);
}

function podeExibirBotaoPorPermissao(botaoId, estado) {
  if (botaoId === 'btn-novo') {
    return podeExecutarAcao('incluir');
  }

  if (botaoId === 'btn-editar') {
    return podeExecutarAcao('editar');
  }

  if (botaoId === 'btn-salvar' || botaoId === 'btn-cancelar') {
    if (estado === 'novo') {
      return podeExecutarAcao('incluir');
    }

    if (estado === 'editar') {
      return podeExecutarAcao('editar');
    }
  }

  return true;
}

function validarPermissaoPorEstado(estado) {
  if (estado === 'novo' && !podeExecutarAcao('incluir')) {
    definirMensagem('erro', 'Você não possui permissão para incluir usuários.', false);
    return false;
  }

  if (estado === 'editar' && !podeExecutarAcao('editar')) {
    definirMensagem('erro', 'Você não possui permissão para editar usuários.', false);
    return false;
  }

  return true;
}

// Configuração dos atualizadores de formulário
const updater = criarAtualizadorForm({
  formId: nomeForm,
  setter: updateFormField,
  form
});

form.addEventListener("input", updater);

initSmartInputs((input, value) => {
  updateFormField(nomeForm, input.name, value);
});

const updater2 = criarAtualizadorForm({
  formId: nomeFormCons,
  setter: updateFormField,
  form: form2
});

form2.addEventListener("input", updater2);

initSmartInputs((input, value) => {
  updateFormField(nomeFormCons, input.name, value);
});

/**
 * Submissão do formulário de cadastro.
 * Interceptada para exibir confirmação antes de enviar.
 */
form.addEventListener("submit", async e => {
  e.preventDefault();

  clearMessages();

  const formData = getForm(nomeForm);
  if (!validarPermissaoPorEstado(formData?.estado)) {
    return;
  }

  if (!formData || !formData.campos || Object.keys(formData.campos).length === 0) {
    definirMensagem('aviso', 'Preencha o formulário antes de enviar');
    return;
  }

  confirmar({
    titulo: 'Confirmar Salvamento',
    mensagem: 'Deseja salvar o registro?',
    onConfirmar: async () => {

      // Loader ativado APÓS a confirmação — não bloqueia o modal
      AppLoader.show();

      const sisVarPayload = {
        form: {
          [nomeForm]: formData
        }
      };

      const resultado = await fazerRequisicao("/app/usuario/cadastro/", sisVarPayload);

      if (!resultado.success) {
        if (resultado.data) {
          updateState(resultado.data);
        } else {
          definirMensagem('erro', `Erro ao enviar dados: ${resultado.error}`, false);
        }
        AppLoader.hide();
        return;
      }

      updateState(resultado.data);
      AppLoader.hide();
    }
  });
});

// Inicialização ao carregar o DOM
document.addEventListener('DOMContentLoaded', () => {
  const divPrincipal = document.getElementById(nomeForm);
  const divPesquisa = document.getElementById('div-pesquisa');
  const btnAbrirPesquisa = document.getElementById('btn-abrir-pesquisa');
  const btnVoltar = document.getElementById('btn-voltar');
  const btnFechar = document.getElementById('btn-fechar');
  const btnEditar = document.getElementById('btn-editar');
  const btnNovo = document.getElementById('btn-novo');
  const btnCancelar = document.getElementById('btn-cancelar');
  const btnSalvar = document.getElementById('btn-salvar');
  const formFiltro = document.getElementById(nomeFormCons);
  const tabelaCorpo = document.getElementById('tabela-corpo');

  function aplicarPermissoesNaInterface() {
    const permissoes = obterPermissoesUsuario();
    const estadoAtual = getForm(nomeForm)?.estado ?? 'visualizar';
    const botoesControlados = [btnSalvar, btnEditar, btnNovo, btnCancelar];

    btnAbrirPesquisa.classList.toggle('d-none', !permissoes.consultar);

    botoesControlados.forEach(botao => {
      const visivelNoEstado = botaoDeveFicarVisivel(botao, estadoAtual);
      const visivelNaPermissao = podeExibirBotaoPorPermissao(botao.id, estadoAtual);
      botao.classList.toggle('d-none', !(visivelNoEstado && visivelNaPermissao));
    });

    if (!permissoes.consultar && !divPesquisa.classList.contains('d-none')) {
      alternarTelas();
    }
  }

  const alternarTelas = () => {
    divPrincipal.classList.toggle('d-none');
    divPesquisa.classList.toggle('d-none');
  };

  btnAbrirPesquisa.addEventListener('click', alternarTelas);
  btnVoltar.addEventListener('click', alternarTelas);
  btnFechar.addEventListener('click', alternarTelas);

  /**
   * Botão Editar: muda estado para 'editar'
   * applyFormState cuida de tudo: inputs, botões e sufixo do título
   */
  btnEditar.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('editar')) {
      definirMensagem('erro', 'Você não possui permissão para editar usuários.', false);
      return;
    }

    setFormState(nomeForm, 'editar');
    aplicarPermissoesNaInterface();
  });

  /**
   * Botão Novo: muda estado para 'novo'
   * applyFormState cuida de tudo: inputs, botões e sufixo do título
   */
  btnNovo.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('incluir')) {
      definirMensagem('erro', 'Você não possui permissão para incluir usuários.', false);
      return;
    }

    setFormState(nomeForm, 'novo');
    aplicarPermissoesNaInterface();
  });

  /**
   * Botão Cancelar: pede confirmação e, se confirmado, reinicia para o estado 'novo'
   */
  btnCancelar.addEventListener('click', () => {
    confirmar({
      titulo: 'Confirmar Cancelamento',
      mensagem: 'Deseja cancelar? Os dados não salvos serão perdidos.',
      onConfirmar: () => {
        setFormState(nomeForm, podeExecutarAcao('incluir') ? 'novo' : 'visualizar');
        aplicarPermissoesNaInterface();
      }
    });
  });

  /**
   * Lógica de Busca - Listagem de Usuários
   */
  formFiltro.addEventListener('submit', async (e) => {
    e.preventDefault();

    clearMessages();

    if (!podeExecutarAcao('consultar')) {
      definirMensagem('erro', 'Você não possui permissão para consultar usuários.', false);
      return;
    }

    AppLoader.show();

    const sisVarPayload = {
      form: {
        [nomeFormCons]: getForm(nomeFormCons)
      }
    };

    const resultado = await fazerRequisicao("/app/usuario/cadastro/cons", sisVarPayload);

    if (!resultado.success) {
      if (resultado.data) {
        updateState(resultado.data);
      } else {
        definirMensagem('erro', `Erro ao buscar usuários: ${resultado.error}`, false);
      }
      AppLoader.hide();
      return;
    }

    updateState(resultado.data);
    aplicarPermissoesNaInterface();

    if (resultado.data?.registros && resultado.data.registros.length > 0) {
      renderizarTabela(resultado.data.registros);
    } else {
      // Limpa a tabela e exibe mensagem quando não há resultados
      tabelaCorpo.innerHTML = '';
      definirMensagem('info', 'Nenhum usuário encontrado');
    }

    AppLoader.hide();
  });

  /**
   * Renderização da Tabela de Usuários
   */
  function renderizarTabela(registros) {
    tabelaCorpo.innerHTML = '';

    if (!Array.isArray(registros) || registros.length === 0) {
      tabelaCorpo.innerHTML = '<tr><td colspan="6" class="text-center">Nenhum registro encontrado</td></tr>';
      return;
    }

    registros.forEach(registro => {
      const linha = document.createElement('tr');
      const ativoStatus = registro.is_active ? '✓' : '✗';
      const alivoBadge = registro.is_active ? 'bg-success' : 'bg-danger';
      
      linha.innerHTML = `
        <td>${registro.id || ''}</td>
        <td>${registro.first_name || ''}</td>
        <td>${registro.username || ''}</td>
        <td>${registro.email || ''}</td>
        <td>
          <span class="badge ${alivoBadge}">${ativoStatus}</span>
        </td>
        <td class="text-center">
          <button class="btn btn-sm btn-primary btn-selecionar" data-id="${registro.id}">
            Selecionar
          </button>
        </td>
      `;
      tabelaCorpo.appendChild(linha);
    });
  }

  /**
   * Event Delegation - Captura clique no botão "Selecionar"
   */
  tabelaCorpo.addEventListener('click', async (e) => {
    if (!e.target.classList.contains('btn-selecionar')) return;

    const id = e.target.dataset.id;
    if (!id) {
      definirMensagem('aviso', 'Erro ao selecionar o registro');
      return;
    }

    if (!podeExecutarAcao('consultar')) {
      definirMensagem('erro', 'Você não possui permissão para consultar usuários.', false);
      return;
    }

    await carregarRegistro(id);
  });

  /**
   * Carrega dados do usuário selecionado e altera o estado para 'visualizar'
   */
  async function carregarRegistro(id) {
    clearMessages();

    if (!podeExecutarAcao('consultar')) {
      definirMensagem('erro', 'Você não possui permissão para consultar usuários.', false);
      return;
    }

    AppLoader.show();

    // Grava o ID, captura o payload como cópia profunda e zera imediatamente
    updateFormField(nomeFormCons, 'id_selecionado', id);

    // structuredClone garante uma cópia independente do estado atual —
    // zerar o sisVar depois não afeta o payload já enviado
    const sisVarPayload = {
      form: {
        [nomeFormCons]: structuredClone(getForm(nomeFormCons))
      }
    };

    // Zera antes da requisição: qualquer filtro posterior já encontra o campo limpo
    updateFormField(nomeFormCons, 'id_selecionado', null);

    const resultado = await fazerRequisicao("/app/usuario/cadastro/cons", sisVarPayload);

    if (!resultado.success) {
      if (resultado.data) {
        updateState(resultado.data);
      } else {
        definirMensagem('erro', `Erro ao carregar registro: ${resultado.error}`, false);
      }
      AppLoader.hide();
      return;
    }

    updateState(resultado.data);
    hidratarFormulario(nomeForm);
    setFormState(nomeForm, 'visualizar');
    aplicarPermissoesNaInterface();
    alternarTelas();
    AppLoader.hide();
  }

  aplicarPermissoesNaInterface();
});