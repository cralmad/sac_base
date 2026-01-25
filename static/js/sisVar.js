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

export function getMesangens(mensagemExtra = null) {
    const mensagens = mensagemExtra || _state.mensagens;
    const container = document.getElementById("container-mensagens");
    container.innerHTML = '';
    
    if (!container || !mensagens) return;

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

    // Se for uma mensagem extra (fetch), tratamos como um único objeto de mensagem
    if (mensagemExtra) {
        // Assume o formato {sucesso: {conteudo: [], ignorar: true}}
        Object.entries(mensagemExtra).forEach(([tipo, dados]) => renderizar(tipo, dados));
    } else {
        // Processa o estado global vindo do context_processors.py
        Object.entries(mensagens).forEach(([tipo, dados]) => renderizar(tipo, dados));
    }
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

export function __debugState() {
  return structuredClone(_state);
}