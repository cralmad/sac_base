// mapa_publico.js — Mapa público por carro (sem login)
// Rota e distância são temporárias (exibição), com reordenação manual na lista.

import {
    chamarRota,
    desenharPolyline,
    initReordenacaoLista,
    montarWaypoints,
    renderizarDeposito,
    renderizarPainelResumo,
} from '/static/js/mapa_rotas_core.js';

const root = document.getElementById('mapa-publico-root');
if (!root) {
    // Nada a fazer (página de erro)
    // eslint-disable-next-line no-undef
    throw new Error('mapa-publico-root não encontrado');
}

const URL_PONTOS  = root.dataset.urlPontos;
const URL_ROTA    = root.dataset.urlRota;
const URL_PERIODO = root.dataset.urlPeriodo;

const avisoEl      = document.getElementById('mapa-aviso');
const avisoTextoEl = document.getElementById('mapa-aviso-texto');
const vazioEl      = document.getElementById('mapa-status-vazio');
const mapaEl       = document.getElementById('mapa-leaflet');
const btnGerarRota = document.getElementById('btn-mostrar-rotas');
const btnLimparRota = document.getElementById('btn-limpar-rotas');
const resumoRotasWrapper = document.getElementById('mapa-rotas-resumo-wrapper');

const listaWrapper = document.getElementById('lista-wrapper');
const listaBadge   = document.getElementById('lista-badge');
const listaTbody   = document.getElementById('lista-tbody');
const chkTodos     = document.getElementById('chk-todos');
const actionBar    = document.getElementById('lista-action-bar');
const selCount     = document.getElementById('lista-sel-count');
const listaStatus  = document.getElementById('lista-status');
const btnSelManha  = document.getElementById('btn-sel-manha');
const btnSelTarde  = document.getElementById('btn-sel-tarde');

let mapaLeaflet  = null;
let rotasLayer   = null;
let marcadores   = {};
let dadosLinhas  = [];        // cache da lista completa
let selecionados = new Set(); // Set de mov_id (number)
let gravando     = false;
let geojsonData  = null;
let depositoCoord = null;
const ordemParadas = []; // mov_ids na ordem manual (somente elegíveis)
let reordenacaoHandle = null;
const marcadorDepositoRef = { current: null };
let avisoOrdemPendente = false;

function mostrarAviso(texto, tipo = 'info') {
    avisoEl.className = `alert alert-${tipo} py-2`;
    avisoTextoEl.textContent = texto;
    avisoEl.classList.remove('d-none');
}

function ocultarAviso() {
    avisoEl.classList.add('d-none');
}

function setListaStatus(texto, tipo = 'muted') {
    listaStatus.textContent = texto;
    listaStatus.className = `small text-${tipo} mt-1`;
}

    // â”€â”€â”€ Mapa (apenas visualizaÃ§Ã£o) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function inicializarMapa() {
    if (mapaLeaflet) return;
    mapaLeaflet = L.map('mapa-leaflet').setView([39.5, -8.0], 7);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
        maxZoom: 19,
    }).addTo(mapaLeaflet);
    rotasLayer = L.layerGroup().addTo(mapaLeaflet);
}

