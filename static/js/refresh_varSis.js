export function criarAtualizadorForm({//Função que cria a função de atualização do form
  formId,
  setter,
  form
}) {
  return function atualizarSisVarForm(event) {//Função que atualiza o valor do form após o evento
    const el = event.target;
    if (!el.name) return;

    queueMicrotask(() => {
      const value = getDataForm(el, form);
      setter(formId, el.name, value);
    });
  };
}

//Captura os valores do form de acordo com o tipo do input
export function getDataForm(el, form) {
  switch (el.type) {

    case 'checkbox':
      return el.checked;

    case 'radio': {
      const checked = form.querySelector(
        `input[type="radio"][name="${el.name}"]:checked`
      );
      return checked ? checked.value : null;
    }

    case 'select-multiple':
      return Array.from(el.selectedOptions).map(opt => opt.value);

    case 'number':
      return el.value === '' ? null : Number(el.value);

    default:
      return el.value;
  }
}
