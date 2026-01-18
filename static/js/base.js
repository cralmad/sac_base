import { getDataBackEnd, getUsuario } from "/static/js/sisVar.js";

export async function inicializarNavbarUsuario() {
    try {
        // Garante que os dados do backend foram carregados
        await getDataBackEnd();

        const usuario = getUsuario();

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
                        <a class="dropdown-item" href="/alterar-senha">
                            Alterar senha
                        </a>
                    </li>
                    <li>
                        <a class="dropdown-item" href="/logout">
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
