"""Definición única de las reglas de la casa que se comprueban con código (R1, R4, R5).

La usan los hooks del plugin (proteger_secretos.sh, sin_dependencias_nuevas.sh,
comprobar_reglas.py y puerta_de_salida.sh), el auditor del laboratorio y cualquier CI,
para que todos digan exactamente lo mismo. R2 y R3 no están aquí: son reglas solo
escritas (AGENTS.md y la skill). Compatible con Python 3.9+.

Uso desde un hook (lee la entrada JSON del hook por stdin):
  reglas.py toca-env          # exit 0 e imprime qué toca si la llamada nombra el .env
  reglas.py es-dependencias   # exit 0 e imprime la ruta si edita un fichero de dependencias
  reglas.py apuntar-inicio    # SessionStart: apunta en .git el commit en el que empieza la sesión
  reglas.py activo            # exit 0 si el repo tiene el marcador .harness-equipo en su raíz

Todas las órdenes que leen la entrada del hook no hacen nada en un repo sin marcador.
"""
import ast
import fnmatch
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

# --- Convenciones del equipo ---------------------------------------------------

# Activación · Los hooks solo actúan en los repos que lo piden con este fichero, versionado en la raíz.
# Sin él no hacen nada aunque el plugin esté instalado (por ejemplo, a nivel de usuario).
MARCADOR = ".harness-equipo"

# R1 · Donde sí se puede tocar la base de datos.
CAPA_DATOS = ("app/repositories/", "app/models/", "app/extensions.py")
# Los tests montan sus fixtures con db.session: no son código de la aplicación.
FUERA_DE_R1 = ("tests/",)
MODULOS_DATOS = ("sqlalchemy", "flask_sqlalchemy", "sqlite3")
ATRIBUTOS_DATOS = {"session", "query", "execute", "query_property"}

# R4 · Ficheros que declaran dependencias (patrones sobre el nombre del fichero).
FICHEROS_DEPENDENCIAS = ("requirements*.txt", "constraints*.txt", "pyproject.toml", "setup.py",
                         "setup.cfg", "Pipfile", "Pipfile.lock", "poetry.lock", "uv.lock",
                         "environment.yml")
# Las dependencias aprobadas son las de este fichero y todo lo que arrastran.
REQUISITOS = "requirements.txt"

# R5 · Los secretos locales viven aquí; el .env.example sí se lee.
FICHERO_SECRETOS = ".env"
# Un comando de shell que nombra el .env por su nombre exacto (cat .env, ./.env, <.env),
# pero no .env.example ni .envrc.
RE_ENV_SHELL = re.compile(r"(?:^|[\s'\"=/<>|;&(])\.env(?![\w.\-])")


# --- R1 · Acceso a datos solo a través del repositorio -------------------------

def r1_aplica(ruta_rel):
    """True si el fichero (ruta relativa al proyecto, con /) está sujeto a R1."""
    if not ruta_rel.endswith(".py"):
        return False
    if ruta_rel.startswith(FUERA_DE_R1) or ruta_rel.startswith(CAPA_DATOS):
        return False
    return True

def _es_modulo_datos(nombre):
    return any(nombre == m or nombre.startswith(m + ".") for m in MODULOS_DATOS)


def accesos_a_datos(codigo):
    """Lista de (línea, motivo, fragmento) con cada acceso a datos del código."""
    try:
        arbol = ast.parse(codigo)
    except SyntaxError:
        return []
    lineas = codigo.splitlines()
    hallazgos = []

    def anota(nodo, motivo):
        texto = lineas[nodo.lineno - 1].strip() if nodo.lineno <= len(lineas) else ""
        hallazgos.append((nodo.lineno, motivo, texto))

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if _es_modulo_datos(alias.name) or alias.name == "app.extensions":
                    anota(nodo, "import " + alias.name)
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            if _es_modulo_datos(nodo.module):
                anota(nodo, "import de " + nodo.module)
            elif nodo.module == "app.extensions" and any(a.name == "db" for a in nodo.names):
                anota(nodo, "import de db")
            elif nodo.module == "app" and any(a.name == "extensions" for a in nodo.names):
                anota(nodo, "import de app.extensions")
        elif isinstance(nodo, ast.Name) and nodo.id == "db":
            anota(nodo, "uso de db")
        elif isinstance(nodo, ast.Attribute) and nodo.attr in ATRIBUTOS_DATOS:
            anota(nodo, "acceso a ." + nodo.attr)
    return sorted(set(hallazgos))


