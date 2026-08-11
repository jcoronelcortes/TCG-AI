"""Architecture rules of the wave refactor (docs/project-history.md).

Eight AST rules over `main.py`, the agent package, the tools and the suite. They
all cover failures that do NOT show up as a red test: either they break the
submission on Kaggle with the suite green, or they make the agent read frozen
state and decide badly in a game without raising any exception -- or, for the
three added on 11 August, they make an INSTRUMENT report a number that is not a
measurement.

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

  R5  No module defines the same top-level name twice.
            Python keeps the LAST definition. A duplicated function is dead code
            that reads like live code: the fix goes into the copy at the top, the
            copy at the bottom is what runs, and nothing changes. Five modules of
            `ptcg/` carried a verbatim second copy of themselves.

  R4  (I1a/I1c) Neither `import <our own package>` inside a function, nor
            `import main` anywhere in the package. The agent's directory leaves
            sys.path as soon as main.py's exec finishes, and main.py never gets
            to be in sys.modules.

  R6  A test that READS a `records/` file must carry a skip guard.
            `records/` is transient local data and gets re-harvested. A census
            that pinned `registro_006_pasos_054...json` step 54 went red when a
            harvest took that board away, with nothing about the rule having
            changed (32a5537). Citing a record in a docstring is provenance and
            stays allowed; depending on the file is what needs the guard.

  R7  A gate that loads two arms must define AND call `provenance()`.
            Before 6c08b87 both arms shared every module under `ptcg/`, so a
            change to any rule measured EXACTLY ZERO -- and the written rule of
            this project is that neutral means revert. A gate that cannot see
            its own change is the most expensive thing here. The rule found a
            live one the day it landed: `utils/gate_promoted_relay.py`.

  R8  In the DISCARD block, the turn flags are read through the horizon.
            `state.supporterPlayed` / `state.energyAttached` describe what the
            OPPONENT spent when the discard is forced by their card, and
            Xerosic's Machinations is itself a Supporter -- so that flag is True
            on every forced discard it can produce, and the protection gated on
            its negation was unreachable code (93a27eb). Only the two
            assignments that build `_supporter_spent` / `_energy_spent` may
            read them there.

Usage:
    python utils/lint_architecture.py          # exit 1 if there are violations
"""

import ast
import re
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


# ---------------------------------------------------------------------------
# R5 -- one module, one definition per name
# ---------------------------------------------------------------------------
def rule_5_no_redefinition():
    """No module may define the same top-level name twice.

    Python keeps the LAST definition and discards the first without a word. A
    duplicated function is therefore dead code that reads exactly like live
    code: someone fixes the copy at the top of the file, the suite stays green
    because the copy at the bottom is the one that runs, and the fix silently
    does nothing. It is the same failure mode as R1 -- a name that looks bound
    to what you are reading and is bound to something else.

    This is not hypothetical. The extraction that moved definitions out of
    main.py in wave 2 appended its block twice in five modules, and 634 lines of
    `ptcg/` were a second copy of the 634 above them -- including
    `prize_count` and `prize_count_op`, the two functions of the prize
    arithmetic that had already cost one wrong-pile bug.
    """
    failures = []
    for path in [MAIN_PY] + _package_files():
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        first = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                if node.name in first:
                    failures.append((
                        "R5", _rel(path), node.lineno,
                        f"`{node.name}` is already defined at line "
                        f"{first[node.name]}: the first definition is dead code "
                        "and editing it changes nothing",
                    ))
                else:
                    first[node.name] = node.lineno
    return failures


# ---------------------------------------------------------------------------
# R6 -- a test may not pin a `records/` filename without a guard
# ---------------------------------------------------------------------------
TESTS = PROJECT_ROOT / "tests"

# A record FILENAME, or a path into the directory. Deliberately not the bare
# word: half the suite cites `registro_004 step 33` in prose, and prose is the
# provenance of a finding, not a dependency on a file. Nor the bare `records/`
# either -- the first draft of this rule flagged the assertion message
# "--snapshot-only no puede mirar records/", which is a sentence about the
# directory and not a read of it.
_REGISTRO = re.compile(r"registro_\d+\w*\.json|(?:^|[./])records/\w")


def _cadenas_ejecutables(tree):
    """String literals that are not somebody's docstring."""
    docs = {ast.get_docstring(n, clean=False) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef,
                              ast.AsyncFunctionDef, ast.ClassDef))}
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value not in docs]


