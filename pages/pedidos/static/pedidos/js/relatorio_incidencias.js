import { getCsrfToken, clearMessages, definirMensagem } from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';

const root = document.getElementById('ri-root');
const URL_BUSCAR = root?.dataset?.urlBuscar ?? '';
const URL_FOTO_ADD = root?.dataset?.urlFotoAdd ?? '';
const URL_FOTO_DEL = root?.dataset?.urlFotoDel ?? '';

const form = document.getElementById('ri-form');
const inpDataIni = document.getElementById('ri-data-ini');
const inpDataFim = document.getElementById('ri-data-fim');
const selOrigem = document.getElementById('ri-origem');
const selMotorista = document.getElementById('ri-motorista');
const chkAgruparMot = document.getElementById('ri-agrupar-motorista');
const wrapGrupos = document.getElementById('ri-wrap-grupos');
const loader = document.getElementById('ri-loader');
const vazio = document.getElementById('ri-vazio');
const tituloPeriodo = document.getElementById('ri-titulo-periodo');
const totalBar = document.getElementById('ri-total-bar');
const btnImprimir = document.getElementById('ri-btn-imprimir');
const uploadArea = document.getElementById('rim-upload-area');

const _MAX_FOTO_BYTES = 2 * 1024 * 1024;
const _MAX_DIM = 1920;
const modalFotosEl = document.getElementById('ri-modal-fotos');

let _podeEditarFotos = false;
let _fotosAtuais = [];
let _incIdAtual = null;
let _bsModalFotos = null;
let _btnFotosTrigger = null;
let _agruparMotorista = false;

function initModalFotos() {
  if (!modalFotosEl || modalFotosEl.dataset.riModalInit) return;
  modalFotosEl.dataset.riModalInit = '1';
  modalFotosEl.addEventListener('hide.bs.modal', () => {
    const alvo = _btnFotosTrigger;
    if (alvo && typeof alvo.focus === 'function') {
      alvo.focus({ preventScroll: true });
      return;
    }
    const ativo = document.activeElement;
    if (ativo && modalFotosEl.contains(ativo) && typeof ativo.blur === 'function') {
      ativo.blur();
    }
  });
  modalFotosEl.addEventListener('hidden.bs.modal', () => {
    _btnFotosTrigger = null;
  });
  _bsModalFotos = new bootstrap.Modal(modalFotosEl);
}

function aplicarPermissoesFotos() {
  const dados = window.sisDados || {};
  const perms = dados.permissions?.relatorio_incidencias || {};
  _podeEditarFotos = Boolean(perms.editar);
  if (_podeEditarFotos && uploadArea) {
    uploadArea.classList.remove('d-none');
  }
}

function renderFotosGrid(fotos) {
  const grid = document.getElementById('rim-fotos-grid');
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

    wrapper.appendChild(img);
    if (_podeEditarFotos) {
      const btnDel = document.createElement('button');
      btnDel.type = 'button';
      btnDel.className = 'btn btn-danger btn-sm position-absolute top-0 end-0 m-1';
      btnDel.title = 'Excluir foto';
      const icone = document.createElement('i');
      icone.className = 'bi bi-trash';
      btnDel.appendChild(icone);
      btnDel.addEventListener('click', () => _confirmarExcluirFoto(foto.id));
      wrapper.appendChild(btnDel);
    }
    col.appendChild(wrapper);
    grid.appendChild(col);
  });
}

function _atualizarBotaoNaTabela(incId, fotos) {
  const btn = root?.querySelector(`.btn-ri-fotos[data-id="${incId}"]`);
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

function abrirModalFotos(reg) {
  _incIdAtual = reg.id;
  _fotosAtuais = reg.fotos ? [...reg.fotos] : [];

  document.getElementById('rim-pedido').textContent = reg.pedido ?? '';
  document.getElementById('rim-data').textContent = reg.data ?? '';
  document.getElementById('rim-tipo').textContent = reg.tipo ?? '';

  renderFotosGrid(_fotosAtuais);
  document.getElementById('rim-progresso').classList.add('d-none');
  document.getElementById('rim-fotos-input').value = '';
  document.getElementById('rim-camera-input').value = '';

  initModalFotos();
  _bsModalFotos?.show();
}

function _comprimirImagem(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        let { width, height } = img;
        if (width > _MAX_DIM || height > _MAX_DIM) {
          const ratio = Math.min(_MAX_DIM / width, _MAX_DIM / height);
          width = Math.round(width * ratio);
          height = Math.round(height * ratio);
        }
        const canvas = document.createElement('canvas');
        canvas.width = width;
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

async function adicionarFotos(files) {
  if (!_incIdAtual || !files.length || !_podeEditarFotos) return;

  const progresso = document.getElementById('rim-progresso');
  const barra = document.getElementById('rim-barra');
  const status = document.getElementById('rim-status');
  progresso.classList.remove('d-none');

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    status.textContent = `Processando ${i + 1}/${files.length}: ${file.name}…`;
    barra.style.width = `${Math.round((i / files.length) * 100)}%`;

    let b64;
    try {
      b64 = await _comprimirImagem(file);
    } catch (err) {
      definirMensagem('erro', err.message, false);
      continue;
    }

    AppLoader.show();
    try {
      const resp = await fetch(URL_FOTO_ADD, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ inc_id: _incIdAtual, imagem_b64: b64 }),
      });
      const json = await resp.json();
      if (json.success && json.foto) {
        _fotosAtuais.push(json.foto);
        renderFotosGrid(_fotosAtuais);
        _atualizarBotaoNaTabela(_incIdAtual, _fotosAtuais);
      } else {
        definirMensagem('erro', json.mensagem || 'Erro ao enviar foto.', false);
      }
    } catch {
      definirMensagem('erro', 'Erro de comunicação ao enviar foto.', false);
    } finally {
      AppLoader.hide();
    }
  }

  barra.style.width = '100%';
  status.textContent = 'Concluído.';
  setTimeout(() => progresso.classList.add('d-none'), 1500);
  document.getElementById('rim-fotos-input').value = '';
  document.getElementById('rim-camera-input').value = '';
}

