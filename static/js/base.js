import {
  getDataBackEnd,
  getMeta,
  getUsuario,
  renderMensagens,
  getCsrfToken
} from "/static/js/sisVar.js";

import { AppLoader } from "/static/js/loader.js";
import { escapeHtml } from "/static/js/html.js";

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
    const containerFluid = navbarContainer?.querySelector(".container-fluid");
    if (!containerFluid) {
      return;
    }

    if (filialAtiva) {
      const filialWrapper = document.createElement("div");
      filialWrapper.className = "d-flex align-items-center ms-auto me-2 text-light small";
      filialWrapper.style.minWidth = "0";
      filialWrapper.style.maxWidth = "48vw";

      const filialIcon = document.createElement("i");
      filialIcon.className = "bi bi-buildings me-2";
      filialWrapper.appendChild(filialIcon);

      const filialLabel = document.createElement("span");
      filialLabel.className = "fw-semibold me-2 d-none d-md-inline";
      filialLabel.textContent = filialAtiva.isMatriz ? "Matriz ativa:" : "Filial ativa:";
      filialWrapper.appendChild(filialLabel);

      const filialBadge = document.createElement("span");
      filialBadge.className = "badge text-bg-light text-dark text-truncate";
      filialBadge.style.maxWidth = "100%";
      filialBadge.textContent = `${filialAtiva.nome} (${filialAtiva.codigo})`;
      filialWrapper.appendChild(filialBadge);

      containerFluid.appendChild(filialWrapper);
    } else {
      const spacer = document.createElement("div");
      spacer.className = "ms-auto";
      containerFluid.appendChild(spacer);
    }

    const dropdown = document.createElement("div");
    dropdown.className = "dropdown ms-auto";

    const toggle = document.createElement("a");
    toggle.className = "nav-link dropdown-toggle text-light d-flex align-items-center gap-2";
    toggle.href = "#";
    toggle.setAttribute("role", "button");
    toggle.setAttribute("data-bs-toggle", "dropdown");
    toggle.setAttribute("aria-expanded", "false");

    const toggleIcon = document.createElement("i");
    toggleIcon.className = "bi bi-person-circle";
    toggle.appendChild(toggleIcon);

    const toggleText = document.createElement("span");
    toggleText.className = "d-none d-sm-inline";
    toggleText.textContent = usuario.nome || "";
    toggle.appendChild(toggleText);

    const menu = document.createElement("ul");
    menu.className = "dropdown-menu dropdown-menu-end";

    const mobileUserItem = document.createElement("li");
    mobileUserItem.className = "dropdown-item-text fw-bold d-sm-none";
    mobileUserItem.textContent = usuario.nome || "";
    menu.appendChild(mobileUserItem);

    const dividerWrapper = document.createElement("li");
    dividerWrapper.className = "d-sm-none";
    const divider = document.createElement("hr");
    divider.className = "dropdown-divider";
    dividerWrapper.appendChild(divider);
    menu.appendChild(dividerWrapper);

    const alterarSenhaItem = document.createElement("li");
    const alterarSenhaLink = document.createElement("a");
    alterarSenhaLink.className = "dropdown-item d-flex align-items-center gap-2";
    alterarSenhaLink.href = "/app/usuario/alterarsenha/";
    const alterarSenhaIcon = document.createElement("i");
    alterarSenhaIcon.className = "bi bi-key";
    alterarSenhaLink.appendChild(alterarSenhaIcon);
    alterarSenhaLink.appendChild(document.createTextNode(" Alterar senha"));
    alterarSenhaItem.appendChild(alterarSenhaLink);
    menu.appendChild(alterarSenhaItem);

    const logoutItem = document.createElement("li");
    const logoutLink = document.createElement("a");
    logoutLink.className = "dropdown-item d-flex align-items-center gap-2 text-danger";
    logoutLink.href = "/app/usuario/logout/";
    const logoutIcon = document.createElement("i");
    logoutIcon.className = "bi bi-box-arrow-right";
    logoutLink.appendChild(logoutIcon);
    logoutLink.appendChild(document.createTextNode(" Logout"));
    logoutItem.appendChild(logoutLink);
    menu.appendChild(logoutItem);

    dropdown.appendChild(toggle);
    dropdown.appendChild(menu);
    containerFluid.appendChild(dropdown);

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