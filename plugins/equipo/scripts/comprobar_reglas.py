#!/usr/bin/env python3
"""PostToolUse Edit|Write|Bash · R1 y R4 sobre el estado del proyecto tras cada cambio.

No mira qué herramienta se usó: revisa lo que git ve distinto del commit en el que empezó la
sesión (lo apunta inicio_de_sesion.sh; si falta, HEAD), esté commiteado o no y venga de un Edit,
de un Write o de un sed en Bash. Avisa (exit 2) con fichero, línea y cómo arreglarlo.
puerta_de_salida.sh lo vuelve a llamar al terminar, con --etiqueta puerta_de_salida.
"""
import json
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
from reglas import COMO_ARREGLAR, activo, commit_de_inicio, revisar_estado  # noqa: E402

if not activo(PROYECTO):
    sys.exit(0)  # repo sin el marcador .harness-equipo: el equipo no ha activado los hooks aquí

# De la entrada del hook solo hace falta la sesión: manda el estado, no la herramienta.
try:
    sesion = json.loads(sys.stdin.read() or "{}").get("session_id")
except ValueError:
    sesion = None
etiqueta = sys.argv[2] if sys.argv[1:2] == ["--etiqueta"] else "comprobar_reglas"

# Los imports de R4 solo se comprueban con el Python del .venv del proyecto: sin él no se sabe qué es
# biblioteca estándar ni qué arrastra requirements.txt, y se avisaría en falso. La falta del .venv la
# señala la puerta de salida.
con_venv = Path(sys.prefix).resolve() == VENV.parent.parent.resolve() and hasattr(sys, "stdlib_module_names")
hallazgos = revisar_estado(PROYECTO, commit_de_inicio(PROYECTO, sesion), comprobar_imports=con_venv)
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
