import {
  getCsrfToken,
  clearMessages,
  definirMensagem,
  getOptions,
  hasScreenPermission,
} from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';
import {
  parseSmartNumber,
  parseSmartText,
  getMultiSelectValues,
  validateSmartNumber,
  validateSmartText,
} from '/static/js/smart_filter.js';

const VONZU_EXPEDITIONS_URL = 'https://app.vonzu.es/user/expeditions';

function criarLinkVonzu(idVonzu, textoExibicao) {
  const id = Number.parseInt(idVonzu, 10);
  if (!Number.isInteger(id) || id <= 0) return null;

  const link = document.createElement('a');
  link.href = `${VONZU_EXPEDITIONS_URL}/${id}`;
  link.className = 'rg-cod-link';
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.title = 'Abrir expedição na VONZU';
  link.textContent = String(textoExibicao ?? id);
  return link;
}

const root       = document.getElementById('rg-root');
const URL_BUSCAR = root?.dataset?.urlBuscar ?? '';
const URL_ANEXO_GMAIL = root?.dataset?.urlAnexoGmail ?? '';

const form        = document.getElementById('rg-form');
const inpDataIni  = document.getElementById('rg-data-ini');
const inpDataFim  = document.getElementById('rg-data-fim');
const inpIdVonzu  = document.getElementById('rg-id-vonzu');
const inpRef      = document.getElementById('rg-referencia');
const selEstados  = document.getElementById('rg-estados');
const resultado   = document.getElementById('rg-resultado');
const loader      = document.getElementById('rg-loader');
const vazio       = document.getElementById('rg-vazio');
const tituloData  = document.getElementById('rg-titulo-data');
const totalBar    = document.getElementById('rg-total-bar');
const btnImprimir      = document.getElementById('rg-btn-imprimir');
const btnSelTodos      = document.getElementById('rg-btn-sel-todos');
const btnDesTodos      = document.getElementById('rg-btn-des-todos');
const selTipo          = document.getElementById('rg-tipo');
const selArmazem       = document.getElementById('rg-armazem');
const selConferencia   = document.getElementById('rg-conferencia');
const colBtnDev        = document.getElementById('rg-col-btn-dev');
const btnRegistrarDev  = document.getElementById('rg-btn-registrar-dev');
const colBtnGmail      = document.getElementById('rg-col-btn-gmail');
const btnGmail         = document.getElementById('rg-btn-gmail');
const erroVonzu        = document.getElementById('rg-id-vonzu-erro');
const erroRef          = document.getElementById('rg-referencia-erro');

// ─── Popula select de estados a partir da sisVar ──────────────────────────────
function preencherEstados() {
  const estados = getOptions('estados') || [];
  selEstados.replaceChildren();
  estados.forEach(e => {
    const opt = document.createElement('option');
    opt.value = e.value;
    opt.textContent = e.label;
    selEstados.appendChild(opt);
  });
}

function preencherMotivos() {
  const motivos = getOptions('motivos_dev') || [];
  const sel = document.getElementById('rgm-motivo');
  sel.replaceChildren();
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = 'Selecione…';
  sel.appendChild(placeholder);
  motivos.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.value;
    opt.textContent = m.label;
    sel.appendChild(opt);
  });
}

btnSelTodos.addEventListener('click', () => {
  Array.from(selEstados.options).forEach(o => { o.selected = true; });
});
btnDesTodos.addEventListener('click', () => {
  Array.from(selEstados.options).forEach(o => { o.selected = false; });
});

// ─── Validação de smart filters ───────────────────────────────────────────────
function validarFiltros() {
  let valido = true;

  if (!validateSmartNumber(inpIdVonzu.value)) {
    erroVonzu.classList.remove('d-none');
    inpIdVonzu.classList.add('is-invalid');
    valido = false;
  } else {
    erroVonzu.classList.add('d-none');
    inpIdVonzu.classList.remove('is-invalid');
  }

  if (!validateSmartText(inpRef.value)) {
    erroRef.classList.remove('d-none');
    inpRef.classList.add('is-invalid');
    valido = false;
  } else {
    erroRef.classList.add('d-none');
    inpRef.classList.remove('is-invalid');
  }

  return valido;
}

