import { confirmar, getCsrfToken } from "/static/js/sisVar.js";

const root = document.getElementById("rel-av-root");
if (!root) {
  // Tela sem container (fallback seguro)
} else {
  const urlLote = root.dataset.urlLote || "";
  const btnEnviar = document.getElementById("btn-enviar-selecionados");
  const chkTodos = document.getElementById("chk-todos-avaliacao");
  const msg = document.getElementById("rel-av-msg");

  const getChecks = () => Array.from(document.querySelectorAll(".chk-avaliacao"));
  const getSelecionados = () => getChecks().filter((c) => c.checked);

  const renderMsg = (tipo, texto) => {
    if (!msg) return;
    const klass = tipo === "erro" ? "danger" : tipo === "sucesso" ? "success" : "warning";
    msg.innerHTML = `<div class="alert alert-${klass} py-2 mb-0">${texto}</div>`;
  };

  const syncBtn = () => {
    if (!btnEnviar) return;
    btnEnviar.disabled = getSelecionados().length === 0;
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

  async function enviarSelecionados(selecionados) {
    btnEnviar.disabled = true;
    renderMsg("aviso", "Enviando e-mails selecionados...");
    try {
      const resp = await fetch(urlLote, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ ids: selecionados }),
      });
      const json = await resp.json();
      if (!resp.ok || !json.success) {
        renderMsg("erro", json.mensagem || "Falha ao enviar e-mails.");
        btnEnviar.disabled = false;
        return;
      }
      renderMsg("sucesso", json.mensagem || "Envio em lote concluído.");
      window.location.reload();
    } catch (err) {
      renderMsg("erro", "Erro de comunicação ao disparar envio em lote.");
      btnEnviar.disabled = false;
    }
  }

  if (btnEnviar) {
    btnEnviar.addEventListener("click", () => {
      const selecionados = getSelecionados().map((c) => Number(c.value));
      if (!selecionados.length) {
        renderMsg("aviso", "Selecione pelo menos uma avaliação.");
        return;
      }

      confirmar({
        titulo: "Confirmar envio",
        mensagem: `Deseja enviar e-mail para ${selecionados.length} avaliação(ões) selecionada(s)?`,
        onConfirmar: () => {
          enviarSelecionados(selecionados);
        },
      });
    });
  }

  syncBtn();
  syncChkTodos();
}
