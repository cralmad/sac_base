import { 
  getDataBackEnd, 
  getUsuario, 
  renderMensagens,
  getCsrfToken 
} from "/static/js/sisVar.js";

import { AppLoader } from "/static/js/loader.js"; // ✅ ADICIONAR IMPORT

/**
 * Função utilitária para fazer requisições POST com CSRF token
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

// ✅ Inicializa AppLoader E navbar quando DOM está pronto
// AGUARDA a navbar terminar (async) antes de ocultar o loader
document.addEventListener("DOMContentLoaded", async () => {
    AppLoader.init();
    await inicializarNavbarUsuario(); // ← await garante esperar a chamada de rede
    AppLoader.hide();                 // ← só oculta após tudo carregar
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