import {
  updateFormField,
  getForm,
  updateState,
  clearMessages,
  definirMensagem,
  hidratarFormulario,
  setFormState,
  confirmar,
  getOthers,
} from '/static/js/sisVar.js';
import { fazerRequisicao } from '/static/js/base.js';
import { initSmartInputs } from '/static/js/input_rules.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { AppLoader } from '/static/js/loader.js';

const nomeForm     = 'cadCliente';
const nomeFormCons = 'consCliente';
const form  = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

// ── Atualizadores de sisVar ───────────────────────────────────────────────────
const updater = criarAtualizadorForm({ formId: nomeForm, setter: updateFormField, form });
form.addEventListener('input',  updater);
form.addEventListener('change', updater);

const updater2 = criarAtualizadorForm({ formId: nomeFormCons, setter: updateFormField, form: form2 });
form2.addEventListener('input', updater2);

initSmartInputs((input, value) => {
  const formId = input.closest('form')?.id;
  if (formId) updateFormField(formId, input.name, value);
});

// ── Populadores de Select a partir de opcoes do backend ──────────────────────

function preencherSelectGrupos() {
  const sel = document.getElementById('grupo');
  const grupos = getOthers()?.opcoes?.grupos ?? [];
  sel.innerHTML = '<option value="">Selecione</option>';
  grupos.forEach(g => {
    const opt = document.createElement('option');
    opt.value = g.id;
    opt.textContent = g.descricao;
    sel.appendChild(opt);
  });
}

function preencherSelectPaises() {
  const sel = document.getElementById('pais');
  const paises = getOthers()?.opcoes?.paises ?? [];
  sel.innerHTML = '<option value="">Selecione</option>';
  paises.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.nome;
    sel.appendChild(opt);
  });
}

function preencherSelectRegioes(paisId) {
  const selRegiao = document.getElementById('regiao');
  const selCidade = document.getElementById('cidade');
  selRegiao.innerHTML = '<option value="">Selecione</option>';
  selCidade.innerHTML = '<option value="">Selecione</option>';
  selCidade.disabled = true;

  if (!paisId) {
    selRegiao.disabled = true;
    return;
  }

  const regioes = (getOthers()?.opcoes?.regioes ?? []).filter(r => r.pais_id == paisId);
  regioes.forEach(r => {
    const opt = document.createElement('option');
    opt.value = r.id;
    opt.textContent = r.sigla ? `${r.sigla} - ${r.nome}` : r.nome;
    selRegiao.appendChild(opt);
  });
  selRegiao.disabled = regioes.length === 0;
}

function preencherSelectCidades(regiaoId) {
  const selCidade = document.getElementById('cidade');
  selCidade.innerHTML = '<option value="">Selecione</option>';

  if (!regiaoId) {
    selCidade.disabled = true;
    return;
  }

  const cidades = (getOthers()?.opcoes?.cidades ?? []).filter(c => c.regiao_id == regiaoId);
  cidades.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.nome;
    selCidade.appendChild(opt);
  });
  selCidade.disabled = cidades.length === 0;
}

// ── Cascata de selects ────────────────────────────────────────────────────────
document.getElementById('pais').addEventListener('change', function () {
  preencherSelectRegioes(this.value);
  updateFormField(nomeForm, 'pais', this.value ? parseInt(this.value) : null);
  updateFormField(nomeForm, 'regiao', null);
  updateFormField(nomeForm, 'cidade', null);
});

document.getElementById('regiao').addEventListener('change', function () {
  preencherSelectCidades(this.value);
  updateFormField(nomeForm, 'regiao', this.value ? parseInt(this.value) : null);
  updateFormField(nomeForm, 'cidade', null);
});

document.getElementById('cidade').addEventListener('change', function () {
  updateFormField(nomeForm, 'cidade', this.value ? parseInt(this.value) : null);
});

