import { getCsrfToken, clearMessages, definirMensagem, getOptions } from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';
import {
  parseSmartNumber,
  parseSmartText,
  getMultiSelectValues,
  validateSmartNumber,
  validateSmartText,
} from '/static/js/smart_filter.js';

const root       = document.getElementById('rg-root');
const URL_BUSCAR = root?.dataset?.urlBuscar ?? '';

const form        = document.getElementById('rg-form');
const inpDataIni  = document.getElementById('rg-data-ini');
const inpDataFim  = document.getElementById('rg-data-fim');
const inpIdVonzu  = document.getElementById('rg-id-vonzu');
const inpRef      = document.getElementById('rg-referencia');
const selEstados  = document.getElementById('rg-estados');
const resultado   = document.getElementById('rg-resultado');
const loader      = document.getElementById('rg-loader');
const vazio       = document.getElementById('rg-vazio');
const tituloData  = document.getElementById('rg-titulo-data');
const totalBar    = document.getElementById('rg-total-bar');
const btnImprimir = document.getElementById('rg-btn-imprimir');
const btnSelTodos = document.getElementById('rg-btn-sel-todos');
const btnDesTodos = document.getElementById('rg-btn-des-todos');
const erroVonzu   = document.getElementById('rg-id-vonzu-erro');
const erroRef     = document.getElementById('rg-referencia-erro');

// ─── Popula select de estados a partir da sisVar ──────────────────────────────
function preencherEstados() {
  const estados = getOptions('estados') || [];
  selEstados.replaceChildren();
  estados.forEach(e => {
    const opt = document.createElement('option');
    opt.value = e.value;
    opt.textContent = e.label;
    selEstados.appendChild(opt);
  });
}

btnSelTodos.addEventListener('click', () => {
  Array.from(selEstados.options).forEach(o => { o.selected = true; });
});
btnDesTodos.addEventListener('click', () => {
  Array.from(selEstados.options).forEach(o => { o.selected = false; });
});

// ─── Validação de smart filters ───────────────────────────────────────────────
function validarFiltros() {
  let valido = true;

  if (!validateSmartNumber(inpIdVonzu.value)) {
    erroVonzu.classList.remove('d-none');
    inpIdVonzu.classList.add('is-invalid');
    valido = false;
  } else {
    erroVonzu.classList.add('d-none');
    inpIdVonzu.classList.remove('is-invalid');
  }

  if (!validateSmartText(inpRef.value)) {
    erroRef.classList.remove('d-none');
    inpRef.classList.add('is-invalid');
    valido = false;
  } else {
    erroRef.classList.add('d-none');
    inpRef.classList.remove('is-invalid');
  }

  return valido;
}

