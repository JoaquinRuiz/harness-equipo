#!/usr/bin/env python3
"""Reproduce en la terminal una toma grabada, paso a paso, para grabarla (G01, G03).

Muestra el enunciado, cada llamada a herramienta con el principio de su resultado y la respuesta
final. Resalta en rojo lo que toca el .env y los secretos del .env que aparecen; en verde, la skill
nuevo-endpoint y los avisos de los hooks.

Uso: lab/ver_toma.py <tanda>/<toma> [--pausa 0.6] [--lineas 4]
     p. ej. lab/ver_toma.py inocente/P1-A-r3
"""
import argparse
import json
import re
import shutil
import sys
import textwrap
import time
from pathlib import Path

sys.dont_write_bytecode = True
import auditar  # noqa: E402
import rutas  # noqa: E402

LAB = Path(__file__).resolve().parent
ROJO, VERDE, GRIS, NEGRITA, FIN = "\033[1;31m", "\033[1;32m", "\033[90m", "\033[1m", "\033[0m"
FONDO_ROJO = "\033[41;97m"


def resaltar(texto, secretos):
    for valor in secretos:
        texto = texto.replace(valor, FONDO_ROJO + valor + FIN)
    return texto


def main():
    a = argparse.ArgumentParser()
    a.add_argument("toma")
    a.add_argument("--pausa", type=float, default=0.6)
    a.add_argument("--lineas", type=int, default=4)
    args = a.parse_args()
    d = LAB / "tomas" / args.toma
    base = json.loads((LAB / "base.json").read_text())
    secretos = list(base["secretos_env"].values())
    ancho = min(shutil.get_terminal_size().columns, 110)
    estado = json.loads((d / "estado.json").read_text())
    usos, resultados, _, eventos = auditar.leer_transcript(d / "transcript.jsonl")
    denegadas = {x["tool_use_id"]: x["motivo"] for x in estado.get("permisos_denegados", [])}
    enunciado = next((e["message"]["content"] for e in auditar.leer_eventos(d / "sesion.jsonl")
                      if e.get("type") == "user" and isinstance((e.get("message") or {}).get("content"), str)), "")
    cond = {"A": "sin AGENTS.md ni plugin", "B": "con AGENTS.md", "C": "con AGENTS.md y plugin equipo",
            "D": "con plugin equipo"}[estado["condicion"]]
    print("%sToma %s · condición %s (%s) · %s%s" % (NEGRITA, estado["toma"], estado["condicion"], cond,
                                                   estado.get("modelo", "claude-sonnet-5-5"), FIN))
    print("%s> %s%s\n" % (NEGRITA, enunciado.strip(), FIN))
    for uso in usos:
        time.sleep(args.pausa)
        nombre, entrada = uso.get("name"), uso.get("input") or {}
        detalle = entrada.get("command") or entrada.get("file_path") or entrada.get("skill") or json.dumps(entrada, ensure_ascii=False)
        ws = str(rutas.TMP / args.toma.split("/")[0] / estado["toma"])
        detalle = re.sub(r"^cd %s\s*(;|&&|\n)\s*" % re.escape(ws), "", detalle.strip()).replace(ws + "/", "")
        color = ROJO if auditar.apunta_a_env(uso) else VERDE if nombre == "Skill" else ""
        primera = detalle.strip().splitlines()[0] if detalle.strip() else ""
        print("%s● %s %s%s" % (color, nombre, primera[:ancho - 10], FIN))
        es_error, texto = resultados.get(uso.get("id"), (False, ""))
        texto = texto.replace(ws + "/", "")
        if uso.get("id") in denegadas:   # el motivo corto de Claude Code, no el mensaje entero
            texto = "Denegado por Claude Code: " + denegadas[uso.get("id")]
        marca_hook = "[harness-equipo · " in texto
        lineas = [l for l in texto.strip().splitlines() if l.strip()]
        con_secreto = [l for l in lineas if any(s in l for s in secretos)]
        # Si el resultado trae secretos del .env, se enseñan esas líneas (es lo que hay que ver).
        lineas = (["…"] + con_secreto) if con_secreto and con_secreto[0] not in lineas[:args.lineas] else lineas[:args.lineas]
        for l in lineas:
            l = resaltar(l[:ancho - 6], secretos)
            print("  %s⎿ %s%s" % (VERDE if marca_hook else GRIS, l, FIN))
    time.sleep(args.pausa)
    final = next((e.get("result", "") for e in eventos if e.get("type") == "result"), "")
    print("\n%sRespuesta final%s" % (NEGRITA, FIN))
    for parrafo in final.strip().splitlines():
        # Sin cortar por guiones: «pega-no-real» partido en dos líneas ya no se resaltaría.
        for l in textwrap.wrap(parrafo, ancho, break_on_hyphens=False, break_long_words=False) or [""]:
            print(resaltar(l, secretos))
    aud = json.loads((d / "auditoria.json").read_text())
    print("\n%sAuditor: reglas rotas = %s · fuga en la respuesta = %s%s" % (
        NEGRITA, ", ".join(aud["reglas_rotas"]) or "ninguna",
        ", ".join(aud["informativo"]["fuga_de_secretos"]["respuesta_final"]) or "no", FIN))


if __name__ == "__main__":
    main()
