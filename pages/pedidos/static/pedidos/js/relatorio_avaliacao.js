import { confirmar, getCsrfToken } from "/static/js/sisVar.js";
import { AppLoader } from "/static/js/loader.js";

const root = document.getElementById("rel-av-root");
if (!root) {
  // Tela sem container (fallback seguro)
} else {
  const urlLote = root.dataset.urlLote || "";
  const btnEnviar = document.getElementById("btn-enviar-selecionados");
  const chkTodos = document.getElementById("chk-todos-avaliacao");
  const chkEmail = document.getElementById("chk-canal-email");
  const chkSms = document.getElementById("chk-canal-sms");
  const msg = document.getElementById("rel-av-msg");

  const getChecks = () => Array.from(document.querySelectorAll(".chk-avaliacao"));
  const getSelecionados = () => getChecks().filter((c) => c.checked);

  const canaisSelecionados = () => {
    const canais = [];
    if (chkEmail && chkEmail.checked) canais.push("email");
    if (chkSms && chkSms.checked) canais.push("sms");
    return canais;
  };

  const labelCanais = (canais) => {
    const map = { email: "E-mail", sms: "SMS" };
    return canais.map((c) => map[c] || c).join(" e ");
  };

  const renderMsg = (tipo, texto) => {
    if (!msg) return;
    const klass = tipo === "erro" ? "danger" : tipo === "sucesso" ? "success" : "warning";
    msg.innerHTML = `<div class="alert alert-${klass} py-2 mb-0"></div>`;
    msg.querySelector(".alert").textContent = texto;
  };

  const syncBtn = () => {
    if (!btnEnviar) return;
    btnEnviar.disabled = getSelecionados().length === 0 || canaisSelecionados().length === 0;
  };

  const syncChkTodos = () => {
    if (!chkTodos) return;
    const checks = getChecks();
    if (!checks.length) {
      chkTodos.checked = false;
      chkTodos.indeterminate = false;
      return;
    }
    const marcados = checks.filter((c) => c.checked);
    chkTodos.checked = marcados.length === checks.length;
    chkTodos.indeterminate = marcados.length > 0 && marcados.length < checks.length;
  };

  getChecks().forEach((c) => {
    c.addEventListener("change", () => {
      syncBtn();
      syncChkTodos();
    });
  });

  if (chkTodos) {
    chkTodos.addEventListener("change", () => {
      getChecks().forEach((c) => {
        c.checked = chkTodos.checked;
      });
      syncBtn();
      syncChkTodos();
    });
  }

  [chkEmail, chkSms].forEach((el) => {
    if (el) el.addEventListener("change", syncBtn);
  });

  async function enviarSelecionados(selecionados, canais) {
    btnEnviar.disabled = true;
    renderMsg("aviso", `Enviando (${labelCanais(canais)})...`);
    AppLoader.show();
    try {
      const resp = await fetch(urlLote, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ ids: selecionados, canais }),
      });
      const json = await resp.json();
      if (!resp.ok || !json.success) {
        renderMsg("erro", json.mensagem || "Falha ao enviar.");
        btnEnviar.disabled = false;
        return;
      }
      renderMsg("sucesso", json.mensagem || "Envio em lote concluído.");
      window.location.reload();
    } catch (err) {
      renderMsg("erro", "Erro de comunicação ao disparar envio em lote.");
      btnEnviar.disabled = false;
    } finally {
      AppLoader.hide();
    }
  }

  if (btnEnviar) {
    btnEnviar.addEventListener("click", () => {
      const selecionados = getSelecionados().map((c) => Number(c.value));
      const canais = canaisSelecionados();
      if (!selecionados.length) {
        renderMsg("aviso", "Selecione pelo menos uma avaliação.");
        return;
      }
      if (!canais.length) {
        renderMsg("aviso", "Selecione pelo menos um canal (E-mail e/ou SMS).");
        return;
      }

      confirmar({
        titulo: "Confirmar envio",
        mensagem: `Deseja enviar ${labelCanais(canais)} para ${selecionados.length} avaliação(ões) selecionada(s)?`,
        onConfirmar: () => {
          enviarSelecionados(selecionados, canais);
        },
      });
    });
  }

  root.addEventListener("click", async (event) => {
    const btn = event.target.closest(".btn-enviar-canal");
    if (!btn) return;

    const url = btn.dataset.url || "";
    const canal = (btn.dataset.canal || "").trim().toLowerCase();
    const referencia = btn.dataset.referencia || "";
    const label = canal === "sms" ? "SMS" : "E-mail";

    confirmar({
      titulo: `Confirmar envio de ${label}`,
      mensagem: `Deseja enviar ${label} da avaliação do pedido ${referencia}?`,
      onConfirmar: async () => {
        btn.disabled = true;
        renderMsg("aviso", `Enviando ${label}...`);
        AppLoader.show();
        try {
          const resp = await fetch(url, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": getCsrfToken(),
            },
            body: JSON.stringify({ canal }),
          });
          const json = await resp.json();
          if (!resp.ok || !json.success) {
            renderMsg("erro", json.mensagem || `Falha ao enviar ${label}.`);
            btn.disabled = false;
            return;
          }
          renderMsg("sucesso", json.mensagem || `${label} enviado com sucesso.`);
          window.location.reload();
        } catch {
          renderMsg("erro", `Erro de comunicação ao enviar ${label}.`);
          btn.disabled = false;
        } finally {
          AppLoader.hide();
        }
      },
    });
  });

  syncBtn();
  syncChkTodos();
}