// ─── Escape seguro ────────────────────────────────────────────────────────────
function _esc(v) {
  if (v == null) return '';
  return String(v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─── Renderizar grupos ────────────────────────────────────────────────────────
function renderizarGrupos(grupos, dataFmt, totalPedidos) {
  resultado.replaceChildren();
  vazio.classList.add('d-none');
  totalBar.classList.add('d-none');

  if (!grupos.length) {
    vazio.classList.remove('d-none');
    btnImprimir.disabled = true;
    return;
  }

  tituloData.textContent = `Período: ${dataFmt}`;

  totalBar.textContent = `Total: ${totalPedidos} pedido(s) em ${grupos.length} carro(s)`;
  totalBar.classList.remove('d-none');

  grupos.forEach(grupo => {
    // Cabeçalho do grupo
    const header = document.createElement('div');
    header.className = 'rg-grupo-header';

    const spanCarro = document.createElement('span');
    spanCarro.textContent = grupo.carro !== '—' ? `Carro ${grupo.carro}` : 'Sem carro';

    const spanTotal = document.createElement('span');
    spanTotal.className = 'rg-badge ms-auto';
    spanTotal.textContent = `${grupo.total} pedido(s)`;

    header.appendChild(spanCarro);
    header.appendChild(spanTotal);

    // Tabela
    const table = document.createElement('table');
    table.className = 'rg-tabela';

    const thead = document.createElement('thead');
    const trHead = document.createElement('tr');
    ['Data', 'Referência', 'ID Vonzu', 'T', 'Destinatário', 'Telefone(s)', 'Endereço', 'Cidade', 'C. Postal', 'Vol', 'Peso', 'Per.', 'Estado', 'Obs. Rota'].forEach(h => {
      const th = document.createElement('th');
      th.textContent = h;
      trHead.appendChild(th);
    });
    thead.appendChild(trHead);

    const tbody = document.createElement('tbody');
    grupo.linhas.forEach(linha => {
      const tr = document.createElement('tr');
      if (!linha.segue_para_entrega) tr.classList.add('rg-nao-segue');

      const volPartes = (linha.volumes || '').split('/');
      const volNegrito = volPartes.length === 2 && parseInt(volPartes[0], 10) < parseInt(volPartes[1], 10);

      const campos = [
        { val: linha.data_tentativa },
        { val: linha.pedido },
        { val: linha.id_vonzu },
        { val: linha.tipo, cls: linha.tipo === 'R' ? 'rg-tipo-r' : 'rg-tipo-e' },
        { val: linha.nome_dest },
        { val: linha.fones },
        { val: linha.endereco_dest },
        { val: linha.cidade_dest },
        { val: linha.codpost_dest },
        { val: linha.volumes, bold: volNegrito },
        { val: linha.peso },
        { val: linha.periodo, cls: linha.periodo ? `rg-periodo-${linha.periodo}` : '' },
        { val: linha.estado },
        { val: linha.obs_rota, cls: 'rg-obs' },
      ];

      campos.forEach(({ val, cls, bold }) => {
        const td = document.createElement('td');
        td.textContent = val ?? '';
        if (cls) td.className = cls;
        if (bold) td.style.fontWeight = 'bold';
        tr.appendChild(td);
      });

      tbody.appendChild(tr);
    });

    table.appendChild(thead);
    table.appendChild(tbody);

    const tableScroll = document.createElement('div');
    tableScroll.className = 'rg-tabela-scroll';
    tableScroll.appendChild(table);

    const wrapper = document.createElement('div');
    wrapper.className = 'rg-grupo';
    wrapper.appendChild(header);
    wrapper.appendChild(tableScroll);
    resultado.appendChild(wrapper);
  });

  btnImprimir.disabled = false;
}

// ─── Buscar ───────────────────────────────────────────────────────────────────
async function buscar() {
  clearMessages();

  if (!validarFiltros()) return;

  const dataIni = inpDataIni.value;
  const dataFim = inpDataFim.value;

  if (!dataIni || !dataFim) {
    definirMensagem('erro', 'Informe a data inicial e a data final.', false);
    return;
  }

  loader.classList.remove('d-none');
  resultado.replaceChildren();
  vazio.classList.add('d-none');
  totalBar.classList.add('d-none');
  btnImprimir.disabled = true;
  AppLoader.show();

  try {
    const payload = {
      filtros: {
        data_inicial: dataIni,
        data_final:   dataFim,
        id_vonzu:     inpIdVonzu.value.trim(),
        referencia:   inpRef.value.trim(),
        estados:      getMultiSelectValues(selEstados),
      },
    };

    const resp = await fetch(URL_BUSCAR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify(payload),
    });
    const json = await resp.json();

    if (!json.success) {
      definirMensagem('erro', json.mensagem || 'Erro ao buscar dados.', false);
      return;
    }

    renderizarGrupos(json.grupos || [], json.data_fmt || '', json.total_pedidos || 0);
  } catch {
    definirMensagem('erro', 'Erro de comunicação com o servidor.', false);
  } finally {
    loader.classList.add('d-none');
    AppLoader.hide();
  }
}

// ─── Feedback em tempo real nos campos smart_filter ───────────────────────────
inpIdVonzu.addEventListener('input', () => {
  if (validateSmartNumber(inpIdVonzu.value)) {
    erroVonzu.classList.add('d-none');
    inpIdVonzu.classList.remove('is-invalid');
  }
});

inpRef.addEventListener('input', () => {
  if (validateSmartText(inpRef.value)) {
    erroRef.classList.add('d-none');
    inpRef.classList.remove('is-invalid');
  }
});

// ─── Inicialização ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  preencherEstados();

  // Inicializar tooltips Bootstrap
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
    new bootstrap.Tooltip(el);
  });
});

// ─── Eventos ─────────────────────────────────────────────────────────────────
form.addEventListener('submit', e => { e.preventDefault(); buscar(); });
btnImprimir.addEventListener('click', () => window.print());
