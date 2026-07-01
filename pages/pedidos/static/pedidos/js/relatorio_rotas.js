import { getCsrfToken, clearMessages, definirMensagem, getOptions, confirmar, getDataset } from '/static/js/sisVar.js';
import { AppLoader } from '/static/js/loader.js';
import { validateSmartNumber, getMultiSelectValues } from '/static/js/smart_filter.js';

const root       = document.getElementById('rr-root');
const URL_BUSCAR = root?.dataset?.urlBuscar ?? '';
const URL_LINK   = root?.dataset?.urlLink   ?? '';
const URL_IMPORTAR_ARTIGOS = root?.dataset?.urlImportarArtigos ?? '';
const URL_PRODUTO_CRITICO = root?.dataset?.urlProdutoCritico ?? '';
const URL_PEDIDOS = root?.dataset?.urlPedidos ?? '/app/logistica/pedidos/';

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
const arquivoArtigosEl = document.getElementById('rr-arquivo-artigos');
const btnConfirmarImportacao = document.getElementById('rr-btn-confirmar-importacao');
const importacaoStatusEl = document.getElementById('rr-importacao-status');
const modalImportarArtigosEl = document.getElementById('rr-modal-importar-artigos');
const modalImportarArtigos = modalImportarArtigosEl ? new bootstrap.Modal(modalImportarArtigosEl) : null;

let artigosPorIdVonzu = new Map();
let artigosPorReferencia = new Map();
let totalPedidosComArtigos = 0;
let totalArtigosImportados = 0;
let ultimosGrupos = [];
let ultimaDataFmt = '';
let ultimoAgrupamento = 'carro';
const codigosProdutosCriticos = new Set(
  (getDataset('produtos_criticos_codigos', []) || []).map(c => normalizarCodigoProduto(c)).filter(Boolean),
);

function normalizarCodigoProduto(codigo) {
  return String(codigo ?? '').trim();
}

function produtoEhCritico(codigo) {
  const cod = normalizarCodigoProduto(codigo);
  return Boolean(cod) && codigosProdutosCriticos.has(cod);
}

function linhaTemProdutoCritico(artigos) {
  return (artigos || []).some(artigo => produtoEhCritico(artigo?.cod_fornecedor));
}

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

function atualizarResumoImportacao() {
  if (!importacaoStatusEl) return;
  if (!totalPedidosComArtigos) {
    importacaoStatusEl.textContent = 'Nenhum artigo importado.';
    return;
  }
  importacaoStatusEl.textContent = `Artigos importados: ${totalPedidosComArtigos} pedido(s), ${totalArtigosImportados} item(ns).`;
}

function normalizarReferencia(valor) {
  return String(valor ?? '').trim();
}

const LEROY_MERLIN_SEARCH_URL = 'https://www.leroymerlin.pt/search';
const VONZU_EXPEDITIONS_URL = 'https://app.vonzu.es/user/expeditions';
const FEEDBACK_COPIA_MS = 1100;

function aplicarFeedbackCopia(el, tipo = 'ok') {
  if (!el) return;
  el.classList.remove('rr-copia-ok', 'rr-copia-erro');
  el.classList.add(tipo === 'erro' ? 'rr-copia-erro' : 'rr-copia-ok');
  window.setTimeout(() => {
    el.classList.remove('rr-copia-ok', 'rr-copia-erro');
  }, FEEDBACK_COPIA_MS);
}

function obterToggleDropdown(ev) {
  return ev?.currentTarget?.closest('.rr-acao-dropdown')?.querySelector('.rr-acao-toggle') ?? null;
}

function criarDropdownAcao(texto, opcoes) {
  const wrap = document.createElement('div');
  wrap.className = 'dropdown rr-acao-dropdown';

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'btn btn-link p-0 rr-acao-toggle dropdown-toggle';
  btn.setAttribute('data-bs-toggle', 'dropdown');
  btn.setAttribute('aria-expanded', 'false');
  btn.textContent = texto;

  const menu = document.createElement('ul');
  menu.className = 'dropdown-menu';

  (opcoes || []).forEach(opt => {
    const li = document.createElement('li');
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'dropdown-item';
    item.textContent = opt.label;
    if (opt.disabled) {
      item.classList.add('disabled');
      item.disabled = true;
    } else if (opt.href) {
      item.addEventListener('click', () => {
        window.open(opt.href, '_blank', 'noopener,noreferrer');
      });
    } else if (opt.onClick) {
      item.addEventListener('click', (ev) => opt.onClick(ev));
    }
    li.appendChild(item);
    menu.appendChild(li);
  });

  wrap.appendChild(btn);
  wrap.appendChild(menu);
  return wrap;
}

