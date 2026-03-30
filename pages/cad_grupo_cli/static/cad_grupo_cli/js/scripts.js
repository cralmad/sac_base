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

// Utilitário: escapa strings para inserção segura no DOM (evita XSS)
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

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

// 5. SUBMIT DO FORMULÁRIO PRINCIPAL (Salvar)
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
        if (resultado.data) updateState(resultado.data);
        else definirMensagem('erro', `Erro: ${resultado.error}`, false);
        if (resultado.status === 422) marcarCampoErro(form, 'descricao', true);
        return;
      }

      updateState(resultado.data);
      hidratarFormulario(nomeForm);
    }
  });
});

// 6. LÓGICA DE UI — dentro do DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  AppLoader.show();

  const divPrincipal     = document.getElementById(nomeForm);
  const divPesquisa      = document.getElementById('div-pesquisa');
  const btnAbrirPesquisa = document.getElementById('btn-abrir-pesquisa');
  const btnVoltar        = document.getElementById('btn-voltar');
  const btnFechar        = document.getElementById('btn-fechar');
  const btnEditar        = document.getElementById('btn-editar');
  const btnNovo          = document.getElementById('btn-novo');
  const btnExcluir       = document.getElementById('btn-excluir');
  const btnCancelar      = document.getElementById('btn-cancelar');
  const tabelaCorpo      = document.getElementById('tabela-corpo');

  // Alternância cadastro ↔ pesquisa
  const alternarTelas = () => {
    divPrincipal.classList.toggle('d-none');
    divPesquisa.classList.toggle('d-none');
  };

  btnAbrirPesquisa.addEventListener('click', alternarTelas);
  btnVoltar.addEventListener('click', alternarTelas);
  btnFechar.addEventListener('click', alternarTelas);

  // Botões de estado
  btnEditar.addEventListener('click', () => setFormState(nomeForm, 'editar'));
  btnNovo.addEventListener('click',   () => setFormState(nomeForm, 'novo'));
  btnCancelar.addEventListener('click', () => {
    confirmar({
      titulo: 'Confirmar Cancelamento',
      mensagem: 'Deseja cancelar? Os dados não salvos serão perdidos.',
      onConfirmar: () => setFormState(nomeForm, 'novo')
    });
  });

  // Botão Excluir
  btnExcluir.addEventListener('click', () => {
    const formData = getForm(nomeForm);
    const descricao = formData?.campos?.descricao || '';

    confirmar({
      titulo: 'Confirmar Exclusão',
      mensagem: `Deseja excluir o grupo \