def accesos_nuevos(codigo_base, codigo_final):
    """Accesos a datos que aparecen en el código final y no estaban en el base.

    Se comparan por (motivo, fragmento) contando repeticiones, así que mover
    código de sitio no cuenta como acceso nuevo y duplicarlo sí.
    """
    base = Counter((m, t) for _, m, t in accesos_a_datos(codigo_base or ""))
    nuevos = []
    for linea, motivo, texto in accesos_a_datos(codigo_final):
        if base[(motivo, texto)] > 0:
            base[(motivo, texto)] -= 1
        else:
            nuevos.append((linea, motivo, texto))
    return nuevos


# --- R4 · Ninguna dependencia nueva --------------------------------------------

def es_fichero_dependencias(ruta):
    nombre = Path(ruta).name
    return any(fnmatch.fnmatchcase(nombre, p) for p in FICHEROS_DEPENDENCIAS)


def normaliza(nombre):
    return re.sub(r"[-_.]+", "-", nombre).lower()


def nombres_requisitos(texto):
    """Nombres de paquete de un requirements.txt (sin versiones, extras ni marcadores)."""
    nombres = []
    for linea in texto.splitlines():
        linea = linea.split("#", 1)[0].strip()
        if linea and not linea.startswith("-"):
            nombres.append(re.split(r"[\s<>=!~\[;(@]", linea, 1)[0])
    return nombres


def _marcador_aplica(marcador):
    if "extra" in marcador:
        return False
    try:
        from packaging.markers import Marker
        return Marker(marcador).evaluate()
    except Exception:
        return True


def _modulos_de(dist):
    modulos = set()
    top = dist.read_text("top_level.txt")
    if top:
        modulos.update(top.split())
    for f in dist.files or []:
        p = f.parts[0]
        if not p.endswith((".dist-info", ".data", ".pth")) and p not in ("..", "__pycache__"):
            modulos.add(p[:-3] if p.endswith(".py") else p)
    return modulos


def cierre_requisitos(texto_requisitos):
    """(distribuciones, módulos) de los requisitos y todo lo que arrastran.

    Usa los metadatos del intérprete que lo ejecuta: hay que llamarlo con el Python del
    .venv del proyecto.
    """
    import importlib.metadata as md
    pendientes = list(nombres_requisitos(texto_requisitos))
    distribuciones, modulos = set(), set()
    while pendientes:
        nombre = normaliza(pendientes.pop())
        if nombre in distribuciones:
            continue
        try:
            dist = md.distribution(nombre)
        except md.PackageNotFoundError:
            continue
        distribuciones.add(nombre)
        modulos |= _modulos_de(dist)
        for req in dist.requires or []:
            req, _, marcador = req.partition(";")
            if not marcador or _marcador_aplica(marcador.strip()):
                pendientes.append(re.split(r"[\s<>=!~\[(@]", req.strip(), 1)[0])
    return distribuciones, modulos


def modulos_locales(proyecto):
    """Paquetes y módulos de primer nivel del propio proyecto."""
    locales = set()
    for p in Path(proyecto).iterdir():
        if p.name.startswith(".") or p.name == "__pycache__":
            continue
        if p.is_dir() and any(p.glob("*.py")):
            locales.add(p.name)
        elif p.suffix == ".py":
            locales.add(p.stem)
    return locales


def es_biblioteca_estandar(raiz):
    return raiz in getattr(sys, "stdlib_module_names", ()) or raiz in sys.builtin_module_names


