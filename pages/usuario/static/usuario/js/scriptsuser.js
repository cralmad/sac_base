import { updateFormField, getForm, updateState } from "/static/js/sisVar.js";
import { initSmartInputs } from "/static/js/input_rules.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";
import { AppLoader } from "/static/js/loader.js";

const nomeForm = "cadUsuario";
const nomeFormCons = "consUsuario";
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
    const divPrincipal = document.getElementById(nomeForm);
    const divPesquisa = document.getElementById('div-pesquisa');
    const btnAbrirPesquisa = document.getElementById('btn-abrir-pesquisa');
    const btnVoltar = document.getElementById('btn-voltar');
    const btnFechar = document.getElementById('btn-fechar');
    const formFiltro = document.getElementById(nomeFormCons);
    const tabelaCorpo = document.getElementById('tabela-corpo');

    // Utilitário para alternar visualização usando classes do Bootstrap
    const alternarTelas = () => {
        divPrincipal.classList.toggle('d-none');
        divPesquisa.classList.toggle('d-none');
    };

    // Event Listeners para Navegação
    btnAbrirPesquisa.addEventListener('click', alternarTelas);
    btnVoltar.addEventListener('click', alternarTelas);
    btnFechar.addEventListener('click', alternarTelas);

    // Lógica de Busca (POST conforme diretriz 3.2)
    formFiltro.addEventListener('submit', async (e) => {
        e.preventDefault();

        const sisVarPayload = {
            form: {
            [nomeFormCons]: getForm(nomeFormCons)
            }
        };

        try {
            const res = await fetch("/app/usuario/cadastro/cons", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
            },
            body: JSON.stringify(sisVarPayload)
            });

            const data = await res.json();
            renderizarTabela(data.registros);
            AppLoader.hide(); // LIBERA A TELA

        } catch (err) {
            console.error("Erro na requisição:", err);
            AppLoader.hide(); // LIBERA A TELA
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
            const response = await fetch("/app/usuario/cadastro/cons/", {
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