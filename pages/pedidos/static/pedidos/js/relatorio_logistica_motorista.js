import { getCsrfToken, clearMessages, definirMensagem, confirmar, getOptions, getDataset, getScreenPermissions } from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';
import { getMultiSelectValues } from '/static/js/smart_filter.js';
import { initSmartInputs } from '/static/js/input_rules.js';

const root = document.getElementById('rlm-root');
const URL_BUSCAR = root?.dataset?.urlBuscar ?? '';
const URL_MOD_FINAN = root?.dataset?.urlModFinan ?? '';
const URL_GSHEETS = root?.dataset?.urlGsheets ?? '';

const form = document.getElementById('rlm-form');
const inpInicio = document.getElementById('rlm-data-inicio');
const inpFim = document.getElementById('rlm-data-fim');
const selMotoristas = document.getElementById('rlm-motoristas');
const btnSelTodos = document.getElementById('rlm-btn-sel-todos');
const btnDesTodos = document.getElementById('rlm-btn-des-todos');
const loader = document.getElementById('rlm-loader');
const vazio = document.getElementById('rlm-vazio');
const resultado = document.getElementById('rlm-resultado');
const btnImprimir = document.getElementById('rlm-btn-imprimir');
const btnGSheets = document.getElementById('rlm-btn-gsheets');

const modalEl = document.getElementById('modFinan');
const modal = modalEl ? new bootstrap.Modal(modalEl) : null;
const mfFilial = document.getElementById('mf-filial');
const mfEmissao = document.getElementById('mf-emissao');
const mfVenc = document.getElementById('mf-venc');
const mfMotorista = document.getElementById('mf-motorista');
const mfPlanoCodigo = document.getElementById('mf-plano-codigo');
const mfSetor = document.getElementById('mf-setor');
const mfSubsetor = document.getElementById('mf-subsetor');
const mfAtivo = document.getElementById('mf-ativo');
const mfValor = document.getElementById('mf-valor');
const mfObs = document.getElementById('mf-obs');
const mfMotoristaId = document.getElementById('mf-motorista-id');
const mfData = document.getElementById('mf-data');
const mfObsPadrao = document.getElementById('mf-obs-padrao');
const mfBtnSalvar = document.getElementById('mf-btn-salvar');

let labelsPlanoCache = null;

function podeLancarFinan() {
  return Boolean(getScreenPermissions('mod_finan', {})?.lancar);
}

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

function labelsPlano() {
  if (labelsPlanoCache) return labelsPlanoCache;
  labelsPlanoCache = getDataset('plano_diarias_labels') || {};
  return labelsPlanoCache;
}

function nomeFilial() {
  return getDataset('filial_nome') || '';
}

function atualizarCabecalhoImpressao(temDados) {
  const meta = document.getElementById('rlm-print-meta');
  if (!meta) return;
  if (!temDados) {
    meta.textContent = '';
    return;
  }
  const filial = nomeFilial() || '—';
  const di = fmtDataIsoParaBr(inpInicio.value);
  const df = fmtDataIsoParaBr(inpFim.value);
  const opts = Array.from(selMotoristas.options);
  const sel = Array.from(selMotoristas.selectedOptions);
  let motTxt = '—';
  if (opts.length > 0) {
    if (sel.length === 0 || sel.length === opts.length) {
      motTxt = 'Todos os motoristas';
    } else if (sel.length <= 2) {
      motTxt = sel.map((o) => o.textContent.trim()).join(', ');
    } else {
      motTxt = `${sel.length} motoristas`;
    }
  }
  meta.textContent = [filial, `${di}–${df}`, motTxt].join(' · ');
}

function fmtDataIsoParaBr(iso) {
  if (!iso || typeof iso !== 'string') return '';
  const p = iso.split('-');
  if (p.length !== 3) return iso;
  return `${p[2]}/${p[1]}/${p[0]}`;
}

