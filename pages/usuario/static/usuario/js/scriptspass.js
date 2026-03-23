// pages/usuario/static/usuario/js/scriptspass.js - VERSÃO CORRIGIDA

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
  
  // VALIDAÇÃO FRONTEND (Opcional mas recomendado)
  if (!campos.campos.senha_atual || !campos.campos.nova_senha || !campos.campos.confirmar_senha) {
    definirMensagem("aviso", ["Todos os campos são obrigatórios"], true);
    AppLoader.hide();
    return;
  }

  const sisVarPayload = {
    form: {
      alterarSenhaForm: campos
    }
  };

  try {
    const res = await fetch("/app/usuario/alterarsenha/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken() // ✅ CORRIGIDO
      },
      body: JSON.stringify(sisVarPayload)
    });

    const data = await res.json();

    // ✅ CORRIGIDO: Atualiza estado completo via sisVar
    if (data.mensagens) {
      updateState(data);
    }

    if (res.ok && data.success) {
      AppLoader.hide();
      // Opcional: Redirecionar ou recarregar após sucesso
      // setTimeout(() => window.location.reload(), 1500);
    } else {
      AppLoader.hide();
    }
  } catch (err) {
    console.error("Erro ao alterar senha:", err);
    definirMensagem("erro", ["Erro ao conectar ao servidor. Tente novamente."], false);
    AppLoader.hide();
  }
});