import { getCsrfToken, hasScreenPermission, confirmar } from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';

// ─── Constantes e estado ─────────────────────────────────────────────────────

const root = document.getElementById('mapa-root');
const URL_PONTOS       = root?.dataset?.urlPontos ?? '';
const URL_SALVAR_COORD = root?.dataset?.urlSalvarCoord ?? '';
const URL_REGEOCODIFICAR = root?.dataset?.urlRegeocodificar ?? '';
const URL_ROTA         = root?.dataset?.urlRota ?? '';
const URL_SALVAR       = root?.dataset?.urlSalvar ?? '';
const DATA_INICIAL     = root?.dataset?.dataInicial ?? '';

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
const painel              = document.getElementById('mapa-painel');
const painelTitulo    = document.getElementById('mapa-painel-titulo');
const painelCorpo     = document.getElementById('mapa-painel-corpo');

let mapaLeaflet   = null;
let marcadores    = {};       // mov_id → marker
let rotasLayer    = null;     // LayerGroup de polylines
let geojsonData   = null;     // última FeatureCollection carregada
let depositoCoord = null;     // { lat, lng } da filial ativa, ou null
let marcadorDeposito = null;  // Leaflet marker do depósito

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

// ─── Ícone de pin colorido ────────────────────────────────────────────────────

function criarIcone(cor, carro) {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="38" viewBox="0 0 28 38">
      <path d="M14 0C6.3 0 0 6.3 0 14c0 9.6 14 24 14 24s14-14.4 14-24C28 6.3 21.7 0 14 0z"
            fill="${cor}" stroke="#fff" stroke-width="2"/>
      <text x="14" y="18" text-anchor="middle" dominant-baseline="middle"
            font-family="Arial,sans-serif" font-size="10" font-weight="bold"
            fill="#fff">${carro != null ? carro : '?'}</text>
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
    ? `<span class="mapa-geocoding-display">${_esc(p.geocoding_display)}</span><br>`
    : '';
  return `
    <div class="mapa-popup">
      <div class="d-flex align-items-center gap-1"><strong>${_esc(p.referencia)}</strong>${dotHtml}</div>
      ${displayLine}<span class="text-muted small">${_esc(p.tipo)}</span><br>
      ${_esc(p.endereco)}<br>
      <em>${_esc(p.codpost)} ${_esc(p.cidade)}</em><br>
      Vol: <b>${p.volume ?? '—'}</b> | VolConf: <b>${p.volume_conf ?? '—'}</b> ${conf}<br>
      Peso: ${_esc(p.peso)}<br>
      ${p.obs_rota ? `<span class="text-primary small">Obs Rota: ${_esc(p.obs_rota)}</span><br>` : ''}
      ${p.obs ? `<span class="text-secondary small">Obs: ${_esc(p.obs)}</span><br>` : ''}
      ${p.periodo ? `Período: ${_esc(p.periodo)}<br>` : ''}
      <hr class="my-1">
      Carro: <b>${p.carro != null ? p.carro : '—'}</b>
      ${podeEditarCarro ? `<br><button class="btn btn-sm btn-outline-primary mt-1 w-100 btn-popup-editar-carro"
                              data-mov-id="${p.mov_id}" data-carro="${p.carro ?? ''}">
                              ✏️ Alterar carro
                           </button>` : ''}
      ${podeMoverMarcador ? `
      <hr class="my-1">
      <button class="btn btn-sm btn-outline-warning w-100 mb-1 btn-popup-regeocodificar"
              data-pedido-id="${p.pedido_id}" data-mov-id="${p.mov_id}">
        🔄 Re-geocodificar
      </button>
      <div class="input-group input-group-sm mt-1">
        <input type="text" class="form-control inp-popup-busca-local"
               placeholder="Buscar endereço para reposicionar…"
               data-pedido-id="${p.pedido_id}" data-mov-id="${p.mov_id}">
        <button class="btn btn-outline-secondary btn-popup-buscar-local" type="button" title="Buscar">🔍</button>
      </div>
      <div class="mapa-popup-busca-status small text-muted mt-1"></div>` : ''}
    </div>`;
}

// ─── Renderização dos marcadores ──────────────────────────────────────────────

