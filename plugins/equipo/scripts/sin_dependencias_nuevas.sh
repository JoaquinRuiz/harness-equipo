#!/bin/bash
# PreToolUse Edit|Write · R4: los ficheros de dependencias no se editan.
# Lo que llegue por otro camino (Bash, pip…) lo ven comprobar_reglas.py y la puerta de salida.
py="${CLAUDE_PROJECT_DIR:-.}/.venv/bin/python"
[ -x "$py" ] || py=python3
if ruta=$("$py" "$(dirname -- "$0")/reglas.py" es-dependencias); then
  cat >&2 <<MSG
[harness-equipo · sin_dependencias_nuevas] Bloqueado: $ruta
En TaskFlow no se añaden dependencias sin aprobación del equipo.
Cómo seguir: resuélvelo con la biblioteca estándar o deja la propuesta en el resumen
para que alguien la apruebe.
MSG
  exit 2
fi
exit 0
