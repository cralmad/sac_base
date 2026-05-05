import {
  updateFormField,
  getForm,
  updateState,
  clearMessages,
  definirMensagem,
  hidratarFormulario,
  setFormState,
  confirmar,
  getOptions,
  getScreenPermissions,
  getDataset,
  getDataBackEnd,
} from '/static/js/sisVar.js';
import { fazerRequisicao } from '/static/js/base.js';
import { initSmartInputs } from '/static/js/input_rules.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { AppLoader } from '/static/js/loader.js';

AppLoader.show();
document.addEventListener('DOMContentLoaded', () => AppLoader.hide());

const nomeForm = 'cadPedido';
const nomeCons = 'consPedido';
const form = document.getElementById(nomeForm);
const formCons = document.getElementById(nomeCons);
const tabelaMovCorpo = document.getElementById('tabela-mov-corpo');
const tabelaDevCorpo = document.getElementById('tabela-dev-corpo');
const tabelaIncCorpo = document.getElementById('tabela-inc-corpo');
const tabelaPedidoCorpo = document.getElementById('tabela-pedido-corpo');
const modalMovEl = document.getElementById('modalMov');
const modalMov = new bootstrap.Modal(modalMovEl);
const modalDevEl = document.getElementById('modalDev');
const modalDev = new bootstrap.Modal(modalDevEl);
const modalIncEl = document.getElementById('modalInc');
const modalInc = new bootstrap.Modal(modalIncEl);
const modalFotosEl = document.getElementById('modalFotos');
const modalFotos = new bootstrap.Modal(modalFotosEl);

const CAMPOS_TRAVADOS_IMPORTADO = ['filial_id', 'origem', 'id_vonzu', 'pedido', 'tipo', 'criado', 'cliente_id'];

getDataBackEnd();

function permissoes() {
  return getScreenPermissions('pedido', {
    acessar: false,
    consultar: false,
    incluir: false,
    editar: false,
    excluir: false,
    importar: false,
  });
}

function pode(acao) {
  return Boolean(permissoes()?.[acao]);
}

function podeAplicarEstiloSomenteLeitura(elemento) {
  return elemento && !['checkbox', 'radio'].includes(elemento.type);
}

function preencherSelect(id, lista, optLabel = 'Selecione', map = x => ({ value: x.value, label: x.label })) {
  const sel = document.getElementById(id);
  if (!sel) return;
  sel.innerHTML = '';
  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = optLabel;
  sel.appendChild(defaultOption);
  lista.forEach(item => {
    const { value, label } = map(item);
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = label;
    sel.appendChild(opt);
  });
}

function preencherFiliais() {
  const filiais = getDataset('filiais_escrita', []);
  const map = f => ({ value: f.id, label: `${f.codigo} - ${f.nome}` });
  preencherSelect('filial_id', filiais, 'Selecione', map);
  preencherSelect('filial_cons', filiais, 'Todas', map);
}

function preencherClientes() {
  const clientes = getOptions('clientes', []);
  preencherSelect('cliente_id', clientes, 'Selecione', c => ({ value: c.id, label: `${c.codigo || '-'} - ${c.nome}` }));
}

function preencherTipos() {
  const tipos = getOptions('tipos', []);
  preencherSelect('tipo', tipos, 'Selecione', t => ({ value: t.value, label: t.label }));
}

function preencherEstados() {
  const estados = getOptions('estados', []);
  preencherSelect('estado', estados, 'Selecione', e => ({ value: e.value, label: e.label }));
  preencherSelect('estado_cons', estados, 'Todos', e => ({ value: e.value, label: e.label }));
  preencherSelect('mov_estado', estados, 'Selecione', e => ({ value: e.value, label: e.label }));
}

function preencherPeriodosMov() {
  const periodos = getOptions('periodos_mov', []);
  preencherSelect('mov_periodo', periodos, 'Selecione', p => ({ value: p.value, label: p.label }));
}

function preencherOrigens() {
  const origens = getOptions('origens', []);
  preencherSelect('origem_cons', origens, 'Todas', o => ({ value: o.value, label: o.label }));
}

function preencherMotivosDev() {
  const motivos = getOptions('motivos_dev', []);
  preencherSelect('dev_motivo', motivos, 'Selecione', m => ({ value: m.value, label: m.label }));
}

function resolverEstadoExibicao(registro) {
  return registro?.estado_label || registro?.estado || '';
}

function renderDevolucoes(registros = []) {
  tabelaDevCorpo.innerHTML = '';
  if (!registros.length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 8;
    td.className = 'text-center text-muted';
    td.textContent = 'Nenhuma devolução';
    tr.appendChild(td);
    tabelaDevCorpo.appendChild(tr);
    aplicarTravasDevolucoes();
    return;
  }

  registros.forEach(d => {
    const tr = document.createElement('tr');

    const colunas = [d.id, d.data, d.palete, d.volume, d.motivo, d.obs];
    colunas.forEach(valor => {
      const td = document.createElement('td');
      td.textContent = String(valor ?? '');
      tr.appendChild(td);
    });

    const tdAcoes = document.createElement('td');
    tdAcoes.className = 'text-center';

    const btnFotos = document.createElement('button');
    btnFotos.type = 'button';
    btnFotos.className = 'btn btn-sm btn-outline-info me-1 btn-dev-fotos';
    const iconeFotos = document.createElement('i');
    iconeFotos.className = 'bi bi-images';
    btnFotos.appendChild(iconeFotos);
    if (d.fotos_count > 0) {
      const badge = document.createElement('span');
      badge.className = 'badge text-bg-info ms-1';
      badge.textContent = String(d.fotos_count);
      btnFotos.appendChild(badge);
    }
    btnFotos.dataset.id = String(d.id ?? '');
    btnFotos.dataset.fotos = JSON.stringify(d.fotos || []);

    const btnEditar = document.createElement('button');
    btnEditar.type = 'button';
    btnEditar.className = 'btn btn-sm btn-outline-warning me-1 btn-dev-editar';
    btnEditar.textContent = 'Editar';
    btnEditar.dataset.id = String(d.id ?? '');
    btnEditar.dataset.data = String(d.data ?? '');
    btnEditar.dataset.palete = String(d.palete ?? '');
    btnEditar.dataset.volume = String(d.volume ?? '');
    btnEditar.dataset.motivo = String(d.motivo ?? '');
    btnEditar.dataset.obs = String(d.obs ?? '');

    const btnExcluir = document.createElement('button');
    btnExcluir.type = 'button';
    btnExcluir.className = 'btn btn-sm btn-outline-danger btn-dev-excluir';
    btnExcluir.textContent = 'Excluir';
    btnExcluir.dataset.id = String(d.id ?? '');

    tdAcoes.appendChild(btnFotos);
    tdAcoes.appendChild(btnEditar);
    tdAcoes.appendChild(btnExcluir);
    tr.appendChild(tdAcoes);
    tabelaDevCorpo.appendChild(tr);
  });

  aplicarTravasDevolucoes();
}