function _confirmarExcluirFoto(imgbbId) {
  if (!confirm('Tem certeza que deseja excluir esta foto?')) return;
  _excluirFoto(imgbbId);
}

async function _excluirFoto(imgbbId) {
  AppLoader.show();
  try {
    const resp = await fetch(URL_FOTO_DEL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ inc_id: _incIdAtual, imgbb_id: imgbbId }),
    });
    const json = await resp.json();
    if (json.success) {
      _fotosAtuais = _fotosAtuais.filter(f => f.id !== imgbbId);
      renderFotosGrid(_fotosAtuais);
      _atualizarBotaoNaTabela(_incIdAtual, _fotosAtuais);
    } else {
      definirMensagem('erro', json.mensagem || 'Erro ao excluir foto.', false);
    }
  } catch {
    definirMensagem('erro', 'Erro de comunicação ao excluir foto.', false);
  } finally {
    AppLoader.hide();
  }
}

function criarCabecalhoTabela(ocultarMotorista) {
  const thead = document.createElement('thead');
  const tr = document.createElement('tr');
  const labels = ['Pedido', 'Data', 'Tipo', 'Artigo', 'Valor'];
  if (!ocultarMotorista) labels.push('Motorista');
  labels.push('Obs.', 'Registado em', 'Fotos');
  labels.forEach(txt => {
    const th = document.createElement('th');
    th.textContent = txt;
    tr.appendChild(th);
  });
  thead.appendChild(tr);
  return thead;
}

function anexarLinha(tbody, reg, ocultarMotorista) {
  const tr = document.createElement('tr');
  const campos = [
    { val: reg.pedido },
    { val: reg.data },
    { val: reg.tipo },
    { val: reg.artigo || '—' },
    { val: reg.valor_fmt || reg.valor || '—' },
  ];
  if (!ocultarMotorista) campos.push({ val: reg.motorista || '—' });
  campos.push({ val: reg.obs || '', cls: 'ri-obs' }, { val: reg.created_at_fmt || '' });

  campos.forEach(({ val, cls }) => {
    const td = document.createElement('td');
    td.textContent = val ?? '';
    if (cls) td.className = cls;
    tr.appendChild(td);
  });

  const tdFotos = document.createElement('td');
  const btnFotos = document.createElement('button');
  btnFotos.type = 'button';
  btnFotos.className = 'btn btn-outline-secondary btn-sm btn-ri-fotos';
  btnFotos.dataset.id = reg.id;
  btnFotos.dataset.fotos = JSON.stringify(reg.fotos || []);
  const ico = document.createElement('i');
  ico.className = 'bi bi-images';
  btnFotos.appendChild(ico);
  if (reg.fotos_count > 0) {
    const badge = document.createElement('span');
    badge.className = 'badge text-bg-info ms-1';
    badge.textContent = String(reg.fotos_count);
    btnFotos.appendChild(badge);
  }
  btnFotos.addEventListener('click', (e) => {
    _btnFotosTrigger = e.currentTarget;
    abrirModalFotos(reg);
  });
  tdFotos.appendChild(btnFotos);
  tr.appendChild(tdFotos);
  tbody.appendChild(tr);
}

function montarTabela(linhas, opts = {}) {
  const { ocultarMotorista = false } = opts;

  const scroll = document.createElement('div');
  scroll.className = 'ri-tabela-scroll';

  const table = document.createElement('table');
  table.className = 'ri-tabela';
  table.appendChild(criarCabecalhoTabela(ocultarMotorista));

  const tbody = document.createElement('tbody');
  linhas.forEach(reg => anexarLinha(tbody, reg, ocultarMotorista));
  table.appendChild(tbody);

  scroll.appendChild(table);
  return scroll;
}

