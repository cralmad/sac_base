/**
 * Painel de diagnóstico: iframe embed + probes (same-origin, CORS, headers servidor).
 */
import { getCsrfToken } from "/static/js/sisVar.js";
import {
  parseReferenciasTexto,
  buildScriptConsoleSelecionarRefs,
  buildBookmarkletSelecionarRefs,
} from "/static/js/enovo_selecionar_refs.js";

const root = document.getElementById("iet-root");
if (root) {
  const elUrl = document.getElementById("iet-url");
  const elIframe = document.getElementById("iet-iframe");
  const elLog = document.getElementById("iet-log");
  const elEstado = document.getElementById("iet-estado");
  const elCount = document.getElementById("iet-log-count");
  const urlProbe = root.dataset.urlProbe || "";

  let logCount = 0;
  let loadTimer = null;

  function setEstado(texto, tipo) {
    if (!elEstado) return;
    elEstado.textContent = texto;
    elEstado.className = "badge iet-badge-estado";
    const map = {
      ok: "text-bg-success",
      warn: "text-bg-warning",
      err: "text-bg-danger",
      info: "text-bg-primary",
    };
    elEstado.classList.add(map[tipo] || "text-bg-secondary");
  }

  function log(nivel, msg, detalhe) {
    if (!elLog) return;
    const ts = new Date().toISOString().slice(11, 23);
    const line = document.createElement("div");
    line.className = "iet-" + (nivel || "info");
    let texto = "[" + ts + "] [" + (nivel || "info").toUpperCase() + "] " + msg;
    if (detalhe !== undefined) {
      try {
        texto +=
          "\n" +
          (typeof detalhe === "string" ? detalhe : JSON.stringify(detalhe, null, 2));
      } catch (_e) {
        texto += "\n" + String(detalhe);
      }
    }
    line.textContent = texto;
    elLog.appendChild(line);
    elLog.scrollTop = elLog.scrollHeight;
    logCount += 1;
    if (elCount) elCount.textContent = String(logCount);
  }

  const SANDBOX_DEFAULT =
    "allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox";
  const elSemSandbox = document.getElementById("iet-sem-sandbox");

  function urlAtual() {
    return (elUrl && elUrl.value ? elUrl.value : "").trim();
  }

  function aplicarSandbox() {
    if (!elIframe) return;
    const sem = elSemSandbox && elSemSandbox.checked;
    if (sem) {
      elIframe.removeAttribute("sandbox");
      log("warn", "sandbox removido do iframe (reteste login).");
    } else {
      elIframe.setAttribute("sandbox", SANDBOX_DEFAULT);
      log("info", "sandbox reaplicado", SANDBOX_DEFAULT);
    }
  }

  function carregarIframe(url) {
    if (!elIframe) return;
    if (!url) {
      log("err", "URL vazia.");
      return;
    }
    aplicarSandbox();
    setEstado("a carregar…", "info");
    log("info", "A definir iframe.src", url);
    log(
      "warn",
      "Se o login “piscar” e em nova aba funcionar: cookie de sessão third-party bloqueado no iframe — embed autenticado inviável neste browser."
    );
    if (loadTimer) clearTimeout(loadTimer);
    loadTimer = setTimeout(function () {
      log(
        "warn",
        "Ainda sem evento load após 8s — pode ser bloqueio de framing, rede lenta ou página a falhar em silêncio."
      );
      setEstado("timeout parcial", "warn");
    }, 8000);
    elIframe.src = url;
  }

  elIframe.addEventListener("load", function () {
    if (loadTimer) clearTimeout(loadTimer);
    const src = elIframe.getAttribute("src") || "";
    if (!src || src === "about:blank") {
      setEstado("blank", "info");
      log("info", "iframe load → about:blank");
      return;
    }
    setEstado("load disparado", "ok");
    log(
      "ok",
      "Evento load do iframe. Isto NÃO prova que o conteúdo externo é visível (pode ser página de erro do browser)."
    );
    testarSameOrigin(false);
  });

  elIframe.addEventListener("error", function () {
    setEstado("error", "err");
    log("err", "Evento error no iframe.");
  });

  window.addEventListener("message", function (ev) {
    log("info", "postMessage recebido", {
      origin: ev.origin,
      data: ev.data,
    });
  });

  function testarSameOrigin(verbose) {
    if (!elIframe) return;
    try {
      const doc = elIframe.contentDocument;
      const loc = elIframe.contentWindow && elIframe.contentWindow.location.href;
      log("warn", "Acesso same-origin SURPREENDENTEMENTE permitido", {
        location: loc,
        title: doc && doc.title,
      });
      setEstado("same-origin OK (!)", "warn");
    } catch (e) {
      log("ok", "Same-origin bloqueado (esperado cross-origin)", {
        name: e && e.name,
        message: e && e.message,
      });
      if (verbose !== false) setEstado("cross-origin", "ok");
    }
  }

  async function probeServidor() {
    const url = urlAtual();
    if (!url) {
      log("err", "URL vazia para probe.");
      return;
    }
    log("info", "Probe headers via servidor…", url);
    setEstado("probe…", "info");
    try {
      const resp = await fetch(urlProbe, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ url: url }),
      });
      const data = await resp.json().catch(function () {
        return null;
      });
      if (!resp.ok || !data || !data.success) {
        log("err", "Probe falhou", data || { status: resp.status });
        setEstado("probe erro", "err");
        return;
      }
      log("ok", "Probe OK", data.resultado);
      const ver = data.resultado && data.resultado.interpretacao;
      if (ver) {
        log(
          ver.veredicto === "sem_bloqueio_explicito" ? "ok" : "warn",
          "Interpretação: " + ver.veredicto,
          ver
        );
      }
      setEstado("probe ok", "ok");
    } catch (e) {
      log("err", "Probe rede/JS", { message: e && e.message });
      setEstado("probe erro", "err");
    }
  }

  async function fetchCorsBrowser() {
    const url = urlAtual();
    if (!url) {
      log("err", "URL vazia.");
      return;
    }
    log("info", "Fetch no browser (espera falha CORS)…", url);
    try {
      const resp = await fetch(url, { method: "GET", mode: "cors", credentials: "omit" });
      log("warn", "Fetch CORS inesperadamente OK", { status: resp.status });
    } catch (e) {
      log("ok", "Fetch CORS bloqueado/falhou (típico)", {
        name: e && e.name,
        message: e && e.message,
      });
    }
  }

  elSemSandbox?.addEventListener("change", function () {
    aplicarSandbox();
    log(
      "info",
      "Altere a opção e volte a Carregar no iframe para retestar o login com a nova config de sandbox."
    );
  });

  document.getElementById("iet-btn-carregar")?.addEventListener("click", function () {
    carregarIframe(urlAtual());
  });
  document.getElementById("iet-btn-reload")?.addEventListener("click", function () {
    if (!elIframe) return;
    log("info", "iframe.contentWindow.location.reload() / src reload");
    try {
      elIframe.contentWindow.location.reload();
    } catch (_e) {
      elIframe.src = urlAtual() || elIframe.src;
    }
  });
  document.getElementById("iet-btn-blank")?.addEventListener("click", function () {
    if (!elIframe) return;
    elIframe.src = "about:blank";
    setEstado("blank", "info");
    log("info", "iframe → about:blank");
  });
  document.getElementById("iet-btn-nova-aba")?.addEventListener("click", function () {
    const u = urlAtual();
    if (!u) return;
    window.open(u, "_blank", "noopener,noreferrer");
    log("info", "Aberta nova aba", u);
  });
  document.getElementById("iet-btn-probe")?.addEventListener("click", function () {
    probeServidor();
  });
  document.getElementById("iet-btn-same-origin")?.addEventListener("click", function () {
    testarSameOrigin(true);
  });
  document.getElementById("iet-btn-fetch-browser")?.addEventListener("click", function () {
    fetchCorsBrowser();
  });
  document.getElementById("iet-btn-limpar-log")?.addEventListener("click", function () {
    if (elLog) elLog.textContent = "";
    logCount = 0;
    if (elCount) elCount.textContent = "0";
  });

  // ── Alternativa: bookmarklet / console na aba autenticada do TMS ───
  const elTrks = document.getElementById("iet-trks");
  const elBmLink = document.getElementById("iet-bm-link");
  const elTrksCount = document.getElementById("iet-trks-count");
  const elBmStatus = document.getElementById("iet-bm-status");

  function atualizarBookmarklet() {
    const ids = parseReferenciasTexto(elTrks && elTrks.value);
    if (elTrksCount) elTrksCount.textContent = ids.length + " item(ns)";
    if (!elBmLink) return;
    if (!ids.length) {
      elBmLink.setAttribute("href", "#");
      if (elBmStatus) {
        elBmStatus.textContent =
          "Cole referências no formato Rotas por Carro (ref1, ref2, …) e atualize.";
      }
      log("warn", "Bookmarklet sem itens.");
      return;
    }
    elBmLink.setAttribute("href", buildBookmarkletSelecionarRefs(ids));
    if (elBmStatus) {
      elBmStatus.textContent =
        "Pronto com " +
        ids.length +
        " item(ns). Preferível: Copiar código console. Opcional: arrastar favorito.";
    }
    log("ok", "Bookmarklet atualizado", { itens: ids.length, amostra: ids.slice(0, 5) });
  }

  document.getElementById("iet-btn-bm-atualizar")?.addEventListener("click", function () {
    atualizarBookmarklet();
  });
  document.getElementById("iet-btn-console-copiar")?.addEventListener("click", async function () {
    const ids = parseReferenciasTexto(elTrks && elTrks.value);
    if (!ids.length) {
      log("warn", "Cole referências antes de copiar o código do console.");
      return;
    }
    atualizarBookmarklet();
    try {
      await navigator.clipboard.writeText(buildScriptConsoleSelecionarRefs(ids));
      log("ok", "Código console copiado", { n: ids.length });
      if (elBmStatus) {
        elBmStatus.textContent =
          "Código copiado. No eNovoTMS: F12 → Console → allow pasting → colar → Enter.";
      }
    } catch (_e) {
      log("err", "Não foi possível copiar o código para a área de transferência.");
    }
  });
  document.getElementById("iet-btn-trks-copiar")?.addEventListener("click", async function () {
    const ids = parseReferenciasTexto(elTrks && elTrks.value);
    const texto = ids.join(", ");
    try {
      await navigator.clipboard.writeText(texto);
      log("ok", "Lista copiada (ref1, ref2, …)", { n: ids.length });
    } catch (_e) {
      log("err", "Não foi possível copiar para a área de transferência.");
    }
  });
  document.getElementById("iet-btn-trks-colar")?.addEventListener("click", async function () {
    try {
      const texto = await navigator.clipboard.readText();
      if (elTrks) elTrks.value = texto;
      atualizarBookmarklet();
      log("ok", "Colado da área de transferência.", {
        itens: parseReferenciasTexto(texto).length,
      });
    } catch (_e) {
      log("err", "Permissão de colar recusada pelo browser.");
    }
  });
  elTrks?.addEventListener("change", atualizarBookmarklet);
  elTrks?.addEventListener("input", function () {
    const ids = parseReferenciasTexto(elTrks.value);
    if (elTrksCount) elTrksCount.textContent = ids.length + " item(ns)";
  });
  elBmLink?.addEventListener("click", function (ev) {
    if ((elBmLink.getAttribute("href") || "#") === "#") {
      ev.preventDefault();
      log("warn", "Atualize o bookmarklet com Referências antes de usar.");
    }
  });

  log(
    "info",
    "Página de teste pronta. Sintoma 'login pisca no iframe / OK em nova aba' = cookies third-party."
  );
  log(
    "info",
    "Rotas por Carro: botão </> copia o script console com as referências do grupo."
  );
  log(
    "info",
    "CSP desta página inclui frame-src para a origem do alvo (ver cabeçalho da resposta HTML)."
  );
  log("info", "URL inicial", root.dataset.urlInicial || "");
  atualizarBookmarklet();
}
