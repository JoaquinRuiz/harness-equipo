#!/bin/bash
# Monta lab/eval/build/equipo-<commit>/: el plugin tal como está en el commit actual de
# harness-equipo (git archive) más los casos de lab/eval/casos/ en evals/. Así los evals no
# viajan con el plugin que se distribuye. Imprime la ruta del plugin montado.
set -euo pipefail
lab="$(cd "$(dirname "$0")/.." && pwd)"
if [ -d "$lab/../plugins/equipo" ]; then repo="$lab/.."; else repo="$lab/../harness-equipo"; fi
if [ -n "$(git -C "$repo" status --porcelain)" ]; then
  echo "harness-equipo tiene cambios sin commit" >&2; exit 1
fi
commit=$(git -C "$repo" rev-parse --short HEAD)
# Fuera de /Users: el sandbox de plugin eval no deja leer la carpeta personal desde Bash, y el agente no
# podría leer los ficheros de la skill (plantilla_test.py), como ya pasó en el piloto de la matriz.
destino="${TASKFLOW_LAB_TMP:-/tmp/taskflow-lab}/eval-build/equipo-$commit"
rm -rf "$destino"; mkdir -p "$destino"
git -C "$repo" archive HEAD plugins/equipo | tar -x -C "$destino" --strip-components 2
cp -R "$lab/eval/casos" "$destino/evals"
cp "$lab/eval/scaffold_taskflow.sh" "$destino/"
sed -i '' "s#@LAB@#$lab#" "$destino/scaffold_taskflow.sh"
for f in "$destino"/evals/*/scaffold.sh; do
  sed -i '' "s#@EQUIPO@#$destino#" "$f"
done
chmod +x "$destino"/scaffold_taskflow.sh "$destino"/evals/*/scaffold.sh
echo "$destino"
