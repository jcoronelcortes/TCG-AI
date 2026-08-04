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
    python utils/lint_architecture.py          # exit 1 if there are violations
"""

import ast
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

MAIN_PY = PROJECT_ROOT / "main.py"
PACKAGE = PROJECT_ROOT / "ptcg"          # it does not exist yet before wave 1
PURE_SUBPACKAGES = ("cards", "engine")

# The name of the module that owns the mutable state (wave 3).
STATE_MODULE = "state"


def mutable_names():
    """The mutable globals between turns, DERIVED from the code (not by hand).

    Before wave 3 they live in main.py and are detected by their
    `global` statements. Afterwards they become attributes of `AgentState`, and then the
    source is that module: the names are no longer loose globals, so R1
    stops having anything to watch in main.py and moves on to watching the package.
    """
    names = set()
    if MAIN_PY.is_file():
        tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Global):
                names.update(node.names)
    agent_state = PACKAGE / STATE_MODULE / "agent_state.py"
    if agent_state.is_file():
        tree = ast.parse(agent_state.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # annotated fields (`x: int`) and, above all, those of `reset()`
            # (`self.x = ...`), which is how they are declared in EstadoAgente.
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                            and t.value.id == "self"):
                        names.add(t.attr)
    return names


def _package_files():
    return sorted(PACKAGE.rglob("*.py")) if PACKAGE.is_dir() else []


def _raiz_paquetes_locales():
    """Names of our own packages that canNOT be imported late."""
    names = {PACKAGE.name}
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
    failures = []
    mutables = mutable_names()
    if not mutables:
        return failures
    for path in _package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in mutables:
                        failures.append((
                            "R1", _rel(path), node.lineno,
                            f"`from {node.module or '.'} import {alias.name}` copia el "
                            f"valor; usa el objeto ({STATE_MODULE}.{alias.name})",
                        ))
    return failures


# ---------------------------------------------------------------------------
# R2 -- cartas/, motor/ and calculo/ are pure
# ---------------------------------------------------------------------------
def rule_2_purity():
    failures = []
    for path in _package_files():
        partes = path.relative_to(PACKAGE).parts
        if not partes or partes[0] not in PURE_SUBPACKAGES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            target = None
            if isinstance(node, ast.ImportFrom) and node.module:
                target = node.module
            elif isinstance(node, ast.Import):
                target = ",".join(a.name for a in node.names)
            if target and STATE_MODULE in target.split("."):
                failures.append((
                    "R2", _rel(path), node.lineno,
                    f"{partes[0]}/ tiene que ser puro: no puede importar {target}",
                ))
    return failures


# ---------------------------------------------------------------------------
# R3 -- `def agent` is the last thing in main.py
# ---------------------------------------------------------------------------
def rule_3_agent_is_last():
    if not MAIN_PY.is_file():
        return []
    tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"), filename=str(MAIN_PY))

    index = None
    for i, node in enumerate(tree.body):
        if isinstance(node, ast.FunctionDef) and node.name == "agent":
            index = i
    if index is None:
        return [("R3", _rel(MAIN_PY), 0, "no se encontro `def agent` a nivel de modulo")]

    failures = []
    LIGAN = (ast.Import, ast.ImportFrom, ast.FunctionDef,
             ast.AsyncFunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)
    for node in tree.body[index + 1:]:
        if isinstance(node, LIGAN):
            failures.append((
                "R3", _rel(MAIN_PY), node.lineno,
                "liga un nombre nuevo DESPUES de `def agent`; el contenedor de "
                "Kaggle se queda con el ULTIMO callable, asi que esto secuestra "
                "el punto de entrada. Muevelo ARRIBA.",
            ))
    return failures


# ---------------------------------------------------------------------------
# R4 -- lazy imports of our own packages / `import main`
# ---------------------------------------------------------------------------
def _raices_de(node):
    if isinstance(node, ast.Import):
        return [a.name.split(".")[0] for a in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return [node.module.split(".")[0]]
    return []


def rule_4_lazy_imports():
    failures = []
    locales = _raiz_paquetes_locales()

    for path in [MAIN_PY, *_package_files()]:
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        # `import main` anywhere in the package (I1c)
        if path != MAIN_PY:
            for node in ast.walk(tree):
                if "main" in _raices_de(node):
                    failures.append((
                        "R4", _rel(path), node.lineno,
                        "`import main` es imposible en el contenedor: main.py se "
                        "ejecuta con exec y nunca entra en sys.modules",
                    ))

        # an import of our own package INSIDE a function (I1a)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                for raiz in _raices_de(node):
                    if raiz in locales:
                        failures.append((
                            "R4", _rel(path), node.lineno,
                            f"import de `{raiz}` dentro de `{fn.name}()`: el dir del "
                            "agente sale de sys.path al terminar el exec de main.py. "
                            "Importalo a NIVEL DE MODULO.",
                        ))
    return failures


RULES = (
    rule_1_imported_mutables,
    rule_2_purity,
    rule_3_agent_is_last,
    rule_4_lazy_imports,
)


def revisar():
    """Returns the list of violations: (rule, file, line, message)."""
    failures = []
    for rule in RULES:
        failures += rule()
    return failures


def main():
    failures = revisar()
    if not failures:
        print("lint_architecture: sin infracciones")
        return 0
    for rule, file_path, line, mensaje in failures:
        print(f"{file_path}:{line}: [{rule}] {mensaje}")
    print(f"\n{len(failures)} infraccion(es)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
