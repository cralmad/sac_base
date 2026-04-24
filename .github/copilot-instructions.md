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
* **Backend DRY:** Helpers compartilhados de autorização e mensagens devem ficar em `sac_base/permissions_utils.py`.

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
    * O `base.html` deve expor obrigatoriamente um bloco `{% block estilo %}` dentro de `<head>` para CSS específico de página.
    * CSS específico de página só pode ser incluído nesse bloco e deve sempre apontar para um arquivo que exista no app.
* **`base.js`:** Comportamentos globais de interface (Navbar, inicialização).
* **`screen_permissions.js`:** Regras globais de visibilidade de botões por estado/permissão. Evitar duplicar `botaoDeveFicarVisivel` e `podeExibirBotaoPorPermissao` em scripts de página.
    * Para leitura de permissões por ação, preferir `createActionChecker(...)` no script da página em vez de recriar helpers de `getScreenPermissions`.
* **`permissions_utils.py`:** Regras globais de autorização e resposta de permissão no backend.
    * Em views, preferir `build_action_permissions(...)` e `permission_denied_response(...)` em vez de recriar helpers locais.
    * Para normalização de `ValidationError`, preferir `extract_validation_messages(...)`.
    * Evitar criar wrappers locais como `obter_acoes_permitidas_*` e `resposta_sem_permissao` quando apenas delegarem para utilitários globais.
* **`sisVar.js`:** Gerenciamento do estado global, Proxy, mensagens e modais de confirmação.
* **`input_rules.js`:** Máscaras e regras de inputs (ativado pela classe `.smart-input`). Uso obrigatório em formulários.
* **`conditional_select.js`:** Lógica para selects dependentes. Uso obrigatório sempre que houver campos condicionais.
    * Em cascatas como país → região → cidade, usar `data-hierarchy*` no template e `initHierarchicalSelects(...)` no script da página; não duplicar lógica manual de dependência.
* **`loader.js` (AppLoader):** Deve ser ativado obrigatoriamente no carregamento da página (evitando cliques precoces) e em todas as requisições assíncronas.
* **`smart_filter.js`** (`static/js/smart_filter.js`) **+ `smart_filter.py`** (`sac_base/smart_filter.py`): Utilitário padrão para filtros avançados em campos de texto e número em relatórios e consultas. **Uso obrigatório** sempre que houver filtros do tipo "número(s)", "faixa numérica" ou "texto(s) com curinga" em formulários de pesquisa/relatório. Nunca recriar lógica equivalente no script da página ou na view.
    * **Frontend (JS):** importar `parseSmartNumber`, `parseSmartText`, `validateSmartNumber`, `validateSmartText`, `getMultiSelectValues` de `static/js/smart_filter.js`.
    * **Backend (Python):** usar `apply_smart_number_filter(qs, field, value)` e `apply_smart_text_filter(qs, field, value)` de `sac_base/smart_filter.py`.
    * **Sintaxe de número:** `1,3,5-10,11` → lista/faixa de inteiros. Exemplo de campo: `<input class="form-control font-monospace" placeholder="ex: 1,3,5-10,11">`.
    * **Sintaxe de texto:** termos separados por vírgula, `*` como curinga no início/fim. Exemplo: `REF001,*LEROY*,COMEÇA*`. Aspas ao redor de cada termo são suportadas mas opcionais (legado).
    * **Select múltiplo:** usar `getMultiSelectValues(selectEl)` para obter os valores selecionados e enviá-los ao backend como array (via JSON body).
* **`styles.css`:** Estilos globais e utilitários de layout.

---

## 4. DESIGN MOBILE-FIRST (BREAKPOINTS)
O layout deve seguir rigorosamente a abordagem Mobile-First:
* **Mobile (Base):** 320px a 375px. Todo conteúdo deve caber sem rolagem horizontal.
* **Tablet / Mobile Landscape:** 481px a 768px. Introdução de colunas duplas ou aumento de margens.
* **Desktop Padrão:** 1025px a 1280px. Layout multi-coluna completo.
* **Limite Máximo (Container):** max-width de 1140px a 1200px para o conteúdo principal, mantendo-o centralizado.
* **Classes Bootstrap:** Nunca inventar classes utilitárias ou de container (ex.: `container-md-3`). Use apenas classes válidas do Bootstrap ou classes próprias declaradas em CSS global.
* **Estilo Inline:** Evitar `style="max-width:..."`, `style="width:..."` e similares em templates. Se a regra se repetir ou fizer parte do layout, mover para CSS global ou CSS do app.

