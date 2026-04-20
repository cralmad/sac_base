import { getCsrfToken, clearMessages, definirMensagem } from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';

const root       = document.getElementById('rr-root');
const URL_BUSCAR = root?.dataset?.urlBuscar ?? '';

const form       = document.getElementById('rr-form');
const inpData    = document.getElementById('rr-data');
const inpCarro   = document.getElementById('rr-carro');
const resultado  = document.getElementById('rr-resultado');
const loader     = document.getElementById('rr-loader');
const vazio      = document.getElementById('rr-vazio');
const tituloData = document.getElementById('rr-titulo-data');
const btnImprimir = document.getElementById('rr-btn-imprimir');

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
function renderizarGrupos(grupos, dataFmt) {
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

    const spanCarro = document.createElement('span');
    spanCarro.textContent = grupo.carro !== '—' ? `Carro ${grupo.carro}` : 'Sem carro';

    const spanData = document.createElement('span');
    spanData.textContent = grupo.data_tentativa;
    spanData.style.fontWeight = 'normal';
    spanData.style.opacity = '0.85';

    const spanTotal = document.createElement('span');
    spanTotal.className = 'rr-badge ms-auto';
    spanTotal.textContent = `${grupo.total} pedido(s)`;

    header.appendChild(spanCarro);
    header.appendChild(spanData);
    header.appendChild(spanTotal);

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

      const campos = [
        { val: linha.pedido },
        { val: linha.tipo,   cls: linha.tipo === 'R' ? 'rr-tipo-r' : 'rr-tipo-e' },
        { val: linha.nome_dest },
        { val: linha.fones },
        { val: linha.endereco_dest },
        { val: linha.cidade_dest },
        { val: linha.codpost_dest },
        { val: linha.volumes },
        { val: linha.peso },
        { val: linha.periodo, cls: linha.periodo ? `rr-periodo-${linha.periodo}` : '' },
        { val: linha.obs_rota, cls: 'rr-obs' },
      ];

      campos.forEach(({ val, cls }) => {
        const td = document.createElement('td');
        td.textContent = val ?? '';
        if (cls) td.className = cls;
        tr.appendChild(td);
      });

      tbody.appendChild(tr);
    });

    table.appendChild(thead);
    table.appendChild(tbody);

    const wrapper = document.createElement('div');
    wrapper.className = 'rr-grupo';
    wrapper.appendChild(header);
    wrapper.appendChild(table);
    resultado.appendChild(wrapper);
  });

  btnImprimir.disabled = false;
}

// ─── Buscar ───────────────────────────────────────────────────────────────────
async function buscar() {
  clearMessages();
  const data = inpData.value;
  if (!data) {
    definirMensagem('erro', 'Informe a data para buscar.', false);
    return;
  }

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
    renderizarGrupos(json.grupos || [], json.data_fmt || '');
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
