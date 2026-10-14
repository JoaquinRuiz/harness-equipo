#!/usr/bin/env python3
"""Resumen de una tanda en el formato de resultados.md: por toma y por condición.

Reglas rotas, verificación (¿vio la suite en verde tras su último cambio?), fuga de secretos,
coste, tiempo, turnos, bloqueos de hooks, skill, commits y ruido del entorno.

Uso: lab/resumen_tanda.py <tanda>
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

LAB = Path(__file__).resolve().parent


def num(x, d=4):
    return ("%.*f" % (d, x)).replace(".", ",")


def main():
    tanda = sys.argv[1]
    filas = []
    for d in sorted((LAB / "tomas" / tanda).glob("*-r*"), key=lambda p: (p.name.split("-")[0], p.name.split("-")[2], p.name.split("-")[1])):
        if ".error" in d.name or not (d / "estado.json").exists():
            continue
        e = json.loads((d / "estado.json").read_text())
        a = json.loads((d / "auditoria.json").read_text())
        filas.append((e, a))
    print("| Toma | Turnos | Tiempo | Coste (USD) | Reglas rotas | Vio la suite en verde | Fuga en la respuesta | Bloqueos de hooks | Skill | Commits | Rechazos del entorno |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for e, a in filas:
        i = a["informativo"]
        print("| %s | %s | %s s | %s | %s | %s | %s | %s | %s | %d | %s |" % (
            e["toma"], e["turnos"], num(e["segundos"], 1), num(e["coste_usd"]), ", ".join(a["reglas_rotas"]) or "ninguna",
            "sí" if i["suite_tras_ultimo_cambio"] else "no", ", ".join(i["fuga_de_secretos"]["respuesta_final"]) or "no",
            ", ".join("%s %d" % kv for kv in e["bloqueos_hooks"].items()) or "—", e["usos_skill"] if e["condicion"] in "CD" else "—",
            len(i["commits_del_agente"]), "; ".join(x["motivo"][:50] for x in e["permisos_denegados"]) or "—"))
    print()
    print("| Condición | Tomas | Reglas rotas (tomas con alguna) | Por regla | Vio la suite en verde | Fuga en la respuesta | Turnos | Tiempo | Coste (USD) | Tomas con commit | Rechazos de comando | Rechazos de red |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    por = defaultdict(list)
    for e, a in filas:
        por[e["condicion"]].append((e, a))
    for c in sorted(por):
        g = por[c]
        reglas = defaultdict(int)
        for _, a in g:
            for r in a["reglas_rotas"]:
                reglas[r] += 1
        print("| %s | %d | %d | %s | %d de %d | %d de %d | %d | %s s | %s | %d | %d | %d |" % (
            c, len(g), sum(1 for _, a in g if a["reglas_rotas"]), ", ".join("%s %d" % kv for kv in sorted(reglas.items())) or "—",
            sum(1 for _, a in g if a["informativo"]["suite_tras_ultimo_cambio"]), len(g),
            sum(1 for _, a in g if a["informativo"]["fuga_de_secretos"]["respuesta_final"]), len(g),
            sum(e["turnos"] for e, _ in g), num(sum(e["segundos"] for e, _ in g), 1), num(sum(e["coste_usd"] for e, _ in g)),
            sum(1 for _, a in g if a["informativo"]["commits_del_agente"]),
            sum(1 for e, _ in g for x in e["permisos_denegados"] if x["herramienta"] != "SandboxNetworkAccess"),
            sum(1 for e, _ in g for x in e["permisos_denegados"] if x["herramienta"] == "SandboxNetworkAccess")))


if __name__ == "__main__":
    main()
