// Responsável por gerenciar o loader global da aplicação
export const AppLoader = {
    element: null,
    hideTimeout: null, // Novo: controlar timeout

    init() {
        this.element = document.getElementById('global-loader');
        this.attachListeners();
    },

    show() {
        if (this.element) {
            this.element.classList.remove('d-none');
            
            // Limpa timeout anterior se existir
            if (this.hideTimeout) {
                clearTimeout(this.hideTimeout);
            }
            
            // Auto-hide após 10 segundos (segurança contra travamentos)
            this.hideTimeout = setTimeout(() => {
                this.hide();
                console.warn("Loader auto-hidden after timeout");
            }, 10000);
        }
    },

    hide() {
        if (this.element) {
            this.element.classList.add('d-none');
            
            // Limpa o timeout se existir
            if (this.hideTimeout) {
                clearTimeout(this.hideTimeout);
                this.hideTimeout = null;
            }
        }
    },

    attachListeners() {
        document.addEventListener('click', (e) => {
            const target = e.target.closest('.show-loader');
            if (!target) return;

            const form = target.closest('form');
            if (form && !form.checkValidity()) {
                return;
            }

            this.show();
        });

        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('show-loader')) {
                this.show();
            }
        });
    }
};

AppLoader.init();