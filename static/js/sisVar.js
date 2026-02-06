// 1. Definição do Estado com Proxy Reativo
let _rawState = { form: {}, schema: {}, mensagens: {}, usuario: {} };

const _state = new Proxy(_rawState, {
  set(target, property, value, receiver) {
    const result = Reflect.set(target, property, value, receiver);

    // Gatilho: Se a chave "form" ou qualquer parte dela mudar
    if (property === 'form') {
        Object.keys(value).forEach(formId => {
            // Verifica se existe o campo "estado" dentro do formId
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

// 2. Controlador de Interface (DOM)
/* Certifique-se de que seus formulários sigam o padrão de atributos:
<form data-form-lock="nomeForm">
<button data-show-on="novo,editar">Salvar</button>
<input data-keep-enabled="true"> (para campos de busca ou filtros que nunca travam).*/
function applyFormState(formId, estado) {
    const form = document.querySelector(`[data-form-lock="${formId}"]`);
    if (!form) return;

    const isDisabled = (estado === 'visualizar');

    // Seleciona campos, exceto os marcados com data-keep-enabled
    const inputs = form.querySelectorAll('input:not([data-keep-enabled]), select:not([data-keep-enabled]), textarea:not([data-keep-enabled]), button:not([data-keep-enabled])');

    inputs.forEach(input => {
        // Se o elemento tem controle de visibilidade, não mexemos no 'disabled'
        if (input.hasAttribute('data-show-on')) return;
        input.disabled = isDisabled;
    });

    // Gerencia visibilidade de botões (Bootstrap 5 d-none)
    const actionButtons = form.querySelectorAll('[data-show-on]');
    actionButtons.forEach(btn => {
        const allowedStates = btn.getAttribute('data-show-on').split(',');
        allowedStates.includes(estado) 
            ? btn.classList.remove('d-none') 
            : btn.classList.add('d-none');
    });
}

// --- Funções Exportadas ---

export function getForm(formId) {
  return _state.form[formId] ?? {};
}

export function getSchema(formId) {
  return _state.schema[formId];
}

export function getUsuario() {
  return _state.usuario;
}

export function renderMensagens() {
    const mensagens = _state.mensagens;
    const container = document.getElementById("container-mensagens");
    
    if (!container || !mensagens) return;
    
    container.innerHTML = '';
    const config = { sucesso: { classe: 'success' }, erro: { classe: 'danger' }, aviso: { classe: 'warning' } };

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
  };
  _state.form[formId]["campos"][name] = value;
}

export function getDataBackEnd() {
  const elemento = document.getElementById(_dadosBE); 
  if (elemento) {
    try {
      const dataBack = JSON.parse(elemento.textContent);
      // Ao atualizar o _state, o Proxy será disparado
      updateState(dataBack);
      elemento.remove(); 
    } catch (e) {
      console.error("Erro ao processar dados do Back-End.", e);
    }
  }
}

export function updateState(newData) {
  if (!newData || typeof newData !== 'object') return;

  // IMPORTANTE: Para disparar o Proxy de nível superior, 
  // atualizamos as chaves principais.
  Object.entries(newData).forEach(([key, value]) => {
    if (key === 'form' && _state.form) {
        // Criamos uma nova referência para garantir que o Proxy perceba a mudança profunda
        _state.form = { ..._state.form, ...value };
    } else {
        _state[key] = value;
    }
  });
}

export function __debugState() {
  return structuredClone(_rawState);
}