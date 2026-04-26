import { getCsrfToken, clearMessages, definirMensagem } from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';
import {
  parseSmartText,
  validateSmartText,
} from '/static/js/smart_filter.js';

const root       = document.getElementById('rd-root');
const URL_BUSCAR  = root?.dataset?.urlBuscar  ?? '';
const URL_GSHEETS = root?.dataset?.urlGsheets ?? '';

const form        = document.getElementById('rd-form');
const inpDataIni  = document.getElementById('rd-data-ini');
const inpDataFim  = document.getElementById('rd-data-fim');
const inpRef      = document.getElementById('rd-referencia');
const erroRef     = document.getElementById('rd-referencia-erro');
const tbody       = document.getElementById('rd-tbody');
const tabela      = document.getElementById('rd-tabela');
const loader      = document.getElementById('rd-loader');
const vazio       = document.getElementById('rd-vazio');
const tituloData  = document.getElementById('rd-titulo-data');
const totalBar    = document.getElementById('rd-total-bar');
const btnImprimir = document.getElementById('rd-btn-imprimir');
const btnDrive    = document.getElementById('rd-btn-drive');
const checkAll    = document.getElementById('rd-check-all');

// Estado dos registros carregados
let _registrosAtuais = [];

// ── Constantes para compressão de imagem ────────────────────────────────────
const _MAX_FOTO_BYTES = 2 * 1024 * 1024; // 2 MB
const _MAX_DIM = 1920;

// ── Estado do modal de fotos ─────────────────────────────────────────────────
let _fotosAtuais  = [];
let _devIdAtual   = null;
let _bsModalFotos = null;

// ── Validação smart filter ───────────────────────────────────────────────────
function validarFiltros() {
  if (!validateSmartText(inpRef.value)) {
    erroRef.classList.remove('d-none');
    inpRef.classList.add('is-invalid');
    return false;
  }
  erroRef.classList.add('d-none');
  inpRef.classList.remove('is-invalid');
  return true;
}

inpRef.addEventListener('input', () => {
  if (validateSmartText(inpRef.value)) {
    erroRef.classList.add('d-none');
    inpRef.classList.remove('is-invalid');
  }
});

// ── Renderizar grid de fotos no modal ────────────────────────────────────────
function renderFotosGrid(fotos) {
  const grid = document.getElementById('rdm-fotos-grid');
  grid.replaceChildren();
  if (!fotos.length) {
    const p = document.createElement('p');
    p.className = 'text-muted col-12';
    p.textContent = 'Nenhuma foto adicionada.';
    grid.appendChild(p);
    return;
  }
  fotos.forEach(foto => {
    const col = document.createElement('div');
    col.className = 'col-6 col-md-3';

    const wrapper = document.createElement('div');
    wrapper.className = 'position-relative';

    const img = document.createElement('img');
    img.src = foto.thumb_url || foto.url;
    img.alt = '';
    img.className = 'img-fluid rounded border';
    img.title = 'Ver em tamanho real';
    img.style.cursor = 'pointer';
    img.addEventListener('click', () => window.open(foto.url, '_blank', 'noopener,noreferrer'));

    const btnDel = document.createElement('button');
    btnDel.type = 'button';
    btnDel.className = 'btn btn-danger btn-sm position-absolute top-0 end-0 m-1';
    btnDel.dataset.imgbbId = foto.id;
    btnDel.title = 'Excluir foto';
    const icone = document.createElement('i');
    icone.className = 'bi bi-trash';
    btnDel.appendChild(icone);
    btnDel.addEventListener('click', () => _confirmarExcluirFoto(foto.id));

    wrapper.appendChild(img);
    wrapper.appendChild(btnDel);
    col.appendChild(wrapper);
    grid.appendChild(col);
  });
}

