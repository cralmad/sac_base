const _state = {
  usuario: {},
  form: {},
  schema: {},
  others: {}
};

const _dadosBE = 'sisDados';// ID do elemento HTML que contem os dados do back-end

export function getSchema(formId) {
  return _state.schema[formId];
}

export function updateFormField(formId, name, value) {
  if (!_state.form[formId]) {
    _state.form[formId] = {};
  }

  _state.form[formId][name] = value;
}

export function getForm(formId) {
  return _state.form[formId] ?? {};
}

export function getDataBackEnd() {// Dados enviados pelo back-end
  if(document.getElementById(_dadosBE)){
    const dadosSis = JSON.parse(document.getElementById(_dadosBE).textContent)
    _state.others = dadosSis.others || {}
    _state.schema = dadosSis.schema || {}
    _state.form = dadosSis.form || {}
    _state.usuario = dadosSis.usuario || {}
  }
}

// !!!!!!!!!!!!!!!!!!!!!!! Apenas para debug !!!!!!!!!!!!!!!!!!!!!!!
export function __debugState() {
  return structuredClone(_state);
}
