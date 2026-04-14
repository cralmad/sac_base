import {
  updateFormField,
  getForm,
  updateState,
  clearMessages,
  definirMensagem,
  hidratarFormulario,
  setFormState,
  confirmar,
  getScreenPermissions,
  getDataBackEnd
} from "/static/js/sisVar.js";
import { fazerRequisicao } from "/static/js/base.js";
import { initSmartInputs } from "/static/js/input_rules.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";
import { AppLoader } from "/static/js/loader.js";
import { PERMISSOES_SCHEMA } from "./permissao_schema.js";
import { buttonVisibleByState, buttonAllowedByPermission, createActionChecker } from '/static/js/screen_permissions.js';

const nomeForm     = "cadGrupo";
const nomeFormCons = "consGrupo";
const form         = document.getElementById(nomeForm);
const form2        = document.getElementById(nomeFormCons);

getDataBackEnd();

const podeExecutarAcao = createActionChecker({
  screenKey: 'permissao_grupo',
  getScreenPermissions,
  fallback: {
    acessar: false,
    consultar: false,
    incluir: false,
    editar: false,
    excluir: false,
  },
});

function obterPermissoesGrupo() {
  return {
    acessar: podeExecutarAcao('acessar'),
    consultar: podeExecutarAcao('consultar'),
    incluir: podeExecutarAcao('incluir'),
    editar: podeExecutarAcao('editar'),
    excluir: podeExecutarAcao('excluir'),
  };
}

function botaoDeveFicarVisivel(botao, estado) {
  return buttonVisibleByState(botao, estado);
}

function podeExibirBotaoPorPermissao(botaoId, estado) {
  return buttonAllowedByPermission({ buttonId: botaoId, state: estado, canExecute: podeExecutarAcao });
}

function validarPermissaoPorEstado(estado) {
  if (estado === "novo" && !podeExecutarAcao("incluir")) {
    definirMensagem("erro", "Você não possui permissão para incluir grupos de permissão.", false);
    return false;
  }

  if (estado === "editar" && !podeExecutarAcao("editar")) {
    definirMensagem("erro", "Você não possui permissão para editar grupos de permissão.", false);
    return false;
  }

  if (estado === "excluir" && !podeExecutarAcao("excluir")) {
    definirMensagem("erro", "Você não possui permissão para excluir grupos de permissão.", false);
    return false;
  }

  return true;
}

// ---------------------------------------------------------------------------
// Sincronismo de checkboxes: marcar um codename em qualquer aba
// marca automaticamente o mesmo codename em todas as demais abas.
// ---------------------------------------------------------------------------
function sincronizarCheckbox(codename, checked) {
  document.querySelectorAll(`input[type="checkbox"][data-codename="${codename}"]`)
    .forEach(cb => { cb.checked = checked; });
}

// ---------------------------------------------------------------------------
// Renderiza os checkboxes de cada módulo a partir do schema
// ---------------------------------------------------------------------------
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

      const wrapper = document.createElement("div");
      wrapper.className = "form-check";

      const input = document.createElement("input");
      input.className = "form-check-input perm-checkbox";
      input.type = "checkbox";
      input.id = id;
      input.dataset.codename = String(codename ?? "");
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

  // Delegação de evento: sincroniza todas as abas ao marcar qualquer checkbox
  document.querySelectorAll(".perm-checkbox").forEach(cb => {
    cb.addEventListener("change", () => {
      sincronizarCheckbox(cb.dataset.codename, cb.checked);
      atualizarPermissoesNoSisVar();
    });
  });
}

// ---------------------------------------------------------------------------
// Lê todos os checkboxes marcados e grava a lista em sisVar.form.cadGrupo.campos.permissoes
// Usa Set para evitar duplicatas (mesma permissão em múltiplas abas).
// ---------------------------------------------------------------------------
function atualizarPermissoesNoSisVar() {
  const marcados = new Set();
  document.querySelectorAll(".perm-checkbox:checked").forEach(cb => {
    marcados.add(cb.dataset.codename);
  });
  updateFormField(nomeForm, "permissoes", [...marcados]);
}

// ---------------------------------------------------------------------------
// Aplica lista de codenames recebida do back-end aos checkboxes
// ---------------------------------------------------------------------------
function aplicarPermissoesNosCheckboxes(permissoes = []) {
  // Desmarca tudo primeiro
  document.querySelectorAll(".perm-checkbox").forEach(cb => {
    cb.checked = false;
  });
  // Marca os recebidos (sincroniza automaticamente todas as abas)
  permissoes.forEach(codename => {
    sincronizarCheckbox(codename, true);
  });
}

// ---------------------------------------------------------------------------
// Habilita/desabilita checkboxes conforme o estado do formulário
// ---------------------------------------------------------------------------
function bloquearCheckboxes(bloquear) {
  document.querySelectorAll(".perm-checkbox").forEach(cb => {
    cb.disabled = bloquear;
  });
}

