#!/usr/bin/env python3
"""PostToolUse Edit|Write · R1: el acceso a datos solo a través del repositorio.

Compara el fichero editado con su versión en HEAD y avisa (exit 2) si añade acceso a
datos fuera de app/repositories/, app/models/ y app/extensions.py.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

PROYECTO = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()

# Se ejecuta con el .venv del proyecto cuando existe.
VENV = PROYECTO / ".venv" / "bin" / "python"
if VENV.exists() and Path(sys.prefix).resolve() != VENV.parent.parent.resolve():
    os.execv(str(VENV), [str(VENV), __file__] + sys.argv[1:])

sys.dont_write_bytecode = True  # no dejar __pycache__ junto a los scripts del plugin
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reglas_taskflow import accesos_nuevos, r1_aplica  # noqa: E402

entrada = json.load(sys.stdin)
ruta = Path(entrada.get("tool_input", {}).get("file_path", ""))
if not ruta.is_absolute():
    ruta = Path(entrada.get("cwd", PROYECTO)) / ruta
try:
    rel = ruta.resolve().relative_to(PROYECTO).as_posix()
except ValueError:
    sys.exit(0)
if not r1_aplica(rel) or not ruta.exists():
    sys.exit(0)

base = subprocess.run(["git", "show", "HEAD:" + rel], cwd=PROYECTO,
                      capture_output=True, text=True)
nuevos = accesos_nuevos(base.stdout if base.returncode == 0 else "", ruta.read_text())
if not nuevos:
    sys.exit(0)

print("[harness-equipo · comprobar_capas] Acceso a datos fuera del repositorio:", file=sys.stderr)
for linea, motivo, texto in nuevos:
    print("  %s:%d  %s  ->  %s" % (rel, linea, motivo, texto), file=sys.stderr)
print("Cómo arreglarlo: mueve la consulta a un método con type hints del repositorio de la\n"
      "entidad (app/repositories/<entidad>_repository.py, exportado en app/repositories/\n"
      "__init__.py) y llama a ese método desde aquí. Fuera de la capa de datos no se importa\n"
      "db, sqlalchemy ni sqlite3, ni se usa .session, .query o .execute.", file=sys.stderr)
sys.exit(2)
