let _dataBackEndProcessado = false;

const _dadosBE = 'sisDados';
const _estadosFormularioValidos = ['novo', 'editar', 'visualizar'];
const _estadoAplicadoPorFormulario = new Map();

function createDefaultMessages() {
  return {
    sucesso: { conteudo: [], ignorar: true },
    erro: { conteudo: [], ignorar: true },
    aviso: { conteudo: [], ignorar: true },
    info: { conteudo: [], ignorar: true }
  };
}

function createDefaultMeta() {
  return {
    security: {
      csrfTokenValue: ''
    },
    permissions: {},
    options: {},
    datasets: {}
  };
}

function isPlainObject(value) {
  return Object.prototype.toString.call(value) === '[object Object]';
}

function cloneValue(value) {
  if (value === undefined) {
    return undefined;
  }

  if (typeof structuredClone === 'function') {
    return structuredClone(value);
  }

  return JSON.parse(JSON.stringify(value));
}

function mergeObjects(base, patch) {
  const baseObj = isPlainObject(base) ? base : {};
  const patchObj = isPlainObject(patch) ? patch : {};
  const result = { ...baseObj };

  Object.entries(patchObj).forEach(([key, value]) => {
    if (isPlainObject(value) && isPlainObject(result[key])) {
      result[key] = mergeObjects(result[key], value);
      return;
    }

    result[key] = cloneValue(value);
  });

  return result;
}

function buildLegacyOthersFromMeta(meta) {
  const normalizedMeta = isPlainObject(meta) ? meta : createDefaultMeta();
  return {
    csrf_token_value: normalizedMeta.security?.csrfTokenValue || '',
    permissoes: cloneValue(normalizedMeta.permissions || {}),
    opcoes: cloneValue(normalizedMeta.options || {}),
    ...cloneValue(normalizedMeta.datasets || {})
  };
}

function normalizeLegacyOthers(others) {
  const normalizedMeta = createDefaultMeta();

  if (!isPlainObject(others)) {
    return normalizedMeta;
  }

  const {
    csrf_token_value,
    permissoes,
    opcoes,
    ...datasets
  } = others;

  normalizedMeta.security.csrfTokenValue = csrf_token_value || '';
  normalizedMeta.permissions = isPlainObject(permissoes) ? cloneValue(permissoes) : {};
  normalizedMeta.options = isPlainObject(opcoes) ? cloneValue(opcoes) : {};
  normalizedMeta.datasets = cloneValue(datasets);

  return normalizedMeta;
}

function normalizeMeta(meta) {
  const normalizedMeta = createDefaultMeta();

  if (!isPlainObject(meta)) {
    return normalizedMeta;
  }

  if (isPlainObject(meta.security)) {
    normalizedMeta.security = mergeObjects(normalizedMeta.security, meta.security);
  }

  if (isPlainObject(meta.permissions)) {
    normalizedMeta.permissions = cloneValue(meta.permissions);
  }

  if (isPlainObject(meta.options)) {
    normalizedMeta.options = cloneValue(meta.options);
  }

  if (isPlainObject(meta.datasets)) {
    normalizedMeta.datasets = cloneValue(meta.datasets);
  }

  if ('csrfTokenValue' in meta || 'csrf_token_value' in meta) {
    normalizedMeta.security.csrfTokenValue = meta.csrfTokenValue ?? meta.csrf_token_value ?? '';
  }

  Object.entries(meta).forEach(([key, value]) => {
    if (['security', 'permissions', 'options', 'datasets', 'csrfTokenValue', 'csrf_token_value'].includes(key)) {
      return;
    }

    normalizedMeta.datasets[key] = cloneValue(value);
  });

  return normalizedMeta;
}

function mergeFormState(currentForm, incomingForm) {
  const current = isPlainObject(currentForm) ? currentForm : {};
  const incoming = isPlainObject(incomingForm) ? incomingForm : {};
  const result = { ...current };

  Object.entries(incoming).forEach(([formId, formData]) => {
    const atual = current[formId] || {};
    const proximo = { ...atual, ...cloneValue(formData) };

    if (isPlainObject(atual.campos) && isPlainObject(formData?.campos)) {
      proximo.campos = mergeObjects(atual.campos, formData.campos);
    }

    result[formId] = proximo;
  });

  return result;
}

