#!/bin/bash
# Qué ve alguien del equipo la primera vez que abre TaskFlow con Claude Code: clona la copia de
# publicación de TaskFlow (con .claude/settings.json y .harness-equipo) en un directorio temporal y abre
# claude en interactivo con una configuración vacía, sin mandar ningún mensaje.
#
# Por defecto simula a alguien que ya usa Claude Code (bienvenida y tema hechos), así que lo primero que
# aparece es lo del proyecto: confiar en la carpeta y la propuesta del marketplace y del plugin. Con
# --primera-vez, ni eso: Claude Code recién instalado.
#
# Uso (en tu terminal, con CLAUDE_CODE_OAUTH_TOKEN exportado):  lab/primera_apertura.sh [--primera-vez]
set -euo pipefail
lab="$(cd "$(dirname "$0")" && pwd)"
origen="${TASKFLOW_PUBLICACION:-$lab/../publicacion/taskflow}"
: "${CLAUDE_CODE_OAUTH_TOKEN:?Falta CLAUDE_CODE_OAUTH_TOKEN (claude setup-token y export)}"
base="${TASKFLOW_LAB_TMP:-/tmp/taskflow-lab}"; mkdir -p "$base"
limpio=$(mktemp -d "$base/primera-apertura.XXXX"); mkdir -p "$limpio/home" "$limpio/config"
git clone -q "$origen" "$limpio/taskflow"
echo "TaskFlow en $(git -C "$limpio/taskflow" log --oneline -1) · configuración vacía en $limpio"
ls -a "$limpio/taskflow/.claude" "$limpio/taskflow/.harness-equipo" | sed 's/^/  /'
if [ "${1:-}" != "--primera-vez" ]; then
  printf '{"hasCompletedOnboarding": true, "theme": "dark"}\n' > "$limpio/config/.claude.json"
fi
claude_bin=$(readlink -f "$(command -v claude)")
cd "$limpio/taskflow"
env -i PATH="/usr/bin:/bin" HOME="$limpio/home" CLAUDE_CONFIG_DIR="$limpio/config" LANG=es_ES.UTF-8 \
  TERM="${TERM:-xterm-256color}" CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN" "$claude_bin"
echo
echo "Al salir: git status del clon (tiene que estar limpio salvo lo que hayas aceptado tú):"
git status --short
echo "Plugins:"; env -i PATH="/usr/bin:/bin" HOME="$limpio/home" CLAUDE_CONFIG_DIR="$limpio/config" "$claude_bin" plugin list
