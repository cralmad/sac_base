import {
  clearMessages,
  confirmar,
  definirMensagem,
  getForm,
  getDataset,
  getScreenPermissions,
  hidratarFormulario,
  setFormState,
  getDataBackEnd,
  updateFormField,
  updateState,
} from "/static/js/sisVar.js";
import { fazerRequisicao } from "/static/js/base.js";
import { initSmartInputs } from "/static/js/input_rules.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";
import { AppLoader } from "/static/js/loader.js";
import { PERMISSOES_SCHEMA } from "./permissao_schema.js";
import { buttonVisibleByState, createActionChecker } from '/static/js/screen_permissions.js';

const nomeForm = "cadPermissaoUsuario";
const nomeFormCons = "consPermissaoUsuario";
const form = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

getDataBackEnd();

const podeExecutarAcao = createActionChecker({
  screenKey: 'permissao_usuario',
  getScreenPermissions,
  fallback: {
    acessar: false,
    consultar: false,
    editar: false,
  },
});

function obterPermissoesTela() {
  return {
    acessar: podeExecutarAcao('acessar'),
    consultar: podeExecutarAcao('consultar'),
    editar: podeExecutarAcao('editar'),
  };
}

function podeConsultar() {
  return podeExecutarAcao('consultar');
}

function podeEditar() {
  return podeExecutarAcao('editar');
}

function botaoDeveFicarVisivel(botao, estado) {
  return buttonVisibleByState(botao, estado);
}

function getPermissoesGerenciaveis() {
  return new Set(getDataset('permissoes_gerenciaveis', []));
}

function getGruposGerenciaveis() {
  return new Set((getDataset('grupos_gerenciaveis_ids', []) || []).map(String));
}

function getFiliaisCadastradas() {
  return getDataset('filiais_cadastradas', []);
}

function alternarSecaoPermissoes(exibir) {
  const secao = document.getElementById("secao-permissoes-usuario");
  const placeholder = document.getElementById("permissoes-usuario-placeholder");

  if (secao) {
    secao.classList.remove("d-none");
  }

  if (placeholder) {
    placeholder.classList.toggle("d-none", exibir);
  }
}

function sincronizarCheckbox(codename, checked) {
  document.querySelectorAll(`input[type="checkbox"][data-codename="${codename}"]`)
    .forEach(cb => { cb.checked = checked; });
}

function renderizarUsuariosSelect() {
  const select = document.getElementById("usuario_id");
  if (!select) return;

  const usuarioSelecionado = String(getForm(nomeForm)?.campos?.usuario_id ?? "");
  const usuarios = getDataset('usuarios_ativos', []);

  select.innerHTML = '';
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = "Selecione um usuário";
  select.appendChild(defaultOption);
  usuarios.forEach(usuario => {
    const option = document.createElement("option");
    option.value = String(usuario.id);
    option.textContent = `${usuario.nome} (${usuario.username})`;
    select.appendChild(option);
  });

  select.value = usuarioSelecionado;
}

function renderizarGrupos() {
  const container = document.getElementById("grupos-disponiveis");
  if (!container) return;

  const grupos = getDataset('grupos_cadastrados', []);
  container.innerHTML = "";

  if (grupos.length === 0) {
    const vazio = document.createElement("p");
    vazio.className = "text-muted fst-italic mb-0";
    vazio.textContent = "Nenhum grupo cadastrado.";
    container.appendChild(vazio);
    return;
  }

  grupos.forEach(grupo => {
    const col = document.createElement("div");
    col.className = "col-12 col-sm-6 col-md-4";

    const id = `chk-grupo-${grupo.id}`;
    const gerenciavel = getGruposGerenciaveis().has(String(grupo.id));

    const wrapper = document.createElement("div");
    wrapper.className = "form-check";

    const input = document.createElement("input");
    input.className = "form-check-input grupo-checkbox";
    input.type = "checkbox";
    input.id = id;
    input.dataset.groupId = String(grupo.id ?? "");
    input.dataset.gerenciavel = gerenciavel ? "true" : "false";
    input.title = gerenciavel ? "" : "Grupo fora do seu escopo de atribuição";
    input.disabled = true;

    const label = document.createElement("label");
    label.className = "form-check-label";
    label.setAttribute("for", id);
    label.textContent = String(grupo.nome ?? "");

    wrapper.appendChild(input);
    wrapper.appendChild(label);
    col.appendChild(wrapper);
    container.appendChild(col);
  });

  document.querySelectorAll(".grupo-checkbox").forEach(cb => {
    cb.addEventListener("change", atualizarGruposNoSisVar);
  });
}