function opcoesReferenciaPedido(linha) {
  const opcoes = [];
  const texto = normalizarReferencia(linha?.pedido);
  if (texto) {
    opcoes.push({
      label: 'Copiar',
      onClick: (ev) => copiarReferenciaPedido(texto, obterToggleDropdown(ev)),
    });
  }
  const idVonzu = Number.parseInt(linha?.id_vonzu, 10);
  if (Number.isInteger(idVonzu) && idVonzu > 0) {
    opcoes.push({
      label: 'VONZU',
      href: `${VONZU_EXPEDITIONS_URL}/${idVonzu}`,
    });
  }
  const pedidoId = Number.parseInt(linha?.pedido_id, 10);
  if (Number.isInteger(pedidoId) && pedidoId > 0) {
    const base = URL_PEDIDOS.replace(/\/?$/, '/');
    opcoes.push({
      label: 'SACBASE',
      href: `${base}?visualizar=${pedidoId}`,
    });
  }
  return opcoes;
}

function anexarReferenciaPedido(container, linha) {
  const texto = linha.pedido ?? '';
  const opcoes = opcoesReferenciaPedido(linha);
  if (opcoes.length) {
    container.appendChild(criarDropdownAcao(texto || '—', opcoes));
    return;
  }
  const span = document.createElement('span');
  span.textContent = texto;
  container.appendChild(span);
}

function anexarCodigoProduto(container, artigo) {
  const cod = String(artigo?.cod_fornecedor ?? '').trim();
  if (!cod) {
    container.textContent = '';
    return;
  }
  const opcoes = [
    {
      label: 'LEROY',
      href: `${LEROY_MERLIN_SEARCH_URL}?q=${encodeURIComponent(cod)}`,
    },
    {
      label: 'CRÍTICO',
      onClick: () => confirmarCadastroProdutoCritico(cod, artigo?.descricao ?? ''),
    },
  ];
  container.appendChild(criarDropdownAcao(cod, opcoes));
}

function confirmarCadastroProdutoCritico(codigo, descricao) {
  const cod = String(codigo ?? '').trim();
  const desc = String(descricao ?? '').trim();
  confirmar({
    titulo: 'Cadastrar produto crítico',
    mensagem: `Deseja cadastrar o produto ${cod}${desc ? ` — ${desc}` : ''} na lista de críticos?`,
    onConfirmar: () => cadastrarProdutoCritico(cod, desc),
  });
}

async function cadastrarProdutoCritico(codigo, descricao) {
  clearMessages();
  if (!URL_PRODUTO_CRITICO) {
    definirMensagem('erro', 'URL de cadastro de produto crítico não configurada.', false);
    return;
  }
  AppLoader.show();
  try {
    const resp = await fetch(URL_PRODUTO_CRITICO, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ codigo, descricao }),
    });
    const json = await resp.json();
    if (!json.success) {
      const erros = json?.mensagens?.erro?.conteudo;
      definirMensagem(
        'erro',
        Array.isArray(erros) && erros.length ? erros[0] : (json.mensagem || 'Erro ao cadastrar produto crítico.'),
        false,
      );
      return;
    }
    const sucesso = json?.mensagens?.sucesso?.conteudo;
    definirMensagem(
      'sucesso',
      Array.isArray(sucesso) && sucesso.length ? sucesso[0] : 'Produto crítico cadastrado.',
      false,
    );
    const codCadastrado = normalizarCodigoProduto(json.produto_critico_codigo || codigo);
    if (codCadastrado) {
      codigosProdutosCriticos.add(codCadastrado);
    }
    if (ultimosGrupos.length) {
      renderizarGrupos(ultimosGrupos, ultimaDataFmt, ultimoAgrupamento);
    }
  } catch {
    definirMensagem('erro', 'Erro de comunicação ao cadastrar produto crítico.', false);
  } finally {
    AppLoader.hide();
  }
}

function obterArtigosDaLinha(linha) {
  const idVonzu = Number.parseInt(linha?.id_vonzu, 10);
  if (Number.isInteger(idVonzu) && artigosPorIdVonzu.has(idVonzu)) {
    return artigosPorIdVonzu.get(idVonzu);
  }
  const referencia = normalizarReferencia(linha?.pedido);
  if (referencia && artigosPorReferencia.has(referencia)) {
    return artigosPorReferencia.get(referencia);
  }
  return null;
}

