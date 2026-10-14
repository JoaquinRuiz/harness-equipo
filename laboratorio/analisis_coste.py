#!/usr/bin/env python3
"""De dónde sale el sobrecoste de C frente a B en una tanda.

Todo sale de lo grabado en cada toma (sesion.jsonl, transcript.jsonl) y del workspace final:
- ejecuciones de cada hook: llamadas a herramientas que casan con su matcher (PostToolUse solo
  cuenta las que terminaron sin error) y, para el Stop, los stop_hook_summary con su durationMs;
- latencia de cada llamada a herramienta (de tool_use a tool_result, incluye los hooks Pre y Post),
  para comparar B y C por tipo de herramienta;
- turnos y tiempo por categoría de llamada (skill, tests de repositorio, otros tests, pytest, código,
  exploración); el tiempo de un paso va del resultado anterior al resultado de esta llamada;
- tests añadidos por fichero, contando funciones test_* del workspace final frente al commit base.

Uso: lab/analisis_coste.py <tanda>
"""
import ast
import json
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import rutas  # noqa: E402

LAB = rutas.LAB
TMP = rutas.TMP
MATCHERS = {
    "proteger_secretos (Pre)": {"Read", "Edit", "Write", "Bash"},
    "sin_dependencias_nuevas (Pre)": {"Edit", "Write"},
    "comprobar_reglas (Post)": {"Edit", "Write", "Bash"},
}


def ts(e):
    return datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).timestamp()


def llamadas(sesion):
    """[(id, nombre, input, t_uso, t_resultado, es_error)] en orden de resultado."""
    usos, resultados, inicio, fin = {}, {}, None, None
    for linea in sesion.read_text().splitlines():
        e = json.loads(linea)
        if "timestamp" not in e or e.get("type") not in ("assistant", "user"):
            continue
        inicio = inicio or ts(e)
        fin = ts(e)
        contenido = (e.get("message") or {}).get("content")
        if not isinstance(contenido, list):
            continue
        for b in contenido:
            if b.get("type") == "tool_use":
                usos[b["id"]] = (b["name"], b.get("input") or {}, ts(e))
            elif b.get("type") == "tool_result":
                resultados[b["tool_use_id"]] = (ts(e), bool(b.get("is_error")))
    filas = [(i, n, inp, t, resultados[i][0], resultados[i][1]) for i, (n, inp, t) in usos.items() if i in resultados]
    return sorted(filas, key=lambda f: f[4]), inicio, fin


RE_RUTA = re.compile(r"(?:app|tests)/[\w/]+\.py")
RE_ESCRITURA = re.compile(r"\.write\(|write_text|open\([^)]*['\"][wa]|sed -i|>>?\s*\S+\.py|cat\s*>|tee ")


def destino(rutas):
    if not rutas:
        return None
    if all(r.endswith("tests/test_repositories.py") for r in rutas):
        return "tests de repositorio"
    if all("tests/" in r for r in rutas):
        return "otros tests"
    if all("tests/" not in r for r in rutas):   # app/, config, .env.example…
        return "código"
    return "mixto (código y tests en la misma llamada)"


def categoria(nombre, entrada):
    """Categoría de una llamada según lo que toca. Una lectura de varios ficheros es exploración;
    una escritura cuenta según los ficheros que escribe; si escribe código y tests a la vez, «mixto»."""
    texto = json.dumps(entrada, ensure_ascii=False)
    if nombre == "Skill" or "/skills/nuevo-endpoint" in texto:
        return "skill"
    if nombre == "Bash" and "pytest" in texto:
        return "pytest"
    if nombre in ("Edit", "Write"):
        return destino([entrada.get("file_path", "")]) or "exploración"
    if nombre == "Read":
        return "tests de repositorio" if entrada.get("file_path", "").endswith("tests/test_repositories.py") else "exploración"
    if nombre == "Bash":
        comando = entrada.get("command", "")
        if RE_ESCRITURA.search(comando):
            return destino(set(RE_RUTA.findall(comando))) or "exploración"
        rutas = set(RE_RUTA.findall(comando))
        if rutas and all(r.endswith("tests/test_repositories.py") for r in rutas):
            return "tests de repositorio"
    return "exploración"