function renderizarAbas() {
  const modulos = Object.keys(PERMISSOES_SCHEMA);

  modulos.forEach(modulo => {
    const container = document.getElementById(`perms-${modulo}`);
    if (!container) return;

    const perms = PERMISSOES_SCHEMA[modulo];
    if (!perms || perms.length === 0) return;

    container.innerHTML = "";

    perms.forEach(({ codename, label }) => {
      const col = document.createElement("div");
      col.className = "col-12 col-sm-6 col-md-4";

      const id = `chk-${modulo}-${codename.replace(/\./g, "-")}`;
      const gerenciavel = getPermissoesGerenciaveis().has(codename);

      const wrapper = document.createElement("div");
      wrapper.className = "form-check";

      const input = document.createElement("input");
      input.className = "form-check-input perm-checkbox";
      input.type = "checkbox";
      input.id = id;
      input.dataset.codename = String(codename ?? "");
      input.dataset.gerenciavel = gerenciavel ? "true" : "false";
      input.title = gerenciavel ? "" : "Permissão fora do seu escopo de atribuição";
      input.disabled = true;

      const labelEl = document.createElement("label");
      labelEl.className = "form-check-label";
      labelEl.setAttribute("for", id);
      labelEl.textContent = String(label ?? "");

      wrapper.appendChild(input);
      wrapper.appendChild(labelEl);
      col.appendChild(wrapper);
      container.appendChild(col);
    });
  });

  document.querySelectorAll(".perm-checkbox").forEach(cb => {
    cb.addEventListener("change", () => {
      sincronizarCheckbox(cb.dataset.codename, cb.checked);
      atualizarPermissoesNoSisVar();
    });
  });
}

function atualizarGruposNoSisVar() {
  const grupos = [];
  const gruposGerenciaveis = getGruposGerenciaveis();
  document.querySelectorAll(".grupo-checkbox:checked").forEach(cb => {
    if (gruposGerenciaveis.has(cb.dataset.groupId)) {
      grupos.push(cb.dataset.groupId);
    }
  });
  updateFormField(nomeForm, "grupos", grupos);
}

function atualizarPermissoesNoSisVar() {
  const marcados = new Set();
  const permissoesGerenciaveis = getPermissoesGerenciaveis();
  document.querySelectorAll(".perm-checkbox:checked").forEach(cb => {
    if (permissoesGerenciaveis.has(cb.dataset.codename)) {
      marcados.add(cb.dataset.codename);
    }
  });
  updateFormField(nomeForm, "permissoes", [...marcados]);
}

function aplicarGruposNosCheckboxes(grupos = []) {
  const grupoSet = new Set((grupos || []).map(String));
  document.querySelectorAll(".grupo-checkbox").forEach(cb => {
    cb.checked = grupoSet.has(cb.dataset.groupId);
  });
  atualizarGruposNoSisVar();
}

function aplicarPermissoesNosCheckboxes(permissoes = []) {
  document.querySelectorAll(".perm-checkbox").forEach(cb => {
    cb.checked = false;
  });
  permissoes.forEach(codename => {
    sincronizarCheckbox(codename, true);
  });
  atualizarPermissoesNoSisVar();
}

function aplicarEstadoAssociacoes() {
  const estado = getForm(nomeForm)?.estado;
  const usuarioSelecionado = Boolean(getForm(nomeForm)?.campos?.usuario_id);
  const somenteLeitura = !podeEditar() || !usuarioSelecionado || estado === "visualizar";
  const gruposGerenciaveis = getGruposGerenciaveis();
  const permissoesGerenciaveis = getPermissoesGerenciaveis();

  document.querySelectorAll(".grupo-checkbox").forEach(cb => {
    cb.disabled = somenteLeitura || !gruposGerenciaveis.has(cb.dataset.groupId);
  });

  document.querySelectorAll(".perm-checkbox").forEach(cb => {
    cb.disabled = somenteLeitura || !permissoesGerenciaveis.has(cb.dataset.codename);
  });

  document.querySelectorAll('.filial-vinculo, .filial-consultar, .filial-escrever').forEach(input => {
    const row = input.closest('tr');
    if (!row) return;

    const vinculo = row.querySelector('.filial-vinculo');
    const consultar = row.querySelector('.filial-consultar');
    const escrever = row.querySelector('.filial-escrever');
    const bloqueado = somenteLeitura;

    vinculo.disabled = bloqueado;
    consultar.disabled = bloqueado || !vinculo.checked;
    escrever.disabled = bloqueado || !vinculo.checked;
  });
}