let _rawState = {
  form: {},
  schema: {},
  mensagens: createDefaultMessages(),
  usuario: {},
  meta: createDefaultMeta(),
  others: buildLegacyOthersFromMeta(createDefaultMeta())
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

function syncLegacyOthersFromMeta() {
  _rawState.others = buildLegacyOthersFromMeta(_rawState.meta);
}

function applyFormState(formId, estado, options = {}) {
  const { force = false } = options;

  const form = document.querySelector(`[data-form-lock="${formId}"]`);
  if (!form) return;

  // 'novo': limpa o DOM e habilita inputs
  // 'editar': apenas habilita inputs (dados carregados permanecem no DOM)
  // 'visualizar': desabilita inputs (hidratarFormulario() deve ter sido chamado antes)
  const estadoAnterior = _estadoAplicadoPorFormulario.get(formId);
  if (estado === 'novo' && (force || estadoAnterior !== 'novo')) {
    clearFormFields(form);
  }

  // Habilita inputs em 'novo' e 'editar'; desabilita em 'visualizar'
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

  // Atualiza o sufixo do título da página.
  // Apenas o estado 'editar' exibe a indicação; nos demais o sufixo é apagado.
  const pageTitleSuffix = document.getElementById('page-title-suffix');
  if (pageTitleSuffix) {
    pageTitleSuffix.textContent = estado === 'editar' ? ' — Edição de Registro' : '';
  }

  _estadoAplicadoPorFormulario.set(formId, estado);
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

/**
 * FIX #3: getForm() retorna structuredClone para evitar mutações externas
 */
export function getForm(formId = null) {
  if (formId) {
    const form = _state.form[formId];
    return form ? structuredClone(form) : null;
  }
  return structuredClone(_state.form);
}

export function getSchema(schemaId = null) {
  if (schemaId) {
    const schema = _state.schema[schemaId];
    return schema ? cloneValue(schema) : null;
  }

  return cloneValue(_state.schema);
}

export function getUsuario() {
  return cloneValue(_state.usuario);
}

export function getMeta(section = null) {
  if (section) {
    return cloneValue(_state.meta?.[section] ?? null);
  }

  return cloneValue(_state.meta);
}

export function getFormState(formId) {
  return _state.form?.[formId]?.estado ?? null;
}

export function getFormFields(formId) {
  return cloneValue(_state.form?.[formId]?.campos ?? {});
}

export function getScreenPermissions(screenKey, fallback = {}) {
  return cloneValue(_state.meta?.permissions?.[screenKey] ?? fallback);
}

export function hasScreenPermission(screenKey, action) {
  return Boolean(_state.meta?.permissions?.[screenKey]?.[action]);
}

export function getOptions(optionKey = null, fallback = null) {
  if (!optionKey) {
    return cloneValue(_state.meta?.options ?? {});
  }

  return cloneValue(_state.meta?.options?.[optionKey] ?? fallback);
}

export function getDataset(datasetKey = null, fallback = null) {
  if (!datasetKey) {
    return cloneValue(_state.meta?.datasets ?? {});
  }

  return cloneValue(_state.meta?.datasets?.[datasetKey] ?? fallback);
}

/**
 * Recupera o token CSRF atual guardado no estado
 */
export function getCsrfToken() {
  return _state.meta?.security?.csrfTokenValue || _state.others?.csrf_token_value || "";
}

export function renderMensagens() {
  const container = document.getElementById('container-mensagens');
  if (!container) return;

  container.innerHTML = '';

  const mensagens = _state.mensagens;

  const config = {
    sucesso: { classe: 'success' },
    erro: { classe: 'danger' },
    aviso: { classe: 'warning' },
    info: { classe: 'info' }
  };

  let temMensagemVisivel = false; // ← NOVO

  const renderizar = (tipo, dados) => {
    if (dados.conteudo && dados.conteudo.length > 0) {
      const podeIgnorar = dados.ignorar !== false;
      temMensagemVisivel = true; // ← NOVO

      dados.conteudo.forEach(msg => {
        const alerta = document.createElement('div');
        alerta.className = `alert alert-${config[tipo]?.classe || 'secondary'} alert-dismissible fade show`;
        alerta.textContent = msg;

        if (podeIgnorar) {
          const btnClose = document.createElement('button');
          btnClose.type = "button";
          btnClose.className = "btn-close";
          btnClose.setAttribute("data-bs-dismiss", "alert");
          alerta.appendChild(btnClose);
        }

        container.appendChild(alerta);
      });
    }
  };

  Object.entries(mensagens).forEach(([tipo, dados]) => renderizar(tipo, dados));

  // ← NOVO: rola para o topo sempre que houver mensagens visíveis
  if (temMensagemVisivel) {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

/**
 * Define uma mensagem no estado global sisVar
 * Dispara renderMensagens automaticamente via Proxy
 * 
 * @param {string} tipo - 'sucesso', 'erro', 'aviso' ou 'info'
 * @param {string|array} conteudo - Mensagem ou array de mensagens
 * @param {boolean} ignorar - Se pode ignorar/fechar a mensagem (padrão: true)
 */
export function definirMensagem(tipo, conteudo, ignorar = true) {
  const tiposValidos = ['sucesso', 'erro', 'aviso', 'info'];
  
  if (!tiposValidos.includes(tipo)) {
    console.warn(`Tipo de mensagem inválido: "${tipo}". Tipos válidos: ${tiposValidos.join(', ')}`);
    return;
  }

  const mensagens = Array.isArray(conteudo) ? conteudo : [conteudo];
  
  _state.mensagens = {
    ..._state.mensagens,
    [tipo]: {
      conteudo: mensagens,
      ignorar: ignorar
    }
  };
}

/**
 * Abre o modal de confirmação global definido em base.html.
 * Reutilizável em qualquer página — não requer nenhum código adicional nos scripts de página.
 *
 * @param {object} opcoes
 * @param {string}   opcoes.titulo      - Título do modal
 * @param {string}   opcoes.mensagem    - Texto da pergunta exibida ao usuário
 * @param {Function} opcoes.onConfirmar - Callback executado se o usuário clicar em "Sim"
 *
 * @example
 * confirmar({
 *   titulo: 'Salvar registro',
 *   mensagem: 'Deseja salvar as alterações?',
 *   onConfirmar: () => form.dispatchEvent(new Event('submit'))
 * });
 */
export function confirmar({ titulo, mensagem, onConfirmar }) {
  const modalEl = document.getElementById('modal-confirmacao');
  if (!modalEl) {
    console.warn('Modal #modal-confirmacao não encontrado. Verifique o base.html.');
    if (confirm(`${titulo}\n\n${mensagem}`)) onConfirmar();
    return;
  }

  document.getElementById('modal-confirmacao-titulo').textContent = titulo;
  document.getElementById('modal-confirmacao-mensagem').textContent = mensagem;

  const modal = bootstrap.Modal.getInstance(modalEl) ?? new bootstrap.Modal(modalEl);

  const btnSim = document.getElementById('modal-confirmacao-btn-sim');

  // FIX #6: Clona o botão para remover listeners anteriores e evitar acúmulo de handlers
  const novoBtn = btnSim.cloneNode(true);
  btnSim.parentNode.replaceChild(novoBtn, btnSim);

  novoBtn.addEventListener('click', () => {
    // Sinaliza que a confirmação foi dada, mas aguarda o modal fechar completamente
    // antes de executar o callback — evita o erro de aria-hidden com foco ativo
    modalEl.addEventListener('hidden.bs.modal', () => onConfirmar(), { once: true });
    modal.hide();
  });

  modal.show();
}

/**
 * FIX #4: hidratarFormulario() agora dispara eventos 'input' para triggers de formatação
 * Hidrata os campos de um formulário com os dados do sisVar
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

  // FIX #4: Dispara eventos 'input' para ativar formatadores (input_rules.js)
  inputs.forEach(input => {
    const inputEvent = new Event('input', { bubbles: true });
    input.dispatchEvent(inputEvent);
  });

  return true;
}

/**
 * FIX #2 e #5: updateFormField() agora:
 * - Valida contra schema se existir
 * - Dispara CustomEvent para componentes externos
 * - Retorna booleano indicando sucesso
 */
export function updateFormField(formId, name, value) {
  if (!_state.form[formId]) {
    console.error(`Formulário ${formId} não encontrado.`);
    return false;
  }

  if (!_state.form[formId]["campos"]) {
    console.error(`Campos não inicializados para ${formId}.`);
    return false;
  }

  // FIX #5: Validar contra schema se existir
  const schema = _state.schema[formId]?.[name];
  if (schema && schema.validate) {
    const validation = schema.validate(value);
    if (!validation.valid) {
      console.warn(`Validação falhou para ${name}:`, validation.error);
      return false;
    }
  }

  const oldValue = _state.form[formId]["campos"][name];
  _state.form[formId]["campos"][name] = value;

  // FIX #2: Dispara CustomEvent para notificar componentes externos
  window.dispatchEvent(new CustomEvent('sisvar:field-changed', {
    detail: {
      formId,
      fieldName: name,
      oldValue,
      newValue: value,
      timestamp: new Date().toISOString()
    }
  }));

  return true;
}

export function getDataBackEnd() {
  // FIX #1: Flag previne múltiplas execuções
  if (_dataBackEndProcessado) {
    console.debug("getDataBackEnd() já foi processado anteriormente");
    return;
  }

  const elemento = document.getElementById(_dadosBE);

  if (elemento) {
    try {
      const dataBack = JSON.parse(elemento.textContent);
      updateState(dataBack);
      elemento.remove();
      _dataBackEndProcessado = true;
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

  const payload = cloneValue(newData);
  const knownKeys = new Set(['form', 'schema', 'mensagens', 'messages', 'usuario', 'user', 'others', 'meta', 'csrfToken']);

  if (payload.form) {
    _state.form = mergeFormState(_state.form, payload.form);

    Object.entries(payload.form).forEach(([formId, formData]) => {
      if (formData?.estado === 'novo') {
        applyFormState(formId, 'novo', { force: true });
      }
    });
  }

  if (payload.schema) {
    _state.schema = mergeObjects(_state.schema, payload.schema);
  }

  if (payload.mensagens || payload.messages) {
    _state.mensagens = mergeObjects(createDefaultMessages(), payload.mensagens ?? payload.messages);
  }

  if (payload.usuario || payload.user) {
    _state.usuario = mergeObjects(_state.usuario, payload.usuario ?? payload.user);
  }

  const metaFromOthers = normalizeLegacyOthers(payload.others);
  const explicitMeta = normalizeMeta(payload.meta);
  const nextMeta = mergeObjects(mergeObjects(_state.meta, metaFromOthers), explicitMeta);

  if (payload.csrfToken) {
    nextMeta.security.csrfTokenValue = payload.csrfToken;
  }

  _state.meta = nextMeta;
  syncLegacyOthersFromMeta();

  Object.entries(payload).forEach(([key, value]) => {
    if (knownKeys.has(key)) {
      return;
    }

    _state[key] = cloneValue(value);
  });
}

/**
 * Limpa todas as mensagens do estado
 */
export function clearMessages() {
  _state.mensagens = createDefaultMessages();
}

/**
 * Define o estado de um formulário no sisVar.
 * 
 * Estados válidos: 'novo' | 'editar' | 'visualizar'
 * 
 * Efeitos colaterais por estado:
 *   'novo'       → reconstrói campos a partir do schema (valores iniciais) e zera update
 *   'editar'     → mantém campos e update intactos; habilita inputs
 *   'visualizar' → desabilita inputs; hidratarFormulario() deve ser chamado antes
 */
export function setFormState(formId, estado) {
  if (!_estadosFormularioValidos.includes(estado)) {
    console.warn(`Estado inválido: "${estado}". Estados válidos: ${_estadosFormularioValidos.join(', ')}`);
    return;
  }

  if (!_state.form[formId]) {
    console.warn(`Formulário "${formId}" não encontrado no sisVar.`);
    return;
  }

  let camposAtualizados = _state.form[formId].campos;
  let updateAtualizado = _state.form[formId].update ?? null;

  if (estado === 'novo') {
    const schema = _state.schema[formId] ?? {};
    camposAtualizados = Object.fromEntries(
      Object.entries(schema).map(([campo, regras]) => [campo, regras.value ?? null])
    );
    updateAtualizado = null;
  }

  _state.form = {
    ..._state.form,
    [formId]: {
      ..._state.form[formId],
      estado,
      update: updateAtualizado,
      campos: camposAtualizados
    }
  };

  applyFormState(formId, estado, { force: estado === 'novo' });
}

export function canTransitionFormState(formId, nextState) {
  if (!_estadosFormularioValidos.includes(nextState)) {
    return false;
  }

  const currentState = getFormState(formId);
  if (!currentState) {
    return false;
  }

  const allowedTransitions = {
    novo: ['visualizar', 'editar', 'novo'],
    editar: ['visualizar', 'novo', 'editar'],
    visualizar: ['editar', 'novo', 'visualizar']
  };

  return allowedTransitions[currentState]?.includes(nextState) ?? false;
}

export function transitionFormState(formId, nextState) {
  if (!canTransitionFormState(formId, nextState)) {
    console.warn(`Transição inválida de estado para o formulário "${formId}": ${getFormState(formId)} -> ${nextState}`);
    return false;
  }

  setFormState(formId, nextState);
  return true;
}

export function resetFormState(formId) {
  if (!_state.form[formId]) {
    console.warn(`Formulário "${formId}" não encontrado no sisVar.`);
    return false;
  }

  setFormState(formId, 'novo');
  return true;
}

/**
 * Define ou atualiza o schema de validação/configuração de um formulário.
 */
export function setSchema(formId, schema) {
  _state.schema = {
    ..._state.schema,
    [formId]: cloneValue(schema)
  };
}

/**
 * Debug: retorna uma cópia segura do estado para inspeção
 */
export function __debugState() {
  return structuredClone(_rawState);
}

/**
 * Retorna uma cópia segura de _state.others para leitura externa.
 * Use para acessar chaves dinâmicas injetadas pelo backend (ex: opcoes).
 */
export function getOthers() {
  syncLegacyOthersFromMeta();
  return cloneValue(_state.others);
}