function pesoParaNumero(valor) {
  const texto = String(valor ?? '').trim().replace(',', '.');
  if (!texto) return 0;
  const numero = Number.parseFloat(texto);
  return Number.isFinite(numero) ? numero : 0;
}

function formatarPeso(total) {
  return total.toLocaleString('pt-PT', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

function volumePedidoParaNumero(valorVolumes) {
  const texto = String(valorVolumes ?? '').trim();
  if (!texto) return 0;
  const partes = texto.split('/');
  const volumePedido = partes.length >= 2 ? partes[1] : partes[0];
  const numero = Number.parseInt(String(volumePedido).trim(), 10);
  return Number.isFinite(numero) ? numero : 0;
}

function agruparLinhasSemCarroPorFaixa(linhas) {
  const mapa = new Map();
  (linhas || []).forEach(linha => {
    const zona = String(linha?.zona_entrega || '').trim() || 'Sem zona de entrega';
    const faixa = String(linha?.faixa_entrega || '').trim() || 'Sem faixa de entrega';
    const chave = `${zona}|||${faixa}`;
    if (!mapa.has(chave)) mapa.set(chave, { zona, faixa, itens: [] });
    mapa.get(chave).itens.push(linha);
  });
  return Array.from(mapa.values())
    .sort((a, b) => {
      if (a.zona === 'Sem zona de entrega') return 1;
      if (b.zona === 'Sem zona de entrega') return -1;
      const cmpZona = a.zona.localeCompare(b.zona, 'pt');
      if (cmpZona !== 0) return cmpZona;
      return a.faixa.localeCompare(b.faixa, 'pt');
    })
    .map(grupo => ({ zona: grupo.zona, faixa: grupo.faixa, itens: grupo.itens }));
}

function resumoZonasSemCarro(linhas) {
  const mapa = new Map();
  (linhas || []).forEach(linha => {
    const zona = String(linha?.zona_entrega || '').trim() || 'Sem zona';
    const atual = mapa.get(zona) || { pedidos: 0, peso: 0, volume: 0 };
    atual.pedidos += 1;
    atual.peso += pesoParaNumero(linha?.peso);
    atual.volume += volumePedidoParaNumero(linha?.volumes);
    mapa.set(zona, atual);
  });
  if (!mapa.size) return '0 zonas';
  const partes = Array.from(mapa.entries())
    .sort((a, b) => b[1].pedidos - a[1].pedidos || a[0].localeCompare(b[0], 'pt'))
    .map(([zona, dados]) => `${zona} (${dados.pedidos} • ${formatarPeso(dados.peso)} kg • ${dados.volume} vol)`);
  return `${mapa.size} zona(s): ${partes.join(', ')}`;
}

function aplicarDadosImportados(pedidos) {
  artigosPorIdVonzu = new Map();
  artigosPorReferencia = new Map();
  totalPedidosComArtigos = 0;
  totalArtigosImportados = 0;

  (pedidos || []).forEach(pedido => {
    const artigos = Array.isArray(pedido?.artigos) ? pedido.artigos : [];
    if (!artigos.length) return;
    totalPedidosComArtigos += 1;
    totalArtigosImportados += artigos.length;
    const idVonzu = Number.parseInt(pedido.id_vonzu, 10);
    if (Number.isInteger(idVonzu)) {
      artigosPorIdVonzu.set(idVonzu, artigos);
    }
    const referencia = normalizarReferencia(pedido.referencia);
    if (referencia) {
      artigosPorReferencia.set(referencia, artigos);
    }
  });

  atualizarResumoImportacao();
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

    const pesoTotalGrupo = (grupo.linhas || []).reduce((acc, linha) => acc + pesoParaNumero(linha.peso), 0);
    const volumeTotalGrupo = (grupo.linhas || []).reduce((acc, linha) => acc + volumePedidoParaNumero(linha.volumes), 0);

    const spanTotalPedidos = document.createElement('span');
    spanTotalPedidos.className = 'rr-badge rr-badge-pedidos ms-auto';
    spanTotalPedidos.textContent = `${grupo.total} pedido(s)`;

    const spanTotaisExtras = document.createElement('span');
    spanTotaisExtras.className = 'rr-badge rr-badge-totais';
    const resumoExtras = `${formatarPeso(pesoTotalGrupo)} kg • ${volumeTotalGrupo} vol`;
    if (agrupamento === 'carro' && grupo.carro === '\u2014') {
      spanTotaisExtras.textContent = `${resumoExtras} • ${resumoZonasSemCarro(grupo.linhas || [])}`;
    } else {
      spanTotaisExtras.textContent = resumoExtras;
    }

    header.appendChild(spanLabel);
    header.appendChild(spanData);
    header.appendChild(spanTotalPedidos);
    header.appendChild(spanTotaisExtras);

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

    const renderizarLinhaPedido = (linha) => {
      const tr = document.createElement('tr');
      if (linha.nao_segue_para_entrega ?? !linha.segue_para_entrega) tr.classList.add('rr-nao-segue');
      const artigosLinha = obterArtigosDaLinha(linha);

      const campos = [
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

      const tdRef = document.createElement('td');
      if (artigosLinha?.length) {
        const refWrap = document.createElement('div');
        refWrap.className = 'rr-ref-wrap';

        const btnExpandir = document.createElement('button');
        btnExpandir.type = 'button';
        btnExpandir.className = 'btn btn-sm btn-link p-0 rr-artigos-toggle';
        if (linhaTemProdutoCritico(artigosLinha)) {
          btnExpandir.classList.add('rr-artigos-toggle-critico');
          btnExpandir.title = `Produtos críticos (${artigosLinha.length} item(ns))`;
        } else {
          btnExpandir.title = `Mostrar produtos (${artigosLinha.length})`;
        }
        btnExpandir.innerHTML = '<i class="bi bi-chevron-right"></i>';
        refWrap.appendChild(btnExpandir);

        anexarReferenciaPedido(refWrap, linha);

        if (linha.tem_devolucao) {
          refWrap.classList.add('rr-ref-dev');
          const devBadge = document.createElement('span');
          devBadge.className = 'rr-dev-ref';
          devBadge.textContent = '(Dev)';
          refWrap.appendChild(devBadge);
        }

        tdRef.appendChild(refWrap);
      } else if (linha.tem_devolucao) {
        const refWrap = document.createElement('div');
        refWrap.className = 'rr-ref-wrap rr-ref-dev';
        anexarReferenciaPedido(refWrap, linha);
        const devBadge = document.createElement('span');
        devBadge.className = 'rr-dev-ref';
        devBadge.textContent = '(Dev)';
        refWrap.appendChild(devBadge);
        tdRef.appendChild(refWrap);
      } else {
        anexarReferenciaPedido(tdRef, linha);
      }
      tr.appendChild(tdRef);

      campos.forEach(({ val, cls, bold }) => {
        const td = document.createElement('td');
        td.textContent = val ?? '';
        if (cls) td.className = cls;
        if (bold) td.style.fontWeight = 'bold';
        tr.appendChild(td);
      });

      tbody.appendChild(tr);

      if (artigosLinha?.length) {
        const trArtigos = document.createElement('tr');
        trArtigos.className = 'd-none';
        const tdArtigos = document.createElement('td');
        tdArtigos.colSpan = 11;

        const artigosWrapper = document.createElement('div');
        artigosWrapper.className = 'rr-artigos';
        const tableArtigos = document.createElement('table');
        tableArtigos.className = 'rr-artigos-table';
        const headArtigos = document.createElement('thead');
        const trHeadArtigos = document.createElement('tr');
        ['Produto', 'Quantidade', 'Código'].forEach(titulo => {
          const th = document.createElement('th');
          th.textContent = titulo;
          trHeadArtigos.appendChild(th);
        });
        headArtigos.appendChild(trHeadArtigos);
        tableArtigos.appendChild(headArtigos);

        const bodyArtigos = document.createElement('tbody');
        artigosLinha.forEach(artigo => {
          const trItem = document.createElement('tr');
          if (produtoEhCritico(artigo?.cod_fornecedor)) {
            trItem.classList.add('rr-artigo-critico');
          }
          const tdDescricao = document.createElement('td');
          tdDescricao.textContent = artigo.descricao ?? '';
          const tdQuantidade = document.createElement('td');
          tdQuantidade.textContent = String(artigo.quantidade ?? '');
          const tdCodigo = document.createElement('td');
          tdCodigo.className = 'rr-codigo-cell';
          anexarCodigoProduto(tdCodigo, artigo);
          trItem.appendChild(tdDescricao);
          trItem.appendChild(tdQuantidade);
          trItem.appendChild(tdCodigo);
          bodyArtigos.appendChild(trItem);
        });
        tableArtigos.appendChild(bodyArtigos);

        artigosWrapper.appendChild(tableArtigos);
        tdArtigos.appendChild(artigosWrapper);
        trArtigos.appendChild(tdArtigos);
        tbody.appendChild(trArtigos);

        const btnExpandir = tr.querySelector('.rr-artigos-toggle');
        const icone = btnExpandir?.querySelector('i');
        btnExpandir?.addEventListener('click', () => {
          const aberto = !trArtigos.classList.contains('d-none');
          trArtigos.classList.toggle('d-none', aberto);
          if (icone) {
            icone.className = aberto ? 'bi bi-chevron-right' : 'bi bi-chevron-down';
          }
        });
      }
    };

    if (agrupamento === 'carro' && grupo.carro === '\u2014') {
      const subgrupos = agruparLinhasSemCarroPorFaixa(grupo.linhas || []);
      subgrupos.forEach(subgrupo => {
        const trSubgrupo = document.createElement('tr');
        trSubgrupo.className = 'rr-subgrupo-faixa';
        const tdSubgrupo = document.createElement('td');
        tdSubgrupo.colSpan = 11;
        const pesoSubgrupo = subgrupo.itens.reduce((acc, linha) => acc + pesoParaNumero(linha.peso), 0);
        const volumeSubgrupo = subgrupo.itens.reduce((acc, linha) => acc + volumePedidoParaNumero(linha.volumes), 0);
        tdSubgrupo.textContent = `${subgrupo.zona} • ${subgrupo.faixa} • ${subgrupo.itens.length} pedido(s) • ${formatarPeso(pesoSubgrupo)} kg • ${volumeSubgrupo} vol`;
        trSubgrupo.appendChild(tdSubgrupo);
        tbody.appendChild(trSubgrupo);
        subgrupo.itens.forEach(renderizarLinhaPedido);
      });
    } else {
      (grupo.linhas || []).forEach(renderizarLinhaPedido);
    }

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

async function importarArtigos() {
  clearMessages();
  if (!URL_IMPORTAR_ARTIGOS) {
    definirMensagem('erro', 'URL de importação não configurada.', false);
    return;
  }
  const arquivo = arquivoArtigosEl?.files?.[0];
  if (!arquivo) {
    definirMensagem('erro', 'Selecione um arquivo CSV para importar.', false);
    return;
  }
  if (!arquivo.name.toLowerCase().endsWith('.csv')) {
    definirMensagem('erro', 'O arquivo deve ter extensão .csv.', false);
    return;
  }

  btnConfirmarImportacao.disabled = true;
  AppLoader.show();
  try {
    const formData = new FormData();
    formData.append('arquivo_csv', arquivo);

    const resp = await fetch(URL_IMPORTAR_ARTIGOS, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() },
      body: formData,
    });
    const json = await resp.json();
    if (!json.success) {
      const erros = json?.mensagens?.erro?.conteudo;
      definirMensagem('erro', Array.isArray(erros) && erros.length ? erros[0] : (json.mensagem || 'Erro ao importar artigos.'), false);
      return;
    }
    aplicarDadosImportados(json.pedidos || []);
    definirMensagem('sucesso', 'Artigos importados com sucesso.', false);
    if (ultimosGrupos.length) {
      renderizarGrupos(ultimosGrupos, ultimaDataFmt, ultimoAgrupamento);
    }
    arquivoArtigosEl.value = '';
    modalImportarArtigos?.hide();
  } catch {
    definirMensagem('erro', 'Erro de comunicação ao importar artigos.', false);
  } finally {
    btnConfirmarImportacao.disabled = false;
    AppLoader.hide();
  }
}

// ─── Copiar referência individual ───────────────────────────────────────────
async function copiarReferenciaPedido(referencia, elFeedback = null) {
  const texto = normalizarReferencia(referencia);
  if (!texto) {
    aplicarFeedbackCopia(elFeedback, 'erro');
    return;
  }
  try {
    await navigator.clipboard.writeText(texto);
    aplicarFeedbackCopia(elFeedback, 'ok');
  } catch {
    aplicarFeedbackCopia(elFeedback, 'erro');
  }
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
    ultimosGrupos = json.grupos || [];
    ultimaDataFmt = json.data_fmt || '';
    ultimoAgrupamento = json.agrupamento || 'carro';
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
btnConfirmarImportacao?.addEventListener('click', importarArtigos);
preencherMotoristas();
atualizarResumoImportacao();
