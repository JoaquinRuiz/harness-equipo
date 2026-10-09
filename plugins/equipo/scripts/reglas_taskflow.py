"""Definición única de las reglas de la casa que se comprueban sobre el código.

La usan el hook comprobar_capas.py, lab/auditar.py y cualquier CI futuro, para que
todos digan exactamente lo mismo. Compatible con Python 3.9+.
"""
import ast
import fnmatch
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent

# --- R1 · Acceso a datos solo a través del repositorio -------------------------

# Donde sí se puede tocar la base de datos.
CAPA_DATOS = ("app/repositories/", "app/models/", "app/extensions.py")
# Los tests montan sus fixtures con db.session: no son código de la aplicación.
FUERA_DE_R1 = ("tests/",)

MODULOS_DATOS = ("sqlalchemy", "flask_sqlalchemy", "sqlite3")
ATRIBUTOS_DATOS = {"session", "query", "execute", "query_property"}


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


# --- R3 · Formato de error: {"error": "<mensaje>"} con código 4xx --------------

DECORADORES_RUTA = {"route", "get", "post", "put", "patch", "delete"}


def _codigo_http(nodo):
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, int):
        return nodo.value
    # HTTPStatus.NOT_FOUND y similares
    if isinstance(nodo, ast.Attribute):
        try:
            from http import HTTPStatus
            return int(HTTPStatus[nodo.attr])
        except KeyError:
            return None
    return None


def _es_cuerpo_error(nodo):
    """True / False si se puede decidir; None si no es determinable estáticamente."""
    if isinstance(nodo, ast.Dict):
        claves = [k.value if isinstance(k, ast.Constant) else None for k in nodo.keys]
        return claves == ["error"]
    if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", None) == "jsonify":
        if len(nodo.args) == 1 and not nodo.keywords:
            return _es_cuerpo_error(nodo.args[0])
        if not nodo.args:
            return [k.arg for k in nodo.keywords] == ["error"]
        return False
    if isinstance(nodo, ast.Constant):
        return False
    return None


def _resuelve(nombre, funcion, antes_de):
    """Último valor asignado a `nombre` dentro de la función antes de la línea dada."""
    valor = None
    for nodo in ast.walk(funcion):
        if isinstance(nodo, ast.Assign) and nodo.lineno < antes_de:
            for destino in nodo.targets:
                if isinstance(destino, ast.Name) and destino.id == nombre:
                    valor = nodo.value
    return valor


def _respuesta(ret, funcion):
    """(cuerpo, código) de un return; None si no devuelve un código explícito."""
    valor = ret.value
    if isinstance(valor, ast.Call) and getattr(valor.func, "id", None) == "make_response":
        if len(valor.args) >= 2:
            return valor.args[0], _codigo_http(valor.args[1])
        return None
    if isinstance(valor, ast.Tuple) and len(valor.elts) >= 2:
        cuerpo = valor.elts[0]
        if isinstance(cuerpo, ast.Name):
            cuerpo = _resuelve(cuerpo.id, funcion, ret.lineno) or cuerpo
        return cuerpo, _codigo_http(valor.elts[1])
    return None


def _manejadores(arbol):
    """Funciones registradas como errorhandler, con el objetivo que cubren."""
    encontrados = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.FunctionDef):
            for dec in nodo.decorator_list:
                if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr in ("errorhandler", "app_errorhandler") and dec.args):
                    encontrados.append((nodo, dec.args[0]))
    return encontrados


def _objetivo(nodo):
    if isinstance(nodo, ast.Constant):
        return nodo.value
    if isinstance(nodo, ast.Name):
        return nodo.id
    if isinstance(nodo, ast.Attribute):
        return nodo.attr
    return None


def _devuelve_formato_error(funcion):
    retornos = [n for n in ast.walk(funcion) if isinstance(n, ast.Return) and n.value is not None]
    if not retornos:
        return False
    for ret in retornos:
        valor = ret.value
        cuerpo = valor.elts[0] if isinstance(valor, ast.Tuple) and valor.elts else valor
        if _es_cuerpo_error(cuerpo) is not True:
            return False
    return True


def formato_errores(ficheros):
    """Comprueba R3 sobre {ruta_rel: código} de app/.

    Devuelve (violaciones, indeterminados), listas de (ruta, línea, motivo, fragmento).
    """
    violaciones, indeterminados = [], []
    cubiertos = set()  # códigos (int) o nombres de excepción convertidos a {"error": ...}
    arboles = {}
    for ruta, codigo in ficheros.items():
        try:
            arboles[ruta] = ast.parse(codigo)
        except SyntaxError:
            continue

    for ruta, arbol in arboles.items():
        lineas = ficheros[ruta].splitlines()
        for funcion, objetivo in _manejadores(arbol):
            if _devuelve_formato_error(funcion):
                cubiertos.add(_objetivo(objetivo))
            else:
                violaciones.append((ruta, funcion.lineno, "errorhandler con otro formato",
                                    lineas[funcion.lineno - 1].strip()))

    for ruta, arbol in arboles.items():
        lineas = ficheros[ruta].splitlines()
        for funcion in ast.walk(arbol):
            if not isinstance(funcion, ast.FunctionDef):
                continue
            for ret in ast.walk(funcion):
                if not isinstance(ret, ast.Return) or ret.value is None:
                    continue
                respuesta = _respuesta(ret, funcion)
                if respuesta is None:
                    continue
                cuerpo, codigo = respuesta
                if codigo is None or not 400 <= codigo < 500:
                    continue
                veredicto = _es_cuerpo_error(cuerpo)
                texto = lineas[ret.lineno - 1].strip()
                if veredicto is False:
                    violaciones.append((ruta, ret.lineno, "respuesta %d sin formato de error" % codigo, texto))
                elif veredicto is None:
                    indeterminados.append((ruta, ret.lineno, "cuerpo no determinable", texto))
            for llamada in ast.walk(funcion):
                if isinstance(llamada, ast.Call) and getattr(llamada.func, "id", None) == "abort":
                    codigo = _codigo_http(llamada.args[0]) if llamada.args else None
                    if not ({codigo, "HTTPException", "Exception"} & cubiertos):
                        violaciones.append((ruta, llamada.lineno, "abort() sin errorhandler que lo convierta",
                                            lineas[llamada.lineno - 1].strip()))
    return violaciones, indeterminados


# --- R4 · Ficheros de dependencias --------------------------------------------

def patrones_dependencias():
    texto = (AQUI / "ficheros_dependencias.txt").read_text()
    return [l.strip() for l in texto.splitlines() if l.strip() and not l.startswith("#")]


def es_fichero_dependencias(ruta):
    nombre = Path(ruta).name
    return any(fnmatch.fnmatchcase(nombre, p) for p in patrones_dependencias())