// ─── Escape seguro ────────────────────────────────────────────────────────────
function _esc(v) {
  if (v == null) return '';
  return String(v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function resolverEstadoExibicao(registro) {
  return registro?.estado_label || registro?.estado || '';
}

// ─── Fila de devoluções pendentes ─────────────────────────────────────────────
let _devQueue      = [];   // [{pedido_id, pedido, tipo, volumes}, ...]
let _devIndex      = 0;
let _bsModal       = null;
let _ultimasLinhas = [];   // último resultado da busca (lista plana)
let _ultimoDataFmt = '';

function _podeRegistrarDevolucoes() {
  return hasScreenPermission('gerencial', 'editar');
}

function _podeDescarregarGmail() {
  return hasScreenPermission('gerencial', 'download_gmail');
}

function _coletarFilaDev(linhas) {
  _devQueue = [];
  linhas.forEach(l => {
    _devQueue.push({
      pedido_id: l.pedido_id,
      pedido:    l.pedido,
      tipo:      l.tipo,
      volumes:   l.volumes,
    });
  });
}

function _abrirModal(index) {
  if (index >= _devQueue.length) {
    _bsModal?.hide();
    definirMensagem('sucesso', 'Todas as devoluções foram registradas.', false);
    return;
  }
  _devIndex = index;
  const item = _devQueue[index];

  document.getElementById('rgm-referencia').textContent = item.pedido;
  document.getElementById('rgm-tipo').textContent       = item.tipo === 'R' ? 'Recolha' : 'Entrega';
  document.getElementById('rgm-volumes').textContent    = item.volumes;
  document.getElementById('rgm-pedido-id').value        = item.pedido_id;
  document.getElementById('rgm-progresso').textContent  =
    `Pedido ${index + 1} de ${_devQueue.length}`;

  // Limpa form
  document.getElementById('rgm-data').value   = new Date().toISOString().slice(0, 10);
  document.getElementById('rgm-motivo').value = '';
  document.getElementById('rgm-palete').value = '';
  document.getElementById('rgm-volume').value = '';
  document.getElementById('rgm-obs').value    = '';
  const erroEl = document.getElementById('rgm-erro');
  erroEl.classList.add('d-none');
  erroEl.textContent = '';

  const btnSalvar = document.getElementById('rgm-btn-salvar');
  btnSalvar.disabled = false;

  if (!_bsModal) {
    _bsModal = new bootstrap.Modal(document.getElementById('rg-modal-dev'));
  }
  _bsModal.show();
}

async function _salvarDevolucao() {
  const pedidoId = document.getElementById('rgm-pedido-id').value;
  const data     = document.getElementById('rgm-data').value;
  const motivo   = document.getElementById('rgm-motivo').value;
  const palete   = document.getElementById('rgm-palete').value;
  const volume   = document.getElementById('rgm-volume').value;
  const obs      = document.getElementById('rgm-obs').value;
  const erroEl   = document.getElementById('rgm-erro');
  const btnSalvar = document.getElementById('rgm-btn-salvar');

  erroEl.classList.add('d-none');

  if (!data) {
    erroEl.textContent = 'A data é obrigatória.';
    erroEl.classList.remove('d-none');
    return;
  }
  if (!motivo) {
    erroEl.textContent = 'O motivo é obrigatório.';
    erroEl.classList.remove('d-none');
    return;
  }

  const paleteNum = palete !== '' ? parseInt(palete, 10) : null;
  const volumeNum = volume !== '' ? parseInt(volume, 10) : null;

  if (palete !== '' && (!Number.isInteger(paleteNum) || paleteNum < 0 || paleteNum > 999)) {
    erroEl.textContent = 'Palete deve ser um número inteiro entre 0 e 999.';
    erroEl.classList.remove('d-none');
    return;
  }
  if (volume !== '' && (!Number.isInteger(volumeNum) || volumeNum < 0 || volumeNum > 999)) {
    erroEl.textContent = 'Volume deve ser um número inteiro entre 0 e 999.';
    erroEl.classList.remove('d-none');
    return;
  }
  if ((paleteNum ?? 0) === 0 && (volumeNum ?? 0) === 0) {
    erroEl.textContent = 'Pelo menos Palete ou Volume deve ser maior que 0.';
    erroEl.classList.remove('d-none');
    return;
  }

  btnSalvar.disabled = true;
  AppLoader.show();
  try {
    const resp = await fetch('/app/logistica/pedidos/dev/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({
        pedido_id: parseInt(pedidoId, 10),
        data,
        motivo,
        palete: paleteNum,
        volume: volumeNum,
        obs: obs || null,
      }),
    });
    const json = await resp.json();
    if (!json.success) {
      erroEl.textContent = json.mensagem || 'Erro ao salvar.';
      erroEl.classList.remove('d-none');
      btnSalvar.disabled = false;
      return;
    }
    // Avança para o próximo
    _abrirModal(_devIndex + 1);
  } catch {
    erroEl.textContent = 'Erro de comunicação com o servidor.';
    erroEl.classList.remove('d-none');
    btnSalvar.disabled = false;
  } finally {
    AppLoader.hide();
  }
}

