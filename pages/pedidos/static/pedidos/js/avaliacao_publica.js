(() => {
  const form = document.getElementById("avaliacao-form");
  const status = document.getElementById("avaliacao-status");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const btn = form.querySelector("button[type='submit']");
    btn.disabled = true;
    btn.textContent = "Enviando...";

    const data = {};
    new FormData(form).forEach((value, key) => {
      data[key] = value;
    });

    try {
      const resp = await fetch(form.dataset.urlEnviar, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const json = await resp.json();
      if (!json.success) {
        status.innerHTML = `<span class="text-danger">${json.mensagem || "Falha ao enviar."}</span>`;
        btn.disabled = false;
        btn.textContent = "Finalizar Avaliação";
        return;
      }
      form.innerHTML = "";
      status.innerHTML = `<div class="alert alert-success mb-0">${json.mensagem}</div>`;
    } catch {
      status.innerHTML = "<span class='text-danger'>Erro de comunicação. Tente novamente.</span>";
      btn.disabled = false;
      btn.textContent = "Finalizar Avaliação";
    }
  });
})();