// ── Fotos ──────────────────────────────────────────────────────────────────

const _MAX_FOTO_BYTES = 2 * 1024 * 1024; // 2 MB
const _MAX_DIM = 1920;

async function comprimirImagem(file) {
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

function renderFotosGrid(fotos = []) {
  const grid = document.getElementById('fotos-grid');
  grid.innerHTML = '';
  if (!fotos.length) {
    const p = document.createElement('p');
    p.className = 'text-muted col-12';
    p.textContent = 'Nenhuma foto adicionada.';
    grid.appendChild(p);
    return;
  }
  fotos.forEach(foto => {
    const col = document.createElement('div');
    col.className = 'col-6 col-md-3 position-relative';

    const wrapper = document.createElement('div');
    wrapper.className = 'position-relative';

    const img = document.createElement('img');
    img.src = foto.thumb_url || foto.url;
    img.alt = '';
    img.className = 'img-fluid rounded border';
    img.style.width = '100%';
    img.style.height = '120px';
    img.style.objectFit = 'cover';
    img.setAttribute('data-bs-toggle', 'tooltip');
    img.setAttribute('data-bs-title', 'Ver em tamanho real');
    img.style.cursor = 'pointer';
    img.addEventListener('click', () => window.open(foto.url, '_blank', 'noopener,noreferrer'));

    wrapper.appendChild(img);
    if (!formEmVisualizacao()) {
      const btnDel = document.createElement('button');
      btnDel.type = 'button';
      btnDel.className = 'btn btn-danger btn-sm position-absolute top-0 end-0 m-1 btn-foto-del';
      btnDel.dataset.imgbbId = foto.id;
      const icone = document.createElement('i');
      icone.className = 'bi bi-trash';
      btnDel.appendChild(icone);
      wrapper.appendChild(btnDel);
    }
    col.appendChild(wrapper);
    grid.appendChild(col);
  });

  // Reinicializar tooltips no grid
  grid.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
    new bootstrap.Tooltip(el, { trigger: 'hover' });
  });
}

let _fotosAtuais = [];

function abrirModalFotos(kind, regId, fotos) {
  document.getElementById('fotos_reg_kind').value = kind;
  document.getElementById('fotos_reg_id').value = String(regId);
  const titulo = document.getElementById('modalFotosTitulo');
  titulo.textContent = kind === 'inc' ? 'Fotos da Incidência' : 'Fotos da Devolução';
  _fotosAtuais = fotos ? [...fotos] : [];
  renderFotosGrid(_fotosAtuais);
  document.getElementById('fotos-progresso').classList.add('d-none');
  document.getElementById('fotos-input').value = '';
  document.getElementById('fotos-camera').value = '';
  // Ocultar upload em modo visualização
  document.getElementById('fotos-upload-area').classList.toggle('d-none', formEmVisualizacao());
  modalFotos.show();
}

async function adicionarFotos(files) {
  const kind = document.getElementById('fotos_reg_kind').value;
  const regId = document.getElementById('fotos_reg_id').value;
  if (!regId) return;

  const progresso = document.getElementById('fotos-progresso');
  const barra = document.getElementById('fotos-barra');
  const status = document.getElementById('fotos-status');
  progresso.classList.remove('d-none');

  const urlAdd = kind === 'inc'
    ? '/app/logistica/pedidos/inc/foto/add'
    : '/app/logistica/pedidos/dev/foto/add';

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    status.textContent = `Processando ${i + 1}/${files.length}: ${file.name}…`;
    barra.style.width = `${Math.round(((i) / files.length) * 100)}%`;

    let b64;
    try {
      b64 = await comprimirImagem(file);
    } catch (err) {
      definirMensagem('erro', err.message, false);
      continue;
    }

    const payload = kind === 'inc'
      ? { inc_id: Number(regId), imagem_b64: b64 }
      : { dev_id: Number(regId), imagem_b64: b64 };

    const resp = await fazerRequisicao(urlAdd, payload);

    if (!resp.success) {
      if (resp.data) updateState(resp.data);
      continue;
    }

    const novaFoto = resp.data?.foto;
    if (novaFoto) {
      _fotosAtuais.push(novaFoto);
      renderFotosGrid(_fotosAtuais);
      _atualizarBotaoFotosNaTabela(kind, Number(regId), _fotosAtuais);
    }
  }

  barra.style.width = '100%';
  status.textContent = 'Concluído.';
  setTimeout(() => progresso.classList.add('d-none'), 1500);
  document.getElementById('fotos-input').value = '';
}

async function removerFoto(imgbbId) {
  const kind = document.getElementById('fotos_reg_kind').value;
  const regId = document.getElementById('fotos_reg_id').value;
  if (!regId) return;

  const urlDel = kind === 'inc'
    ? '/app/logistica/pedidos/inc/foto/del'
    : '/app/logistica/pedidos/dev/foto/del';

  const payload = kind === 'inc'
    ? { inc_id: Number(regId), imgbb_id: imgbbId }
    : { dev_id: Number(regId), imgbb_id: imgbbId };

  const resp = await fazerRequisicao(urlDel, payload);

  if (!resp.success) {
    if (resp.data) updateState(resp.data);
    return;
  }

  _fotosAtuais = _fotosAtuais.filter(f => f.id !== imgbbId);
  renderFotosGrid(_fotosAtuais);
  _atualizarBotaoFotosNaTabela(kind, Number(regId), _fotosAtuais);
}