function renderizarFiliais() {
  const tabela = document.getElementById('tabela-filiais-usuario');
  if (!tabela) return;

  const filiais = getFiliaisCadastradas();
  tabela.innerHTML = '';

  if (!filiais.length) {
    const linhaVazia = document.createElement('tr');
    const celulaVazia = document.createElement('td');
    celulaVazia.colSpan = 7;
    celulaVazia.className = 'text-center text-muted';
    celulaVazia.textContent = 'Nenhuma matriz/filial cadastrada.';
    linhaVazia.appendChild(celulaVazia);
    tabela.appendChild(linhaVazia);
    return;
  }

  filiais.forEach((filial) => {
    const linha = document.createElement('tr');
    linha.dataset.filialId = String(filial.id);

    const tdCodigo = document.createElement('td');
    tdCodigo.textContent = String(filial.codigo ?? '');
    linha.appendChild(tdCodigo);

    const tdNome = document.createElement('td');
    tdNome.textContent = String(filial.nome ?? '');
    linha.appendChild(tdNome);

    const tdTipo = document.createElement('td');
    tdTipo.textContent = filial.is_matriz ? 'Matriz' : 'Filial';
    linha.appendChild(tdTipo);

    const tdStatus = document.createElement('td');
    tdStatus.textContent = filial.ativa ? 'Ativa' : 'Inativa';
    linha.appendChild(tdStatus);

    const criarCheckboxCell = (classe) => {
      const td = document.createElement('td');
      td.className = 'text-center';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.className = `form-check-input ${classe}`;
      td.appendChild(checkbox);
      return td;
    };

    linha.appendChild(criarCheckboxCell('filial-vinculo'));
    linha.appendChild(criarCheckboxCell('filial-consultar'));
    linha.appendChild(criarCheckboxCell('filial-escrever'));

    tabela.appendChild(linha);
  });

  tabela.querySelectorAll('.filial-vinculo').forEach((checkbox) => {
    checkbox.addEventListener('change', () => {
      const row = checkbox.closest('tr');
      const consultar = row.querySelector('.filial-consultar');
      const escrever = row.querySelector('.filial-escrever');

      if (!checkbox.checked) {
        consultar.checked = false;
        escrever.checked = false;
      } else if (!consultar.checked && !escrever.checked) {
        consultar.checked = true;
      }

      atualizarFiliaisNoSisVar();
      aplicarEstadoAssociacoes();
    });
  });

  tabela.querySelectorAll('.filial-consultar').forEach((checkbox) => {
    checkbox.addEventListener('change', () => {
      const row = checkbox.closest('tr');
      const vinculo = row.querySelector('.filial-vinculo');
      const escrever = row.querySelector('.filial-escrever');

      if (checkbox.checked) {
        vinculo.checked = true;
      }

      if (!checkbox.checked && escrever.checked) {
        checkbox.checked = true;
      }

      if (!checkbox.checked && !escrever.checked) {
        vinculo.checked = false;
      }

      atualizarFiliaisNoSisVar();
      aplicarEstadoAssociacoes();
    });
  });

  tabela.querySelectorAll('.filial-escrever').forEach((checkbox) => {
    checkbox.addEventListener('change', () => {
      const row = checkbox.closest('tr');
      const vinculo = row.querySelector('.filial-vinculo');
      const consultar = row.querySelector('.filial-consultar');

      if (checkbox.checked) {
        vinculo.checked = true;
        consultar.checked = true;
      }

      atualizarFiliaisNoSisVar();
      aplicarEstadoAssociacoes();
    });
  });
}

