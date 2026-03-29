# 📘 Guia de Padrões de Desenvolvimento — SAC Base

> Referência de padrão baseada em `cadastro_view` (`pages/usuario/views.py`) e suas dependências (`usuario.html`, `scriptsuser.js`). Use este guia como fonte de verdade ao desenvolver qualquer nova funcionalidade.

---

## 1. VISÃO GERAL DA ARQUITETURA

O projeto segue um padrão **Django MTV + SPA-like via Vanilla JS**, onde:
- O **servidor** entrega a página inicial (GET → `render`) e processa operações (POST → `JsonResponse`)
- O **frontend** é controlado por uma variável de estado global chamada **`sisVar`**, que é a **única fonte de verdade dos dados**
- A comunicação usa **JWT em cookies HttpOnly** + **CSRF token** injetado automaticamente pelo middleware

---

## 2. ESTRUTURA DE PASTAS

```
SAC_BASE/                          ← Raiz do projeto
├── base.html                      ← Template base global (herança de todos os outros)
├── manage.py
├── sac_base/                      ← Configurações do projeto Django
│   ├── settings.py
│   ├── urls.py                    ← Roteamento raiz (inclui os urls.py de cada app)
│   ├── context_processors.py      ← Injeta sisVar no contexto de TODOS os templates
│   └── form_validador.py          ← Validador de schema de formulários (back-end)
├── pages/                         ← Todos os apps ficam AQUI
│   ├── usuario/                   ← App de referência (padrão ouro)
│   │   ├── views.py               ← Lógica de negócio
│   │   ├── urls.py                ← Rotas do app
│   │   ├── models.py
│   │   ├── middleware.py          ← Autenticação JWT
│   │   ├── templates/             ← HTMLs do app
│   │   │   └── usuario.html
│   │   └── static/usuario/        ← Estáticos isolados por app (namespace = nome do app)
│   │       ├── js/scriptsuser.js  ← Script de página
│   │       └── css/stylesuser.css
│   └── <novo_app>/                ← Mesmo padrão para todo novo app
└── static/                        ← Estáticos GLOBAIS
    ├── css/styles.css
    └── js/
        ├── sisVar.js              ← Estado global (fonte única)
        ├── base.js                ← JS global (carregado por base.html)
        ├── refresh_varSis.js      ← Hidratação do estado via input events
        ├── input_rules.js         ← Máscaras e regras de inputs
        └── loader.js              ← Spinner global
```

**Regra:** cada app em `pages/` tem sua própria pasta `templates/` e `static/<nome_do_app>/`. Os arquivos estáticos globais ficam em `static/`.

---

## 3. O CONTRATO DA `sisVar` — A REGRA MAIS IMPORTANTE

`sisVar` é um **objeto JavaScript reativo (Proxy)** que serve como estado global. Ela é **inicializada pelo back-end** via `context_processors.py` e **serializada no HTML** pelo `base.html`.

### 3.1 Estrutura fixa do contrato

```json
{
  "usuario": {
    "autenticado": true,
    "id": 1,
    "nome": "admin"
  },
  "schema": {
    "nomeDoForm": {
      "campo1": { "type": "string", "maxlength": 30, "required": true, "value": "" }
    }
  },
  "form": {
    "nomeDoForm": {
      "estado": "novo",
      "update": null,
      "campos": { "campo1": "" }
    }
  },
  "mensagens": {
    "sucesso": { "ignorar": true,  "conteudo": ["Mensagem..."] },
    "erro":    { "ignorar": false, "conteudo": ["Mensagem..."] },
    "aviso":   { "ignorar": true,  "conteudo": ["Mensagem..."] },
    "info":    { "ignorar": true,  "conteudo": ["Mensagem..."] }
  },
  "others": {
    "csrf_token_value": "abc123..."
  }
}
```

### 3.2 Como o back-end alimenta a sisVar

Na **view**, antes de chamar `render()`, popule `request.sisvar_extra`:

```python
request.sisvar_extra = {
    "schema": schema,
    "form": {
        nomeForm: {
            "estado": "novo",
            "update": None,
            "campos": { "campo1": "", ... }
        }
    }
}
return render(request, template)
```