function renderizarMarcadores(geojson) {
  // Remove marcadores antigos
  for (const m of Object.values(marcadores)) m.remove();
  marcadores = {};

  for (const feat of geojson.features) {
    const p = feat.properties;
    const [lng, lat] = feat.geometry.coordinates;

    const marker = L.marker([lat, lng], {
      icon: criarIcone(p.cor, p.carro),
      draggable: podeMoverMarcador,
      title: p.referencia,
    });

    marker.bindPopup(conteudoPopup(p), { maxWidth: 280 });
    marker.feature = feat;

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
            await salvarCoordenadas(p.pedido_id, novoLat, novoLng);
          },
        });
      });
    }

    marker.addTo(mapaLeaflet);
    marcadores[p.mov_id] = marker;
  }

  // Evento delegado nos popups (alterar carro + busca de endereço)
  mapaLeaflet.on('popupopen', (e) => {
    const popup = e.popup.getElement();
    if (!popup) return;

    // Botão editar carro
    const btnCarro = popup.querySelector('.btn-popup-editar-carro');
    if (btnCarro) {
      btnCarro.addEventListener('click', () => abrirPainelCarro(btnCarro.dataset.movId, btnCarro.dataset.carro, e.popup));
    }

    // Botão re-geocodificar
    const btnRegeo = popup.querySelector('.btn-popup-regeocodificar');
    if (btnRegeo) {
      btnRegeo.addEventListener('click', async () => {
        const pedidoId = parseInt(btnRegeo.dataset.pedidoId, 10);
        const movId = btnRegeo.dataset.movId;
        const statusEl = popup.querySelector('.mapa-popup-busca-status');
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
          const feat = geojsonData?.features.find(f => String(f.properties.mov_id) === String(movId));
          if (marker) marker.setLatLng([data.lat, data.lng]);
          if (feat) {
            feat.geometry.coordinates = [data.lng, data.lat];
            feat.properties.geocoding_display = data.geocoding_display;
            feat.properties.geocoding_precision = data.geocoding_precision;
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
    const statusEl  = popup.querySelector('.mapa-popup-busca-status');
    if (!btnBuscar || !inpBusca) return;

    const executarBusca = async () => {
      const q = inpBusca.value.trim();
      if (!q) return;
      btnBuscar.disabled = true;
      btnBuscar.textContent = '\u23f3';
      statusEl.textContent = 'Buscando...';
      try {
        const resp = await fetch(
          `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=1&countrycodes=pt`,
          { headers: { 'Accept-Language': 'pt-PT,pt' } }
        );
        const resultados = await resp.json();
        if (!resultados.length) {
          statusEl.textContent = 'Endereço não encontrado.';
          return;
        }
        const novoLat = parseFloat(resultados[0].lat);
        const novoLng = parseFloat(resultados[0].lon);
        const displayName = resultados[0].display_name || '';
        const tipoNom = resultados[0].type || '';
        const classeNom = resultados[0].class || '';
        const _TIPOS_MUITO_IMP = new Set(['postcode', 'city', 'town', 'village', 'county', 'municipality', 'state', 'country']);
        let novaPrec = 'ok';
        if (_TIPOS_MUITO_IMP.has(tipoNom) || classeNom === 'boundary') {
          novaPrec = 'muito_impreciso';
        } else if (classeNom === 'highway' || classeNom === 'place') {
          novaPrec = 'impreciso';
        }
        const pedidoId = parseInt(inpBusca.dataset.pedidoId, 10);
        const movId    = inpBusca.dataset.movId;

        // Move o marcador
        const marker = marcadores[movId];
        if (marker) {
          marker.setLatLng([novoLat, novoLng]);
          mapaLeaflet.panTo([novoLat, novoLng]);
        }

        // Salva coordenadas no banco
        await salvarCoordenadas(pedidoId, novoLat, novoLng, displayName, novaPrec);

        // Atualiza geojson em memória
        const feat = geojsonData?.features.find(f => String(f.properties.mov_id) === String(movId));
        if (feat) {
          feat.geometry.coordinates = [novoLng, novoLat];
          feat.properties.geocoding_display = displayName;
          feat.properties.geocoding_precision = novaPrec;
          if (marker) marker.setPopupContent(conteudoPopup(feat.properties));
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
    item.addEventListener('click', () => filtrarPorCarro(carro === '—' ? null : parseInt(carro, 10)));
    legendaItens.appendChild(item);
  }
  legendaWrapper.classList.remove('d-none');
}

// Destaca/oculta pins por carro
let filtroCarroAtivo = null;
function filtrarPorCarro(carro) {
  if (filtroCarroAtivo === carro) {
    // Desfaz o filtro
    filtroCarroAtivo = null;
    for (const [id, m] of Object.entries(marcadores)) {
      m.setOpacity(1);
    }
    return;
  }
  filtroCarroAtivo = carro;
  for (const feat of geojsonData.features) {
    const m = marcadores[feat.properties.mov_id];
    if (!m) continue;
    const match = carro === null
      ? feat.properties.carro == null
      : feat.properties.carro === carro;
    m.setOpacity(match ? 1 : 0.15);
  }
}

// ─── Carregar pontos ─────────────────────────────────────────────────────────

async function carregarPontos(data) {
  inicializarMapa();
  AppLoader.show();
  avisoGeocoding.classList.remove('d-none');
  avisoTexto.textContent = 'Carregando pontos e geocodificando endereços, aguarde…';
  rotasLayer.clearLayers();
  btnMostrarRotas.disabled = true;
  btnLimparRotas.classList.add('d-none');
  mapaInfo.classList.add('d-none');

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

    // Ajusta o mapa aos marcadores
    const coords = geojsonData.features.map(f => [f.geometry.coordinates[1], f.geometry.coordinates[0]]);
    if (coords.length > 0) mapaLeaflet.fitBounds(L.latLngBounds(coords), { padding: [40, 40] });

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
      avisoTexto.textContent = `${totalSemCoord} endereço(s) não foram geocodificados e não aparecem no mapa.`;
    } else {
      avisoGeocoding.classList.add('d-none');
    }

    btnMostrarRotas.disabled = geojsonData.features.length === 0;
  } catch {
    avisoTexto.textContent = 'Erro de comunicação ao carregar pontos.';
  } finally {
    AppLoader.hide();
  }
}

// ─── Salvar coordenadas (drag do pin) ────────────────────────────────────────

async function salvarCoordenadas(pedidoId, lat, lng, geocodingDisplay = '', geocodingPrecision = '') {
  try {
    await fetch(URL_SALVAR_COORD, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ pedido_id: pedidoId, lat, lng, geocoding_display: geocodingDisplay, geocoding_precision: geocodingPrecision }),
    });
  } catch {
    // Falha silenciosa — coordenada atualizada localmente de qualquer forma
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

function renderizarDeposito() {
  if (marcadorDeposito) { marcadorDeposito.remove(); marcadorDeposito = null; }
  if (!depositoCoord || !mapaLeaflet) return;
  marcadorDeposito = L.marker([depositoCoord.lat, depositoCoord.lng], {
    icon: criarIconeDeposito(),
    title: 'Depósito',
    zIndexOffset: 1000,
  });
  marcadorDeposito.bindPopup('<strong>Depósito</strong><br>Ponto de partida/chegada das rotas.');
  marcadorDeposito.addTo(mapaLeaflet);
}

// ─── Rotas por carro ─────────────────────────────────────────────────────────

async function tracarRotas() {
  if (!geojsonData) return;
  AppLoader.show();
  rotasLayer.clearLayers();

  // Agrupa features por carro
  const grupos = new Map();
  for (const f of geojsonData.features) {
    const c = f.properties.carro ?? '__sem_carro__';
    if (!grupos.has(c)) grupos.set(c, { pontos: [], cor: f.properties.cor });
    grupos.get(c).pontos.push({ lat: f.geometry.coordinates[1], lng: f.geometry.coordinates[0] });
  }

  // Inclui depósito como ponto de partida e chegada, se configurado
  if (depositoCoord) {
    for (const grupo of grupos.values()) {
      grupo.pontos.unshift({ lat: depositoCoord.lat, lng: depositoCoord.lng });
      grupo.pontos.push({ lat: depositoCoord.lat, lng: depositoCoord.lng });
    }
  }

  const promessas = [];
  for (const [carro, grupo] of grupos.entries()) {
    if (grupo.pontos.length < 2) continue;
    promessas.push(
      fetch(URL_ROTA, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ pontos: grupo.pontos, carro }),
      })
      .then(r => r.json())
      .then(data => {
        if (!data.success) return;
        const latLngs = data.geometry.coordinates.map(([lng, lat]) => [lat, lng]);
        L.polyline(latLngs, {
          color: grupo.cor,
          weight: 4,
          opacity: 0.8,
        }).addTo(rotasLayer);
      })
      .catch(() => {
        // Rota falhou para este carro — desenha linha direta entre os pontos
        const latLngs = grupo.pontos.map(p => [p.lat, p.lng]);
        L.polyline(latLngs, { color: grupo.cor, weight: 3, opacity: 0.5, dashArray: '6, 6' }).addTo(rotasLayer);
      })
    );
  }

  await Promise.all(promessas);
  btnLimparRotas.classList.remove('d-none');
  AppLoader.hide();
}

// ─── Painel lateral: editar carro ────────────────────────────────────────────

function abrirPainelCarro(movId, carroAtual, popup) {
  painelTitulo.textContent = `Editar carro — mov. #${movId}`;
  painelCorpo.replaceChildren();

  const labelEl = document.createElement('label');
  labelEl.className = 'form-label';
  labelEl.textContent = 'Número do carro';
  labelEl.htmlFor = 'painel-carro-input';

  const inputEl = document.createElement('input');
  inputEl.type = 'number';
  inputEl.id = 'painel-carro-input';
  inputEl.className = 'form-control mb-2';
  inputEl.min = '1';
  inputEl.value = carroAtual ?? '';

  const btnSalvar = document.createElement('button');
  btnSalvar.className = 'btn btn-success btn-sm w-100';
  btnSalvar.innerHTML = '<i class="bi bi-check"></i> Salvar';

  btnSalvar.addEventListener('click', async () => {
    const novoCarro = inputEl.value.trim();
    btnSalvar.disabled = true;
    btnSalvar.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    AppLoader.show();

    try {
      const movFeat = geojsonData?.features.find(f => String(f.properties.mov_id) === String(movId));
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
        btnSalvar.innerHTML = '⚠️ Conflito — recarregue';
        return;
      }
      if (data.success) {
        // Atualiza no estado local
        if (movFeat) {
          const carroNum = novoCarro !== '' ? parseInt(novoCarro, 10) : null;
          const corNova = _corCarro(carroNum);
          movFeat.properties.carro = carroNum;
          movFeat.properties.cor = corNova;
          movFeat.properties.updated_at = data.updated_at ?? updatedAt;

          // Atualiza ícone do marcador
          const marker = marcadores[movId];
          if (marker) marker.setIcon(criarIcone(corNova, carroNum));

          // Fecha popup e painel
          popup?.close?.();
        }
        renderizarLegenda(geojsonData);
        fecharPainel();
      } else {
        btnSalvar.innerHTML = '❌ Erro';
      }
    } catch {
      btnSalvar.innerHTML = '❌ Erro';
    } finally {
      AppLoader.hide();
      setTimeout(() => { btnSalvar.disabled = false; btnSalvar.innerHTML = '<i class="bi bi-check"></i> Salvar'; }, 2000);
    }
  });

  painelCorpo.appendChild(labelEl);
  painelCorpo.appendChild(inputEl);
  painelCorpo.appendChild(btnSalvar);
  painel.classList.remove('d-none');
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

function fecharPainel() {
  painel.classList.add('d-none');
  painelCorpo.replaceChildren();
}

// ─── Eventos ─────────────────────────────────────────────────────────────────

document.getElementById('form-filtro-mapa').addEventListener('submit', e => {
  e.preventDefault();
  const data = document.getElementById('mapa-filtro-data').value;
  if (data) carregarPontos(data);
});

btnMostrarRotas?.addEventListener('click', tracarRotas);

btnLimparRotas?.addEventListener('click', () => {
  rotasLayer.clearLayers();
  btnLimparRotas.classList.add('d-none');
});

document.getElementById('mapa-painel-fechar')?.addEventListener('click', fecharPainel);

// Carrega automaticamente se veio com data da tela anterior
if (DATA_INICIAL) {
  carregarPontos(DATA_INICIAL);
}
