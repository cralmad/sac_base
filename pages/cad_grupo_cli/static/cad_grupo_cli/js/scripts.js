// 1. IMPORTS — caminhos absolutos /static/
import {
  updateFormField, getForm, updateState,
  clearMessages, definirMensagem,
  hidratarFormulario, setFormState, confirmar, getScreenPermissions, getDataBackEnd
} from '/static/js/sisVar.js';
import { fazerRequisicao }      from '/static/js/base.js';
import { initSmartInputs }      from '/static/js/input_rules.js';
import { criarAtualizadorForm } from '/static/js/refresh_varSis.js';
import { AppLoader }            from '/static/js/loader.js';

// 2. CONSTANTES
const nomeForm     = 'cadGrupoCli';
const nomeFormCons = 'consGrupoCli';
const form  = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

getDataBackEnd();

function obterPermissoesGrupoCli() {
  return getScreenPermissions('cad_grupo_cli', {
    acessar: false,
    consultar: false,
    incluir: false,
    editar: false,
    excluir: false,
  });
}

function podeExecutarAcao(acao) {
  return Boolean(obterPermissoesGrupoCli()?.[acao]);
}

function botaoDeveFicarVisivel(botao, estado) {
  const estadosPermitidos = (botao.dataset.showOn || '')
    .split(',')
    .map(item => item.trim())
    .filter(Boolean);

  return estadosPermitidos.includes(estado);
}

function podeExibirBotaoPorPermissao(botaoId, estado) {
  if (botaoId === 'btn-novo') {
    return podeExecutarAcao('incluir');
  }

  if (botaoId === 'btn-editar') {
    return podeExecutarAcao('editar');
  }

  if (botaoId === 'btn-excluir') {
    return podeExecutarAcao('excluir');
  }

  if (botaoId === 'btn-salvar' || botaoId === 'btn-cancelar') {
    if (estado === 'novo') {
      return podeExecutarAcao('incluir');
    }

    if (estado === 'editar') {
      return podeExecutarAcao('editar');
    }
  }

  return true;
}

// 3. VÍNCULO sisVar ↔ inputs do formulário principal
const updater = criarAtualizadorForm({ formId: nomeForm, setter: updateFormField, form });
form.addEventListener('input', updater);
initSmartInputs((input, value) => { updateFormField(nomeForm, input.name, value); });

// 4. VÍNCULO sisVar ↔ inputs do formulário de consulta
const updater2 = criarAtualizadorForm({ formId: nomeFormCons, setter: updateFormField, form: form2 });
form2.addEventListener('input', updater2);

// Utilitário: escapa strings para inserção segura no DOM (evita XSS)
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Utilitário: marca/desmarca campo com erro visual Bootstrap
function marcarCampoErro(formEl, nomeCampo, ativo) {
  const input = formEl.querySelector(`[name="${nomeCampo}"]`);
  if (!input) return;
  if (ativo) {
    input.classList.add('is-invalid');
    input.addEventListener('input', () => input.classList.remove('is-invalid'), { once: true });
  } else {
    input.classList.remove('is-invalid');
  }
}

function validarPermissaoPorEstado(estado) {
  if (estado === 'novo' && !podeExecutarAcao('incluir')) {
    definirMensagem('erro', 'Você não possui permissão para incluir grupos de cliente.', false);
    return false;
  }

  if (estado === 'editar' && !podeExecutarAcao('editar')) {
    definirMensagem('erro', 'Você não possui permissão para editar grupos de cliente.', false);
    return false;
  }

  return true;
}

// 5. SUBMIT DO FORMULÁRIO PRINCIPAL (Salvar)
form.addEventListener('submit', async e => {
  e.preventDefault();
  clearMessages();
  marcarCampoErro(form, 'descricao', false);

  const formData = getForm(nomeForm);
  if (!validarPermissaoPorEstado(formData?.estado)) {
    return;
  }

  confirmar({
    titulo: 'Confirmar Salvamento',
    mensagem: 'Deseja salvar o grupo de cliente?',
    onConfirmar: async () => {
      AppLoader.show();

      const resultado = await fazerRequisicao('/app/cad/grupocli/', {
        form: { [nomeForm]: formData }
      });

      AppLoader.hide();

      if (!resultado.success) {
        if (resultado.data) updateState(resultado.data);
        else definirMensagem('erro', `Erro: ${resultado.error}`, false);
        if (resultado.status === 422) marcarCampoErro(form, 'descricao', true);
        return;
      }

      updateState(resultado.data);
      hidratarFormulario(nomeForm);
    }
  });
});

