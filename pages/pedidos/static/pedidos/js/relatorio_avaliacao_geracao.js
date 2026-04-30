import { confirmar, getCsrfToken } from "/static/js/sisVar.js";
import { AppLoader } from "/static/js/loader.js";

const root = document.getElementById("rel-av-ger-root");
if (root) {
  const urlGeracao = root.dataset.urlGeracao || "";
  const btnGerar = document.getElementById("btn-gerar-fila");
  const chkTodos = document.getElementById("chk-todos-geracao");
  const msg = document.getElementById("rel-av-ger-msg");

  const getChecks = () => Array.from(document.querySelectorAll(".chk-pedido-geracao:not(:disabled)"));
  const getSelecionados = () => getChecks().filter((c) => c.checked);

  const renderMsg = (tipo, texto) => {
    if (!msg) return;
    const klass = tipo === "erro" ? "danger" : tipo === "sucesso" ? "success" : "warning";
    msg.innerHTML = `<div class="alert alert-${klass} py-2 mb-0">${texto}</div>`;
  };

  const showBusy = () => {
    AppLoader.show();
    const loaderEl = document.getElementById("global-loader");
    if (loaderEl) loaderEl.classList.remove("d-none");
  };

  const hideBusy = () => {
    AppLoader.hide();
    const loaderEl = document.getElementById("global-loader");
    if (loaderEl) loaderEl.classList.add("d-none");
  };

  const syncUI = () => {
    const checks = getChecks();
    const marcados = getSelecionados();
    if (btnGerar) btnGerar.disabled = marcados.length === 0;
    if (chkTodos) {
      chkTodos.checked = checks.length > 0 && marcados.length === checks.length;
      chkTodos.indeterminate = marcados.length > 0 && marcados.length < checks.length;
    }
  };

  getChecks().forEach((c) => c.addEventListener("change", syncUI));
  if (chkTodos) {
    chkTodos.addEventListener("change", () => {
      getChecks().forEach((c) => {
        c.checked = chkTodos.checked;
      });
      syncUI();
    });
  }

  if (btnGerar) {
    btnGerar.addEventListener("click", () => {
      const ids = getSelecionados().map((c) => Number(c.value));
      if (!ids.length) {
        renderMsg("aviso", "Selecione pelo menos um pedido.");
        return;
      }
      confirmar({
        titulo: "Confirmar geração da fila",
        mensagem: `Deseja gerar fila para ${ids.length} pedido(s) selecionado(s)?`,
        onConfirmar: async () => {
          btnGerar.disabled = true;
          renderMsg("aviso", "Gerando fila de avaliações...");
          showBusy();
          try {
            const resp = await fetch(urlGeracao, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
              },
              body: JSON.stringify({ ids }),
            });
            const json = await resp.json();
            if (!resp.ok || !json.success) {
              renderMsg("erro", json.mensagem || "Falha ao gerar fila.");
              syncUI();
              return;
            }
            renderMsg("sucesso", json.mensagem || "Fila gerada com sucesso.");
            window.location.reload();
          } catch {
            renderMsg("erro", "Erro de comunicação ao gerar fila.");
            syncUI();
          } finally {
            hideBusy();
          }
        },
      });
    });
  }

  syncUI();
}
