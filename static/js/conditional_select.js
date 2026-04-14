/**
 * Inicializa selects hierárquicos genéricos
 *
 * @param {HTMLElement} root
 * @param {Object<string, Object>} hierarchies
 */
export function initHierarchicalSelects(root, hierarchies) {
    const selects = [...root.querySelectorAll('select')];

    // Inicializa roots
    selects
        .filter(s => s.hasAttribute('data-hierarchy-root'))
        .forEach(select => {
            const key = select.dataset.hierarchy;
            const hierarchy = hierarchies[key];
            if (!hierarchy) return;

            populateRoot(select, hierarchy);
        });

    // Registra dependências
    selects
        .filter(s => s.dataset.selectDepends)
        .forEach(target => {
            const deps = target.dataset.selectDepends.split(',');
            const hierarchyKey = target.dataset.hierarchy;
            const hierarchy = hierarchies[hierarchyKey];

            if (!hierarchy) return;

            deps.forEach(depName => {
                const source = root.querySelector(`[name="${depName}"]`);
                if (!source) return;

                source.addEventListener('change', () => {
                    updateSelect(root, target, deps, hierarchy);
                });
            });
        });
}

function populateRoot(select, hierarchy) {
    resetSelect(select);

    Object.entries(hierarchy).forEach(([value, node]) => {
        select.appendChild(option(value, node.label));
    });

    select.disabled = false;
}

function updateSelect(root, target, deps, hierarchy) {
    resetSelect(target);

    const path = deps.map(name => {
        const el = root.querySelector(`[name="${name}"]`);
        return el?.value;
    });

    if (path.some(v => !v)) return;

    const node = resolvePath(hierarchy, path);
    if (!node?.children) return;

    Object.entries(node.children).forEach(([value, child]) => {
        target.appendChild(option(value, child.label));
    });

    target.disabled = false;
}

function resolvePath(hierarchy, path) {
    return path.reduce((node, key, index) => {
        if (index === 0) return hierarchy[key];
        return node?.children?.[key];
    }, null);
}

function resetSelect(select) {
    select.innerHTML = '';
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = 'Selecione';
    select.appendChild(defaultOption);
    select.disabled = true;
    select.dispatchEvent(new Event('change', { bubbles: true }));
}

function option(value, label) {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = label;
    return opt;
}
