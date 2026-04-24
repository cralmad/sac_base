import { getCsrfToken, clearMessages, definirMensagem } from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';

const root       = document.getElementById('rs-root');
const URL_BUSCAR  = root?.dataset?.urlBuscar  ?? '';
const URL_ENVIAR  = root?.dataset?.urlEnviar  ?? '';
const URL_PREVIEW = root?.dataset?.urlPreview ?? '';

const form        = document.getElementById('rs-form');
const inpData     = document.getElementById('rs-data');
const tabelaWrapper = document.getElementById('rs-tabela-wrapper');
const tbody       = document.getElementById('rs-tbody');
const chkTodos    = document.getElementById('rs-chk-todos');
const loader      = document.getElementById('rs-loader');
const vazio       = document.getElementById('rs-vazio');
const tituloData  = document.getElementById('rs-titulo-data');
const btnEnviar   = document.getElementById('rs-btn-enviar');
const btnPreview  = document.getElementById('rs-btn-preview');
const modalPreviewEl   = document.getElementById('rs-modal-preview');
const modalPreviewBody = document.getElementById('rs-modal-preview-body');
const modalPreview = new bootstrap.Modal(modalPreviewEl);

// ─── Escape seguro ─────────────────────────────────────────────────────────────
function _esc(v) {
  if (v == null) return '';
  return String(v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─── Estado local ──────────────────────────────────────────────────────────────
let _dataAtual = '';

// ─── Atualizar botão Enviar SMS ────────────────────────────────────────────────
function atualizarBtnEnviar() {
  const marcados = tbody.querySelectorAll('input[type="checkbox"]:not(:disabled):checked');
  btnEnviar.disabled = marcados.length === 0;
}

// ─── Renderizar tabela ─────────────────────────────────────────────────────────
function renderizarTabela(registros, dataFmt) {
  tbody.replaceChildren();
  tabelaWrapper.classList.add('d-none');
  vazio.classList.add('d-none');

  if (!registros.length) {
    vazio.classList.remove('d-none');
    btnEnviar.disabled = true;
    chkTodos.checked = false;
    chkTodos.disabled = true;
    return;
  }

  tituloData.textContent = `Data: ${dataFmt}`;
  chkTodos.disabled = false;

  registros.forEach(reg => {
    const smsEnviado  = !!reg.sms_enviado;
    const temPeriodo  = !!(reg.periodo && reg.periodo !== '');
    const desabilitado = smsEnviado || !temPeriodo;

    const tr = document.createElement('tr');
    if (smsEnviado) tr.classList.add('rs-enviado');
    tr.dataset.id = String(reg.id);

    // Checkbox
    const tdChk = document.createElement('td');
    tdChk.className = 'text-center';
    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.className = 'form-check-input rs-chk';
    chk.dataset.id = String(reg.id);
    chk.disabled = desabilitado;
    if (smsEnviado) chk.checked = true;
    chk.addEventListener('change', () => {
      atualizarBtnEnviar();
      sincronizarChkTodos();
    });
    tdChk.appendChild(chk);
    tr.appendChild(tdChk);

    // Referência
    const tdRef = document.createElement('td');
    tdRef.textContent = reg.referencia;
    tr.appendChild(tdRef);

    // Tipo
    const tdTipo = document.createElement('td');
    const spanTipo = document.createElement('span');
    spanTipo.textContent = reg.tipo;
    spanTipo.className = reg.tipo === 'RECOLHA' ? 'rs-tipo-r' : 'rs-tipo-e';
    tdTipo.appendChild(spanTipo);
    tr.appendChild(tdTipo);

    // Telefone(s)
    const tdFones = document.createElement('td');
    tdFones.textContent = (reg.fones || []).join(' / ');
    tr.appendChild(tdFones);

    // C. Postal
    const tdCp = document.createElement('td');
    tdCp.textContent = reg.codpost_dest;
    tr.appendChild(tdCp);

    // Volume
    const tdVol = document.createElement('td');
    tdVol.textContent = reg.volume ?? '';
    tr.appendChild(tdVol);

    // Peso
    const tdPeso = document.createElement('td');
    tdPeso.textContent = reg.peso;
    tr.appendChild(tdPeso);

    // Período
    const tdPer = document.createElement('td');
    if (reg.periodo) {
      const spanPer = document.createElement('span');
      spanPer.textContent = reg.periodo;
      spanPer.className = `rs-periodo-${reg.periodo}`;
      tdPer.appendChild(spanPer);
    }
    tr.appendChild(tdPer);

    tbody.appendChild(tr);
  });

  tabelaWrapper.classList.remove('d-none');
  atualizarBtnEnviar();
}

// ─── Sincronizar "Selecionar todos" ────────────────────────────────────────────
function sincronizarChkTodos() {
  const habilitados = Array.from(tbody.querySelectorAll('input.rs-chk:not(:disabled)'));
  if (!habilitados.length) {
    chkTodos.checked = false;
    chkTodos.indeterminate = false;
    return;
  }
  const marcados = habilitados.filter(c => c.checked);
  chkTodos.indeterminate = marcados.length > 0 && marcados.length < habilitados.length;
  chkTodos.checked = marcados.length === habilitados.length;
}

// ─── "Selecionar todos" ────────────────────────────────────────────────────────
chkTodos.addEventListener('change', () => {
  tbody.querySelectorAll('input.rs-chk:not(:disabled)').forEach(c => {
    c.checked = chkTodos.checked;
  });
  atualizarBtnEnviar();
});

// ─── Buscar ────────────────────────────────────────────────────────────────────
async function buscar() {
  clearMessages();
  const data = inpData.value;
  if (!data) {
    definirMensagem('erro', 'Informe a data para buscar.', false);
    return;
  }

  _dataAtual = data;
  loader.classList.remove('d-none');
  tabelaWrapper.classList.add('d-none');
  vazio.classList.add('d-none');
  btnEnviar.disabled = true;
  chkTodos.checked = false;
  chkTodos.disabled = true;
  AppLoader.show();

  try {
    const resp = await fetch(URL_BUSCAR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ filtros: { data_tentativa: data } }),
    });
    const json = await resp.json();

    if (!json.success) {
      definirMensagem('erro', json.mensagem || 'Erro ao buscar registros.', false);
      return;
    }

    renderizarTabela(json.registros, json.data_fmt);
  } catch {
    definirMensagem('erro', 'Falha na comunicação com o servidor.', false);
  } finally {
    loader.classList.add('d-none');
    AppLoader.hide();
  }
}