O `context_processors.py` mescla `request.sisvar_extra` na base da `sisVar` automaticamente. O `base.html` serializa tudo em uma tag `<script id="sisDados">` via:
```html
{{ sisVar|json_script:"sisDados" }}
```

---

## 4. PADRÃO DE UMA VIEW — MODELO `cadastro_view`

Toda view de cadastro segue **exatamente** esta estrutura:

```python
def minha_view(request):
    # 1. Definir template e nomes dos formulários
    template     = "minha_pagina.html"
    nomeForm     = "cadMeuForm"       # ID do <form> no HTML
    nomeFormCons = "consMeuForm"      # ID do form de consulta (se houver)

    # 2. Definir o schema de validação (front e back usam o mesmo)
    schema = {
        nomeForm: {
            "campo1": {'type': 'string',  'maxlength': 50, 'required': True,  'value': ''},
            "campo2": {'type': 'boolean', 'required': False, 'value': None},
        },
        nomeFormCons: {
            "filtro1": {'type': 'string', 'maxlength': 50},
        }
    }

    # ── GET ──────────────────────────────────────────────────────────────────
    if request.method == "GET":
        request.sisvar_extra = {
            "schema": schema,
            "form": {
                nomeForm: {
                    "estado": "novo",   # estados: novo | editar | visualizar
                    "update": None,
                    "campos": {
                        "id":     None,
                        "campo1": "",
                        "campo2": None,
                    }
                },
                nomeFormCons: {
                    "estado": "novo",
                    "campos": { "filtro1": "", "id_selecionado": None }
                }
            }
        }
        return render(request, template)   # ← GET sempre retorna render()

    # ── POST ─────────────────────────────────────────────────────────────────
    dataFront = request.sisvar_front               # JSON já parseado pelo middleware
    form      = dataFront.get("form", {}).get(nomeForm, {})
    campos    = form.get("campos", {})
    estado    = form.get("estado", "")

    # 3. Validação de schema (1ª camada)
    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        erros = [f"{c} - {', '.join(e)}" for c, e in validator.get_errors().items()]
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": erros, "ignorar": False}}
        }, status=400)

    # 4. Validações de negócio (2ª camada) — sua lógica aqui

    # 5. Operação com match/case por estado
    match estado:
        case 'novo':
            registro = MeuModel.objects.create(...)
        case 'editar':
            registro.campo1 = campos.get("campo1")
            registro.save()
        case _:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": [f"Estado inválido: '{estado}'"], "ignorar": False}}
            }, status=400)

    # 6. Resposta de sucesso — POST sempre retorna JsonResponse()
    return JsonResponse({
        "success": True,
        "form": {
            nomeForm: {
                "estado": "visualizar",
                "update": registro.updated_at,
                "campos": { "id": registro.id, "campo1": registro.campo1 }
            }
        },
        "mensagens": {
            "sucesso": {"ignorar": True, "conteudo": ["Operação realizada com sucesso!"]}
        }
    })
```

**Regras da view:**

| Método | Retorno | O que faz |
|--------|---------|-----------|
| `GET` | `render(request, template)` | Popula `sisvar_extra` e entrega o HTML |
| `POST` | `JsonResponse(...)` | Lê `request.sisvar_front`, valida, salva, retorna JSON |

---

## 5. PADRÃO DE URLS

### `sac_base/urls.py` (raiz)
```python
# Prefixo global "app/" para rotas de aplicação
path('app/', include('pages.meu_app.urls')),
```

### `pages/meu_app/urls.py`
```python
from django.urls import path
from . import views

urlpatterns = [
    path('meuapp/cadastro/',      views.meu_cadastro_view),
    path('meuapp/cadastro/cons',  views.meu_cons_view),
]
# URL final: /app/meuapp/cadastro/
```

---

## 6. PADRÃO DO TEMPLATE HTML

Todo template **herda de `base.html`** e preenche os blocos obrigatórios:

```html
{% extends "base.html" %}
{% load static %}

{% block title %}SacBase - Nome da Página{% endblock %}

{% block estilo %}
  <link rel="stylesheet" href="{% static 'meu_app/css/styles.css' %}">
{% endblock %}

{% block page_title %}Título da Página{% endblock %}

{% block content %}
  {# ── Formulário principal com data-form-lock ── #}
  <form id="cadMeuForm" data-form-lock="cadMeuForm" method="POST">
    {% csrf_token %}

    <div class="container-md-3 my-3 mx-auto">
      <div class="row g-3">

        <div class="col-12 col-sm-5">
          <label class="form-label mb-0">Nome do Campo</label>
          <input type="text" name="campo1" class="form-control smart-input"
                 data-textcase="upper" maxlength="50" required/>
        </div>

      </div>
    </div>

    {# Botões controlados pelo estado via data-show-on #}
    <button id="btn-salvar"   class="btn btn-primary"                   data-show-on="novo,editar" type="submit">
      <i class="bi bi-save"></i> Salvar
    </button>
    <button id="btn-editar"   class="btn btn-warning  d-none"           data-show-on="visualizar"  type="button">
      <i class="bi bi-pencil"></i> Editar
    </button>
    <button id="btn-novo"     class="btn btn-success  d-none"           data-show-on="visualizar"  type="button">
      <i class="bi bi-plus-circle"></i> Novo
    </button>
    <button id="btn-cancelar" class="btn btn-outline-secondary d-none"  data-show-on="novo,editar" type="button">
      <i class="bi bi-x-circle"></i> Cancelar
    </button>
    <button id="btn-abrir-pesquisa" class="btn btn-secondary"           type="button">
      <i class="bi bi-search"></i> Pesquisar
    </button>
  </form>
{% endblock %}

{% block scripts %}
  <script type="module" src="{% static 'meu_app/js/scripts.js' %}"></script>
{% endblock %}
```

**Regras do template:**
- Sempre usar `{% extends "base.html" %}` e `{% load static %}`
- CSS da página deve ser declarado **dentro do `{% block estilo %}`** — nunca solto fora de um bloco
- O `<form>` principal **deve ter** `id="nomeForm"` E `data-form-lock="nomeForm"` com os **mesmos valores**
- Inputs usam a classe `smart-input` para ativar as regras de `input_rules.js`
- Botões controlados por estado usam `data-show-on="estado1,estado2"` — a `sisVar` gerencia a visibilidade automaticamente
- Layout usa **Mobile First** com Bootstrap grid: `col-12` como base, expandindo com `col-sm-*` e `col-md-*`

### Atributos de `smart-input` disponíveis:

| Atributo | Valores | Efeito |
|---|---|---|
| `data-textcase` | `upper` / `lower` | Converte automaticamente |
| `data-deny` | lista de chars | Bloqueia caracteres |
| `data-allow` | regex charset | Permite apenas esses chars |
| `data-mask` | `pt-phone` / `pt-postcode` | Aplica máscara |
| `maxlength` / `minlength` | número | Limita tamanho |

---

## 7. PADRÃO DO SCRIPT DE PÁGINA (JS)

Cada página tem **um único arquivo JS** em `pages/<app>/static/<app>/js/scripts.js`:

```javascript
// 1. IMPORTS — sempre com caminhos absolutos /static/... 
import {
  updateFormField, getForm, updateState,
  clearMessages, definirMensagem,
  hidratarFormulario, setFormState, confirmar
} from "/static/js/sisVar.js";
import { fazerRequisicao }      from "/static/js/base.js";
import { initSmartInputs }      from "/static/js/input_rules.js";
import { criarAtualizadorForm } from "/static/js/refresh_varSis.js";
import { AppLoader }            from "/static/js/loader.js";

// 2. CONSTANTES — nomes dos formulários (iguais ao HTML e à view)
const nomeForm     = "cadMeuForm";
const nomeFormCons = "consMeuForm";
const form  = document.getElementById(nomeForm);
const form2 = document.getElementById(nomeFormCons);

// 3. VÍNCULO sisVar ↔ inputs (fora do DOMContentLoaded)
const updater = criarAtualizadorForm({ formId: nomeForm, setter: updateFormField, form });
form.addEventListener("input", updater);
initSmartInputs((input, value) => { updateFormField(nomeForm, input.name, value); });

// 4. SUBMIT DO FORMULÁRIO PRINCIPAL
form.addEventListener("submit", async e => {
  e.preventDefault();
  clearMessages(); // ← SEMPRE limpar mensagens antes de nova requisição

  const formData = getForm(nomeForm);

  confirmar({
    titulo: 'Confirmar Salvamento',
    mensagem: 'Deseja salvar o registro?',
    onConfirmar: async () => {
      AppLoader.show();

      const resultado = await fazerRequisicao("/app/meuapp/cadastro/", {
        form: { [nomeForm]: formData }
      });

      if (!resultado.success) {
        definirMensagem('erro', `Erro: ${resultado.error}`, false);
        AppLoader.hide();
        return;
      }

      updateState(resultado.data); // Atualiza sisVar com a resposta do servidor
      AppLoader.hide();
    }
  });
});

// 5. LÓGICA DE UI — dentro do DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {

  // Botões de estado
  document.getElementById('btn-editar').addEventListener('click',   () => setFormState(nomeForm, 'editar'));
  document.getElementById('btn-novo').addEventListener('click',     () => setFormState(nomeForm, 'novo'));
  document.getElementById('btn-cancelar').addEventListener('click', () => {
    confirmar({
      titulo: 'Cancelar',
      mensagem: 'Dados não salvos serão perdidos.',
      onConfirmar: () => setFormState(nomeForm, 'novo')
    });
  });

  // Alternância cadastro ↔ pesquisa
  const alternarTelas = () => {
    document.getElementById(nomeForm).classList.toggle('d-none');
    document.getElementById('div-pesquisa').classList.toggle('d-none');
  };
  document.getElementById('btn-abrir-pesquisa').addEventListener('click', alternarTelas);
  document.getElementById('btn-voltar').addEventListener('click', alternarTelas);
  document.getElementById('btn-fechar').addEventListener('click', alternarTelas);

  // Submit da consulta/pesquisa
  form2.addEventListener('submit', async e => {
    e.preventDefault();
    clearMessages();
    const resultado = await fazerRequisicao("/app/meuapp/cadastro/cons", {
      form: { [nomeFormCons]: getForm(nomeFormCons) }
    });
    if (!resultado.success) { definirMensagem('erro', resultado.error, false); return; }
    updateState(resultado.data);
    renderizarTabela(resultado.data.registros);
    AppLoader.hide();
  });

  // Event delegation — clique em "Selecionar" na tabela
  document.getElementById('tabela-corpo').addEventListener('click', async e => {
    if (!e.target.classList.contains('btn-selecionar')) return;
    const id = e.target.dataset.id;
    if (!id) { definirMensagem('aviso', 'Erro ao selecionar o registro'); return; }

    updateFormField(nomeFormCons, 'id_selecionado', id);
    const payload = { form: { [nomeFormCons]: structuredClone(getForm(nomeFormCons)) } };
    updateFormField(nomeFormCons, 'id_selecionado', null);

    const resultado = await fazerRequisicao("/app/meuapp/cadastro/cons", payload);
    if (!resultado.success) { definirMensagem('erro', resultado.error, false); return; }

    updateState(resultado.data);
    hidratarFormulario(nomeForm);
    setFormState(nomeForm, 'visualizar');
    alternarTelas();
    AppLoader.hide();
  });
});
```

**Fluxo completo após receber resposta do servidor:**
```
fazerRequisicao() → resultado.data
  └→ updateState(resultado.data)         // atualiza sisVar com form + mensagens
       ├→ Proxy dispara applyFormState() // controla botões e inputs automaticamente
       └→ Proxy dispara renderMensagens() // exibe alertas no #container-mensagens
  └→ hidratarFormulario(nomeForm)        // popula campos do DOM com dados da sisVar
```

---

## 8. FUNÇÕES PÚBLICAS DA `sisVar.js`