// ---------------------------------------------------------------------------
// Atualizadores de formulário (padrão do projeto)
// ---------------------------------------------------------------------------
const updater = criarAtualizadorForm({ formId: nomeForm, setter: updateFormField, form });
form.addEventListener("input", updater);

const updater2 = criarAtualizadorForm({ formId: nomeFormCons, setter: updateFormField, form: form2 });
form2.addEventListener("input", updater2);

initSmartInputs((input, value) => {
  const formId = input.closest("form")?.id;
  if (formId) updateFormField(formId, input.name, value);
});

// ---------------------------------------------------------------------------
// Submit do formulário principal
// ---------------------------------------------------------------------------
form.addEventListener("submit", async e => {
  e.preventDefault();
  clearMessages();

  // Garante que as permissões estão atualizadas no sisVar antes de enviar
  atualizarPermissoesNoSisVar();

  const formData = getForm(nomeForm);
  if (!validarPermissaoPorEstado(formData?.estado)) {
    return;
  }

  if (!formData?.campos?.nome) {
    definirMensagem("aviso", "Preencha o nome do grupo antes de salvar.");
    return;
  }

  confirmar({
    titulo: "Confirmar Salvamento",
    mensagem: "Deseja salvar o registro?",
    onConfirmar: async () => {
      AppLoader.show();

      const resultado = await fazerRequisicao("/app/permissao/grupos/", {
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

      // Aplica permissões retornadas do back-end nos checkboxes
      const permissoesRetornadas = resultado.data?.form?.[nomeForm]?.campos?.permissoes || [];
      aplicarPermissoesNosCheckboxes(permissoesRetornadas);
      bloquearCheckboxes(true);

      AppLoader.hide();
    }
  });
});

// ---------------------------------------------------------------------------
// Inicialização do DOM
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  // Renderiza os checkboxes das abas a partir do schema
  renderizarAbas();

  const divPrincipal       = document.getElementById(nomeForm);
  const divPesquisa        = document.getElementById("div-pesquisa");
  const btnAbrirPesquisa   = document.getElementById("btn-abrir-pesquisa");
  const btnVoltar          = document.getElementById("btn-voltar");
  const btnFechar          = document.getElementById("btn-fechar");
  const btnEditar          = document.getElementById("btn-editar");
  const btnNovo            = document.getElementById("btn-novo");
  const btnCancelar        = document.getElementById("btn-cancelar");
  const btnExcluir         = document.getElementById("btn-excluir");
  const btnSalvar          = document.getElementById("btn-salvar");
  const formFiltro         = document.getElementById(nomeFormCons);
  const tabelaCorpo        = document.getElementById("tabela-corpo");

  function aplicarPermissoesNaInterface() {
    const permissoes = obterPermissoesGrupo();
    const estadoAtual = getForm(nomeForm)?.estado ?? "visualizar";
    const botoesControlados = [btnSalvar, btnEditar, btnNovo, btnExcluir, btnCancelar];

    btnAbrirPesquisa.classList.toggle("d-none", !permissoes.consultar);

    botoesControlados.forEach(botao => {
      const visivelNoEstado = botaoDeveFicarVisivel(botao, estadoAtual);
      const visivelNaPermissao = podeExibirBotaoPorPermissao(botao.id, estadoAtual);
      botao.classList.toggle("d-none", !(visivelNoEstado && visivelNaPermissao));
    });

    if (!permissoes.consultar && !divPesquisa.classList.contains("d-none")) {
      alternarTelas();
    }
  }

  const alternarTelas = () => {
    divPrincipal.classList.toggle("d-none");
    divPesquisa.classList.toggle("d-none");
  };

  btnAbrirPesquisa.addEventListener("click", alternarTelas);
  btnVoltar.addEventListener("click", alternarTelas);
  btnFechar.addEventListener("click", alternarTelas);

  // Botão Editar
  btnEditar.addEventListener("click", () => {
    clearMessages();
    if (!podeExecutarAcao("editar")) {
      definirMensagem("erro", "Você não possui permissão para editar grupos de permissão.", false);
      return;
    }

    setFormState(nomeForm, "editar");
    bloquearCheckboxes(false);
    aplicarPermissoesNaInterface();
  });

  // Botão Novo
  btnNovo.addEventListener("click", () => {
    clearMessages();
    if (!podeExecutarAcao("incluir")) {
      definirMensagem("erro", "Você não possui permissão para incluir grupos de permissão.", false);
      return;
    }

    setFormState(nomeForm, "novo");
    aplicarPermissoesNosCheckboxes([]);
    bloquearCheckboxes(false);
    aplicarPermissoesNaInterface();
  });

  // Botão Cancelar
  btnCancelar.addEventListener("click", () => {
    confirmar({
      titulo: "Confirmar Cancelamento",
      mensagem: "Deseja cancelar? Os dados não salvos serão perdidos.",
      onConfirmar: () => {
        setFormState(nomeForm, podeExecutarAcao("incluir") ? "novo" : "visualizar");
        aplicarPermissoesNosCheckboxes([]);
        bloquearCheckboxes(false);
        aplicarPermissoesNaInterface();
      }
    });
  });

  // Botão Excluir
  btnExcluir.addEventListener("click", () => {
    confirmar({
      titulo: "Confirmar Exclusão",
      mensagem: "Deseja excluir este grupo? Esta ação não pode ser desfeita.",
      onConfirmar: async () => {
        AppLoader.show();
        clearMessages();

        const formData = getForm(nomeForm);
        formData.estado = "excluir";

        if (!validarPermissaoPorEstado(formData.estado)) {
          AppLoader.hide();
          return;
        }

        const resultado = await fazerRequisicao("/app/permissao/grupos/", {
          form: { [nomeForm]: formData }
        });

        if (!resultado.success) {
          if (resultado.data) {
            updateState(resultado.data);
          } else {
            definirMensagem("erro", `Erro ao excluir: ${resultado.error}`, false);
          }
          AppLoader.hide();
          return;
        }

        updateState(resultado.data);
        hidratarFormulario(nomeForm);
        aplicarPermissoesNosCheckboxes([]);
        bloquearCheckboxes(false);
        aplicarPermissoesNaInterface();
        AppLoader.hide();
      }
    });
  });

  // Busca de grupos
  formFiltro.addEventListener("submit", async e => {
    e.preventDefault();
    clearMessages();

    if (!podeExecutarAcao("consultar")) {
      definirMensagem("erro", "Você não possui permissão para consultar grupos de permissão.", false);
      return;
    }

    const resultado = await fazerRequisicao("/app/permissao/grupos/cons", {
      form: { [nomeFormCons]: getForm(nomeFormCons) }
    });

    if (!resultado.success) {
      if (resultado.data) {
        updateState(resultado.data);
      } else {
        definirMensagem("erro", `Erro ao buscar grupos: ${resultado.error}`, false);
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
      definirMensagem("info", "Nenhum grupo encontrado.");
    }
    AppLoader.hide();
  });

  // Renderização da tabela de resultados
  function renderizarTabela(registros) {
    tabelaCorpo.innerHTML = "";

    if (!Array.isArray(registros) || registros.length === 0) {
      const linhaSemDados = document.createElement("tr");
      const celulaSemDados = document.createElement("td");
      celulaSemDados.colSpan = 3;
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
      tdNome.textContent = String(reg.name ?? "");

      const tdAcao = document.createElement("td");
      tdAcao.className = "text-center";
      const btnSelecionar = document.createElement("button");
      btnSelecionar.className = "btn btn-sm btn-primary btn-selecionar";
      btnSelecionar.dataset.id = String(reg.id ?? "");
      btnSelecionar.textContent = "Selecionar";

      tdAcao.appendChild(btnSelecionar);
      linha.appendChild(tdId);
      linha.appendChild(tdNome);
      linha.appendChild(tdAcao);
      tabelaCorpo.appendChild(linha);
    });
  }

  // Event delegation — botão Selecionar
  tabelaCorpo.addEventListener("click", async e => {
    if (!e.target.classList.contains("btn-selecionar")) return;

    const id = e.target.dataset.id;
    if (!id) { definirMensagem("aviso", "Erro ao selecionar o registro."); return; }

    if (!podeExecutarAcao("consultar")) {
      definirMensagem("erro", "Você não possui permissão para consultar grupos de permissão.", false);
      return;
    }

    await carregarRegistro(id);
  });

  // Carrega grupo selecionado
  async function carregarRegistro(id) {
    clearMessages();

    if (!podeExecutarAcao("consultar")) {
      definirMensagem("erro", "Você não possui permissão para consultar grupos de permissão.", false);
      return;
    }

    updateFormField(nomeFormCons, "id_selecionado", id);
    const sisVarPayload = { form: { [nomeFormCons]: structuredClone(getForm(nomeFormCons)) } };
    updateFormField(nomeFormCons, "id_selecionado", null);

    const resultado = await fazerRequisicao("/app/permissao/grupos/cons", sisVarPayload);

    if (!resultado.success) {
      if (resultado.data) {
        updateState(resultado.data);
      } else {
        definirMensagem("erro", `Erro ao carregar registro: ${resultado.error}`, false);
      }
      AppLoader.hide();
      return;
    }

    updateState(resultado.data);
    hidratarFormulario(nomeForm);

    // Aplica as permissões do grupo nos checkboxes e bloqueia (modo visualizar)
    const permissoes = resultado.data?.form?.[nomeForm]?.campos?.permissoes || [];
    aplicarPermissoesNosCheckboxes(permissoes);
    bloquearCheckboxes(true);

    setFormState(nomeForm, "visualizar");
    aplicarPermissoesNaInterface();
    alternarTelas();
    AppLoader.hide();
  }

  aplicarPermissoesNaInterface();
});