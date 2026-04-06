import {
  clearMessages,
  confirmar,
  definirMensagem,
  getForm,
  getOthers,
  hidratarFormulario,
  setFormState,
  updateFormField,
  updateState,
} from "/static/js/sisVar.js";
import { fazerRequisicao } from "/static/js/base.js";
import { initSmartInputs } from "/static/js/input_rules.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";
import { AppLoader } from "/static/js/loader.js";
import { PERMISSOES_SCHEMA } from "./permissao_schema.js";

const nomeForm = "cadPermissaoUsuario";
const nomeFormCons = "consPermissaoUsuario";
const form = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

function getPermissoesGerenciaveis() {
  return new Set(getOthers().permissoes_gerenciaveis || []);
}

function getGruposGerenciaveis() {
  return new Set((getOthers().grupos_gerenciaveis_ids || []).map(String));
}

function alternarSecaoPermissoes(exibir) {
  const secao = document.getElementById("secao-permissoes-usuario");
  const placeholder = document.getElementById("permissoes-usuario-placeholder");

  if (secao) {
    secao.classList.toggle("d-none", !exibir);
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
  const usuarios = getOthers().usuarios_ativos || [];

  select.innerHTML = '<option value="">Selecione um usuário</option>';
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

  const grupos = getOthers().grupos_cadastrados || [];
  container.innerHTML = "";

  if (grupos.length === 0) {
    container.innerHTML = '<p class="text-muted fst-italic mb-0">Nenhum grupo cadastrado.</p>';
    return;
  }

  grupos.forEach(grupo => {
    const col = document.createElement("div");
    col.className = "col-12 col-sm-6 col-md-4";

    const id = `chk-grupo-${grupo.id}`;
    const gerenciavel = getGruposGerenciaveis().has(String(grupo.id));
    col.innerHTML = `
      <div class="form-check">
        <input class="form-check-input grupo-checkbox" type="checkbox"
          id="${id}"
          data-group-id="${grupo.id}"
          data-gerenciavel="${gerenciavel ? "true" : "false"}"
          title="${gerenciavel ? "" : "Grupo fora do seu escopo de atribuição"}"
          disabled>
        <label class="form-check-label" for="${id}">${grupo.nome}</label>
      </div>`;
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
      col.innerHTML = `
        <div class="form-check">
          <input class="form-check-input perm-checkbox" type="checkbox"
            id="${id}"
            data-codename="${codename}"
            data-gerenciavel="${gerenciavel ? "true" : "false"}"
            title="${gerenciavel ? "" : "Permissão fora do seu escopo de atribuição"}"
            disabled>
          <label class="form-check-label" for="${id}">${label}</label>
        </div>`;
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
  const somenteLeitura = !usuarioSelecionado || estado === "visualizar";
  const gruposGerenciaveis = getGruposGerenciaveis();
  const permissoesGerenciaveis = getPermissoesGerenciaveis();

  document.querySelectorAll(".grupo-checkbox").forEach(cb => {
    cb.disabled = somenteLeitura || !gruposGerenciaveis.has(cb.dataset.groupId);
  });

  document.querySelectorAll(".perm-checkbox").forEach(cb => {
    cb.disabled = somenteLeitura || !permissoesGerenciaveis.has(cb.dataset.codename);
  });
}

function resetarSelecaoUsuario() {
  setFormState(nomeForm, "novo");
  renderizarUsuariosSelect();
  aplicarGruposNosCheckboxes([]);
  aplicarPermissoesNosCheckboxes([]);
  alternarSecaoPermissoes(false);
  aplicarEstadoAssociacoes();
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
      aplicarGruposNosCheckboxes(resultado.data?.form?.[nomeForm]?.campos?.grupos || []);
      aplicarPermissoesNosCheckboxes(resultado.data?.form?.[nomeForm]?.campos?.permissoes || []);
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
    setFormState(nomeForm, "editar");
    alternarSecaoPermissoes(true);
    aplicarEstadoAssociacoes();
  });

  btnNovo.addEventListener("click", () => {
    resetarSelecaoUsuario();
  });

  btnCancelar.addEventListener("click", () => {
    confirmar({
      titulo: "Confirmar Cancelamento",
      mensagem: "Deseja cancelar? Os dados não salvos serão perdidos.",
      onConfirmar: () => {
        resetarSelecaoUsuario();
      }
    });
  });

  selectUsuario.addEventListener("change", async e => {
    const id = e.target.value;

    if (!id) {
      resetarSelecaoUsuario();
      return;
    }

    await carregarRegistro(id);
  });

  form2.addEventListener("submit", async e => {
    e.preventDefault();
    clearMessages();

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
      tabelaCorpo.innerHTML = '<tr><td colspan="4" class="text-center">Nenhum registro encontrado</td></tr>';
      return;
    }

    registros.forEach(reg => {
      const linha = document.createElement("tr");
      linha.innerHTML = `
        <td>${reg.id || ""}</td>
        <td>${reg.first_name || ""}</td>
        <td>${reg.username || ""}</td>
        <td class="text-center">
          <button class="btn btn-sm btn-primary btn-selecionar" data-id="${reg.id}">
            Selecionar
          </button>
        </td>`;
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

    await carregarRegistro(id, true);
  });

  async function carregarRegistro(id, fecharPesquisa = false) {
    clearMessages();

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
    aplicarGruposNosCheckboxes(resultado.data?.form?.[nomeForm]?.campos?.grupos || []);
    aplicarPermissoesNosCheckboxes(resultado.data?.form?.[nomeForm]?.campos?.permissoes || []);
    alternarSecaoPermissoes(true);
    setFormState(nomeForm, "visualizar");
    aplicarEstadoAssociacoes();

    if (fecharPesquisa && !divPesquisa.classList.contains("d-none")) {
      alternarTelas();
    }

    AppLoader.hide();
  }

  alternarSecaoPermissoes(Boolean(getForm(nomeForm)?.campos?.usuario_id));
  aplicarGruposNosCheckboxes(getForm(nomeForm)?.campos?.grupos || []);
  aplicarPermissoesNosCheckboxes(getForm(nomeForm)?.campos?.permissoes || []);
  aplicarEstadoAssociacoes();
});