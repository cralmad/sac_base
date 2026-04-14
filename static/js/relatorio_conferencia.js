
import { getCsrfToken, hasScreenPermission } from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';

let pagina = 1;
let carregando = false;
let fim = false;
let filtros = {};
const pageSize = 30;

const root = document.getElementById('relatorio-root');
const movLista = document.getElementById('mov-lista');
const loader = document.getElementById('loader');
const fimLista = document.getElementById('fim-lista');
const URL_SALVAR = root?.dataset?.urlSalvar ?? '';
const podeEditar = hasScreenPermission('relatorio', 'editar');


// ─── Renderização segura via createElement ───────────────────────────────────

function criarCampoNumerico(id, campo, valor, readonly) {
  const wrapper = document.createElement('div');
  const label = document.createElement('label');
  label.className = 'form-label mb-0 d-flex align-items-center gap-1';
  label.htmlFor = `${campo}-${id}`;
  const labelSpan = document.createElement('span');
  labelSpan.textContent = campo === 'carro' ? 'Carro' : 'Volume Conf.';
  label.appendChild(labelSpan);

  if (campo === 'volume_conf') {
    const helpSpan = document.createElement('span');
    helpSpan.className = 'text-primary';
    helpSpan.setAttribute('role', 'button');
    helpSpan.setAttribute('tabindex', '0');
    helpSpan.setAttribute('data-bs-toggle', 'tooltip');
    helpSpan.setAttribute('data-bs-placement', 'top');
    helpSpan.setAttribute('data-bs-title', 'Usado para conferência da entrada dos volumes no armazém.');
    const icon = document.createElement('i');
    icon.className = 'bi bi-question-circle';
    helpSpan.appendChild(icon);
    label.appendChild(helpSpan);
  } else {
    const helpSpan = document.createElement('span');
    helpSpan.className = 'text-primary';
    helpSpan.setAttribute('role', 'button');
    helpSpan.setAttribute('tabindex', '0');
    helpSpan.setAttribute('data-bs-toggle', 'tooltip');
    helpSpan.setAttribute('data-bs-placement', 'top');
    helpSpan.setAttribute('data-bs-title', 'Número do carro responsável pela entrega.');
    const icon = document.createElement('i');
    icon.className = 'bi bi-question-circle';
    helpSpan.appendChild(icon);
    label.appendChild(helpSpan);
  }

  const inputGroup = document.createElement('div');
  inputGroup.className = 'input-group';

  const btnMenos = document.createElement('button');
  btnMenos.type = 'button';
  btnMenos.className = 'btn btn-outline-secondary btn-sm btn-campo-menor';
  btnMenos.dataset.campo = campo;
  btnMenos.dataset.op = '-';
  btnMenos.setAttribute('tabindex', '-1');
  btnMenos.textContent = '-';

  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'form-control mov-editable input-num-xs';
  input.id = `${campo}-${id}`;
  input.value = Math.max(0, parseInt(valor ?? 0, 10) || 0);
  input.dataset.campo = campo;
  // Sempre readonly: valor só muda via botões +/-
  input.setAttribute('readonly', '');

  const btnMais = document.createElement('button');
  btnMais.type = 'button';
  btnMais.className = 'btn btn-outline-secondary btn-sm btn-campo-maior';
  btnMais.dataset.campo = campo;
  btnMais.dataset.op = '+';
  btnMais.setAttribute('tabindex', '-1');
  btnMais.textContent = '+';

  inputGroup.appendChild(btnMenos);
  inputGroup.appendChild(input);
  inputGroup.appendChild(btnMais);
  wrapper.appendChild(label);
  wrapper.appendChild(inputGroup);
  return wrapper;
}


