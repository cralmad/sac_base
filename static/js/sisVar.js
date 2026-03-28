
/**
 * Retorna uma cópia segura do estado completo para leitura externa.
 * Útil para acessar chaves dinâmicas como 'opcoes' injetadas pelo backend.
 */
export function getSisVar() {
  return structuredClone(_rawState);
}