| Função | Uso |
|---|---|
| `getForm(formId)` | Lê o estado atual de um formulário (retorna `structuredClone`) |
| `getSchema(schemaId)` | Lê o schema de um formulário |
| `getUsuario()` | Retorna dados do usuário autenticado |
| `getCsrfToken()` | Retorna o CSRF token atual |
| `updateFormField(formId, campo, valor)` | Atualiza um campo individual na sisVar |
| `setFormState(formId, estado)` | Muda estado do form (`novo` / `editar` / `visualizar`) |
| `updateState(data)` | Mescla resposta JSON do servidor na sisVar inteira |
| `hidratarFormulario(formId)` | Preenche o DOM com os dados de `sisVar.form[formId].campos` |
| `clearMessages()` | Limpa todas as mensagens — **chamar sempre antes de nova requisição** |
| `definirMensagem(tipo, conteudo, ignorar)` | Define mensagem (`sucesso` / `erro` / `aviso` / `info`) |
| `renderMensagens()` | Renderiza as mensagens no `#container-mensagens` |
| `confirmar({titulo, mensagem, onConfirmar})` | Abre modal de confirmação global |

---

## 9. SISTEMA DE AUTENTICAÇÃO (Middleware JWT)

O `JWTAuthMiddleware` (`pages/usuario/middleware.py`) intercepta **todas** as requisições e:

1. Extrai o body JSON → `request.sisvar_front` (disponível em qualquer view)
2. Verifica `access_token` no cookie → autentica o `request.user`
3. Se expirado, tenta renovar via `refresh_token` automaticamente
4. Se não autorizado: redireciona para `/app/usuario/login/` (HTML) ou retorna `401` (API JSON)
5. Em **todas** as respostas JSON (incluindo erros), injeta `csrfToken` no payload automaticamente

**Rotas públicas** (sem autenticação) são configuradas no middleware:
```python
ROTAS_PUBLICAS = [
    "/app/usuario/login/",
    "/app/usuario/logout/",
    "/static/",
]
```
Para adicionar novas rotas públicas, inclua nessa lista.

---

## 10. VALIDAÇÃO DE FORMULÁRIOS

### Camada 1 — Back-end: `SchemaValidator` (`sac_base/form_validador.py`)

```python
from sac_base.form_validador import SchemaValidator

validator = SchemaValidator(schema[nomeForm])
if not validator.validate(campos):
    erros = [f"{c} - {', '.join(e)}" for c, e in validator.get_errors().items()]
    return JsonResponse({
        "mensagens": {"erro": {"conteudo": erros, "ignorar": False}}
    }, status=400)
```

**Tipos de validação suportados pelo schema:**

| Chave | Tipo do valor | O que valida |
|---|---|---|
| `required` | `bool` | Campo obrigatório |
| `type: 'string'` | — | Texto genérico |
| `type: 'password'` | — | Senha |
| `type: 'email'` | — | Formato de e-mail (`regex`) |
| `type: 'boolean'` | — | Deve ser `True` ou `False` |
| `type: 'integer'` | — | Número inteiro |
| `maxlength` | `int` | Tamanho máximo |
| `minlength` | `int` | Tamanho mínimo |

### Camada 2 — Regras de negócio (na própria view)

Após a validação de schema, implemente validações de negócio (duplicidade, consistência entre campos, etc.), retornando `JsonResponse` com `status=422`.

---

## 11. PADRÃO DE RESPOSTAS JSON

### Sucesso (POST)
```json
{
  "success": true,
  "form": {
    "cadMeuForm": {
      "estado": "visualizar",
      "update": "2026-03-24T10:00:00Z",
      "campos": { "id": 1, "campo1": "valor salvo" }
    }
  },
  "mensagens": {
    "sucesso": { "ignorar": true, "conteudo": ["Operação realizada com sucesso!"] }
  }
}
```

### Erro de validação (400/422)
```json
{
  "mensagens": {
    "erro": { "ignorar": false, "conteudo": ["campo1 - Este campo é obrigatório"] }
  }
}
```

> **`ignorar: false`** = mensagem não pode ser fechada pelo usuário (sem botão X).
> **`ignorar: true`** = mensagem tem botão X e pode ser dispensada.