def tokens_por_mensaje(sesion):
    """[(categorías con peso, tokens de entrada, tokens de salida)] por mensaje del modelo.

    Un mensaje se guarda en varias líneas (una por bloque) con el mismo id y el mismo uso: se cuenta
    una vez. Un mensaje sin llamadas (el resumen final) va a «cierre»."""
    mensajes = {}
    for linea in sesion.read_text().splitlines():
        e = json.loads(linea)
        if e.get("type") != "assistant":
            continue
        m = e["message"]
        dato = mensajes.setdefault(m["id"], {"uso": m.get("usage") or {}, "cats": []})
        for b in m.get("content") or []:
            if b.get("type") == "tool_use":
                dato["cats"].append(categoria(b["name"], b.get("input") or {}))
    salida = []
    for dato in mensajes.values():
        u = dato["uso"]
        entrada = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
        cats = Counter(dato["cats"] or ["cierre (resumen final y Stop)"])
        n = sum(cats.values())
        salida.append(({k: v / n for k, v in cats.items()}, entrada, u.get("output_tokens", 0)))
    return salida


def tests_por_fichero(ws, commit):
    def cuenta(codigo):
        try:
            return sum(1 for n in ast.walk(ast.parse(codigo))
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_"))
        except SyntaxError:
            return 0
    añadidos = {}
    for f in sorted((ws / "tests").glob("test_*.py")):
        rel = "tests/" + f.name
        base = subprocess.run(["git", "-C", str(ws), "show", "%s:%s" % (commit, rel)], capture_output=True, text=True)
        n = cuenta(f.read_text()) - (cuenta(base.stdout) if base.returncode == 0 else 0)
        if n:
            añadidos[f.name] = n
    return añadidos


def main():
    tanda = sys.argv[1]
    dir_tanda = LAB / "tomas" / tanda
    tomas = {}
    for d in sorted(dir_tanda.glob("T*-r*")):
        if ".error" in d.name or not (d / "estado.json").exists():
            continue
        estado = json.loads((d / "estado.json").read_text())
        if estado["condicion"] not in ("B", "C"):
            continue
        filas, inicio, fin = llamadas(d / "sesion.jsonl")
        stops = [h["durationMs"] for linea in (d / "sesion.jsonl").read_text().splitlines()
                 for e in [json.loads(linea)] if e.get("subtype") == "stop_hook_summary"
                 for h in e.get("hookInfos", [])]
        ws = TMP / tanda / d.name
        commit = subprocess.run(["git", "-C", str(ws), "merge-base", "HEAD", "origin/main"],
                                capture_output=True, text=True).stdout.strip()
        tomas[d.name] = dict(estado=estado, filas=filas, inicio=inicio, fin=fin, stops=stops,
                             tests=tests_por_fichero(ws, commit))

    print("## Sobrecoste de C frente a B (%s)\n" % tanda)
    print("### Ejecuciones de hooks en C\n")
    print("| Toma | " + " | ".join(MATCHERS) + " | puerta_de_salida (Stop) |")
    print("|---|" + "---|" * (len(MATCHERS) + 1))
    total = Counter()
    stop_ms = []
    for nombre, t in tomas.items():
        if t["estado"]["condicion"] != "C":
            continue
        celdas = []
        for hook, herramientas in MATCHERS.items():
            n = sum(1 for _, h, _, _, _, err in t["filas"] if h in herramientas and not ("Post" in hook and err))
            total[hook] += n
            celdas.append(str(n))
        stop_ms += t["stops"]
        total["stop"] += len(t["stops"])
        celdas.append("%d (%s ms)" % (len(t["stops"]), ", ".join(str(m) for m in t["stops"])))
        print("| %s | %s |" % (nombre, " | ".join(celdas)))
    print("| **Total** | %s | %d (%.1f s) |\n" % (" | ".join(str(total[h]) for h in MATCHERS), total["stop"], sum(stop_ms) / 1000))

    print("### Latencia de cada llamada (tool_use → tool_result; en C incluye los hooks Pre y Post)\n")
    print("| Herramienta | B: llamadas | B: mediana | C: llamadas | C: mediana | C − B (mediana) |")
    print("|---|---|---|---|---|---|")
    lat = defaultdict(lambda: defaultdict(list))
    for t in tomas.values():
        for _, h, _, tu, tr, _ in t["filas"]:
            lat[h][t["estado"]["condicion"]].append(tr - tu)
    for h in sorted(lat):
        b, c = lat[h].get("B", []), lat[h].get("C", [])
        mb = statistics.median(b) if b else None
        mc = statistics.median(c) if c else None
        print("| %s | %d | %s | %d | %s | %s |" % (
            h, len(b), "%.2f s" % mb if mb is not None else "—", len(c), "%.2f s" % mc if mc is not None else "—",
            "%+.2f s" % (mc - mb) if mb is not None and mc is not None else "—"))

    print("\n### Llamadas y tiempo por categoría (suma de las 5 tomas)\n")
    print("| Categoría | B: llamadas | B: tiempo | C: llamadas | C: tiempo |")
    print("|---|---|---|---|---|")
    cat = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))
    for t in tomas.values():
        cond, previo = t["estado"]["condicion"], t["inicio"]
        for _, h, inp, _, tr, _ in t["filas"]:
            c = cat[categoria(h, inp)][cond]
            c[0] += 1
            c[1] += max(tr - previo, 0)
            previo = max(previo, tr)
        c = cat["cierre (resumen final y Stop)"][cond]
        c[1] += max(t["fin"] - previo, 0)
    orden = ["skill", "exploración", "código", "tests de repositorio", "otros tests",
             "mixto (código y tests en la misma llamada)", "pytest", "cierre (resumen final y Stop)"]
    for k in orden:
        b, c = cat[k]["B"], cat[k]["C"]
        print("| %s | %d | %.1f s | %d | %.1f s |" % (k, b[0], b[1], c[0], c[1]))

    print("\n### Tokens por categoría (suma de las 5 tomas; uso de cada mensaje del modelo, repartido entre sus llamadas)\n")
    print("| Categoría | B: entrada (incl. caché) | B: salida | C: entrada (incl. caché) | C: salida |")
    print("|---|---|---|---|---|")
    tok = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for nombre, t in tomas.items():
        cond = t["estado"]["condicion"]
        for categoria_msg, entrada, salida in tokens_por_mensaje(LAB / "tomas" / tanda / nombre / "sesion.jsonl"):
            for k, peso in categoria_msg.items():
                tok[k][cond][0] += entrada * peso
                tok[k][cond][1] += salida * peso
    for k in orden:
        b, c = tok[k]["B"], tok[k]["C"]
        print("| %s | %d | %d | %d | %d |" % (k, b[0], b[1], c[0], c[1]))
    tb = [sum(tok[k]["B"][i] for k in orden) for i in (0, 1)]
    tc = [sum(tok[k]["C"][i] for k in orden) for i in (0, 1)]
    print("| **Total** | %d | %d | %d | %d |" % (tb[0], tb[1], tc[0], tc[1]))

    print("\n### Tests añadidos por ticket\n")
    print("| Ticket | B | C |")
    print("|---|---|---|")
    por_ticket = defaultdict(dict)
    for nombre, t in tomas.items():
        por_ticket[t["estado"]["ticket"]][t["estado"]["condicion"]] = t["tests"]
    for ticket in sorted(por_ticket):
        fila = []
        for cond in "BC":
            tests = por_ticket[ticket].get(cond)
            fila.append("—" if tests is None else "%d (%s)" % (sum(tests.values()), ", ".join(
                "%s +%d" % (f, n) for f, n in tests.items())))
        print("| %s | %s | %s |" % (ticket, fila[0], fila[1]))


if __name__ == "__main__":
    main()