// ── Atualiza botão de fotos na tabela após mudança ───────────────────────────
function _atualizarBotaoNaTabela(devId, fotos) {
  const btn = tbody.querySelector(`.btn-rd-fotos[data-id="${devId}"]`);
  if (!btn) return;
  btn.dataset.fotos = JSON.stringify(fotos);
  const badge = btn.querySelector('.badge');
  if (fotos.length > 0) {
    if (badge) {
      badge.textContent = String(fotos.length);
    } else {
      const novoBadge = document.createElement('span');
      novoBadge.className = 'badge text-bg-info ms-1';
      novoBadge.textContent = String(fotos.length);
      btn.appendChild(novoBadge);
    }
  } else if (badge) {
    badge.remove();
  }
}

// ── Abrir modal de fotos ─────────────────────────────────────────────────────
function abrirModalFotos(devId, referencia, dataDev, motivo, fotos) {
  _devIdAtual  = devId;
  _fotosAtuais = fotos ? [...fotos] : [];

  document.getElementById('rdm-referencia').textContent = referencia;
  document.getElementById('rdm-data-dev').textContent   = dataDev;
  document.getElementById('rdm-motivo').textContent     = motivo;

  renderFotosGrid(_fotosAtuais);
  document.getElementById('rdm-progresso').classList.add('d-none');
  document.getElementById('rdm-fotos-input').value  = '';
  document.getElementById('rdm-camera-input').value = '';

  if (!_bsModalFotos) {
    _bsModalFotos = new bootstrap.Modal(document.getElementById('rd-modal-fotos'));
  }
  _bsModalFotos.show();
}

// ── Comprimir imagem para base64 ─────────────────────────────────────────────
function _comprimirImagem(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        let { width, height } = img;
        if (width > _MAX_DIM || height > _MAX_DIM) {
          const ratio = Math.min(_MAX_DIM / width, _MAX_DIM / height);
          width  = Math.round(width * ratio);
          height = Math.round(height * ratio);
        }
        const canvas = document.createElement('canvas');
        canvas.width  = width;
        canvas.height = height;
        canvas.getContext('2d').drawImage(img, 0, 0, width, height);
        let qualidade = 0.85;
        let b64 = '';
        while (qualidade >= 0.40) {
          const dataUrl = canvas.toDataURL('image/jpeg', qualidade);
          b64 = dataUrl.split(',')[1];
          const bytes = Math.ceil((b64.length * 3) / 4);
          if (bytes <= _MAX_FOTO_BYTES) break;
          qualidade -= 0.10;
        }
        if (!b64) {
          reject(new Error('Não foi possível comprimir a imagem para menos de 2 MB.'));
          return;
        }
        resolve(b64);
      };
      img.onerror = () => reject(new Error('Arquivo inválido.'));
      img.src = e.target.result;
    };
    reader.onerror = () => reject(new Error('Erro ao ler arquivo.'));
    reader.readAsDataURL(file);
  });
}

// ── Adicionar fotos ──────────────────────────────────────────────────────────
async function adicionarFotos(files) {
  if (!_devIdAtual || !files.length) return;

  const progresso = document.getElementById('rdm-progresso');
  const barra     = document.getElementById('rdm-barra');
  const status    = document.getElementById('rdm-status');
  progresso.classList.remove('d-none');

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    status.textContent = `Processando ${i + 1}/${files.length}: ${file.name}…`;
    barra.style.width  = `${Math.round((i / files.length) * 100)}%`;

    let b64;
    try {
      b64 = await _comprimirImagem(file);
    } catch (err) {
      definirMensagem('erro', err.message, false);
      continue;
    }

    AppLoader.show();
    try {
      const resp = await fetch('/app/logistica/pedidos/dev/foto/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ dev_id: _devIdAtual, imagem_b64: b64 }),
      });
      const json = await resp.json();
      if (json.success && json.foto) {
        _fotosAtuais.push(json.foto);
        renderFotosGrid(_fotosAtuais);
        _atualizarBotaoNaTabela(_devIdAtual, _fotosAtuais);
      } else {
        definirMensagem('erro', json.mensagem || 'Erro ao enviar foto.', false);
      }
    } catch {
      definirMensagem('erro', 'Erro de comunicação ao enviar foto.', false);
    } finally {
      AppLoader.hide();
    }
  }

  barra.style.width  = '100%';
  status.textContent = 'Concluído.';
  setTimeout(() => progresso.classList.add('d-none'), 1500);
  document.getElementById('rdm-fotos-input').value  = '';
  document.getElementById('rdm-camera-input').value = '';
}

