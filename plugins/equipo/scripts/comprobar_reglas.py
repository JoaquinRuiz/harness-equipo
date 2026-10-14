#!/usr/bin/env python3
"""PostToolUse Edit|Write|Bash · R1 y R4 sobre el estado del proyecto tras cada cambio.

No mira qué herramienta se usó: revisa lo que git ve distinto de HEAD (sea de un Edit, de
un Write o de un sed en Bash) y avisa (exit 2) con fichero, línea y cómo arreglarlo.
puerta_de_salida.sh lo vuelve a llamar al terminar, con --etiqueta puerta_de_salida.
"""
import os
import sys
from pathlib import Path

PROYECTO = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()

# Se ejecuta con el .venv del proyecto cuando existe: el cierre de requirements.txt
# se calcula con sus metadatos.
VENV = PROYECTO / ".venv" / "bin" / "python"
if VENV.exists() and Path(sys.prefix).resolve() != VENV.parent.parent.resolve():
    os.execv(str(VENV), [str(VENV), __file__] + sys.argv[1:])

sys.dont_write_bytecode = True  # no dejar __pycache__ junto a los scripts del plugin
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reglas import COMO_ARREGLAR, revisar_estado  # noqa: E402

if not sys.stdin.isatty():
    sys.stdin.read()  # la entrada del hook no hace falta: manda el estado, no la herramienta
etiqueta = sys.argv[2] if sys.argv[1:2] == ["--etiqueta"] else "comprobar_reglas"

hallazgos = revisar_estado(PROYECTO)
if not hallazgos:
    sys.exit(0)

print("[harness-equipo · %s] Reglas de la casa rotas en el estado actual:" % etiqueta, file=sys.stderr)
for regla, fichero, linea, motivo, texto in hallazgos:
    donde = "%s:%d" % (fichero, linea) if linea else fichero
    print("  [%s] %s  %s%s" % (regla, donde, motivo, "  ->  " + texto if texto else ""), file=sys.stderr)
print("Cómo arreglarlo:", file=sys.stderr)
for regla in sorted({h[0] for h in hallazgos}):
    print("  " + COMO_ARREGLAR[regla], file=sys.stderr)
sys.exit(2)
