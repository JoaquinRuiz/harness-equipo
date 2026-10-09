#!/bin/bash
# Stop · R6: la suite tiene que estar en verde antes de dar la tarea por cerrada.
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
if [ ! -x .venv/bin/python ]; then
  cat >&2 <<MSG
[harness-equipo · suite_en_verde] No encuentro .venv/bin/python en $PWD.
Cómo seguir: crea el entorno con python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
y vuelve a ejecutar .venv/bin/python -m pytest -q
MSG
  exit 2
fi
salida=$(PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider 2>&1)
if [ $? -ne 0 ]; then
  {
    echo "[harness-equipo · suite_en_verde] La suite no está en verde: no des la tarea por cerrada."
    echo "Cómo seguir: corrige el fallo (sin borrar ni desactivar tests) y vuelve a ejecutar"
    echo ".venv/bin/python -m pytest -q. Últimas líneas:"
    echo "$salida" | tail -n 25
  } >&2
  exit 2
fi
exit 0
