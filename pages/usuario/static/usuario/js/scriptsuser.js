import { 
  updateFormField, 
  getForm, 
  updateState,
  clearMessages,
  definirMensagem,
  hidratarFormulario
} from "/static/js/sisVar.js";
import { fazerRequisicao } from "/static/js/base.js";
import { initSmartInputs } from "/static/js/input_rules.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";
import { AppLoader } from "/static/js/loader.js";

const nomeForm = "cadUsuario";
const nomeFormCons = "consUsuario";
const form = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

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
 * Submissão do formulário de cadastro
 */
form.addEventListener("submit", async e => {
  e.preventDefault();

  // Limpa mensagens anteriores
  clearMessages();

  // Valida se o formulário tem dados
  const formData = getForm(nomeForm);
  if (!formData || !formData.campos || Object.keys(formData.campos).length === 0) {
    definirMensagem('aviso', 'Preencha o formulário antes de enviar');
    return;
  }

  const sisVarPayload = {
    form: {
      [nomeForm]: formData
    }
  };

  const resultado = await fazerRequisicao("/app/usuario/cadastro/", sisVarPayload);

  if (!resultado.success) {
    // Erro de rede ou servidor
    definirMensagem('erro', `Erro ao enviar dados: ${resultado.error}`, false);
    AppLoader.hide();
    return;
  }

  // Atualiza sisVar com resposta (inclui novo CSRF token e mensagens!)
  updateState(resultado.data);

  if (resultado.data?.success) {
    // Sucesso! Mensagem já foi renderizada via updateState
    AppLoader.hide();
  } else {
    // Erro de validação do servidor - mensagens já vêm na resposta
    AppLoader.hide();
  }
});

// Inicialização ao carregar o DOM
document.addEventListener('DOMContentLoaded', () => {
  // Seletores de Elementos
  const divPrincipal = document.getElementById(nomeForm);
  const divPesquisa = document.getElementById('div-pesquisa');
  const btnAbrirPesquisa = document.getElementById('btn-abrir-pesquisa');
  const btnVoltar = document.getElementById('btn-voltar');
  const btnFechar = document.getElementById('btn-fechar');
  const formFiltro = document.getElementById(nomeFormCons);
  const tabelaCorpo = document.getElementById('tabela-corpo');

  // Utilitário para alternar visualização usando classes do Bootstrap
  const alternarTelas = () => {
    divPrincipal.classList.toggle('d-none');
    divPesquisa.classList.toggle('d-none');
  };

  // Event Listeners para Navegação
  btnAbrirPesquisa.addEventListener('click', alternarTelas);
  btnVoltar.addEventListener('click', alternarTelas);
  btnFechar.addEventListener('click', alternarTelas);

  /**
   * Lógica de Busca - Listagem de Usuários
   */
  formFiltro.addEventListener('submit', async (e) => {
    e.preventDefault();

    clearMessages();

    const sisVarPayload = {
      form: {
        [nomeFormCons]: getForm(nomeFormCons)
      }
    };

    const resultado = await fazerRequisicao("/app/usuario/cadastro/cons", sisVarPayload);

    if (!resultado.success) {
      definirMensagem('erro', `Erro ao buscar usuários: ${resultado.error}`, false);
      AppLoader.hide();
      return;
    }

    // Atualiza sisVar
    updateState(resultado.data);

    if (resultado.data?.registros && resultado.data.registros.length > 0) {
      renderizarTabela(resultado.data.registros);
    } else {
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

    await carregarRegistro(id);
  });

  /**
   * Carrega dados do usuário selecionado
   */
  async function carregarRegistro(id) {
    clearMessages();

    // Atualiza o campo de ID no formulário
    updateFormField(nomeFormCons, 'id_selecionado', id);

    const sisVarPayload = {
      form: {
        [nomeFormCons]: getForm(nomeFormCons)
      }
    };

    const resultado = await fazerRequisicao("/app/usuario/cadastro/cons", sisVarPayload);

    if (!resultado.success) {
      definirMensagem('erro', `Erro ao carregar registro: ${resultado.error}`, false);
      AppLoader.hide();
      return;
    }

    // Atualiza sisVar com os dados do usuário
    updateState(resultado.data);

    // Hidrata o formulário principal com os dados carregados
    hidratarFormulario(nomeForm);

    // Alterna para a tela principal (com dados carregados)
    alternarTelas();
    AppLoader.hide();
  }
});