def imports(codigo):
    """Lista de (línea, módulo) de los imports absolutos del código."""
    try:
        arbol = ast.parse(codigo)
    except SyntaxError:
        return []
    encontrados = []
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            encontrados += [(n.lineno, a.name) for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            encontrados.append((n.lineno, n.module))
    return encontrados


def imports_no_aprobados(codigo_base, codigo_final, permitidos):
    """Imports nuevos (respecto al código base) de paquetes que no son de la biblioteca
    estándar, del proyecto ni del cierre de requirements.txt."""
    base = Counter(m for _, m in imports(codigo_base or ""))
    fuera = []
    for linea, modulo in imports(codigo_final):
        if base[modulo] > 0:
            base[modulo] -= 1
            continue
        raiz = modulo.split(".")[0]
        if not es_biblioteca_estandar(raiz) and raiz not in permitidos:
            fuera.append((linea, modulo))
    return fuera


# --- R5 · El .env ni se lee ni se edita ------------------------------------------

def _alternativas(glob):
    """Expande las llaves de un glob: "{.env,*.py}" -> [".env", "*.py"]."""
    m = re.search(r"\{([^{}]*)\}", glob)
    if not m:
        return [glob]
    return [x for alt in m.group(1).split(",")
            for x in _alternativas(glob[:m.start()] + alt + glob[m.end():])]


def _glob_nombra_env(glob):
    """True si alguna alternativa del glob apunta al .env por su nombre (".env", ".env*", "**/.env").
    Un glob genérico como "*" no cuenta: no nombra el fichero."""
    for alt in _alternativas(glob or ""):
        if alt.startswith("!"):   # exclusión: deja el .env fuera
            continue
        nombre = alt.split("/")[-1]
        if nombre.startswith(".") and fnmatch.fnmatchcase(FICHERO_SECRETOS, nombre):
            return True
    return False


def toca_env(herramienta, entrada):
    """Descripción de la llamada si puede traer el contenido del .env; None si no.

    Glob no cuenta: solo devuelve rutas, como un find, y saber que el .env existe no es leerlo.
    Grep sí: devuelve líneas, así que cuenta si su path es el .env o su glob lo nombra.
    """
    entrada = entrada or {}
    if herramienta in ("Read", "Edit", "Write", "NotebookEdit"):
        ruta = entrada.get("file_path") or entrada.get("notebook_path") or ""
        return "%s %s" % (herramienta, ruta) if Path(ruta).name == FICHERO_SECRETOS else None
    if herramienta == "Grep":
        ruta, glob = entrada.get("path") or "", entrada.get("glob") or ""
        if Path(ruta).name == FICHERO_SECRETOS or _glob_nombra_env(glob):
            return "Grep %s%s" % (entrada.get("pattern", ""), " en " + (ruta or glob))
        return None
    if herramienta == "Bash":
        comando = entrada.get("command", "")
        return "Bash: %s" % comando if RE_ENV_SHELL.search(comando) else None
    return None


# --- Estado del proyecto (hooks SessionStart, PostToolUse y Stop) ---------------

def _git(proyecto, *args):
    r = subprocess.run(["git"] + list(args), cwd=str(proyecto), capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def _fichero_inicio(proyecto, sesion):
    """Dónde se apunta el commit de inicio de una sesión: dentro de .git, fuera del árbol de trabajo."""
    ruta = _git(proyecto, "rev-parse", "--git-path", "harness-equipo/inicio-de-sesion")
    if not ruta or not sesion:
        return None
    nombre = re.sub(r"[^\w.-]", "_", str(sesion))
    return Path(proyecto) / ruta.strip() / nombre


def apuntar_inicio(proyecto, sesion):
    """SessionStart: apunta el commit en el que empieza la sesión (si ya estaba apuntado, se respeta)."""
    fichero = _fichero_inicio(proyecto, sesion)
    head = _git(proyecto, "rev-parse", "HEAD")
    if fichero is None or head is None or fichero.exists():
        return
    fichero.parent.mkdir(parents=True, exist_ok=True)
    fichero.write_text(head.strip() + "\n")


def commit_de_inicio(proyecto, sesion):
    """Commit con el que se compara: el apuntado al empezar la sesión o, si falta, HEAD.

    Comparar con HEAD a secas dejaba ciego al hook ante cualquier cosa que el agente hubiera commiteado.
    """
    fichero = _fichero_inicio(proyecto, sesion)
    if fichero is not None and fichero.exists():
        commit = fichero.read_text().strip()
        if _git(proyecto, "cat-file", "-e", commit + "^{commit}") is not None:
            return commit
    return "HEAD"


def cambios_git(proyecto, referencia="HEAD"):
    """Rutas (relativas, con /) distintas de `referencia`, commiteadas o no: modificadas, nuevas,
    borradas o renombradas, más las nuevas sin seguimiento. Lo ignorado por .gitignore no cuenta."""
    salida = _git(proyecto, "diff", "--name-only", "--no-renames", "-z", referencia)
    nuevas = _git(proyecto, "ls-files", "--others", "--exclude-standard", "-z")
    if salida is None or nuevas is None:
        return []
    return sorted({r for r in (salida + nuevas).split("\0") if r})


def _en(proyecto, referencia, rel):
    return _git(proyecto, "show", "%s:%s" % (referencia, rel))


def activo(proyecto):
    """True si el repo activa los hooks del equipo con el fichero marcador en su raíz."""
    return (Path(proyecto) / MARCADOR).is_file()


def revisar_estado(proyecto, referencia="HEAD", comprobar_imports=True):
    """R1 y R4 sobre lo que ha cambiado respecto a `referencia` (el commit de inicio de la sesión),
    venga de donde venga el cambio y esté commiteado o no.

    `comprobar_imports=False` salta la parte de R4 que mira los imports: hace falta el Python del .venv
    del proyecto para saber qué es biblioteca estándar y qué arrastra requirements.txt.

    Devuelve una lista de (regla, fichero, línea, motivo, fragmento).
    """
    proyecto = Path(proyecto)
    hallazgos, permitidos = [], None
    for rel in cambios_git(proyecto, referencia):
        ruta = proyecto / rel
        if es_fichero_dependencias(rel):
            hallazgos.append(("R4", rel, 0, "fichero de dependencias distinto del inicio de la sesión", ""))
        if not rel.endswith(".py") or not ruta.is_file():
            continue
        base, final = _en(proyecto, referencia, rel), ruta.read_text(errors="replace")
        if r1_aplica(rel):
            for linea, motivo, texto in accesos_nuevos(base, final):
                hallazgos.append(("R1", rel, linea, motivo, texto))
        if not comprobar_imports:
            continue
        if permitidos is None:
            requisitos = _en(proyecto, referencia, REQUISITOS) or ""
            permitidos = cierre_requisitos(requisitos)[1] | modulos_locales(proyecto)
        for linea, modulo in imports_no_aprobados(base, final, permitidos):
            hallazgos.append(("R4", rel, linea, "import de un paquete que no está en " + REQUISITOS, modulo))
    return hallazgos


COMO_ARREGLAR = {
    "R1": "R1 · Mueve la consulta a un método con type hints del repositorio de la entidad\n"
          "     (app/repositories/<entidad>_repository.py, exportado en app/repositories/__init__.py)\n"
          "     y llama a ese método. Fuera de la capa de datos no se importa db, sqlalchemy ni\n"
          "     sqlite3, ni se usa .session, .query o .execute.",
    "R4": "R4 · No se añaden dependencias sin aprobación del equipo. Deja los ficheros de\n"
          "     dependencias como al empezar (git checkout <commit> -- <fichero>, o bórralo si es nuevo), quita\n"
          "     el import y resuélvelo con la biblioteca estándar; si de verdad hace falta, deja la\n"
          "     propuesta en el resumen para que alguien la apruebe.",
}


def main():
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    proyecto = os.environ.get("CLAUDE_PROJECT_DIR") or "."
    if orden == "activo":
        sys.exit(0 if activo(proyecto) else 1)
    entrada = json.load(sys.stdin)
    if not activo(os.environ.get("CLAUDE_PROJECT_DIR") or entrada.get("cwd") or "."):
        sys.exit(0 if orden == "apuntar-inicio" else 1)   # repo sin marcador: no se hace nada
    if orden == "apuntar-inicio":
        apuntar_inicio(os.environ.get("CLAUDE_PROJECT_DIR") or entrada.get("cwd") or ".", entrada.get("session_id"))
        sys.exit(0)
    herramienta, datos = entrada.get("tool_name"), entrada.get("tool_input") or {}
    if orden == "toca-env":
        que = toca_env(herramienta, datos)
    elif orden == "es-dependencias":
        ruta = datos.get("file_path") or ""
        que = ruta if herramienta in ("Edit", "Write") and es_fichero_dependencias(ruta) else None
    else:
        sys.exit("orden desconocida: %r" % orden)
    if que:
        print(que)
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