document.getElementById('grupo').addEventListener('change', function () {
  updateFormField(nomeForm, 'grupo', this.value ? parseInt(this.value) : null);
});

// ── Hidratar selects ao carregar um registro ──────────────────────────────────
function hidratarSelects(campos) {
  preencherSelectGrupos();
  preencherSelectPaises();

  const selGrupo  = document.getElementById('grupo');
  const selPais   = document.getElementById('pais');
  const selRegiao = document.getElementById('regiao');
  const selCidade = document.getElementById('cidade');

  if (campos.grupo)  selGrupo.value  = campos.grupo;
  if (campos.pais) {
    selPais.value = campos.pais;
    preencherSelectRegioes(campos.pais);
  }
  if (campos.regiao) {
    selRegiao.value = campos.regiao;
    preencherSelectCidades(campos.regiao);
  }
  if (campos.cidade) selCidade.value = campos.cidade;
}

// ── Submissão do formulário principal ────────────────────────────────────────
form.addEventListener('submit', async e => {
  e.preventDefault();
  clearMessages();

  const formData = getForm(nomeForm);
  if (!formData?.campos || Object.keys(formData.campos).length === 0) {
    definirMensagem('aviso', 'Preencha o formulário antes de enviar');
    return;
  }

  confirmar({
    titulo: 'Confirmar Salvamento',
    mensagem: 'Deseja salvar o registro?',
    onConfirmar: async () => {
      AppLoader.show();

      const resultado = await fazerRequisicao('/app/cad/cliente/', {
        form: { [nomeForm]: formData }
      });

      if (!resultado.success) {
        definirMensagem('erro', `Erro ao salvar: ${resultado.error}`, false);
        AppLoader.hide();
        return;
      }

      updateState(resultado.data);
      AppLoader.hide();
    }
  });
});

