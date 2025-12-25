/**
 * Inicializa e aplica regras de formatação e máscaras
 * em inputs com a classe 'smart-input'.
 *
 * @param {Function} onChange Callback opcional (input, value)
 */
export function initSmartInputs(onChange) {
    document.querySelectorAll('.smart-input').forEach(input => {

        // === Configurações principais ===
        const textCase = input.dataset.textcase;
        const allow = input.dataset.allow;
        const deny  = input.dataset.deny;

        const mask = input.dataset.mask;
        const maskValueMode = input.dataset.maskValue || 'formatted'; // formatted | raw

        const maxLength = input.maxLength > 0 ? input.maxLength : null;

        // === Regex pré-compilada ===
        const allowRegex = allow ? new RegExp(`[^${allow}]`, 'g') : null;
        const denyRegex  = deny  ? new RegExp(`[${deny}]`, 'g') : null;

        input.addEventListener('input', () => {
            const originalValue = input.value;
            let value = originalValue;

            // === Regras base (core) ===

            // Espaços iniciais
            if (value.length > 0) {
                value = value.replace(/^\s+/, '');
            }

            // Regras de caracteres
            if (allowRegex) {
                value = value.replace(allowRegex, '');
            }
            if (denyRegex) {
                value = value.replace(denyRegex, '');
            }

            // Capitalização
            switch (textCase) {
                case 'upper':
                    value = value.toUpperCase();
                    break;
                case 'lower':
                    value = value.toLowerCase();
                    break;
            }

            // Limite de caracteres (autoridade máxima)
            if (maxLength && value.length > maxLength) {
                value = value.slice(0, maxLength);
            }

            // === Máscara (opcional e não intrusiva) ===
            let formattedValue = value;
            let rawValue = value;

            if (mask) {
                const result = tryApplyMask(value, mask);

                if (result) {
                    formattedValue = result.formatted;
                    rawValue = result.raw;
                }
            }

            // Atualiza DOM apenas se mudou
            if (formattedValue !== originalValue) {
                input.value = formattedValue;
            }

            // === Notifica a aplicação ===
            if (typeof onChange === 'function') {
                const emittedValue =
                    mask && maskValueMode === 'raw'
                        ? rawValue
                        : formattedValue;

                onChange(input, emittedValue);
            }
        });
    });
}

/**
 * Tenta aplicar uma máscara sem interferir nas regras principais.
 * Retorna null se a máscara não for aplicável.
 */
function tryApplyMask(value, mask) {
    switch (mask) {
        case 'pt-phone':
            return maskPtPhone(value);

        case 'pt-postcode':
            return maskPtPostcode(value);

        default:
            return null;
    }
}

/**
 * Máscara telefone PT: 000 000 000
 * Aplica apenas se o valor contiver apenas dígitos e espaços
 */
function maskPtPhone(value) {
    if (!/^[\d\s]*$/.test(value)) return null;

    const digits = value.replace(/\s+/g, '');

    // Aplica progressivamente, sem cortar
    const parts = [];
    if (digits.length > 0) parts.push(digits.slice(0, 3));
    if (digits.length > 3) parts.push(digits.slice(3, 6));
    if (digits.length > 6) parts.push(digits.slice(6));

    return {
        raw: digits,
        formatted: parts.join(' ')
    };
}

/**
 * Máscara código postal PT: 0000-000
 * Aplica apenas se o valor contiver apenas dígitos ou hífen
 */
function maskPtPostcode(value) {
    if (!/^[\d-]*$/.test(value)) return null;

    const digits = value.replace(/-/g, '');

    if (digits.length <= 4) {
        return {
            raw: digits,
            formatted: digits
        };
    }

    return {
        raw: digits,
        formatted: `${digits.slice(0, 4)}-${digits.slice(4)}`
    };
}
