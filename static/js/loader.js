// static/js/loader.js - VERSÃO CORRIGIDA E SEGURA

export const AppLoader = {
    element: null,
    hideTimeout: null,
    isVisible: false,

    init() {
        this.element = document.getElementById('global-loader');
        if (!this.element) {
            console.error('❌ #global-loader não encontrado no DOM!');
            return;
        }
        console.log('✅ AppLoader inicializado');
        this.attachListeners();
    },

    show() {
        if (!this.element) return;
        
        // Evita múltiplas chamadas
        if (this.isVisible) return;
        
        console.log('📍 AppLoader.show()');
        this.isVisible = true;
        
        // Remove classe d-none para exibir
        this.element.classList.remove('d-none');
        
        // Limpa timeout anterior
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
        }
        
        // AUTO-HIDE após 15 segundos (segurança contra travamentos)
        this.hideTimeout = setTimeout(() => {
            console.warn('⚠️ Loader auto-hidden após 15s');
            this.hide();
        }, 15000);
    },

    hide() {
        if (!this.element) return;
        
        // Evita múltiplas chamadas
        if (!this.isVisible) return;
        
        console.log('📍 AppLoader.hide()');
        this.isVisible = false;
        
        // Adiciona classe d-none para esconder
        this.element.classList.add('d-none');
        
        // Limpa timeout
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
            
            // Valida formulário antes de mostrar loader
            if (form && !form.checkValidity()) {
                return; // Deixa o navegador mostrar erros nativos
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

// Inicializa quando o módulo é carregado
if (document.readyState === 'loading') {
    // DOM ainda está carregando
    document.addEventListener('DOMContentLoaded', () => AppLoader.init());
} else {
    // DOM já foi carregado
    AppLoader.init();
}