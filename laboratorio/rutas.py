#!/usr/bin/env python3
"""Dónde está cada cosa del laboratorio.

Sirve igual en la carpeta de trabajo (lab/ junto a harness-equipo/ y taskflow/) que en el repo público
(laboratorio/ dentro de harness-equipo, con TaskFlow clonado al lado del repo o en TASKFLOW_REPO).
"""
import os
import shutil
import sys
from pathlib import Path

# El laboratorio necesita Python 3.10+ (sys.stdlib_module_names) y el mismo Python con el que se construyó
# el wheelhouse. Si el python3 del PATH es más viejo (el de macOS es 3.9), se relanza con el python3.x más
# nuevo que haya en el PATH, o con LAB_PYTHON.
if sys.version_info < (3, 10):
    candidatos = [os.environ.get("LAB_PYTHON")] + ["python3.%d" % m for m in range(20, 9, -1)]
    for c in candidatos:
        ruta = c and shutil.which(c)
        if ruta and sys.argv and sys.argv[0] not in ("", "-c"):
            os.execv(ruta, [ruta] + sys.argv)
    sys.exit("El laboratorio necesita Python 3.10 o posterior: instálalo o indica cuál con LAB_PYTHON.")

LAB = Path(__file__).resolve().parent
# Repo público: el plugin está en el repo que contiene el laboratorio; carpeta de trabajo: al lado.
HARNESS = LAB.parent if (LAB.parent / "plugins" / "equipo").is_dir() else LAB.parent / "harness-equipo"
PLUGIN = HARNESS / "plugins" / "equipo"
SCRIPTS = PLUGIN / "scripts"


def _taskflow():
    if os.environ.get("TASKFLOW_REPO"):
        return Path(os.environ["TASKFLOW_REPO"]).expanduser().resolve()
    for candidato in (LAB.parent / "taskflow", HARNESS.parent / "taskflow"):
        if candidato.is_dir():
            return candidato
    return HARNESS.parent / "taskflow"


TASKFLOW = _taskflow()
WHEELHOUSE = LAB / "wheelhouse"
ENV_PEGA = LAB / "env.pega"        # el .env de pega que se copia a cada toma (valores falsos, con canario)
SANDBOX = LAB / "sandbox.json"
# Fuera de la carpeta personal, que el sandbox no deja leer.
TMP = Path(os.environ.get("TASKFLOW_LAB_TMP", "/tmp/taskflow-lab")).resolve()
PYTHON = sys.executable              # crea los .venv de las tomas: tiene que casar con el wheelhouse


if __name__ == "__main__":
    # Para los scripts de shell: rutas.py --python | --taskflow
    print({"--python": PYTHON, "--taskflow": str(TASKFLOW)}.get(sys.argv[1] if len(sys.argv) > 1 else "", ""))
