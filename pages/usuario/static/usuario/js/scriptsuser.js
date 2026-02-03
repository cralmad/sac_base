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