import {
  clearMessages,
  definirMensagem,
  getDataBackEnd,
  getDataset,
  getForm,
  setFormState,
  updateFormField,
  updateState,
} from "/static/js/sisVar.js";
import { fazerRequisicao } from "/static/js/base.js";
import { initSmartInputs } from "/static/js/input_rules.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";
import { AppLoader } from "/static/js/loader.js";

getDataBackEnd();

const nomeForm = "consAuditoria";
const form = document.getElementById(nomeForm);
let registrosAtuais = [];

const updater = criarAtualizadorForm({ formId: nomeForm, setter: updateFormField, form });
form.addEventListener("input", updater);
form.addEventListener("change", updater);

initSmartInputs((input, value) => {
  const formId = input.closest("form")?.id;
  if (formId) {
    updateFormField(formId, input.name, value);
  }
});

function getContextoAuditoria() {
  return getDataset('auditoria', {
    atores: [],
    acoes: [],
    entidades: [],
    registros: [],
    paginacao: {
      page: 1,
      per_page: 20,
      total_registros: 0,
      total_paginas: 1,
      has_previous: false,
      has_next: false,
    },
  });
}

function getPaginacaoAuditoria() {
  return getContextoAuditoria().paginacao || {
    page: 1,
    per_page: 20,
    total_registros: 0,
    total_paginas: 1,
    has_previous: false,
    has_next: false,
  };
}

function limparResultadosAuditoria() {
  updateState({
    others: {
      auditoria: {
        ...getContextoAuditoria(),
        registros: [],
        paginacao: {
          page: 1,
          per_page: 20,
          total_registros: 0,
          total_paginas: 1,
          has_previous: false,
          has_next: false,
        },
      },
    },
  });
}

function preencherSelectAtores() {
  const select = document.getElementById("actor_id");
  const valorAtual = String(getForm(nomeForm)?.campos?.actor_id ?? "");
  const atores = getContextoAuditoria().atores || [];

  select.innerHTML = '';
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = "Todos";
  select.appendChild(defaultOption);
  atores.forEach(ator => {
    const option = document.createElement("option");
    option.value = String(ator.id);
    option.textContent = `${ator.nome} (${ator.username})`;
    select.appendChild(option);
  });
  select.value = valorAtual;
}

function preencherSelectAcoes() {
  const select = document.getElementById("action");
  const valorAtual = getForm(nomeForm)?.campos?.action ?? "";
  const acoes = getContextoAuditoria().acoes || [];

  select.innerHTML = '';
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = "Todas";
  select.appendChild(defaultOption);
  acoes.forEach(acao => {
    const option = document.createElement("option");
    option.value = acao.value;
    option.textContent = acao.label;
    select.appendChild(option);
  });
  select.value = valorAtual;
}

function preencherSelectApps() {
  const select = document.getElementById("app_label");
  const valorAtual = getForm(nomeForm)?.campos?.app_label ?? "";
  const entidades = getContextoAuditoria().entidades || [];

  select.innerHTML = '';
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = "Todas";
  select.appendChild(defaultOption);
  entidades.forEach(entidade => {
    const option = document.createElement("option");
    option.value = entidade.app_label;
    option.textContent = entidade.app_label.toUpperCase();
    select.appendChild(option);
  });
  select.value = valorAtual;
}

function preencherSelectModels() {
  const select = document.getElementById("model");
  const appLabel = getForm(nomeForm)?.campos?.app_label ?? "";
  const valorAtual = getForm(nomeForm)?.campos?.model ?? "";
  const entidades = getContextoAuditoria().entidades || [];
  const entidade = entidades.find(item => item.app_label === appLabel);
  const models = entidade?.models || [];

  select.innerHTML = '';
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = "Todos";
  select.appendChild(defaultOption);
  models.forEach(model => {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    select.appendChild(option);
  });

  select.value = models.includes(valorAtual) ? valorAtual : "";
  if (!models.includes(valorAtual) && valorAtual) {
    updateFormField(nomeForm, "model", "");
  }
}

function formatarDataHora(valor) {
  if (!valor) {
    return "";
  }

  const data = new Date(valor);
  return Number.isNaN(data.getTime()) ? valor : data.toLocaleString("pt-BR");
}

function abrirModalDetalhes(indice) {
  const evento = registrosAtuais[indice];
  if (!evento) {
    return;
  }

  document.getElementById("auditoria-changed-fields").textContent = JSON.stringify(evento.changed_fields || {}, null, 2);
  document.getElementById("auditoria-extra-data").textContent = JSON.stringify(evento.extra_data || {}, null, 2);

  const modalEl = document.getElementById("modal-auditoria-detalhes");
  const modal = bootstrap.Modal.getInstance(modalEl) ?? new bootstrap.Modal(modalEl);
  modal.show();
}

