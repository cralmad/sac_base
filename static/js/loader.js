// static/js/loader.js - VERSÃO CORRIGIDA

export const AppLoader = {
    element: null,
    hideTimeout: null,
    isVisible: false,
    isInitialized: false,

    init() {
        // Previne múltiplas inicializações
        if (this.isInitialized) return;
        
        this.element = document.getElementById('global-loader');
        
        if (!this.element) {
            console.error('❌ CRÍTICO: #global-loader não encontrado no DOM!');
            return;
        }
        
        console.log('✅ AppLoader inicializado com sucesso');
        this.isInitialized = true;
        this.attachListeners();
    },

    show() {
        // ✅ Auto-inicializa se ainda não foi feito
        if (!this.isInitialized) {
            this.init();
        }

        if (!this.element) return;
        
        if (this.isVisible) return;
        
        console.log('📍 AppLoader.show()');
        this.isVisible = true;
        
        this.element.classList.remove('d-none');
        
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
        }
        
        this.hideTimeout = setTimeout(() => {
            console.warn('⚠️ Loader auto-hidden após 15s');
            this.hide();
        }, 15000);
    },

    hide() {
        // ✅ Auto-inicializa se ainda não foi feito
        if (!this.isInitialized) {
            this.init();
        }

        if (!this.element) return;
        
        if (!this.isVisible) return;
        
        console.log('📍 AppLoader.hide()');
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

// ✅ MUDA: Não inicializa aqui! Espera por chamada explícita ou auto-init
// AppLoader.init(); // ❌ REMOVIDO

// ✅ Inicializa quando o DOM está totalmente pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('🔧 Inicializando AppLoader após DOMContentLoaded');
        AppLoader.init();
    });
} else {
    // DOM já carregou (raro em módulos, mas acontece)
    console.log('🔧 Inicializando AppLoader imediatamente');
    AppLoader.init();
}