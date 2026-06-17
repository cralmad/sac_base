// mapa_rotas_core.js — utilitários compartilhados de rotas (Leaflet + OSRM)
// Estado (rota/ordem) fica no chamador; este módulo é stateless.

export function formatarDistanciaKm(metros) {
  const m = typeof metros === 'number' ? metros : parseFloat(String(metros));
  if (!Number.isFinite(m)) return '—';
  const km = m / 1000;
  return km.toLocaleString('pt-PT', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' km';
}

export function formatarDuracao(segundos) {
  const s = typeof segundos === 'number' ? segundos : parseFloat(String(segundos));
  if (!Number.isFinite(s) || s <= 0) return '—';
  const totalMin = Math.round(s / 60);
  const h = Math.floor(totalMin / 60);
  const min = totalMin % 60;
  if (h <= 0) return `~${min}min`;
  if (min <= 0) return `~${h}h`;
  return `~${h}h ${min}min`;
}

function _featureLatLng(feat) {
  const [lng, lat] = feat.geometry.coordinates;
  return { lat: Number(lat), lng: Number(lng) };
}

function _parseMovId(x) {
  if (x == null) return null;
  const n = typeof x === 'number' ? x : parseInt(String(x), 10);
  return Number.isFinite(n) ? n : null;
}

/**
 * Monta waypoints para cálculo da rota.
 * - Se `deposito` existir, é sempre o primeiro ponto (origem).
 * - NÃO adiciona retorno ao depósito.
 * - Se `ordemMovIds` existir, respeita essa ordem para as features elegíveis.
 * - Se `somenteSegueEntrega` for true, exclui `segue_para_entrega === false`.
 */
export function montarWaypoints(features, { deposito = null, ordemMovIds = null, somenteSegueEntrega = true } = {}) {
  const feats = Array.isArray(features) ? [...features] : [];

  const elegiveis = feats.filter(f => {
    const p = f?.properties || {};
    if (somenteSegueEntrega && p.segue_para_entrega === false) return false;
    // exige coords válidas
    const ll = _featureLatLng(f);
    return Number.isFinite(ll.lat) && Number.isFinite(ll.lng);
  });

  let ordered = elegiveis;
  if (Array.isArray(ordemMovIds) && ordemMovIds.length > 0) {
    const byId = new Map();
    for (const f of elegiveis) {
      const id = _parseMovId(f?.properties?.mov_id);
      if (id != null) byId.set(id, f);
    }
    const result = [];
    for (const rawId of ordemMovIds) {
      const id = _parseMovId(rawId);
      const f = id != null ? byId.get(id) : null;
      if (f) result.push(f);
    }
    // acrescenta os que não estavam na ordem manual (ex. novos pontos após recarregar)
    for (const f of elegiveis) {
      const id = _parseMovId(f?.properties?.mov_id);
      if (id != null && !ordemMovIds.some(x => _parseMovId(x) === id)) result.push(f);
    }
    ordered = result;
  } else {
    ordered = elegiveis.sort((a, b) => String(a?.properties?.codpost || '').localeCompare(String(b?.properties?.codpost || '')));
  }

  const pontos = [];
  if (deposito && deposito.lat != null && deposito.lng != null) {
    pontos.push({ lat: Number(deposito.lat), lng: Number(deposito.lng), __tipo: 'deposito' });
  }
  for (const f of ordered) {
    const ll = _featureLatLng(f);
    pontos.push({ ...ll, mov_id: _parseMovId(f?.properties?.mov_id), __tipo: 'parada' });
  }
  return pontos;
}

export async function chamarRota(url, pontos, csrfToken = null, carro = '') {
  const headers = { 'Content-Type': 'application/json' };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;
  const resp = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({ pontos, carro }),
  });
  const data = await resp.json().catch(() => ({}));
  return { ok: resp.ok, status: resp.status, data };
}

export function desenharPolyline(rotasLayer, geometry, { color = '#198754', weight = 4, opacity = 0.85, dashArray = null } = {}) {
  if (!rotasLayer || !geometry) return null;
  rotasLayer.clearLayers();
  const coords = geometry.coordinates || [];
  const latLngs = coords.map(([lng, lat]) => [lat, lng]);
  const opts = { color, weight, opacity };
  if (dashArray) opts.dashArray = dashArray;
  const poly = L.polyline(latLngs, opts);
  poly.addTo(rotasLayer);
  return poly;
}

