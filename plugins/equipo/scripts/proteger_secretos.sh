#!/bin/bash
# PreToolUse Read|Edit|Write · R5: el .env ni se lee ni se edita (el .env.example sí).
ruta=$(jq -r '.tool_input.file_path // empty')
if [ "$(basename -- "$ruta")" = ".env" ]; then
  cat >&2 <<MSG
[harness-equipo · proteger_secretos] Bloqueado: $ruta
El .env guarda los secretos locales de cada persona y no se lee ni se edita.
Cómo seguir: si necesitas una variable de configuración, léela en app/config.py con
os.environ.get("NOMBRE", <valor por defecto>) y documéntala en .env.example.
MSG
  exit 2
fi
exit 0