// ─── Renderizar tabela única (sem agrupamento) ────────────────────────────────
function renderizarRelatorio(linhas, dataFmt, totalPedidos, totalPeso) {
  resultado.replaceChildren();
  vazio.classList.add('d-none');
  totalBar.classList.add('d-none');
  _devQueue = [];
  _ultimasLinhas = linhas;
  _ultimoDataFmt = dataFmt || '';

  if (!linhas.length) {
    vazio.classList.remove('d-none');
    btnImprimir.disabled = true;
    if (btnGmail) btnGmail.disabled = true;
    return;
  }

  tituloData.textContent = `Período: ${dataFmt}`;

  totalBar.textContent = `Total: ${totalPedidos} registro(s) | Peso total: ${totalPeso || 0}`;
  totalBar.classList.remove('d-none');

  const table = document.createElement('table');
  table.className = 'rg-tabela';

  const thead = document.createElement('thead');
  const trHead = document.createElement('tr');
  ['Data', 'Referência', 'T', 'D', 'Cidade', 'C. Postal', 'Vol', 'Peso', 'Estado', 'Mov', 'Dev', 'Armazém'].forEach(h => {
    const th = document.createElement('th');
    th.textContent = h;
    trHead.appendChild(th);
  });
  thead.appendChild(trHead);

  const tbody = document.createElement('tbody');
  linhas.forEach(linha => {
    const tr = document.createElement('tr');
    if (!linha.segue_para_entrega) tr.classList.add('rg-nao-segue');
    const estadoExibicao = resolverEstadoExibicao(linha);

    const volPartes = (linha.volumes || '').split('/');
    const volNegrito = volPartes.length === 2 && parseInt(volPartes[0], 10) < parseInt(volPartes[1], 10);

    const campos = [
      { val: linha.data_tentativa },
      { val: linha.pedido, linkReferencia: true, idVonzu: linha.id_vonzu },
      { val: linha.tipo, cls: linha.tipo === 'R' ? 'rg-tipo-r' : 'rg-tipo-e' },
      { val: linha.tem_devolucao ? '\u2022' : '', cls: linha.tem_devolucao ? 'rg-dev-sim' : '' },
      { val: linha.cidade_dest },
      { val: linha.codpost_dest },
      { val: linha.volumes, bold: volNegrito },
      { val: linha.peso },
      { val: estadoExibicao },
      { val: linha.mov },
      { val: linha.dev },
      { val: linha.armazem },
    ];

    campos.forEach(({ val, cls, bold, linkReferencia, idVonzu }) => {
      const td = document.createElement('td');
      if (linkReferencia) {
        const link = criarLinkVonzu(idVonzu, val);
        if (link) td.appendChild(link);
        else td.textContent = val ?? '';
      } else {
        td.textContent = val ?? '';
      }
      if (cls) td.className = cls;
      if (bold) td.style.fontWeight = 'bold';
      tr.appendChild(td);
    });

    tbody.appendChild(tr);
  });

  table.appendChild(thead);
  table.appendChild(tbody);

  const tableScroll = document.createElement('div');
  tableScroll.className = 'rg-tabela-scroll';
  tableScroll.appendChild(table);

  const wrapper = document.createElement('div');
  wrapper.className = 'rg-grupo';
  wrapper.appendChild(tableScroll);
  resultado.appendChild(wrapper);

  btnImprimir.disabled = false;
  if (btnGmail) btnGmail.disabled = false;
}