function renderizarTabela() {
  const tabelaCorpo = document.getElementById("tabela-auditoria-corpo");
  registrosAtuais = getContextoAuditoria().registros || [];
  tabelaCorpo.innerHTML = "";

  if (!Array.isArray(registrosAtuais) || registrosAtuais.length === 0) {
    const trVazio = document.createElement("tr");
    const tdVazio = document.createElement("td");
    tdVazio.colSpan = 7;
    tdVazio.className = "text-center text-muted";
    tdVazio.textContent = "Nenhum evento encontrado.";
    trVazio.appendChild(tdVazio);
    tabelaCorpo.appendChild(trVazio);
    return;
  }

  registrosAtuais.forEach((registro, indice) => {
    const tr = document.createElement("tr");

    [
      formatarDataHora(registro.created_at),
      registro.actor,
      registro.action,
      registro.entity,
      registro.object_repr || registro.object_id,
      registro.summary,
    ].forEach(valor => {
      const td = document.createElement("td");
      td.textContent = valor ?? "";
      tr.appendChild(td);
    });

    const tdAcao = document.createElement("td");
    tdAcao.className = "text-center";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-sm btn-outline-primary btn-detalhes-auditoria";
    button.dataset.index = String(indice);
    button.textContent = "Detalhes";
    tdAcao.appendChild(button);
    tr.appendChild(tdAcao);

    tabelaCorpo.appendChild(tr);
  });
}

function renderizarControlesPaginacao() {
  const paginacao = getPaginacaoAuditoria();
  const resumo = document.getElementById("auditoria-resumo-paginacao");
  const paginaAtual = document.getElementById("auditoria-pagina-atual");
  const btnAnterior = document.getElementById("btn-pagina-anterior");
  const btnProxima = document.getElementById("btn-proxima-pagina");

  resumo.textContent = `${paginacao.total_registros} registro(s)`;
  paginaAtual.textContent = `Página ${paginacao.page} de ${paginacao.total_paginas}`;
  btnAnterior.classList.toggle("d-none", !paginacao.has_previous);
  btnProxima.classList.toggle("d-none", !paginacao.has_next);
}

async function executarConsulta(resetPagina = false) {
  clearMessages();

  const dataInicio = getForm(nomeForm)?.campos?.data_inicio;
  const dataFim = getForm(nomeForm)?.campos?.data_fim;
  if (dataInicio && dataFim && dataInicio > dataFim) {
    definirMensagem("erro", "A data inicial não pode ser maior que a data final.", false);
    return;
  }

  if (resetPagina) {
    updateFormField(nomeForm, "page", 1);
  }

  AppLoader.show();
  const resultado = await fazerRequisicao("/app/auditoria/consulta/cons", {
    form: {
      [nomeForm]: getForm(nomeForm),
    },
  });

  if (!resultado.success) {
    if (resultado.data) {
      updateState(resultado.data);
    } else {
      definirMensagem("erro", `Erro ao consultar auditoria: ${resultado.error}`, false);
    }
    AppLoader.hide();
    return;
  }

  updateState(resultado.data);
  updateFormField(nomeForm, "page", getPaginacaoAuditoria().page);
  updateFormField(nomeForm, "per_page", getPaginacaoAuditoria().per_page);
  preencherSelectAtores();
  preencherSelectAcoes();
  preencherSelectApps();
  preencherSelectModels();
  renderizarTabela();
  renderizarControlesPaginacao();

  if ((getContextoAuditoria().registros || []).length === 0) {
    definirMensagem("info", "Nenhum evento encontrado para os filtros informados.");
  }

  AppLoader.hide();
}

document.addEventListener("DOMContentLoaded", () => {
  AppLoader.show();

  preencherSelectAtores();
  preencherSelectAcoes();
  preencherSelectApps();
  preencherSelectModels();
  renderizarTabela();
  renderizarControlesPaginacao();
  setFormState(nomeForm, "novo");
  updateFormField(nomeForm, "page", 1);
  updateFormField(nomeForm, "per_page", getPaginacaoAuditoria().per_page || 20);

  document.getElementById("app_label").addEventListener("change", event => {
    updateFormField(nomeForm, "app_label", event.target.value);
    preencherSelectModels();
  });

  document.getElementById("btn-limpar").addEventListener("click", () => {
    clearMessages();
    setFormState(nomeForm, "novo");
    updateFormField(nomeForm, "page", 1);
    updateFormField(nomeForm, "per_page", 20);
    limparResultadosAuditoria();
    preencherSelectAtores();
    preencherSelectAcoes();
    preencherSelectApps();
    preencherSelectModels();
    renderizarTabela();
    renderizarControlesPaginacao();
  });

  form.addEventListener("submit", async event => {
    event.preventDefault();
    await executarConsulta(true);
  });

  document.getElementById("btn-pagina-anterior").addEventListener("click", async () => {
    const paginacao = getPaginacaoAuditoria();
    if (!paginacao.has_previous) {
      return;
    }

    updateFormField(nomeForm, "page", paginacao.page - 1);
    await executarConsulta(false);
  });

  document.getElementById("btn-proxima-pagina").addEventListener("click", async () => {
    const paginacao = getPaginacaoAuditoria();
    if (!paginacao.has_next) {
      return;
    }

    updateFormField(nomeForm, "page", paginacao.page + 1);
    await executarConsulta(false);
  });

  document.getElementById("tabela-auditoria-corpo").addEventListener("click", event => {
    const botao = event.target.closest(".btn-detalhes-auditoria");
    if (!botao) {
      return;
    }

    abrirModalDetalhes(Number(botao.dataset.index));
  });

  AppLoader.hide();
});