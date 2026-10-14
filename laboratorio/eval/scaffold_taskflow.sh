#!/bin/bash
# Scaffold de los casos de eval: TaskFlow en el commit del caso, en el directorio actual (el
# workspace del caso), preparado igual que una toma del laboratorio (.venv del wheelhouse, .env de
# pega, pip.conf e identidad de git neutra). @LAB@ lo sustituye lab/eval/preparar.sh.
set -euo pipefail
commit="$1"
"@LAB@/toma.py" preparar "$PWD" "$commit"
# Desde v0.3.1 los hooks solo actúan con el marcador; los commits del laboratorio no lo llevan.
[ -f .harness-equipo ] || printf '# Activa los hooks del plugin equipo (scaffold del eval).\n' > .harness-equipo
echo "scaffold: TaskFlow en $commit preparado en $PWD" >&2
