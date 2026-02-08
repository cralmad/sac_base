import { updateFormField, getForm, updateState } from "/static/js/sisVar.js";
import { initSmartInputs } from "/static/js/input_rules.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";
import { AppLoader } from "/static/js/loader.js";

const nomeForm = "cadUsuario";
const form = document.getElementById(nomeForm);

const updater = criarAtualizadorForm({
  formId: nomeForm,
  setter: updateFormField,
  form
});

form.addEventListener("input", updater);

initSmartInputs((input, value) => {
    updateFormField(nomeForm, input.name, value);
});

form.addEventListener("submit", async e => {
  e.preventDefault();

  // O AppLoader.show() já foi disparado automaticamente pelo 'submit' 
  // se o botão ou o form tiverem a classe "show-loader".

  const sisVarPayload = {
    form: {
      [nomeForm]: getForm(nomeForm)
    }
  };

  try {
    const res = await fetch("/app/usuario/cadastro/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
      },
      body: JSON.stringify(sisVarPayload)
    });

    const data = await res.json();
    updateState(data);
    AppLoader.hide(); // LIBERA A TELA

  } catch (err) {
    console.error("Erro na requisição:", err);
    AppLoader.hide(); // LIBERA A TELA
  }
});

document.addEventListener('DOMContentLoaded', () => {
    // Seletores de Elementos
    const divPrincipal = document.getElementById('cadUsuario');
    const divPesquisa = document.getElementById('div-pesquisa');
    const btnAbrirPesquisa = document.getElementById('btn-abrir-pesquisa');
    const btnVoltarPrincipal = document.getElementById('btn-voltar-principal');
    const formFiltro = document.getElementById('consUsuario');
    const tabelaCorpo = document.getElementById('tabela-corpo');

    // Utilitário para alternar visualização usando classes do Bootstrap
    const alternarTelas = () => {
        divPrincipal.classList.toggle('d-none');
        divPesquisa.classList.toggle('d-none');
    };

    // Event Listeners para Navegação
    btnAbrirPesquisa.addEventListener('click', alternarTelas);
    btnVoltarPrincipal.addEventListener('click', alternarTelas);

    // Lógica de Busca (POST conforme diretriz 3.2)
    formFiltro.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (typeof loader !== 'undefined') loader.show();

        const payload = {
            nome_filtro: document.getElementById('filtro_nome').value,
            user_filtro: document.getElementById('filtro_user').value
        };

        try {
            const response = await fetch('/usuario/pesquisa/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            renderizarTabela(data.registros);
        } catch (error) {
            console.error('Erro na busca:', error);
        } finally {
            if (typeof loader !== 'undefined') loader.hide();
        }
    });

    // Renderização com Event Delegation (Evita múltiplos listeners)
    function renderizarTabela(registros) {
        tabelaCorpo.innerHTML = registros.map(reg => `
            <tr>
                <td>${reg.id}</td>
                <td>${reg.nome}</td>
                <td>${reg.username}</td>
                <td class="text-center">
                    <button class="btn btn-sm btn-info btn-selecionar" data-id="${reg.id}">
                        Selecionar
                    </button>
                </td>
            </tr>
        `).join('');
    }

    // Captura o clique no botão selecionar (Dinâmico)
    tabelaCorpo.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-selecionar')) {
            const id = e.target.getAttribute('data-id');
            await carregarRegistro(id);
        }
    });

    async function carregarRegistro(id) {
        if (typeof loader !== 'undefined') loader.show();

        try {
            const response = await fetch('/usuario/pesquisa/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ id_selecionado: id })
            });

            const res = await response.json();

            if (res.estado === "visualizar") {
                document.getElementById('id_nome').value = res.dados.nome;
                
                // Aplica regras do input_rules.js se disponível
                if (window.inputRules) window.inputRules.applyAll();

                alternarTelas(); // Volta ao form principal
            }
        } finally {
            if (typeof loader !== 'undefined') loader.hide();
        }
    }
});