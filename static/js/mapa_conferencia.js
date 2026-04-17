import { getCsrfToken, hasScreenPermission } from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';

// ─── Constantes e estado ─────────────────────────────────────────────────────

const root = document.getElementById('mapa-root');
const URL_PONTOS       = root?.dataset?.urlPontos ?? '';
const URL_SALVAR_COORD = root?.dataset?.urlSalvarCoord ?? '';
const URL_ROTA         = root?.dataset?.urlRota ?? '';
const URL_SALVAR       = root?.dataset?.urlSalvar ?? '';
const DATA_INICIAL     = root?.dataset?.dataInicial ?? '';

const podeEditar     = hasScreenPermission('mapa', 'editar');
const podeEditarCarro = hasScreenPermission('mapa', 'editar_carro');

const btnMostrarRotas = document.getElementById('btn-mostrar-rotas');
const btnLimparRotas  = document.getElementById('btn-limpar-rotas');
const legendaWrapper  = document.getElementById('mapa-legenda');
const legendaItens    = document.getElementById('mapa-legenda-itens');
const avisoGeocoding  = document.getElementById('mapa-aviso-geocoding');
const avisoTexto      = document.getElementById('mapa-aviso-texto');
const painel          = document.getElementById('mapa-painel');
const painelTitulo    = document.getElementById('mapa-painel-titulo');
const painelCorpo     = document.getElementById('mapa-painel-corpo');

let mapaLeaflet = null;
let marcadores  = {};       // mov_id → marker
let rotasLayer  = null;     // LayerGroup de polylines
let geojsonData = null;     // última FeatureCollection carregada

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

function conteudoPopup(p) {
  const conf = (p.volume != null && p.volume === p.volume_conf) ? '✅' : '❌';
  return `
    <div class="mapa-popup">
      <strong>${_esc(p.referencia)}</strong><br>
      <span class="text-muted small">${_esc(p.tipo)}</span><br>
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
      draggable: podeEditar,
      title: p.referencia,
    });

    marker.bindPopup(conteudoPopup(p), { maxWidth: 280 });
    marker.feature = feat;

    if (podeEditar) {
      marker.on('dragend', async (e) => {
        const { lat: novoLat, lng: novoLng } = e.target.getLatLng();
        await salvarCoordenadas(p.pedido_id, novoLat, novoLng);
        // Atualiza no geojson em memória
        feat.geometry.coordinates = [novoLng, novoLat];
      });
    }

    marker.addTo(mapaLeaflet);
    marcadores[p.mov_id] = marker;
  }

  // Evento delegado nos popups (alterar carro)
  mapaLeaflet.on('popupopen', (e) => {
    const popup = e.popup.getElement();
    const btn = popup?.querySelector('.btn-popup-editar-carro');
    if (!btn) return;
    btn.addEventListener('click', () => abrirPainelCarro(btn.dataset.movId, btn.dataset.carro, e.popup));
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

    geojsonData = result.geojson;
    renderizarMarcadores(geojsonData);
    renderizarLegenda(geojsonData);

    // Ajusta o mapa aos marcadores
    const coords = geojsonData.features.map(f => [f.geometry.coordinates[1], f.geometry.coordinates[0]]);
    if (coords.length > 0) mapaLeaflet.fitBounds(L.latLngBounds(coords), { padding: [40, 40] });

    const totalSemCoord = result.sem_coord ?? 0;
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

async function salvarCoordenadas(pedidoId, lat, lng) {
  try {
    await fetch(URL_SALVAR_COORD, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ pedido_id: pedidoId, lat, lng }),
    });
  } catch {
    // Falha silenciosa — coordenada atualizada localmente de qualquer forma
  }
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
