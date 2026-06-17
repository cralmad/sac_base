import { getCsrfToken, hasScreenPermission, confirmar } from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';
import {
  chamarRota,
  desenharPolyline,
  initReordenacaoLista,
  montarWaypoints,
  renderizarPainelResumo,
} from '/static/js/mapa_rotas_core.js';

// ─── Constantes e estado ─────────────────────────────────────────────────────

const root = document.getElementById('mapa-root');
const URL_PONTOS       = root?.dataset?.urlPontos ?? '';
const URL_SALVAR_COORD = root?.dataset?.urlSalvarCoord ?? '';
const URL_BUSCAR_LOCAL = root?.dataset?.urlBuscarLocal ?? '';
const URL_REGEOCODIFICAR = root?.dataset?.urlRegeocodificar ?? '';
const URL_ROTA         = root?.dataset?.urlRota ?? '';
const URL_SALVAR       = root?.dataset?.urlSalvar ?? '';
const DATA_INICIAL     = root?.dataset?.dataInicial ?? '';
const MOV_ID_INICIAL   = new URLSearchParams(window.location.search).get('mov_id') ?? '';

const podeEditar      = hasScreenPermission('mapa', 'editar');
const podeEditarCarro = hasScreenPermission('mapa', 'editar_carro');
// Mover marcador, re-geocodificar e buscar endereço requerem qualquer uma das permissões de edição
const podeMoverMarcador = podeEditar || podeEditarCarro;

const btnMostrarRotas = document.getElementById('btn-mostrar-rotas');
const btnLimparRotas  = document.getElementById('btn-limpar-rotas');
const legendaWrapper  = document.getElementById('mapa-legenda');
const legendaItens    = document.getElementById('mapa-legenda-itens');
const avisoGeocoding      = document.getElementById('mapa-aviso-geocoding');
const avisoTexto          = document.getElementById('mapa-aviso-texto');
const mapaInfo            = document.getElementById('mapa-info');
const mapaContagemLabel   = document.getElementById('mapa-contagem-label');
const mapaProgressoLabel  = document.getElementById('mapa-progresso-label');
const mapaProgressoWrapper = document.getElementById('mapa-progresso-wrapper');
const mapaProgressoBarra  = document.getElementById('mapa-progresso-barra');
const listaWrapper    = document.getElementById('mapa-lista-wrapper');
const listaBadge      = document.getElementById('mapa-lista-badge');
const listaTbody      = document.getElementById('mapa-lista-tbody');
const listaFiltro     = document.getElementById('mapa-lista-filtro');
const inputRaioFilialKm = document.getElementById('mapa-raio-filial-km');
const resumoRotasWrapper = document.getElementById('mapa-rotas-resumo-wrapper');

let mapaLeaflet   = null;
let marcadores    = {};       // mov_id → marker
let rotasLayer    = null;     // LayerGroup de polylines
let geojsonData   = null;     // última FeatureCollection carregada
let depositoCoord = null;     // { lat, lng } da filial ativa, ou null
let marcadorDeposito = null;  // Leaflet marker do depósito
let circuloRaioFilial = null; // círculo opcional em torno da filial (Leaflet radius em metros)
let carregamentoPontosEmCurso = false;
let popupEventsInicializados = false;
const featByMovId = new Map();
let carroSelecionado = null; // number|null
const ordemParadasPorCarro = new Map(); // carroKey -> [mov_id]
let reordenacaoHandle = null;
let avisoOrdemPendente = false;

// ─── Inicialização do mapa ───────────────────────────────────────────────────

function inicializarMapa() {
  if (mapaLeaflet) return;
  mapaLeaflet = L.map('mapa-leaflet').setView([39.5, -8.0], 7);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
    maxZoom: 19,
  }).addTo(mapaLeaflet);
  rotasLayer = L.layerGroup().addTo(mapaLeaflet);
}

function _carroKey(carro) {
  return carro == null ? '__sem_carro__' : String(carro);
}

function _parseCarro(x) {
  if (x == null) return null;
  const n = typeof x === 'number' ? x : parseInt(String(x), 10);
  return Number.isFinite(n) ? n : null;
}

// ─── Ícone de pin colorido ────────────────────────────────────────────────────

