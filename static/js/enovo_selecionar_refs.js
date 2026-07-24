/**
 * Seleção de envios no eNovoTMS (console / bookmarklet) por Referência ou TRK.
 * Formato de lista: "ref1, ref2, …" (Rotas por Carro) ou uma por linha.
 */

/**
 * @param {string} raw
 * @returns {string[]}
 */
export function parseReferenciasTexto(raw) {
  const seen = new Set();
  const out = [];
  String(raw || "")
    .split(/[\n\r,;]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .forEach((t) => {
      if (t === "…" || t === "...") return;
      if (!seen.has(t)) {
        seen.add(t);
        out.push(t);
      }
    });
  return out;
}

/**
 * Extrai referências no mesmo critério de Rotas por Carro (campo pedido).
 * @param {{ linhas?: Array<{ pedido?: unknown }> }} grupo
 * @returns {string[]}
 */
export function referenciasDoGrupoRotas(grupo) {
  const seen = new Set();
  const out = [];
  for (const l of grupo?.linhas || []) {
    const p = l?.pedido;
    if (p == null) continue;
    const s = String(p).trim();
    if (!s || seen.has(s)) continue;
    seen.add(s);
    out.push(s);
  }
  return out;
}

/**
 * Script pronto para colar no DevTools Console na aba autenticada do eNovoTMS.
 * @param {string[]} ids
 * @returns {string}
 */
export function buildScriptConsoleSelecionarRefs(ids) {
  const lista = Array.isArray(ids) ? ids.map((x) => String(x).trim()).filter(Boolean) : [];
  const payload = JSON.stringify(lista);
  return (
    "(function(){\n" +
    "  var IDS = " +
    payload +
    ";\n" +
    "  if (!IDS.length) { alert('SisVar: lista vazia (Referencia ou TRK).'); return; }\n" +
    "  function norm(v) {\n" +
    "    return String(v == null ? '' : v).replace(/<[^>]*>/g, ' ').replace(/\\s+/g, ' ').trim();\n" +
    "  }\n" +
    "  function idsQueBatamNoTexto(txt) {\n" +
    "    txt = norm(txt);\n" +
    "    var hits = [];\n" +
    "    if (!txt) return hits;\n" +
    "    for (var i = 0; i < IDS.length; i++) {\n" +
    "      var id = norm(IDS[i]);\n" +
    "      if (!id) continue;\n" +
    "      if (txt === id || txt.indexOf(id) !== -1) hits.push(IDS[i]);\n" +
    "    }\n" +
    "    return hits;\n" +
    "  }\n" +
    "  function idsQueBatamNaLinha(d) {\n" +
    "    var fields = [d.reference, d.reference2, d.reference3, d.tracking_code, d.provider_tracking_code, d.id];\n" +
    "    var seen = {};\n" +
    "    var hits = [];\n" +
    "    for (var f = 0; f < fields.length; f++) {\n" +
    "      var part = idsQueBatamNoTexto(fields[f]);\n" +
    "      for (var i = 0; i < part.length; i++) {\n" +
    "        var key = norm(part[i]);\n" +
    "        if (seen[key]) continue;\n" +
    "        seen[key] = true;\n" +
    "        hits.push(part[i]);\n" +
    "      }\n" +
    "    }\n" +
    "    return hits;\n" +
    "  }\n" +
    "  function registarMatches(hits, matchedMap) {\n" +
    "    for (var i = 0; i < hits.length; i++) matchedMap[norm(hits[i])] = true;\n" +
    "  }\n" +
    "  function markNode(node, st) {\n" +
    "    if (!node) return;\n" +
    "    var cb = node.querySelector && node.querySelector('input[type=checkbox]');\n" +
    "    if (!cb || cb.disabled) return;\n" +
    "    st.found++;\n" +
    "    if (cb.checked) { st.already++; return; }\n" +
    "    cb.click();\n" +
    "    if (!cb.checked) {\n" +
    "      cb.checked = true;\n" +
    "      try { cb.dispatchEvent(new Event('change', { bubbles: true })); } catch (e) {}\n" +
    "    }\n" +
    "    st.marked++;\n" +
    "  }\n" +
    "  var matchedMap = {};\n" +
    "  var st = { found: 0, marked: 0, already: 0, mode: 'dom', sem_match: [] };\n" +
    "  try {\n" +
    "    if (window.jQuery && jQuery.fn && jQuery.fn.dataTable) {\n" +
    "      var api = jQuery.fn.dataTable.tables({ api: true });\n" +
    "      if (api && api.tables().count() > 0) {\n" +
    "        st.mode = 'datatables';\n" +
    "        api.rows({ page: 'current' }).every(function () {\n" +
    "          var d = this.data() || {};\n" +
    "          var hits = idsQueBatamNaLinha(d);\n" +
    "          if (!hits.length) return;\n" +
    "          registarMatches(hits, matchedMap);\n" +
    "          markNode(this.node(), st);\n" +
    "          try { if (this.select) this.select(); } catch (e2) {}\n" +
    "        });\n" +
    "      }\n" +
    "    }\n" +
    "  } catch (e3) { st.mode = 'dom-fallback'; }\n" +
    "  if (st.found === 0) {\n" +
    "    st.mode = 'dom';\n" +
    "    var rows = document.querySelectorAll('table.dataTable tbody tr, table tbody tr');\n" +
    "    for (var r = 0; r < rows.length; r++) {\n" +
    "      var t = rows[r].innerText || rows[r].textContent || '';\n" +
    "      var hitsDom = idsQueBatamNoTexto(t);\n" +
    "      if (!hitsDom.length) continue;\n" +
    "      registarMatches(hitsDom, matchedMap);\n" +
    "      markNode(rows[r], st);\n" +
    "    }\n" +
    "  }\n" +
    "  var semMatch = [];\n" +
    "  for (var i = 0; i < IDS.length; i++) {\n" +
    "    if (!matchedMap[norm(IDS[i])]) semMatch.push(IDS[i]);\n" +
    "  }\n" +
    "  st.sem_match = semMatch;\n" +
    "  console.log(st);\n" +
    "  if (semMatch.length) console.warn('SisVar sem match (' + semMatch.length + '):', semMatch);\n" +
    "  else console.log('SisVar: todos os codigos deram match.');\n" +
    "  var msgSem = semMatch.length\n" +
    "    ? ('\\n\\nSem match (' + semMatch.length + '):\\n- ' + semMatch.join('\\n- '))\n" +
    "    : '\\n\\nSem match: nenhum.';\n" +
    "  alert('SisVar (' + st.mode + ')\\nItens: ' + IDS.length + '\\nMatch: ' + st.found +\n" +
    "    '\\nMarcados: ' + st.marked + '\\nJa estavam: ' + st.already +\n" +
    "    msgSem +\n" +
    "    '\\n\\nNota: so linhas na pagina atual do DataTables. Detalhe em console.warn.');\n" +
    "})();\n"
  );
}

/**
 * @param {string[]} ids
 * @returns {string} href javascript:...
 */
export function buildBookmarkletSelecionarRefs(ids) {
  // Compacta o script (uma linha) para o limite de URL de favoritos
  const script = buildScriptConsoleSelecionarRefs(ids).replace(/\n\s*/g, "");
  return "javascript:" + encodeURIComponent(script);
}
