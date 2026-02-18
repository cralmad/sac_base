import { 
  getDataBackEnd, 
  getUsuario, 
  renderMensagens,
  getCsrfToken 
} from "/static/js/sisVar.js";

/**
 * Função utilitária para fazer requisições POST com CSRF token
 * Centraliza a lógica de requisição e tratamento de erros
 * Reutilizável em toda a aplicação
 * 
 * @param {string} url - URL do endpoint
 * @param {object} payload - Dados a enviar
 * @returns {Promise<{success: boolean, data: any, error: string | null}>}
 */
export async function fazerRequisicao(url, payload) {
  try {
    const csrfToken = getCsrfToken();
    
    if (!csrfToken) {
      console.warn("CSRF token não encontrado! Tente recarregar a página.");
    }

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken || ""
      },
      body: JSON.stringify(payload)
    });

    // Se a resposta não for JSON válido (exceto erros esperados 400, 401)
    if (!response.ok && response.status !== 400 && response.status !== 401) {
      throw new Error(`Erro HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    return { success: true, data };

  } catch (err) {
    console.error("Erro na requisição:", err);
    return { 
      success: false, 
      error: err.message,
      data: null
    };
  }
}

/**
 * Inicializa a navbar com informações do usuário autenticado
 */
export async function inicializarNavbarUsuario() {
    try {
        // Garante que os dados do backend foram carregados
        await getDataBackEnd();

        const usuario = getUsuario();

        renderMensagens();

        // Se não estiver autenticado, não faz nada
        if (!usuario || !usuario.autenticado) {
            return;
        }

        // Localiza a navbar existente
        const navbarContainer = document.getElementById("navbase");

        // Cria o elemento do dropdown
        const dropdownHtml = `
            <div class="dropdown ms-auto">
                <a class="nav-link dropdown-toggle text-light d-flex align-items-center"
                   href="#"
                   role="button"
                   data-bs-toggle="dropdown"
                   aria-expanded="false">
                    <i class="bi bi-person-circle me-2"></i>
                </a>

                <ul class="dropdown-menu dropdown-menu-end">
                    <li class="dropdown-item-text fw-bold">
                        ${usuario.nome}
                    </li>
                    <li><hr class="dropdown-divider"></li>
                    <li>
                        <a class="dropdown-item" href="/app/usuario/alterarsenha/">
                            Alterar senha
                        </a>
                    </li>
                    <li>
                        <a class="dropdown-item" href="/app/usuario/logout/">
                            Logout
                        </a>
                    </li>
                </ul>
            </div>
        `;

        // Insere no final da navbar (lado direito)
        navbarContainer.insertAdjacentHTML("beforeend", dropdownHtml);

    } catch (erro) {
        console.error("Erro ao inicializar navbar de usuário:", erro);
    }
}

// Auto-executa ao carregar o módulo
document.addEventListener("DOMContentLoaded", () => {
    inicializarNavbarUsuario();
});

/*****************DEBUG**********************/
import { __debugState } from '/static/js/sisVar.js';

window.__DEBUG__ = {
  get state() {
    return __debugState();
  }
};

function exibir() {
  console.log(window.__DEBUG__.state);
}

document.getElementById('teste').addEventListener('click', exibir);