// ─── Buscar ───────────────────────────────────────────────────────────────────
async function buscar() {
  clearMessages();

  if (!validarFiltros()) return;

  const dataIni = inpDataIni.value;
  const dataFim = inpDataFim.value;

  if (!dataIni || !dataFim) {
    definirMensagem('erro', 'Informe a data inicial e a data final.', false);
    return;
  }

  loader.classList.remove('d-none');
  resultado.replaceChildren();
  vazio.classList.add('d-none');
  totalBar.classList.add('d-none');
  btnImprimir.disabled = true;
  if (btnGmail) btnGmail.disabled = true;
  _ultimasLinhas = [];
  AppLoader.show();

  try {
    const payload = {
      filtros: {
        data_inicial: dataIni,
        data_final:   dataFim,
        id_vonzu:     inpIdVonzu.value.trim(),
        referencia:   inpRef.value.trim(),
        tipo:         selTipo.value,
        estados:      getMultiSelectValues(selEstados),
        armazem:      selArmazem.value,
        conferencia:  selConferencia.value,
      },
    };

    const resp = await fetch(URL_BUSCAR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify(payload),
    });
    const json = await resp.json();

    if (!json.success) {
      definirMensagem('erro', json.mensagem || 'Erro ao buscar dados.', false);
      return;
    }

    renderizarRelatorio(
      json.linhas || [],
      json.data_fmt || '',
      json.total_pedidos || 0,
      json.total_peso || 0,
    );
  } catch {
    definirMensagem('erro', 'Erro de comunicação com o servidor.', false);
  } finally {
    loader.classList.add('d-none');
    AppLoader.hide();
  }
}

function referenciasUnicasDoRelatorio(linhas) {
  const vistas = new Set();
  const refs = [];
  (linhas || []).forEach(l => {
    const ref = String(l?.pedido ?? '').trim();
    if (!ref || vistas.has(ref)) return;
    vistas.add(ref);
    refs.push(ref);
  });
  return refs;
}

function filenameDeContentDisposition(header, fallback) {
  if (!header) return fallback;
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (star) {
    try {
      return decodeURIComponent(star[1].trim());
    } catch {
      return fallback;
    }
  }
  const quoted = /filename="([^"]+)"/i.exec(header);
  if (quoted) return quoted[1];
  const plain = /filename=([^;]+)/i.exec(header);
  if (plain) return plain[1].trim();
  return fallback;
}

function dispararDownloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function descarregarAnexosGmail() {
  clearMessages();
  if (!_podeDescarregarGmail()) {
    definirMensagem('erro', 'Sem permissão para descarregar anexos Gmail.', false);
    return;
  }
  const refs = referenciasUnicasDoRelatorio(_ultimasLinhas);
  if (!refs.length) {
    definirMensagem('aviso', 'Não há registros no relatório. Execute uma busca com resultados.', false);
    return;
  }
  if (!URL_ANEXO_GMAIL) {
    definirMensagem('erro', 'URL de anexos Gmail não configurada.', false);
    return;
  }

  btnGmail.disabled = true;
  AppLoader.show(0);

  let descarregados = 0;
  const refsSemEmail = [];
  const refsSemAnexo = [];
  const refsErro = [];
  const abortarCodigos = new Set([
    'gmail_nao_configurado',
    'sem_filial',
    'erro_api',
    'erro_credenciais',
  ]);
  let abortou = false;
  let mensagemAbort = '';

  try {
    for (let i = 0; i < refs.length; i += 1) {
      const referencia = refs[i];
      tituloData.textContent = `Anexos Gmail: ${i + 1}/${refs.length}`;
      try {
        const resp = await fetch(URL_ANEXO_GMAIL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
          body: JSON.stringify({ referencia }),
        });
        if (resp.status === 401 || resp.status === 403) {
          abortou = true;
          mensagemAbort = 'Sem permissão ou sessão expirada para descarregar anexos Gmail.';
          break;
        }
        const ctype = (resp.headers.get('Content-Type') || '').toLowerCase();
        if (resp.ok && !ctype.includes('application/json')) {
          const blob = await resp.blob();
          if (!blob.size) {
            refsErro.push(referencia);
            continue;
          }
          const nome = filenameDeContentDisposition(
            resp.headers.get('Content-Disposition'),
            `${referencia}.bin`,
          );
          dispararDownloadBlob(blob, nome);
          descarregados += 1;
        } else {
          let json = {};
          try {
            json = await resp.json();
          } catch {
            json = {};
          }
          const codigo = json.codigo || '';
          if (abortarCodigos.has(codigo)) {
            abortou = true;
            mensagemAbort = json.mensagem || 'Não foi possível consultar o Gmail.';
            break;
          }
          if (codigo === 'sem_email') refsSemEmail.push(referencia);
          else if (codigo === 'sem_anexo_permitido') refsSemAnexo.push(referencia);
          else refsErro.push(referencia);
        }
      } catch {
        refsErro.push(referencia);
      }
    }
  } finally {
    AppLoader.hide();
    btnGmail.disabled = false;
    if (_ultimoDataFmt) tituloData.textContent = `Período: ${_ultimoDataFmt}`;
  }

  if (abortou) {
    definirMensagem('erro', mensagemAbort, false);
    return;
  }

  function trechoComRefs(rotulo, lista) {
    if (!lista.length) return '';
    return `${lista.length} ${rotulo} (${lista.join(', ')})`;
  }

  const partes = [`${descarregados} descarregado(s)`];
  const semEmail = trechoComRefs('sem e-mail', refsSemEmail);
  const semAnexo = trechoComRefs('sem PDF/imagem', refsSemAnexo);
  const comErro = trechoComRefs('com erro', refsErro);
  if (semEmail) partes.push(semEmail);
  if (semAnexo) partes.push(semAnexo);
  if (comErro) partes.push(comErro);
  const tipo = descarregados > 0 && refsErro.length === 0 ? 'sucesso' : (descarregados > 0 ? 'aviso' : 'erro');
  definirMensagem(tipo, `Anexos Gmail: ${partes.join(', ')}.`, false);
}

// ─── Feedback em tempo real nos campos smart_filter ───────────────────────────
inpIdVonzu.addEventListener('input', () => {
  if (validateSmartNumber(inpIdVonzu.value)) {
    erroVonzu.classList.add('d-none');
    inpIdVonzu.classList.remove('is-invalid');
  }
});

inpRef.addEventListener('input', () => {
  if (validateSmartText(inpRef.value)) {
    erroRef.classList.add('d-none');
    inpRef.classList.remove('is-invalid');
  }
});

// ─── Inicialização ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  preencherEstados();
  preencherMotivos();

  if (_podeRegistrarDevolucoes()) {
    colBtnDev.classList.remove('d-none');
  }
  if (_podeDescarregarGmail() && colBtnGmail) {
    colBtnGmail.classList.remove('d-none');
  }

  // Inicializar tooltips Bootstrap
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
    new bootstrap.Tooltip(el);
  });
});

// ─── Eventos ─────────────────────────────────────────────────────────────────
form.addEventListener('submit', e => { e.preventDefault(); buscar(); });
btnImprimir.addEventListener('click', () => window.print());
if (btnGmail) {
  btnGmail.addEventListener('click', () => { descarregarAnexosGmail(); });
}
btnRegistrarDev.addEventListener('click', () => {
  _coletarFilaDev(_ultimasLinhas);
  if (!_devQueue.length) {
    definirMensagem('aviso', 'Não há registros no relatório. Execute uma busca com resultados.', false);
    return;
  }
  _abrirModal(0);
});
document.getElementById('rgm-btn-salvar').addEventListener('click', _salvarDevolucao);
document.getElementById('rgm-btn-pular').addEventListener('click', () => _abrirModal(_devIndex + 1));