function renderGrupos(gruposOrigem, agruparMotorista) {
  wrapGrupos.replaceChildren();
  _agruparMotorista = agruparMotorista;

  gruposOrigem.forEach(grupo => {
    const box = document.createElement('div');
    box.className = 'ri-grupo';

    const header = document.createElement('div');
    header.className = 'ri-grupo-header';
    header.textContent = `Origem: ${grupo.origem}`;
    const badgeQtd = document.createElement('span');
    badgeQtd.className = 'ri-badge';
    badgeQtd.textContent = `${grupo.total} reg.`;
    header.appendChild(badgeQtd);
    const badgeVal = document.createElement('span');
    badgeVal.className = 'ri-badge';
    badgeVal.textContent = `Valor: ${grupo.valor_total_fmt}`;
    header.appendChild(badgeVal);
    box.appendChild(header);

    if (agruparMotorista && grupo.subgrupos) {
      grupo.subgrupos.forEach(sub => {
        const subHdr = document.createElement('div');
        subHdr.className = 'ri-subgrupo-header';
        subHdr.textContent = sub.motorista_nome;
        const subBadgeQtd = document.createElement('span');
        subBadgeQtd.className = 'ri-badge ms-2';
        subBadgeQtd.style.background = 'rgba(26, 58, 92, .12)';
        subBadgeQtd.style.color = '#1a3a5c';
        subBadgeQtd.textContent = `${sub.total} reg.`;
        subHdr.appendChild(subBadgeQtd);
        const subBadgeVal = document.createElement('span');
        subBadgeVal.className = 'ri-badge ms-1';
        subBadgeVal.style.background = 'rgba(26, 58, 92, .12)';
        subBadgeVal.style.color = '#1a3a5c';
        subBadgeVal.textContent = `Valor: ${sub.valor_total_fmt}`;
        subHdr.appendChild(subBadgeVal);
        box.appendChild(subHdr);
        box.appendChild(montarTabela(sub.linhas, { ocultarMotorista: true }));
      });
    } else if (grupo.linhas) {
      box.appendChild(montarTabela(grupo.linhas, { ocultarMotorista: false }));
    }

    wrapGrupos.appendChild(box);
  });
}

function renderizarResultado(data) {
  const grupos = data.grupos_origem || [];
  const total = data.total || 0;
  const periodoTexto = data.periodo_texto || '';
  const valorGeral = data.valor_total_fmt || '0,00';

  vazio.classList.add('d-none');
  wrapGrupos.classList.add('d-none');
  totalBar.classList.add('d-none');
  btnImprimir.disabled = true;

  if (!total) {
    vazio.classList.remove('d-none');
    tituloPeriodo.textContent = '';
    return;
  }

  tituloPeriodo.textContent = periodoTexto ? `Período: ${periodoTexto}` : '';
  totalBar.textContent =
    `Total: ${total} incidência(s) — Valor total: ${valorGeral}`;
  totalBar.classList.remove('d-none');

  renderGrupos(grupos, Boolean(data.agrupar_motorista));
  wrapGrupos.classList.remove('d-none');
  btnImprimir.disabled = false;
}

async function buscar() {
  clearMessages();

  const dataIni = inpDataIni.value;
  const dataFim = inpDataFim.value;
  if (!dataIni || !dataFim) {
    definirMensagem('erro', 'Informe a data inicial e a data final.', false);
    return;
  }

  loader.classList.remove('d-none');
  wrapGrupos.replaceChildren();
  wrapGrupos.classList.add('d-none');
  vazio.classList.add('d-none');
  totalBar.classList.add('d-none');
  btnImprimir.disabled = true;
  AppLoader.show();

  try {
    const filtros = {
      data_inicial: dataIni,
      data_final: dataFim,
      origem: selOrigem.value,
      agrupar_motorista: chkAgruparMot?.checked === true,
    };
    if (selMotorista.value) {
      filtros.motorista_id = selMotorista.value;
    }

    const resp = await fetch(URL_BUSCAR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ filtros }),
    });
    const json = await resp.json();

    if (!json.success) {
      definirMensagem('erro', json.mensagem || 'Erro ao buscar dados.', false);
      return;
    }

    renderizarResultado(json);
  } catch {
    definirMensagem('erro', 'Erro de comunicação com o servidor.', false);
  } finally {
    loader.classList.add('d-none');
    AppLoader.hide();
  }
}

form.addEventListener('submit', e => { e.preventDefault(); buscar(); });
btnImprimir.addEventListener('click', () => window.print());

document.getElementById('rim-fotos-input').addEventListener('change', e => {
  if (e.target.files.length) adicionarFotos(e.target.files);
});
document.getElementById('rim-camera-input').addEventListener('change', e => {
  if (e.target.files.length) adicionarFotos(e.target.files);
});

document.addEventListener('DOMContentLoaded', () => {
  AppLoader.init();
  aplicarPermissoesFotos();
  initModalFotos();
});
