#!/usr/bin/env python3
"""Vuelve a auditar las tomas de una o varias tandas con el auditor actual.

Guarda la auditoría anterior como auditoria.<etiqueta>.json e imprime, por tanda, las reglas rotas
antes y después. Uso: lab/reauditar.py <etiqueta-de-lo-anterior> <tanda> [<tanda> ...]
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
import auditar  # noqa: E402
import rutas  # noqa: E402

LAB = Path(__file__).resolve().parent
TMP = rutas.TMP


def main():
    etiqueta, tandas = sys.argv[1], sys.argv[2:]
    for tanda in tandas:
        antes, despues, cambios = Counter(), Counter(), []
        tomas = sorted(d for d in (LAB / "tomas" / tanda).glob("*-r*") if ".error" not in d.name and (d / "auditoria.json").exists())
        for d in tomas:
            viejo = json.loads((d / "auditoria.json").read_text())
            sesion = d / "sesion.jsonl"
            nuevo = auditar.auditar(TMP / tanda / d.name, d / "transcript.jsonl", sesion if sesion.exists() else None)
            guardado = d / ("auditoria.%s.json" % etiqueta)
            if not guardado.exists():
                guardado.write_text(json.dumps(viejo, indent=2, ensure_ascii=False))
            (d / "auditoria.json").write_text(json.dumps(nuevo, indent=2, ensure_ascii=False))
            cond = d.name.split("-")[1]
            for r in viejo["reglas_rotas"]:
                antes[(cond, r)] += 1
            for r in nuevo["reglas_rotas"]:
                despues[(cond, r)] += 1
            if viejo["reglas_rotas"] != nuevo["reglas_rotas"]:
                cambios.append("%s: %s → %s" % (d.name, ",".join(viejo["reglas_rotas"]) or "ninguna",
                                                 ",".join(nuevo["reglas_rotas"]) or "ninguna"))
        def fmt(c):
            return ", ".join("%s %s=%d" % (k[0], k[1], v) for k, v in sorted(c.items())) or "ninguna"
        print("%s · %d tomas · antes: %s · después: %s" % (tanda, len(tomas), fmt(antes), fmt(despues)))
        for c in cambios:
            print("   " + c)


if __name__ == "__main__":
    main()