function criarIcone(cor, carro, segueParaEntrega = true, geocodingPrecision = '') {
  const badgeEntrega = segueParaEntrega ? '' : `
      <circle cx="22" cy="6" r="6" fill="#dc3545" stroke="#fff" stroke-width="1.5"/>
      <text x="22" y="10" text-anchor="middle" font-family="Arial,sans-serif" font-size="9" font-weight="bold" fill="#fff">!</text>`;
  const badgeMuitoImpreciso = geocodingPrecision === 'muito_impreciso' ? `
      <circle cx="6" cy="6" r="6" fill="#dc3545" stroke="#fff" stroke-width="1.5"/>
      <text x="6" y="10" text-anchor="middle" font-family="Arial,sans-serif" font-size="9" font-weight="bold" fill="#fff">?</text>` : '';
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="38" viewBox="0 0 28 38">
      <path d="M14 0C6.3 0 0 6.3 0 14c0 9.6 14 24 14 24s14-14.4 14-24C28 6.3 21.7 0 14 0z"
            fill="${cor}" stroke="#fff" stroke-width="2"/>
      <text x="14" y="18" text-anchor="middle" dominant-baseline="middle"
            font-family="Arial,sans-serif" font-size="10" font-weight="bold"
            fill="#fff">${carro != null ? carro : '?'}</text>
      ${badgeMuitoImpreciso}${badgeEntrega}
    </svg>`;
  return L.divIcon({
    html: svg,
    iconSize: [28, 38],
    iconAnchor: [14, 38],
    popupAnchor: [0, -40],
    className: '',
  });
}

// ─── Popup HTML ───────────────────────────────────────────────────────────────

function _esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function _fmtPeso(valor) {
  const n = parseFloat(valor);
  if (isNaN(n)) return valor ?? '—';
  return n.toLocaleString('pt-PT', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function _precisaoCor(precision) {
  if (precision === 'muito_impreciso') return '#dc3545';
  if (precision === 'impreciso') return '#ffc107';
  return null;
}

function conteudoPopup(p) {
  const conf = (p.volume != null && p.volume === p.volume_conf) ? '✅' : '❌';
  const corPrec = _precisaoCor(p.geocoding_precision);
  const dotHtml = corPrec
    ? `<span class="mapa-prec-dot" style="background:${corPrec}" title="${p.geocoding_precision === 'muito_impreciso' ? 'Localiza\u00e7\u00e3o muito imprecisa' : 'Localiza\u00e7\u00e3o imprecisa'}"></span>`
    : '';
  const displayLine = p.geocoding_display
    ? `<span class="mapa-geocoding-display">${_esc(p.geocoding_display)}</span><hr style="width:80%;margin:2px auto">`
    : '';
  const carroLabel = p.carro != null ? `Carro ${p.carro}` : 'Sem carro';
  const editorCarro = podeEditarCarro ? `
      <div class="input-group input-group-sm flex-shrink-1" style="min-width: 0; max-width: 210px;">
        <span class="input-group-text">Carro</span>
        <input type="number" min="1" class="form-control form-control-sm inp-popup-carro"
               style="max-width:72px"
               value="${p.carro ?? ''}" data-mov-id="${p.mov_id}">
        <button class="btn btn-outline-primary btn-popup-salvar-carro" type="button"
                data-mov-id="${p.mov_id}" title="Salvar carro">Salvar</button>
      </div>` : '';
  const botoesAcao = (podeEditarCarro || podeMoverMarcador) ? `
      <hr class="my-1">
      <div class="d-flex align-items-center gap-1 flex-nowrap">
        ${editorCarro}
        ${podeMoverMarcador ? `<button class="btn btn-sm btn-outline-warning btn-popup-regeocodificar flex-shrink-0"
                              data-pedido-id="${p.pedido_id}" data-mov-id="${p.mov_id}"
                              title="Re-geocodificar"><i class="bi bi-arrow-repeat"></i></button>` : ''}
      </div>` : '';
  return `
    <div class="mapa-popup">
      <div class="d-flex align-items-center gap-1"><strong>${_esc(p.referencia)}</strong> <span class="text-muted small">(${_esc(p.tipo)})</span>${dotHtml}</div>
      ${p.tem_devolucao ? '<div class="alert alert-warning py-1 px-2 my-1 small mb-1">Atenção: pedido com devolução associada.</div>' : ''}
      ${displayLine}<span class="small">${_esc(p.endereco)}, <em>${_esc(p.codpost)} ${_esc(p.cidade)}</em></span><br>
      <div class="d-flex justify-content-between gap-2">
        <span>Vol: <b>${p.volume_conf ?? '—'}</b>/<b>${p.volume ?? '—'}</b> ${conf}</span>
        <span>Peso: ${_esc(_fmtPeso(p.peso))}</span>
        ${p.periodo ? `<span class="text-muted small">${_esc(p.periodo)}</span>` : ''}
      </div>
      ${p.obs_rota ? `<span class="text-primary small">Obs Rota: ${_esc(p.obs_rota)}</span><br>` : ''}
      ${p.obs ? `<span class="text-secondary small">Obs: ${_esc(p.obs)}</span><br>` : ''}
      ${botoesAcao}
      ${podeMoverMarcador ? `
      <div class="input-group input-group-sm mt-1">
        <input type="text" class="form-control inp-popup-busca-local"
               placeholder="Buscar endereço…"
               data-pedido-id="${p.pedido_id}" data-mov-id="${p.mov_id}">
        <button class="btn btn-outline-secondary btn-popup-buscar-local" type="button" title="Buscar"><i class="bi bi-search"></i></button>
      </div>
      <div class="mapa-popup-busca-status small text-muted mt-1"></div>` : ''}
    </div>`;
}

// ─── Renderização dos marcadores ──────────────────────────────────────────────

function renderizarMarcadores(geojson) {
  // Remove marcadores antigos
  for (const m of Object.values(marcadores)) m.remove();
  marcadores = {};
  featByMovId.clear();

  for (const feat of geojson.features) {
    const p = feat.properties;
    const [lng, lat] = feat.geometry.coordinates;

    const marker = L.marker([lat, lng], {
      icon: criarIcone(p.cor, p.carro, p.segue_para_entrega !== false, p.geocoding_precision || ''),
      draggable: podeMoverMarcador,
      title: p.referencia,
    });

    marker.bindPopup(conteudoPopup(p), { maxWidth: 280 });
    marker.feature = feat;
    featByMovId.set(String(p.mov_id), feat);

    if (podeMoverMarcador) {
      marker.on('dragend', (e) => {
        const latLngOriginal = L.latLng(feat.geometry.coordinates[1], feat.geometry.coordinates[0]);
        const { lat: novoLat, lng: novoLng } = e.target.getLatLng();

        // Reverte imediatamente — só move se o utilizador confirmar
        marker.setLatLng(latLngOriginal);

        confirmar({
          titulo: 'Confirmar reposicionamento',
          mensagem: `Mover o ponto "${p.referencia}" para a nova localização?`,
          onConfirmar: async () => {
            marker.setLatLng([novoLat, novoLng]);
            feat.geometry.coordinates = [novoLng, novoLat];
            const ok = await salvarCoordenadas(p.pedido_id, novoLat, novoLng);
            if (ok) {
              feat.properties.geocoding_display = '';
              feat.properties.geocoding_precision = '';
              marker.setIcon(
                criarIcone(feat.properties.cor, feat.properties.carro, feat.properties.segue_para_entrega !== false, ''),
              );
            }
          },
        });
      });
    }

    marker.addTo(mapaLeaflet);
    marcadores[p.mov_id] = marker;
  }

  if (!popupEventsInicializados) {
    popupEventsInicializados = true;
    mapaLeaflet.on('popupopen', (e) => {
    const popup = e.popup.getElement();
    if (!popup) return;
    const statusEl = popup.querySelector('.mapa-popup-busca-status');

    // Salvar carro inline no popup
    const btnSalvarCarro = popup.querySelector('.btn-popup-salvar-carro');
    const inpCarro = popup.querySelector('.inp-popup-carro');
    if (btnSalvarCarro && inpCarro) {
      btnSalvarCarro.addEventListener('click', async () => {
        const movId = btnSalvarCarro.dataset.movId;
        await salvarCarroNoPopup(movId, inpCarro.value.trim(), e.popup, statusEl);
      });
      inpCarro.addEventListener('keydown', async (ev) => {
        if (ev.key === 'Enter') {
          ev.preventDefault();
          const movId = btnSalvarCarro.dataset.movId;
          await salvarCarroNoPopup(movId, inpCarro.value.trim(), e.popup, statusEl);
        }
      });
    }

    // Botão re-geocodificar
    const btnRegeo = popup.querySelector('.btn-popup-regeocodificar');
    if (btnRegeo) {
      btnRegeo.addEventListener('click', async () => {
        const pedidoId = parseInt(btnRegeo.dataset.pedidoId, 10);
        const movId = btnRegeo.dataset.movId;
        btnRegeo.disabled = true;
        btnRegeo.textContent = '⏳ Geocodificando...';
        try {
          const resp = await fetch(URL_REGEOCODIFICAR, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ pedido_id: pedidoId }),
          });
          const data = await resp.json();
          if (!data.success) {
            btnRegeo.textContent = `❌ ${data.mensagem || 'Erro'}`;
            return;
          }
          // Actualiza marcador e geojson em memória
          const marker = marcadores[movId];
          const feat = featByMovId.get(String(movId));
          if (marker) marker.setLatLng([data.lat, data.lng]);
          if (feat) {
            feat.geometry.coordinates = [data.lng, data.lat];
            feat.properties.geocoding_display = data.geocoding_display;
            feat.properties.geocoding_precision = data.geocoding_precision;
          }
          if (marker && feat) {
            marker.setIcon(
              criarIcone(feat.properties.cor, feat.properties.carro, feat.properties.segue_para_entrega !== false, feat.properties.geocoding_precision || ''),
            );
          }
          // Mostra feedback antes de substituir o DOM do popup
          if (statusEl) {
            statusEl.textContent = `\u2713 Re-geocodificado: ${(data.geocoding_display || '').slice(0, 60)}`;
            statusEl.className = 'mapa-popup-busca-status small text-success mt-1';
          }
          btnRegeo.textContent = '\u2714 Concluído';
          // Fecha e reabre o popup para actualizar o conteúdo (dot + display_name)
          // e re-vincular os event listeners via popupopen
          if (marker && feat) {
            setTimeout(() => {
              marker.setPopupContent(conteudoPopup(feat.properties));
              marker.closePopup();
              marker.openPopup();
            }, 800);
          }
        } catch {
          btnRegeo.disabled = false;
          btnRegeo.textContent = '🔄 Re-geocodificar';
          if (statusEl) {
            statusEl.textContent = 'Erro de comunicação.';
            statusEl.className = 'mapa-popup-busca-status small text-danger mt-1';
          }
        }
      });
    }

    // Busca de endereço para reposicionar pin
    const btnBuscar = popup.querySelector('.btn-popup-buscar-local');
    const inpBusca  = popup.querySelector('.inp-popup-busca-local');
    if (!btnBuscar || !inpBusca) return;

    const executarBusca = async () => {
      const q = inpBusca.value.trim();
      if (!q) return;
      btnBuscar.disabled = true;
      btnBuscar.textContent = '\u23f3';
      statusEl.textContent = 'Buscando...';
      try {
        const pedidoId = parseInt(inpBusca.dataset.pedidoId, 10);
        const movId    = inpBusca.dataset.movId;
        const resp = await fetch(URL_BUSCAR_LOCAL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
          body: JSON.stringify({ pedido_id: pedidoId, query: q }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.success) {
          statusEl.textContent = data.mensagem || 'Endereço não encontrado.';
          return;
        }
        const novoLat = parseFloat(data.lat);
        const novoLng = parseFloat(data.lng);
        const displayName = data.geocoding_display || '';
        const novaPrec = data.geocoding_precision || '';

        // Move o marcador
        const marker = marcadores[movId];
        if (marker) {
          marker.setLatLng([novoLat, novoLng]);
          mapaLeaflet.panTo([novoLat, novoLng]);
        }

        // Salva coordenadas no banco
        const salvou = await salvarCoordenadas(pedidoId, novoLat, novoLng, displayName, novaPrec);
        if (!salvou) {
          statusEl.textContent = 'Falha ao salvar coordenadas.';
          statusEl.className = 'mapa-popup-busca-status small text-danger mt-1';
          return;
        }

        // Atualiza geojson em memória
        const feat = featByMovId.get(String(movId));
        if (feat) {
          feat.geometry.coordinates = [novoLng, novoLat];
          feat.properties.geocoding_display = displayName;
          feat.properties.geocoding_precision = novaPrec;
          if (marker) {
            marker.setIcon(
              criarIcone(feat.properties.cor, feat.properties.carro, feat.properties.segue_para_entrega !== false, feat.properties.geocoding_precision || ''),
            );
            marker.setPopupContent(conteudoPopup(feat.properties));
          }
        }

        statusEl.textContent = `\u2713 Posicionado em: ${displayName.slice(0, 60)}...`;
        statusEl.className = 'mapa-popup-busca-status small text-success mt-1';
      } catch {
        statusEl.textContent = 'Erro ao buscar endereço.';
        statusEl.className = 'mapa-popup-busca-status small text-danger mt-1';
      } finally {
        btnBuscar.disabled = false;
        btnBuscar.textContent = '\uD83D\uDD0D';
      }
    };

    btnBuscar.addEventListener('click', executarBusca);
    inpBusca.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); executarBusca(); } });
    });
  }
}

// ─── Lista de pedidos ─────────────────────────────────────────────────────────────

function renderizarLista(geojson) {
  listaTbody.replaceChildren();
  const total = geojson.features.length;
  listaBadge.textContent = String(total);

  const featuresSorted = [...geojson.features].sort((a, b) => {
    const ca = a.properties.carro, cb = b.properties.carro;
    // Sem carro vai para o fim
    const na = ca != null ? parseInt(ca, 10) : Infinity;
    const nb = cb != null ? parseInt(cb, 10) : Infinity;
    if (na !== nb) return na - nb;
    return String(a.properties.codpost || '').localeCompare(String(b.properties.codpost || ''));
  });

  for (const feat of featuresSorted) {
    const p = feat.properties;
    const tr = document.createElement('tr');
    tr.dataset.movId = p.mov_id;
    tr.dataset.ref   = String(p.referencia).toLowerCase();
    tr.dataset.carro = p.carro != null ? String(p.carro) : '';
    tr.dataset.segue = p.segue_para_entrega === false ? '0' : '1';
    if (p.segue_para_entrega === false) tr.classList.add('mapa-linha-nao-segue');

    // Handle de reordenação (mostra só quando carro selecionado)
    const tdOrd = document.createElement('td');
    tdOrd.className = 'mapa-ordem-td';
    const handle = document.createElement('span');
    handle.className = 'mapa-ordem-handle';
    handle.title = 'Arraste para reordenar as paradas da rota';
    handle.textContent = '⋮⋮';
    tdOrd.appendChild(handle);
    tr.appendChild(tdOrd);

    // Referência (botão que foca o pin)
    const tdRef = document.createElement('td');
    const btnRef = document.createElement('button');
    btnRef.type = 'button';
    btnRef.className = 'btn btn-link btn-sm p-0 fw-semibold text-decoration-none';
    btnRef.textContent = p.referencia;
    btnRef.title = 'Ver no mapa';
    btnRef.addEventListener('click', () => focarMarcador(p.mov_id));
    tdRef.appendChild(btnRef);
    if (p.tem_devolucao) {
      const badgeDev = document.createElement('span');
      badgeDev.className = 'badge text-bg-warning ms-2';
      badgeDev.textContent = 'Devolucao';
      badgeDev.title = 'Pedido com devolucao associada';
      tdRef.appendChild(badgeDev);
    }
    if (p.segue_para_entrega === false) {
      const badgeNao = document.createElement('span');
      badgeNao.className = 'badge text-bg-danger ms-2';
      badgeNao.textContent = 'Nao segue';
      badgeNao.title = 'Pedido não segue para entrega (não entra na rota).';
      tdRef.appendChild(badgeNao);
    }
    tr.appendChild(tdRef);

    // Tipo
    const tdTipo = document.createElement('td');
    tdTipo.textContent = p.tipo ? p.tipo.charAt(0) : '—';
    tr.appendChild(tdTipo);

    // Destinatário / Endereço
    const tdEnd = document.createElement('td');
    const small = document.createElement('small');
    small.className = 'text-muted';
    small.textContent = [p.endereco, p.cidade].filter(Boolean).join(', ');
    tdEnd.textContent = '';
    tdEnd.appendChild(small);
    tr.appendChild(tdEnd);

    // Cód. Postal
    const tdCodpost = document.createElement('td');
    tdCodpost.textContent = p.codpost || '—';
    tr.appendChild(tdCodpost);

    // Carro
    const tdCarro = document.createElement('td');
    if (p.carro != null) {
      const badge = document.createElement('span');
      badge.className = 'badge';
      badge.style.background = p.cor;
      badge.textContent = p.carro;
      tdCarro.appendChild(badge);
    } else {
      tdCarro.textContent = '—';
    }
    tr.appendChild(tdCarro);

    listaTbody.appendChild(tr);
  }

  listaWrapper.classList.toggle('d-none', total === 0);
  aplicarFiltroLista();
  inicializarReordenacaoLista();
}

function filtrarLista(termo) {
  const t = termo.trim().toLowerCase();
  listaFiltro.value = termo;
  aplicarFiltroLista();
}

listaFiltro?.addEventListener('input', () => filtrarLista(listaFiltro.value));

function aplicarFiltroLista() {
  const t = (listaFiltro?.value || '').trim().toLowerCase();
  let visiveis = 0;
  listaTbody.querySelectorAll('tr').forEach(tr => {
    const matchRef = t === '' || (tr.dataset.ref || '').includes(t);
    const matchCarro = carroSelecionado == null
      ? true
      : (tr.dataset.carro || '') === String(carroSelecionado);
    const hide = !(matchRef && matchCarro);
    tr.classList.toggle('d-none', hide);
    if (!hide) visiveis += 1;
  });
  if (listaBadge) listaBadge.textContent = String(visiveis);
  if (reordenacaoHandle) reordenacaoHandle.refresh?.();
}

// ─── Focar marcador por mov_id ──────────────────────────────────────────────

function focarMarcador(movId) {
  const marker = marcadores[String(movId)];
  if (!marker) return;
  mapaLeaflet.setView(marker.getLatLng(), Math.max(mapaLeaflet.getZoom(), 15));
  marker.openPopup();
  // Destaca linha correspondente na lista
  listaTbody.querySelectorAll('tr').forEach(tr => tr.classList.remove('table-primary'));
  const linhaAtiva = listaTbody.querySelector(`tr[data-mov-id="${movId}"]`);
  if (linhaAtiva) {
    linhaAtiva.classList.add('table-primary');
    linhaAtiva.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

// ─── Legenda de carros ────────────────────────────────────────────────────────

function renderizarLegenda(geojson) {
  const carros = new Map();
  for (const f of geojson.features) {
    const c = f.properties.carro;
    const key = c != null ? String(c) : '—';
    if (!carros.has(key)) carros.set(key, f.properties.cor);
  }

  legendaItens.replaceChildren();
  for (const [carro, cor] of [...carros.entries()].sort((a, b) => {
    const na = parseInt(a[0], 10), nb = parseInt(b[0], 10);
    return isNaN(na) || isNaN(nb) ? a[0].localeCompare(b[0]) : na - nb;
  })) {
    const item = document.createElement('span');
    item.className = 'mapa-legenda-item';
    const dot = document.createElement('span');
    dot.className = 'mapa-legenda-dot';
    dot.style.background = cor;
    const txt = document.createElement('span');
    txt.textContent = carro !== '—' ? `Carro ${carro}` : 'Sem carro';
    item.appendChild(dot);
    item.appendChild(txt);
    // Clique na legenda → filtra/destaca marcadores desse carro
    item.style.cursor = 'pointer';
    item.dataset.carro = carro === '—' ? '' : String(parseInt(carro, 10));
    item.addEventListener('click', () => selecionarCarro(carro === '—' ? null : parseInt(carro, 10), item));
    legendaItens.appendChild(item);
  }
  legendaWrapper.classList.remove('d-none');
}

function selecionarCarro(carro, itemEl = null) {
  const novo = _parseCarro(carro);
  const mesmo = carroSelecionado === novo;
  carroSelecionado = mesmo ? null : novo;
  avisoOrdemPendente = false;
  rotasLayer?.clearLayers();
  btnLimparRotas?.classList.add('d-none');
  if (resumoRotasWrapper) resumoRotasWrapper.classList.add('d-none');

  // Atualiza classe ativa na legenda
  legendaItens?.querySelectorAll('.mapa-legenda-item').forEach(el => el.classList.remove('mapa-legenda-item--ativo'));
  if (carroSelecionado != null) {
    const el = itemEl || legendaItens?.querySelector(`.mapa-legenda-item[data-carro="${carroSelecionado}"]`);
    el?.classList.add('mapa-legenda-item--ativo');
  }

  // Botão rota habilita só com carro selecionado
  if (btnMostrarRotas) btnMostrarRotas.disabled = carroSelecionado == null;

  // Opacidade dos pins
  if (geojsonData) {
    for (const feat of geojsonData.features) {
      const m = marcadores[feat.properties.mov_id];
      if (!m) continue;
      const match = carroSelecionado == null ? true : feat.properties.carro === carroSelecionado;
      m.setOpacity(match ? 1 : 0.15);
    }
  }

  aplicarFiltroLista();
  _inicializarOrdemCarroSelecionado();
  inicializarReordenacaoLista();
}

function _inicializarOrdemCarroSelecionado() {
  if (carroSelecionado == null || !listaTbody) return;
  const ids = [...listaTbody.querySelectorAll('tr:not(.d-none)')]
    .filter(tr => (tr.dataset.carro || '') === String(carroSelecionado))
    .filter(tr => (tr.dataset.segue || '1') === '1')
    .map(tr => parseInt(tr.dataset.movId, 10))
    .filter(n => Number.isFinite(n));
  ordemParadasPorCarro.set(_carroKey(carroSelecionado), ids);
}

function _featuresCarroSelecionado() {
  if (!geojsonData || carroSelecionado == null) return [];
  return geojsonData.features.filter(f => f.properties?.carro === carroSelecionado);
}

async function gerarRotaCarroSelecionado() {
  if (!geojsonData || carroSelecionado == null) return;
  AppLoader.show();
  try {
    const feats = _featuresCarroSelecionado();
    const ordem = ordemParadasPorCarro.get(_carroKey(carroSelecionado)) || null;
    const pontos = montarWaypoints(feats, { deposito: depositoCoord, ordemMovIds: ordem, somenteSegueEntrega: true });
    const pontosApi = pontos.map(p => ({ lat: p.lat, lng: p.lng }));

    if (pontosApi.length < 2) {
      renderizarPainelResumo(resumoRotasWrapper, {
        carro: carroSelecionado,
        distancia_metros: null,
        duracao_segundos: null,
        paradas: Math.max(0, pontosApi.length - (depositoCoord ? 1 : 0)),
        fallback: false,
        deposito: !!depositoCoord,
        aviso: 'Sem paradas elegíveis para calcular rota.',
      });
      return;
    }

    const { ok, data } = await chamarRota(URL_ROTA, pontosApi, getCsrfToken(), carroSelecionado);
    if (!ok || !data?.success) {
      renderizarPainelResumo(resumoRotasWrapper, {
        carro: carroSelecionado,
        distancia_metros: null,
        duracao_segundos: null,
        paradas: Math.max(0, pontosApi.length - (depositoCoord ? 1 : 0)),
        fallback: false,
        deposito: !!depositoCoord,
        aviso: data?.mensagem || 'Falha ao calcular rota.',
      });
      return;
    }

    desenharPolyline(rotasLayer, data.geometry, { color: feats[0]?.properties?.cor || '#198754', weight: 4, opacity: 0.85 });
    btnLimparRotas.classList.remove('d-none');
    renderizarPainelResumo(resumoRotasWrapper, {
      carro: carroSelecionado,
      distancia_metros: data.distancia_metros,
      duracao_segundos: data.duracao_segundos,
      paradas: Math.max(0, pontosApi.length - (depositoCoord ? 1 : 0)),
      fallback: !!data.fallback,
      deposito: !!depositoCoord,
      aviso: avisoOrdemPendente ? 'Ordem alterada — gere a rota novamente.' : '',
    });
    avisoOrdemPendente = false;
  } finally {
    AppLoader.hide();
  }
}

// ─── Carregar pontos ─────────────────────────────────────────────────────────

async function carregarPontos(data) {
  if (carregamentoPontosEmCurso) return;
  carregamentoPontosEmCurso = true;
  inicializarMapa();
  AppLoader.show();
  avisoGeocoding.classList.remove('d-none');
  avisoTexto.textContent = 'Carregando pontos e geocodificando endereços, aguarde…';
  rotasLayer.clearLayers();
  btnMostrarRotas.disabled = true;
  btnLimparRotas.classList.add('d-none');
  mapaInfo.classList.add('d-none');
  if (resumoRotasWrapper) resumoRotasWrapper.classList.add('d-none');
  carroSelecionado = null;
  ordemParadasPorCarro.clear();
  avisoOrdemPendente = false;

  try {
    const resp = await fetch(URL_PONTOS, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ data }),
    });
    const result = await resp.json();

    if (!result.success) {
      avisoTexto.textContent = result.mensagem || 'Erro ao carregar pontos.';
      return;
    }

    geojsonData   = result.geojson;
    depositoCoord = result.deposito ?? null;
    renderizarMarcadores(geojsonData);
    renderizarLegenda(geojsonData);
    renderizarDeposito();
    definirInputRaioFilialDisponivel(
      !!(depositoCoord && depositoCoord.lat != null && depositoCoord.lng != null),
    );
    renderizarLista(geojsonData);

    // Ajusta o mapa aos marcadores (salta fitBounds se veio com mov_id específico)
    const coords = geojsonData.features.map(f => [f.geometry.coordinates[1], f.geometry.coordinates[0]]);
    if (coords.length > 0 && !MOV_ID_INICIAL) mapaLeaflet.fitBounds(L.latLngBounds(coords), { padding: [40, 40] });

    const totalComCoord = result.total ?? 0;
    const totalSemCoord = result.sem_coord ?? 0;
    const totalGeral    = totalComCoord + totalSemCoord;
    const pct           = totalGeral > 0 ? Math.round((totalComCoord / totalGeral) * 100) : 0;

    mapaContagemLabel.textContent  = `${totalComCoord} endereço(s) exibido(s) no mapa`;
    mapaProgressoLabel.textContent = `${totalComCoord}/${totalGeral} com coordenadas (${pct}%)`;
    mapaProgressoBarra.style.width = `${pct}%`;
    mapaProgressoWrapper.setAttribute('aria-valuenow', pct);
    mapaProgressoBarra.className   = pct === 100 ? 'progress-bar bg-success'
                                   : pct > 0    ? 'progress-bar bg-warning'
                                                : 'progress-bar bg-danger';
    mapaInfo.classList.remove('d-none');

    if (totalSemCoord > 0) {
      if (result.limite_atingido) {
        avisoTexto.textContent = `${totalSemCoord} endereço(s) ainda sem coordenadas. O sistema processou um lote parcial para manter performance; recarregue para continuar.`;
      } else {
        avisoTexto.textContent = `${totalSemCoord} endereço(s) não foram geocodificados e não aparecem no mapa.`;
      }
    } else {
      avisoGeocoding.classList.add('d-none');
    }

    btnMostrarRotas.disabled = geojsonData.features.length === 0;
  } catch {
    avisoTexto.textContent = 'Erro de comunicação ao carregar pontos.';
  } finally {
    carregamentoPontosEmCurso = false;
    AppLoader.hide();
  }
}

// ─── Salvar coordenadas (drag do pin) ────────────────────────────────────────

async function salvarCoordenadas(pedidoId, lat, lng, geocodingDisplay = '', geocodingPrecision = '') {
  try {
    const resp = await fetch(URL_SALVAR_COORD, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ pedido_id: pedidoId, lat, lng, geocoding_display: geocodingDisplay, geocoding_precision: geocodingPrecision }),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

// ─── Marcador do depósito ────────────────────────────────────────────────────

function criarIconeDeposito() {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
      <circle cx="16" cy="16" r="15" fill="#1a1a2e" stroke="#fff" stroke-width="2"/>
      <text x="16" y="21" text-anchor="middle" font-size="16" fill="#fff">🏭</text>
    </svg>`;
  return L.divIcon({ html: svg, iconSize: [32, 32], iconAnchor: [16, 16], popupAnchor: [0, -18], className: '' });
}

