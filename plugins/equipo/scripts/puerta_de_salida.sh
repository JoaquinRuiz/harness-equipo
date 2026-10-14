#!/bin/bash
# Stop · R6, R1 y R4: no se da la tarea por cerrada mientras la suite falle o el estado
# final rompa una regla. Exit 2 = Claude sigue trabajando con este mensaje.
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
entrada=$(cat)  # comprobar_reglas.py la necesita para saber en qué commit empezó la sesión
py=.venv/bin/python
[ -x "$py" ] || py=python3
"$py" "$(dirname -- "$0")/reglas.py" activo || exit 0   # repo sin el marcador .harness-equipo
if [ ! -x .venv/bin/python ]; then
  cat >&2 <<MSG
[harness-equipo · puerta_de_salida] No encuentro .venv/bin/python en $PWD.
Cómo seguir: crea el entorno con python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
y vuelve a ejecutar .venv/bin/python -m pytest -q
MSG
  exit 2
fi
bloquear=0
salida=$(PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider 2>&1)
if [ $? -ne 0 ]; then
  {
    echo "[harness-equipo · puerta_de_salida] La suite no está en verde: no des la tarea por cerrada."
    echo "Cómo seguir: corrige el fallo (sin borrar ni desactivar tests) y vuelve a ejecutar"
    echo ".venv/bin/python -m pytest -q. Últimas líneas:"
    echo "$salida" | tail -n 25
  } >&2
  bloquear=1
fi
printf '%s' "$entrada" | "$(dirname -- "$0")/comprobar_reglas.py" --etiqueta puerta_de_salida || bloquear=1
[ "$bloquear" -eq 0 ] || exit 2
exit 0
