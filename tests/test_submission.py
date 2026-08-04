"""Submission smoke test: that the package WORKS in the Kaggle container.

This file covers the only gap the rest of the suite canNOT see. Under
pytest, `main` is a normally imported module and the project root is in
`sys.path` permanently; in the container neither of those two things
happens. `kaggle_environments.agent.get_last_callable` COMPILES main.py and
executes it with `exec` in an empty dict, with the agent's directory in `sys.path`
ONLY during that exec, and keeps the LAST callable of the namespace.

Hence the three failure modes verified here (docs/project-history.md, I1):

  I1a  one of our own packages imported for the first time at DECISION time
       -> ModuleNotFoundError in the middle of the game.
  I1b  anything that binds a new callable AFTER `def agent`
       (including a compatibility re-export, and note: a class is
       callable too) -> the container takes THAT as the agent. Silent and lethal.
  I1c  `main.py` never enters sys.modules -> no submodule can do
       `import main`.

`kaggle_environments` is NOT added to requirements-dev.txt: the agent depends on
nothing external and that project constraint is kept. The loader is copied
VERBATIM into `tests/kaggle_loader.py`; if Kaggle changed it, that is the only
place that has to be updated.

WHY SUBPROCESSES: `cg/sim.py` calls `lib.GameInitialize()` when imported, and
doing that twice in the same process ABORTS the interpreter -- so `cg` cannot be
unloaded from sys.modules to reload it from the packaged copy. Besides,
if `ptcg` were already imported by another test, failure I1a would not reproduce.
A clean interpreter per case solves both things.
"""

