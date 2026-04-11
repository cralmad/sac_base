import { getDataset, getForm, updateFormField, updateState } from "/static/js/sisVar.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";
import { AppLoader } from "/static/js/loader.js";

const form = document.getElementById("selecionarFilialForm");
const select = document.getElementById("filial_id");

function preencherOpcoes() {
  const filiais = getDataset("availableFiliais", []);

  filiais.forEach(filial => {
    const option = document.createElement("option");
    option.value = String(filial.id);
    option.textContent = filial.isMatriz ? `${filial.nome} (Matriz)` : filial.nome;
    select.appendChild(option);
  });
}

const updater = criarAtualizadorForm({
  formId: "selecionarFilialForm",
  setter: updateFormField,
  form,
});

form.addEventListener("input", updater);

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    form: {
      selecionarFilialForm: getForm("selecionarFilialForm"),
    },
  };

  try {
    const response = await fetch("/app/usuario/filial/ativar/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")?.value || "",
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    if (data.success && data.redirect) {
      window.location.href = data.redirect;
      return;
    }

    updateState(data);
    AppLoader.hide();
  } catch (error) {
    console.error("Erro ao ativar matriz/filial:", error);
    AppLoader.hide();
  }
});

document.addEventListener("DOMContentLoaded", () => {
  preencherOpcoes();
});
