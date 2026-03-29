import { 
  getDataBackEnd, 
  getUsuario, 
  renderMensagens,
  getCsrfToken 
} from "/static/js/sisVar.js";

import { AppLoader } from "/static/js/loader.js";

/**
 * Função utilitária para fazer requisições POST com CSRF token.
 * Status tratados como resposta legível (não lançam exceção):
 *   200 — sucesso
 *   400 — erro de validação de schema
 *   401 — não autenticado
 *   422 — erro de regra de negócio (ex: duplicidade)
 * Qualquer outro status de erro lança exceção.
 */
export async function fazerRequisicao(url, payload) {
  const STATUS_LEGIVEIS = [400, 401, 422];

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

    if (!response.ok && !STATUS_LEGIVEIS.includes(response.status)) {
      throw new Error(`Erro HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();

    // Para status de erro legível, retorna success: false com data para
    // que updateState() possa processar as mensagens do servidor
    if (!response.ok) {
      return { success: false, status: response.status, data, error: null };
    }

    return { success: true, status: response.status, data };

  } catch (err) {
    console.error("Erro na requisição:", err);
    return {
      success: false,
      status: null,
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
        await getDataBackEnd();

        const usuario = getUsuario();

        renderMensagens();

        if (!usuario || !usuario.autenticado) {
            return;
        }

        const navbarContainer = document.getElementById("navbase");

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

        navbarContainer.insertAdjacentHTML("beforeend", dropdownHtml);

    } catch (erro) {
        console.error("Erro ao inicializar navbar de usuário:", erro);
    }
}

// Inicializa AppLoader e navbar quando DOM está pronto
document.addEventListener("DOMContentLoaded", async () => {
    AppLoader.init();
    await inicializarNavbarUsuario();
    AppLoader.hide();
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

document.addEventListener('DOMContentLoaded', () => {
  const testeBtn = document.getElementById('teste');
  if (testeBtn) {
    testeBtn.addEventListener('click', exibir);
  }
});