function atualizarFiliaisNoSisVar() {
  const filiais = [];
  document.querySelectorAll('#tabela-filiais-usuario tr[data-filial-id]').forEach((row) => {
    const ativo = row.querySelector('.filial-vinculo')?.checked || false;
    const podeConsultar = row.querySelector('.filial-consultar')?.checked || false;
    const podeEscrever = row.querySelector('.filial-escrever')?.checked || false;

    filiais.push({
      filial_id: Number(row.dataset.filialId),
      ativo,
      pode_consultar: ativo && (podeConsultar || podeEscrever),
      pode_escrever: ativo && podeEscrever,
    });
  });

  updateFormField(nomeForm, 'filiais', filiais);
}

function aplicarFiliaisNosCheckboxes(vinculos = []) {
  const vinculosMap = new Map((vinculos || []).map((item) => [String(item.filial_id), item]));

  document.querySelectorAll('#tabela-filiais-usuario tr[data-filial-id]').forEach((row) => {
    const vinculo = vinculosMap.get(row.dataset.filialId) || {
      ativo: false,
      pode_consultar: false,
      pode_escrever: false,
    };

    row.querySelector('.filial-vinculo').checked = Boolean(vinculo.ativo);
    row.querySelector('.filial-consultar').checked = Boolean(vinculo.ativo && (vinculo.pode_consultar || vinculo.pode_escrever));
    row.querySelector('.filial-escrever').checked = Boolean(vinculo.ativo && vinculo.pode_escrever);
  });

  atualizarFiliaisNoSisVar();
}

function resetarSelecaoUsuario() {
  setFormState(nomeForm, "novo");
  renderizarUsuariosSelect();
  aplicarGruposNosCheckboxes([]);
  aplicarPermissoesNosCheckboxes([]);
  aplicarFiliaisNosCheckboxes([]);
  alternarSecaoPermissoes(false);
  aplicarEstadoAssociacoes();
}

function aplicarPermissoesNaInterface() {
  const permissoes = obterPermissoesTela();
  const estadoAtual = getForm(nomeForm)?.estado ?? "visualizar";
  const btnSalvar = document.getElementById("btn-salvar");
  const btnEditar = document.getElementById("btn-editar");
  const btnNovo = document.getElementById("btn-novo");
  const btnCancelar = document.getElementById("btn-cancelar");
  const btnAbrirPesquisa = document.getElementById("btn-abrir-pesquisa");

  if (btnSalvar) {
    btnSalvar.classList.toggle("d-none", !(botaoDeveFicarVisivel(btnSalvar, estadoAtual) && permissoes.editar));
  }
  if (btnEditar) {
    btnEditar.classList.toggle("d-none", !(botaoDeveFicarVisivel(btnEditar, estadoAtual) && permissoes.editar));
  }
  if (btnNovo) {
    btnNovo.classList.toggle("d-none", !(botaoDeveFicarVisivel(btnNovo, estadoAtual) && permissoes.editar));
  }
  if (btnCancelar) {
    btnCancelar.classList.toggle("d-none", !(botaoDeveFicarVisivel(btnCancelar, estadoAtual) && permissoes.editar));
  }
  if (btnAbrirPesquisa) {
    btnAbrirPesquisa.classList.toggle("d-none", !permissoes.consultar);
  }
}

const updater = criarAtualizadorForm({ formId: nomeForm, setter: updateFormField, form });
form.addEventListener("input", updater);
form.addEventListener("change", updater);

const updater2 = criarAtualizadorForm({ formId: nomeFormCons, setter: updateFormField, form: form2 });
form2.addEventListener("input", updater2);

initSmartInputs((input, value) => {
  const formId = input.closest("form")?.id;
  if (formId) updateFormField(formId, input.name, value);
});

