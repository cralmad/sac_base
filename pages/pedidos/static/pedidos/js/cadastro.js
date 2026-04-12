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
  getCsrfToken,
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
const tabelaPedidoCorpo = document.getElementById('tabela-pedido-corpo');
const modalMovEl = document.getElementById('modalMov');
const modalMov = new bootstrap.Modal(modalMovEl);

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

function preencherSelect(id, lista, optLabel = 'Selecione', map = x => ({ value: x.value, label: x.label })) {
  const sel = document.getElementById(id);
  if (!sel) return;
  sel.innerHTML = `<option value="">${optLabel}</option>`;
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

function preencherOrigens() {
  const origens = getOptions('origens', []);
  preencherSelect('origem_cons', origens, 'Todas', o => ({ value: o.value, label: o.label }));
}

function preencherMotoristasFilial(filialId) {
  const select = document.getElementById('motorista_id');
  const atual = getForm(nomeForm)?.campos?.motorista_id;
  select.innerHTML = '<option value="">Selecione</option>';
  if (!filialId) {
    updateFormField(nomeForm, 'motorista_id', null);
    return;
  }

  fetch('/app/logistica/pedidos/motoristas', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken() || '',
    },
    body: JSON.stringify({ filial_id: filialId }),
  })
    .then(resp => resp.json())
    .then(data => {
      const registros = data.registros || [];
      registros.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.id;
        opt.textContent = `${m.codigo || '-'} - ${m.nome}`;
        select.appendChild(opt);
      });
      if (atual) {
        select.value = String(atual);
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
    el.classList.toggle('bg-light-subtle', bloquearTudo);
  });

  if (bloquearTudo) {
    return;
  }

  const travar = origem === 'IMPORTADO' && estado === 'editar';
  CAMPOS_TRAVADOS_IMPORTADO.forEach(nome => {
    const el = form.querySelector(`[name="${nome}"]`);
    if (el) {
      el.disabled = travar;
      el.classList.toggle('bg-light-subtle', travar);
    }
  });
}

function renderMovimentacoes(registros = []) {
  tabelaMovCorpo.innerHTML = '';
  if (!registros.length) {
    tabelaMovCorpo.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Nenhuma movimentação</td></tr>';
    return;
  }

  registros.forEach(m => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${m.id}</td>
      <td>${m.data_tentativa || ''}</td>
      <td>${m.estado || ''}</td>
      <td>${m.dt_entrega || ''}</td>
      <td>${m.faturado ? 'Sim' : 'Não'}</td>
      <td>${m.interno ? 'Sim' : 'Não'}</td>
      <td class="text-center">
        <button class="btn btn-sm btn-outline-warning me-1 btn-mov-editar" data-id="${m.id}">Editar</button>
        <button class="btn btn-sm btn-outline-danger btn-mov-excluir" data-id="${m.id}">Excluir</button>
      </td>
    `;
    tabelaMovCorpo.appendChild(tr);
  });
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
  document.getElementById('mov_dt_entrega').value = reg?.dt_entrega || '';
  document.getElementById('mov_faturado').checked = Boolean(reg?.faturado);
  document.getElementById('mov_interno').checked = Boolean(reg?.interno);
  modalMov.show();
}

async function salvarMovimentacao() {
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

function renderPesquisa(registros = []) {
  tabelaPedidoCorpo.innerHTML = '';
  if (!registros.length) {
    tabelaPedidoCorpo.innerHTML = '<tr><td colspan="10" class="text-center text-muted">Nenhum registro</td></tr>';
    return;
  }

  registros.forEach(r => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.id}</td>
      <td>${r.filial || ''}</td>
      <td><span class="badge ${r.origem === 'IMPORTADO' ? 'text-bg-info' : 'text-bg-secondary'}">${r.origem || ''}</span></td>
      <td>${r.id_vonzu || ''}</td>
      <td>${r.pedido || ''}</td>
      <td>${r.tipo || ''}</td>
      <td>${r.estado || ''}</td>
      <td>${r.prev_entrega || ''}</td>
      <td>${r.nome_dest || ''}</td>
      <td class="text-center"><button class="btn btn-primary btn-sm btn-selecionar" data-id="${r.id}">Selecionar</button></td>
    `;
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
  preencherOrigens();

  hidratarFormulario(nomeForm);
  aplicarPermissoesNaInterface();
  preencherMotoristasFilial(getForm(nomeForm)?.campos?.filial_id || '');
  carregarMovimentacoes();

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
    aplicarPermissoesNaInterface();
  });

  document.getElementById('btn-cancelar').addEventListener('click', () => {
    confirmar({
      titulo: 'Confirmar Cancelamento',
      mensagem: 'Deseja cancelar? Os dados não salvos serão perdidos.',
      onConfirmar: () => {
        setFormState(nomeForm, pode('incluir') ? 'novo' : 'visualizar');
        hidratarFormulario(nomeForm);
        preencherMotoristasFilial(getForm(nomeForm)?.campos?.filial_id || '');
        aplicarPermissoesNaInterface();
      },
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
    await carregarMovimentacoes();
    updateFormField(nomeCons, 'id_selecionado', null);
    alternar();
    aplicarPermissoesNaInterface();
  });

  document.getElementById('btn-mov-novo').addEventListener('click', () => {
    abrirModalMov(null);
  });

  document.getElementById('btn-mov-salvar').addEventListener('click', salvarMovimentacao);

  tabelaMovCorpo.addEventListener('click', (e) => {
    const btnEditar = e.target.closest('.btn-mov-editar');
    if (btnEditar) {
      const id = Number(btnEditar.dataset.id);
      const tr = btnEditar.closest('tr');
      abrirModalMov({
        id,
        data_tentativa: tr.children[1].textContent.trim(),
        estado: tr.children[2].textContent.trim(),
        dt_entrega: tr.children[3].textContent.trim(),
        faturado: tr.children[4].textContent.trim() === 'Sim',
        interno: tr.children[5].textContent.trim() === 'Sim',
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
});
