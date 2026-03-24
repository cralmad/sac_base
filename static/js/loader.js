// static/js/loader.js

export const AppLoader = {
    element: null,
    hideTimeout: null,
    isVisible: false,
    isInitialized: false,

    init() {
        if (this.isInitialized) return;

        this.element = document.getElementById('global-loader');

        if (!this.element) {
            console.error('❌ CRÍTICO: #global-loader não encontrado no DOM!');
            return;
        }

        this.isVisible = !this.element.classList.contains('d-none');

        this.isInitialized = true;
        this.attachListeners();
    },

    show() {
        if (!this.isInitialized) this.init();
        if (!this.element) return;
        if (this.isVisible) return;

        this.isVisible = true;
        this.element.classList.remove('d-none');

        if (this.hideTimeout) clearTimeout(this.hideTimeout);

        this.hideTimeout = setTimeout(() => {
            console.warn('⚠️ Loader auto-hidden após 15s');
            this.hide();
        }, 15000);
    },

    hide() {
        if (!this.isInitialized) this.init();
        if (!this.element) return;
        if (!this.isVisible) return;

        this.isVisible = false;
        this.element.classList.add('d-none');

        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
            this.hideTimeout = null;
        }
    },

    attachListeners() {
        document.addEventListener('click', (e) => {
            const target = e.target.closest('.show-loader');
            if (!target) return;

            const form = target.closest('form');
            if (form && !form.checkValidity()) return;

            this.show();
        });

        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('show-loader')) {
                this.show();
            }
        });
    }
};