form.addEventListener("submit", async e => {
  e.preventDefault();
  clearMessages();
  atualizarGruposNoSisVar();
  atualizarPermissoesNoSisVar();
  atualizarFiliaisNoSisVar();

  if (!podeEditar()) {
    definirMensagem("erro", "Você não possui permissão para alterar permissões de usuários.", false);
    return;
  }

  const formData = getForm(nomeForm);
  if (!formData?.campos?.usuario_id) {
    definirMensagem("aviso", "Selecione um usuário ativo antes de salvar.");
    return;
  }

  confirmar({
    titulo: "Confirmar Salvamento",
    mensagem: "Deseja salvar as permissões do usuário?",
    onConfirmar: async () => {
      AppLoader.show();

      const resultado = await fazerRequisicao("/app/permissao/usuario/", {
        form: { [nomeForm]: formData }
      });

      if (!resultado.success) {
        if (resultado.data) {
          updateState(resultado.data);
        } else {
          definirMensagem("erro", `Erro ao enviar dados: ${resultado.error}`, false);
        }
        AppLoader.hide();
        return;
      }

      updateState(resultado.data);
      hidratarFormulario(nomeForm);
      renderizarFiliais();
      aplicarGruposNosCheckboxes(resultado.data?.form?.[nomeForm]?.campos?.grupos || []);
      aplicarPermissoesNosCheckboxes(resultado.data?.form?.[nomeForm]?.campos?.permissoes || []);
      aplicarFiliaisNosCheckboxes(resultado.data?.form?.[nomeForm]?.campos?.filiais || []);
      renderizarUsuariosSelect();
      alternarSecaoPermissoes(true);
      aplicarEstadoAssociacoes();
      AppLoader.hide();
    }
  });
});