// ── Confirmar e excluir foto ─────────────────────────────────────────────────
function _confirmarExcluirFoto(imgbbId) {
  if (!confirm('Tem certeza que deseja excluir esta foto?')) return;
  _excluirFoto(imgbbId);
}

async function _excluirFoto(imgbbId) {
  AppLoader.show();
  try {
    const resp = await fetch('/app/logistica/pedidos/dev/foto/del', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ dev_id: _devIdAtual, imgbb_id: imgbbId }),
    });
    const json = await resp.json();
    if (json.success) {
      _fotosAtuais = _fotosAtuais.filter(f => f.id !== imgbbId);
      renderFotosGrid(_fotosAtuais);
      _atualizarBotaoNaTabela(_devIdAtual, _fotosAtuais);
    } else {
      definirMensagem('erro', json.mensagem || 'Erro ao excluir foto.', false);
    }
  } catch {
    definirMensagem('erro', 'Erro de comunicação ao excluir foto.', false);
  } finally {
    AppLoader.hide();
  }
}

// ── Renderizar tabela ────────────────────────────────────────────────────────
function renderizarTabela(registros, dataFmt, total) {
  _registrosAtuais = registros;
  tbody.replaceChildren();
  vazio.classList.add('d-none');
  tabela.classList.add('d-none');
  totalBar.classList.add('d-none');
  btnImprimir.disabled = true;
  btnDrive.disabled    = true;
  checkAll.checked     = false;

  if (!registros.length) {
    vazio.classList.remove('d-none');
    return;
  }

  tituloData.textContent = `Período: ${dataFmt}`;
  totalBar.textContent   = `Total: ${total} devolução(ões)`;
  totalBar.classList.remove('d-none');

  registros.forEach(reg => {
    const tr = document.createElement('tr');

    // Coluna checkbox
    const tdCheck = document.createElement('td');
    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.dataset.id = reg.id;
    chk.classList.add('rd-row-check');
    tdCheck.appendChild(chk);
    tr.appendChild(tdCheck);

    const tipoLabel = (reg.tipo || '').toUpperCase() === 'RECOLHA' ? 'R' : 'E';
    const tipoCls   = tipoLabel === 'R' ? 'rd-tipo-r' : 'rd-tipo-e';

    const campos = [
      { val: reg.data },
      { val: reg.referencia },
      { val: tipoLabel, cls: tipoCls },
      { val: reg.motivo },
      { val: reg.palete != null ? reg.palete : '—' },
      { val: reg.volume != null ? reg.volume : '—' },
      { val: reg.obs, cls: 'rd-obs' },
    ];

    campos.forEach(({ val, cls }) => {
      const td = document.createElement('td');
      td.textContent = val ?? '';
      if (cls) td.className = cls;
      tr.appendChild(td);
    });

    // Coluna fotos
    const tdFotos = document.createElement('td');
    const btnFotos = document.createElement('button');
    btnFotos.type = 'button';
    btnFotos.className = 'btn btn-outline-secondary btn-sm btn-rd-fotos';
    btnFotos.dataset.id    = reg.id;
    btnFotos.dataset.fotos = JSON.stringify(reg.fotos || []);
    const icoFotos = document.createElement('i');
    icoFotos.className = 'bi bi-images';
    btnFotos.appendChild(icoFotos);
    if (reg.fotos_count > 0) {
      const badge = document.createElement('span');
      badge.className = 'badge text-bg-info ms-1';
      badge.textContent = String(reg.fotos_count);
      btnFotos.appendChild(badge);
    }
    btnFotos.addEventListener('click', () => {
      const fotos = JSON.parse(btnFotos.dataset.fotos || '[]');
      abrirModalFotos(reg.id, reg.referencia, reg.data, reg.motivo, fotos);
    });
    tdFotos.appendChild(btnFotos);
    tr.appendChild(tdFotos);

    // Coluna driver (enviado ao GSheets)
    const tdDriver = document.createElement('td');
    tdDriver.className = 'text-center';
    tdDriver.dataset.driverId = reg.id;
    const ico = document.createElement('i');
    ico.className = reg.driver
      ? 'bi bi-cloud-check-fill text-success'
      : 'bi bi-cloud text-secondary';
    ico.title = reg.driver ? 'Enviado ao Google Sheets' : 'Não enviado';
    tdDriver.appendChild(ico);
    tr.appendChild(tdDriver);

    tbody.appendChild(tr);
  });

  tabela.classList.remove('d-none');
  btnImprimir.disabled = false;
  btnDrive.disabled    = false;
}