function criarMovCard(mov) {
  const card = document.createElement('div');
  card.className = 'col-12 col-md-6 col-xl-4';

  const inner = document.createElement('div');
  inner.className = 'mov-card h-100';
  inner.dataset.id = mov.id;

  // ── Visualização do Carro salvo (topo do card, reflete apenas o valor persistido) ──
  const carroDisplay = document.createElement('div');
  carroDisplay.className = 'mov-carro-display';
  const carroDisplayLabel = document.createElement('span');
  carroDisplayLabel.className = 'mov-carro-display-label text-muted small';
  carroDisplayLabel.textContent = 'Carro';
  const carroDisplayValue = document.createElement('span');
  carroDisplayValue.className = 'badge bg-primary ms-1';
  carroDisplayValue.dataset.carroDisplay = '';
  carroDisplayValue.textContent = (mov.carro != null && String(mov.carro).trim() !== '') ? mov.carro : '—';
  carroDisplay.appendChild(carroDisplayLabel);
  carroDisplay.appendChild(carroDisplayValue);
  inner.appendChild(carroDisplay);

  // Campos somente leitura
  const leitura = document.createElement('div');
  leitura.className = 'mov-fields mt-1';
  const pares = [
    ['Data', mov.data_tentativa],
    ['Referência', mov.referencia],
    ['Cód. Postal', mov.codpost_dest],
    ['Cidade', mov.cidade_dest],
    ['Volume', mov.volume ?? ''],
    ['Peso', mov.peso ?? ''],
  ];
  for (const [rotulo, valor] of pares) {
    const div = document.createElement('div');
    const labelEl = document.createElement('span');
    labelEl.className = 'mov-field-label';
    labelEl.textContent = rotulo;
    const span = document.createElement('span');
    span.textContent = valor;
    div.appendChild(labelEl);
    div.appendChild(span);
    leitura.appendChild(div);
  }
  inner.appendChild(leitura);

  // ── Edição (apenas com permissão) ──────────────────────────────────────
  if (podeEditar) {
    const edicao = document.createElement('div');
    edicao.className = 'mt-2';

    // Volume Conf. — centrado a 60% do card
    const volSection = document.createElement('div');
    volSection.className = 'mov-vol-section';
    volSection.appendChild(criarCampoNumerico(mov.id, 'volume_conf', mov.volume_conf, false));
    edicao.appendChild(volSection);

    // Botão toggle sanfona
    const collapseId = `sanfona-${mov.id}`;
    const toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.className = 'btn btn-link btn-sm mov-sanfona-toggle w-100 mt-1';
    toggleBtn.setAttribute('data-bs-toggle', 'collapse');
    toggleBtn.setAttribute('data-bs-target', `#${collapseId}`);
    toggleBtn.setAttribute('aria-expanded', 'false');
    toggleBtn.setAttribute('aria-controls', collapseId);
    const toggleIcon = document.createElement('i');
    toggleIcon.className = 'bi bi-chevron-down mov-sanfona-icon me-1';
    const toggleText = document.createElement('span');
    toggleText.className = 'small';
    toggleText.textContent = 'Carro / Período / Obs.';
    toggleBtn.appendChild(toggleIcon);
    toggleBtn.appendChild(toggleText);
    edicao.appendChild(toggleBtn);

    // Conteúdo colapsável
    const collapseDiv = document.createElement('div');
    collapseDiv.className = 'collapse';
    collapseDiv.id = collapseId;
    const collapseInner = document.createElement('div');
    collapseInner.className = 'mov-fields mt-1';

    // Carro
    collapseInner.appendChild(criarCampoNumerico(mov.id, 'carro', mov.carro, false));

    // Período
    const periodoWrapper = document.createElement('div');
    const periodoLabel = document.createElement('label');
    periodoLabel.className = 'form-label mb-0 d-flex align-items-center gap-1';
    periodoLabel.htmlFor = `periodo-${mov.id}`;
    const periodoSpan = document.createElement('span');
    periodoSpan.textContent = 'Período';
    periodoLabel.appendChild(periodoSpan);
    const periodoHelp = document.createElement('span');
    periodoHelp.className = 'text-primary';
    periodoHelp.setAttribute('role', 'button');
    periodoHelp.setAttribute('tabindex', '0');
    periodoHelp.setAttribute('data-bs-toggle', 'tooltip');
    periodoHelp.setAttribute('data-bs-placement', 'top');
    periodoHelp.setAttribute('data-bs-title', 'Período do dia para a entrega: Manhã ou Tarde.');
    const periodoIcon = document.createElement('i');
    periodoIcon.className = 'bi bi-question-circle';
    periodoHelp.appendChild(periodoIcon);
    periodoLabel.appendChild(periodoHelp);
    const periodoSelect = document.createElement('select');
    periodoSelect.className = 'form-select form-select-sm mov-editable';
    periodoSelect.id = `periodo-${mov.id}`;
    periodoSelect.dataset.campo = 'periodo';
    [['', '— Selecionar —'], ['MANHA', 'MANHÃ'], ['TARDE', 'TARDE']].forEach(([val, txt]) => {
      const opt = document.createElement('option');
      opt.value = val;
      opt.textContent = txt;
      periodoSelect.appendChild(opt);
    });
    periodoSelect.value = mov.periodo ?? '';
    periodoWrapper.appendChild(periodoLabel);
    periodoWrapper.appendChild(periodoSelect);
    collapseInner.appendChild(periodoWrapper);

    // Obs. Rota (ocupa toda a largura via .mov-obs-wrapper)
    const obsWrapper = document.createElement('div');
    obsWrapper.className = 'mov-obs-wrapper';
    const obsLabel = document.createElement('label');
    obsLabel.className = 'form-label mb-0 d-flex align-items-center gap-1';
    obsLabel.htmlFor = `obs_rota-${mov.id}`;
    const obsSpan = document.createElement('span');
    obsSpan.textContent = 'Obs. Rota';
    obsLabel.appendChild(obsSpan);
    const obsHelp = document.createElement('span');
    obsHelp.className = 'text-primary';
    obsHelp.setAttribute('role', 'button');
    obsHelp.setAttribute('tabindex', '0');
    obsHelp.setAttribute('data-bs-toggle', 'tooltip');
    obsHelp.setAttribute('data-bs-placement', 'top');
    obsHelp.setAttribute('data-bs-title', 'Observação de rota que acompanhará o pedido na entrega.');
    const obsIcon = document.createElement('i');
    obsIcon.className = 'bi bi-question-circle';
    obsHelp.appendChild(obsIcon);
    obsLabel.appendChild(obsHelp);
    const textarea = document.createElement('textarea');
    textarea.className = 'form-control mov-editable auto-grow';
    textarea.id = `obs_rota-${mov.id}`;
    textarea.dataset.campo = 'obs_rota';
    textarea.rows = 1;
    textarea.style.resize = 'none';
    textarea.textContent = mov.obs_rota ?? '';
    obsWrapper.appendChild(obsLabel);
    obsWrapper.appendChild(textarea);
    collapseInner.appendChild(obsWrapper);

    collapseDiv.appendChild(collapseInner);
    edicao.appendChild(collapseDiv);
    inner.appendChild(edicao);

    const rodape = document.createElement('div');
    rodape.className = 'mt-2 btn-salvar-wrapper';
    const btnSalvar = document.createElement('button');
    btnSalvar.className = 'btn btn-success btn-sm btn-salvar-mov';
    btnSalvar.dataset.id = mov.id;
    btnSalvar.innerHTML = '<i class="bi bi-check"></i> Salvar';
    rodape.appendChild(btnSalvar);
    inner.appendChild(rodape);
  }

  card.appendChild(inner);
  return card;
}


