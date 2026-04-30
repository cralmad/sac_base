# Guia de desenvolvimento SAC Base (instrucoes para Copilot)

Este documento define padroes de implementacao para o projeto. Em caso de conflito, use esta prioridade: **Seguranca > Arquitetura > UI**.

Referencia de padrao: `cadastro_view` (`pages/usuario/views.py`) e dependencias (`usuario.html`, `scriptsuser.js`).

---

## 1) Escopo e prioridade

Este guia tem tres objetivos:
- alinhar arquitetura e fluxo de dados;
- evitar duplicacao de logica entre apps;
- garantir seguranca e consistencia de interface.

Classificacao das regras:
- **MUST:** obrigatorio.
- **SHOULD:** recomendado.
- **AVOID:** evitar; use so com justificativa no codigo.

---

## 2) Arquitetura e fluxo `sisVar`

O projeto segue Django MTV com comportamento SPA em Vanilla JS:
- **GET (servidor):** renderiza pagina e estado inicial.
- **POST (servidor):** retorna dados/mensagens via `JsonResponse()`.
- **Frontend:** `sisVar` e a fonte de verdade de estado.
- **Seguranca:** JWT em cookie HttpOnly + CSRF token em respostas JSON.

Fluxo da `sisVar`:
1. View popula `request.sisvar_extra`.
2. `context_processors.py` mescla dados e `base.html` serializa em `#sisDados`.
3. `sisVar.js` cria Proxy reativo e dispara `applyFormState()` e `renderMensagens()`.
4. Dados sem chave principal devem ir em `others`.

---

## 3) Reutilizacao obrigatoria (DRY)

Se uma logica pode ser usada por mais de uma tela/app, ela deve ficar em utilitario global.

### Frontend
- `base.js`: comportamentos globais da interface.
- `screen_permissions.js`: visibilidade de botoes por estado/permissao.
- `sisVar.js`: estado global, mensagens e confirmacoes.
- `input_rules.js`: mascaras e regras de input (`.smart-input`).
- `conditional_select.js`: selects dependentes (`initHierarchicalSelects(...)`).
- `loader.js`: bloquear interacoes no load e em requests assincronos.
- `static/js/smart_filter.js`: parsing/validacao de filtros numericos/textuais.

### Backend
- `sac_base/permissions_utils.py`: permissoes e payloads de erro (`build_action_permissions(...)`, `permission_denied_response(...)`, `extract_validation_messages(...)`).
- `sac_base/smart_filter.py`: `apply_smart_number_filter(...)` e `apply_smart_text_filter(...)`.
- `pages/filial/services.py`: `get_filiais_escrita_queryset(...)` e `obter_filial_escrita(...)`.

### Regra pratica
- **MUST:** reutilizar helpers globais existentes.
- **AVOID:** criar wrappers locais que apenas delegam para utilitarios globais.

---

## 4) UI e formularios

### Layout e responsividade
- **MUST:** mobile-first (320-375 base, 481-768 intermediario, 1025-1280 desktop).
- **MUST:** usar classes validas do Bootstrap; evitar classes ad hoc de container.
- **SHOULD:** usar max-width de 1140-1200 para conteudo principal.
- **AVOID:** `style` inline repetitivo de layout (`width`, `max-width` etc.).

### Formularios
- **MUST:** validacao em 3 camadas: HTML nativo -> JS -> backend.
- **MUST:** manter schema consistente entre View, HTML e JS.
- **MUST:** limpar mensagens antes de novo POST.

### Renderizacao segura no JS
- **MUST:** tratar dados do backend como nao confiaveis.
- **MUST:** preferir `createElement` + `textContent`.
- **SHOULD:** quando precisar HTML dinamico, escapar com helper global (`_esc()`).
- **AVOID:** interpolar dados brutos em `innerHTML`, `outerHTML`, `insertAdjacentHTML`.
- **AVOID:** montar listas/tabelas com `array.map(...).join('')` para dados externos.

### Padrao de ajuda em campos
- **MUST:** usar tooltip Bootstrap no label (`data-bs-toggle="tooltip"`, `data-bs-placement="top"`, `data-bs-title="..."`).
- **MUST:** padrao visual `d-flex align-items-center gap-1` + `bi bi-question-circle`.
- **SHOULD:** preferir tooltip a `small/form-text` quando a ajuda for contextual.

