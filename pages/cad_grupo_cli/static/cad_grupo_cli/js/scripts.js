import { initSmartInputs } from '/static/js/input_rules.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { setSchema, updateFormField, getForm, getSchema } from '/static/js/sisVar.js';

initSmartInputs()

const form = document.getElementById('cadForm');

// Definição do schema de validação do formulário
setSchema('cadForm', {
  descricao: {
    required: true,
    maxLength: 30,
    minLength: 3,
    tipo: 'string',
  }
});

const atualizarSisVarForm = criarAtualizadorForm({
  formId: 'cadForm',
  setter: updateFormField,
  form
});

form.addEventListener('input', atualizarSisVarForm);
form.addEventListener('change', atualizarSisVarForm);

//Função de validação dos campos do formulário (lançados no sisVar.form)
export function validateForm(formData, schema) {
  const errors = {};

  for (const field in schema) {
    const rules = schema[field];
    const value = formData[field];

    // Obrigatório
    if (rules.required && (value === null || value === undefined || value === '')) {
      errors[field] = 'Campo obrigatório';
      continue;
    }

    // Ignora se vazio e não obrigatório
    if (value === null || value === undefined || value === '') continue;

    // Tipo
    if (rules.tipo === 'boolean' && typeof value !== 'boolean') {
      errors[field] = 'Valor inválido';
      continue;
    }

    // Tamanho mínimo
    if (rules.minLength && value.length < rules.minLength) {
      errors[field] = `Mínimo de ${rules.minLength} caracteres`;
      continue;
    }

    // Tamanho máximo
    if (rules.maxLength && value.length > rules.maxLength) {
      errors[field] = `Máximo de ${rules.maxLength} caracteres`;
      continue;
    }

    // Regex
    if (rules.pattern && !rules.pattern.test(value)) {
      errors[field] = 'Formato inválido';
      continue;
    }

    // Validação customizada
    if (rules.validate && !rules.validate(value, formData)) {
      errors[field] = 'Valor inválido';
    }
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors
  };
}

function submitForm(event) {
  event.preventDefault();

  const formData = getForm('cadForm');
  const schema = getSchema('cadForm');

  const result = validateForm(formData, schema);

  if (!result.valid) {
    console.log('Erros de validação:', result.errors);
    // aqui você pode renderizar os erros no DOM
    return;
  }

  alert('Formulário válido! Enviando dados...');
}

form.addEventListener('submit', submitForm)


/*****************DEBUG**********************/
import { __debugState } from '../../js/sisVar.js';

window.__DEBUG__ = {
  get state() {
    return __debugState();
  }
};

function exibir() {
  console.log(window.__DEBUG__.state);
}

document.getElementById('teste').addEventListener('click', exibir);