// ── Enviar ao Google Sheets ───────────────────────────────────────────────────
async function enviarAoDrive() {
  const checked = [...tbody.querySelectorAll('.rd-row-check:checked')];
  const ids = checked.length
    ? checked.map(c => Number(c.dataset.id))
    : _registrosAtuais.map(r => r.id);

  if (!ids.length) {
    definirMensagem('aviso', 'Selecione ao menos um registro para enviar.', false);
    return;
  }

  clearMessages();
  AppLoader.show();
  btnDrive.disabled = true;
  try {
    const resp = await fetch(URL_GSHEETS, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ ids }),
    });
    const json = await resp.json();
    if (!json.success) {
      definirMensagem('erro', json.mensagem || 'Erro ao enviar.', false);
      return;
    }
    // Actualiza ícones de driver na tabela
    (json.ids_enviados || []).forEach(id => {
      const cell = tbody.querySelector(`[data-driver-id="${id}"]`);
      if (cell) {
        const ico = cell.querySelector('i');
        if (ico) {
          ico.className = 'bi bi-cloud-check-fill text-success';
          ico.title = 'Enviado ao Google Sheets';
        }
      }
      // actualiza estado local
      const reg = _registrosAtuais.find(r => r.id === id);
      if (reg) reg.driver = true;
    });
    // desmarca checkboxes
    tbody.querySelectorAll('.rd-row-check').forEach(c => { c.checked = false; });
    checkAll.checked = false;
    definirMensagem('sucesso', json.mensagem || 'Enviado com sucesso.', false);
  } catch {
    definirMensagem('erro', 'Erro de comunicação com o servidor.', false);
  } finally {
    AppLoader.hide();
    btnDrive.disabled = false;
  }
}

// ── Buscar ───────────────────────────────────────────────────────────────────
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
  tbody.replaceChildren();
  tabela.classList.add('d-none');
  vazio.classList.add('d-none');
  totalBar.classList.add('d-none');
  btnImprimir.disabled = true;
  AppLoader.show();

  try {
    const payload = {
      filtros: {
        data_inicial: dataIni,
        data_final:   dataFim,
        referencia:   inpRef.value.trim(),
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

    renderizarTabela(json.registros || [], json.data_fmt || '', json.total || 0);
  } catch {
    definirMensagem('erro', 'Erro de comunicação com o servidor.', false);
  } finally {
    loader.classList.add('d-none');
    AppLoader.hide();
  }
}

// ── Eventos ──────────────────────────────────────────────────────────────────
form.addEventListener('submit', e => { e.preventDefault(); buscar(); });
btnImprimir.addEventListener('click', () => window.print());
btnDrive.addEventListener('click', enviarAoDrive);

checkAll.addEventListener('change', () => {
  tbody.querySelectorAll('.rd-row-check').forEach(c => { c.checked = checkAll.checked; });
});

tbody.addEventListener('change', e => {
  if (e.target.classList.contains('rd-row-check')) {
    const all = [...tbody.querySelectorAll('.rd-row-check')];
    checkAll.checked = all.every(c => c.checked);
  }
});

document.getElementById('rdm-fotos-input').addEventListener('change', e => {
  if (e.target.files.length) adicionarFotos(e.target.files);
});
document.getElementById('rdm-camera-input').addEventListener('change', e => {
  if (e.target.files.length) adicionarFotos(e.target.files);
});

// ── Inicialização ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
    new bootstrap.Tooltip(el);
  });
  AppLoader.init();
});
