import { updateFormField, getForm, definirMensagem, updateState, getCsrfToken } from "/static/js/sisVar.js";
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

  const campos = getForm("alterarSenhaForm");
  
  // Validação básica
  if (!campos || !campos.campos || !campos.campos.senha_atual || !campos.campos.nova_senha || !campos.campos.confirmar_senha) {
    definirMensagem("aviso", ["Todos os campos são obrigatórios"], true);
    return; // NÃO mostra loader se validação falhar
  }

  const sisVarPayload = {
    form: {
      alterarSenhaForm: campos
    }
  };

  // MOSTRA LOADER ANTES DE FAZER REQUEST
  AppLoader.show();

  try {
    const res = await fetch("/app/usuario/alterarsenha/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken()
      },
      body: JSON.stringify(sisVarPayload)
    });

    const data = await res.json();

    // Atualiza estado com mensagens
    if (data.mensagens) {
      updateState(data);
    }

    // ✅ SEMPRE ESCONDE O LOADER
    AppLoader.hide();

    if (res.ok && data.success) {
      console.log("✅ Senha alterada com sucesso!");
      // Opcional: redirecionar após sucesso
      // setTimeout(() => window.location.href = "/", 2000);
    } else {
      console.log("❌ Erro na operação");
    }
  } catch (err) {
    console.error("❌ Erro ao alterar senha:", err);
    definirMensagem("erro", ["Erro ao conectar ao servidor. Tente novamente."], false);
    
    // ✅ SEMPRE ESCONDE O LOADER MESMO EM ERRO
    AppLoader.hide();
  }
});