function _kmFilialParaMetros() {
  if (!inputRaioFilialKm) return 0;
  let v = parseFloat(String(inputRaioFilialKm.value).replace(',', '.'));
  if (Number.isNaN(v) || v <= 0) return 0;
  const maxKm = parseFloat(inputRaioFilialKm.getAttribute('max') || '2000');
  if (!Number.isNaN(maxKm) && v > maxKm) v = maxKm;
  return v * 1000;
}

function atualizarCirculoFilialOpcional() {
  if (circuloRaioFilial) {
    circuloRaioFilial.remove();
    circuloRaioFilial = null;
  }
  if (!depositoCoord || !mapaLeaflet) return;
  const metros = _kmFilialParaMetros();
  if (metros <= 0) return;
  const centro = [depositoCoord.lat, depositoCoord.lng];
  const km = Math.round(metros / 1000);
  circuloRaioFilial = L.circle(centro, {
    radius: metros,
    color: '#1a1a2e',
    weight: 2,
    opacity: 0.45,
    fillColor: '#4363d8',
    fillOpacity: 0.06,
  });
  circuloRaioFilial.bindPopup(
    `<strong>Área de referência</strong><br>Raio aproximado de ${km} km em torno da filial.`,
  );
  circuloRaioFilial.addTo(mapaLeaflet);
}