// ─── Carregamento paginado ────────────────────────────────────────────────────

async function carregarPagina() {
  if (carregando || fim) return;
  carregando = true;
  loader.classList.remove('d-none');
  fimLista.classList.add('d-none');
  AppLoader.show();
  try {
    const resp = await fetch(window.location.pathname, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ filtros, pagina, page_size: pageSize }),
    });
    const data = await resp.json();
    if (data.success) {
      if (data.registros.length === 0 && pagina === 1) {
        const aviso = document.createElement('div');
        aviso.className = 'text-center text-muted col-12';
        aviso.textContent = 'Nenhum registro encontrado.';
        movLista.appendChild(aviso);
        fim = true;
      } else {
        for (const mov of data.registros) {
          movLista.appendChild(criarMovCard(mov));
        }
        if (!data.has_next) {
          fim = true;
          fimLista.classList.remove('d-none');
        }
        pagina++;
        // Reativa tooltips nos novos elementos
        document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
          new bootstrap.Tooltip(el);
        });
      }
    }
  } finally {
    carregando = false;
    loader.classList.add('d-none');
    AppLoader.hide();
  }
}

function resetarLista() {
  pagina = 1;
  fim = false;
  movLista.replaceChildren();
  fimLista.classList.add('d-none');
}


// ─── Eventos de UI ────────────────────────────────────────────────────────────

document.getElementById('filtro-relatorio').addEventListener('submit', e => {
  e.preventDefault();
  filtros = {
    data_tentativa: document.getElementById('filtro-data').value,
    referencia: document.getElementById('filtro-referencia').value,
    tipo: document.getElementById('filtro-tipo').value,
  };
  resetarLista();
  carregarPagina();
});

window.addEventListener('scroll', () => {
  if ((window.innerHeight + window.scrollY) >= (document.body.offsetHeight - 200)) {
    carregarPagina();
  }
});


function marcarAlterado(card) { card.classList.add('unsaved'); }
function desmarcarAlterado(card) { card.classList.remove('unsaved'); }

// Botões +/– para campos numéricos
movLista.addEventListener('click', e => {
  const btn = e.target.closest('.btn-campo-menor, .btn-campo-maior');
  if (!btn) return;
  const card = btn.closest('.mov-card');
  const campo = btn.dataset.campo;
  const input = card.querySelector(`input[data-campo="${campo}"]`);
  let valor = parseInt(input.value, 10) || 0;
  if (btn.dataset.op === '+') valor++;
  if (btn.dataset.op === '-' && valor > 0) valor--;
  input.value = valor;
  marcarAlterado(card);
});