function _atualizarBotaoFotosNaTabela(kind, regId, fotos) {
  const table = kind === 'inc' ? tabelaIncCorpo : tabelaDevCorpo;
  const sel = kind === 'inc' ? `.btn-inc-fotos[data-id="${regId}"]` : `.btn-dev-fotos[data-id="${regId}"]`;
  const btn = table.querySelector(sel);
  if (!btn) return;
  btn.dataset.fotos = JSON.stringify(fotos);
  // Atualizar badge
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

async function carregarDevolucoes() {
  const pedidoId = getForm(nomeForm)?.campos?.id;
  if (!pedidoId) {
    renderDevolucoes([]);
    return;
  }
  const resp = await fazerRequisicao('/app/logistica/pedidos/dev/list', { pedido_id: pedidoId });
  if (!resp.success) return;
  renderDevolucoes(resp.data.registros || []);
}

function abrirModalDev(reg = null) {
  document.getElementById('dev_id').value = reg?.id || '';
  document.getElementById('dev_data').value = reg?.data || '';
  document.getElementById('dev_palete').value = reg?.palete ?? '';
  document.getElementById('dev_volume').value = reg?.volume ?? '';
  document.getElementById('dev_motivo').value = reg?.motivo || '';
  document.getElementById('dev_obs').value = reg?.obs || '';
  modalDev.show();
}

async function salvarDevolucao() {
  if (formEmVisualizacao()) {
    definirMensagem('erro', 'Devoluções estão bloqueadas no modo visualização.', false);
    return;
  }

  const pedidoId = getForm(nomeForm)?.campos?.id;
  if (!pedidoId) {
    definirMensagem('erro', 'Salve o pedido antes de adicionar devoluções.', false);
    return;
  }

  const payload = {
    id: document.getElementById('dev_id').value || null,
    pedido_id: pedidoId,
    data: document.getElementById('dev_data').value,
    palete: document.getElementById('dev_palete').value,
    volume: document.getElementById('dev_volume').value,
    motivo: document.getElementById('dev_motivo').value,
    obs: document.getElementById('dev_obs').value,
  };

  const resp = await fazerRequisicao('/app/logistica/pedidos/dev/save', payload);
  if (!resp.success) {
    if (resp.data) updateState(resp.data);
    return;
  }

  if (resp.data) updateState(resp.data);
  modalDev.hide();
  await carregarDevolucoes();
}

async function excluirDevolucao(id) {
  const resp = await fazerRequisicao('/app/logistica/pedidos/dev/del', { id });
  if (!resp.success) {
    if (resp.data) updateState(resp.data);
    return;
  }
  if (resp.data) updateState(resp.data);
  await carregarDevolucoes();
}

function formEmVisualizacao() {
  return (getForm(nomeForm)?.estado || 'visualizar') === 'visualizar';
}

function pedidoEstaSalvo() {
  return Boolean(getForm(nomeForm)?.campos?.id);
}

function aplicarTravasMovimentacoes() {
  const bloqueado = formEmVisualizacao();
  const semPedidoSalvo = !pedidoEstaSalvo();
  const btnNovoMov = document.getElementById('btn-mov-novo');
  const btnSalvarMov = document.getElementById('btn-mov-salvar');

  if (btnNovoMov) btnNovoMov.disabled = bloqueado || semPedidoSalvo;
  if (btnSalvarMov) btnSalvarMov.disabled = bloqueado;

  tabelaMovCorpo.querySelectorAll('.btn-mov-editar, .btn-mov-excluir').forEach(btn => {
    btn.disabled = bloqueado;
  });
}

function aplicarTravasDevolucoes() {
  const bloqueado = formEmVisualizacao();
  const semPedidoSalvo = !pedidoEstaSalvo();
  const btnNovoDev = document.getElementById('btn-dev-novo');
  const btnSalvarDev = document.getElementById('btn-dev-salvar');

  if (btnNovoDev) btnNovoDev.disabled = bloqueado || semPedidoSalvo;
  if (btnSalvarDev) btnSalvarDev.disabled = bloqueado;

  tabelaDevCorpo.querySelectorAll('.btn-dev-editar, .btn-dev-excluir').forEach(btn => {
    btn.disabled = bloqueado;
  });
  // Botão de fotos: visível sempre que o pedido estiver salvo (leitura livre)
  tabelaDevCorpo.querySelectorAll('.btn-dev-fotos').forEach(btn => {
    btn.disabled = semPedidoSalvo;
  });
}

function aplicarTravasIncidencias() {
  const bloqueado = formEmVisualizacao();
  const semPedidoSalvo = !pedidoEstaSalvo();
  const btnNovoInc = document.getElementById('btn-inc-novo');
  const btnSalvarInc = document.getElementById('btn-inc-salvar');

  if (btnNovoInc) btnNovoInc.disabled = bloqueado || semPedidoSalvo;
  if (btnSalvarInc) btnSalvarInc.disabled = bloqueado;

  tabelaIncCorpo.querySelectorAll('.btn-inc-editar, .btn-inc-excluir').forEach(btn => {
    btn.disabled = bloqueado;
  });
  tabelaIncCorpo.querySelectorAll('.btn-inc-fotos').forEach(btn => {
    btn.disabled = semPedidoSalvo;
  });
}

// ── Tipos de incidência filtrados por origem ──────────────────────────────────
const _INCIDENCIA_CHOICE = [
  { tipo: 'Acondicionamento/Embalagem', filtro: 'cliente' },
  { tipo: 'Peso/Volume',               filtro: 'cliente' },
  { tipo: 'Data/Horário',              filtro: 'cliente' },
  { tipo: 'Pedido incompleto',         filtro: 'cliente' },
  { tipo: 'Outros',                    filtro: '' },
  { tipo: 'Artigo Danificado',         filtro: 'filial' },
  { tipo: 'Artigo Extraviado',         filtro: 'filial' },
];

function preencherTiposIncidencia(origem) {
  const sel = document.getElementById('inc_tipo');
  const valorAtual = sel.value;
  sel.replaceChildren();
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = 'Selecione';
  sel.appendChild(placeholder);

  const origemNorm = (origem || '').toLowerCase();
  _INCIDENCIA_CHOICE.forEach(({ tipo, filtro }) => {
    if (filtro === '' || filtro === origemNorm) {
      const opt = document.createElement('option');
      opt.value = tipo;
      opt.textContent = tipo;
      sel.appendChild(opt);
    }
  });

  if (valorAtual) sel.value = valorAtual;
}

function renderIncidencias(registros = []) {
  tabelaIncCorpo.innerHTML = '';
  if (!registros.length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 10;
    td.className = 'text-center text-muted';
    td.textContent = 'Nenhuma incidência';
    tr.appendChild(td);
    tabelaIncCorpo.appendChild(tr);
    aplicarTravasIncidencias();
    return;
  }

  registros.forEach(inc => {
    const tr = document.createElement('tr');

    const colunas = [
      inc.id,
      inc.data,
      inc.origem,
      inc.tipo,
      inc.artigo,
      inc.valor !== null && inc.valor !== undefined ? inc.valor : '',
      inc.motorista_nome,
      inc.obs,
    ];
    colunas.forEach(valor => {
      const td = document.createElement('td');
      td.textContent = String(valor ?? '');
      tr.appendChild(td);
    });

    const tdFotos = document.createElement('td');
    tdFotos.className = 'text-center';
    const btnFotos = document.createElement('button');
    btnFotos.type = 'button';
    btnFotos.className = 'btn btn-sm btn-outline-info btn-inc-fotos';
    const iconeFotos = document.createElement('i');
    iconeFotos.className = 'bi bi-images';
    btnFotos.appendChild(iconeFotos);
    if (inc.fotos_count > 0) {
      const badge = document.createElement('span');
      badge.className = 'badge text-bg-info ms-1';
      badge.textContent = String(inc.fotos_count);
      btnFotos.appendChild(badge);
    }
    btnFotos.dataset.id = String(inc.id ?? '');
    btnFotos.dataset.fotos = JSON.stringify(inc.fotos || []);
    tdFotos.appendChild(btnFotos);
    tr.appendChild(tdFotos);

    const tdAcoes = document.createElement('td');
    tdAcoes.className = 'text-center';

    const btnEditar = document.createElement('button');
    btnEditar.type = 'button';
    btnEditar.className = 'btn btn-sm btn-outline-warning me-1 btn-inc-editar';
    btnEditar.textContent = 'Editar';
    btnEditar.dataset.id          = String(inc.id ?? '');
    btnEditar.dataset.data        = String(inc.data ?? '');
    btnEditar.dataset.origem      = String(inc.origem ?? '');
    btnEditar.dataset.tipo        = String(inc.tipo ?? '');
    btnEditar.dataset.artigo      = String(inc.artigo ?? '');
    btnEditar.dataset.valor       = String(inc.valor ?? '');
    btnEditar.dataset.motoristaId = String(inc.motorista_id ?? '');
    btnEditar.dataset.obs         = String(inc.obs ?? '');

    const btnExcluir = document.createElement('button');
    btnExcluir.type = 'button';
    btnExcluir.className = 'btn btn-sm btn-outline-danger btn-inc-excluir';
    btnExcluir.textContent = 'Excluir';
    btnExcluir.dataset.id = String(inc.id ?? '');

    tdAcoes.appendChild(btnEditar);
    tdAcoes.appendChild(btnExcluir);
    tr.appendChild(tdAcoes);
    tabelaIncCorpo.appendChild(tr);
  });

  aplicarTravasIncidencias();
}

async function carregarIncidencias() {
  const pedidoId = getForm(nomeForm)?.campos?.id;
  if (!pedidoId) {
    renderIncidencias([]);
    return;
  }
  const resp = await fazerRequisicao('/app/logistica/pedidos/inc/list', { pedido_id: pedidoId });
  if (!resp.success) return;
  renderIncidencias(resp.data.registros || []);
}

function abrirModalInc(reg = null) {
  document.getElementById('inc_id').value       = reg?.id || '';
  document.getElementById('inc_data').value     = reg?.data || '';
  document.getElementById('inc_artigo').value   = reg?.artigo || '';
  document.getElementById('inc_valor').value    = reg?.valor ?? '';
  document.getElementById('inc_obs').value      = reg?.obs || '';

  const selOrigem = document.getElementById('inc_origem');
  selOrigem.value = reg?.origem || '';
  preencherTiposIncidencia(reg?.origem || '');
  document.getElementById('inc_tipo').value = reg?.tipo || '';

  // Motorista: só ativo se origem = Filial
  const selMotorista = document.getElementById('inc_motorista');
  selMotorista.disabled = (reg?.origem || '').toLowerCase() !== 'filial';
  selMotorista.value = reg?.motorista_id ? String(reg.motorista_id) : '';

  modalInc.show();
}

async function salvarIncidencia() {
  if (formEmVisualizacao()) {
    definirMensagem('erro', 'Incidências estão bloqueadas no modo visualização.', false);
    return;
  }

  const pedidoId = getForm(nomeForm)?.campos?.id;
  if (!pedidoId) {
    definirMensagem('erro', 'Salve o pedido antes de adicionar incidências.', false);
    return;
  }

  const payload = {
    id:           document.getElementById('inc_id').value || null,
    pedido_id:    pedidoId,
    data:         document.getElementById('inc_data').value,
    origem:       document.getElementById('inc_origem').value,
    tipo:         document.getElementById('inc_tipo').value,
    artigo:       document.getElementById('inc_artigo').value,
    valor:        document.getElementById('inc_valor').value,
    motorista_id: document.getElementById('inc_motorista').value || null,
    obs:          document.getElementById('inc_obs').value,
  };

  const resp = await fazerRequisicao('/app/logistica/pedidos/inc/save', payload);
  if (!resp.success) {
    if (resp.data) updateState(resp.data);
    return;
  }

  if (resp.data) updateState(resp.data);
  modalInc.hide();
  await carregarIncidencias();
}

async function excluirIncidencia(id) {
  const resp = await fazerRequisicao('/app/logistica/pedidos/inc/del', { id });
  if (!resp.success) {
    if (resp.data) updateState(resp.data);
    return;
  }
  if (resp.data) updateState(resp.data);
  await carregarIncidencias();
}

function preencherMotoristasFilial(filialId) {
  const selectPedido = document.getElementById('motorista_id');
  const selectMov = document.getElementById('mov_motorista');
  const selectInc = document.getElementById('inc_motorista');
  const atualPedido = getForm(nomeForm)?.campos?.motorista_id;
  const atualMov = document.getElementById('mov_motorista')?.value || '';

  [selectPedido, selectMov, selectInc].forEach(select => {
    if (select) {
      select.innerHTML = '';
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = 'Selecione';
      select.appendChild(opt);
    }
  });

  if (!filialId) {
    updateFormField(nomeForm, 'motorista_id', null);
    return;
  }

  fazerRequisicao('/app/logistica/pedidos/motoristas', { filial_id: filialId })
    .then(resultado => {
      if (!resultado?.success) {
        throw new Error('Falha ao buscar motoristas.');
      }

      const registros = resultado?.data?.registros || [];
      registros.forEach(m => {
        [selectPedido, selectMov, selectInc].forEach(select => {
          if (!select) return;
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = `${m.codigo || '-'} - ${m.nome}`;
          select.appendChild(opt);
        });
      });

      if (atualPedido && selectPedido) {
        selectPedido.value = String(atualPedido);
      }
      if (atualMov && selectMov) {
        selectMov.value = String(atualMov);
      }
    })
    .catch(() => {
      definirMensagem('erro', 'Não foi possível carregar motoristas da filial.', false);
    });
}

function aplicarTravasImportados() {
  const fd = getForm(nomeForm);
  const origem = fd?.campos?.origem;
  const estado = fd?.estado;

  const campos = form.querySelectorAll('input, select, textarea');
  const bloquearTudo = estado === 'visualizar';
  campos.forEach(el => {
    if (el.id === 'origem') {
      el.readOnly = true;
      return;
    }
    el.disabled = bloquearTudo;
    if (podeAplicarEstiloSomenteLeitura(el)) {
      el.classList.toggle('bg-light-subtle', bloquearTudo);
    } else {
      el.classList.remove('bg-light-subtle');
    }
  });

  if (bloquearTudo) {
    return;
  }

  const travar = origem === 'IMPORTADO' && estado === 'editar';
  CAMPOS_TRAVADOS_IMPORTADO.forEach(nome => {
    const el = form.querySelector(`[name="${nome}"]`);
    if (el) {
      el.disabled = travar;
      if (podeAplicarEstiloSomenteLeitura(el)) {
        el.classList.toggle('bg-light-subtle', travar);
      } else {
        el.classList.remove('bg-light-subtle');
      }
    }
  });

  // Campos de avaliação são sempre somente leitura visual (disabled),
  // independentemente do estado do formulário (novo/editar/visualizar).
  form.querySelectorAll('#avaliacao input, #avaliacao textarea, #avaliacao select').forEach(el => {
    el.disabled = true;
  });
}

function renderMovimentacoes(registros = []) {
  tabelaMovCorpo.innerHTML = '';
  if (!registros.length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 10;
    td.className = 'text-center text-muted';
    td.textContent = 'Nenhuma movimentação';
    tr.appendChild(td);
    tabelaMovCorpo.appendChild(tr);
    aplicarTravasMovimentacoes();
    return;
  }

  registros.forEach(m => {
    const tr = document.createElement('tr');
    const estadoExibicao = resolverEstadoExibicao(m);

    const colunas = [
      m.id,
      m.data_tentativa,
      estadoExibicao,
      m.carro,
      m.motorista_nome,
      m.periodo === 'MANHA' ? 'MANHÃ' : (m.periodo || ''),
      m.dt_entrega,
      m.faturado ? 'Sim' : 'Não',
      m.interno ? 'Sim' : 'Não',
    ];

    colunas.forEach(valor => {
      const td = document.createElement('td');
      td.textContent = String(valor ?? '');
      tr.appendChild(td);
    });

    const tdAcoes = document.createElement('td');
    tdAcoes.className = 'text-center';

    const btnEditar = document.createElement('button');
    btnEditar.type = 'button';
    btnEditar.className = 'btn btn-sm btn-outline-warning me-1 btn-mov-editar';
    btnEditar.textContent = 'Editar';
    btnEditar.dataset.id = String(m.id ?? '');
    btnEditar.dataset.dataTentativa = String(m.data_tentativa ?? '');
    btnEditar.dataset.estado = String(m.estado ?? '');
    btnEditar.dataset.carro = String(m.carro ?? '');
    btnEditar.dataset.motoristaId = String(m.motorista_id ?? '');
    btnEditar.dataset.periodo = String(m.periodo ?? '');
    btnEditar.dataset.dtEntrega = String(m.dt_entrega ?? '');
    btnEditar.dataset.faturado = m.faturado ? '1' : '0';
    btnEditar.dataset.interno = m.interno ? '1' : '0';

    const btnExcluir = document.createElement('button');
    btnExcluir.type = 'button';
    btnExcluir.className = 'btn btn-sm btn-outline-danger btn-mov-excluir';
    btnExcluir.textContent = 'Excluir';
    btnExcluir.dataset.id = String(m.id ?? '');

    tdAcoes.appendChild(btnEditar);
    tdAcoes.appendChild(btnExcluir);
    tr.appendChild(tdAcoes);
    tabelaMovCorpo.appendChild(tr);
  });

  aplicarTravasMovimentacoes();
}

/** Mov/dev/inc/avaliação já no payload do pedido (cons/save): evita round-trips redundantes. */
async function aplicarListasPedidoDoPayload(payload) {
  const pedidoId = getForm(nomeForm)?.campos?.id;
  if (Array.isArray(payload?.registros_mov)) {
    renderMovimentacoes(payload.registros_mov);
  } else if (pedidoId) {
    await carregarMovimentacoes();
  } else {
    renderMovimentacoes([]);
  }
  if (Array.isArray(payload?.registros_dev)) {
    renderDevolucoes(payload.registros_dev);
  } else if (pedidoId) {
    await carregarDevolucoes();
  } else {
    renderDevolucoes([]);
  }
  if (Array.isArray(payload?.registros_inc)) {
    renderIncidencias(payload.registros_inc);
  } else if (pedidoId) {
    await carregarIncidencias();
  } else {
    renderIncidencias([]);
  }
  renderAvaliacao(payload?.avaliacao ?? null);
}

async function carregarMovimentacoes() {
  const pedidoId = getForm(nomeForm)?.campos?.id;
  if (!pedidoId) {
    renderMovimentacoes([]);
    return;
  }
  const resp = await fazerRequisicao('/app/logistica/pedidos/mov/list', { pedido_id: pedidoId });
  if (!resp.success) {
    return;
  }
  renderMovimentacoes(resp.data.registros || []);
}

function abrirModalMov(reg = null) {
  document.getElementById('mov_id').value = reg?.id || '';
  document.getElementById('mov_data_tentativa').value = reg?.data_tentativa || '';
  document.getElementById('mov_estado').value = reg?.estado || '';
  document.getElementById('mov_carro').value = reg?.carro ?? '';
  document.getElementById('mov_motorista').value = reg?.motorista_id ? String(reg.motorista_id) : '';
  document.getElementById('mov_periodo').value = reg?.periodo || '';
  document.getElementById('mov_dt_entrega').value = reg?.dt_entrega || '';
  document.getElementById('mov_faturado').checked = Boolean(reg?.faturado);
  document.getElementById('mov_interno').checked = Boolean(reg?.interno);
  modalMov.show();
}

async function salvarMovimentacao() {
  if (formEmVisualizacao()) {
    definirMensagem('erro', 'Movimentações estão bloqueadas no modo visualização.', false);
    return;
  }

  const pedidoId = getForm(nomeForm)?.campos?.id;
  if (!pedidoId) {
    definirMensagem('erro', 'Salve o pedido antes de adicionar movimentações.', false);
    return;
  }

  const payload = {
    id: document.getElementById('mov_id').value || null,
    pedido_id: pedidoId,
    data_tentativa: document.getElementById('mov_data_tentativa').value,
    estado: document.getElementById('mov_estado').value,
    carro: document.getElementById('mov_carro').value,
    motorista_id: document.getElementById('mov_motorista').value,
    periodo: document.getElementById('mov_periodo').value,
    dt_entrega: document.getElementById('mov_dt_entrega').value,
    faturado: document.getElementById('mov_faturado').checked,
    interno: document.getElementById('mov_interno').checked,
  };

  const resp = await fazerRequisicao('/app/logistica/pedidos/mov/save', payload);
  if (!resp.success) {
    if (resp.data) updateState(resp.data);
    return;
  }

  if (resp.data) updateState(resp.data);
  modalMov.hide();
  await carregarMovimentacoes();
}

async function excluirMovimentacao(id) {
  const resp = await fazerRequisicao('/app/logistica/pedidos/mov/del', { id });
  if (!resp.success) {
    if (resp.data) updateState(resp.data);
    return;
  }
  if (resp.data) updateState(resp.data);
  await carregarMovimentacoes();
}

async function resetarFormularioAposCancelamento() {
  setFormState(nomeForm, pode('incluir') ? 'novo' : 'visualizar');
  hidratarFormulario(nomeForm);
  preencherMotoristasFilial(getForm(nomeForm)?.campos?.filial_id || '');
  await carregarMovimentacoes();
  await carregarDevolucoes();
  await carregarIncidencias();
  aplicarPermissoesNaInterface();
}

function renderPesquisa(registros = []) {
  tabelaPedidoCorpo.innerHTML = '';
  if (!registros.length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 10;
    td.className = 'text-center text-muted';
    td.textContent = 'Nenhum registro';
    tr.appendChild(td);
    tabelaPedidoCorpo.appendChild(tr);
    return;
  }

  registros.forEach(r => {
    const tr = document.createElement('tr');

    const campos = [r.id, r.filial];
    campos.forEach(valor => {
      const td = document.createElement('td');
      td.textContent = String(valor ?? '');
      tr.appendChild(td);
    });

    const tdOrigem = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = `badge ${r.origem === 'IMPORTADO' ? 'text-bg-info' : 'text-bg-secondary'}`;
    badge.textContent = String(r.origem ?? '');
    tdOrigem.appendChild(badge);
    tr.appendChild(tdOrigem);

    const estadoExibicao = resolverEstadoExibicao(r);
    [r.id_vonzu, r.pedido, r.tipo, estadoExibicao, r.prev_entrega, r.nome_dest].forEach(valor => {
      const td = document.createElement('td');
      td.textContent = String(valor ?? '');
      tr.appendChild(td);
    });

    const tdAcao = document.createElement('td');
    tdAcao.className = 'text-center';
    const btnSelecionar = document.createElement('button');
    btnSelecionar.className = 'btn btn-primary btn-sm btn-selecionar';
    btnSelecionar.dataset.id = String(r.id ?? '');
    btnSelecionar.textContent = 'Selecionar';
    tdAcao.appendChild(btnSelecionar);
    tr.appendChild(tdAcao);

    tabelaPedidoCorpo.appendChild(tr);
  });
}

function aplicarPermissoesNaInterface() {
  const estado = getForm(nomeForm)?.estado || 'visualizar';
  const mapa = {
    'btn-novo': pode('incluir'),
    'btn-editar': pode('editar'),
    'btn-excluir': pode('excluir'),
    'btn-abrir-pesquisa': pode('consultar'),
  };

  ['btn-salvar', 'btn-cancelar', 'btn-editar', 'btn-novo', 'btn-excluir', 'btn-abrir-pesquisa'].forEach(id => {
    const btn = document.getElementById(id);
    const showOn = (btn.dataset.showOn || '').split(',').map(x => x.trim()).filter(Boolean);
    const visivelEstado = showOn.length ? showOn.includes(estado) : true;
    const visivelPerm = mapa[id] !== undefined ? mapa[id] : (estado === 'novo' ? pode('incluir') : pode('editar'));
    btn.classList.toggle('d-none', !(visivelEstado && visivelPerm));
  });

  aplicarTravasImportados();
  aplicarTravasMovimentacoes();
  aplicarTravasDevolucoes();
  aplicarTravasIncidencias();
}

function formatarDataHoraIso(valor) {
  if (!valor) return '';
  const dt = new Date(valor);
  if (Number.isNaN(dt.getTime())) return valor;
  const dd = String(dt.getDate()).padStart(2, '0');
  const mm = String(dt.getMonth() + 1).padStart(2, '0');
  const yyyy = dt.getFullYear();
  const hh = String(dt.getHours()).padStart(2, '0');
  const mi = String(dt.getMinutes()).padStart(2, '0');
  return `${dd}/${mm}/${yyyy} ${hh}:${mi}`;
}

function renderAvaliacao(av = null) {
  const setVal = (id, v) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.value = v ?? '';
  };
  if (!av) {
    setVal('av-id', '');
    setVal('av-email-enviado', '');
    setVal('av-email-enviado-em', '');
    setVal('av-email-tentativas', '');
    setVal('av-link-ativo', '');
    setVal('av-respondido-em', '');
    setVal('av-p1', '');
    setVal('av-p2', '');
    setVal('av-p3', '');
    setVal('av-p4', '');
    setVal('av-p5', '');
    setVal('av-p6', '');
    setVal('av-p7', '');
    setVal('av-p8', '');
    setVal('av-p9', '');
    setVal('av-p10', '');
    setVal('av-comentario', '');
    return;
  }
  setVal('av-id', av.id || '');
  setVal('av-email-enviado', av.email_enviado ? 'Sim' : 'Não');
  setVal('av-email-enviado-em', formatarDataHoraIso(av.email_enviado_em));
  setVal('av-email-tentativas', av.email_tentativas ?? 0);
  setVal('av-link-ativo', av.link_ativo ? 'Sim' : 'Não');
  setVal('av-respondido-em', formatarDataHoraIso(av.respondido_em));
  setVal('av-p1', av.p1_entrega_no_prazo || '');
  setVal('av-p2', av.p2_aviso_antes_chegada || '');
  setVal('av-p3', av.p3_educacao_simpatia ?? '');
  setVal('av-p4', av.p4_cuidado_encomenda ?? '');
  setVal('av-p5', av.p5_equipa_identificada || '');
  setVal('av-p6', av.p6_facilidade_processo ?? '');
  setVal('av-p7', av.p7_veiculo_limpo || '');
  setVal('av-p8', av.p8_esclareceu_duvidas || '');
  setVal('av-p9', av.p9_satisfacao_geral ?? '');
  setVal('av-p10', av.p10_recomendaria || '');
  setVal('av-comentario', av.comentario || '');
}

