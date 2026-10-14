#!/bin/bash
# Demostración para el vídeo (sin modelo): un agente mete una consulta en la vista (R1), hace
# commit e intenta terminar. Con v0.2.0 la puerta de salida le deja irse; con v0.3.0, no.
#
# Uso: lab/demo_commit.sh            (tarda unos 30 s; todo ocurre en /tmp/taskflow-lab/demo-commit)
set -uo pipefail
lab="$(cd "$(dirname "$0")" && pwd)"
if [ -d "$lab/../plugins/equipo" ]; then repo="$lab/.."; else repo="$lab/../harness-equipo"; fi
base="${TASKFLOW_LAB_TMP:-/tmp/taskflow-lab}/demo-commit"
rm -rf "$base"; mkdir -p "$base"
negrita=$(tput bold 2>/dev/null || true); normal=$(tput sgr0 2>/dev/null || true)

for version in v0.2.0 v0.3.0; do
  echo; echo "${negrita}=== harness-equipo $version ===${normal}"
  plugin="$base/plugin-$version"; ws="$base/taskflow-$version"
  mkdir -p "$plugin"
  git -C "$repo" archive "$version" plugins/equipo | tar -x -C "$plugin" --strip-components 2
  "$lab/toma.py" preparar "$ws" 33d8e26 || exit 1
  export CLAUDE_PROJECT_DIR="$ws"
  entrada='{"session_id": "demo-commit", "cwd": "'"$ws"'"}'
  cd "$ws"
  if [ -x "$plugin/scripts/inicio_de_sesion.sh" ]; then
    echo "$entrada" | "$plugin/scripts/inicio_de_sesion.sh"
    echo "\$ SessionStart: inicio_de_sesion.sh apunta el commit $(git rev-parse --short HEAD)"
  fi
  echo "\$ el agente mete db.session.query(Tag) en app/views/tags.py"
  sed -i '' -e 's/^from app.repositories import TagRepository/from app.extensions import db\
from app.models.task import Tag\
from app.repositories import TagRepository/' \
    -e 's/tags = TagRepository.list_ordered()/tags = db.session.query(Tag).order_by(Tag.name).all()/' app/views/tags.py
  echo "\$ git commit -am 'Consulta directa en list_tags'"
  git commit -qam "Consulta directa en list_tags"
  echo "\$ el agente intenta terminar (Stop → puerta_de_salida.sh)"
  echo "$entrada" | "$plugin/scripts/puerta_de_salida.sh"
  codigo=$?
  if [ "$codigo" -eq 2 ]; then
    echo "${negrita}→ exit 2: la puerta NO le deja terminar${normal}"
  else
    echo "${negrita}→ exit $codigo: la puerta le deja terminar con R1 rota y commiteada${normal}"
  fi
  cd "$lab"
done
