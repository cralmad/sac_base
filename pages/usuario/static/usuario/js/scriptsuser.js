import { 
  updateFormField, 
  getForm, 
  updateState,
  clearMessages,
  definirMensagem,
  hidratarFormulario,
  setFormState
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

  clearMessages();

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
    definirMensagem('erro', `Erro ao enviar dados: ${resultado.error}`, false);
    AppLoader.hide();
    return;
  }

  updateState(resultado.data);

  AppLoader.hide();
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
  const formFiltro = document.getElementById(nomeFormCons);
  const tabelaCorpo = document.getElementById('tabela-corpo');

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
    setFormState(nomeForm, 'editar');
  });

  /**
   * Botão Novo: muda estado para 'novo'
   * applyFormState cuida de tudo: inputs, botões e sufixo do título
   */
  btnNovo.addEventListener('click', () => {
    setFormState(nomeForm, 'novo');
  });

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
   * Carrega dados do usuário selecionado e altera o estado para 'visualizar'
   */
  async function carregarRegistro(id) {
    clearMessages();

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

    updateState(resultado.data);
    hidratarFormulario(nomeForm);

    // applyFormState cuida de tudo automaticamente — incluindo o sufixo do título
    setFormState(nomeForm, 'visualizar');

    alternarTelas();
    AppLoader.hide();
  }
});