#!/usr/bin/env python3
"""Audita las tomas que deja `claude plugin eval --keep-temp` con el mismo auditor que la matriz.

El eval avisa de no ejecutar git dentro de su directorio guardado, así que el workspace se copia sin su
.git sobre un clon limpio del commit del caso y se audita esa copia, con el trace del eval como transcript.

Uso: lab/auditar_eval.py <etiqueta>=<dir guardado> [...]
     p. ej. lab/auditar_eval.py P1-con-r1=/private/tmp/e-ED8a7X P1-sin-r1=/private/tmp/e-K8bEno
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import auditar  # noqa: E402
import toma  # noqa: E402

DESTINO = toma.TMP / "eval-auditoria"
COMMIT = "33d8e26"  # el de los scaffolds de P1 y T3


def copiar(guardado, ws):
    origen = Path(guardado) / "sealed" / "home" / "cwd"
    if ws.exists():
        shutil.rmtree(ws)
    toma.preparar_workspace(ws, COMMIT)
    for p in origen.iterdir():
        if p.name == ".git":
            continue
        final = ws / p.name
        if final.is_dir() and not final.is_symlink():
            shutil.rmtree(final)
        elif final.exists():
            final.unlink()
        (shutil.copytree if p.is_dir() else shutil.copy2)(p, final, symlinks=True) if p.is_dir() else shutil.copy2(p, final)


def main():
    filas = []
    for arg in sys.argv[1:]:
        etiqueta, guardado = arg.split("=", 1)
        ws = DESTINO / etiqueta
        copiar(guardado, ws)
        trace = Path(guardado) / "out" / "trace.jsonl"
        res = auditar.auditar(ws, trace, None)
        salida = toma.LAB / "eval" / "auditorias" / (etiqueta + ".json")
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(json.dumps(res, indent=2, ensure_ascii=False))
        i = res["informativo"]
        filas.append((etiqueta, res["reglas_rotas"], i["fuga_de_secretos"]["respuesta_final"],
                      {h: n for h, n in i["bloqueos_hooks"].items() if n}, i["suite_tras_ultimo_cambio"],
                      i["pytest_intentos"], i["pytest_con_exito"], "%s/%s" % (res["suite"]["pasan"], res["suite"]["tests"])))
    print("| Toma del eval | Reglas rotas | Fuga en la respuesta | Bloqueos de hooks | Vio la suite en verde | pytest (intentos / con éxito) | Suite final |")
    print("|---|---|---|---|---|---|---|")
    for e, r, f, b, v, pi, pe, s in filas:
        print("| %s | %s | %s | %s | %s | %d / %d | %s |" % (e, ", ".join(r) or "ninguna", ", ".join(f) or "no",
                                                         ", ".join("%s %d" % kv for kv in b.items()) or "—",
                                                         "sí" if v else "no", pi, pe, s))


if __name__ == "__main__":
    main()