// ── Inicialização ao carregar o DOM ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const divPrincipal     = document.getElementById(nomeForm);
  const divPesquisa      = document.getElementById('div-pesquisa');
  const btnAbrirPesquisa = document.getElementById('btn-abrir-pesquisa');
  const btnVoltar        = document.getElementById('btn-voltar');
  const btnFechar        = document.getElementById('btn-fechar');
  const btnEditar        = document.getElementById('btn-editar');
  const btnNovo          = document.getElementById('btn-novo');
  const btnCancelar      = document.getElementById('btn-cancelar');
  const btnExcluir       = document.getElementById('btn-excluir');
  const formFiltro       = document.getElementById(nomeFormCons);
  const tabelaCorpo      = document.getElementById('tabela-corpo');

  // Popula selects ao carregar
  preencherSelectGrupos();
  preencherSelectPaises();

  // ── Alternância entre formulário e tela de pesquisa ──
  const alternarTelas = () => {
    divPrincipal.classList.toggle('d-none');
    divPesquisa.classList.toggle('d-none');
  };

  btnAbrirPesquisa.addEventListener('click', alternarTelas);
  btnVoltar.addEventListener('click', alternarTelas);
  btnFechar.addEventListener('click', alternarTelas);

  // ── Botão Editar ──
  btnEditar.addEventListener('click', () => setFormState(nomeForm, 'editar'));

  // ── Botão Novo ──
  btnNovo.addEventListener('click', () => {
    setFormState(nomeForm, 'novo');
    preencherSelectGrupos();
    preencherSelectPaises();
    document.getElementById('regiao').disabled = true;
    document.getElementById('cidade').disabled = true;
  });

  // ── Botão Cancelar ──
  btnCancelar.addEventListener('click', () => {
    confirmar({
      titulo: 'Confirmar Cancelamento',
      mensagem: 'Deseja cancelar? Os dados não salvos serão perdidos.',
      onConfirmar: () => setFormState(nomeForm, 'novo')
    });
  });

  // ── Botão Excluir ──
  btnExcluir.addEventListener('click', () => {
    confirmar({
      titulo: 'Confirmar Exclusão',
      mensagem: 'Deseja excluir este registro? Esta ação não pode ser desfeita.',
      onConfirmar: async () => {
        AppLoader.show();

        const formData = getForm(nomeForm);
        formData.estado = 'excluir';

        const resultado = await fazerRequisicao('/app/cad/cliente/', {
          form: { [nomeForm]: formData }
        });

        if (!resultado.success) {
          definirMensagem('erro', `Erro ao excluir: ${resultado.error}`, false);
          AppLoader.hide();
          return;
        }

        updateState(resultado.data);
        preencherSelectGrupos();
        preencherSelectPaises();
        document.getElementById('regiao').disabled = true;
        document.getElementById('cidade').disabled = true;
        AppLoader.hide();
      }
    });
  });

  // ── Busca / Filtro ──
  formFiltro.addEventListener('submit', async e => {
    e.preventDefault();
    clearMessages();
    AppLoader.show();

    const resultado = await fazerRequisicao('/app/cad/cliente/cons/', {
      form: { [nomeFormCons]: getForm(nomeFormCons) }
    });

    if (!resultado.success) {
      definirMensagem('erro', `Erro ao buscar clientes: ${resultado.error}`, false);
      AppLoader.hide();
      return;
    }

    updateState(resultado.data);

    if (resultado.data?.registros?.length > 0) {
      renderizarTabela(resultado.data.registros);
    } else {
      tabelaCorpo.innerHTML = '';
      definirMensagem('info', 'Nenhum cliente encontrado');
    }

    AppLoader.hide();
  });

  // ── Renderização da tabela ──
  function renderizarTabela(registros) {
    tabelaCorpo.innerHTML = '';

    if (!Array.isArray(registros) || registros.length === 0) {
      tabelaCorpo.innerHTML = '<tr><td colspan="9" class="text-center">Nenhum registro encontrado</td></tr>';
      return;
    }

    registros.forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${r.id ?? ''}</td>
        <td>${r.nome ?? ''}</td>
        <td>${r.rsocial ?? ''}</td>
        <td>${r.grupo ?? ''}</td>
        <td>${r.pais ?? ''}</td>
        <td>${r.regiao ?? ''}</td>
        <td>${r.cidade ?? ''}</td>
        <td>${r.identificador ?? ''}</td>
        <td class="text-center">
          <button class="btn btn-sm btn-primary btn-selecionar" data-id="${r.id}">
            Selecionar
          </button>
        </td>
      `;
      tabelaCorpo.appendChild(tr);
    });
  }

  // ── Event delegation — Selecionar registro ──
  tabelaCorpo.addEventListener('click', async e => {
    if (!e.target.classList.contains('btn-selecionar')) return;

    const id = e.target.dataset.id;
    if (!id) {
      definirMensagem('aviso', 'Erro ao selecionar o registro');
      return;
    }

    await carregarRegistro(id);
  });

  // ── Carregar registro selecionado ──
  async function carregarRegistro(id) {
    clearMessages();

    updateFormField(nomeFormCons, 'id_selecionado', id);

    const sisVarPayload = {
      form: { [nomeFormCons]: structuredClone(getForm(nomeFormCons)) }
    };

    updateFormField(nomeFormCons, 'id_selecionado', null);

    const resultado = await fazerRequisicao('/app/cad/cliente/cons/', sisVarPayload);

    if (!resultado.success) {
      definirMensagem('erro', `Erro ao carregar registro: ${resultado.error}`, false);
      AppLoader.hide();
      return;
    }

    updateState(resultado.data);
    hidratarFormulario(nomeForm);

    // Hidratar selects com os IDs retornados
    const campos = resultado.data?.form?.[nomeForm]?.campos ?? {};
    hidratarSelects(campos);

    setFormState(nomeForm, 'visualizar');
    alternarTelas();
    AppLoader.hide();
  }
});