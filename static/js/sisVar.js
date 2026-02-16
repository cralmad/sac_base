// 1.
// Definição do Estado com Proxy Reativo

let _rawState = {
  form: {},
  schema: {},
  mensagens: {},
  usuario: {},
  // Local centralizado para metadados e tokens de segurança
  others: {
    csrf_token_value: ""
  }
};

const _state = new Proxy(_rawState, {
  set(target, property, value, receiver) {

    const result = Reflect.set(target, property, value, receiver);

    // Gatilho: Se a chave "form" ou qualquer parte dela mudar
    if (property === 'form') {
      Object.keys(value).forEach(formId => {
        const estado = value[formId]?.estado;
        if (estado) {
          applyFormState(formId, estado);
        }
      });
    }

    // Gatilho automático para mensagens
    if (property === 'mensagens') {
      renderMensagens();
    }

    return result;
  }
});

const _dadosBE = 'sisDados';

// 2.
// Controlador de Interface (DOM)

function applyFormState(formId, estado) {

  const form = document.querySelector(`[data-form-lock="${formId}"]`);
  if (!form) return;

  const isDisabled = (estado === 'visualizar');

  if (estado === 'visualizar') {
    clearFormFields(form);
  }

  const elements = form.querySelectorAll('input, select, textarea, button[type="submit"]');
  elements.forEach(el => {
    el.disabled = isDisabled;
  });
}

function clearFormFields(form) {
  const inputs = form.querySelectorAll('input:not([type="hidden"]), select, textarea');
  inputs.forEach(input => {
    if (input.type === 'checkbox' || input.type === 'radio') {
      input.checked = false;
    } else {
      input.value = '';
    }
  });
}

// --- Funções Exportadas ---

export function getForm(formId = null) {
  if (formId) return _state.form[formId] || null;
  return _state.form;
}

export function getSchema(schemaId = null) {
  if (schemaId) return _state.schema[schemaId] || null;
  return _state.schema;
}

export function getUsuario() {
  return _state.usuario;
}

/**
 * Recupera o token CSRF atual guardado no estado
 */
export function getCsrfToken() {
  return _state.others?.csrf_token_value || "";
}

export function renderMensagens() {
  const container = document.getElementById('alert-container');
  if (!container) return;

  container.innerHTML = '';

  const mensagens = _state.mensagens;

  const config = {
    sucesso: { classe: 'success' },
    erro: { classe: 'danger' },
    aviso: { classe: 'warning' },
    info: { classe: 'info' }
  };

  const renderizar = (tipo, dados) => {
    if (dados.conteudo && dados.conteudo.length > 0) {
      const podeIgnorar = dados.ignorar !== false;

      dados.conteudo.forEach(msg => {
        const alerta = document.createElement('div');
        alerta.className = `alert alert-${config[tipo]?.classe || 'secondary'} alert-dismissible fade show`;
        alerta.innerHTML = `${msg}${podeIgnorar ? '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>' : ''}`;
        container.appendChild(alerta);
      });
    }
  };

  Object.entries(mensagens).forEach(([tipo, dados]) => renderizar(tipo, dados));
}

export function updateFormField(formId, name, value) {
  if (!_state.form[formId]) {
    console.error(`Formulário ${formId} não encontrado.`);
    return;
  }
  _state.form[formId]["campos"][name] = value;
}

export function getDataBackEnd() {
  const elemento = document.getElementById(_dadosBE);

  if (elemento) {
    try {
      const dataBack = JSON.parse(elemento.textContent);
      updateState(dataBack);
      elemento.remove();
    } catch (e) {
      console.error("Erro ao processar dados do Back-End.", e);
    }
  }
}

/**
 * Atualiza o estado global.
 * Se encontrar 'csrfToken' na raiz de newData, move-o para 'others.csrf_token_value'.
 */
export function updateState(newData) {
  if (!newData || typeof newData !== 'object') return;

  // Intercepta o token vindo do Middleware antes de processar o loop
  if (newData.csrfToken) {
    _state.others.csrf_token_value = newData.csrfToken;
    // Opcional: deletar de newData para não duplicar no estado se houver chave idêntica
    // delete newData.csrfToken; 
  }

  Object.entries(newData).forEach(([key, value]) => {
    // Merge para formulários
    if (key === 'form' && _state.form) {
      _state.form = { ..._state.form, ...value };
    } 
    // Merge para a estrutura 'others'
    else if (key === 'others' && _state.others) {
      _state.others = { ..._state.others, ...value };
    } 
    // Impede que o csrfToken solto na raiz do JSON entre no estado global fora de 'others'
    else if (key !== 'csrfToken') {
      _state[key] = value;
    }
  });
}

export function __debugState() {
  return structuredClone(_rawState);
}