### Botoes e acoes
- **MUST:** visibilidade por `data-show-on` com regra global de permissao.
- **MUST:** usar wrapper semantico `<div class="btn-actions">` para barra responsiva.
- Acoes padrao: `NOVO`, `SALVAR`, `EDITAR`, `EXCLUIR`, `PESQUISAR`, `FILTRAR`, `GERAR`, `VOLTAR`, `CANCELAR`.

### Container de pesquisa
- **MUST:** `#div-pesquisa` com `class="container-xl d-none mt-3"`.

---

## 5) Seguranca obrigatoria

### 5.1 IDOR multi-tenant por filial ativa
Toda view multi-tenant deve validar e filtrar por `request.filial_ativa`.

```python
filial_ativa = getattr(request, "filial_ativa", None)
if not filial_ativa:
    return JsonResponse(build_error_payload("Filial ativa nao encontrada."), status=403)

Pedido.objects.filter(filial=filial_ativa, ...)
TentativaEntrega.objects.filter(pedido__filial=filial_ativa, ...)
Devolucao.objects.filter(pedido__filial=filial_ativa, ...)
```

- `request.filial_ativa` vem de `JWTAuthMiddleware._resolve_filial_context()` (`pages/usuario/middleware.py`).
- Excecoes (endpoint publico com token) devem ser documentadas no codigo.

### 5.2 JWT blacklist em logout/troca de senha

```python
refresh_token_str = request.COOKIES.get("refresh_token")
if refresh_token_str:
    try:
        from rest_framework_simplejwt.tokens import RefreshToken as _RT
        _RT(refresh_token_str).blacklist()
    except Exception:
        pass
```

Requer `rest_framework_simplejwt.token_blacklist` no `INSTALLED_APPS` e migracoes aplicadas.

### 5.3 Rate limit no login
- **MUST:** limitar a 5 tentativas por IP em 5 minutos (cache).

### 5.4 Paginacao segura

```python
pagina = max(1, int(data.get("pagina", 1)))
page_size = max(1, min(int(data.get("page_size", 30)), 200))
```

- Cap de 200 reduz risco de DoS.

### 5.5 CSP
- `sac_base.csp_middleware.CSPMiddleware` injeta `Content-Security-Policy`.
- **AVOID:** `unsafe-inline` e `unsafe-eval` sem justificativa formal.

### 5.6 Regras complementares
- `SchemaValidator` (`sac_base/form_validador.py`) aceita: `string`, `password`, `email`, `integer`, `boolean`.
- `SoftDeleteMixin`: `objects` retorna ativos; para deletados usar `all_objects`.
- Em `pages/pedidos/views_relatorio.py`, sempre passar filial em `_build_qs_relatorio(filtros, filial=...)`.

---

## 6) Producao no Heroku

### Variaveis obrigatorias
- `BANCO_DE_DADOS` (ou fallback `DATABASE_URL`).
- `DJANGO_SECRET_KEY`.
- `DJANGO_ALLOWED_HOSTS`.
- `DJANGO_CSRF_TRUSTED_ORIGINS`.

### Variaveis de seguranca
- `DJANGO_DEBUG=false` em producao.
- `DJANGO_SESSION_COOKIE_SECURE=true`.
- `DJANGO_CSRF_COOKIE_SECURE=true`.
- `DJANGO_AUTH_COOKIE_SECURE=true`.
- Em Heroku, configurar:
  - `DJANGO_USE_X_FORWARDED_PROTO=true`
  - `DJANGO_SECURE_SSL_REDIRECT=true`

### Variaveis opcionais/infra
- `REDIS_URL` para WebSockets em multi-dyno.
- `DJANGO_DB_SSL_REQUIRE=true` (padrao seguro em prod).

### Integracoes externas
- `BULKGATE_APP_ID` e `BULKGATE_APP_TOKEN` para SMS.
- `IMGBB_API_KEY` para upload de fotos em devolucoes.
- `EMAIL_HOST_USER` e `EMAIL_HOST_PASSWORD` para autenticacao SMTP (Gmail).

### Avaliacoes e e-mails automaticos
Fluxo funcional da pesquisa de satisfacao:
- a fila deve ser gerada manualmente no relatorio por data (`prev_entrega`);
- apenas pedidos selecionados entram em `AvaliacaoPedido` (1 por pedido);
- o envio do e-mail usa apenas registros pre-gerados na fila;
- o cliente responde via link publico (`/app/logistica/avaliacao/<token>/`);
- apos resposta, o link e inativado (`link_ativo=False`) e nao permite novo envio.

