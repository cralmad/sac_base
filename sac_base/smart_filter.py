"""
sac_base/smart_filter.py — Filtro Avançado (Smart Filter) — Backend

Utilitário reutilizável que espelha a lógica de static/js/smart_filter.js.

Tipos:
  Número : "1,3,5-10,11"          → lista de inteiros expandida
  Texto  : '"txt1","*parte*"'     → lista de dicts com tipo e valor
  Select : lista de strings já parseada pelo frontend
"""

import re
from django.db.models import Q


def parse_smart_number(value: str) -> list:
    """
    Parseia filtro numérico: "1,3,5-10,11" → [1, 3, 5, 6, 7, 8, 9, 10, 11]
    Limita expansão de intervalos a 10.000 elementos por segurança.
    """
    if not value or not value.strip():
        return []
    result: set = set()
    for part in value.split(','):
        t = part.strip()
        if not t:
            continue
        m = re.match(r'^(\d+)-(\d+)$', t)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b and (b - a) <= 10_000:
                result.update(range(a, b + 1))
        else:
            try:
                result.add(int(t))
            except ValueError:
                pass
    return sorted(result)


def parse_smart_text(value: str) -> list:
    """
    Parseia filtro de texto: 'REF001,*LEROY*' ou (legado) '"REF001","*LEROY*"' ->
    [{'type': 'exact', 'value': 'REF001'}, {'type': 'contains', 'value': 'LEROY'}]
    Separa por virgula; aspas ao redor do termo sao opcionais e ignoradas.
    """
    if not value or not value.strip():
        return []
    terms = []
    for part in value.split(','):
        # Remove aspas opcionais ao redor do termo (suporte legado)
        raw = re.sub(r'^"(.*)"$', r'\1', part.strip())
        if not raw:
            continue
        start = raw.startswith('*')
        end   = raw.endswith('*')
        if start and end:
            terms.append({'type': 'contains',   'value': raw[1:-1]})
        elif start:
            terms.append({'type': 'endswith',   'value': raw[1:]})
        elif end:
            terms.append({'type': 'startswith', 'value': raw[:-1]})
        else:
            terms.append({'type': 'exact',      'value': raw})
    return terms


def apply_smart_number_filter(qs, field: str, value: str):
    """Aplica filtro numérico ao queryset. Sem valor, retorna qs sem alteração."""
    ids = parse_smart_number(value)
    if ids:
        qs = qs.filter(**{f'{field}__in': ids})
    return qs


def apply_smart_text_filter(qs, field: str, value: str):
    """
    Aplica filtro de texto ao queryset.
    Os termos são combinados com OR; sem valor, retorna qs sem alteração.
    """
    terms = parse_smart_text(value)
    if not terms:
        return qs
    q = Q()
    for term in terms:
        t, v = term['type'], term['value']
        if t == 'exact':
            q |= Q(**{field: v})
        elif t == 'contains':
            q |= Q(**{f'{field}__icontains': v})
        elif t == 'startswith':
            q |= Q(**{f'{field}__istartswith': v})
        elif t == 'endswith':
            q |= Q(**{f'{field}__iendswith': v})
    return qs.filter(q)
