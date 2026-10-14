#!/bin/bash
# SessionStart · Apunta en .git el commit en el que empieza la sesión. comprobar_reglas.py y la
# puerta de salida comparan con él, así que lo que el agente commitee no se les escapa.
py="${CLAUDE_PROJECT_DIR:-.}/.venv/bin/python"
[ -x "$py" ] || py=python3
"$py" "$(dirname -- "$0")/reglas.py" apuntar-inicio
exit 0