export function renderizarDeposito(map, depositoCoord, marcadorRef) {
  if (!map) return null;
  if (marcadorRef?.current) {
    try { marcadorRef.current.remove(); } catch { /* noop */ }
    marcadorRef.current = null;
  }
  if (!depositoCoord || depositoCoord.lat == null || depositoCoord.lng == null) return null;

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
      <circle cx="16" cy="16" r="15" fill="#1a1a2e" stroke="#fff" stroke-width="2"/>
      <text x="16" y="21" text-anchor="middle" font-size="16" fill="#fff">🏭</text>
    </svg>`;
  const icon = L.divIcon({ html: svg, iconSize: [32, 32], iconAnchor: [16, 16], popupAnchor: [0, -18], className: '' });
  const marker = L.marker([Number(depositoCoord.lat), Number(depositoCoord.lng)], {
    icon,
    title: 'Depósito',
    zIndexOffset: 1000,
  });
  marker.bindPopup('<strong>Depósito</strong><br>Ponto de partida das rotas.');
  marker.addTo(map);
  if (marcadorRef) marcadorRef.current = marker;
  return marker;
}

export function renderizarPainelResumo(el, { carro = null, distancia_metros = null, duracao_segundos = null, paradas = 0, fallback = false, deposito = false, aviso = '' } = {}) {
  if (!el) return;
  el.classList.remove('d-none');
  const carroTxt = carro != null && carro !== '' ? `Carro ${carro}` : 'Rota';
  const distTxt = formatarDistanciaKm(distancia_metros);
  const durTxt = formatarDuracao(duracao_segundos);
  const depTxt = deposito ? 'Depósito como origem' : 'Sem depósito';
  const falTxt = fallback ? ' (linha estimada)' : '';
  el.innerHTML = '';

  const wrap = document.createElement('div');
  wrap.className = 'mapa-rotas-resumo';

  const left = document.createElement('div');
  left.className = 'mapa-rotas-resumo-main';
  left.textContent = `${carroTxt} — ${distTxt}${falTxt} — ${paradas} parada(s) — ${durTxt}`;

  const right = document.createElement('div');
  right.className = 'mapa-rotas-resumo-meta text-muted small';
  right.textContent = depTxt;

  wrap.appendChild(left);
  wrap.appendChild(right);

  if (aviso) {
    const av = document.createElement('div');
    av.className = 'mapa-rotas-resumo-aviso small text-warning';
    av.textContent = aviso;
    wrap.appendChild(av);
  }

  el.appendChild(wrap);
}

/**
 * Drag-and-drop nativo para reordenar `<tr>` dentro de um `<tbody>`.
 * Requer que as linhas reordenáveis tenham `data-mov-id` e `draggable=true`.
 */
export function initReordenacaoLista(tbody, { selectorLinha = 'tr', canDrag = () => true, onOrdemAlterada = () => {} } = {}) {
  if (!tbody) return { destroy: () => {} };

  let dragging = null;

  function linhas() {
    return Array.from(tbody.querySelectorAll(selectorLinha));
  }

  function currentOrder() {
    return linhas()
      .filter(tr => canDrag(tr))
      .map(tr => _parseMovId(tr.dataset.movId))
      .filter(x => x != null);
  }

  function setDraggables() {
    for (const tr of linhas()) {
      const ok = canDrag(tr);
      tr.draggable = ok;
      tr.classList.toggle('mapa-linha-reordenavel', ok);
    }
  }

  function onDragStart(ev) {
    const tr = ev.target?.closest(selectorLinha);
    if (!tr || !canDrag(tr)) {
      ev.preventDefault();
      return;
    }
    dragging = tr;
    tr.classList.add('mapa-linha-arrastando');
    ev.dataTransfer.effectAllowed = 'move';
    try { ev.dataTransfer.setData('text/plain', tr.dataset.movId || ''); } catch { /* noop */ }
  }

  function onDragOver(ev) {
    if (!dragging) return;
    ev.preventDefault();
    ev.dataTransfer.dropEffect = 'move';
    const over = ev.target?.closest(selectorLinha);
    if (!over || over === dragging || !tbody.contains(over)) return;
    if (!canDrag(over)) return;
    const rect = over.getBoundingClientRect();
    const after = (ev.clientY - rect.top) > (rect.height / 2);
    if (after) over.after(dragging);
    else over.before(dragging);
  }

  function onDragEnd() {
    if (!dragging) return;
    dragging.classList.remove('mapa-linha-arrastando');
    dragging = null;
    onOrdemAlterada(currentOrder());
  }

  setDraggables();
  tbody.addEventListener('dragstart', onDragStart);
  tbody.addEventListener('dragover', onDragOver);
  tbody.addEventListener('dragend', onDragEnd);
  tbody.addEventListener('drop', (ev) => ev.preventDefault());

  return {
    refresh: setDraggables,
    destroy: () => {
      tbody.removeEventListener('dragstart', onDragStart);
      tbody.removeEventListener('dragover', onDragOver);
      tbody.removeEventListener('dragend', onDragEnd);
    },
  };
}

