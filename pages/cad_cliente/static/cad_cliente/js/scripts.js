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
  getDataBackEnd,
} from '/static/js/sisVar.js';
import { fazerRequisicao } from '/static/js/base.js';
import { initSmartInputs } from '/static/js/input_rules.js';
import { initHierarchicalSelects } from '/static/js/conditional_select.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { AppLoader } from '/static/js/loader.js';
import { buttonVisibleByState, buttonAllowedByPermission, createActionChecker } from '/static/js/screen_permissions.js';

// ── Bloqueio de cliques precoces no carregamento da página ────────────────────
AppLoader.show();
document.addEventListener('DOMContentLoaded', () => AppLoader.hide());

const nomeForm     = 'cadCliente';
const nomeFormCons = 'consCliente';
const form  = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);
let hierarquiaGeograficaInicializada = false;

getDataBackEnd();

const podeExecutarAcao = createActionChecker({
  screenKey: 'cad_cliente',
  getScreenPermissions,
  fallback: {
    acessar: false,
    consultar: false,
    incluir: false,
    editar: false,
    excluir: false,
  },
});

function botaoDeveFicarVisivel(botao, estado) {
  return buttonVisibleByState(botao, estado);
}

function podeExibirBotaoPorPermissao(botaoId, estado) {
  return buttonAllowedByPermission({ buttonId: botaoId, state: estado, canExecute: podeExecutarAcao });
}

function obterPermissoesCliente() {
  return {
    acessar: podeExecutarAcao('acessar'),
    consultar: podeExecutarAcao('consultar'),
    incluir: podeExecutarAcao('incluir'),
    editar: podeExecutarAcao('editar'),
    excluir: podeExecutarAcao('excluir'),
  };
}

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
  const grupos = getOptions('grupos', []);
  sel.innerHTML = '';
  const optionPadrao = document.createElement('option');
  optionPadrao.value = '';
  optionPadrao.textContent = 'Selecione';
  sel.appendChild(optionPadrao);
  grupos.forEach(g => {
    const opt = document.createElement('option');
    opt.value = g.id;
    opt.textContent = g.descricao;
    sel.appendChild(opt);
  });
}

function preencherSelectPaises() {
  if (hierarquiaGeograficaInicializada) {
    return;
  }

  const paises = getOptions('paises', []);
  const regioes = getOptions('regioes', []);
  const cidades = getOptions('cidades', []);

  const regioesPorId = new Map(regioes.map(regiao => [String(regiao.id), regiao]));
  const hierarchy = {};

  paises.forEach((pais) => {
    hierarchy[String(pais.id)] = {
      label: pais.nome,
      children: {},
    };
  });

  regioes.forEach((regiao) => {
    const paisNode = hierarchy[String(regiao.pais_id)];
    if (!paisNode) {
      return;
    }

    paisNode.children[String(regiao.id)] = {
      label: regiao.sigla ? `${regiao.sigla} - ${regiao.nome}` : regiao.nome,
      children: {},
    };
  });

  cidades.forEach((cidade) => {
    const regiao = regioesPorId.get(String(cidade.regiao_id));
    if (!regiao) {
      return;
    }

    const paisNode = hierarchy[String(regiao.pais_id)];
    const regiaoNode = paisNode?.children?.[String(cidade.regiao_id)];
    if (!regiaoNode) {
      return;
    }

    regiaoNode.children[String(cidade.id)] = {
      label: cidade.nome,
    };
  });

  initHierarchicalSelects(form, {
    cad_cliente_geo: hierarchy,
  });

  hierarquiaGeograficaInicializada = true;
}

// ── Cascata de selects ────────────────────────────────────────────────────────
document.getElementById('pais').addEventListener('change', function () {
  updateFormField(nomeForm, 'pais', this.value ? parseInt(this.value) : null);
  updateFormField(nomeForm, 'regiao', null);
  updateFormField(nomeForm, 'cidade', null);
});

document.getElementById('regiao').addEventListener('change', function () {
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
    selPais.dispatchEvent(new Event('change', { bubbles: true }));
  }
  if (campos.regiao) {
    selRegiao.value = campos.regiao;
    selRegiao.dispatchEvent(new Event('change', { bubbles: true }));
  }
  if (campos.cidade) selCidade.value = campos.cidade;
}

// ── Validação JS ──────────────────────────────────────────────────────────────
function validarFormulario(campos) {
  const erros = [];

  if (!campos.grupo) {
    erros.push('Grupo é obrigatório.');
  }
  if (!campos.nome || campos.nome.trim().length === 0) {
    erros.push('Nome é obrigatório.');
  } else if (campos.nome.trim().length < 3) {
    erros.push('Nome deve ter pelo menos 3 caracteres.');
  }
  if (!campos.rsocial || campos.rsocial.trim().length === 0) {
    erros.push('Razão Social é obrigatória.');
  } else if (campos.rsocial.trim().length < 3) {
    erros.push('Razão Social deve ter pelo menos 3 caracteres.');
  }
  if (!campos.pais) {
    erros.push('País é obrigatório.');
  }

  return erros;
}

