"""Reglas de arquitectura del refactor por olas (docs/main-refactor-arquitectura.md).

Cuatro reglas AST sobre `main.py` y el paquete del agente. Todas cubren fallos
que NO se manifiestan como un test rojo: o rompen la submission en Kaggle con la
suite en verde, o hacen que el agente lea estado congelado y decida mal en
partida sin lanzar ninguna excepcion.

  R1  (I5)  Nunca `from <modulo> import <mutable>`.
            `from x import ko_last_turn` COPIA el valor en el momento del
            import; cuando main.py lo reasigna, el modulo sigue viendo el valor
            viejo. Silencioso. Se accede siempre por objeto: `estado.ko_last_turn`.

  R2  (pureza)  Nada bajo cartas/, motor/ o calculo/ puede tocar el estado.
            Es lo que mantiene esos modulos reutilizables y testeables solos.

  R3  (I1b) En main.py, nada liga un nombre nuevo DESPUES de `def agent`.
            El contenedor se queda con el ULTIMO callable del namespace: un
            re-export puesto debajo secuestra el punto de entrada.

  R4  (I1a/I1c) Ni `import <paquete propio>` dentro de una funcion, ni
            `import main` en ningun sitio del paquete. El dir del agente sale de
            sys.path en cuanto termina el exec de main.py, y main.py nunca llega
            a estar en sys.modules.

Uso:
    python utils/lint_arquitectura.py          # exit 1 si hay infracciones
"""

import ast
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

MAIN_PY = PROJECT_ROOT / "main.py"
PAQUETE = PROJECT_ROOT / "ptcg"          # aun no existe antes de la Ola 1
SUBPAQUETES_PUROS = ("cartas", "motor", "calculo")

# Nombre del modulo dueño del estado mutable (Ola 3).
MODULO_ESTADO = "estado"


def nombres_mutables():
    """Los globals mutables entre turnos, DERIVADOS del codigo (no a mano).

    Antes de la Ola 3 viven en main.py y se detectan por sus sentencias
    `global`. Despues pasan a ser atributos de `EstadoAgente`, y entonces la
    fuente es ese modulo: los nombres ya no son globals sueltos, asi que R1
    deja de tener nada que vigilar en main.py y pasa a vigilar el paquete.
    """
    nombres = set()
    if MAIN_PY.is_file():
        arbol = ast.parse(MAIN_PY.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Global):
                nombres.update(nodo.names)
    agente = PAQUETE / MODULO_ESTADO / "agente.py"
    if agente.is_file():
        arbol = ast.parse(agente.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.AnnAssign) and isinstance(nodo.target, ast.Name):
                nombres.add(nodo.target.id)
    return nombres


def _archivos_del_paquete():
    return sorted(PAQUETE.rglob("*.py")) if PAQUETE.is_dir() else []


def _raiz_paquetes_locales():
    """Nombres de paquete propios que NO pueden importarse tarde."""
    nombres = {PAQUETE.name}
    for hijo in PROJECT_ROOT.iterdir():
        if (hijo / "__init__.py").is_file():
            nombres.add(hijo.name)
    return nombres


def _rel(ruta):
    try:
        return str(Path(ruta).relative_to(PROJECT_ROOT))
    except ValueError:
        return str(ruta)


# ---------------------------------------------------------------------------
# R1 -- nunca `from ... import <mutable>`
# ---------------------------------------------------------------------------
def regla_1_mutables_importados():
    fallos = []
    mutables = nombres_mutables()
    if not mutables:
        return fallos
    for ruta in _archivos_del_paquete():
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom):
                for alias in nodo.names:
                    if alias.name in mutables:
                        fallos.append((
                            "R1", _rel(ruta), nodo.lineno,
                            f"`from {nodo.module or '.'} import {alias.name}` copia el "
                            f"valor; usa el objeto ({MODULO_ESTADO}.{alias.name})",
                        ))
    return fallos


