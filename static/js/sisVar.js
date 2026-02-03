const _state = {};

const _dadosBE = 'sisDados'; // ID do elemento HTML

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

    const config = {
        sucesso: { classe: 'success' },
        erro:    { classe: 'danger' },
        aviso:   { classe: 'warning' }
    };

    // Função interna para evitar repetição de código na renderização
    const renderizar = (tipo, dados) => {
        if (dados.conteudo && dados.conteudo.length > 0) {
            const podeIgnorar = dados.ignorar !== false;
            
            dados.conteudo.forEach(msg => {
                const alerta = document.createElement('div');
                alerta.className = `alert alert-${config[tipo]?.classe || 'secondary'} fade show`;
                
                if (podeIgnorar) {
                    alerta.classList.add('alert-dismissible');
                }

                alerta.innerHTML = `
                    ${msg}
                    ${podeIgnorar ? '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>' : ''}
                `;
                
                container.appendChild(alerta);
            });
        }
    };

    Object.entries(mensagens).forEach(([tipo, dados]) => renderizar(tipo, dados));
}

export function updateFormField(formId, name, value) {
  if (!_state.form[formId]) {
    alert(`Formulário ${formId} não encontrado no estado. Verifique o back-end.`);
    return;
  };
  _state.form[formId]["campos"][name] = value;
}

export function getDataBackEnd() {
  const elemento = document.getElementById(_dadosBE); 
  
  if (elemento) {
    try {
      const dataBack = JSON.parse(elemento.textContent);

      // "Hidrata" o objeto _state mantendo a mesma referência de memória
      Object.assign(_state, dataBack);

      // Limpa o elemento do DOM após a leitura
      elemento.remove(); 
    } catch (e) {
      console.error("Erro ao processar dados do Back-End: JSON inválido.", e);
    }
  }
}

/**
  Atualiza o estado global com novos dados vindos do Back-End.
 * @param {Object} newData - Objeto vindo do JsonResponse do Back-End
 */
export function updateState(newData) {
  if (!newData || typeof newData !== 'object') return;

  // Percorremos as chaves enviadas pelo Back-End (ex: "form", "mensagens")
  Object.entries(newData).forEach(([key, value]) => {
    
    // Se a chave for "form", fazemos um merge dos formulários específicos
    // para não apagar outros formulários que já estão no estado.
    if (key === 'form' && _state.form) {
      Object.assign(_state.form, value);
    } 
    
    else {
      _state[key] = value;
    }
  });

  // Gatilho automático: se vieram mensagens novas, renderiza na tela
  if (newData.mensagens) {renderMensagens();}
}

export function __debugState() {
  return structuredClone(_state);
}