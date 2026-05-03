import { getCsrfToken, clearMessages, definirMensagem, getOptions } from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';
import { validateSmartNumber, getMultiSelectValues } from '/static/js/smart_filter.js';

const root       = document.getElementById('rr-root');
const URL_BUSCAR = root?.dataset?.urlBuscar ?? '';
const URL_LINK   = root?.dataset?.urlLink   ?? '';

const form       = document.getElementById('rr-form');
const inpData    = document.getElementById('rr-data');
const inpCarro   = document.getElementById('rr-carro');
const selMotoristas = document.getElementById('rr-motoristas');
const btnSelTodos   = document.getElementById('rr-btn-sel-todos');
const btnDesTodos   = document.getElementById('rr-btn-des-todos');
const erroCarroEl = document.getElementById('rr-carro-erro');
const selAgrupamento = document.getElementById('rr-agrupamento');
const tituloAgrup = document.getElementById('rr-titulo-agrup');
const resultado  = document.getElementById('rr-resultado');
const loader     = document.getElementById('rr-loader');
const vazio      = document.getElementById('rr-vazio');
const tituloData = document.getElementById('rr-titulo-data');
const btnImprimir = document.getElementById('rr-btn-imprimir');

// ─── Popula select de motoristas a partir da sisVar ───────────────────────────
function preencherMotoristas() {
  const motoristas = getOptions('motoristas') || [];
  selMotoristas.replaceChildren();
  motoristas.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.value;
    opt.textContent = m.label;
    selMotoristas.appendChild(opt);
  });
}

btnSelTodos?.addEventListener('click', () => {
  Array.from(selMotoristas.options).forEach(o => { o.selected = true; });
});
btnDesTodos?.addEventListener('click', () => {
  Array.from(selMotoristas.options).forEach(o => { o.selected = false; });
});