# ---------------------------------------------------------------------------
# R2 -- cartas/, motor/ y calculo/ son puros
# ---------------------------------------------------------------------------
def regla_2_pureza():
    fallos = []
    for ruta in _archivos_del_paquete():
        partes = ruta.relative_to(PAQUETE).parts
        if not partes or partes[0] not in SUBPAQUETES_PUROS:
            continue
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
        for nodo in ast.walk(arbol):
            objetivo = None
            if isinstance(nodo, ast.ImportFrom) and nodo.module:
                objetivo = nodo.module
            elif isinstance(nodo, ast.Import):
                objetivo = ",".join(a.name for a in nodo.names)
            if objetivo and MODULO_ESTADO in objetivo.split("."):
                fallos.append((
                    "R2", _rel(ruta), nodo.lineno,
                    f"{partes[0]}/ tiene que ser puro: no puede importar {objetivo}",
                ))
    return fallos


# ---------------------------------------------------------------------------
# R3 -- `def agent` es lo ultimo de main.py
# ---------------------------------------------------------------------------
def regla_3_agent_es_lo_ultimo():
    if not MAIN_PY.is_file():
        return []
    arbol = ast.parse(MAIN_PY.read_text(encoding="utf-8"), filename=str(MAIN_PY))

    indice = None
    for i, nodo in enumerate(arbol.body):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == "agent":
            indice = i
    if indice is None:
        return [("R3", _rel(MAIN_PY), 0, "no se encontro `def agent` a nivel de modulo")]

    fallos = []
    LIGAN = (ast.Import, ast.ImportFrom, ast.FunctionDef,
             ast.AsyncFunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)
    for nodo in arbol.body[indice + 1:]:
        if isinstance(nodo, LIGAN):
            fallos.append((
                "R3", _rel(MAIN_PY), nodo.lineno,
                "liga un nombre nuevo DESPUES de `def agent`; el contenedor de "
                "Kaggle se queda con el ULTIMO callable, asi que esto secuestra "
                "el punto de entrada. Muevelo ARRIBA.",
            ))
    return fallos


# ---------------------------------------------------------------------------
# R4 -- imports perezosos de paquetes propios / `import main`
# ---------------------------------------------------------------------------
def _raices_de(nodo):
    if isinstance(nodo, ast.Import):
        return [a.name.split(".")[0] for a in nodo.names]
    if isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
        return [nodo.module.split(".")[0]]
    return []


def regla_4_imports_perezosos():
    fallos = []
    locales = _raiz_paquetes_locales()

    for ruta in [MAIN_PY, *_archivos_del_paquete()]:
        if not ruta.is_file():
            continue
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))

        # `import main` en cualquier parte del paquete (I1c)
        if ruta != MAIN_PY:
            for nodo in ast.walk(arbol):
                if "main" in _raices_de(nodo):
                    fallos.append((
                        "R4", _rel(ruta), nodo.lineno,
                        "`import main` es imposible en el contenedor: main.py se "
                        "ejecuta con exec y nunca entra en sys.modules",
                    ))

        # import de paquete propio DENTRO de una funcion (I1a)
        for fn in ast.walk(arbol):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for nodo in ast.walk(fn):
                for raiz in _raices_de(nodo):
                    if raiz in locales:
                        fallos.append((
                            "R4", _rel(ruta), nodo.lineno,
                            f"import de `{raiz}` dentro de `{fn.name}()`: el dir del "
                            "agente sale de sys.path al terminar el exec de main.py. "
                            "Importalo a NIVEL DE MODULO.",
                        ))
    return fallos


REGLAS = (
    regla_1_mutables_importados,
    regla_2_pureza,
    regla_3_agent_es_lo_ultimo,
    regla_4_imports_perezosos,
)


def revisar():
    """Devuelve la lista de infracciones: (regla, archivo, linea, mensaje)."""
    fallos = []
    for regla in REGLAS:
        fallos += regla()
    return fallos


def main():
    fallos = revisar()
    if not fallos:
        print("lint_arquitectura: sin infracciones")
        return 0
    for regla, archivo, linea, mensaje in fallos:
        print(f"{archivo}:{linea}: [{regla}] {mensaje}")
    print(f"\n{len(fallos)} infraccion(es)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