function validarPermissaoPorEstado(estado) {
  if (estado === 'novo' && !podeExecutarAcao('incluir')) {
    definirMensagem('erro', 'Você não possui permissão para incluir clientes.', false);
    return false;
  }

  if (estado === 'editar' && !podeExecutarAcao('editar')) {
    definirMensagem('erro', 'Você não possui permissão para editar clientes.', false);
    return false;
  }

  if (estado === 'excluir' && !podeExecutarAcao('excluir')) {
    definirMensagem('erro', 'Você não possui permissão para excluir clientes.', false);
    return false;
  }

  return true;
}

// ── Submissão do formulário principal ────────────────────────────────────────
form.addEventListener('submit', async e => {
  e.preventDefault();
  clearMessages();

  const formData = getForm(nomeForm);
  if (!validarPermissaoPorEstado(formData?.estado)) {
    return;
  }

  if (!formData?.campos || Object.keys(formData.campos).length === 0) {
    definirMensagem('aviso', 'Preencha o formulário antes de enviar.');
    return;
  }

  const erros = validarFormulario(formData.campos);
  if (erros.length > 0) {
    erros.forEach(msg => definirMensagem('erro', msg, false));
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
        if (resultado.data) {
          updateState(resultado.data);
        } else {
          definirMensagem('erro', `Erro ao salvar: ${resultado.error}`, false);
        }
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
  const areaCadastro     = document.getElementById('area-cadastro');
  const divPesquisa      = document.getElementById('div-pesquisa');
  const btnAbrirPesquisa = document.getElementById('btn-abrir-pesquisa');
  const btnVoltar        = document.getElementById('btn-voltar');
  const btnFechar        = document.getElementById('btn-fechar');
  const btnEditar        = document.getElementById('btn-editar');
  const btnNovo          = document.getElementById('btn-novo');
  const btnCancelar      = document.getElementById('btn-cancelar');
  const btnExcluir       = document.getElementById('btn-excluir');
  const btnSalvar        = document.getElementById('btn-salvar');
  const formFiltro       = document.getElementById(nomeFormCons);
  const tabelaCorpo      = document.getElementById('tabela-corpo');

  function aplicarPermissoesNaInterface() {
    const permissoes = obterPermissoesCliente();
    const estadoAtual = getForm(nomeForm)?.estado ?? 'visualizar';
    const botoesControlados = [btnSalvar, btnEditar, btnNovo, btnCancelar, btnExcluir];

    btnAbrirPesquisa.classList.toggle('d-none', !permissoes.consultar);

    botoesControlados.forEach(botao => {
      const visivelNoEstado = botaoDeveFicarVisivel(botao, estadoAtual);
      const visivelNaPermissao = podeExibirBotaoPorPermissao(botao.id, estadoAtual);
      botao.classList.toggle('d-none', !(visivelNoEstado && visivelNaPermissao));
    });

    if (!permissoes.consultar && !divPesquisa.classList.contains('d-none')) {
      alternarTelas();
    }
  }

  // Popula selects ao carregar
  preencherSelectGrupos();
  preencherSelectPaises();

  // ── Alternância entre formulário e tela de pesquisa ──
  const alternarTelas = () => {
    areaCadastro.classList.toggle('d-none');
    divPesquisa.classList.toggle('d-none');
  };

  btnAbrirPesquisa.addEventListener('click', alternarTelas);
  btnVoltar.addEventListener('click', alternarTelas);
  btnFechar.addEventListener('click', alternarTelas);

  // ── Botão Editar ──
  btnEditar.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('editar')) {
      definirMensagem('erro', 'Você não possui permissão para editar clientes.', false);
      return;
    }

    setFormState(nomeForm, 'editar');
    aplicarPermissoesNaInterface();
  });

  // ── Botão Novo ──
  btnNovo.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('incluir')) {
      definirMensagem('erro', 'Você não possui permissão para incluir clientes.', false);
      return;
    }

    setFormState(nomeForm, 'novo');
    preencherSelectGrupos();
    preencherSelectPaises();
    aplicarPermissoesNaInterface();
  });

  // ── Botão Cancelar ──
  btnCancelar.addEventListener('click', () => {
    confirmar({
      titulo: 'Confirmar Cancelamento',
      mensagem: 'Deseja cancelar? Os dados não salvos serão perdidos.',
      onConfirmar: () => {
        setFormState(nomeForm, podeExecutarAcao('incluir') ? 'novo' : 'visualizar');
        aplicarPermissoesNaInterface();
      }
    });
  });

  // ── Botão Excluir ──
  btnExcluir.addEventListener('click', () => {
    confirmar({
      titulo: 'Confirmar Exclusão',
      mensagem: 'Deseja excluir este registro? Esta ação não pode ser desfeita.',
      onConfirmar: async () => {
        clearMessages();
        if (!podeExecutarAcao('excluir')) {
          definirMensagem('erro', 'Você não possui permissão para excluir clientes.', false);
          return;
        }

        AppLoader.show();

        const formData = getForm(nomeForm);
        formData.estado = 'excluir';

        if (!validarPermissaoPorEstado(formData.estado)) {
          AppLoader.hide();
          return;
        }

        const resultado = await fazerRequisicao('/app/cad/cliente/', {
          form: { [nomeForm]: formData }
        });

        if (!resultado.success) {
          if (resultado.data) {
            updateState(resultado.data);
          } else {
            definirMensagem('erro', `Erro ao excluir: ${resultado.error}`, false);
          }
          AppLoader.hide();
          return;
        }

        updateState(resultado.data);
        aplicarPermissoesNaInterface();
        AppLoader.hide();
      }
    });
  });

  // ── Busca / Filtro ──
  formFiltro.addEventListener('submit', async e => {
    e.preventDefault();
    clearMessages();

    if (!podeExecutarAcao('consultar')) {
      definirMensagem('erro', 'Você não possui permissão para consultar clientes.', false);
      return;
    }

    AppLoader.show();

    const resultado = await fazerRequisicao('/app/cad/cliente/cons/', {
      form: { [nomeFormCons]: getForm(nomeFormCons) }
    });

    if (!resultado.success) {
      if (resultado.data) {
        updateState(resultado.data);
      } else {
        definirMensagem('erro', `Erro ao buscar clientes: ${resultado.error}`, false);
      }
      AppLoader.hide();
      return;
    }

    updateState(resultado.data);
    aplicarPermissoesNaInterface();

    if (resultado.data?.registros?.length > 0) {
      renderizarTabela(resultado.data.registros);
    } else {
      tabelaCorpo.innerHTML = '';
      definirMensagem('info', 'Nenhum cliente encontrado.');
    }

    AppLoader.hide();
  });

  // ── Renderização da tabela (textContent previne XSS) ─────────────────────
  function renderizarTabela(registros) {
    tabelaCorpo.innerHTML = '';

    if (!Array.isArray(registros) || registros.length === 0) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 10;
      td.className = 'text-center';
      td.textContent = 'Nenhum registro encontrado';
      tr.appendChild(td);
      tabelaCorpo.appendChild(tr);
      return;
    }

    registros.forEach(r => {
      const tr = document.createElement('tr');

      // Colunas de texto — textContent garante segurança contra XSS
      [r.id, r.codigo, r.nome, r.rsocial, r.grupo, r.pais, r.regiao, r.cidade, r.identificador].forEach(valor => {
        const td = document.createElement('td');
        td.textContent = valor ?? '';
        tr.appendChild(td);
      });

      // Coluna de ação — botão com data-id seguro
      const tdAcao = document.createElement('td');
      tdAcao.className = 'text-center';
      const btn = document.createElement('button');
      btn.className = 'btn btn-sm btn-primary btn-selecionar';
      btn.dataset.id = r.id;
      btn.textContent = 'Selecionar';
      tdAcao.appendChild(btn);
      tr.appendChild(tdAcao);

      tabelaCorpo.appendChild(tr);
    });
  }

  // ── Event delegation — Selecionar registro ──
  tabelaCorpo.addEventListener('click', async e => {
    if (!e.target.classList.contains('btn-selecionar')) return;

    const id = e.target.dataset.id;
    if (!id) {
      definirMensagem('aviso', 'Erro ao selecionar o registro.');
      return;
    }

    await carregarRegistro(id);
  });

  // ── Carregar registro selecionado ──
  async function carregarRegistro(id) {
    clearMessages();

    if (!podeExecutarAcao('consultar')) {
      definirMensagem('erro', 'Você não possui permissão para consultar clientes.', false);
      return;
    }

    AppLoader.show();

    updateFormField(nomeFormCons, 'id_selecionado', id);

    const sisVarPayload = {
      form: { [nomeFormCons]: structuredClone(getForm(nomeFormCons)) }
    };

    updateFormField(nomeFormCons, 'id_selecionado', null);

    const resultado = await fazerRequisicao('/app/cad/cliente/cons/', sisVarPayload);

    if (!resultado.success) {
      if (resultado.data) {
        updateState(resultado.data);
      } else {
        definirMensagem('erro', `Erro ao carregar registro: ${resultado.error}`, false);
      }
      AppLoader.hide();
      return;
    }

    updateState(resultado.data);
    hidratarFormulario(nomeForm);

    // Hidratar selects com os IDs retornados
    const campos = resultado.data?.form?.[nomeForm]?.campos ?? {};
    hidratarSelects(campos);

    setFormState(nomeForm, 'visualizar');
    aplicarPermissoesNaInterface();
    alternarTelas();
    AppLoader.hide();
  }

  aplicarPermissoesNaInterface();
});
