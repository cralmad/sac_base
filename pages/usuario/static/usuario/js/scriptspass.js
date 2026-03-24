import { updateFormField, getForm, definirMensagem, updateState, clearMessages, hidratarFormulario, getCsrfToken } from "/static/js/sisVar.js";
import { initSmartInputs } from "/static/js/input_rules.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";
import { AppLoader } from "/static/js/loader.js";

const FORM_ID = "alterarSenhaForm";
const form = document.getElementById(FORM_ID);

// ── Vínculo sisVar ↔ inputs ────────────────────────────────────────────────
const updater = criarAtualizadorForm({ formId: FORM_ID, setter: updateFormField, form });
form.addEventListener("input", updater);

initSmartInputs((input, value) => {
  updateFormField(FORM_ID, input.name, value);
});

// ── Submit ─────────────────────────────────────────────────────────────────
form.addEventListener("submit", async e => {
  e.preventDefault();

  // Limpa mensagens anteriores antes de qualquer nova requisição
  clearMessages();

  const campos = getForm(FORM_ID);

  // Validação básica no front
  if (!campos?.campos?.senha_atual || !campos?.campos?.nova_senha || !campos?.campos?.confirmar_senha) {
    definirMensagem("aviso", ["Todos os campos são obrigatórios"], true);
    return;
  }

  AppLoader.show();

  try {
    const res = await fetch("/app/usuario/alterarsenha/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken()
      },
      body: JSON.stringify({ form: { [FORM_ID]: campos } })
    });

    const data = await res.json();

    // Atualiza sisVar (mensagens + estado)
    updateState(data);

    // Limpa os campos do formulário somente em caso de sucesso
    if (res.ok && data.success) {
      hidratarFormulario(FORM_ID);
    }

  } catch (err) {
    console.error("Erro ao alterar senha:", err);
    definirMensagem("erro", ["Erro ao conectar ao servidor. Tente novamente."], false);
  } finally {
    AppLoader.hide();
  }
});