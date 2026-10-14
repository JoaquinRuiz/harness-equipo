#!/usr/bin/env python3
"""Runner de la Fase 3: lanza tomas aisladas (claude -p) por ticket y condición, y las audita.

Condiciones (mismo modelo, esfuerzo, flags, sandbox y topes en todas):
  A  commit base, sin plugin          B  base + AGENTS.md, sin plugin
  C  base + AGENTS.md + plugin equipo D  commit base + plugin equipo

Cada toma deja en lab/tomas/<tanda>/<ticket>-<condición>-r<n>/: comando.json, transcript.jsonl,
sesion.jsonl, stderr.txt, resumen.json, auditoria.json y estado.json.

Reanudable: una toma con estado.json terminado no se repite. Una toma con error de ejecución
se archiva como <dir>.error<k> y se repite al relanzar. La tanda se para si:
  - una toma acaba en error de ejecución (límite de uso del plan, API, red…);
  - una toma pasa del techo de coste estimado (--techo-usd; no se le pasa a claude);
  - el aislamiento o la carga del AGENTS.md no son los esperados.
Llegar al tope de turnos o de tiempo no es error: la toma se audita tal cual.

Uso (en tu terminal, con CLAUDE_CODE_OAUTH_TOKEN exportado):
  lab/correr.py --tanda piloto --tickets T2 --condiciones B C
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import auditar  # noqa: E402
import toma  # noqa: E402

CONDICIONES = {
    "A": (toma.COMMIT_BASE, False, False),
    "B": (toma.COMMIT_AGENTS, False, True),
    "C": (toma.COMMIT_AGENTS, True, True),
    "D": (toma.COMMIT_BASE, True, False),
}  # (commit, plugin, AGENTS.md)
TERMINADOS = ("ok", "tope_turnos", "tope_tiempo")
# Haiku 4.5 no admite --effort: se lanza sin él (y sin heredar ningún esfuerzo del entorno, por env -i).
MODELOS = {"sonnet-5.5": (toma.MODELO, toma.ESFUERZO), "haiku-4.5": ("claude-haiku-4-5-20251001", None)}
AISLAMIENTO = json.loads((toma.LAB / "aislamiento.json").read_text())


def ticket(nombre):
    ficheros = sorted((toma.LAB / "tickets").glob(nombre + "-*.md"))
    if len(ficheros) != 1:
        sys.exit("No encuentro un único ticket %s en lab/tickets/" % nombre)
    return ficheros[0].read_text().strip()


def clasificar(ejecucion, datos):
    """Estado de la toma: ok, tope_turnos, tope_tiempo o error_ejecucion (con motivo)."""
    r = datos.get("result")
    if ejecucion["timeout"]:
        return "tope_tiempo", "proceso parado al llegar al tope de tiempo"
    if not r:
        return "error_ejecucion", "sin evento result (código de salida %s)" % ejecucion["codigo_salida"]
    if r.get("subtype") == "error_max_turns":
        return "tope_turnos", "llegó a --max-turns"
    if r.get("is_error") or r.get("subtype") != "success":
        texto = str(r.get("result") or r.get("subtype"))
        if any(m in texto.lower() for m in ("usage limit", "limit reached", "rate limit", "quota")):
            return "error_ejecucion", "límite de uso del plan: " + texto[:200]
        return "error_ejecucion", texto[:300]
    return "ok", ""


def verificar(cond, salida, datos, modelo):
    """Problemas de aislamiento o de carga del AGENTS.md; lista vacía si todo es lo esperado."""
    commit, con_plugin, con_agents = CONDICIONES[cond]
    problemas, init = [], datos.get("init") or {}
    if not init:
        return ["sin evento init"]
    if init.get("model") != modelo:
        problemas.append("modelo %s" % init.get("model"))
    if init.get("claude_code_version") != AISLAMIENTO["claude_code_version"]:
        problemas.append("Claude Code %s (la base de aislamiento es de %s)" % (
            init.get("claude_code_version"), AISLAMIENTO["claude_code_version"]))
    if init.get("mcp_servers"):
        problemas.append("servidores MCP: %s" % init["mcp_servers"])
    plugins = {p.get("name") for p in init.get("plugins") or []}
    esperados = set(AISLAMIENTO["plugins_de_serie"]) | ({"equipo"} if con_plugin else set())
    if plugins != esperados:
        problemas.append("plugins %s (esperados %s)" % (sorted(plugins), sorted(esperados)))
    skills = set(init.get("skills") or [])
    extra = skills - set(AISLAMIENTO["skills_de_serie"]) - ({"equipo:nuevo-endpoint"} if con_plugin else set())
    if extra:
        problemas.append("skills ajenas: %s" % sorted(extra))
    cargado = agents_md_en_contexto(salida / "sesion.jsonl")
    if cargado != con_agents:
        problemas.append("AGENTS.md %s en el contexto" % ("presente" if cargado else "ausente"))
    return problemas


def agents_md_en_contexto(sesion):
    """True si el AGENTS.md llegó al contexto por carga automática (no por un Read del agente)."""
    if not sesion.exists():
        return False
    for ev in auditar.leer_eventos(sesion):
        mensaje = ev.get("message") if isinstance(ev.get("message"), dict) else {}
        contenido = mensaje.get("content")
        if isinstance(contenido, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in contenido):
            continue
        if AISLAMIENTO["frase_agents_md"] in json.dumps(ev, ensure_ascii=False):
            return True
    return False


def usos_skill(transcript):
    usos, _, _, _ = auditar.leer_transcript(transcript)
    return sum(1 for u in usos if u.get("name") == "Skill"
               and (u.get("input") or {}).get("skill") == "equipo:nuevo-endpoint")


def correr_toma(tanda, nombre_ticket, cond, rep, args):
    salida = toma.LAB / "tomas" / tanda / ("%s-%s-r%d" % (nombre_ticket, cond, rep))
    estado_json = salida / "estado.json"
    if estado_json.exists():
        previo = json.loads(estado_json.read_text())
        if previo["estado"] in TERMINADOS:
            print("== %s: ya hecha (%s), se salta" % (salida.name, previo["estado"]))
            return previo
        k = 1
        while salida.with_name(salida.name + ".error%d" % k).exists():
            k += 1
        salida.rename(salida.with_name(salida.name + ".error%d" % k))
    commit, con_plugin, _ = CONDICIONES[cond]
    ws = toma.TMP / tanda / salida.name
    toma.montar(ws, commit, con_plugin)
    print("== %s: lanzando…" % salida.name, flush=True)
    modelo, esfuerzo = MODELOS[args.modelo]
    ejecucion = toma.lanzar(ws, ticket(nombre_ticket), salida, con_plugin=con_plugin,
                            max_turnos=args.max_turnos, timeout_s=args.timeout_s,
                            modelo=modelo, esfuerzo=esfuerzo)
    datos = dict(ejecucion, **toma.resumen_transcript(salida / "transcript.jsonl"), workspace=str(ws))
    (salida / "resumen.json").write_text(json.dumps(datos, indent=2, ensure_ascii=False))
    estado, motivo = clasificar(ejecucion, datos)
    sesion = salida / "sesion.jsonl"
    auditoria = auditar.auditar(ws, salida / "transcript.jsonl", sesion if sesion.exists() else None)
    (salida / "auditoria.json").write_text(json.dumps(auditoria, indent=2, ensure_ascii=False))
    r = datos.get("result") or {}
    info = auditoria["informativo"]
    registro = {
        "toma": salida.name, "ticket": nombre_ticket, "condicion": cond, "repeticion": rep,
        "estado": estado, "motivo": motivo, "harness": toma.version_harness(),
        "modelo": modelo, "esfuerzo": esfuerzo,
        "verificaciones": verificar(cond, salida, datos, modelo),
        "turnos": r.get("num_turns"), "segundos": ejecucion["segundos_reloj"],
        "coste_usd": r.get("total_cost_usd"), "reglas_rotas": auditoria["reglas_rotas"],
        "suite": "%s/%s" % (auditoria["suite"]["pasan"], auditoria["suite"]["tests"]),
        "bloqueos_hooks": {h: n for h, n in info.get("bloqueos_hooks", {}).items() if n},
        "tope_stop": info.get("tope_stop_alcanzado"), "usos_skill": usos_skill(salida / "transcript.jsonl"),
        "permisos_denegados": info.get("permisos_denegados", []),
        # Ruido del entorno: rechazos de Claude Code ajenos a las reglas de la casa (comprobaciones de
        # seguridad de comandos, p. ej. «expansion obfuscation») y peticiones de red fuera de PyPI.
        "rechazos_entorno": {
            "comando": sum(1 for d in info.get("permisos_denegados", []) if d["herramienta"] != "SandboxNetworkAccess"),
            "red": sum(1 for d in info.get("permisos_denegados", []) if d["herramienta"] == "SandboxNetworkAccess"),
        },
        "instalaciones": info.get("instalaciones", []), "commits_del_agente": info.get("commits_del_agente", []),
        "r3_indeterminados": info.get("r3_indeterminados", []),
    }
    estado_json.write_text(json.dumps(registro, indent=2, ensure_ascii=False))
    print("   %(estado)s turnos=%(turnos)s %(segundos)ss coste=%(coste_usd)s USD rotas=%(reglas_rotas)s "
          "suite=%(suite)s bloqueos=%(bloqueos_hooks)s skill=%(usos_skill)s" % registro, flush=True)
    for clave in ("verificaciones", "permisos_denegados", "instalaciones", "commits_del_agente", "r3_indeterminados"):
        if registro[clave]:
            print("   %s: %s" % (clave, json.dumps(registro[clave], ensure_ascii=False)[:500]))
    return registro


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--tanda", required=True)
    a.add_argument("--tickets", nargs="+", required=True)
    a.add_argument("--condiciones", nargs="+", required=True, choices=list(CONDICIONES))
    a.add_argument("--repeticiones", type=int, default=1)
    a.add_argument("--modelo", choices=list(MODELOS), default="sonnet-5.5")
    a.add_argument("--max-turnos", type=int, required=True)
    a.add_argument("--timeout-s", type=int, required=True)
    a.add_argument("--techo-usd", type=float, required=True, help="coste estimado por toma que para la tanda")
    args = a.parse_args()
    for t in args.tickets:
        ticket(t)

    dir_tanda = toma.LAB / "tomas" / args.tanda
    dir_tanda.mkdir(parents=True, exist_ok=True)
    modelo, esfuerzo = MODELOS[args.modelo]
    config = {"modelo": modelo, "esfuerzo": esfuerzo, "max_turnos": args.max_turnos,
              "timeout_s": args.timeout_s, "techo_usd": args.techo_usd, "sandbox": json.loads(toma.SANDBOX.read_text())}
    previa = dir_tanda / "tanda.json"
    if previa.exists():
        anterior = json.loads(previa.read_text())
        if {k: anterior.get(k) for k in config} != config:
            sys.exit("La tanda %s ya existe con otra configuración: usa otro nombre de tanda." % args.tanda)
    previa.write_text(json.dumps(dict(config, harness=toma.version_harness()), indent=2, ensure_ascii=False))
    print("tanda %s · %s%s · harness-equipo %s · %d turnos · %d s · techo %.2f USD" % (
        args.tanda, modelo, " --effort " + esfuerzo if esfuerzo else " (sin --effort)", toma.version_harness(),
        args.max_turnos, args.timeout_s, args.techo_usd), flush=True)

    total = 0.0
    for rep in range(1, args.repeticiones + 1):
        for t in args.tickets:
            for cond in args.condiciones:
                reg = correr_toma(args.tanda, t, cond, rep, args)
                total += reg.get("coste_usd") or 0
                if reg["estado"] == "error_ejecucion":
                    sys.exit("PARADA: error de ejecución en %s (%s). Relanza el mismo comando para repetirla."
                             % (reg["toma"], reg["motivo"]))
                if reg["verificaciones"]:
                    sys.exit("PARADA: %s no cumple el aislamiento esperado: %s" % (reg["toma"], reg["verificaciones"]))
                if (reg.get("coste_usd") or 0) > args.techo_usd:
                    sys.exit("PARADA: %s costó %.4f USD estimados, más que el techo de %.2f"
                             % (reg["toma"], reg["coste_usd"], args.techo_usd))
    print("tanda %s terminada · coste estimado de lo lanzado en esta ejecución: %.4f USD" % (args.tanda, total))


if __name__ == "__main__":
    main()