function criarTabelaLinhas(linhas) {
  const table = document.createElement('table');
  table.className = 'rlm-tabela';
  const thead = document.createElement('thead');
  const trh = document.createElement('tr');
  ['Carro', 'Pedido', 'Estado', 'Cidade', 'CP', 'Zona', 'Peso', 'Volumes'].forEach(t => {
    const th = document.createElement('th');
    th.textContent = t;
    trh.appendChild(th);
  });
  thead.appendChild(trh);
  table.appendChild(thead);
  const tb = document.createElement('tbody');
  (linhas || []).forEach(linha => {
    const tr = document.createElement('tr');
    const td = [];
    const c0 = document.createElement('td');
    const carro = linha?.carro;
    c0.textContent = carro != null && carro !== '' ? String(carro) : '—';
    td.push(c0);
    const c1 = document.createElement('td');
    c1.textContent = String(linha?.pedido_ref ?? '');
    td.push(c1);
    const c2 = document.createElement('td');
    c2.textContent = String(linha?.estado_label ?? linha?.estado ?? '');
    td.push(c2);
    const c3 = document.createElement('td');
    c3.textContent = String(linha?.cidade_dest ?? '');
    td.push(c3);
    const c4 = document.createElement('td');
    c4.textContent = String(linha?.codpost_dest ?? '');
    td.push(c4);
    const c5 = document.createElement('td');
    c5.textContent = String(linha?.zona_entrega ?? '');
    td.push(c5);
    const c6 = document.createElement('td');
    c6.textContent = linha?.peso != null && linha.peso !== '' ? String(linha.peso) : '—';
    td.push(c6);
    const c7 = document.createElement('td');
    const vol = linha?.volume;
    c7.textContent = vol != null && vol !== '' ? String(vol) : '—';
    td.push(c7);
    td.forEach(x => tr.appendChild(x));
    tb.appendChild(tr);
  });
  table.appendChild(tb);
  return table;
}

function btnFinanceiro(dadosGrupo) {
  const wrap = document.createElement('span');
  wrap.className = 'd-print-none ms-auto';
  if (!podeLancarFinan() || dadosGrupo.sem_motorista || dadosGrupo.motorista_id == null) {
    return wrap;
  }
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'btn btn-sm btn-warning ms-2';
  btn.innerHTML = '<i class="bi bi-currency-exchange"></i> Lançamento';
  btn.addEventListener('click', () => abrirModFinan(dadosGrupo));
  wrap.appendChild(btn);
  return wrap;
}

function abrirModFinan(ctx) {
  if (!modal) return;
  const lb = labelsPlano();
  mfFilial.textContent = nomeFilial();
  mfEmissao.textContent = fmtDataIsoParaBr(ctx.data_tentativa);
  mfVenc.textContent = fmtDataIsoParaBr(ctx.data_tentativa);
  mfMotorista.textContent = ctx.motorista_label || '';
  mfPlanoCodigo.textContent = lb.codigo_folha || '2.1.2.1';
  mfSetor.textContent = lb.setor || '—';
  mfSubsetor.textContent = lb.subsetor || '—';
  mfAtivo.textContent = lb.ativo || '—';
  mfMotoristaId.value = String(ctx.motorista_id);
  mfData.value = ctx.data_tentativa;
  mfObsPadrao.value = ctx.observacao_padrao || '';
  mfValor.value = '';
  mfObs.value = ctx.observacao_padrao || '';
  modal.show();
  setTimeout(() => mfValor.focus(), 400);
}

async function salvarModFinan() {
  clearMessages();
  const valor = (mfValor.value || '').trim();
  if (!valor) {
    definirMensagem('erro', 'Informe o valor.', false);
    return;
  }
  mfBtnSalvar.disabled = true;
  try {
    const payload = {
      mod_finan: {
        motorista_id: Number.parseInt(mfMotoristaId.value, 10),
        data_tentativa: mfData.value,
        valor,
        observacao: (mfObs.value || '').trim(),
      },
    };
    const resp = await fetch(URL_MOD_FINAN, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify(payload),
    });
    const json = await resp.json();
    if (!json.success) {
      definirMensagem('erro', json.mensagem || 'Não foi possível salvar.', false);
      return;
    }
    definirMensagem('sucesso', json.mensagem || 'Salvo com sucesso.', true);
    modal?.hide();
  } catch {
    definirMensagem('erro', 'Erro de comunicação com o servidor.', false);
  } finally {
    mfBtnSalvar.disabled = false;
  }
}