---

## 12. BLOCOS DISPONÍVEIS EM `base.html`

| Bloco | Onde aparece | Uso |
|---|---|---|
| `{% block title %}` | `<title>` | Título da aba do navegador |
| `{% block estilo %}` | `<head>` | CSS específico da página — **usar sempre este bloco para `<link>` de CSS** |
| `{% block page_title %}` | `<h1>` no main | Título visível da página |
| `{% block content %}` | `<main>` | Conteúdo principal |
| `{% block scripts %}` | Antes de `</body>` | JS específico da página (`type="module"`) |

### Elementos globais já presentes em `base.html` (use direto, sem redeclarar):

| ID / Elemento | Responsável | Descrição |
|---|---|---|
| `#navbase` | `base.js` | Navbar — o `base.js` injeta o dropdown do usuário aqui |
| `#container-mensagens` | `sisVar.renderMensagens()` | Onde os alertas Bootstrap são exibidos |
| `#page-title-suffix` | `sisVar.applyFormState()` | Span após o `<h1>`, preenchido no estado `editar` |
| `#modal-confirmacao` | `sisVar.confirmar()` | Modal reutilizável de confirmação |
| `#global-loader` | `AppLoader.show/hide()` | Spinner global |
| Bootstrap 5.3.3 | CDN | CSS + JS já carregados |
| `static/js/base.js` | automático | Carregado por `base.html` em todas as páginas |
| `static/css/styles.css` | automático | CSS global carregado em todas as páginas |

---

## 13. DIRETRIZES DE LAYOUT — MOBILE FIRST

- Todo layout usa **Bootstrap 5 com abordagem Mobile First**
- Colunas começam em `col-12` (mobile) e expandem com `col-sm-*`, `col-md-*`, `col-lg-*`
- Campos de formulário são organizados em `<div class="container-md-3 my-3 mx-auto"> > <div class="row g-3">`
- Botões em mobile ficam empilhados (`d-grid gap-2`) e lado a lado em desktop (`d-md-flex`)
- Tabelas usam `table-responsive` para scroll horizontal em mobile

**Exemplo de campo Mobile First:**
```html
<div class="container-md-3 my-3 mx-auto">
  <div class="row g-3">
    <div class="col-12 col-sm-5">  <!-- 100% mobile, ~50% tablet+ -->
      <label class="form-label mb-0">Campo</label>
      <input type="text" name="campo" class="form-control smart-input" />
    </div>
  </div>
</div>
```

---

## 14. CRIANDO UM NOVO APP — CHECKLIST

```
1. [ ] python manage.py startapp <nome>
         → Mover a pasta gerada para pages/<nome>/

2. [ ] Registrar em INSTALLED_APPS: 'pages.<nome>'

3. [ ] Criar pages/<nome>/urls.py com urlpatterns

4. [ ] Incluir em sac_base/urls.py:
         path('app/', include('pages.<nome>.urls'))

5. [ ] Criar pages/<nome>/templates/<template>.html
         → {% extends "base.html" %}
         → Definir blocos: title, estilo, page_title, content, scripts
         → CSS em {% block estilo %}, nunca solto fora de bloco
         → Layout Mobile First: col-12 como base

6. [ ] Criar pages/<nome>/static/<nome>/js/scripts.js
         → Importar de /static/js/sisVar.js, base.js, input_rules.js, etc.
         → Chamar clearMessages() antes de toda requisição POST

7. [ ] Criar pages/<nome>/static/<nome>/css/styles.css

8. [ ] Implementar a view seguindo o padrão GET/POST (seção 4)

9. [ ] Definir schema na view (mesmos campos que o HTML e o JS)

10.[ ] Rotas públicas: adicionar em ROTAS_PUBLICAS no middleware se necessário
```

---

## 15. PREFERÊNCIAS DE USO DO COPILOT

### Antes de qualquer ação, sempre apresentar as opções disponíveis

Sempre que o usuário pedir uma ação que envolva escrita de código ou alterações no repositório, **pausar e apresentar as opções abaixo antes de executar**, no seguinte formato:

