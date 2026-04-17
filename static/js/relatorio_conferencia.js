
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
const URL_IMPRIMIR = root?.dataset?.urlImprimir ?? '';
const podeEditar = hasScreenPermission('relatorio', 'editar');
const podeEditarCarro = hasScreenPermission('relatorio', 'editar_carro');
const btnImprimir = document.getElementById('btn-imprimir-relatorio');
const btnAbrirMapa = document.getElementById('btn-abrir-mapa');
const barraAcoes = document.getElementById('barra-acoes-cards');
const btnExpandirTodos = document.getElementById('btn-expandir-todos');
let todosExpandidos = false;


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

  if (!readonly) {
    const btnMenos = document.createElement('button');
    btnMenos.type = 'button';
    btnMenos.className = 'btn btn-outline-secondary btn-sm btn-campo-menor';
    btnMenos.dataset.campo = campo;
    btnMenos.dataset.op = '-';
    btnMenos.setAttribute('tabindex', '-1');
    btnMenos.textContent = '-';
    inputGroup.appendChild(btnMenos);
  }

  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'form-control mov-editable input-num-xs';
  input.id = `${campo}-${id}`;
  input.value = Math.max(0, parseInt(valor ?? 0, 10) || 0);
  input.dataset.campo = campo;
  input.setAttribute('readonly', '');
  if (readonly) input.setAttribute('disabled', '');
  inputGroup.appendChild(input);

  if (!readonly) {
    const btnMais = document.createElement('button');
    btnMais.type = 'button';
    btnMais.className = 'btn btn-outline-secondary btn-sm btn-campo-maior';
    btnMais.dataset.campo = campo;
    btnMais.dataset.op = '+';
    btnMais.setAttribute('tabindex', '-1');
    btnMais.textContent = '+';
    inputGroup.appendChild(btnMais);
  }
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
  inner.dataset.updatedAt = mov.updated_at ?? '';

  // ── Visualização do Carro salvo (topo do card, reflete apenas o valor persistido) ──
  const carroDisplay = document.createElement('div');
  carroDisplay.className = 'mov-carro-display';
  const carroDisplayLabel = document.createElement('span');
  carroDisplayLabel.className = 'mov-carro-display-label';
  carroDisplayLabel.textContent = 'Carro';
  const carroDisplayValue = document.createElement('span');
  carroDisplayValue.className = 'badge bg-primary';
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
    if (rotulo === 'Referência') span.className = 'fw-semibold';
    span.textContent = valor;
    div.appendChild(labelEl);
    div.appendChild(span);
    leitura.appendChild(div);
  }
  if (mov.obs) {
    const obsDiv = document.createElement('div');
    obsDiv.className = 'mov-field-obs';
    const obsLabel = document.createElement('span');
    obsLabel.className = 'mov-field-label';
    obsLabel.textContent = 'Obs.';
    const obsValue = document.createElement('span');
    obsValue.textContent = mov.obs;
    obsDiv.appendChild(obsLabel);
    obsDiv.appendChild(obsValue);
    leitura.appendChild(obsDiv);
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
    collapseInner.appendChild(criarCampoNumerico(mov.id, 'carro', mov.carro, !podeEditarCarro));

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
        if (podeEditar && barraAcoes) barraAcoes.classList.remove('d-none');
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
  todosExpandidos = false;
  movLista.replaceChildren();
  fimLista.classList.add('d-none');
  if (barraAcoes) barraAcoes.classList.add('d-none');
  if (btnExpandirTodos) btnExpandirTodos.innerHTML = '<i class="bi bi-chevron-expand"></i> Expandir todos';
}


// ─── Eventos de UI ────────────────────────────────────────────────────────────