---

## 5. PADRÕES DE FORMULÁRIO E UI
* **Estilização:** A estilização deve ser realizada, sempre que possível, pelo Bootstrap.
* **Hierarquia de Validação:**
    1. Regras nativas do HTML (required, maxlength, etc.).
    2. Validação JavaScript (via scripts de página).
    3. Validação de Back-end (SchemaValidator e regras de negócio).
* **Diversos:**
    1. Schemas: O mesmo schema de campos definido na View deve ser refletido no HTML e no JS.
    2. Mensagens: Sempre chamar a limpeza de mensagens antes de iniciar uma nova requisição POST.
    3. Segurança de renderização: Nunca interpolar dados dinâmicos em `innerHTML`, `outerHTML` ou `insertAdjacentHTML` sem sanitização. Preferir `textContent`, `createElement` ou helper global de escape HTML.
    4. Renderização de listas/tabelas: Não usar `array.map(...).join('')` para montar HTML com dados vindos do backend. Construir linhas/células com `document.createElement` e atribuir conteúdo com `textContent`.
    5. Tabelas e listas renderizadas via JS devem tratar todo valor vindo do backend como não confiável.
        6. **Texto de ajuda em campos (padrão obrigatório):**
                * Sempre usar no `<label>` o mesmo padrão visual do app motorista (campo `codigo`): `d-flex align-items-center gap-1` + ícone `bi bi-question-circle`.
                * O texto de ajuda deve ficar em tooltip Bootstrap via `data-bs-toggle="tooltip"`, `data-bs-placement="top"` e `data-bs-title="..."`.
                * Evitar `small/form-text` abaixo do input quando a ajuda for apenas contextual; nesses casos, preferir tooltip para manter o layout consistente.
                * Modelo padrão (copiar e adaptar apenas o texto e o `for/id`):
                    ```html
                    <label class="form-label mb-0 d-flex align-items-center gap-1" for="campo_exemplo">
                        <span>Rótulo do Campo</span>
                        <span
                            class="text-primary"
                            role="button"
                            tabindex="0"
                            data-bs-toggle="tooltip"
                            data-bs-placement="top"
                            data-bs-title="Texto de ajuda objetivo e curto.">
                            <i class="bi bi-question-circle"></i>
                        </span>
                    </label>
                    ```
* **Botões Padronizados (visibilidade via `data-show-on`) (devem ser estilizados via CSS global):**
    * `NOVO`: Inicia novo registro.
    * `SALVAR`: Submete o formulário.
    * `EDITAR`: Habilita edição em modo visualização.
    * `EXCLUIR`: Remove o registro.
    * `PESQUISAR`: Direciona para o formulário de consulta/pesquisa.
    * `FILTRAR`: Executa busca com base nos filtros.
    * `GERAR`: Exclusivo para processamento de relatórios.
    * `VOLTAR`: Retorna à tela anterior.
    * `CANCELAR`: Limpa o formulário e/ou cancela a ação em andamento.
* **Barra de Ações Responsiva:** Envolver botões principais em `<div class="btn-actions">` para empilhamento no mobile e linha no desktop. Evitar botões soltos fora de wrapper semântico.

---

## 6. PREFERÊNCIAS DO COPILOT (Código no chat)
* **Ação Preferida:** Sempre utilize a ferramenta **Código no chat** para comitar alterações diretamente no repositório.
* **Transparência:** Apresente sempre as opções (githubwrite, Código no chat, Copilot Agent) e seus custos antes de agir.
* **DRY Global:** Se o comportamento for necessário em múltiplas páginas, implemente em um arquivo global, nunca no script específico da página.
* **DRY Backend:** Em views Django, evitar duplicar helpers de permissões por app; reutilizar utilitários de `sac_base/permissions_utils.py`.
* **Permissões de Botões:** Em telas de cadastro, reutilizar o helper global `screen_permissions.js` para visibilidade por `data-show-on` e por ação (`incluir/editar/excluir`).
* **Renderização Segura:** Ao precisar gerar HTML dinamicamente em JS, usar helper global compartilhado para escape ou construir o DOM com `document.createElement`.
* **Layout Consistente:** Para páginas de cadastro/consulta, preferir containers Bootstrap válidos e consistentes entre apps, evitando classes ad hoc no template.
* **Container de Pesquisa:** O bloco `#div-pesquisa` deve usar `class="container-xl d-none mt-3"` para manter alinhamento e respiro visual consistentes entre apps.