function renderResultados(motoristas) {
  resultado.replaceChildren();
  motoristas.forEach((m, idx) => {
    const wrap = document.createElement('div');
    wrap.className = 'rlm-grupo-motorista';

    const header = document.createElement('div');
    header.className = 'rlm-grupo-header d-flex flex-wrap align-items-center gap-2';
    const tit = document.createElement('span');
    tit.textContent = m.motorista_label || 'Motorista';
    header.appendChild(tit);
    const b1 = document.createElement('span');
    b1.className = 'rlm-badge';
    b1.textContent = `${m.total_dias_distintos} dia(s)`;
    header.appendChild(b1);
    const b2 = document.createElement('span');
    b2.className = 'rlm-badge';
    b2.textContent = `${m.total_registros} registro(s)`;
    header.appendChild(b2);
    const btnToggle = document.createElement('button');
    btnToggle.type = 'button';
    btnToggle.className = 'btn btn-sm btn-light ms-auto d-print-none';
    btnToggle.setAttribute('data-bs-toggle', 'collapse');
    btnToggle.setAttribute('data-bs-target', `#rlm-c-m-${idx}`);
    btnToggle.setAttribute('aria-expanded', 'false');
    btnToggle.innerHTML = '<i class="bi bi-chevron-down"></i>';
    header.appendChild(btnToggle);
    wrap.appendChild(header);

    const collapseM = document.createElement('div');
    collapseM.className = 'collapse';
    collapseM.id = `rlm-c-m-${idx}`;

    (m.datas || []).forEach((d, j) => {
      const dh = document.createElement('div');
      dh.className = 'rlm-grupo-data-header d-flex flex-wrap align-items-center gap-2';
      const s1 = document.createElement('span');
      s1.textContent = d.data_fmt || fmtDataIsoParaBr(d.data_tentativa);
      dh.appendChild(s1);
      const bz = document.createElement('span');
      bz.className = 'rlm-badge';
      const zonasTxt = (d.zonas_texto || []).join(', ') || '—';
      const pesoResumo = d.total_peso != null && d.total_peso !== '' ? d.total_peso : '0';
      const volResumo = d.total_volume != null ? d.total_volume : 0;
      bz.textContent = `${d.total_registros} reg. | Peso: ${pesoResumo} | Vol.: ${volResumo} | Zonas: ${zonasTxt}`;
      dh.appendChild(bz);
      dh.appendChild(btnFinanceiro({
        motorista_id: m.motorista_id,
        sem_motorista: m.sem_motorista,
        motorista_label: m.motorista_label,
        data_tentativa: d.data_tentativa,
        observacao_padrao: d.observacao_padrao || '',
      }));

      const btnTd = document.createElement('button');
      btnTd.type = 'button';
      btnTd.className = 'btn btn-sm btn-outline-secondary d-print-none ms-1';
      btnTd.setAttribute('data-bs-toggle', 'collapse');
      btnTd.setAttribute('data-bs-target', `#rlm-c-d-${idx}-${j}`);
      btnTd.innerHTML = '<i class="bi bi-list-ul"></i>';
      dh.appendChild(btnTd);

      collapseM.appendChild(dh);

      const collapseD = document.createElement('div');
      collapseD.className = 'collapse';
      collapseD.id = `rlm-c-d-${idx}-${j}`;
      const scroll = document.createElement('div');
      scroll.style.overflowX = 'auto';
      scroll.appendChild(criarTabelaLinhas(d.linhas));
      collapseD.appendChild(scroll);
      collapseM.appendChild(collapseD);
    });

    wrap.appendChild(collapseM);
    resultado.appendChild(wrap);
  });
}