function renderizarDeposito() {
  if (marcadorDeposito) { marcadorDeposito.remove(); marcadorDeposito = null; }
  if (circuloRaioFilial) { circuloRaioFilial.remove(); circuloRaioFilial = null; }
  if (!depositoCoord || !mapaLeaflet) return;
  const centro = [depositoCoord.lat, depositoCoord.lng];
  marcadorDeposito = L.marker(centro, {
    icon: criarIconeDeposito(),
    title: 'Depósito',
    zIndexOffset: 1000,
  });
  marcadorDeposito.bindPopup('<strong>Depósito</strong><br>Ponto de partida/chegada das rotas.');
  marcadorDeposito.addTo(mapaLeaflet);
  atualizarCirculoFilialOpcional();
}

function definirInputRaioFilialDisponivel(disponivel) {
  if (!inputRaioFilialKm) return;
  inputRaioFilialKm.disabled = !disponivel;
  if (!disponivel) {
    inputRaioFilialKm.value = '0';
    if (circuloRaioFilial && mapaLeaflet) {
      circuloRaioFilial.remove();
      circuloRaioFilial = null;
    }
  }
}

function inicializarReordenacaoLista() {
  if (!listaTbody) return;
  if (!reordenacaoHandle) {
    reordenacaoHandle = initReordenacaoLista(listaTbody, {
      selectorLinha: 'tr',
      canDrag: (tr) => {
        if (carroSelecionado == null) return false;
        if (tr.classList.contains('d-none')) return false;
        if ((tr.dataset.carro || '') !== String(carroSelecionado)) return false;
        if ((tr.dataset.segue || '1') !== '1') return false;
        return true;
      },
      onOrdemAlterada: (movIds) => {
        if (carroSelecionado == null) return;
        ordemParadasPorCarro.set(_carroKey(carroSelecionado), movIds);
        avisoOrdemPendente = true;
        if (!btnLimparRotas.classList.contains('d-none')) {
          renderizarPainelResumo(resumoRotasWrapper, {
            carro: carroSelecionado,
            distancia_metros: null,
            duracao_segundos: null,
            paradas: movIds.length,
            fallback: false,
            deposito: !!depositoCoord,
            aviso: 'Ordem alterada — clique em Gerar rota.',
          });
        }
      },
    });
  } else {
    reordenacaoHandle.refresh?.();
  }
}

