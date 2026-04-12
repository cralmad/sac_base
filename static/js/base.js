import {
  getDataBackEnd,
  getMeta,
  getUsuario,
  renderMensagens,
  getCsrfToken
} from "/static/js/sisVar.js";

import { AppLoader } from "/static/js/loader.js";

getDataBackEnd();

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
 * Inicializa a navbar com informações do usuário autenticado.
 * Exibe: ícone + nome do usuário + seta de dropdown.
 * O menu offcanvas da sidebar é 100% Bootstrap — sem JS necessário.
 */
export async function inicializarNavbarUsuario() {
  try {
    getDataBackEnd();

    const usuario = getUsuario();
    const security = getMeta("security") || {};
    const filialAtiva = security.activeFilial || null;

    renderMensagens();

    if (!usuario || !usuario.autenticado) {
      return;
    }

    const navbarContainer = document.getElementById("navbase");

    const filialHtml = filialAtiva
      ? `
      <div class="d-flex align-items-center ms-auto me-2 text-light small" style="min-width: 0; max-width: 48vw;">
        <i class="bi bi-buildings me-2"></i>
        <span class="fw-semibold me-2 d-none d-md-inline">${filialAtiva.isMatriz ? "Matriz ativa:" : "Filial ativa:"}</span>
        <span class="badge text-bg-light text-dark text-truncate" style="max-width: 100%;">${filialAtiva.nome} (${filialAtiva.codigo})</span>
      </div>
    `
      : "<div class=\"ms-auto\"></div>";

    const dropdownHtml = `
      ${filialHtml}
      <div class="dropdown ms-auto">
        <a class="nav-link dropdown-toggle text-light d-flex align-items-center gap-2"
           href="#"
           role="button"
           data-bs-toggle="dropdown"
           aria-expanded="false">
          <i class="bi bi-person-circle"></i>
          <span class="d-none d-sm-inline">${usuario.nome}</span>
        </a>

        <ul class="dropdown-menu dropdown-menu-end">
          <li class="dropdown-item-text fw-bold d-sm-none">${usuario.nome}</li>
          <li class="d-sm-none"><hr class="dropdown-divider"></li>
          <li>
            <a class="dropdown-item d-flex align-items-center gap-2" href="/app/usuario/alterarsenha/">
              <i class="bi bi-key"></i> Alterar senha
            </a>
          </li>
          <li>
            <a class="dropdown-item d-flex align-items-center gap-2 text-danger" href="/app/usuario/logout/">
              <i class="bi bi-box-arrow-right"></i> Logout
            </a>
          </li>
        </ul>
      </div>
    `;

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
        const trigger = document.querySelector(`[data-bs-target="#${collapse.id}"]`);
        if (trigger) trigger.setAttribute("aria-expanded", "true");
      }
    }
  });
}

function aplicarPermissoesSidebar() {
  const usuario = getUsuario();
  const permissoes = new Set(usuario?.permissoes || []);

  document.querySelectorAll("#sidebar-nav .sidebar-sublink[data-required-permission]").forEach(link => {
    const permissao = link.dataset.requiredPermission;
    const item = link.closest("li.nav-item");
    const permitido = !permissao || permissoes.has(permissao);

    if (item) {
      item.classList.toggle("d-none", !permitido);
    }
  });

  const collapses = Array.from(document.querySelectorAll("#sidebar-nav .collapse")).reverse();
  collapses.forEach(collapse => {
    const lista = collapse.querySelector(":scope > ul");
    if (!lista) {
      return;
    }

    const temFilhoVisivel = Array.from(lista.children).some(child => !child.classList.contains("d-none"));
    collapse.classList.toggle("d-none", !temFilhoVisivel);

    const itemPai = collapse.closest("li.nav-item");
    if (itemPai) {
      itemPai.classList.toggle("d-none", !temFilhoVisivel);
    }
  });
}

function inicializarTooltips() {
  const triggers = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  triggers.forEach((element) => {
    bootstrap.Tooltip.getOrCreateInstance(element);
  });
}

// Inicializa AppLoader e navbar quando DOM está pronto
document.addEventListener("DOMContentLoaded", async () => {
  AppLoader.init();
  await inicializarNavbarUsuario();
  aplicarPermissoesSidebar();
  inicializarTooltips();
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