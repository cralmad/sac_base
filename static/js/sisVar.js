const _state = {
  form: {},
  schema: {}
};

export function setSchema(formId, schema) {
  _state.schema[formId] = schema;
}

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

// !!!!!!!!!!!!!!!!!!!!!!! Apenas para debug !!!!!!!!!!!!!!!!!!!!!!!
export function __debugState() {
  return structuredClone(_state);
}