// ─── Enviar SMS ────────────────────────────────────────────────────────────────
async function enviarSms() {
  clearMessages();

  const ids = Array.from(tbody.querySelectorAll('input.rs-chk:not(:disabled):checked'))
    .map(c => parseInt(c.dataset.id, 10));

  if (!ids.length) {
    definirMensagem('aviso', 'Nenhum registro selecionado.', false);
    return;
  }

  btnEnviar.disabled = true;
  AppLoader.show();

  try {
    const resp = await fetch(URL_ENVIAR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ ids, data_tentativa: _dataAtual }),
    });
    const json = await resp.json();

    if (!json.success) {
      definirMensagem('erro', json.mensagem || 'Erro ao enviar SMS.', false);
      btnEnviar.disabled = false;
      return;
    }

    // Desabilitar checkboxes dos registros enviados
    const enviados = new Set(json.ids_enviados || []);
    tbody.querySelectorAll('tr').forEach(tr => {
      const id = parseInt(tr.dataset.id, 10);
      if (enviados.has(id)) {
        tr.classList.add('rs-enviado');
        const chk = tr.querySelector('input.rs-chk');
        if (chk) {
          chk.checked = true;
          chk.disabled = true;
        }
      }
    });

    if (json.enviados > 0) {
      definirMensagem('sucesso', json.mensagem, true);
    }

    // Mostrar detalhes de erros, se houver
    if (json.erros > 0 && Array.isArray(json.erros_detalhe) && json.erros_detalhe.length) {
      const detalhe = json.erros_detalhe.join(' | ');
      definirMensagem('erro', `${json.erros} erro(s): ${detalhe}`, false);
    } else if (json.erros > 0) {
      definirMensagem('erro', `${json.erros} erro(s) ao enviar SMS.`, false);
    }

    atualizarBtnEnviar();
    sincronizarChkTodos();
  } catch {
    definirMensagem('erro', 'Falha na comunicação com o servidor.', false);
    btnEnviar.disabled = false;
  } finally {
    AppLoader.hide();
  }
}

// ─── Prévia das mensagens ──────────────────────────────────────────────────────────────────────────
function _buildPreviewBody(previews, dataFmt) {
  const wrap = document.createElement('div');

  const info = document.createElement('p');
  info.className = 'text-muted small mb-3';
  info.textContent = `Mensagens que serão enviadas na data ${dataFmt || '(nenhuma data selecionada)'}:`;
  wrap.appendChild(info);

  const periodos = [['MANHA', 'MANhÃ', 'text-warning'], ['TARDE', 'TARDE', 'text-primary']];
  periodos.forEach(([chave, rotulo, cor]) => {
    const label = document.createElement('strong');
    label.className = cor;
    label.textContent = rotulo;
    wrap.appendChild(label);

    const box = document.createElement('pre');
    box.className = 'bg-light rounded p-2 mt-1 mb-3';
    box.style.whiteSpace = 'pre-wrap';
    box.style.wordBreak = 'break-word';
    box.textContent = previews[chave] ?? '(sem mensagem)';
    wrap.appendChild(box);
  });

  return wrap;
}

async function abrirPreview() {
  const data = inpData.value;
  if (!data) {
    definirMensagem('aviso', 'Selecione uma data para ver a prévia.', false);
    return;
  }

  // Mostra modal com spinner
  modalPreviewBody.replaceChildren();
  const spinner = document.createElement('div');
  spinner.className = 'text-center text-muted py-3';
  spinner.innerHTML = '<div class="spinner-border spinner-border-sm me-2" role="status"></div>Carregando…';
  modalPreviewBody.appendChild(spinner);
  modalPreview.show();

  try {
    const resp = await fetch(URL_PREVIEW, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ data_tentativa: data }),
    });
    const json = await resp.json();

    if (!json.success) {
      modalPreviewBody.replaceChildren();
      const err = document.createElement('p');
      err.className = 'text-danger';
      err.textContent = json.mensagem || 'Erro ao carregar prévia.';
      modalPreviewBody.appendChild(err);
      return;
    }

    // Formata data para exibição
    const [ano, mes, dia] = data.split('-');
    const dataFmt = `${dia}/${mes}/${ano}`;
    modalPreviewBody.replaceChildren(_buildPreviewBody(json.previews, dataFmt));
  } catch {
    modalPreviewBody.replaceChildren();
    const err = document.createElement('p');
    err.className = 'text-danger';
    err.textContent = 'Falha na comunicação com o servidor.';
    modalPreviewBody.appendChild(err);
  }
}

// ─── Eventos ──────────────────────────────────────────────────────────────────────────
form.addEventListener('submit', e => { e.preventDefault(); buscar(); });
btnEnviar.addEventListener('click', enviarSms);
btnPreview.addEventListener('click', abrirPreview);
