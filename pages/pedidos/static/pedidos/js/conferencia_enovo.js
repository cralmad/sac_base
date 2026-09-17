import { confirmar } from "/static/js/sisVar.js";
import { fazerRequisicao } from "/static/js/base.js";
import { AppLoader } from "/static/js/loader.js";

const root = document.getElementById("ce-root");
if (!root) {
  // página sem root
} else {
  const URL_PREVIEW = root.dataset.urlPreview || "";
  const URL_SALVAR = root.dataset.urlSalvar || "";
  const ZXING_SRC = "https://cdn.jsdelivr.net/npm/@zxing/library@0.21.3/umd/index.min.js";

  const btnLer = document.getElementById("ce-btn-ler");
  const btnGravar = document.getElementById("ce-btn-gravar");
  const btnSeguinte = document.getElementById("ce-btn-seguinte");
  const btnFecharCam = document.getElementById("ce-btn-fechar-cam");
  const overlay = document.getElementById("ce-overlay");
  const video = document.getElementById("ce-video");
  const flash = document.getElementById("ce-flash");
  const loteBanner = document.getElementById("ce-lote-banner");
  const tbody = document.getElementById("ce-tbody");
  const scanHint = document.getElementById("ce-scan-hint");

  /** @type {Array<Record<string, unknown>>} */
  let lista = [];
  let stream = null;
  let detector = null;
  let zxingReader = null;
  let scanPausado = false;
  let rafId = 0;
  let processandoCodigo = false;

  function textoMensagem(payload, fallback) {
    const erro = payload?.mensagens?.erro?.conteudo;
    if (Array.isArray(erro) && erro[0]) return String(erro[0]);
    const ok = payload?.mensagens?.sucesso?.conteudo;
    if (Array.isArray(ok) && ok[0]) return String(ok[0]);
    return fallback;
  }

  function atualizarBotaoGravar() {
    btnGravar.disabled = lista.length === 0;
  }

  function renderLista() {
    tbody.replaceChildren();
    if (!lista.length) {
      const tr = document.createElement("tr");
      tr.id = "ce-vazio";
      const td = document.createElement("td");
      td.colSpan = 6;
      td.className = "text-center text-muted";
      td.textContent = "Nenhuma leitura na lista.";
      tr.appendChild(td);
      tbody.appendChild(tr);
      atualizarBotaoGravar();
      return;
    }
    lista.forEach((item, idx) => {
      const tr = document.createElement("tr");
      const cols = [
        item.trk,
        item.referencia || "—",
        `${item.volume} / ${item.total_volume}`,
        item.sem_carro ? "Sem carro" : item.carro,
        item.prev_entrega || "—",
      ];
      cols.forEach((val) => {
        const td = document.createElement("td");
        td.textContent = val == null ? "—" : String(val);
        tr.appendChild(td);
      });
      const tdBtn = document.createElement("td");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-sm btn-outline-danger";
      btn.textContent = "Remover";
      btn.addEventListener("click", () => {
        lista.splice(idx, 1);
        renderLista();
      });
      tdBtn.appendChild(btn);
      tr.appendChild(tdBtn);
      tbody.appendChild(tr);
    });
    atualizarBotaoGravar();
  }

  function mostrarFlash(ok, leitura, mensagemErro) {
    flash.classList.remove("d-none", "alert-success", "alert-danger");
    flash.replaceChildren();
    if (!ok) {
      flash.classList.add("alert-danger");
      const p = document.createElement("p");
      p.className = "mb-0 fw-semibold";
      p.textContent = mensagemErro || "Leitura recusada.";
      flash.appendChild(p);
      return;
    }
    flash.classList.add("alert-success");
    const carro = document.createElement("div");
    carro.id = "ce-flash-carro";
    carro.textContent = leitura.sem_carro ? "SEM CARRO" : `CARRO ${leitura.carro}`;
    const det = document.createElement("div");
    det.className = "mt-2";
    det.textContent = `TRK ${leitura.trk}  ·  vol. ${leitura.volume} de ${leitura.total_volume}`;
    if (leitura.referencia) {
      det.textContent += `  ·  ${leitura.referencia}`;
    }
    flash.appendChild(carro);
    flash.appendChild(det);
  }

  function mostrarBannerLote(ok, texto, erros) {
    loteBanner.classList.remove("d-none", "alert-success", "alert-danger");
    loteBanner.replaceChildren();
    loteBanner.classList.add(ok ? "alert-success" : "alert-danger");
    const titulo = document.createElement("div");
    titulo.className = "fw-bold fs-5";
    titulo.textContent = ok
      ? "Gravação realizada com sucesso"
      : "A gravação não foi concluída com sucesso";
    const p = document.createElement("p");
    p.className = "mb-0";
    p.textContent = texto;
    loteBanner.appendChild(titulo);
    loteBanner.appendChild(p);
    if (!ok && Array.isArray(erros) && erros.length) {
      const ul = document.createElement("ul");
      ul.className = "mb-0 mt-2";
      erros.forEach((e) => {
        const li = document.createElement("li");
        const trk = e.trk != null ? `TRK ${e.trk}` : "código";
        const vol = e.volume != null ? ` vol. ${e.volume}` : "";
        li.textContent = `${trk}${vol}: ${e.mensagem || "erro"}`;
        ul.appendChild(li);
      });
      loteBanner.appendChild(ul);
    }
  }

  function jaNaLista(trk, volume) {
    return lista.some((l) => l.trk === trk && l.volume === volume);
  }

  async function enviarPreview(codigo) {
    AppLoader.show();
    try {
      const resp = await fazerRequisicao(URL_PREVIEW, { codigo });
      if (!resp.success) {
        const msg = textoMensagem(resp.data, resp.error || "Falha na leitura.");
        mostrarFlash(false, null, msg);
        return null;
      }
      return resp.data?.leitura || null;
    } finally {
      AppLoader.hide();
    }
  }

  async function processarCodigo(codigo) {
    if (processandoCodigo || scanPausado) return;
    processandoCodigo = true;
    scanPausado = true;
    btnSeguinte.disabled = false;
    if (scanHint) scanHint.textContent = "Leitura pausada. Toque em «Ler seguinte» para continuar.";
    try {
      const leitura = await enviarPreview(codigo);
      if (!leitura) return;
      if (jaNaLista(leitura.trk, leitura.volume)) {
        mostrarFlash(false, null, `Volume ${leitura.volume} do TRK ${leitura.trk} já está na lista.`);
        return;
      }
      lista.push(leitura);
      renderLista();
      mostrarFlash(true, leitura);
    } finally {
      processandoCodigo = false;
    }
  }

  async function pararCamera() {
    scanPausado = true;
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = 0;
    }
    if (zxingReader) {
      try {
        zxingReader.reset();
      } catch {
        /* ignore */
      }
      zxingReader = null;
    }
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
    }
    if (video) video.srcObject = null;
    overlay.classList.add("d-none");
    overlay.hidden = true;
    btnSeguinte.disabled = true;
    if (scanHint) scanHint.textContent = "Aponte a câmara para o QR da etiqueta.";
  }

  async function loopBarcodeDetector() {
    if (!detector || !video || video.readyState < 2) {
      rafId = requestAnimationFrame(loopBarcodeDetector);
      return;
    }
    if (!scanPausado) {
      try {
        const codes = await detector.detect(video);
        if (codes && codes[0] && codes[0].rawValue) {
          await processarCodigo(codes[0].rawValue);
        }
      } catch {
        /* frame sem código */
      }
    }
    rafId = requestAnimationFrame(loopBarcodeDetector);
  }

  function carregarZxing() {
    if (window.ZXing) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = ZXING_SRC;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error("Não foi possível carregar o leitor de QR."));
      document.head.appendChild(s);
    });
  }

  async function iniciarZxing() {
    await carregarZxing();
    const ZXing = window.ZXing;
    zxingReader = new ZXing.BrowserMultiFormatReader();
    const devices = await zxingReader.listVideoInputDevices();
    const traseira = devices.find((d) => /back|rear|environment/i.test(d.label));
    const deviceId = (traseira || devices[devices.length - 1] || {}).deviceId;
    await zxingReader.decodeFromVideoDevice(deviceId || null, video, (result) => {
      if (result && result.getText) {
        processarCodigo(result.getText());
      }
    });
  }

  async function iniciarCamera() {
    scanPausado = false;
    processandoCodigo = false;
    overlay.hidden = false;
    overlay.classList.remove("d-none");
    btnSeguinte.disabled = true;
    if (scanHint) scanHint.textContent = "Aponte a câmara para o QR da etiqueta.";
    try {
      if (window.BarcodeDetector) {
        detector = new window.BarcodeDetector({ formats: ["qr_code"] });
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" } },
          audio: false,
        });
        video.srcObject = stream;
        await video.play();
        loopBarcodeDetector();
        return;
      }
      await iniciarZxing();
    } catch (err) {
      await pararCamera();
      mostrarFlash(
        false,
        null,
        err?.message || "Não foi possível abrir a câmara. Verifique a permissão do navegador (HTTPS).",
      );
    }
  }

  btnLer.addEventListener("click", () => {
    loteBanner.classList.add("d-none");
    iniciarCamera();
  });
  btnFecharCam.addEventListener("click", () => pararCamera());
  btnSeguinte.addEventListener("click", () => {
    scanPausado = false;
    processandoCodigo = false;
    btnSeguinte.disabled = true;
    if (scanHint) scanHint.textContent = "Aponte a câmara para o QR da etiqueta.";
  });

  btnGravar.addEventListener("click", () => {
    if (!lista.length) return;
    confirmar({
      titulo: "Confirmar gravação",
      mensagem: `Gravar ${lista.length} conferência(s) na filial activa? Esta acção não pode ser desfeita pela lista.`,
      onConfirmar: async () => {
        AppLoader.show();
        try {
          const resp = await fazerRequisicao(URL_SALVAR, {
            leituras: lista.map((l) => ({ codigo: l.codigo })),
          });
          const data = resp.data || {};
          const erros = data.erros || [];
          const gravados = data.gravados || [];
          if (resp.success && data.todos_ok) {
            lista = [];
            renderLista();
            mostrarBannerLote(true, textoMensagem(data, "Conferências gravadas."), []);
            return;
          }
          const chavesOk = new Set(
            gravados.map((g) => `${g.trk}-${g.volume}`),
          );
          lista = lista.filter((l) => !chavesOk.has(`${l.trk}-${l.volume}`));
          renderLista();
          mostrarBannerLote(
            false,
            textoMensagem(data, resp.error || "Falha ao gravar."),
            erros,
          );
        } finally {
          AppLoader.hide();
        }
      },
    });
  });

  renderLista();
}
