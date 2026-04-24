/**
 * static/js/smart_filter.js — Filtro Avançado (Smart Filter)
 *
 * Utilitário reutilizável para filtros com sintaxe avançada.
 *
 * Tipos suportados:
 *   Número : "1,3,5-10,11"          → lista de inteiros expandida
 *   Texto  : '"txt1","*parte*"'     → lista de termos com curingas
 *   Select : <select multiple>      → usar getMultiSelectValues()
 */

/**
 * Parseia filtro numérico: "1,3,5-10,11" → [1, 3, 5, 6, 7, 8, 9, 10, 11]
 * @param {string} str
 * @returns {number[]}
 */
export function parseSmartNumber(str) {
  if (!str || !str.trim()) return [];
  const result = new Set();
  for (const part of str.split(',')) {
    const t = part.trim();
    if (!t) continue;
    const rangeMatch = t.match(/^(\d+)-(\d+)$/);
    if (rangeMatch) {
      const a = parseInt(rangeMatch[1], 10);
      const b = parseInt(rangeMatch[2], 10);
      if (a <= b && (b - a) <= 10_000) {
        for (let i = a; i <= b; i++) result.add(i);
      }
    } else {
      const n = parseInt(t, 10);
      if (!isNaN(n)) result.add(n);
    }
  }
  return [...result].sort((a, b) => a - b);
}

/**
 * Parseia filtro de texto com curingas.
 * Separa por vírgula; aspas ao redor do termo são opcionais e ignoradas.
 * * no início/fim indica curinga.
 * Ex: REF001,*LEROY*,COMEÇA*,*TERMINA
 * Ex (com aspas, legado): "REF001","*LEROY*"
 * @param {string} str
 * @returns {{ type: 'exact'|'contains'|'startswith'|'endswith', value: string }[]}
 */
export function parseSmartText(str) {
  if (!str || !str.trim()) return [];
  const terms = [];
  for (const part of str.split(',')) {
    // Remove aspas opcionais ao redor do termo (suporte legado)
    const raw = part.trim().replace(/^"|"$/g, '');
    if (!raw) continue;
    const start = raw.startsWith('*');
    const end   = raw.endsWith('*');
    if (start && end) {
      terms.push({ type: 'contains',   value: raw.slice(1, -1) });
    } else if (start) {
      terms.push({ type: 'endswith',   value: raw.slice(1) });
    } else if (end) {
      terms.push({ type: 'startswith', value: raw.slice(0, -1) });
    } else {
      terms.push({ type: 'exact',      value: raw });
    }
  }
  return terms;
}

/**
 * Retorna os valores selecionados de um <select multiple>.
 * @param {HTMLSelectElement} selectEl
 * @returns {string[]}
 */
export function getMultiSelectValues(selectEl) {
  return Array.from(selectEl.selectedOptions).map(o => o.value).filter(Boolean);
}

/**
 * Valida a sintaxe de um filtro numérico.
 * @param {string} str
 * @returns {boolean}
 */
export function validateSmartNumber(str) {
  if (!str || !str.trim()) return true;
  return /^[\d\s,\-]+$/.test(str.trim());
}

/**
 * Valida a sintaxe de um filtro de texto.
 * Aceita qualquer string não vazia (aspas são opcionais).
 * @param {string} str
 * @returns {boolean}
 */
export function validateSmartText(str) {
  if (!str || !str.trim()) return true;
  // Termos separados por vírgula; basta ter ao menos um caractere não vazio
  return str.split(',').some(p => p.trim().replace(/^"|"$/g, '').length > 0);
}
