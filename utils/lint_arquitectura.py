"""Architecture rules of the wave refactor (docs/project-history.md).

Four AST rules over `main.py` and the agent package. They all cover failures
that do NOT show up as a red test: either they break the submission on Kaggle with the
suite green, or they make the agent read frozen state and decide badly in a
game without raising any exception.

  R1  (I5)  Never `from <module> import <mutable>`.
            `from x import ko_last_turn` COPIES the value at the moment of the
            import; when main.py reassigns it, the module goes on seeing the old
            value. Silently. It is always accessed through the object: `estado.ko_last_turn`.

  R2  (purity)  Nothing under cartas/ or motor/ may touch the state.
            `cartas/` is data and `motor/` is the generic rules resolver:
            both are read and tested without setting up a game.

            `calculo/` MAY: leaving it pure was attempted and the code proved
            it is not. The effective energy depends on whether Meganium is in play, and
            the attack cost on the Nighttime Mine tax; passing that through
            parameters to `_can_attack_eff`, `_physical_energy` and company would be
            REWRITING the logic, not moving it -- exactly what this refactor does
            not do. The useful boundary ended up at data/rules, not at calculation.

  R3  (I1b) In main.py, nothing binds a new name AFTER `def agent`.
            The container keeps the LAST callable of the namespace: a
            re-export placed below hijacks the entry point.

  R4  (I1a/I1c) Neither `import <our own package>` inside a function, nor
            `import main` anywhere in the package. The agent's directory leaves
            sys.path as soon as main.py's exec finishes, and main.py never gets
            to be in sys.modules.

Usage:
    python utils/lint_arquitectura.py          # exit 1 if there are violations
"""

import ast
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

MAIN_PY = PROJECT_ROOT / "main.py"
PAQUETE = PROJECT_ROOT / "ptcg"          # it does not exist yet before wave 1
SUBPAQUETES_PUROS = ("cartas", "motor")

# The name of the module that owns the mutable state (wave 3).
MODULO_ESTADO = "estado"


def mutable_names():
    """The mutable globals between turns, DERIVED from the code (not by hand).

    Before wave 3 they live in main.py and are detected by their
    `global` statements. Afterwards they become attributes of `EstadoAgente`, and then the
    source is that module: the names are no longer loose globals, so R1
    stops having anything to watch in main.py and moves on to watching the package.
    """
    names = set()
    if MAIN_PY.is_file():
        arbol = ast.parse(MAIN_PY.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Global):
                names.update(nodo.names)
    agente = PAQUETE / MODULO_ESTADO / "agente.py"
    if agente.is_file():
        arbol = ast.parse(agente.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            # annotated fields (`x: int`) and, above all, those of `reset()`
            # (`self.x = ...`), which is how they are declared in EstadoAgente.
            if isinstance(nodo, ast.AnnAssign) and isinstance(nodo.target, ast.Name):
                names.add(nodo.target.id)
            elif isinstance(nodo, ast.Assign):
                for t in nodo.targets:
                    if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                            and t.value.id == "self"):
                        names.add(t.attr)
    return names


def _package_files():
    return sorted(PAQUETE.rglob("*.py")) if PAQUETE.is_dir() else []


def _raiz_paquetes_locales():
    """Names of our own packages that canNOT be imported late."""
    names = {PAQUETE.name}
    for hijo in PROJECT_ROOT.iterdir():
        if (hijo / "__init__.py").is_file():
            names.add(hijo.name)
    return names


def _rel(path):
    try:
        return str(Path(path).relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# R1 -- never `from ... import <mutable>`
# ---------------------------------------------------------------------------
def rule_1_imported_mutables():
    fallos = []
    mutables = mutable_names()
    if not mutables:
        return fallos
    for path in _package_files():
        arbol = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom):
                for alias in nodo.names:
                    if alias.name in mutables:
                        fallos.append((
                            "R1", _rel(path), nodo.lineno,
                            f"`from {nodo.module or '.'} import {alias.name}` copia el "
                            f"valor; usa el objeto ({MODULO_ESTADO}.{alias.name})",
                        ))
    return fallos


# ---------------------------------------------------------------------------
# R2 -- cartas/, motor/ and calculo/ are pure
# ---------------------------------------------------------------------------
def rule_2_purity():
    fallos = []
    for path in _package_files():
        partes = path.relative_to(PAQUETE).parts
        if not partes or partes[0] not in SUBPAQUETES_PUROS:
            continue
        arbol = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for nodo in ast.walk(arbol):
            target = None
            if isinstance(nodo, ast.ImportFrom) and nodo.module:
                target = nodo.module
            elif isinstance(nodo, ast.Import):
                target = ",".join(a.name for a in nodo.names)
            if target and MODULO_ESTADO in target.split("."):
                fallos.append((
                    "R2", _rel(path), nodo.lineno,
                    f"{partes[0]}/ tiene que ser puro: no puede importar {target}",
                ))
    return fallos


# ---------------------------------------------------------------------------
# R3 -- `def agent` is the last thing in main.py
# ---------------------------------------------------------------------------
def rule_3_agent_is_last():
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
# R4 -- lazy imports of our own packages / `import main`
# ---------------------------------------------------------------------------
def _raices_de(nodo):
    if isinstance(nodo, ast.Import):
        return [a.name.split(".")[0] for a in nodo.names]
    if isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
        return [nodo.module.split(".")[0]]
    return []


def rule_4_lazy_imports():
    fallos = []
    locales = _raiz_paquetes_locales()

    for path in [MAIN_PY, *_package_files()]:
        if not path.is_file():
            continue
        arbol = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        # `import main` anywhere in the package (I1c)
        if path != MAIN_PY:
            for nodo in ast.walk(arbol):
                if "main" in _raices_de(nodo):
                    fallos.append((
                        "R4", _rel(path), nodo.lineno,
                        "`import main` es imposible en el contenedor: main.py se "
                        "ejecuta con exec y nunca entra en sys.modules",
                    ))

        # an import of our own package INSIDE a function (I1a)
        for fn in ast.walk(arbol):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for nodo in ast.walk(fn):
                for raiz in _raices_de(nodo):
                    if raiz in locales:
                        fallos.append((
                            "R4", _rel(path), nodo.lineno,
                            f"import de `{raiz}` dentro de `{fn.name}()`: el dir del "
                            "agente sale de sys.path al terminar el exec de main.py. "
                            "Importalo a NIVEL DE MODULO.",
                        ))
    return fallos


RULES = (
    rule_1_imported_mutables,
    rule_2_purity,
    rule_3_agent_is_last,
    rule_4_lazy_imports,
)


def revisar():
    """Returns the list of violations: (rule, file, line, message)."""
    fallos = []
    for rule in RULES:
        fallos += rule()
    return fallos


def main():
    fallos = revisar()
    if not fallos:
        print("lint_arquitectura: sin infracciones")
        return 0
    for rule, file_path, line, mensaje in fallos:
        print(f"{file_path}:{line}: [{rule}] {mensaje}")
    print(f"\n{len(fallos)} infraccion(es)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