document.addEventListener("DOMContentLoaded", () => {
  renderizarUsuariosSelect();
  renderizarGrupos();
  renderizarAbas();
  renderizarFiliais();

  const divPrincipal = document.getElementById(nomeForm);
  const divPesquisa = document.getElementById("div-pesquisa");
  const btnAbrirPesquisa = document.getElementById("btn-abrir-pesquisa");
  const btnVoltar = document.getElementById("btn-voltar");
  const btnFechar = document.getElementById("btn-fechar");
  const btnEditar = document.getElementById("btn-editar");
  const btnNovo = document.getElementById("btn-novo");
  const btnCancelar = document.getElementById("btn-cancelar");
  const tabelaCorpo = document.getElementById("tabela-corpo-usuarios");
  const selectUsuario = document.getElementById("usuario_id");

  const alternarTelas = () => {
    divPrincipal.classList.toggle("d-none");
    divPesquisa.classList.toggle("d-none");
  };

  btnAbrirPesquisa.addEventListener("click", alternarTelas);
  btnVoltar.addEventListener("click", alternarTelas);
  btnFechar.addEventListener("click", alternarTelas);

  btnEditar.addEventListener("click", () => {
    clearMessages();
    if (!podeEditar()) {
      definirMensagem("erro", "Você não possui permissão para alterar permissões de usuários.", false);
      return;
    }

    setFormState(nomeForm, "editar");
    alternarSecaoPermissoes(true);
    aplicarEstadoAssociacoes();
    aplicarPermissoesNaInterface();
  });

  btnNovo.addEventListener("click", () => {
    clearMessages();
    if (!podeEditar()) {
      definirMensagem("erro", "Você não possui permissão para alterar permissões de usuários.", false);
      return;
    }

    resetarSelecaoUsuario();
    aplicarPermissoesNaInterface();
  });

  btnCancelar.addEventListener("click", () => {
    confirmar({
      titulo: "Confirmar Cancelamento",
      mensagem: "Deseja cancelar? Os dados não salvos serão perdidos.",
      onConfirmar: () => {
        resetarSelecaoUsuario();
        aplicarPermissoesNaInterface();
      }
    });
  });

  selectUsuario.addEventListener("change", async e => {
    const id = e.target.value;

    if (!podeConsultar()) {
      definirMensagem("erro", "Você não possui permissão para consultar usuários.", false);
      e.target.value = "";
      return;
    }

    if (!id) {
      resetarSelecaoUsuario();
      return;
    }

    await carregarRegistro(id);
  });

  form2.addEventListener("submit", async e => {
    e.preventDefault();
    clearMessages();

    if (!podeConsultar()) {
      definirMensagem("erro", "Você não possui permissão para consultar usuários.", false);
      return;
    }

    const resultado = await fazerRequisicao("/app/permissao/usuario/cons", {
      form: { [nomeFormCons]: getForm(nomeFormCons) }
    });

    if (!resultado.success) {
      if (resultado.data) {
        updateState(resultado.data);
      } else {
        definirMensagem("erro", `Erro ao buscar usuários: ${resultado.error}`, false);
      }
      AppLoader.hide();
      return;
    }

    updateState(resultado.data);
  aplicarPermissoesNaInterface();

    if (resultado.data?.registros?.length > 0) {
      renderizarTabela(resultado.data.registros);
    } else {
      tabelaCorpo.innerHTML = "";
      definirMensagem("info", "Nenhum usuário ativo encontrado.");
    }
    AppLoader.hide();
  });

  function renderizarTabela(registros) {
    tabelaCorpo.innerHTML = "";

    if (!Array.isArray(registros) || registros.length === 0) {
      const linhaSemDados = document.createElement("tr");
      const celulaSemDados = document.createElement("td");
      celulaSemDados.colSpan = 4;
      celulaSemDados.className = "text-center";
      celulaSemDados.textContent = "Nenhum registro encontrado";
      linhaSemDados.appendChild(celulaSemDados);
      tabelaCorpo.appendChild(linhaSemDados);
      return;
    }

    registros.forEach(reg => {
      const linha = document.createElement("tr");

      const tdId = document.createElement("td");
      tdId.textContent = String(reg.id ?? "");

      const tdNome = document.createElement("td");
      tdNome.textContent = String(reg.first_name ?? "");

      const tdLogin = document.createElement("td");
      tdLogin.textContent = String(reg.username ?? "");

      const tdAcao = document.createElement("td");
      tdAcao.className = "text-center";
      const btnSelecionar = document.createElement("button");
      btnSelecionar.className = "btn btn-sm btn-primary btn-selecionar";
      btnSelecionar.dataset.id = String(reg.id ?? "");
      btnSelecionar.textContent = "Selecionar";

      tdAcao.appendChild(btnSelecionar);
      linha.appendChild(tdId);
      linha.appendChild(tdNome);
      linha.appendChild(tdLogin);
      linha.appendChild(tdAcao);
      tabelaCorpo.appendChild(linha);
    });
  }

  tabelaCorpo.addEventListener("click", async e => {
    if (!e.target.classList.contains("btn-selecionar")) return;

    const id = e.target.dataset.id;
    if (!id) {
      definirMensagem("aviso", "Erro ao selecionar o usuário.");
      return;
    }

    if (!podeConsultar()) {
      definirMensagem("erro", "Você não possui permissão para consultar usuários.", false);
      return;
    }

    await carregarRegistro(id, true);
  });

  async function carregarRegistro(id, fecharPesquisa = false) {
    clearMessages();

    if (!podeConsultar()) {
      definirMensagem("erro", "Você não possui permissão para consultar usuários.", false);
      return;
    }

    updateFormField(nomeFormCons, "id_selecionado", id);
    const sisVarPayload = { form: { [nomeFormCons]: structuredClone(getForm(nomeFormCons)) } };
    updateFormField(nomeFormCons, "id_selecionado", null);

    const resultado = await fazerRequisicao("/app/permissao/usuario/cons", sisVarPayload);

    if (!resultado.success) {
      if (resultado.data) {
        updateState(resultado.data);
      } else {
        definirMensagem("erro", `Erro ao carregar usuário: ${resultado.error}`, false);
      }
      AppLoader.hide();
      return;
    }

    updateState(resultado.data);
    hidratarFormulario(nomeForm);
    renderizarUsuariosSelect();
    renderizarFiliais();
    aplicarGruposNosCheckboxes(resultado.data?.form?.[nomeForm]?.campos?.grupos || []);
    aplicarPermissoesNosCheckboxes(resultado.data?.form?.[nomeForm]?.campos?.permissoes || []);
    aplicarFiliaisNosCheckboxes(resultado.data?.form?.[nomeForm]?.campos?.filiais || []);
    alternarSecaoPermissoes(true);
    setFormState(nomeForm, "visualizar");
    aplicarEstadoAssociacoes();
    aplicarPermissoesNaInterface();

    if (fecharPesquisa && !divPesquisa.classList.contains("d-none")) {
      alternarTelas();
    }

    AppLoader.hide();
  }

  alternarSecaoPermissoes(Boolean(getForm(nomeForm)?.campos?.usuario_id));
  aplicarGruposNosCheckboxes(getForm(nomeForm)?.campos?.grupos || []);
  aplicarPermissoesNosCheckboxes(getForm(nomeForm)?.campos?.permissoes || []);
  aplicarFiliaisNosCheckboxes(getForm(nomeForm)?.campos?.filiais || []);
  aplicarEstadoAssociacoes();
  aplicarPermissoesNaInterface();
});