const updater = criarAtualizadorForm({ formId: nomeForm, setter: updateFormField, form });
form.addEventListener('input', updater);
form.addEventListener('change', updater);

const updaterCons = criarAtualizadorForm({ formId: nomeCons, setter: updateFormField, form: formCons });
formCons.addEventListener('input', updaterCons);
formCons.addEventListener('change', updaterCons);

initSmartInputs((input, value) => {
  const formId = input.closest('form')?.id;
  if (formId) updateFormField(formId, input.name, value);
});

document.addEventListener('DOMContentLoaded', () => {
  preencherFiliais();
  preencherClientes();
  preencherTipos();
  preencherEstados();
  preencherPeriodosMov();
  preencherOrigens();
  preencherMotivosDev();

  hidratarFormulario(nomeForm);
  aplicarPermissoesNaInterface();
  preencherMotoristasFilial(getForm(nomeForm)?.campos?.filial_id || '');
  carregarMovimentacoes();
  carregarDevolucoes();
  carregarIncidencias();
  renderAvaliacao(getDataBackEnd()?.avaliacao || null);

  const areaCadastro = document.getElementById('area-cadastro');
  const divPesquisa = document.getElementById('div-pesquisa');
  const alternar = () => {
    areaCadastro.classList.toggle('d-none');
    divPesquisa.classList.toggle('d-none');
  };

  document.getElementById('btn-abrir-pesquisa').addEventListener('click', alternar);
  document.getElementById('btn-voltar').addEventListener('click', alternar);
  document.getElementById('btn-fechar').addEventListener('click', alternar);

  document.getElementById('btn-editar').addEventListener('click', () => {
    setFormState(nomeForm, 'editar');
    aplicarPermissoesNaInterface();
  });

  document.getElementById('btn-novo').addEventListener('click', () => {
    setFormState(nomeForm, 'novo');
    form.reset();
    updateState({ form: { [nomeForm]: { estado: 'novo', campos: { ...getForm(nomeForm).campos, id: null, origem: 'MANUAL' } } } });
    carregarMovimentacoes();
    carregarDevolucoes();
    carregarIncidencias();
    renderAvaliacao(null);
    aplicarPermissoesNaInterface();
  });

  document.getElementById('btn-cancelar').addEventListener('click', () => {
    confirmar({
      titulo: 'Confirmar Cancelamento',
      mensagem: 'Deseja cancelar? Os dados não salvos serão perdidos.',
      onConfirmar: async () => resetarFormularioAposCancelamento(),
    });
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearMessages();

    const dataForm = getForm(nomeForm);
    const resultado = await fazerRequisicao('/app/logistica/pedidos/', {
      form: { [nomeForm]: dataForm },
    });

    if (!resultado.success) {
      if (resultado.data) updateState(resultado.data);
      return;
    }

    updateState(resultado.data);
    hidratarFormulario(nomeForm);
    await aplicarListasPedidoDoPayload(resultado.data);
    aplicarPermissoesNaInterface();
  });

  document.getElementById('btn-excluir').addEventListener('click', () => {
    confirmar({
      titulo: 'Confirmar exclusão',
      mensagem: 'Deseja excluir o pedido selecionado?',
      onConfirmar: async () => {
        const dataForm = getForm(nomeForm);
        const resultado = await fazerRequisicao('/app/logistica/pedidos/del', {
          form: { [nomeForm]: dataForm },
        });

        if (!resultado.success) {
          if (resultado.data) updateState(resultado.data);
          return;
        }

        updateState(resultado.data);
        document.getElementById('btn-novo').click();
      },
    });
  });

  formCons.addEventListener('submit', async (e) => {
    e.preventDefault();
    AppLoader.show();
    try {
      const dataCons = getForm(nomeCons);
      const resultado = await fazerRequisicao('/app/logistica/pedidos/cons', {
        form: { [nomeCons]: dataCons },
      });

      if (!resultado.success) {
        if (resultado.data) updateState(resultado.data);
        return;
      }

      if (resultado.data.registros) {
        renderPesquisa(resultado.data.registros);
        return;
      }

      updateState(resultado.data);
      hidratarFormulario(nomeForm);
      preencherMotoristasFilial(getForm(nomeForm)?.campos?.filial_id || '');
      await aplicarListasPedidoDoPayload(resultado.data);
      alternar();
      aplicarPermissoesNaInterface();
    } finally {
      AppLoader.hide();
    }
  });

  tabelaPedidoCorpo.addEventListener('click', async (e) => {
    const btn = e.target.closest('.btn-selecionar');
    if (!btn) return;

    AppLoader.show();
    try {
      const id = Number(btn.dataset.id);
      updateFormField(nomeCons, 'id_selecionado', id);
      const dataCons = getForm(nomeCons);
      const resultado = await fazerRequisicao('/app/logistica/pedidos/cons', {
        form: { [nomeCons]: dataCons },
      });

      if (!resultado.success) {
        if (resultado.data) updateState(resultado.data);
        return;
      }

      updateState(resultado.data);
      hidratarFormulario(nomeForm);
      preencherMotoristasFilial(getForm(nomeForm)?.campos?.filial_id || '');
      await aplicarListasPedidoDoPayload(resultado.data);
      updateFormField(nomeCons, 'id_selecionado', null);
      alternar();
      aplicarPermissoesNaInterface();
    } finally {
      AppLoader.hide();
    }
  });

  document.getElementById('btn-mov-novo').addEventListener('click', () => {
    if (formEmVisualizacao()) return;
    if (!pedidoEstaSalvo()) {
      definirMensagem('aviso', 'Salve o pedido antes de adicionar movimentações.');
      return;
    }
    abrirModalMov(null);
  });

  document.getElementById('btn-mov-salvar').addEventListener('click', salvarMovimentacao);

  tabelaMovCorpo.addEventListener('click', (e) => {
    if (e.target.closest('.btn-mov-editar, .btn-mov-excluir')) {
      e.preventDefault();
    }

    if (formEmVisualizacao()) return;

    const btnEditar = e.target.closest('.btn-mov-editar');
    if (btnEditar) {
      abrirModalMov({
        id: Number(btnEditar.dataset.id),
        data_tentativa: btnEditar.dataset.dataTentativa,
        estado: btnEditar.dataset.estado,
        carro: btnEditar.dataset.carro,
        motorista_id: btnEditar.dataset.motoristaId,
        periodo: btnEditar.dataset.periodo,
        dt_entrega: btnEditar.dataset.dtEntrega,
        faturado: btnEditar.dataset.faturado === '1',
        interno: btnEditar.dataset.interno === '1',
      });
      return;
    }

    const btnExcluir = e.target.closest('.btn-mov-excluir');
    if (btnExcluir) {
      const id = Number(btnExcluir.dataset.id);
      confirmar({
        titulo: 'Excluir movimentação',
        mensagem: 'Deseja excluir esta movimentação?',
        onConfirmar: async () => excluirMovimentacao(id),
      });
    }
  });

  document.getElementById('filial_id').addEventListener('change', e => {
    updateFormField(nomeForm, 'filial_id', e.target.value || null);
    preencherMotoristasFilial(e.target.value);
    aplicarTravasImportados();
  });

  document.getElementById('motorista_id').addEventListener('change', e => {
    updateFormField(nomeForm, 'motorista_id', e.target.value || null);
  });

  document.getElementById('btn-dev-novo').addEventListener('click', () => {
    if (formEmVisualizacao()) return;
    if (!pedidoEstaSalvo()) {
      definirMensagem('aviso', 'Salve o pedido antes de adicionar devoluções.');
      return;
    }
    abrirModalDev(null);
  });

  document.getElementById('btn-dev-salvar').addEventListener('click', salvarDevolucao);

  tabelaDevCorpo.addEventListener('click', (e) => {
    if (e.target.closest('.btn-dev-editar, .btn-dev-excluir, .btn-dev-fotos')) {
      e.preventDefault();
    }

    const btnFotos = e.target.closest('.btn-dev-fotos');
    if (btnFotos) {
      const id = Number(btnFotos.dataset.id);
      let fotos = [];
      try { fotos = JSON.parse(btnFotos.dataset.fotos || '[]'); } catch (_) {}
      abrirModalFotos('dev', id, fotos);
      return;
    }

    if (formEmVisualizacao()) return;

    const btnEditar = e.target.closest('.btn-dev-editar');
    if (btnEditar) {
      abrirModalDev({
        id: Number(btnEditar.dataset.id),
        data: btnEditar.dataset.data,
        palete: btnEditar.dataset.palete,
        volume: btnEditar.dataset.volume,
        motivo: btnEditar.dataset.motivo,
        obs: btnEditar.dataset.obs,
      });
      return;
    }

    const btnExcluir = e.target.closest('.btn-dev-excluir');
    if (btnExcluir) {
      const id = Number(btnExcluir.dataset.id);
      confirmar({
        titulo: 'Excluir devolução',
        mensagem: 'Deseja excluir esta devolução?',
        onConfirmar: async () => excluirDevolucao(id),
      });
    }
  });

  document.getElementById('fotos-input').addEventListener('change', (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length) adicionarFotos(files);
  });

  document.getElementById('fotos-camera').addEventListener('change', (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length) adicionarFotos(files);
  });

  document.getElementById('fotos-grid').addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-foto-del');
    if (!btn) return;
    confirmar({
      titulo: 'Remover foto',
      mensagem: 'Deseja remover esta foto?',
      onConfirmar: async () => removerFoto(btn.dataset.imgbbId),
    });
  });

  // ── Incidências ────────────────────────────────────────────────────────────
  document.getElementById('btn-inc-novo').addEventListener('click', () => {
    if (formEmVisualizacao()) return;
    if (!pedidoEstaSalvo()) {
      definirMensagem('aviso', 'Salve o pedido antes de adicionar incidências.');
      return;
    }
    abrirModalInc(null);
  });

  document.getElementById('btn-inc-salvar').addEventListener('click', salvarIncidencia);

  document.getElementById('inc_origem').addEventListener('change', (e) => {
    const origem = e.target.value;
    preencherTiposIncidencia(origem);
    const selMotorista = document.getElementById('inc_motorista');
    selMotorista.disabled = origem.toLowerCase() !== 'filial';
    if (selMotorista.disabled) selMotorista.value = '';
  });

  tabelaIncCorpo.addEventListener('click', (e) => {
    if (e.target.closest('.btn-inc-editar, .btn-inc-excluir, .btn-inc-fotos')) {
      e.preventDefault();
    }

    const btnFotos = e.target.closest('.btn-inc-fotos');
    if (btnFotos) {
      const id = Number(btnFotos.dataset.id);
      let fotos = [];
      try { fotos = JSON.parse(btnFotos.dataset.fotos || '[]'); } catch (_) {}
      abrirModalFotos('inc', id, fotos);
      return;
    }

    if (formEmVisualizacao()) return;

    const btnEditar = e.target.closest('.btn-inc-editar');
    if (btnEditar) {
      abrirModalInc({
        id:           Number(btnEditar.dataset.id),
        data:         btnEditar.dataset.data,
        origem:       btnEditar.dataset.origem,
        tipo:         btnEditar.dataset.tipo,
        artigo:       btnEditar.dataset.artigo,
        valor:        btnEditar.dataset.valor,
        motorista_id: btnEditar.dataset.motoristaId,
        obs:          btnEditar.dataset.obs,
      });
      return;
    }

    const btnExcluir = e.target.closest('.btn-inc-excluir');
    if (btnExcluir) {
      const id = Number(btnExcluir.dataset.id);
      confirmar({
        titulo: 'Excluir incidência',
        mensagem: 'Deseja excluir esta incidência?',
        onConfirmar: async () => excluirIncidencia(id),
      });
    }
  });
});
