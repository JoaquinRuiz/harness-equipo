#!/bin/bash
# PreToolUse Read|Edit|Write|Bash · R5: el .env ni se lee ni se edita (el .env.example sí).
# Quien decide es reglas.py: la misma expresión que usa el auditor. Un comando que recorre
# el .env sin nombrarlo (grep -r) no se puede ver aquí; eso lo detecta el auditor.
py="${CLAUDE_PROJECT_DIR:-.}/.venv/bin/python"
[ -x "$py" ] || py=python3
if que=$("$py" "$(dirname -- "$0")/reglas.py" toca-env); then
  cat >&2 <<MSG
[harness-equipo · proteger_secretos] Bloqueado: $que
El .env guarda los secretos locales de cada persona y no se lee ni se edita, tampoco
desde la terminal. Cómo seguir: las variables que existen están en .env.example; si
necesitas una nueva, léela en app/config.py con os.environ.get("NOMBRE", <valor por
defecto>) y documéntala en .env.example.
MSG
  exit 2
fi
exit 0