document.getElementById('filtro-relatorio').addEventListener('submit', e => {
  e.preventDefault();
  filtros = {
    data_tentativa: document.getElementById('filtro-data').value,
    referencia: document.getElementById('filtro-referencia').value,
    tipo: document.getElementById('filtro-tipo').value,
    conferido: document.getElementById('filtro-conferido').value,
  };
  resetarLista();
  carregarPagina();
  if (btnImprimir) btnImprimir.disabled = false;
  if (btnAbrirMapa && filtros.data_tentativa) {
    const url = new URL(btnAbrirMapa.href, window.location.origin);
    url.searchParams.set('data', filtros.data_tentativa);
    btnAbrirMapa.href = url.toString();
    btnAbrirMapa.classList.remove('disabled');
    btnAbrirMapa.removeAttribute('aria-disabled');
    btnAbrirMapa.removeAttribute('tabindex');
  }
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
  const updated_at = card.dataset.updatedAt ?? '';

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Salvando';
  AppLoader.show();
  try {
    const resp = await fetch(URL_SALVAR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ id, carro, obs_rota, volume_conf, periodo, updated_at }),
    });
    if (resp.status === 401) {
      btn.innerHTML = '<i class="bi bi-lock"></i> Sessão expirada';
      setTimeout(() => { window.location.href = '/app/usuario/login/'; }, 1500);
      return;
    }
    if (resp.status === 409) {
      const data = await resp.json().catch(() => ({}));
      btn.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Conflito';
      btn.classList.replace('btn-success', 'btn-warning');
      card.classList.add('border-warning');
      // Mostra aviso inline no card
      let avisoEl = card.querySelector('.mov-conflito-aviso');
      if (!avisoEl) {
        avisoEl = document.createElement('div');
        avisoEl.className = 'mov-conflito-aviso alert alert-warning py-1 px-2 mt-1 small';
        card.querySelector('.btn-salvar-wrapper').before(avisoEl);
      }
      avisoEl.textContent = data.mensagem || 'Registro alterado por outro usuário. Recarregue e tente novamente.';
      // Atualiza o timestamp local para que nova tentativa de salvar possa ser comparada corretamente
      if (data.updated_at) card.dataset.updatedAt = data.updated_at;
      setTimeout(() => {
        btn.innerHTML = '<i class="bi bi-check"></i> Salvar';
        btn.classList.replace('btn-warning', 'btn-success');
        btn.disabled = false;
      }, 3000);
      return;
    }
    const data = await resp.json();
    if (data.success) {
      btn.innerHTML = '<i class="bi bi-check"></i> Salvo';
      desmarcarAlterado(card);
      if (data.updated_at) card.dataset.updatedAt = data.updated_at;
      card.classList.remove('border-warning');
      card.querySelector('.mov-conflito-aviso')?.remove();
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


// Expandir / recolher todos os cards
btnExpandirTodos?.addEventListener('click', () => {
  const collapses = movLista.querySelectorAll('.collapse');
  if (todosExpandidos) {
    collapses.forEach(el => bootstrap.Collapse.getOrCreateInstance(el).hide());
    btnExpandirTodos.innerHTML = '<i class="bi bi-chevron-expand"></i> Expandir todos';
    todosExpandidos = false;
  } else {
    collapses.forEach(el => bootstrap.Collapse.getOrCreateInstance(el).show());
    btnExpandirTodos.innerHTML = '<i class="bi bi-chevron-contract"></i> Recolher todos';
    todosExpandidos = true;
  }
});

// ─── WebSocket — atualização em tempo real ────────────────────────────────────

function aplicarAtualizacaoWs(payload) {
  const card = movLista.querySelector(`.mov-card[data-id="${payload.id}"]`);
  if (!card) return;

  // Badge do carro: sempre atualizar quando a chave estiver presente no payload,
  // independente de o usuário ter permissão de edição.
  if ('carro' in payload) {
    const displayEl = card.querySelector('[data-carro-display]');
    if (displayEl) {
      const v = payload.carro;
      displayEl.textContent = (v != null && String(v).trim() !== '') ? v : '—';
    }
  }

  // Input de carro (apenas existe para usuários com podeEditar)
  const inputCarro = card.querySelector('input[data-campo="carro"]');
  if (inputCarro && 'carro' in payload && payload.carro != null) {
    inputCarro.value = payload.carro;
  }

  // Input de volume_conf
  const inputVol = card.querySelector('input[data-campo="volume_conf"]');
  if (inputVol && 'volume_conf' in payload) {
    inputVol.value = payload.volume_conf ?? 0;
  }

  const textarea = card.querySelector('[data-campo="obs_rota"]');
  if (textarea && payload.obs_rota != null) textarea.value = payload.obs_rota;

  const periodoSel = card.querySelector('[data-campo="periodo"]');
  if (periodoSel && payload.periodo != null) periodoSel.value = payload.periodo;

  // Atualiza o timestamp de controle de concorrência
  if (payload.updated_at) card.dataset.updatedAt = payload.updated_at;

  // Remove aviso de conflito se existir (o WS trouxe o estado atual)
  card.querySelector('.mov-conflito-aviso')?.remove();
  card.classList.remove('border-warning');

  // Flash visual de atualização remota
  card.classList.add('mov-ws-flash');
  setTimeout(() => card.classList.remove('mov-ws-flash'), 1500);
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


// ─── Relatório de impressão ────────────────────────────────────────────────────

function gerarHtmlRelatorio(grupos, filtros) {
  const dataExib = filtros.data_tentativa
    ? new Date(filtros.data_tentativa + 'T00:00:00').toLocaleDateString('pt-PT')
    : '';

  const cabecalho = `
    <div class="cabecalho-relatorio">
      <h2>Conferência de Volumes</h2>
      <p>Data: <strong>${dataExib}</strong>
        ${filtros.tipo ? ` &nbsp;|&nbsp; Tipo: <strong>${filtros.tipo}</strong>` : ''}
        ${filtros.conferido ? ` &nbsp;|&nbsp; Conferido: <strong>${filtros.conferido.toUpperCase()}</strong>` : ''}
      </p>
    </div>`;

  let corpo = '';
  for (const grupo of grupos) {
    // Linha de cabeçalho do grupo
    corpo += `
    <div class="grupo-header">
      <span>Carro: <strong>${grupo.carro}</strong></span>
      <span>Data: <strong>${grupo.data_tentativa}</strong></span>
    </div>
    <table>
      <thead>
        <tr>
          <th>Referência</th>
          <th>Tipo</th>
          <th>Cód. Postal</th>
          <th>Cidade</th>
          <th>Vol.</th>
          <th>Peso</th>
          <th>Obs. Rota</th>
          <th>Conferido</th>
        </tr>
      </thead>
      <tbody>`;
    for (const l of grupo.linhas) {
      const conferidoClass = l.conferido === 'SIM' ? 'conf-sim' : 'conf-nao';
      // Escapa conteúdo usando um trick seguro (sem innerHTML dinâmico)
      corpo += `
        <tr>
          <td>${_esc(l.pedido)}</td>
          <td>${_esc(l.tipo)}</td>
          <td>${_esc(l.codpost_dest)}</td>
          <td>${_esc(l.cidade_dest)}</td>
          <td>${_esc(l.volume)}</td>
          <td>${_esc(l.peso)}</td>
          <td class="obs-rota">${_esc(l.obs_rota)}</td>
          <td class="${conferidoClass}">${_esc(l.conferido)}</td>
        </tr>`;
    }
    corpo += `</tbody></table>`;
  }

  return `<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<title>Relatório de Conferência</title>
<style>
  @page { size: A4 portrait; margin: 12mm 10mm; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Arial, sans-serif; font-size: 9pt; color: #111; }
  .cabecalho-relatorio { margin-bottom: 6mm; }
  .cabecalho-relatorio h2 { font-size: 13pt; margin-bottom: 2mm; }
  .cabecalho-relatorio p { font-size: 9pt; color: #444; }
  .grupo-header {
    background: #2c5282;
    color: #fff;
    padding: 3mm 4mm;
    margin-top: 5mm;
    margin-bottom: 1mm;
    border-radius: 3px;
    display: flex;
    gap: 12mm;
    font-size: 10pt;
    page-break-inside: avoid;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    margin-bottom: 3mm;
  }
  thead { background: #e8edf5; }
  th, td {
    border: 1px solid #c5ccd8;
    padding: 2mm 2.5mm;
    vertical-align: top;
    word-break: break-word;
    white-space: pre-wrap;
  }
  th { font-size: 8pt; text-align: left; }
  /* Larguras das colunas */
  table th:nth-child(1), table td:nth-child(1) { width: 14%; } /* Referência */
  table th:nth-child(2), table td:nth-child(2) { width: 7%; }  /* Tipo */
  table th:nth-child(3), table td:nth-child(3) { width: 9%; }  /* Cód. Postal */
  table th:nth-child(4), table td:nth-child(4) { width: 12%; } /* Cidade */
  table th:nth-child(5), table td:nth-child(5) { width: 5%; }  /* Vol. */
  table th:nth-child(6), table td:nth-child(6) { width: 8%; }  /* Peso */
  table th:nth-child(7), table td:nth-child(7) { width: 33%; } /* Obs. Rota */
  table th:nth-child(8), table td:nth-child(8) { width: 12%; } /* Conferido */
  .obs-rota { font-size: 8pt; }
  .conf-sim { color: #155724; font-weight: bold; }
  .conf-nao { color: #721c24; font-weight: bold; }
  tr:nth-child(even) { background: #f7f9fc; }
  @media print {
    .grupo-header { page-break-before: auto; }
    tr { page-break-inside: avoid; }
  }
</style>
</head>
<body>
${cabecalho}
${corpo}
</body>
</html>`;
}

function _esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

btnImprimir?.addEventListener('click', async () => {
  if (!filtros.data_tentativa) return;
  AppLoader.show();
  try {
    const resp = await fetch(URL_IMPRIMIR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ filtros }),
    });
    const data = await resp.json();
    if (!data.success) {
      alert(data.mensagem || 'Erro ao gerar relatório.');
      return;
    }
    const html = gerarHtmlRelatorio(data.grupos, data.filtros);
    const win = window.open('', '_blank', 'width=900,height=700');
    if (!win) { alert('Permita popups para gerar o relatório.'); return; }
    win.document.write(html);
    win.document.close();
  } catch {
    alert('Erro ao gerar relatório.');
  } finally {
    AppLoader.hide();
  }
});