async function salvarCarroNoPopup(movId, novoCarro, popupInstance, statusEl) {
  AppLoader.show();
  try {
    const movFeat = featByMovId.get(String(movId));
    const updatedAt = movFeat?.properties?.updated_at ?? '';
    const resp = await fetch(URL_SALVAR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({
        id: movId,
        carro: novoCarro,
        obs_rota: movFeat?.properties?.obs_rota ?? '',
        volume_conf: movFeat?.properties?.volume_conf ?? 0,
        periodo: movFeat?.properties?.periodo ?? '',
        updated_at: updatedAt,
      }),
    });
    const data = await resp.json();
    if (resp.status === 409) {
      if (statusEl) {
        statusEl.textContent = 'Conflito de edição, recarregue o mapa.';
        statusEl.className = 'mapa-popup-busca-status small text-warning mt-1';
      }
      return;
    }
    if (!data.success || !movFeat) {
      if (statusEl) {
        statusEl.textContent = data.mensagem || 'Falha ao salvar carro.';
        statusEl.className = 'mapa-popup-busca-status small text-danger mt-1';
      }
      return;
    }

    const carroNum = novoCarro !== '' ? parseInt(novoCarro, 10) : null;
    const corNova = _corCarro(carroNum);
    movFeat.properties.carro = carroNum;
    movFeat.properties.cor = corNova;
    movFeat.properties.updated_at = data.updated_at ?? updatedAt;
    const marker = marcadores[movId];
    if (marker) {
      marker.setIcon(
        criarIcone(corNova, carroNum, movFeat.properties.segue_para_entrega !== false, movFeat.properties.geocoding_precision || ''),
      );
      marker.setPopupContent(conteudoPopup(movFeat.properties));
      popupInstance.close();
      marker.openPopup();
    }
    renderizarLegenda(geojsonData);
    renderizarLista(geojsonData);
  } finally {
    AppLoader.hide();
  }
}