// 6. LÓGICA DE UI — dentro do DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  AppLoader.show();

  const divPrincipal     = document.getElementById(nomeForm);
  const divPesquisa      = document.getElementById('div-pesquisa');
  const btnAbrirPesquisa = document.getElementById('btn-abrir-pesquisa');
  const btnVoltar        = document.getElementById('btn-voltar');
  const btnFechar        = document.getElementById('btn-fechar');
  const btnEditar        = document.getElementById('btn-editar');
  const btnNovo          = document.getElementById('btn-novo');
  const btnExcluir       = document.getElementById('btn-excluir');
  const btnCancelar      = document.getElementById('btn-cancelar');
  const btnSalvar        = document.getElementById('btn-salvar');
  const tabelaCorpo      = document.getElementById('tabela-corpo');

  function aplicarPermissoesNaInterface() {
    const permissoes = obterPermissoesGrupoCli();
    const estadoAtual = getForm(nomeForm)?.estado ?? 'visualizar';
    const botoesControlados = [btnSalvar, btnEditar, btnNovo, btnExcluir, btnCancelar];

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

  // Alternância cadastro ↔ pesquisa
  const alternarTelas = () => {
    divPrincipal.classList.toggle('d-none');
    divPesquisa.classList.toggle('d-none');
  };

  btnAbrirPesquisa.addEventListener('click', alternarTelas);
  btnVoltar.addEventListener('click', alternarTelas);
  btnFechar.addEventListener('click', alternarTelas);

  // Botões de estado
  btnEditar.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('editar')) {
      definirMensagem('erro', 'Você não possui permissão para editar grupos de cliente.', false);
      return;
    }

    setFormState(nomeForm, 'editar');
    aplicarPermissoesNaInterface();
  });
  btnNovo.addEventListener('click', () => {
    clearMessages();
    if (!podeExecutarAcao('incluir')) {
      definirMensagem('erro', 'Você não possui permissão para incluir grupos de cliente.', false);
      return;
    }

    setFormState(nomeForm, 'novo');
    aplicarPermissoesNaInterface();
  });
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

  // Botão Excluir
  btnExcluir.addEventListener('click', () => {
    const formData = getForm(nomeForm);
    const descricao = formData?.campos?.descricao || '';

    confirmar({
      titulo: 'Confirmar Exclusão',
      mensagem: `Deseja excluir o grupo "${escHtml(descricao)}"? Esta ação não pode ser desfeita.`,
      onConfirmar: async () => {
        clearMessages();
        if (!podeExecutarAcao('excluir')) {
          definirMensagem('erro', 'Você não possui permissão para excluir grupos de cliente.', false);
          return;
        }

        AppLoader.show();

        const resultado = await fazerRequisicao('/app/cad/grupocli/del', {
          form: { [nomeForm]: formData }
        });

        AppLoader.hide();

        if (!resultado.success) {
          if (resultado.data) updateState(resultado.data);
          else definirMensagem('erro', `Erro: ${resultado.error}`, false);
          return;
        }

        updateState(resultado.data);
        setFormState(nomeForm, podeExecutarAcao('incluir') ? 'novo' : 'visualizar');
        aplicarPermissoesNaInterface();
      }
    });
  });

  // Submit da consulta (Filtrar)
  form2.addEventListener('submit', async e => {
    e.preventDefault();
    clearMessages();

    if (!podeExecutarAcao('consultar')) {
      definirMensagem('erro', 'Você não possui permissão para consultar grupos de cliente.', false);
      return;
    }

    AppLoader.show();

    const resultado = await fazerRequisicao('/app/cad/grupocli/cons', {
      form: { [nomeFormCons]: getForm(nomeFormCons) }
    });

    AppLoader.hide();

    if (!resultado.success) {
      if (resultado.data) updateState(resultado.data);
      else definirMensagem('erro', `Erro: ${resultado.error}`, false);
      return;
    }

    updateState(resultado.data);
  aplicarPermissoesNaInterface();

    if (resultado.data?.registros && resultado.data.registros.length > 0) {
      renderizarTabela(resultado.data.registros);
    } else {
      tabelaCorpo.innerHTML = '';
      definirMensagem('info', 'Nenhum grupo de cliente encontrado.');
    }
  });

  // Event delegation — selecionar da tabela
tabelaCorpo.addEventListener('click', async e => {
    if (!e.target.classList.contains('btn-selecionar')) return;

    const id = e.target.dataset.id;
    if (!id) { definirMensagem('aviso', 'Erro ao selecionar o registro.', true); return; }

    if (!podeExecutarAcao('consultar')) {
      definirMensagem('erro', 'Você não possui permissão para consultar grupos de cliente.', false);
      return;
    }

    clearMessages();
    AppLoader.show();

    updateFormField(nomeFormCons, 'id_selecionado', id);
    const payload = { form: { [nomeFormCons]: structuredClone(getForm(nomeFormCons)) } };
    updateFormField(nomeFormCons, 'id_selecionado', null);

    const resultado = await fazerRequisicao('/app/cad/grupocli/cons', payload);

    AppLoader.hide();

    if (!resultado.success) {
      if (resultado.data) updateState(resultado.data);
      else definirMensagem('erro', `Erro: ${resultado.error}`, false);
      return;
    }

    updateState(resultado.data);
    hidratarFormulario(nomeForm);
    setFormState(nomeForm, 'visualizar');
    aplicarPermissoesNaInterface();
    alternarTelas();
  });

  // Renderização da tabela
  function renderizarTabela(registros) {
    tabelaCorpo.innerHTML = '';

    if (!Array.isArray(registros) || registros.length === 0) {
      tabelaCorpo.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Nenhum registro encontrado.</td></tr>';
      return;
    }

    registros.forEach(reg => {
      const tr = document.createElement('tr');

      const tdId = document.createElement('td');
      tdId.textContent = reg.id;

      const tdDesc = document.createElement('td');
      tdDesc.textContent = reg.descricao;

      const tdAcao = document.createElement('td');
      tdAcao.className = 'text-center';

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-sm btn-primary btn-selecionar';
      btn.dataset.id = reg.id;
      btn.textContent = 'Selecionar';

      tdAcao.appendChild(btn);
      tr.appendChild(tdId);
      tr.appendChild(tdDesc);
      tr.appendChild(tdAcao);
      tabelaCorpo.appendChild(tr);
    });
  }

  aplicarPermissoesNaInterface();
  AppLoader.hide();
});