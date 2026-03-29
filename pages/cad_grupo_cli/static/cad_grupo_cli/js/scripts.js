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

// 3. VÍNCULO sisVar ↔ inputs
const updater = criarAtualizadorForm({ formId: nomeForm, setter: updateFormField, form });
form.addEventListener('input', updater);
initSmartInputs((input, value) => { updateFormField(nomeForm, input.name, value); });

// 4. SUBMIT DO FORMULÁRIO PRINCIPAL
form.addEventListener('submit', async e => {
  e.preventDefault();
  clearMessages();

  const formData = getForm(nomeForm);

  confirmar({
    titulo: 'Confirmar Salvamento',
    mensagem: 'Deseja salvar o grupo de cliente?',
    onConfirmar: async () => {
      AppLoader.show();

      const resultado = await fazerRequisicao('/app/cad/grupo/grupocli/', {
        form: { [nomeForm]: formData }
      });

      AppLoader.hide();

      if (!resultado.success) {
        definirMensagem('erro', resultado.error, false);
        return;
      }

      updateState(resultado.data);
      hidratarFormulario(nomeForm);
    }
  });
});

// 5. LÓGICA DE UI
document.addEventListener('DOMContentLoaded', () => {

  // Botões de estado
  document.getElementById('btn-editar').addEventListener('click', () => setFormState(nomeForm, 'editar'));
  document.getElementById('btn-novo').addEventListener('click',   () => setFormState(nomeForm, 'novo'));
  document.getElementById('btn-cancelar').addEventListener('click', () => {
    confirmar({
      titulo: 'Cancelar',
      mensagem: 'Dados não salvos serão perdidos. Deseja continuar?',
      onConfirmar: () => setFormState(nomeForm, 'novo')
    });
  });

  // Alternância cadastro ↔ pesquisa
  const alternarTelas = () => {
    form.classList.toggle('d-none');
    document.getElementById('div-pesquisa').classList.toggle('d-none');
  };
  document.getElementById('btn-abrir-pesquisa').addEventListener('click', alternarTelas);
  document.getElementById('btn-fechar').addEventListener('click', alternarTelas);

  // Submit da consulta
  form2.addEventListener('submit', async e => {
    e.preventDefault();
    clearMessages();
    AppLoader.show();

    const resultado = await fazerRequisicao('/app/cad/grupo/grupocli/cons', {
      form: { [nomeFormCons]: getForm(nomeFormCons) }
    });

    AppLoader.hide();

    if (!resultado.success) {
      definirMensagem('erro', resultado.error, false);
      return;
    }

    updateState(resultado.data);
    renderizarTabela(resultado.data.registros);
  });

  // Event delegation — selecionar da tabela
  document.getElementById('tabela-corpo').addEventListener('click', async e => {
    if (!e.target.classList.contains('btn-selecionar')) return;

    const id = e.target.dataset.id;
    if (!id) { definirMensagem('aviso', 'Erro ao selecionar o registro.', true); return; }

    clearMessages();
    AppLoader.show();

    updateFormField(nomeFormCons, 'id_selecionado', id);
    const payload = { form: { [nomeFormCons]: structuredClone(getForm(nomeFormCons)) } };
    updateFormField(nomeFormCons, 'id_selecionado', null);

    const resultado = await fazerRequisicao('/app/cad/grupo/grupocli/cons', payload);

    AppLoader.hide();

    if (!resultado.success) {
      definirMensagem('erro', resultado.error, false);
      return;
    }

    updateState(resultado.data);
    hidratarFormulario(nomeForm);
    setFormState(nomeForm, 'visualizar');
    alternarTelas();
  });

});

// 6. RENDERIZAÇÃO DA TABELA DE PESQUISA
function renderizarTabela(registros) {
  const tbody = document.getElementById('tabela-corpo');
  tbody.innerHTML = '';

  if (!registros || registros.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Nenhum registro encontrado.</td></tr>';
    return;
  }

  for (const reg of registros) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${reg.id}</td>
      <td>${reg.descricao}</td>
      <td>
        <button type="button" class="btn btn-sm btn-outline-primary btn-selecionar" data-id="${reg.id}">
          Selecionar
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  }
}