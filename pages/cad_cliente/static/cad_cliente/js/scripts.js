import { initSmartInputs } from '/static/js/input_rules.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { initHierarchicalSelects } from '/static/js/conditional_select.js';
import { setSchema, updateFormField, getForm, getSchema } from '/static/js/sisVar.js';

initSmartInputs()

const form = document.getElementById('cadForm');

// Definição do schema de validação do formulário
setSchema('cadForm', {
  grupo: {
    required: true,
    maxLength: 30,
    tipo: 'string',
  },
  pessoa: {
    required: true,
    minLength: 3,
    maxLength: 100,
    tipo: 'string',
  },
  nome: {
    required: true,
    minLength: 3,
    maxLength: 100,
    tipo: 'string',
  },
  logradouro:{
    maxLength: 20,
    tipo: 'string',
  },
  endereco:{
    maxLength: 150,
    tipo: 'string',
  },
  numero:{
    maxLength: 10,
    tipo: 'string',
  },
  complemento:{
    maxLength: 50,
    tipo: 'string',
  },
  localidade:{
    maxLength: 60,
    tipo: 'string',
  },
  freguesia:{
    maxLength: 60,
    tipo: 'string',
  },
  distrito:{
    required: true,
    maxLength: 10,
    tipo: 'string',
  },
  conselho:{
    required: true,
    maxLength: 20,
    tipo: 'string',
  },
  pais:{
    required: true,
    maxLength: 20,
    tipo: 'string',
  },
  codpostal:{
    maxLength: 15,
    tipo: 'string',
  },
  fone:{
    maxLength: 15,
    tipo: 'string',
  },
  email:{
    maxLength: 15,
    tipo: 'string',
  },
  obs:{
    maxLength: 15,
    tipo: 'string',
  },
  nif:{
    maxLength: 15,
    tipo: 'string',
  },
  cartcidadao:{
    maxLength: 15,
    tipo: 'string',
  },
  passaporte:{
    maxLength: 15,
    tipo: 'string',
  },
  cartresidencia:{
    maxLength: 15,
    tipo: 'string',
  },
  fatura:{
    maxLength: 15,
    tipo: 'string',
  },
  dadosfat:{
    maxLength: 15,
    tipo: 'string',
  },
  codfat:{
    maxLength: 15,
    tipo: 'string',
  },
});

const atualizarSisVarForm = criarAtualizadorForm({
  formId: 'cadForm',
  setter: updateFormField,
  form
});

form.addEventListener('input', atualizarSisVarForm);
form.addEventListener('change', atualizarSisVarForm);

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
