
# 📘 Guia de Padrões de Desenvolvimento — SAC Base (Instruções para Copilot)

Este guia define a arquitetura, o fluxo de dados e os padrões de interface do projeto. Use-o como fonte de verdade absoluta.

> Referência de padrão baseada em `cadastro_view` (`pages/usuario/views.py`) e suas dependências (`usuario.html`, `scriptsuser.js`). Use este guia como fonte de verdade ao desenvolver qualquer nova funcionalidade.

---

## 1. VISÃO GERAL DA ARQUITETURA
O projeto segue o padrão Django MTV com comportamento de SPA via Vanilla JS:
* **Servidor (GET):** Entrega a página inicial e o estado inicial via `render()`.
* **Servidor (POST):** Processa operações e retorna dados ou mensagens via `JsonResponse()`.
* **Frontend:** Controlado pela variável de estado global `sisVar`, que é a única fonte de verdade dos dados.
* **Segurança:** Autenticação via JWT (cookies HttpOnly) e CSRF Token injetado automaticamente em todas as respostas JSON.

---

## 2. O FLUXO DE DADOS PELA `sisVar`
A `sisVar` é um objeto reativo (Proxy) que sincroniza o back-end e o front-end:
1. **Origem:** Na View, o desenvolvedor popula `request.sisvar_extra`.
2. **Hidratação:** O `context_processors.py` mescla esses dados e o `base.html` os serializa no script `#sisDados`.
3. **Reatividade:** A `sisVar.js` transforma o objeto em Proxy. Mudanças no estado disparam automaticamente:
    * `applyFormState()`: Controla visibilidade de botões e bloqueio de inputs.
    * `renderMensagens()`: Exibe alertas no `#container-mensagens`.
4. **Regra de Chaves:** Qualquer dado novo sem uma chave principal (como 'usuario' ou 'form') deve ser adicionado obrigatoriamente em `others`.

---

## 3. RELAÇÃO DE ARQUIVOS GLOBAIS E DEPENDÊNCIAS
Comportamentos globais devem ser implementados uma única vez nestes arquivos:
* **`base.html`:** Estrutura base, carrega Bootstrap 5.3.3 e scripts globais.
* **`base.js`:** Comportamentos globais de interface (Navbar, inicialização).
* **`sisVar.js`:** Gerenciamento do estado global, Proxy, mensagens e modais de confirmação.
* **`input_rules.js`:** Máscaras e regras de inputs (ativado pela classe `.smart-input`). Uso obrigatório em formulários.
* **`conditional_select.js`:** Lógica para selects dependentes. Uso obrigatório sempre que houver campos condicionais.
* **`loader.js` (AppLoader):** Deve ser ativado obrigatoriamente no carregamento da página (evitando cliques precoces) e em todas as requisições assíncronas.
* **`styles.css`:** Estilos globais e utilitários de layout.

---

## 4. DESIGN MOBILE-FIRST (BREAKPOINTS)
O layout deve seguir rigorosamente a abordagem Mobile-First:
* **Mobile (Base):** 320px a 375px. Todo conteúdo deve caber sem rolagem horizontal.
* **Tablet / Mobile Landscape:** 481px a 768px. Introdução de colunas duplas ou aumento de margens.
* **Desktop Padrão:** 1025px a 1280px. Layout multi-coluna completo.
* **Limite Máximo (Container):** max-width de 1140px a 1200px para o conteúdo principal, mantendo-o centralizado.

---

## 5. PADRÕES DE FORMULÁRIO E UI
* **Hierarquia de Validação:**
    1. Regras nativas do HTML (required, maxlength, etc.).
    2. Validação JavaScript (via scripts de página).
    3. Validação de Back-end (SchemaValidator e regras de negócio).
* **Diversos:**
    1. Schemas: O mesmo schema de campos definido na View deve ser refletido no HTML e no JS.
    2. Mensagens: Sempre chamar a limpeza de mensagens antes de iniciar uma nova requisição POST.
* **Botões Padronizados (visibilidade via `data-show-on`) (devem ser estilizados via CSS global):**
    * `NOVO`: Inicia novo registro.
    * `SALVAR`: Submete o formulário.
    * `EDITAR`: Habilita edição em modo visualização.
    * `EXCLUIR`: Remove o registro.
    * `PESQUISAR`: Direciona para o formulário de consulta/pesquisa.
    * `FILTRAR`: Executa busca com base nos filtros.
    * `GERAR`: Exclusivo para processamento de relatórios.
    * `VOLTAR`: Retorna à tela anterior ou cancela edição.

---

## 6. PREFERÊNCIAS DO COPILOT (Código no chat)
* **Ação Preferida:** Sempre utilize a ferramenta **Código no chat** para comitar alterações diretamente no repositório.
* **Transparência:** Apresente sempre as opções (githubwrite, Código no chat, Copilot Agent) e seus custos antes de agir.
* **DRY Global:** Se o comportamento for necessário em múltiplas páginas, implemente em um arquivo global, nunca no script específico da página.