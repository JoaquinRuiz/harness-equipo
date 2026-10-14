#!/usr/bin/env python3
"""Prepara un workspace limpio de TaskFlow y lanza una toma aislada con claude -p.

Aislamiento por toma:
- env -i: solo PATH, LANG, HOME y CLAUDE_CONFIG_DIR temporales y CLAUDE_CODE_OAUTH_TOKEN
  (lo exportas tú en tu terminal; aquí solo se pasa al proceso hijo, nunca se escribe);
- workspace fuera de $HOME (rutas.TMP, /tmp/taskflow-lab por defecto), clonado del commit pedido;
- Bash dentro del sandbox de Claude Code (lab/sandbox.json): escritura solo en el
  workspace, red solo hacia PyPI y sin lectura de la carpeta personal; ningún comando puede
  salir del sandbox (allowUnsandboxedCommands: false). Las reglas permissions.allow de
  sandbox.json evitan que python, pip install, pytest y flask pidan una aprobación que en
  -p nadie puede dar.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import rutas
from rutas import ENV_PEGA, LAB, PLUGIN, PYTHON, SANDBOX, TASKFLOW, TMP, WHEELHOUSE  # noqa: F401

COMMIT_BASE = "4b04714ffa64e47d56905f5e8013c3576bb8fcd4"      # sin AGENTS.md
COMMIT_AGENTS = "33d8e26"                                       # base + AGENTS.md

# pip 26 verifica TLS con truststore (Security.framework de macOS), que dentro del sandbox falla
# con OSStatus -26276; legacy-certs vuelve a su fichero de certificados (diagnóstico en
# prueba_hooks/sandbox_pip). Sin aviso de versión nueva de pip, que invita a instalar.
PIP_CONF = "[global]\nuse-deprecated = legacy-certs\ndisable-pip-version-check = true\n"

MODELO = "claude-sonnet-5-5"
ESFUERZO = "medium"


def claude_bin():
    ruta = shutil.which("claude")
    if not ruta:
        raise SystemExit("No encuentro claude en el PATH")
    return str(Path(ruta).resolve())


def version_harness():
    """Commit de harness-equipo con el que corre la toma; «-sucio» si hay cambios sin commit."""
    repo = PLUGIN.parent.parent
    commit = subprocess.run(["git", "-C", str(repo), "describe", "--tags", "--long", "--always", "--dirty=-sucio"],
                            capture_output=True, text=True).stdout.strip()
    return commit or "desconocido"


def plugin_fijado():
    """Copia del plugin tal como está en el commit actual de harness-equipo, fuera de la carpeta personal.

    El sandbox no deja leer la carpeta personal (denyRead): con --plugin-dir apuntando al repo, el agente
    de C no podía leer desde Bash los ficheros de la skill (plantilla_test.py). La copia sale de
    git archive, así que además fija exactamente la versión con la que corre la tanda.
    """
    repo = PLUGIN.parent.parent
    if version_harness().endswith("-sucio"):
        raise SystemExit("harness-equipo tiene cambios sin commit: haz commit antes de lanzar tomas")
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    destino = TMP / "harness-equipo" / commit
    if not (destino / "plugins" / "equipo").exists():
        destino.mkdir(parents=True, exist_ok=True)
        archivo = subprocess.run(["git", "-C", str(repo), "archive", "HEAD", "plugins/equipo"],
                                 capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(destino)], input=archivo, check=True)
    return destino / "plugins" / "equipo"


def preparar_workspace(destino, commit):
    if destino.exists():
        shutil.rmtree(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    poblar_workspace(destino, commit)


def poblar_workspace(destino, commit):
    """TaskFlow en `commit` dentro de `destino` (vacío o no; lo usa también el scaffold de los evals)."""
    destino.mkdir(parents=True, exist_ok=True)
    if any(destino.iterdir()):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "clone", "-q", str(TASKFLOW), tmp + "/c"], check=True)
            shutil.copytree(tmp + "/c", destino, symlinks=True, dirs_exist_ok=True)
    else:
        subprocess.run(["git", "clone", "-q", str(TASKFLOW), str(destino)], check=True)
    subprocess.run(["git", "-C", str(destino), "checkout", "-q", "-B", "main", commit], check=True)
    # Ninguna configuración de Claude Code del proyecto: un .claude/settings.json (como el que trae la cabeza
    # de TaskFlow para el equipo) activaría el plugin en A o B y contaminaría la condición.
    shutil.rmtree(destino / ".claude", ignore_errors=True)
    for nombre in ("CLAUDE.md", "CLAUDE.local.md"):
        if (destino / nombre).exists():
            raise SystemExit("%s en el commit %s: el laboratorio no lo espera" % (nombre, commit))
    # Identidad neutra para los commits que haga el agente (sin ella, git usa el usuario y el nombre
    # de la máquina, que acabarían en los transcripts).
    for clave, valor in (("user.name", "Agente del laboratorio"), ("user.email", "agente@laboratorio.invalid")):
        subprocess.run(["git", "-C", str(destino), "config", clave, valor], check=True)
    shutil.copy(ENV_PEGA, destino / ".env")
    subprocess.run([PYTHON, "-m", "venv", str(destino / ".venv")], check=True)
    subprocess.run([str(destino / ".venv/bin/pip"), "install", "-q", "--no-index", "--find-links",
                    str(WHEELHOUSE), "-r", str(destino / "requirements.txt")], check=True,
                   env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
    (destino / ".venv" / "pip.conf").write_text(PIP_CONF)


def ajustes_sandbox(aislado):
    """sandbox.json con la carpeta personal de quien lanza la toma añadida a denyRead."""
    ajustes = json.loads(SANDBOX.read_text())
    leer = ajustes["sandbox"].setdefault("filesystem", {}).setdefault("denyRead", [])
    if str(Path.home()) not in leer:
        leer.append(str(Path.home()))
    ruta = aislado / "ajustes-sandbox.json"
    ruta.write_text(json.dumps(ajustes, indent=2, ensure_ascii=False))
    return ruta


def entorno_aislado(ws, binario):
    """Entorno de una toma: env -i con HOME y CLAUDE_CONFIG_DIR vacíos y el token del usuario."""
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if not token:
        raise SystemExit("Falta CLAUDE_CODE_OAUTH_TOKEN en el entorno (claude setup-token y export)")
    aislado = ws.parent / (ws.name + "-aislado")
    if aislado.exists():  # ni sesiones ni caché de una toma anterior
        shutil.rmtree(aislado)
    for d in ("home", "config"):
        (aislado / d).mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:" + str(Path(binario).parent),
        "LANG": "es_ES.UTF-8",
        "HOME": str(aislado / "home"),
        "CLAUDE_CONFIG_DIR": str(aislado / "config"),
        "CLAUDE_CODE_OAUTH_TOKEN": token,
    }
    return env, aislado


def lanzar(ws, prompt, salida, con_plugin, max_turnos, timeout_s, modelo=MODELO, esfuerzo=ESFUERZO):
    """Lanza claude -p en `ws`. Escribe transcript.jsonl y stderr.txt en `salida`."""
    binario = claude_bin()
    env, aislado = entorno_aislado(ws, binario)
    cmd = [binario, "-p", prompt, "--model", modelo] + (["--effort", esfuerzo] if esfuerzo else []) + [
           "--permission-mode", "acceptEdits", "--permission-prompts", "none",
           "--output-format", "stream-json", "--verbose",
           "--max-turns", str(max_turnos), "--settings", str(ajustes_sandbox(aislado))]
    # Sin --max-budget-usd: el agente vería su presupuesto en cada turno (adjunto budget_usd).
    # El techo de coste lo vigila quien lanza la tanda, al terminar cada toma.
    if con_plugin:
        cmd += ["--plugin-dir", str(plugin_fijado())]
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "comando.json").write_text(json.dumps(
        {"cmd": cmd, "cwd": str(ws), "env": sorted(env), "harness": version_harness()},
        indent=2, ensure_ascii=False))
    inicio = time.time()
    with open(salida / "transcript.jsonl", "w") as out, open(salida / "stderr.txt", "w") as err:
        proc = subprocess.Popen(cmd, cwd=ws, env=env, stdout=out, stderr=err, stdin=subprocess.DEVNULL)
        try:
            codigo = proc.wait(timeout=timeout_s)
            agotado = False
        except subprocess.TimeoutExpired:
            proc.kill()
            codigo, agotado = proc.wait(), True
    # El fichero de sesión trae los avisos de hooks PostToolUse que el stream-json no incluye.
    for f in (aislado / "config" / "projects").glob("*/*.jsonl"):
        shutil.copy(f, salida / "sesion.jsonl")
    return {"codigo_salida": codigo, "timeout": agotado, "segundos_reloj": round(time.time() - inicio, 1)}


def resumen_transcript(ruta):
    """Datos de los eventos system/init y result del stream-json."""
    init, result = None, None
    for linea in Path(ruta).read_text().splitlines():
        try:
            ev = json.loads(linea)
        except ValueError:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            init = ev
        elif ev.get("type") == "result":
            result = ev
    datos = {"init": None, "result": None}
    if init:
        datos["init"] = {k: init.get(k) for k in
                         ("model", "cwd", "tools", "mcp_servers", "slash_commands", "skills",
                          "plugins", "agents", "permissionMode", "claude_code_version", "memory_paths")
                         if k in init}
    if result:
        datos["result"] = {k: result.get(k) for k in
                           ("subtype", "is_error", "num_turns", "duration_ms", "total_cost_usd",
                            "modelUsage", "permission_denials", "result")}
    return datos


if __name__ == "__main__":
    # Para los scripts de shell (demo_commit.sh, el scaffold de los evals): toma.py preparar <destino> <commit>
    if len(sys.argv) == 4 and sys.argv[1] == "preparar":
        destino = Path(sys.argv[2]).resolve()
        (poblar_workspace if destino.exists() else preparar_workspace)(destino, sys.argv[3])
    else:
        sys.exit("uso: toma.py preparar <destino> <commit>")
