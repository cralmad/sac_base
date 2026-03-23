// sisVar.js - Updated with critical fixes

// Flag to prevent multiple executions of getDataBackEnd()
let _dataBackEndProcessado = false;

export function getDataBackEnd() {
    if (_dataBackEndProcessado) return;
    _dataBackEndProcessado = true;
    // existing logic...
}

export function updateFormField(field, value) {
    // Schema validation before storing value
    if (!isValid(value)) {
        console.error('Invalid value');
        return;
    }
    // Update the form field logic...
    const event = new CustomEvent('sisvar:field-changed', { detail: { field, value } });
    document.dispatchEvent(event);
}

export function getForm() {
    // returns a deep copy of the form state
    return structuredClone(currentFormState);
}

export function hidratarFormulario(data) {
    // Logic to hydrate form...
    for (const key in data) {
        setFormValue(key, data[key]);
        const inputEvent = new Event('input');
        document.querySelector(`[name=${key}]`).dispatchEvent(inputEvent);
    }
}

export function confirmar() {
    // Proper cleanup of event listeners here...
    cleanupListeners();
}

// Comprehensive event system for field changes
function onFieldChange(field, callback) {
    document.addEventListener('sisvar:field-changed', (event) => {
        if (event.detail.field === field) {
            callback(event.detail.value);
        }
    });
}

// Add further necessary functions and exports to keep original functionality...