> **⚠️ Escolha como deseja proceder:**
>
> | Opção | Como funciona | Custo |
> |---|---|---|
> | ✍️ **githubwrite** | Commita os arquivos diretamente na branch/repo via ferramenta | ✅ Sem custo extra — **opção preferida** |
> | 💬 **Código no chat** | Gero o código aqui, o usuário aplica manualmente | ✅ Sem custo extra |
> | 🤖 **Copilot Agent** | Cria branch + PR de forma autônoma | ⚠️ Consome premium requests (limite 300/mês no plano Pro) |

### Regras obrigatórias

- **Nunca** usar o Copilot Coding Agent (PR automático) sem confirmação explícita do usuário.
- **Sempre** informar o custo/benefício de cada opção antes de agir.
- A opção preferida do usuário é **githubwrite** (commit direto, sem custo extra).
- Só usar o Copilot Agent se o usuário **explicitamente** escolher essa opção após ver as alternativas.

### Tabela de referência de custos

| Ação | Custo |
|---|---|
| Análise de código, relatórios, perguntas | ✅ Sem custo extra |
| Geração de código no chat | ✅ Sem custo extra |
| **githubwrite** (commit direto no repo) | ✅ Sem custo extra — **preferido** |
| **Copilot Coding Agent** (PR automático) | ⚠️ Consome premium requests |

## 16. PRINCÍPIO DE COMPORTAMENTO GLOBAL POR PADRÃO

### Regra obrigatória

> **Sempre que um comportamento precisar ocorrer em múltiplas páginas, ele deve ser implementado UMA ÚNICA VEZ em um arquivo global** — nunca repetido em cada `scripts.js` de página.

Antes de implementar qualquer lógica recorrente num script de página, pergunte:

> *"Isso pode ser resolvido em `sisVar.js`, `base.js`, `styles.css` ou `base.html`?"*

Se sim, implemente lá. Os scripts de página (`pages/<app>/static/<app>/js/scripts.js`) devem conter apenas lógica **específica** daquela página.

### Exemplos de aplicação

| Comportamento | Onde implementar | Por quê |
|---|---|---|
| Rolar para o topo ao exibir mensagens | `sisVar.js` → `renderMensagens()` | Toda mensagem passa por essa função via Proxy |
| Spinner de carregamento | `base.js` → `AppLoader` | Já é global; basta chamar `AppLoader.show/hide()` |
| Injeção do dropdown de usuário na navbar | `base.js` → `inicializarNavbarUsuario()` | Executado automaticamente em todas as páginas |
| Validação de inputs (máscaras, case) | `input_rules.js` | Ativado pela classe `smart-input` em qualquer input |
| Controle de visibilidade de botões por estado | `sisVar.js` → `applyFormState()` | Disparado pelo Proxy ao mudar `sisVar.form` |
| Exibição de alertas | `sisVar.js` → `renderMensagens()` | Disparado pelo Proxy ao mudar `sisVar.mensagens` |

### Exemplo concreto — scroll ao exibir mensagens

❌ **Errado** — repetir em cada `scripts.js`:
```javascript
// scripts.js de cada página
definirMensagem('erro', 'Campo obrigatório', false);
window.scrollTo({ top: 0, behavior: 'smooth' }); // repetido em todo lugar
```

✅ **Correto** — implementar uma vez em `sisVar.js`:
```javascript
// sisVar.js — função renderMensagens()
export function renderMensagens() {
  // ... renderização dos alertas ...
  if (temMensagemVisivel) {
    window.scrollTo({ top: 0, behavior: 'smooth' }); // global, automático
  }
}
```

### Hierarquia de arquivos globais

```
base.html          ← estrutura HTML + carrega Bootstrap, base.js, styles.css
  └── base.js      ← comportamentos globais de JS (navbar, AppLoader)
  └── sisVar.js    ← estado global + reações automáticas via Proxy
  └── input_rules.js ← regras de inputs (máscaras, case, allow/deny)
  └── styles.css   ← estilos globais
```

Qualquer lógica que deva funcionar em **todas as páginas sem configuração adicional** pertence a um desses arquivos.
