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
const tabelaPedidoCorpo = document.getElementById('tabela-pedido-corpo');
const modalMovEl = document.getElementById('modalMov');
const modalMov = new bootstrap.Modal(modalMovEl);
const modalDevEl = document.getElementById('modalDev');
const modalDev = new bootstrap.Modal(modalDevEl);

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

function renderDevolucoes(registros = []) {
  tabelaDevCorpo.innerHTML = '';
  if (!registros.length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 7;
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

    tdAcoes.appendChild(btnEditar);
    tdAcoes.appendChild(btnExcluir);
    tr.appendChild(tdAcoes);
    tabelaDevCorpo.appendChild(tr);
  });

  aplicarTravasDevolucoes();
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
}

function preencherMotoristasFilial(filialId) {
  const selectPedido = document.getElementById('motorista_id');
  const selectMov = document.getElementById('mov_motorista');
  const atualPedido = getForm(nomeForm)?.campos?.motorista_id;
  const atualMov = document.getElementById('mov_motorista')?.value || '';

  [selectPedido, selectMov].forEach(select => {
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
        [selectPedido, selectMov].forEach(select => {
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

    const colunas = [
      m.id,
      m.data_tentativa,
      m.estado,
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

    [r.id_vonzu, r.pedido, r.tipo, r.estado, r.prev_entrega, r.nome_dest].forEach(valor => {
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
    await carregarMovimentacoes();
    await carregarDevolucoes();
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
    await carregarMovimentacoes();
    await carregarDevolucoes();
    alternar();
    aplicarPermissoesNaInterface();
  });

  tabelaPedidoCorpo.addEventListener('click', async (e) => {
    const btn = e.target.closest('.btn-selecionar');
    if (!btn) return;

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
    await carregarMovimentacoes();
    await carregarDevolucoes();
    updateFormField(nomeCons, 'id_selecionado', null);
    alternar();
    aplicarPermissoesNaInterface();
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
    if (e.target.closest('.btn-dev-editar, .btn-dev-excluir')) {
      e.preventDefault();
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
});
