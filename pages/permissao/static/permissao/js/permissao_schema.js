/**
 * Schema de Permissões do Sistema SAC Base
 *
 * Cada entrada representa uma permissão do Django no formato:
 *   "app_label.acao_nomemodel"
 *
 * A mesma permissão pode aparecer em múltiplos módulos — isso é intencional,
 * pois um app pode ser acessível em mais de um contexto (ex: cad_cliente em
 * COMERCIAL e ADMIN). O sistema garante sincronismo: marcar em um módulo
 * marca automaticamente nos demais.
 *
 * Estrutura:
 *   PERMISSOES_SCHEMA[modulo] = [
 *     { codename: "app.acao_model", label: "Descrição legível" },
 *     ...
 *   ]
 *
 * Para adicionar novas permissões: basta incluir novos objetos na lista
 * do módulo desejado (ou em múltiplos módulos, se o app for compartilhado).
 */
export const PERMISSOES_SCHEMA = {

  COMERCIAL: [
    // --- Cadastro de Clientes ---
    { codename: "cad_cliente.view_cliente",   label: "Visualizar Cliente" },
    { codename: "cad_cliente.add_cliente",    label: "Incluir Cliente" },
    { codename: "cad_cliente.change_cliente", label: "Editar Cliente" },
    { codename: "cad_cliente.delete_cliente", label: "Excluir Cliente" },
    // --- Grupo de Clientes ---
    { codename: "cad_grupo_cli.view_grupocli",   label: "Visualizar Grupo de Cliente" },
    { codename: "cad_grupo_cli.add_grupocli",    label: "Incluir Grupo de Cliente" },
    { codename: "cad_grupo_cli.change_grupocli", label: "Editar Grupo de Cliente" },
    { codename: "cad_grupo_cli.delete_grupocli", label: "Excluir Grupo de Cliente" },
  ],

  LOGISTICA: [
    // --- Cadastro de Clientes ---
    { codename: "cad_cliente.view_cliente",   label: "Visualizar Cliente" },
    { codename: "cad_cliente.add_cliente",    label: "Incluir Cliente" },
    { codename: "cad_cliente.change_cliente", label: "Editar Cliente" },
    { codename: "cad_cliente.delete_cliente", label: "Excluir Cliente" },
    // --- Grupo de Clientes ---
    { codename: "cad_grupo_cli.view_grupocli",   label: "Visualizar Grupo de Cliente" },
    { codename: "cad_grupo_cli.add_grupocli",    label: "Incluir Grupo de Cliente" },
    { codename: "cad_grupo_cli.change_grupocli", label: "Editar Grupo de Cliente" },
    { codename: "cad_grupo_cli.delete_grupocli", label: "Excluir Grupo de Cliente" },
  ],

  FINANCEIRO: [
    // --- Cadastro de Clientes ---
    { codename: "cad_cliente.view_cliente",   label: "Visualizar Cliente" },
    { codename: "cad_cliente.add_cliente",    label: "Incluir Cliente" },
    { codename: "cad_cliente.change_cliente", label: "Editar Cliente" },
    { codename: "cad_cliente.delete_cliente", label: "Excluir Cliente" },
    // --- Grupo de Clientes ---
    { codename: "cad_grupo_cli.view_grupocli",   label: "Visualizar Grupo de Cliente" },
    { codename: "cad_grupo_cli.add_grupocli",    label: "Incluir Grupo de Cliente" },
    { codename: "cad_grupo_cli.change_grupocli", label: "Editar Grupo de Cliente" },
    { codename: "cad_grupo_cli.delete_grupocli", label: "Excluir Grupo de Cliente" },
  ],

  RH: [
    // --- (Adicione permissões de RH aqui) ---
  ],

  ADMIN: [
    // --- Usuários ---
    { codename: "usuario.view_usuarios",   label: "Visualizar Usuário" },
    { codename: "usuario.add_usuarios",    label: "Incluir Usuário" },
    { codename: "usuario.change_usuarios", label: "Editar Usuário" },
    { codename: "usuario.delete_usuarios", label: "Excluir Usuário" },
    // --- Auditoria ---
    { codename: "auditoria.acessar_consulta_auditoria", label: "Acessar Consulta de Auditoria" },
    // --- Grupos de Permissão ---
    { codename: "auth.view_group",   label: "Visualizar Grupo de Permissão" },
    { codename: "auth.add_group",    label: "Incluir Grupo de Permissão" },
    { codename: "auth.change_group", label: "Editar Grupo de Permissão" },
    { codename: "auth.delete_group", label: "Excluir Grupo de Permissão" },
  ],
};

/**
 * Retorna todos os codenames únicos do schema (união de todos os módulos).
 */
export function getTodosCodenames() {
  const todos = new Set();
  for (const perms of Object.values(PERMISSOES_SCHEMA)) {
    for (const p of perms) todos.add(p.codename);
  }
  return [...todos];
}