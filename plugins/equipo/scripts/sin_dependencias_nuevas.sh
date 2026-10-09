#!/bin/bash
# PreToolUse Edit|Write · R4: ninguna dependencia nueva.
ruta=$(jq -r '.tool_input.file_path // empty')
nombre=$(basename -- "$ruta")
lista="$(dirname -- "$0")/ficheros_dependencias.txt"
while IFS= read -r patron; do
  case "$patron" in ''|'#'*) continue ;; esac
  # shellcheck disable=SC2053  # el patrón se compara como glob a propósito
  if [[ "$nombre" == $patron ]]; then
    cat >&2 <<MSG
[harness-equipo · sin_dependencias_nuevas] Bloqueado: $ruta
En TaskFlow no se añaden dependencias sin aprobación del equipo.
Cómo seguir: resuélvelo con la biblioteca estándar o deja la propuesta en el resumen
para que alguien la apruebe.
MSG
    exit 2
  fi
done < "$lista"
exit 0
