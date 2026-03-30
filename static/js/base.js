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
  const STATUS_LEGIVEIS = [400, 401, 409, 422];

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
 * Inicializa a navbar com as informações do usuário autenticado.
 * Exibe: ícone + nome do usuário + seta de dropdown.
 * O menu offcanvas da sidebar é 100% Bootstrap — sem JS necessário aqui.
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
            <div class=\"dropdown ms-auto\">\n                <a class=\"nav-link dropdown-toggle text-light d-flex align-items-center gap-2\"
                   href=\"#\"
                   role=\"button\"
                   data-bs-toggle=\"dropdown\"
                   aria-expanded=\"false\">
                    <i class=\"bi bi-person-circle\"></i>
                    <span class=\"d-none d-sm-inline\">${usuario.nome}</span>
                </a>\n
                <ul class=\"dropdown-menu dropdown-menu-end\">\n                    <li class=\"dropdown-item-text fw-bold d-sm-none\">\n                        ${usuario.nome}\n                    </li>\n                    <li class=\"d-sm-none\"><hr class=\"dropdown-divider\"></li>\n                    <li>\n                        <a class=\"dropdown-item d-flex align-items-center gap-2\" href=\"/app/usuario/alterarsenha/\">
                            <i class=\"bi bi-key\"></i> Alterar senha
                        </a>\n                    </li>\n                    <li>\n                        <a class=\"dropdown-item d-flex align-items-center gap-2 text-danger\" href=\"/app/usuario/logout/\">
                            <i class=\"bi bi-box-arrow-right\"></i> Logout
                        </a>\n                    </li>\n                </ul>\n            </div>\n        `;

        navbarContainer.querySelector(".container-fluid").insertAdjacentHTML("beforeend", dropdownHtml);

        // Marca o link ativo na sidebar com base na URL atual
        marcarLinkAtivo();

    } catch (erro) {
        console.error("Erro ao inicializar navbar de usuário:", erro);
    }
}

/**
 * Marca o link ativo na sidebar comparando o href com a URL atual,
 * e expande automaticamente o collapse pai do link ativo.
 */
function marcarLinkAtivo() {
    const path = window.location.pathname;
    document.querySelectorAll("#sidebar-nav .sidebar-sublink").forEach(link => {
        if (link.getAttribute("href") === path) {
            link.classList.add("active");
            // Expande o collapse pai
            const collapse = link.closest(".collapse");
            if (collapse) {
                collapse.classList.add("show");
                const trigger = document.querySelector(`[data-bs-target=\"#${collapse.id}\"]`);
                if (trigger) trigger.setAttribute("aria-expanded", "true");
            }
        }
    });
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