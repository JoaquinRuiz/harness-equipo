#!/bin/bash
# Fase 6 · Alcance de proyecto: alguien del equipo clona TaskFlow e instala el harness solo para ese repo.
# Configuración vacía (nada tuyo), TaskFlow y harness-equipo desde GitHub. Sin modelo: no gasta cuota.
#
# Uso: lab/distribucion_proyecto.sh
set -euo pipefail
base="${TASKFLOW_LAB_TMP:-/tmp/taskflow-lab}"; mkdir -p "$base"
limpio=$(mktemp -d "$base/proyecto.XXXX"); mkdir -p "$limpio/home" "$limpio/config" "$limpio/otro-proyecto"
claude_bin=$(readlink -f "$(command -v claude)")
run() { env -i PATH="/usr/bin:/bin" HOME="$limpio/home" CLAUDE_CONFIG_DIR="$limpio/config" LANG=es_ES.UTF-8 "$claude_bin" "$@"; }
ahora() { python3 -c 'import time; print(time.time())'; }

echo "Configuración vacía en $limpio"
# Fijado en d51fdc3 (marcador, sin .claude/settings.json): después de ese commit el settings.json ya viene
# hecho en main y la demo dejaría de enseñar el momento «?? .claude/».
echo; echo '$ git clone https://github.com/JoaquinRuiz/taskflow.git && git checkout d51fdc3'
git clone -q https://github.com/JoaquinRuiz/taskflow.git "$limpio/taskflow"
cd "$limpio/taskflow"
git -c advice.detachedHead=false checkout -q d51fdc3
echo "  marcador del equipo en la raíz: $(ls .harness-equipo)"
inicio=$(ahora)
echo; echo '$ claude plugin marketplace add JoaquinRuiz/harness-equipo --scope project'
run plugin marketplace add JoaquinRuiz/harness-equipo --scope project
echo; echo '$ claude plugin install equipo@harness-equipo --scope project'
run plugin install equipo@harness-equipo --scope project
fin=$(ahora)
echo; echo '$ cat .claude/settings.json   (lo que el equipo commitea)'; cat .claude/settings.json
echo; echo '$ git status --short'; git status --short
echo; echo '$ claude plugin list   (dentro de TaskFlow)'; run plugin list
echo; echo '$ claude plugin list   (en otro proyecto)'; (cd "$limpio/otro-proyecto" && run plugin list)
python3 -c "print('\nAlcance de proyecto · marketplace add + install: %.1f s' % ($fin - $inicio))"
