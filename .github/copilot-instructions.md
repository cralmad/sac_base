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