---

## 7. VARIÁVEIS DE AMBIENTE (PRODUÇÃO — HEROKU)

### Obrigatórias
| Variável | Descrição |
|---|---|
| `BANCO_DE_DADOS` | URL de conexão com o banco (ex.: `postgres://user:pass@host:5432/db`). O settings também aceita `DATABASE_URL` como fallback (padrão do addon Heroku Postgres). |
| `DJANGO_SECRET_KEY` | Chave secreta do Django. Gerar com `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`. **Nunca reutilizar a chave de desenvolvimento.** |
| `DJANGO_ALLOWED_HOSTS` | Domínios aceitos, separados por vírgula. Ex.: `meuapp.herokuapp.com,meudominio.com`. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origens confiáveis para CSRF, separadas por vírgula. Ex.: `https://meuapp.herokuapp.com,https://meudominio.com`. |

### Segurança (assumem valor seguro automaticamente quando `DJANGO_DEBUG` está ausente/false)
| Variável | Padrão em produção | Descrição |
|---|---|---|
| `DJANGO_DEBUG` | `false` (não definir em prod) | Nunca definir como `true` em produção. |
| `DJANGO_SESSION_COOKIE_SECURE` | `true` | Cookies de sessão somente via HTTPS. |
| `DJANGO_CSRF_COOKIE_SECURE` | `true` | Cookie CSRF somente via HTTPS. |
| `DJANGO_AUTH_COOKIE_SECURE` | `true` | Cookie JWT somente via HTTPS. |
| `DJANGO_USE_X_FORWARDED_PROTO` | `false` | Definir como `true` no Heroku para reconhecer HTTPS via proxy. |
| `DJANGO_SECURE_SSL_REDIRECT` | `false` | Definir como `true` para redirecionar HTTP → HTTPS. |

### Opcionais / Infraestrutura
| Variável | Descrição |
|---|---|
| `REDIS_URL` | URL do Redis. Necessário para WebSockets em ambientes multi-dyno (addon Heroku Redis). Sem ela, usa `InMemoryChannelLayer` (não funciona com mais de um dyno). |
| `DJANGO_DB_SSL_REQUIRE` | `true` por padrão em produção. Forçar SSL na conexão com o banco. |

### Integrações externas
| Variável | Descrição |
|---|---|
| `BULKGATE_APP_ID` | Application ID gerado no portal BulkGate (`portal.bulkgate.com` → Modules & APIs → Create API). Obrigatório para envio de SMS. |
| `BULKGATE_APP_TOKEN` | Application Token gerado no portal BulkGate. Nunca versionar. Obrigatório para envio de SMS. |

> **SMS — padrão de números:** A função `sac_base/sms_service.py::normalizar_numero()` aceita qualquer formato (`+351...`, `00351...`, `912...`). Números sem DDI são tratados como pertencentes ao país de atuação da Filial (`Filial.pais_atuacao.codigo_tel`). O fallback hardcoded é `351` (Portugal).

### Exemplo mínimo para o Heroku
```bash
heroku config:set BANCO_DE_DADOS="postgres://..." \
  DJANGO_SECRET_KEY="..." \
  DJANGO_ALLOWED_HOSTS="meuapp.herokuapp.com" \
  DJANGO_CSRF_TRUSTED_ORIGINS="https://meuapp.herokuapp.com" \
  DJANGO_USE_X_FORWARDED_PROTO=true \
  DJANGO_SECURE_SSL_REDIRECT=true \
  BULKGATE_APP_ID="12345" \
  BULKGATE_APP_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### Após o deploy
```bash
heroku run python manage.py migrate
heroku run python manage.py collectstatic --noinput  # executado automaticamente no build
```