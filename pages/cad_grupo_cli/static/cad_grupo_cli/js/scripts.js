// 1. IMPORTS — caminhos absolutos /static/
import {
  updateFormField, getForm, updateState,
  clearMessages, definirMensagem,
  hidratarFormulario, setFormState, confirmar
} from '/static/js/sisVar.js';
import { fazerRequisicao }      from '/static/js/base.js';
import { initSmartInputs }      from '/static/js/input_rules.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { AppLoader }            from '/static/js/loader.js';

// 2. CONSTANTES
const nomeForm     = 'cadGrupoCli';
const nomeFormCons = 'consGrupoCli';
const form  = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

// 3. VÍNCULO sisVar ↔ inputs do formulário principal
const updater = criarAtualizadorForm({ formId: nomeForm, setter: updateFormField, form });
form.addEventListener('input', updater);
initSmartInputs((input, value) => { updateFormField(nomeForm, input.name, value); });

// 4. VÍNCULO sisVar ↔ inputs do formulário de consulta
const updater2 = criarAtualizadorForm({ formId: nomeFormCons, setter: updateFormField, form: form2 });
form2.addEventListener('input', updater2);

// Utilitário: marca/desmarca campo com erro visual Bootstrap
function marcarCampoErro(formEl, nomeCampo, ativo) {
  const input = formEl.querySelector(`[name="${nomeCampo}"]`);
  if (!input) return;
  if (ativo) {
    input.classList.add('is-invalid');
    input.addEventListener('input', () => input.classList.remove('is-invalid'), { once: true });
  } else {
    input.classList.remove('is-invalid');
  }
}

// 5. SUBMIT DO FORMULÁRIO PRINCIPAL
form.addEventListener('submit', async e => {
  e.preventDefault();
  clearMessages();
  marcarCampoErro(form, 'descricao', false);

  const formData = getForm(nomeForm);

  confirmar({
    titulo: 'Confirmar Salvamento',
    mensagem: 'Deseja salvar o grupo de cliente?',
    onConfirmar: async () => {
      AppLoader.show();

      const resultado = await fazerRequisicao('/app/cad/grupocli/', {
        form: { [nomeForm]: formData }
      });

      AppLoader.hide();

      if (!resultado.success) {
        // data contém as mensagens do servidor (400 e 422) — updateState exibe no #container-mensagens
        if (resultado.data) {
          updateState(resultado.data);
        } else {
          definirMensagem('erro', `Erro: ${resultado.error}`, false);
        }
        // Destaca o campo visualmente se for duplicidade (422)
        if (resultado.status === 422) {
          marcarCampoErro(form, 'descricao', true);
        }
        return;
      }

      updateState(resultado.data);
      hidratarFormulario(nomeForm);
    }
  });
});

// 6. LÓGICA DE UI — dentro do DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  const divPrincipal      = document.getElementById(nomeForm);
  const divPesquisa       = document.getElementById('div-pesquisa');
  const btnAbrirPesquisa  = document.getElementById('btn-abrir-pesquisa');
  const btnVoltar         = document.getElementById('btn-voltar');
  const btnFechar         = document.getElementById('btn-fechar');
  const btnEditar         = document.getElementById('btn-editar');
  const btnNovo           = document.getElementById('btn-novo');
  const btnCancelar       = document.getElementById('btn-cancelar');
  const tabelaCorpo       = document.getElementById('tabela-corpo');

  const alternarTelas = () => {
    divPrincipal.classList.toggle('d-none');
    divPesquisa.classList.toggle('d-none');
  };

  btnAbrirPesquisa.addEventListener('click', alternarTelas);
  btnVoltar.addEventListener('click', alternarTelas);
  btnFechar.addEventListener('click', alternarTelas);

  btnEditar.addEventListener('click', () => setFormState(nomeForm, 'editar'));
  btnNovo.addEventListener('click',   () => setFormState(nomeForm, 'novo'));
  btnCancelar.addEventListener('click', () => {
    confirmar({
      titulo: 'Confirmar Cancelamento',
      mensagem: 'Deseja cancelar? Os dados não salvos serão perdidos.',
      onConfirmar: () => setFormState(nomeForm, 'novo')
    });
  });

  // Submit da consulta (Filtrar)
  form2.addEventListener('submit', async e => {
    e.preventDefault();
    clearMessages();
    AppLoader.show();

    const resultado = await fazerRequisicao('/app/cad/grupocli/cons', {
      form: { [nomeFormCons]: getForm(nomeFormCons) }
    });

    AppLoader.hide();

    if (!resultado.success) {
      if (resultado.data) updateState(resultado.data);
      else definirMensagem('erro', `Erro: ${resultado.error}`, false);
      return;
    }

    updateState(resultado.data);

    if (resultado.data?.registros && resultado.data.registros.length > 0) {
      renderizarTabela(resultado.data.registros);
    } else {
      tabelaCorpo.innerHTML = '';
      definirMensagem('info', 'Nenhum grupo de cliente encontrado.');
    }
  });

  // Event delegation — selecionar da tabela
  tabelaCorpo.addEventListener('click', async e => {
    if (!e.target.classList.contains('btn-selecionar')) return;

    const id = e.target.dataset.id;
    if (!id) { definirMensagem('aviso', 'Erro ao selecionar o registro.', true); return; }

    clearMessages();
    AppLoader.show();

    updateFormField(nomeFormCons, 'id_selecionado', id);
    const payload = { form: { [nomeFormCons]: structuredClone(getForm(nomeFormCons)) } };
    updateFormField(nomeFormCons, 'id_selecionado', null);

    const resultado = await fazerRequisicao('/app/cad/grupocli/cons', payload);

    AppLoader.hide();

    if (!resultado.success) {
      if (resultado.data) updateState(resultado.data);
      else definirMensagem('erro', `Erro: ${resultado.error}`, false);
      return;
    }

    updateState(resultado.data);
    hidratarFormulario(nomeForm);
    setFormState(nomeForm, 'visualizar');
    alternarTelas();
  });

  // Renderização da tabela
  function renderizarTabela(registros) {
    tabelaCorpo.innerHTML = '';

    if (!Array.isArray(registros) || registros.length === 0) {
      tabelaCorpo.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Nenhum registro encontrado.</td></tr>';
      return;
    }

    registros.forEach(reg => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${reg.id}</td>
        <td>${reg.descricao}</td>
        <td class="text-center">
          <button type="button" class="btn btn-sm btn-primary btn-selecionar" data-id="${reg.id}">
            Selecionar
          </button>
        </td>
      `;
      tabelaCorpo.appendChild(tr);
    });
  }

});