// mapa_publico.js â€” Mapa pÃºblico por carro (sem autenticaÃ§Ã£o de utilizador)
// O mapa Ã© apenas visualizaÃ§Ã£o. EdiÃ§Ã£o restrita ao campo perÃ­odo, por seleÃ§Ã£o.

(function () {
    'use strict';

    const root = document.getElementById('mapa-publico-root');
    if (!root) return;

    const URL_PONTOS  = root.dataset.urlPontos;
    const URL_PERIODO = root.dataset.urlPeriodo;

    const avisoEl      = document.getElementById('mapa-aviso');
    const avisoTextoEl = document.getElementById('mapa-aviso-texto');
    const vazioEl      = document.getElementById('mapa-status-vazio');
    const mapaEl       = document.getElementById('mapa-leaflet');
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
    let marcadores   = {};
    let dadosLinhas  = [];        // cache da lista completa
    let selecionados = new Set(); // Set de mov_id (number)
    let gravando     = false;

    // â”€â”€â”€ UtilitÃ¡rios â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
            attribution: 'Â© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors Â© <a href="https://carto.com/attributions">CARTO</a>',
            maxZoom: 19,
        }).addTo(mapaLeaflet);
    }

    function criarIcone(cor, carro) {
        const corEsc = String(cor).replace(/[^#a-zA-Z0-9]/g, '');
        const carroN = carro != null ? Number(carro) : '?';
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="38" viewBox="0 0 28 38">
          <path d="M14 0C6.3 0 0 6.3 0 14c0 9.6 14 24 14 24s14-14.4 14-24C28 6.3 21.7 0 14 0z"
                fill="${corEsc}" stroke="#fff" stroke-width="2"/>
          <text x="14" y="18" text-anchor="middle" dominant-baseline="middle"
                font-family="Arial,sans-serif" font-size="10" font-weight="bold"
                fill="#fff">${carroN}</text>
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
        vol.textContent = `Vol: ${p.volume ?? 'â€”'}`;
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
                icon: criarIcone(p.cor, root.dataset.carro),
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
        if (periodo === 'MANHA') return 'ManhÃ£';
        if (periodo === 'TARDE') return 'Tarde';
        return 'â€”';
    }

    function focarMarcador(movId) {
        const marker = marcadores[movId];
        if (!marker) return;
        mapaEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // Pequeno atraso para o scroll completar antes de abrir o popup
        setTimeout(() => {
            mapaLeaflet.setView(marker.getLatLng(), Math.max(mapaLeaflet.getZoom(), 15));
            marker.openPopup();
        }, 300);
    }

    function renderizarLista(linhas) {
        dadosLinhas = linhas;
        selecionados.clear();
        listaTbody.replaceChildren();

        linhas.forEach(linha => {
            const tr = document.createElement('tr');
            tr.dataset.movId = linha.mov_id;

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

            // Coluna Referência (clicável → foca no mapa)
            const tdRef = document.createElement('td');
            const btnRef = document.createElement('button');
            btnRef.type = 'button';
            btnRef.className = 'btn btn-link btn-sm p-0 fw-semibold text-decoration-none';
            btnRef.textContent = linha.referencia ?? '';
            btnRef.title = 'Ver no mapa';
            btnRef.addEventListener('click', () => focarMarcador(linha.mov_id));
            tdRef.appendChild(btnRef);
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
                // Actualiza cÃ©lulas de perÃ­odo na tabela
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

                // Desmarca seleÃ§Ã£o
                selecionados.clear();
                listaTbody.querySelectorAll('.chk-linha').forEach(c => {
                    c.checked = false;
                    c.closest('tr')?.classList.remove('selecionado');
                });
                chkTodos.checked       = false;
                chkTodos.indeterminate = false;

                setListaStatus(
                    `PerÃ­odo atualizado para ${periodo === 'MANHA' ? 'ManhÃ£' : 'Tarde'} em ${result.atualizados} pedido(s).`,
                    'success'
                );
            } else {
                setListaStatus(result.mensagem || 'Erro ao atualizar perÃ­odo.', 'danger');
            }
        } catch {
            setListaStatus('Erro de comunicaÃ§Ã£o.', 'danger');
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
        mostrarAviso('Carregandoâ€¦');
        mapaEl.classList.add('d-none');
        vazioEl.classList.add('d-none');
        listaWrapper.classList.add('d-none');
        actionBar.classList.add('d-none');

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

            // Mapa
            if (result.total_mapa > 0) {
                inicializarMapa();
                mapaEl.classList.remove('d-none');
                mapaLeaflet.invalidateSize();
                renderizarMarcadores(result.geojson);
            }

            if (result.sem_coord > 0) {
                mostrarAviso(
                    result.total_mapa === 0
                        ? `${result.total} pedido(s) encontrado(s), mas nenhum possui coordenadas para exibiÃ§Ã£o no mapa.`
                        : `${result.sem_coord} pedido(s) sem coordenadas nÃ£o aparecem no mapa.`,
                    'warning'
                );
            }

            // Lista
            renderizarLista(result.linhas || []);

        } catch {
            mostrarAviso('Erro de comunicaÃ§Ã£o ao carregar os dados.', 'danger');
        }
    }

    // â”€â”€â”€ InicializaÃ§Ã£o â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    carregarPontos();
}());