selAgrupamento?.addEventListener('change', () => {
  tituloAgrup.textContent = selAgrupamento.value === 'motorista' ? 'Motorista' : 'Carro';
});

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
function renderizarGrupos(grupos, dataFmt, agrupamento) {
  resultado.replaceChildren();
  vazio.classList.add('d-none');

  if (!grupos.length) {
    vazio.classList.remove('d-none');
    return;
  }

  tituloData.textContent = `Data: ${dataFmt}`;

  grupos.forEach(grupo => {
    // Cabeçalho do grupo
    const header = document.createElement('div');
    header.className = 'rr-grupo-header';

    const spanLabel = document.createElement('span');
    if (agrupamento === 'motorista') {
      spanLabel.textContent = grupo.motorista_nome
        ? `Motorista: ${grupo.motorista_nome}`
        : 'Sem motorista';
    } else {
      spanLabel.textContent = grupo.carro !== '\u2014' ? `Carro ${grupo.carro}` : 'Sem carro';
    }

    const spanData = document.createElement('span');
    spanData.textContent = grupo.data_tentativa;
    spanData.style.fontWeight = 'normal';
    spanData.style.opacity = '0.85';

    const spanTotal = document.createElement('span');
    spanTotal.className = 'rr-badge ms-auto';
    spanTotal.textContent = `${grupo.total} pedido(s)`;

    header.appendChild(spanLabel);
    header.appendChild(spanData);
    header.appendChild(spanTotal);

    const btnCopiarRefs = document.createElement('button');
    btnCopiarRefs.type = 'button';
    btnCopiarRefs.className = 'btn btn-sm btn-light';
    btnCopiarRefs.title = 'Copiar todas as referências do grupo (ref1, ref2, …)';
    btnCopiarRefs.innerHTML = '<i class="bi bi-clipboard"></i>';
    btnCopiarRefs.addEventListener('click', () => copiarReferenciasGrupo(grupo, btnCopiarRefs));
    header.appendChild(btnCopiarRefs);

    if (agrupamento !== 'motorista' && grupo.carro !== '\u2014') {
      const btnLink = document.createElement('button');
      btnLink.type = 'button';
      btnLink.className = 'btn btn-sm btn-light';
      btnLink.title = 'Copiar link público do carro';
      btnLink.innerHTML = '<i class="bi bi-link-45deg"></i>';
      btnLink.addEventListener('click', () => gerarECopiarLink(grupo.carro, btnLink));
      header.appendChild(btnLink);
    }

    // Tabela
    const table = document.createElement('table');
    table.className = 'rr-tabela';

    const thead = document.createElement('thead');
    const trHead = document.createElement('tr');
    ['Referência', 'T', 'Destinatário', 'Telefone(s)', 'Endereço', 'Cidade', 'C. Postal', 'Vol', 'Peso', 'Per.', 'Obs. Rota'].forEach(h => {
      const th = document.createElement('th');
      th.textContent = h;
      trHead.appendChild(th);
    });
    thead.appendChild(trHead);

    const tbody = document.createElement('tbody');
    grupo.linhas.forEach(linha => {
      const tr = document.createElement('tr');
      if (linha.nao_segue_para_entrega ?? !linha.segue_para_entrega) tr.classList.add('rr-nao-segue');

      const campos = [
        { val: linha.pedido },
        { val: linha.tipo,   cls: linha.tipo === 'R' ? 'rr-tipo-r' : 'rr-tipo-e' },
        { val: linha.nome_dest },
        { val: linha.fones },
        { val: linha.endereco_dest },
        { val: linha.cidade_dest },
        { val: linha.codpost_dest },
        { val: linha.volumes, bold: (() => { const p = (linha.volumes || '').split('/'); return p.length === 2 && parseInt(p[0], 10) < parseInt(p[1], 10); })() },
        { val: linha.peso },
        { val: linha.periodo, cls: linha.periodo ? `rr-periodo-${linha.periodo}` : '' },
        { val: linha.obs_rota, cls: 'rr-obs' },
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
    tableScroll.className = 'rr-tabela-scroll';
    tableScroll.appendChild(table);

    const wrapper = document.createElement('div');
    wrapper.className = 'rr-grupo';
    wrapper.appendChild(header);
    wrapper.appendChild(tableScroll);
    resultado.appendChild(wrapper);
  });

  btnImprimir.disabled = false;
}

// ─── Copiar referências do grupo (ref1, ref2, …) ────────────────────────────
async function copiarReferenciasGrupo(grupo, btn) {
  clearMessages();
  const refs = (grupo.linhas || [])
    .map(l => {
      const p = l.pedido;
      if (p == null) return '';
      const s = String(p).trim();
      return s;
    })
    .filter(Boolean);
  if (!refs.length) {
    definirMensagem('aviso', 'Nenhuma referência neste grupo.', false);
    return;
  }
  const texto = refs.join(', ');
  const textoOriginal = btn.innerHTML;
  btn.disabled = true;
  try {
    await navigator.clipboard.writeText(texto);
    btn.innerHTML = '<i class="bi bi-check-lg"></i>';
    btn.classList.replace('btn-light', 'btn-success');
    setTimeout(() => {
      btn.innerHTML = textoOriginal;
      btn.classList.replace('btn-success', 'btn-light');
      btn.disabled = false;
    }, 2000);
  } catch {
    definirMensagem('erro', 'Não foi possível copiar. Verifique as permissões do navegador.', false);
    btn.innerHTML = textoOriginal;
    btn.disabled = false;
  }
}

// ─── Gerar e copiar link público do carro ───────────────────────────────────
async function gerarECopiarLink(carro, btn) {
  clearMessages();

  const dataRel = inpData.value;
  const hoje    = new Date().toISOString().slice(0, 10);

  if (dataRel && dataRel < hoje) {
    definirMensagem('aviso', 'Links públicos não são válidos para datas passadas. A data do relatório deve ser a partir de hoje.', false);
    return;
  }

  const textoOriginal = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>';

  try {
    const resp = await fetch(`${URL_LINK}?carro=${encodeURIComponent(carro)}&data=${encodeURIComponent(dataRel)}`, {
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    const json = await resp.json();

    if (!json.success) {
      definirMensagem('erro', json.mensagem || 'Erro ao gerar link.', false);
      btn.innerHTML = textoOriginal;
      btn.disabled = false;
      return;
    }

    await navigator.clipboard.writeText(json.url);
    btn.innerHTML = '<i class="bi bi-check-lg"></i>';
    btn.classList.replace('btn-light', 'btn-success');
    setTimeout(() => {
      btn.innerHTML = textoOriginal;
      btn.classList.replace('btn-success', 'btn-light');
      btn.disabled = false;
    }, 2500);
  } catch {
    definirMensagem('erro', 'Erro ao gerar ou copiar o link.', false);
    btn.innerHTML = textoOriginal;
    btn.disabled = false;
  }
}

// ─── Buscar ───────────────────────────────────────────────────────────────────
async function buscar() {
  clearMessages();
  const data = inpData.value;
  if (!data) {
    definirMensagem('erro', 'Informe a data para buscar.', false);
    return;
  }

  if (!validateSmartNumber(inpCarro.value)) {
    erroCarroEl.classList.remove('d-none');
    inpCarro.classList.add('is-invalid');
    return;
  }
  erroCarroEl.classList.add('d-none');
  inpCarro.classList.remove('is-invalid');

  loader.classList.remove('d-none');
  resultado.replaceChildren();
  vazio.classList.add('d-none');
  btnImprimir.disabled = true;
  AppLoader.show();

  try {
    const payload = {
      filtros: {
        data_tentativa: data,
        carro: inpCarro.value.trim(),
        motoristas: getMultiSelectValues(selMotoristas),
        agrupamento: selAgrupamento.value || 'carro',
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
    renderizarGrupos(json.grupos || [], json.data_fmt || '', json.agrupamento || 'carro');
  } catch {
    definirMensagem('erro', 'Erro de comunicação com o servidor.', false);
  } finally {
    loader.classList.add('d-none');
    AppLoader.hide();
  }
}

// ─── Eventos ──────────────────────────────────────────────────────────────────
form.addEventListener('submit', e => { e.preventDefault(); buscar(); });
btnImprimir.addEventListener('click', () => window.print());
preencherMotoristas();
