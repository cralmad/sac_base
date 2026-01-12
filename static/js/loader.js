// Responsável por gerenciar o loader global da aplicação (um spinner que indica que algo está carregando)
// O loader é exibido quando o usuário clica em elementos com a classe 'show-loader'
export const AppLoader = {
    element: null,

    init() {
        this.element = document.getElementById('global-loader');
        this.attachListeners();
    },

    show() {
        if (this.element) this.element.classList.remove('d-none');
    },

    hide() {
        if (this.element) this.element.classList.add('d-none');
    },

    attachListeners() {
        document.addEventListener('click', (e) => {
            const target = e.target.closest('.show-loader');
            if (!target) return;

            // Se o elemento estiver dentro de um formulário
            const form = target.closest('form');
            
            // Se existir um formulário e ele for INVÁLIDO (campos required vazios, etc)
            if (form && !form.checkValidity()) {
                // Não faz nada, deixa o navegador mostrar os avisos de erro nativos
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