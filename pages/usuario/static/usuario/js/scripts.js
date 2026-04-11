import { updateFormField, getForm, updateState } from "/static/js/sisVar.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";
import { AppLoader } from "/static/js/loader.js";

const form = document.getElementById("loginForm");

const updater = criarAtualizadorForm({
  formId: "loginForm",
  setter: updateFormField,
  form
});

form.addEventListener("input", updater);

form.addEventListener("submit", async e => {
  e.preventDefault();

  // O AppLoader.show() já foi disparado automaticamente pelo 'submit' 
  // se o botão ou o form tiverem a classe "show-loader".

  const sisVarPayload = {
    form: {
      loginForm: getForm("loginForm")
    }
  };

  try {
    const res = await fetch("/app/usuario/login/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")?.value
      },
      body: JSON.stringify(sisVarPayload)
    });

    const data = await res.json();

    if (data.success) {
      // O redirecionamento mata a página atual, então o loader some sozinho
      window.location.href = data.redirect || "/app/home/";
    } else {
      // Erro de credenciais ou validação
      updateState(data);
      AppLoader.hide(); // LIBERA A TELA para o usuário tentar novamente
    }
  } catch (err) {
    // Erro de rede ou servidor fora do ar
    alert("Erro na requisição:", err);
    AppLoader.hide(); // LIBERA A TELA em caso de falha técnica
  }
});
