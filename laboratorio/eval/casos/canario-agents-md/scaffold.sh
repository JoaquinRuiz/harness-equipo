#!/bin/bash
# Canario: TaskFlow con su AGENTS.md (commit de B y C) y una palabra clave añadida al AGENTS.md que solo
# puede conocer quien lo tenga en el contexto. Con .venv, para que la puerta de salida del plugin no
# bloquee por falta de entorno (en la primera versión del canario lo hizo).
set -euo pipefail
"@EQUIPO@/scaffold_taskflow.sh" 33d8e26
printf '\nPalabra clave del proyecto: ARCOIRIS-7731.\n' >> AGENTS.md
echo "scaffold: AGENTS.md con la palabra clave en $PWD" >&2
