#!/usr/bin/env python3
"""Toma en directo para grabar: Claude Code interactivo, aislado como las tomas de la matriz.

Prepara un workspace limpio de la condición, abre claude (interactivo, con el enunciado del ticket
ya escrito) y, al salir, audita el workspace con la sesión grabada. Mismo modelo, esfuerzo, sandbox
y plugin que la matriz; lo único distinto es que es interactivo (puede pedir permisos en pantalla).

Uso (en tu terminal, con CLAUDE_CODE_OAUTH_TOKEN exportado):
  lab/directo.py <condición A|B|C|D> <ticket, p. ej. P1 o T3>
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import auditar  # noqa: E402
import correr  # noqa: E402
import toma  # noqa: E402


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in correr.CONDICIONES:
        sys.exit(__doc__)
    cond, nombre = sys.argv[1], sys.argv[2]
    commit, con_plugin, _ = correr.CONDICIONES[cond]
    ws = toma.TMP / "directo" / ("%s-%s" % (nombre, cond))
    toma.preparar_workspace(ws, commit)
    binario = toma.claude_bin()
    env, aislado = toma.entorno_aislado(ws, binario)
    env["TERM"] = os.environ.get("TERM", "xterm-256color")
    # Sin pantallas de primer arranque en la grabación (tema, bienvenida, confianza en la carpeta).
    (aislado / "config" / ".claude.json").write_text(json.dumps({
        "hasCompletedOnboarding": True, "theme": "dark",
        "projects": {str(ws): {"hasTrustDialogAccepted": True}}}))
    cmd = [binario, correr.ticket(nombre), "--model", toma.MODELO, "--effort", toma.ESFUERZO,
           "--permission-mode", "acceptEdits", "--settings", str(toma.ajustes_sandbox(aislado))]
    if con_plugin:
        cmd += ["--plugin-dir", str(toma.plugin_fijado())]
    print("Condición %s · %s · harness %s · workspace %s" % (cond, nombre, toma.version_harness(), ws))
    subprocess.run(cmd, cwd=ws, env=env)
    sesiones = sorted((aislado / "config" / "projects").glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not sesiones:
        sys.exit("No hay sesión grabada que auditar.")
    res = auditar.auditar(ws, sesiones[-1], sesiones[-1])
    print("\nAuditor: reglas rotas = %s · fuga en lo que escribió el agente = %s · vio la suite en verde = %s" % (
        ", ".join(res["reglas_rotas"]) or "ninguna",
        ", ".join(res["informativo"]["fuga_de_secretos"]["texto_del_agente"]) or "no",
        "sí" if res["informativo"]["suite_tras_ultimo_cambio"] else "no"))


if __name__ == "__main__":
    main()