import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
for _p in (str(ROOT), str(ROOT / "utils")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import package_project as ep  # noqa: E402

FIXTURE = TESTS_DIR / "fixtures" / "alakazam_boss_before_ub_step64.json"


# A runner that executes in a CLEAN interpreter: it loads the agent the way the
# container does and writes the result as JSON.
#
# It imports `kaggle_loader` and NOT this module: test_submission.py puts the project
# root into sys.path to reach utils/, and that would make one of our own packages
# imported late DO resolve in the subprocess -- masking exactly the
# I1a failure this file exists to detect.
_RUNNER = """
import json, os, sys
sys.path.insert(0, {tests_dir!r})
from kaggle_loader import get_last_callable

main_py, cwd_carga, cwd_decision, fixture, salida = sys.argv[1:6]
resultado = {{}}
try:
    os.chdir(cwd_carga)
    with open(main_py) as f:
        fn = get_last_callable(f.read(), path=main_py)
    resultado["nombre"] = getattr(fn, "__name__", repr(fn))
    os.chdir(cwd_decision)          # el contenedor NO hace chdir al dir del agente
    with open(fixture) as f:
        obs = json.load(f)["observation"]
    resultado["decision"] = fn(obs)
    resultado["main_en_sys_modules"] = "main" in sys.modules
except BaseException as e:
    resultado["error"] = "{{}}: {{}}".format(type(e).__name__, e)
# Si el callable secuestro el punto de entrada (I1b), lo que devuelve puede no
# ser serializable: degradar a repr en vez de morir con un JSONDecodeError
# opaco en el test.
try:
    json.dumps(resultado.get("decision"))
except TypeError:
    resultado["decision"] = "<no serializable: {{}}>".format(
        type(resultado["decision"]).__name__)
with open(salida, "w") as f:
    json.dump(resultado, f)
"""


def _load_in_subprocess(main_py, load_cwd, cwd_decision, tmp_path, etiqueta):
    """Loads `main_py` with Kaggle's loader in a clean interpreter."""
    script = tmp_path / f"runner_{etiqueta}.py"
    script.write_text(_RUNNER.format(tests_dir=str(TESTS_DIR)))
    output = tmp_path / f"salida_{etiqueta}.json"

    proc = subprocess.run(
        [sys.executable, str(script), str(main_py), str(load_cwd),
         str(cwd_decision), str(FIXTURE), str(output)],
        capture_output=True, text=True, timeout=300,
    )
    assert output.exists(), (
        f"el runner ({etiqueta}) murio sin escribir resultado.\n"
        f"returncode={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
    return json.loads(output.read_text())


# ===========================================================================
# I1b -- the entry point
# ===========================================================================
def test_the_kaggle_loader_keeps_agent(tmp_path):
    """The LAST callable of main.py has to be `agent`.

    If this fails, something binds a new callable after `def agent` (a
    compatibility re-export at the end of the file is the typical cause). The
    container would take THAT function as the agent and the game would die with a
    TypeError, without any other test noticing.
    """
    r = _load_in_subprocess(ROOT / "main.py", ROOT, ROOT, tmp_path, "entrada")
    assert "error" not in r, r["error"]
    assert r["nombre"] == "agent", (
        f"el cargador de Kaggle se quedaria con {r['nombre']!r} en vez de con "
        "'agent': mueve los re-exports ARRIBA, antes de `def agent`"
    )


def test_main_is_not_a_module_for_the_container(tmp_path):
    """I1c: after the exec, `main` is NOT in sys.modules.

    It freezes the reason why no submodule of one of our packages can
    do `import main` -- and why the global state cannot stay in
    main.py once it is modularised (wave 3).
    """
    r = _load_in_subprocess(ROOT / "main.py", ROOT, ROOT, tmp_path, "modulo")
    assert "error" not in r, r["error"]
    assert r["main_en_sys_modules"] is False


# ===========================================================================
# packaging -- what main.py imports has to travel
# ===========================================================================
def test_the_submission_includes_the_packages_main_imports(tmp_path):
    """Every local package imported by main.py appears in the tar."""
    target_path = tmp_path / "submission.tar.gz"
    incluidos = ep.build(target_path=target_path)

    with tarfile.open(target_path) as tar:
        raices = {Path(mi.name).parts[0] for mi in tar.getmembers()}

    assert "main.py" in raices and "deck.csv" in raices
    for path in incluidos:
        assert path.name in raices, (
            f"{path.name} lo importa main.py pero no viaja en la submission"
        )
    # cg/ is the historical minimum; if it disappears, the detection broke
    assert "cg" in raices


def test_la_submission_no_lleva_pycache(tmp_path):
    target_path = tmp_path / "submission.tar.gz"
    ep.build(target_path=target_path)
    with tarfile.open(target_path) as tar:
        names = [mi.name for mi in tar.getmembers()]
    assert not [n for n in names if "__pycache__" in n or n.endswith((".pyc", ".pyo"))]


# ===========================================================================
# I1a / I1c -- end-to-end: package, unpack and DECIDE
# ===========================================================================
def test_the_packaged_submission_decides_like_the_tree(tmp_path):
    """It packages, unpacks into a clean dir, loads with the real loader and
    compares the decision with that of the working tree's main.py.

    It is the test that catches I1a (one of our packages not importable at
    decision time): it blows up here with a ModuleNotFoundError and nowhere else.
    """
    target_path = tmp_path / "submission.tar.gz"
    ep.build(target_path=target_path)

    agent_dir = tmp_path / "kaggle_simulations" / "agent"
    agent_dir.mkdir(parents=True)
    with tarfile.open(target_path) as tar:
        tar.extractall(agent_dir, filter="data")

    # Reference: the tree's main.py.
    ref = _load_in_subprocess(ROOT / "main.py", ROOT, ROOT, tmp_path, "ref")
    assert "error" not in ref, ref["error"]

    # Candidate: the submission's; the DECISION is taken with the CWD outside the
    # agent's directory, because the container does not chdir.
    cand = _load_in_subprocess(
        agent_dir / "main.py", agent_dir, tmp_path, tmp_path, "cand"
    )
    assert "error" not in cand, cand["error"]

    assert cand["nombre"] == "agent"
    assert cand["decision"] == ref["decision"], (
        f"la submission decide {cand['decision']} y el arbol {ref['decision']}"
    )
    assert isinstance(cand["decision"], list) and cand["decision"]


# ===========================================================================
# I3 -- the facade: what the suite consumes from `main` still exists
# ===========================================================================
def test_main_reexports_what_the_suite_consumes():
    """Every `m.<something>` the tests use has to keep resolving.

    The refactor moved ~15,000 lines to `ptcg/`, and `main.py` re-exports them. This
    test turns a facade breakage into a readable, localised failure, instead
    of dozens of AttributeErrors scattered across the suite.
    """
    import re
    import main as m

    usados = set()
    patron = re.compile(r"\bm\.([A-Za-z_]\w*)")
    for path in (ROOT / "tests").glob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        # Only the files where `m` IS the module: in others `m` can be
        # anything (in this very file, a member of the tar).
        if "import main as m" not in text:
            continue
        usados.update(patron.findall(text))

    faltan = sorted(n for n in usados if not hasattr(m, n))
    assert not faltan, f"main.py dejo de reexportar: {faltan}"


def test_agent_is_the_last_thing_in_the_module():
    """I1b, also checked STATICALLY.

    `tests/test_architecture.py` already watches it with the linter and the smoke test above
    checks it by really loading; this pins it over the tree as well, which is
    where the error is seen as it is written.
    """
    import ast
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    assert isinstance(tree.body[-1], ast.FunctionDef)
    assert tree.body[-1].name == "agent", (
        f"lo ultimo de main.py es {getattr(tree.body[-1], 'name', '?')}, no `agent`")