function criarIcone(cor, carro, segueParaEntrega = true) {
    const corEsc = String(cor).replace(/[^#a-zA-Z0-9]/g, '');
    const carroN = carro != null ? Number(carro) : '?';
    const badge = segueParaEntrega ? '' : `
      <circle cx="22" cy="6" r="6" fill="#dc3545" stroke="#fff" stroke-width="1.5"/>
      <text x="22" y="10" text-anchor="middle" font-family="Arial,sans-serif" font-size="9" font-weight="bold" fill="#fff">!</text>`;
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="38" viewBox="0 0 28 38">
      <path d="M14 0C6.3 0 0 6.3 0 14c0 9.6 14 24 14 24s14-14.4 14-24C28 6.3 21.7 0 14 0z"
            fill="${corEsc}" stroke="#fff" stroke-width="2"/>
      <text x="14" y="18" text-anchor="middle" dominant-baseline="middle"
            font-family="Arial,sans-serif" font-size="10" font-weight="bold"
            fill="#fff">${carroN}</text>
      ${badge}
    </svg>`;
    return L.divIcon({ html: svg, iconSize: [28, 38], iconAnchor: [14, 38], popupAnchor: [0, -40], className: '' });
}

function conteudoPopup(p) {
    const div = document.createElement('div');
    div.className = 'mapa-popup';

    const ref = document.createElement('strong');
    ref.textContent = p.referencia;
    div.appendChild(ref);

    const tipo = document.createElement('span');
    tipo.className = 'text-muted small d-block';
    tipo.textContent = p.tipo;
    div.appendChild(tipo);

    const end = document.createElement('div');
    end.textContent = p.endereco;
    div.appendChild(end);

    const codCidade = document.createElement('em');
    codCidade.textContent = `${p.codpost} ${p.cidade}`;
    div.appendChild(codCidade);

    const hr = document.createElement('hr');
    hr.className = 'my-1';
    div.appendChild(hr);

    const vol = document.createElement('div');
    vol.textContent = `Vol: ${p.volume ?? '—'}`;
    div.appendChild(vol);

    if (p.obs_rota) {
        const obsRota = document.createElement('div');
        obsRota.className = 'text-primary small mt-1';
        obsRota.textContent = `Obs rota: ${p.obs_rota}`;
        div.appendChild(obsRota);
    }

    return div;
}

function renderizarMarcadores(geojson) {
    for (const m of Object.values(marcadores)) m.remove();
    marcadores = {};

    for (const feat of geojson.features) {
        const p = feat.properties;
        const [lng, lat] = feat.geometry.coordinates;

        const marker = L.marker([lat, lng], {
            icon: criarIcone(p.cor, root.dataset.carro, p.segue_para_entrega !== false),
            draggable: false,
            title: p.referencia,
        });
        marker.bindPopup(conteudoPopup(p), { maxWidth: 260 });
        marker.addTo(mapaLeaflet);
        marcadores[p.mov_id] = marker;
    }

    if (geojson.features.length > 0) {
        const coords = geojson.features.map(f => [f.geometry.coordinates[1], f.geometry.coordinates[0]]);
        mapaLeaflet.fitBounds(L.latLngBounds(coords), { padding: [40, 40] });
    }
}

    // â”€â”€â”€ Lista de pedidos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function labelPeriodo(periodo) {
    if (periodo === 'MANHA') return 'Manhã';
    if (periodo === 'TARDE') return 'Tarde';
    return '—';
}

function focarMarcador(movId) {
    const marker = marcadores[movId];
    if (!marker) return;
    mapaEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setTimeout(() => {
        mapaLeaflet.setView(marker.getLatLng(), Math.max(mapaLeaflet.getZoom(), 15));
        marker.openPopup();
    }, 300);
}

function renderizarLista(linhas) {
    dadosLinhas = linhas;
    selecionados.clear();
    listaTbody.replaceChildren();

    const movIdsComCoord = new Set((geojsonData?.features || []).map(f => Number(f.properties?.mov_id)));

    linhas.forEach(linha => {
        const tr = document.createElement('tr');
        tr.dataset.movId = linha.mov_id;
        tr.dataset.segue = linha.segue_para_entrega === false ? '0' : '1';
        tr.dataset.temCoord = movIdsComCoord.has(Number(linha.mov_id)) ? '1' : '0';
        if (linha.segue_para_entrega === false) tr.classList.add('mapa-linha-nao-segue');

        // Checkbox
        const tdChk = document.createElement('td');
        const chk = document.createElement('input');
        chk.type = 'checkbox';
        chk.className = 'form-check-input chk-linha';
        chk.dataset.movId = linha.mov_id;
        chk.setAttribute('aria-label', `Selecionar pedido ${linha.referencia}`);
        chk.addEventListener('change', () => onCheckboxLinha(chk, tr));
        tdChk.appendChild(chk);
        tr.appendChild(tdChk);

        // Handle de reordenação
        const tdOrd = document.createElement('td');
        tdOrd.className = 'mapa-ordem-td';
        const handle = document.createElement('span');
        handle.className = 'mapa-ordem-handle';
        handle.title = 'Arraste para reordenar a rota';
        handle.textContent = '⋮⋮';
        tdOrd.appendChild(handle);
        tr.appendChild(tdOrd);

        // Referência (clicável → foca no mapa)
        const tdRef = document.createElement('td');
        const btnRef = document.createElement('button');
        btnRef.type = 'button';
        btnRef.className = 'btn btn-link btn-sm p-0 fw-semibold text-decoration-none';
        btnRef.textContent = linha.referencia ?? '';
        btnRef.title = 'Ver no mapa';
        btnRef.addEventListener('click', () => focarMarcador(linha.mov_id));
        tdRef.appendChild(btnRef);
        if (linha.segue_para_entrega === false) {
            const badge = document.createElement('span');
            badge.className = 'badge text-bg-danger ms-2';
            badge.textContent = 'Nao segue';
            tdRef.appendChild(badge);
        }
        tr.appendChild(tdRef);

            // Colunas de dados
        const cols = [
            { val: linha.tipo, cls: linha.tipo === 'R' ? 'tipo-R' : 'tipo-E' },
            { val: linha.nome_dest },
            { val: linha.fones },
            { val: linha.endereco_dest },
            { val: linha.cidade_dest },
            { val: linha.codpost_dest },
            { val: linha.volume != null ? String(linha.volume) : '—' },
            { val: linha.peso != null ? String(linha.peso) : '—' },
            { val: linha.obs_rota, cls: 'text-secondary fst-italic small' },
        ];

        cols.forEach(({ val, cls }) => {
            const td = document.createElement('td');
            td.textContent = val ?? '';
            if (cls) td.className = cls;
            tr.appendChild(td);
        });

            // Coluna perÃ­odo
        const tdPeriodo = document.createElement('td');
        tdPeriodo.className = 'periodo-cell' + (linha.periodo ? ` periodo-${linha.periodo}` : '');
        tdPeriodo.textContent = labelPeriodo(linha.periodo);
        tr.appendChild(tdPeriodo);

        listaTbody.appendChild(tr);
    });

    listaBadge.textContent = `${linhas.length} pedido(s)`;
    listaWrapper.classList.remove('d-none');
    actionBar.classList.remove('d-none');
    atualizarBotoesAcao();
    inicializarReordenacaoLista();
}

function _inicializarOrdemParadas() {
    ordemParadas.splice(0, ordemParadas.length);
    if (!listaTbody) return;
    for (const tr of listaTbody.querySelectorAll('tr')) {
        if ((tr.dataset.segue || '1') !== '1') continue;
        if ((tr.dataset.temCoord || '0') !== '1') continue;
        const id = parseInt(tr.dataset.movId, 10);
        if (Number.isFinite(id)) ordemParadas.push(id);
    }
}

function inicializarReordenacaoLista() {
    if (!listaTbody) return;
    if (!reordenacaoHandle) {
        reordenacaoHandle = initReordenacaoLista(listaTbody, {
            selectorLinha: 'tr',
            canDrag: (tr) => {
                if (tr.classList.contains('d-none')) return false;
                if ((tr.dataset.segue || '1') !== '1') return false;
                if ((tr.dataset.temCoord || '0') !== '1') return false;
                return true;
            },
            onOrdemAlterada: (movIds) => {
                ordemParadas.splice(0, ordemParadas.length, ...movIds);
                avisoOrdemPendente = true;
                if (!btnLimparRota.classList.contains('d-none')) {
                    renderizarPainelResumo(resumoRotasWrapper, {
                        carro: root.dataset.carro,
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

async function gerarRota() {
    if (!geojsonData) return;
    const feats = geojsonData.features || [];
    const pontos = montarWaypoints(feats, { deposito: depositoCoord, ordemMovIds: ordemParadas, somenteSegueEntrega: true });
    const pontosApi = pontos.map(p => ({ lat: p.lat, lng: p.lng }));

    if (pontosApi.length < 2) {
        renderizarPainelResumo(resumoRotasWrapper, {
            carro: root.dataset.carro,
            distancia_metros: null,
            duracao_segundos: null,
            paradas: Math.max(0, pontosApi.length - (depositoCoord ? 1 : 0)),
            fallback: false,
            deposito: !!depositoCoord,
            aviso: 'Sem paradas elegíveis para calcular rota.',
        });
        return;
    }

    btnGerarRota.disabled = true;
    try {
        const { ok, data } = await chamarRota(URL_ROTA, pontosApi, null, root.dataset.carro || '');
        if (!ok || !data?.success) {
            renderizarPainelResumo(resumoRotasWrapper, {
                carro: root.dataset.carro,
                distancia_metros: null,
                duracao_segundos: null,
                paradas: Math.max(0, pontosApi.length - (depositoCoord ? 1 : 0)),
                fallback: false,
                deposito: !!depositoCoord,
                aviso: data?.mensagem || 'Falha ao calcular rota.',
            });
            return;
        }
        desenharPolyline(rotasLayer, data.geometry, { color: '#198754', weight: 4, opacity: 0.85 });
        btnLimparRota.classList.remove('d-none');
        renderizarPainelResumo(resumoRotasWrapper, {
            carro: root.dataset.carro,
            distancia_metros: data.distancia_metros,
            duracao_segundos: data.duracao_segundos,
            paradas: Math.max(0, pontosApi.length - (depositoCoord ? 1 : 0)),
            fallback: !!data.fallback,
            deposito: !!depositoCoord,
            aviso: avisoOrdemPendente ? 'Ordem alterada — gere a rota novamente.' : '',
        });
        avisoOrdemPendente = false;
    } finally {
        btnGerarRota.disabled = false;
    }
}

    // â”€â”€â”€ SeleÃ§Ã£o â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function onCheckboxLinha(chk, tr) {
    const id = Number(chk.dataset.movId);
    if (chk.checked) {
        selecionados.add(id);
        tr.classList.add('selecionado');
    } else {
        selecionados.delete(id);
        tr.classList.remove('selecionado');
    }
    sincronizarChkTodos();
    atualizarBotoesAcao();
}

function sincronizarChkTodos() {
    const total = dadosLinhas.length;
    const sel   = selecionados.size;
    chkTodos.checked       = sel > 0 && sel === total;
    chkTodos.indeterminate = sel > 0 && sel < total;
}

chkTodos.addEventListener('change', () => {
    const marcar = chkTodos.checked;
    selecionados.clear();
    listaTbody.querySelectorAll('tr').forEach(tr => {
        const chk = tr.querySelector('.chk-linha');
        if (!chk) return;
        const id = Number(chk.dataset.movId);
        chk.checked = marcar;
        if (marcar) {
            selecionados.add(id);
            tr.classList.add('selecionado');
        } else {
            tr.classList.remove('selecionado');
        }
    });
    atualizarBotoesAcao();
});

function atualizarBotoesAcao() {
    const n = selecionados.size;
    const temSel = n > 0;
    selCount.textContent = temSel ? `${n} selecionado(s)` : 'Nenhum selecionado';
    btnSelManha.disabled = !temSel;
    btnSelTarde.disabled = !temSel;
}

    // â”€â”€â”€ Definir perÃ­odo nos selecionados â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async function definirPeriodoSelecionados(periodo) {
        if (gravando || selecionados.size === 0) return;
        gravando = true;

        const btnAtivo      = periodo === 'MANHA' ? btnSelManha : btnSelTarde;
        const textoOriginal = btnAtivo.innerHTML;
        btnAtivo.disabled  = true;
        btnAtivo.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>';
        btnSelManha.disabled = true;
        btnSelTarde.disabled = true;
        setListaStatus('', 'muted');

        const movIds = [...selecionados];

        try {
            const resp = await fetch(URL_PERIODO, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ periodo, mov_ids: movIds }),
            });
            const result = await resp.json();

            if (result.success) {
                // Actualiza células de período na tabela
                movIds.forEach(id => {
                    const tr = listaTbody.querySelector(`tr[data-mov-id="${id}"]`);
                    if (!tr) return;
                    const td = tr.querySelector('.periodo-cell');
                    if (!td) return;
                    td.className = `periodo-cell periodo-${periodo}`;
                    td.textContent = labelPeriodo(periodo);
                    const linha = dadosLinhas.find(l => l.mov_id === id);
                    if (linha) linha.periodo = periodo;
                });

                // Desmarca seleção
                selecionados.clear();
                listaTbody.querySelectorAll('.chk-linha').forEach(c => {
                    c.checked = false;
                    c.closest('tr')?.classList.remove('selecionado');
                });
                chkTodos.checked       = false;
                chkTodos.indeterminate = false;

                setListaStatus(
                    `Período atualizado para ${periodo === 'MANHA' ? 'Manhã' : 'Tarde'} em ${result.atualizados} pedido(s).`,
                    'success'
                );
            } else {
                setListaStatus(result.mensagem || 'Erro ao atualizar período.', 'danger');
            }
        } catch {
            setListaStatus('Erro de comunicação.', 'danger');
        } finally {
            btnAtivo.innerHTML = textoOriginal;
            gravando = false;
            atualizarBotoesAcao();
        }
    }

btnSelManha.addEventListener('click', () => definirPeriodoSelecionados('MANHA'));
btnSelTarde.addEventListener('click', () => definirPeriodoSelecionados('TARDE'));

    // â”€â”€â”€ Carregar dados â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async function carregarPontos() {
    mostrarAviso('Carregando…');
    mapaEl.classList.add('d-none');
    vazioEl.classList.add('d-none');
    listaWrapper.classList.add('d-none');
    actionBar.classList.add('d-none');
    btnGerarRota.disabled = true;
    btnLimparRota.classList.add('d-none');
    resumoRotasWrapper.classList.add('d-none');
    rotasLayer?.clearLayers();
    avisoOrdemPendente = false;

    try {
        const resp = await fetch(URL_PONTOS, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
        const result = await resp.json();

        if (!result.success) {
            mostrarAviso(result.mensagem || 'Erro ao carregar dados.', 'danger');
            return;
        }

        ocultarAviso();

        if (result.total === 0) {
            vazioEl.classList.remove('d-none');
            return;
        }

        geojsonData = result.geojson;
        depositoCoord = result.deposito ?? null;

        if (result.total_mapa > 0) {
            inicializarMapa();
            mapaEl.classList.remove('d-none');
            mapaLeaflet.invalidateSize();
            renderizarMarcadores(result.geojson);
            renderizarDeposito(mapaLeaflet, depositoCoord, marcadorDepositoRef);
        }

        if (result.sem_coord > 0) {
            mostrarAviso(
                result.total_mapa === 0
                    ? `${result.total} pedido(s) encontrado(s), mas nenhum possui coordenadas para exibição no mapa.`
                    : `${result.sem_coord} pedido(s) sem coordenadas não aparecem no mapa.`,
                'warning',
            );
        }

        renderizarLista(result.linhas || []);
        _inicializarOrdemParadas();

        btnGerarRota.disabled = (geojsonData.features || []).length === 0;
    } catch {
        mostrarAviso('Erro de comunicação ao carregar os dados.', 'danger');
    }
}

btnGerarRota?.addEventListener('click', gerarRota);
btnLimparRota?.addEventListener('click', () => {
    rotasLayer?.clearLayers();
    btnLimparRota.classList.add('d-none');
    resumoRotasWrapper.classList.add('d-none');
});

carregarPontos();