function renderizar(payload) {
  const motoristas = payload.motoristas || [];
  if (!motoristas.length) {
    vazio.classList.remove('d-none');
    atualizarCabecalhoImpressao(false);
    btnImprimir.disabled = true;
    if (btnGSheets) btnGSheets.disabled = true;
    return;
  }
  vazio.classList.add('d-none');
  renderResultados(motoristas);
  atualizarCabecalhoImpressao(true);
  btnImprimir.disabled = false;
  if (btnGSheets) btnGSheets.disabled = false;
}

async function enviarAoGSheets() {
  const di = inpInicio.value;
  const df = inpFim.value;
  if (!di || !df) {
    definirMensagem('erro', 'Informe o período antes de enviar.', false);
    return;
  }
  confirmar({
    titulo: 'Enviar ao Google Sheets',
    mensagem: 'Deseja enviar ao Google Sheets as tentativas do relatório (exceto Concluído, interno e estados de danos/recusa)?',
    onConfirmar: async () => {
      clearMessages();
      if (btnGSheets) btnGSheets.disabled = true;
      AppLoader.show();
      try {
        const payload = {
          filtros: {
            data_inicio: di,
            data_fim: df,
            motoristas: getMultiSelectValues(selMotoristas),
          },
        };
        const resp = await fetch(URL_GSHEETS, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
          body: JSON.stringify(payload),
        });
        const json = await resp.json();
        if (!json.success) {
          definirMensagem('erro', json.mensagem || 'Erro ao enviar.', false);
          return;
        }
        let msgOk = json.mensagem || 'Enviado com sucesso.';
        const ignorados = json.ignorados || [];
        if (ignorados.length) {
          const linhas = ignorados.map((r) => {
            const ref = String(r.referencia ?? '');
            const dt = String(r.data_tentativa ?? '');
            const est = String(r.estado_label || r.estado || '');
            return `${ref} (${dt}${est ? ` — ${est}` : ''})`;
          });
          msgOk += ` Ignorados (interno): ${linhas.join('; ')}.`;
        }
        definirMensagem('sucesso', msgOk, false);
      } catch {
        definirMensagem('erro', 'Erro de comunicação com o servidor.', false);
      } finally {
        AppLoader.hide();
        if (btnGSheets && vazio.classList.contains('d-none')) {
          btnGSheets.disabled = false;
        }
      }
    },
  });
}

async function buscar() {
  clearMessages();
  const di = inpInicio.value;
  const df = inpFim.value;
  if (!di || !df) {
    definirMensagem('erro', 'Informe o período.', false);
    return;
  }
  btnImprimir.disabled = true;
  if (btnGSheets) btnGSheets.disabled = true;
  atualizarCabecalhoImpressao(false);
  loader.classList.remove('d-none');
  resultado.replaceChildren();
  vazio.classList.add('d-none');
  try {
    const payload = {
      filtros: {
        data_inicio: di,
        data_fim: df,
        motoristas: getMultiSelectValues(selMotoristas),
      },
    };
    const resp = await fetch(URL_BUSCAR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify(payload),
    });
    const json = await resp.json();
    if (!json.success) {
      definirMensagem('erro', json.mensagem || 'Erro ao buscar.', false);
      btnImprimir.disabled = true;
      return;
    }
    renderizar(json);
  } catch {
    definirMensagem('erro', 'Erro de comunicação com o servidor.', false);
  } finally {
    loader.classList.add('d-none');
  }
}

function sincronizarDataFimComInicio() {
  inpFim.value = inpInicio.value || '';
}
inpInicio?.addEventListener('change', sincronizarDataFimComInicio);
inpInicio?.addEventListener('input', sincronizarDataFimComInicio);

form?.addEventListener('submit', e => { e.preventDefault(); buscar(); });
btnSelTodos?.addEventListener('click', () => {
  Array.from(selMotoristas.options).forEach(o => { o.selected = true; });
});
btnDesTodos?.addEventListener('click', () => {
  Array.from(selMotoristas.options).forEach(o => { o.selected = false; });
});
btnImprimir?.addEventListener('click', () => window.print());
btnGSheets?.addEventListener('click', enviarAoGSheets);
mfBtnSalvar?.addEventListener('click', salvarModFinan);

preencherMotoristas();
initSmartInputs();
