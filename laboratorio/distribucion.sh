#!/bin/bash
# Fase 6 · D14: instalar el harness del equipo desde cero, como lo haría alguien nuevo.
# CLAUDE_CONFIG_DIR y HOME vacíos (nada de tu configuración), marketplace desde el repo de
# harness-equipo en su etiqueta actual. Sin modelo: no gasta cuota.
#
# Uso: lab/distribucion.sh [origen]   (por defecto, la ruta local de harness-equipo)
set -euo pipefail
lab="$(cd "$(dirname "$0")" && pwd)"
if [ -d "$lab/../plugins/equipo" ]; then local_repo="$(cd "$lab/.." && pwd)"; else local_repo="$(cd "$lab/../harness-equipo" && pwd)"; fi
origen="${1:-$local_repo}"
mkdir -p "${TASKFLOW_LAB_TMP:-/tmp/taskflow-lab}"
limpio=$(mktemp -d "${TASKFLOW_LAB_TMP:-/tmp/taskflow-lab}/distribucion.XXXX")
mkdir -p "$limpio/home" "$limpio/config"
claude_bin=$(readlink -f "$(command -v claude)")
run() { env -i PATH="/usr/bin:/bin" HOME="$limpio/home" CLAUDE_CONFIG_DIR="$limpio/config" LANG=es_ES.UTF-8 "$claude_bin" "$@"; }

if [ -d "$origen" ]; then version="$(git -C "$origen" describe --tags 2>/dev/null)"; else version="la del repo en GitHub"; fi
echo "Configuración vacía en $limpio · origen: $origen · harness $version"
inicio=$(python3 -c 'import time; print(time.time())')
echo; echo '$ claude plugin marketplace add '"$origen"; run plugin marketplace add "$origen"
echo; echo '$ claude plugin install equipo@harness-equipo'; run plugin install equipo@harness-equipo
fin=$(python3 -c 'import time; print(time.time())')
echo; echo '$ claude plugin list'; run plugin list
echo; echo '$ claude plugin details equipo@harness-equipo'; run plugin details equipo@harness-equipo
python3 -c "print('\nD14 · marketplace add + install: %.1f s' % ($fin - $inicio))"
