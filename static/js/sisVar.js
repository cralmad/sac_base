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

  // Limpa campos apenas ao entrar em 'visualizar'
  if (estado === 'visualizar') {
    clearFormFields(form);
  }

  // Habilita/desabilita inputs conforme o estado
  const isDisabled = (estado === 'visualizar');
  const inputs = form.querySelectorAll('input, select, textarea');
  inputs.forEach(el => {
    el.disabled = isDisabled;
  });

  // Controla visibilidade dos botões via data-show-on
  const botoes = form.querySelectorAll('button[data-show-on]');
  botoes.forEach(btn => {
    const estados = btn.dataset.showOn.split(',').map(s => s.trim());
    btn.classList.toggle('d-none', !estados.includes(estado));
  });

  // Regra especial: botão Salvar (submit) fica desabilitado no estado 'editar'
  const btnSalvar = form.querySelector('button[type="submit"]');
  if (btnSalvar) {
    btnSalvar.disabled = (estado === 'editar');
  }
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

/**
 * Define uma mensagem no estado global sisVar
 * Dispara renderMensagens automaticamente via Proxy
 * 
 * @param {string} tipo - 'sucesso', 'erro', 'aviso' ou 'info'
 * @param {string|array} conteudo - Mensagem ou array de mensagens
 * @param {boolean} ignorar - Se pode ignorar/fechar a mensagem (padrão: true)
 * 
 * @example
 * // Mensagem única
 * definirMensagem('sucesso', 'Operação realizada com sucesso!');
 * 
 * @example
 * // Array de mensagens
 * definirMensagem('erro', ['Erro 1', 'Erro 2', 'Erro 3']);
 * 
 * @example
 * // Mensagem que não pode ser fechada
 * definirMensagem('aviso', 'Ação irreversível!', false);
 */
export function definirMensagem(tipo, conteudo, ignorar = true) {
  const tiposValidos = ['sucesso', 'erro', 'aviso', 'info'];
  
  if (!tiposValidos.includes(tipo)) {
    console.warn(`Tipo de mensagem inválido: "${tipo}". Tipos válidos: ${tiposValidos.join(', ')}`);
    return;
  }

  // Normaliza conteudo para array
  const mensagens = Array.isArray(conteudo) ? conteudo : [conteudo];
  
  // Atualiza o estado das mensagens (dispara renderMensagens automaticamente via Proxy)
  _state.mensagens = {
    ..._state.mensagens,
    [tipo]: {
      conteudo: mensagens,
      ignorar: ignorar
    }
  };
}

/**
 * Hidrata os campos de um formulário com os dados do sisVar
 * Preenche os inputs HTML com os valores armazenados no estado
 * 
 * @param {string} formId - ID do formulário (deve corresponder a data-form-lock)
 * @returns {boolean} - true se hidratado com sucesso, false caso contrário
 * 
 * @example
 * hidratarFormulario('cadUsuario'); // Preenche todos os inputs do formulário
 */
export function hidratarFormulario(formId) {
  const form = document.querySelector(`[data-form-lock="${formId}"]`);
  if (!form) {
    console.warn(`Formulário com data-form-lock="${formId}" não encontrado no DOM`);
    return false;
  }

  const formData = _state.form[formId];
  if (!formData || !formData.campos) {
    console.warn(`Dados do formulário "${formId}" não encontrados no sisVar`);
    return false;
  }

  // Percorre todos os inputs do formulário
  const inputs = form.querySelectorAll('input, select, textarea');
  
  inputs.forEach(input => {
    const fieldName = input.name;
    const fieldValue = formData.campos[fieldName];

    if (fieldValue !== undefined && fieldValue !== null) {
      switch (input.type) {
        case 'checkbox':
          input.checked = Boolean(fieldValue);
          break;
        
        case 'radio':
          if (input.value === String(fieldValue)) {
            input.checked = true;
          }
          break;
        
        case 'number':
          input.value = fieldValue !== null ? Number(fieldValue) : '';
          break;
        
        default:
          input.value = fieldValue;
      }
    }
  });

  return true;
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
    delete newData.csrfToken;
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
    // Merge para a estrutura 'mensagens'
    else if (key === 'mensagens' && _state.mensagens) {
      _state.mensagens = { ..._state.mensagens, ...value };
    }
    // Atribuição direta para outras chaves
    else if (key !== 'csrfToken') {
      _state[key] = value;
    }
  });
}

/**
 * Limpa todas as mensagens do estado
 */
export function clearMessages() {
  _state.mensagens = {
    sucesso: { conteudo: [], ignorar: true },
    erro: { conteudo: [], ignorar: true },
    aviso: { conteudo: [], ignorar: true },
    info: { conteudo: [], ignorar: true }
  };
}

/**
 * Define o estado de um formulário no sisVar.
 * Ponto único de entrada para mudança de estado — nunca altere o estado diretamente.
 * O Proxy reativo dispara applyFormState() automaticamente.
 * 
 * Estados válidos: 'novo' | 'editar' | 'visualizar'
 * 
 * @param {string} formId - ID do formulário (ex: 'cadUsuario')
 * @param {string} estado - Novo estado do formulário
 * 
 * @example
 * setFormState('cadUsuario', 'editar');
 * setFormState('cadUsuario', 'novo');
 * setFormState('cadUsuario', 'visualizar');
 */
export function setFormState(formId, estado) {
  const estadosValidos = ['novo', 'editar', 'visualizar'];

  if (!estadosValidos.includes(estado)) {
    console.warn(`Estado inválido: "${estado}". Estados válidos: ${estadosValidos.join(', ')}`);
    return;
  }

  if (!_state.form[formId]) {
    console.warn(`Formulário "${formId}" não encontrado no sisVar.`);
    return;
  }

  // Atualiza o estado via Proxy — dispara applyFormState automaticamente
  _state.form = {
    ..._state.form,
    [formId]: {
      ..._state.form[formId],
      estado
    }
  };
}

/**
 * Debug: retorna uma cópia segura do estado para inspeção
 */
export function __debugState() {
  return structuredClone(_rawState);
}