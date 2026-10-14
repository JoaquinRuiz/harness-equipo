#!/bin/bash
# Reconstruye lab/wheelhouse: las ruedas de requirements.txt de TaskFlow y todo lo que arrastran, para el
# mismo Python que usa el laboratorio (el que elige rutas.py). Las tomas instalan su .venv desde aquí, sin red.
set -euo pipefail
lab="$(cd "$(dirname "$0")" && pwd)"
py=$("$lab/rutas.py" --python)
taskflow=$("$lab/rutas.py" --taskflow)
"$py" -m pip wheel -q -r "$taskflow/requirements.txt" -w "$lab/wheelhouse"
echo "wheelhouse para $("$py" --version) en $lab/wheelhouse"
