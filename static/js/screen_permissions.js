export function buttonVisibleByState(button, state) {
  return (button?.dataset?.showOn || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .includes(state);
}

export function createActionChecker({ screenKey, getScreenPermissions, fallback }) {
  return (action) => Boolean(getScreenPermissions(screenKey, fallback)?.[action]);
}

export function buttonAllowedByPermission({ buttonId, state, canExecute }) {
  if (buttonId === "btn-novo") {
    return canExecute("incluir");
  }

  if (buttonId === "btn-editar") {
    return canExecute("editar");
  }

  if (buttonId === "btn-excluir") {
    return canExecute("excluir");
  }

  if (buttonId === "btn-salvar" || buttonId === "btn-cancelar") {
    if (state === "novo") {
      return canExecute("incluir");
    }

    if (state === "editar") {
      return canExecute("editar");
    }
  }

  return true;
}