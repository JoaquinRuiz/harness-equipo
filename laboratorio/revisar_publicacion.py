#!/usr/bin/env python3
"""Monta la copia pública del repo en un directorio aparte y la revisa antes de publicar.

  lab/revisar_publicacion.py montar <destino>   # copia lo que se publica (no toca los repos de trabajo)
  lab/revisar_publicacion.py revisar <destino>  # busca datos personales; exit 1 si encuentra alguno

Qué se busca: rutas de /Users, el usuario y el nombre de esta máquina (se leen al ejecutar, no se
escriben aquí), correos fuera de la lista de permitidos, y cualquier patrón extra de
~/.config/publicacion/prohibido.txt (uno por línea; fuera del repo, para no publicar la propia lista).
También revisa autor y committer de cada commit del destino, si es un repo git.
"""
import getpass
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import rutas  # noqa: E402

LAB = rutas.LAB
CORREOS_PERMITIDOS = re.compile(r"@(example\.com|laboratorio\.invalid|db\.interno\.example)$|^noreply@|^x@x\.com$")
LAB_PUBLICO = [
    "auditar.py", "calibrar.py", "correr.py", "toma.py", "prueba_hooks.py", "reglas_escritas.py",
    "analisis_coste.py", "resumen_tanda.py", "reauditar.py", "ver_toma.py", "directo.py",
    "demo_commit.sh", "distribucion.sh", "revisar_publicacion.py", "rutas.py", "auditar_eval.py",
    "construir_wheelhouse.sh", "env.pega",
    "reglas.md", "sandbox.json", "aislamiento.json", "resultados.md", "analisis_pasada1.md",
    "grabaciones.md", "distribucion_proyecto.md", "tickets", "eval/casos", "eval/preparar.sh",
    "eval/scaffold_taskflow.sh",
]


def montar(destino):
    """Clon de harness-equipo con su historia y sus etiquetas (las usan demo_commit.sh y la distribución)
    más laboratorio/ con lo que se publica del laboratorio. El commit de laboratorio/ lo haces tú."""
    destino = Path(destino)
    if destino.exists():
        shutil.rmtree(destino)
    subprocess.run(["git", "clone", "-q", str(rutas.HARNESS), str(destino)], check=True)
    subprocess.run(["git", "-C", str(destino), "remote", "remove", "origin"], check=True)
    for rel in LAB_PUBLICO:
        origen, final = LAB / rel, destino / "laboratorio" / rel
        final.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if origen.is_dir() else shutil.copy2)(origen, final)
    print("Montado en %s: harness-equipo con historia y etiquetas + laboratorio/ sin commitear" % destino)


def patrones():
    usuario, maquina = getpass.getuser(), socket.gethostname().split(".")[0]
    lista = [("ruta de /Users", re.compile("/" + "Users/")),
             ("usuario de la máquina", re.compile(r"\b%s\b" % re.escape(usuario))),
             ("nombre de la máquina", re.compile(re.escape(maquina), re.I))]
    extra = Path.home() / ".config" / "publicacion" / "prohibido.txt"
    if extra.exists():
        for linea in extra.read_text().splitlines():
            if linea.strip():
                lista.append(("patrón de prohibido.txt", re.compile(re.escape(linea.strip()), re.I)))
    return lista


def revisar(destino):
    destino = Path(destino)
    hallazgos = []
    for f in sorted(destino.rglob("*")):
        if not f.is_file() or ".git" in f.parts:
            continue
        try:
            texto = f.read_text()
        except UnicodeDecodeError:
            hallazgos.append((f, 0, "fichero binario (¿debe publicarse?)", ""))
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            for motivo, patron in patrones():
                if patron.search(linea):
                    hallazgos.append((f, n, motivo, linea.strip()[:120]))
            for correo in re.findall(r"(?<![\\\w.%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[a-z]{2,}", linea):
                if not CORREOS_PERMITIDOS.search(correo):
                    hallazgos.append((f, n, "correo", correo))
    if (destino / ".git").exists():
        # Lo que ya está commiteado también se publica: se revisa toda la historia.
        revisiones = subprocess.run(["git", "-C", str(destino), "rev-list", "--all"], capture_output=True,
                                    text=True).stdout.split()
        for motivo, patron in patrones():
            r = subprocess.run(["git", "-C", str(destino), "grep", "-I", "-n", "-P"] + (["-i"] if patron.flags & re.I else []) + [patron.pattern] + revisiones,
                               capture_output=True, text=True)
            for linea in r.stdout.splitlines()[:20]:
                hallazgos.append((destino / ".git", 0, "historia: " + motivo, linea[:120]))
        autores = subprocess.run(["git", "-C", str(destino), "log", "--all", "--format=%an <%ae>%n%cn <%ce>"],
                                 capture_output=True, text=True).stdout.split("\n")
        for autor in sorted(set(a for a in autores if a)):
            hallazgos.append((destino / ".git", 0, "autor de commits (revisar)", autor))
    for f, n, motivo, texto in hallazgos:
        print("%s:%s  %s  %s" % (f.relative_to(destino) if f != destino / ".git" else ".git", n, motivo, texto))
    print("\n%d hallazgos" % len(hallazgos))
    return 1 if any(m != "autor de commits (revisar)" for _, _, m, _ in hallazgos) else 0


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("montar", "revisar"):
        sys.exit(__doc__)
    if sys.argv[1] == "montar":
        montar(sys.argv[2])
    else:
        sys.exit(revisar(sys.argv[2]))
