import { updateFormField, getForm, getMesangens } from "/static/js/sisVar.js";
import { initSmartInputs } from "/static/js/input_rules.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";
import { AppLoader } from "/static/js/loader.js";

const form = document.getElementById("alterarSenhaForm");

const updater = criarAtualizadorForm({
  formId: "alterarSenhaForm",
  setter: updateFormField,
  form
});

form.addEventListener("input", updater);

initSmartInputs((input, value) => {
    updateFormField("alterarSenhaForm", input.name, value);
});

form.addEventListener("submit", async e => {
  e.preventDefault();

  // O AppLoader.show() já foi disparado automaticamente pelo 'submit' 
  // se o botão ou o form tiverem a classe "show-loader".

  const sisVarPayload = {
    form: {
      alterarSenhaForm: getForm("alterarSenhaForm")
    }
  };

  try {
    const res = await fetch("/app/usuario/alterarsenha/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
      },
      body: JSON.stringify(sisVarPayload)
    });

    const data = await res.json();

    if (data.success) {
      // O redirecionamento mata a página atual, então o loader some sozinho
      getMesangens(data.mensagens);
      AppLoader.hide(); // LIBERA A TELA para o usuário tentar novamente
    } else {
      // Erro de credenciais ou validação
      getMesangens(data.mensagens);
      AppLoader.hide(); // LIBERA A TELA para o usuário tentar novamente
    }
  } catch (err) {
    // Erro de rede ou servidor fora do ar
    getMesangens(data.mensagens);
    AppLoader.hide(); // LIBERA A TELA em caso de falha técnica
  }
});