def rule_6_records_are_transient(archivos=None):
    """`records/` is re-harvested; a test that needs one must say what to do
    when it is not there.

    THE BUG (32a5537). The census of "the prize is cashed by the body that
    outlasts" pinned `registro_006_pasos_054_hasta_056.json` step 54. A harvest
    replaced the bundle, the foundational board left with it, and the test went
    red without one thing about the rule changing -- while the skip guard at the
    top of that same file already said, out loud, that `records/` is transient
    local data. The repair was to assert the property whichever games happen to
    be on disk.

    So: cite a record in a docstring as much as you like; the moment a test
    READS one it must carry `pytest.skip`/`skipif`.
    """
    failures = []
    for path in (archivos if archivos is not None
                 else sorted(TESTS.glob("test_*.py")) if TESTS.is_dir() else []):
        source = Path(path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        if "pytest.skip" in source or "skipif" in source:
            continue
        for node in _cadenas_ejecutables(tree):
            if _REGISTRO.search(node.value):
                failures.append((
                    "R6", _rel(path), node.lineno,
                    f"usa {node.value[:40]!r} sin guarda: records/ es dato "
                    "transitorio y se recosecha; anade pytest.skip o afirma la "
                    "propiedad, no el fichero",
                ))
    return failures


# ---------------------------------------------------------------------------
# R7 -- a two-arm gate must prove its arms differ before it measures
# ---------------------------------------------------------------------------
UTILS = PROJECT_ROOT / "utils"


def rule_7_gates_check_provenance(archivos=None):
    """A gate that cannot see its own change reports NEUTRAL, and in this
    project neutral orders a revert.

    THE BUG (6c08b87). `selfplay --base` exported one file and both arms then
    resolved `from ptcg... import` through the working tree, so they shared every
    module object under `ptcg`: after the refactor -- 26 571 lines there against
    11 328 in main.py -- a change to any rule measured EXACTLY ZERO, by
    construction, in the two tools named as the heavy gates. The gates written
    since answer it with `provenance()`, which asks both arms on a board the rule
    is about and refuses to measure if they agree.

    The rule is scoped to gates that load an agent more than once, because that
    is what a two-arm gate IS. `gate_coverage.py` and `gate_mutation.py` load
    none and are none.
    """
    failures = []
    for path in (archivos if archivos is not None
                 else sorted(UTILS.glob("gate_*.py")) if UTILS.is_dir() else []):
        tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
        cargas = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Call)
                  and (getattr(n.func, "attr", None) or getattr(n.func, "id", None))
                  in ("load_agent", "load_agent_from_git")]
        if len(cargas) < 2:
            continue
        definida = any(isinstance(n, ast.FunctionDef) and n.name == "provenance"
                       for n in ast.walk(tree))
        llamada = any(isinstance(n, ast.Call) and getattr(n.func, "id", None) == "provenance"
                      for n in ast.walk(tree))
        if not (definida and llamada):
            falta = "no la define" if not definida else "la define y no la llama"
            failures.append((
                "R7", _rel(path), cargas[0].lineno,
                f"carga {len(cargas)} agentes y {falta} `provenance()`: un gate "
                "ciego informa NEUTRO, y neutro aqui ordena revertir",
            ))
    return failures


# ---------------------------------------------------------------------------
# R8 -- the turn flags of a forced discard are the OPPONENT's
# ---------------------------------------------------------------------------
CARD_PY = PACKAGE / "turn" / "options" / "card.py"
BANDERAS_DE_TURNO = ("supporterPlayed", "energyAttached")
HORIZONTE = ("_supporter_spent", "_energy_spent")


def rule_8_discard_reads_its_horizon(archivo=None):
    """Inside the DISCARD block, `state.supporterPlayed` and
    `state.energyAttached` may only be read to build the horizon.

    THE BUG (93a27eb). One menu serves two callers with opposite horizons: the
    COST of our own Ultra Ball, on our turn, and a discard FORCED by their card,
    which happens on THEIR turn. Those two flags describe what THEY spent, and
    Xerosic's Machinations IS a Supporter, so `supporterPlayed` is True on every
    forced discard it can produce -- `_protect_last_supporter`, gated on `not
    state.supporterPlayed`, was not misfiring, it was unreachable code on that
    whole path.

    The block now asks `_forced_discard` first and derives `_supporter_spent` /
    `_energy_spent` from it. This rule is what stops the raw flags coming back:
    the two assignments that BUILD the horizon are the only readings allowed.
    """
    path = Path(archivo) if archivo else CARD_PY
    if not path.is_file():
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def es_bloque_discard(node):
        return (isinstance(node, ast.If)
                and any(isinstance(c, ast.Attribute) and c.attr == "DISCARD"
                        for c in ast.walk(node.test)))

    def permitido(asignacion):
        return (isinstance(asignacion, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id in HORIZONTE
                        for t in asignacion.targets))

    failures = []
    for node in ast.walk(tree):
        if not es_bloque_discard(node):
            continue
        for sentencia in node.body:
            if permitido(sentencia):
                continue
            for hijo in ast.walk(sentencia):
                if (isinstance(hijo, ast.Attribute)
                        and hijo.attr in BANDERAS_DE_TURNO
                        and isinstance(hijo.value, ast.Name)
                        and hijo.value.id == "state"):
                    failures.append((
                        "R8", _rel(path), hijo.lineno,
                        f"`state.{hijo.attr}` crudo en el bloque DISCARD: en un "
                        "descarte FORZADO esa bandera es del RIVAL. Leela por "
                        f"{HORIZONTE[0]}/{HORIZONTE[1]}, que pasan por "
                        "`_forced_discard`",
                    ))
    return failures


RULES = (
    rule_1_imported_mutables,
    rule_2_purity,
    rule_3_agent_is_last,
    rule_4_lazy_imports,
    rule_5_no_redefinition,
    rule_6_records_are_transient,
    rule_7_gates_check_provenance,
    rule_8_discard_reads_its_horizon,
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
        print("lint_architecture: no violations")
        return 0
    for rule, file_path, line, mensaje in failures:
        print(f"{file_path}:{line}: [{rule}] {mensaje}")
    print(f"\n{len(failures)} infraccion(es)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