function _corCarro(carro) {
  const CORES = [
    "#e6194b","#3cb44b","#4363d8","#f58231","#911eb4",
    "#42d4f4","#f032e6","#bfef45","#fabed4","#469990",
    "#dcbeff","#9A6324","#fffac8","#800000","#aaffc3",
    "#808000","#ffd8b1","#000075","#a9a9a9","#ffffff",
  ];
  if (carro == null) return "#6c757d";
  return CORES[(parseInt(carro, 10) - 1) % CORES.length];
}

// ─── Eventos ─────────────────────────────────────────────────────────────────

document.getElementById('form-filtro-mapa').addEventListener('submit', e => {
  e.preventDefault();
  const data = document.getElementById('mapa-filtro-data').value;
  if (data) carregarPontos(data);
});

btnMostrarRotas?.addEventListener('click', gerarRotaCarroSelecionado);

btnLimparRotas?.addEventListener('click', () => {
  rotasLayer.clearLayers();
  btnLimparRotas.classList.add('d-none');
  if (resumoRotasWrapper) resumoRotasWrapper.classList.add('d-none');
});

inputRaioFilialKm?.addEventListener('input', () => {
  if (!depositoCoord || !mapaLeaflet) return;
  atualizarCirculoFilialOpcional();
});
inputRaioFilialKm?.addEventListener('change', () => {
  if (!depositoCoord || !mapaLeaflet) return;
  atualizarCirculoFilialOpcional();
});

// Carrega automaticamente se veio com data da tela anterior
if (DATA_INICIAL) {
  carregarPontos(DATA_INICIAL).then(() => {
    if (MOV_ID_INICIAL) setTimeout(() => focarMarcador(MOV_ID_INICIAL), 300);
  });
}