Comando automatico:
- `pages/pedidos/management/commands/enviar_email_avaliacao_automatico.py`;
- processa por filial conforme `FilialConfig.email_auto`;
- processa somente fila pre-gerada (`selecionado_para_envio=True`, pendentes sem `email_enviado`) e evita duplicidade;
- flags de apoio: `--dry-run` (simula) e `--force` (ignora horario).

### Variaveis essenciais de e-mail (Gmail SMTP)
Usar um unico payload no padrao dicionario:

```bash
EMAIL_AUTO='{"EMAIL_HOST":"smtp.gmail.com","EMAIL_PORT":"587","EMAIL_USE_TLS":"true","EMAIL_HOST_USER":"conta@gmail.com","EMAIL_HOST_PASSWORD":"app_password","DEFAULT_FROM_EMAIL":"conta@gmail.com","APP_BASE_URL":"https://meuapp.herokuapp.com"}'
```

### Scheduler de SMS automatico
O comando `pages/pedidos/management/commands/enviar_sms_automatico.py` deve ser agendado no Heroku Scheduler.

Configurar job:
- **Task:** `python manage.py enviar_sms_automatico`
- **Frequency:** a cada 10 minutos (ou conforme negocio)
- **Next due:** horario de inicio desejado

Observacoes:
- o comando e idempotente (nao duplica notificacoes ja enviadas);
- teste sem envio real: `python manage.py enviar_sms_automatico --dry-run`;
- forcar envio ignorando horario: `python manage.py enviar_sms_automatico --force`.

### Scheduler de e-mail automatico (avaliacao)
O comando `pages/pedidos/management/commands/enviar_email_avaliacao_automatico.py` deve ser agendado no Heroku Scheduler.

Configurar job:
- **Task:** `python manage.py enviar_email_avaliacao_automatico`
- **Frequency:** a cada 10 minutos (ou conforme negocio)
- **Next due:** horario de inicio desejado

Observacoes:
- o comando e idempotente para pedidos ja enviados/respondidos;
- teste sem envio real: `python manage.py enviar_email_avaliacao_automatico --dry-run`;
- forcar envio ignorando horario: `python manage.py enviar_email_avaliacao_automatico --force`.

### Exemplo minimo de setup
```bash
heroku config:set BANCO_DE_DADOS="postgres://..." \
  DJANGO_SECRET_KEY="..." \
  DJANGO_ALLOWED_HOSTS="meuapp.herokuapp.com" \
  DJANGO_CSRF_TRUSTED_ORIGINS="https://meuapp.herokuapp.com" \
  DJANGO_USE_X_FORWARDED_PROTO=true \
  DJANGO_SECURE_SSL_REDIRECT=true \
  EMAIL_AUTO='{"EMAIL_HOST":"smtp.gmail.com","EMAIL_PORT":"587","EMAIL_USE_TLS":"true","EMAIL_HOST_USER":"conta@gmail.com","EMAIL_HOST_PASSWORD":"app_password","DEFAULT_FROM_EMAIL":"conta@gmail.com","APP_BASE_URL":"https://meuapp.herokuapp.com"}' \
  BULKGATE_APP_ID="12345" \
  BULKGATE_APP_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  IMGBB_API_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### Pos-deploy
```bash
heroku run python manage.py migrate
heroku run python manage.py collectstatic --noinput
```

---

## 7) Modo de atuacao do agente (Copilot)

- **MUST:** quando houver opcao, priorizar "Codigo no chat" para alteracoes no repositorio.
- **MUST:** explicitar opcoes de execucao (githubwrite, Codigo no chat, Copilot Agent) e custo antes de agir.
- **MUST:** respeitar padroes globais deste documento antes de criar implementacao local.
- **SHOULD:** manter respostas objetivas, com foco em reuso, seguranca e consistencia visual.

---

## 8) Checklist por feature (entrega)

Antes de finalizar uma funcionalidade, validar:
- [ ] View aplica regras de permissao e filial ativa (se multi-tenant).
- [ ] `request.sisvar_extra` e payload de resposta estao consistentes com a UI.
- [ ] Template usa estrutura Bootstrap valida e sem regras de layout duplicadas.
- [ ] Script da pagina reutiliza helpers globais (`screen_permissions`, `smart_filter`, etc.).
- [ ] Renderizacao JS nao injeta dados nao confiaveis sem escape/sanitizacao.
- [ ] Botoes padrao e `btn-actions` aplicados corretamente.
- [ ] Validacao HTML + JS + backend alinhada ao schema.
- [ ] Variaveis de ambiente/deploy (quando aplicavel) documentadas e conferidas.