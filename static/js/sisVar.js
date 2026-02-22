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

  // 'novo': limpa o DOM e habilita inputs
  // 'editar': apenas habilita inputs (dados carregados permanecem no DOM)
  // 'visualizar': desabilita inputs (hidratarFormulario() deve ter sido chamado antes)
  if (estado === 'novo') {
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
  // Apenas o estado 'editar' exibe a indica��ão; nos demais o sufixo é apagado.
  const pageTitleSuffix = document.getElementById('page-title-suffix');
  if (pageTitleSuffix) {
    pageTitleSuffix.textContent = estado === 'editar' ? ' — Edição de Registro' : '';
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

  // Clona o botão para remover listeners anteriores e evitar acúmulo de handlers
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

  if (newData.csrfToken) {
    _state.others.csrf_token_value = newData.csrfToken;
    delete newData.csrfToken;
  }

  Object.entries(newData).forEach(([key, value]) => {
    if (key === 'form' && _state.form) {
      _state.form = { ..._state.form, ...value };
    } 
    else if (key === 'others' && _state.others) {
      _state.others = { ..._state.others, ...value };
    } 
    else if (key === 'mensagens' && _state.mensagens) {
      _state.mensagens = { ..._state.mensagens, ...value };
    }
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
 * 
 * Estados válidos: 'novo' | 'editar' | 'visualizar'
 * 
 * Efeitos colaterais por estado:
 *   'novo'       → reconstrói campos a partir do schema (valores iniciais) e zera update
 *   'editar'     → mantém campos e update intactos; habilita inputs
 *   'visualizar' → desabilita inputs; hidratarFormulario() deve ser chamado antes
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
}

/**
 * Define ou atualiza o schema de validação/configuração de um formulário.
 */
export function setSchema(formId, schema) {
  _state.schema = {
    ..._state.schema,
    [formId]: schema
  };
}

/**
 * Debug: retorna uma cópia segura do estado para inspeção
 */
export function __debugState() {
  return structuredClone(_rawState);
}