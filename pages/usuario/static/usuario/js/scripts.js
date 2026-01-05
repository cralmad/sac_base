import { updateFormField, getForm, getDataBackEnd } from "/static/js/sisVar.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";

const form = document.getElementById("loginForm");
getDataBackEnd();

const updater = criarAtualizadorForm({
  formId: "loginForm",
  setter: updateFormField,
  form
});

form.addEventListener("input", updater);

form.addEventListener("submit", async e => {
  e.preventDefault();

  const sisVarPayload = {
    form: {
      loginForm: getForm("loginForm")
    }
  };

  const res = await fetch("/app/usuario/login/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
    },
    body: JSON.stringify(sisVarPayload)
  });

  const data = await res.json();

  if (data.success) {
    window.location.href = "/app/cad/cliente/";
  } else {
    console.log(data.error);
  }
});

/*****************DEBUG**********************/
import { __debugState } from '../../js/sisVar.js';

window.__DEBUG__ = {
  get state() {
    return __debugState();
  }
};

function exibir() {
  console.log(window.__DEBUG__.state);
}

document.getElementById('teste').addEventListener('click', exibir);