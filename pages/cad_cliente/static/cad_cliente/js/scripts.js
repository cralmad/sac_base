import { initSmartInputs } from '/static/js/input_rules.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { initHierarchicalSelects } from '/static/js/conditional_select.js';
import {
  updateFormField, getForm, updateState,
  clearMessages, definirMensagem,
  hidratarFormulario, setFormState, confirmar
} from '/static/js/sisVar.js';
import { fazerRequisicao } from '/static/js/base.js';
import { AppLoader } from '/static/js/loader.js';

const nomeForm     = 'cadCliente';
const nomeFormCons = 'consCliente';
const form = document.getElementById(nomeForm);

const atualizarSisVarForm = criarAtualizadorForm({
  formId: nomeForm,
  setter: updateFormField,
  form
});

form.addEventListener('input', atualizarSisVarForm);
form.addEventListener('change', atualizarSisVarForm);

initSmartInputs((input, value) => { updateFormField(nomeForm, input.name, value); });

// Dados para o select condicional (País => UF => Cidade)
export const HIERARCHY_DATA = {
  Paises: {
    Brasil: {
      label: 'Brasil',
      children: {
        ce: {
          label: 'Ceará',
          children: {
            for: { label: 'Fortaleza' }
          }
        }
      }
    },
    Portugal: {
      label: 'Portugal',
      children: {
        lis: {
          label: 'Lisboa',
          children: {
            ama: { label: 'Amadora' }
          }
        }
      }
    },
  }
};

initHierarchicalSelects(form, HIERARCHY_DATA);

form.addEventListener('submit', async e => {
  e.preventDefault();
  clearMessages();

  const formData = getForm(nomeForm);

  confirmar({
    titulo: 'Confirmar Salvamento',
    mensagem: 'Deseja salvar o registro?',
    onConfirmar: async () => {
      AppLoader.show();

      const resultado = await fazerRequisicao('/app/cad/cliente/', {
        form: { [nomeForm]: formData }
      });

      if (!resultado.success) {
        definirMensagem('erro', `Erro: ${resultado.error}`, false);
        AppLoader.hide();
        return;
      }

      updateState(resultado.data);
      AppLoader.hide();
    }
  });
});

document.addEventListener('DOMContentLoaded', () => {
  const btnEditar   = document.getElementById('btn-editar');
  const btnNovo     = document.getElementById('btn-novo');
  const btnCancelar = document.getElementById('btn-cancelar');

  if (btnEditar)   btnEditar.addEventListener('click',   () => setFormState(nomeForm, 'editar'));
  if (btnNovo)     btnNovo.addEventListener('click',     () => setFormState(nomeForm, 'novo'));
  if (btnCancelar) btnCancelar.addEventListener('click', () => {
    confirmar({
      titulo: 'Cancelar',
      mensagem: 'Dados não salvos serão perdidos.',
      onConfirmar: () => setFormState(nomeForm, 'novo')
    });
  });
});