// Autoexpansão do textarea e marcação de alterado
movLista.addEventListener('input', e => {
  const ta = e.target.closest('textarea[data-campo="obs_rota"]');
  if (ta) {
    ta.style.height = 'auto';
    ta.style.height = `${ta.scrollHeight}px`;
    marcarAlterado(ta.closest('.mov-card'));
  }
  const input = e.target.closest('[data-campo]');
  if (input && (input.type === 'text' || input.tagName === 'TEXTAREA')) {
    marcarAlterado(input.closest('.mov-card'));
  }
});

// Marcação de alterado em selects (período)
movLista.addEventListener('change', e => {
  const sel = e.target.closest('select[data-campo]');
  if (sel) marcarAlterado(sel.closest('.mov-card'));
});

// Salvar
movLista.addEventListener('click', async e => {
  const btn = e.target.closest('.btn-salvar-mov');
  if (!btn) return;
  const id = btn.dataset.id;
  const card = movLista.querySelector(`.mov-card[data-id="${id}"]`);
  const carro = card.querySelector('input[data-campo="carro"]').value;
  const obs_rota = card.querySelector('textarea[data-campo="obs_rota"]').value;
  const volume_conf = card.querySelector('input[data-campo="volume_conf"]').value;
  const periodo = card.querySelector('select[data-campo="periodo"]')?.value ?? '';

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Salvando';
  AppLoader.show();
  try {
    const resp = await fetch(URL_SALVAR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ id, carro, obs_rota, volume_conf, periodo }),
    });
    if (resp.status === 401) {
      btn.innerHTML = '<i class="bi bi-lock"></i> Sessão expirada';
      setTimeout(() => { window.location.href = '/app/usuario/login/'; }, 1500);
      return;
    }
    const data = await resp.json();
    if (data.success) {
      btn.innerHTML = '<i class="bi bi-check"></i> Salvo';
      desmarcarAlterado(card);
      const displayEl = card.querySelector('[data-carro-display]');
      if (displayEl) displayEl.textContent = String(carro).trim() !== '' ? carro : '—';
      setTimeout(() => { btn.innerHTML = '<i class="bi bi-check"></i> Salvar'; btn.disabled = false; }, 1000);
    } else {
      btn.innerHTML = '<i class="bi bi-x-circle"></i> Erro';
      setTimeout(() => { btn.innerHTML = '<i class="bi bi-check"></i> Salvar'; btn.disabled = false; }, 2000);
    }
  } catch {
    btn.innerHTML = '<i class="bi bi-x-circle"></i> Erro';
    setTimeout(() => { btn.innerHTML = '<i class="bi bi-check"></i> Salvar'; btn.disabled = false; }, 2000);
  } finally {
    AppLoader.hide();
  }
});


// ─── WebSocket — atualização em tempo real ────────────────────────────────────

function aplicarAtualizacaoWs(payload) {
  const card = movLista.querySelector(`.mov-card[data-id="${payload.id}"]`);
  if (!card) return;

  const inputCarro = card.querySelector('[data-campo="carro"]');
  if (inputCarro && payload.carro != null) {
    inputCarro.value = payload.carro;
    const displayEl = card.querySelector('[data-carro-display]');
    if (displayEl) displayEl.textContent = String(payload.carro).trim() !== '' ? payload.carro : '—';
  }

  const inputVol = card.querySelector('[data-campo="volume_conf"]');
  if (inputVol && payload.volume_conf != null) inputVol.value = payload.volume_conf;

  const textarea = card.querySelector('[data-campo="obs_rota"]');
  if (textarea && payload.obs_rota != null) textarea.value = payload.obs_rota;

  const periodoSel = card.querySelector('[data-campo="periodo"]');
  if (periodoSel && payload.periodo != null) periodoSel.value = payload.periodo;

  // Sinaliza brevemente que o card foi atualizado remotamente
  card.classList.add('table-info');
  setTimeout(() => card.classList.remove('table-info'), 1500);
  desmarcarAlterado(card);
}

function conectarWebSocket() {
  const protocolo = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${protocolo}//${window.location.host}/ws/relatorio_conferencia/`);

  ws.onmessage = e => {
    try {
      const payload = JSON.parse(e.data);
      aplicarAtualizacaoWs(payload);
    } catch { /* mensagem malformada */ }
  };

  ws.onclose = event => {
    // Código 4001 = sem permissão; não tentar reconectar
    if (event.code === 4001) return;
    // Reconexão exponencial (máx. 30 s)
    const delay = Math.min(30000, 1000 * 2 ** (ws._retries || 0));
    ws._retries = (ws._retries || 0) + 1;
    setTimeout(conectarWebSocket, delay);
  };

  ws.onerror = () => ws.close();
}

conectarWebSocket();
