"""The self-play baseline must run the ref's `ptcg/`, not the working tree's.

WHY THIS TEST EXISTS (user, August 2026, measured). `load_agent_from_git` used
to fetch a single file -- `git show <ref>:main.py` -- write it to a temporary
path and import it from there. Its thirty-nine `from ptcg... import` lines then
resolved through `sys.path` to the WORKING TREE, so the baseline and the
candidate shared every module object under `ptcg`:

    baseline resolves ptcg.turn.options.card to .../ptcg/turn/options/card.py
    SAME MODULE OBJECT as working tree: True

While main.py WAS the agent that was harmless. After the refactor main.py is
11 328 lines against 26 571 in `ptcg/`, and every rule now lives in the package
-- so a change there measured EXACTLY ZERO difference, by construction, in the
two tools CONTRIBUTING names as the heavy gates: `utils/selfplay.py` and
`utils/matchup_matrix.py`, which reuses the same loader. A gate that cannot see
the change it is gating reports "neutral", and the project's written rule is
that neutral means revert.

The mechanism that makes the fix work is already enforced elsewhere: rule R4 of
`utils/lint_architecture.py` forbids lazy imports of our own package, so every
`ptcg` import happens while the module executes -- which is exactly the window
`load_agent` prepends the ref's root to `sys.path` for. If R4 were ever relaxed,
this test is what would notice.

What is deliberately NOT isolated: `cg` (importing it twice calls
`GameInitialize()` again and aborts the interpreter -- both agents must play
inside the same simulator) and `deck.csv` (read relative to the process's
working directory, so both sides pilot the same sixty cards).
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))


def ptcg_files_of(agent):
    """Which `ptcg/` files the functions this agent imported were defined in.

    main.py imports names, not modules, so the package cannot be reached through
    its namespace directly -- and `sys.modules` is deliberately restored after
    each load. A function carries its defining module's globals, which is the
    one handle that survives: `__globals__['__file__']`.
    """
    files = set()
    for value in vars(agent).values():
        if isinstance(value, types.FunctionType):
            name = value.__globals__.get("__name__", "")
            path = value.__globals__.get("__file__")
            if path and name.startswith("ptcg"):
                files.add(Path(path).resolve())
    return files


@pytest.fixture(scope="module")
def sp():
    spec = importlib.util.spec_from_file_location(
        "selfplay_under_test", ROOT / "utils" / "selfplay.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_baseline_materialises_the_whole_tree(sp):
    root = sp.checkout_tree("HEAD", "gate_isolation_probe")
    assert (root / "main.py").is_file()
    assert (root / "ptcg" / "state" / "agent_state.py").is_file(), (
        "the baseline must carry its own ptcg/ package, not just main.py")
    assert root != ROOT


def test_the_baseline_imports_that_tree_and_not_the_working_one(sp):
    """The decisive one, and the exact shape of the bug it replaces."""
    base = sp.load_agent_from_git("HEAD", "gate_isolation_base")
    files = ptcg_files_of(base)

    assert files, "the baseline imported no ptcg function at all"
    intruders = [f for f in files if ROOT in f.parents]
    assert not intruders, (
        "the baseline's ptcg imports resolved to the WORKING TREE -- the gate "
        f"is blind to every change under ptcg/: {sorted(intruders)[:3]}")


def test_the_two_agents_do_not_share_the_package(sp):
    """Same guarantee, stated as the property the measurement depends on."""
    base = sp.load_agent_from_git("HEAD", "gate_pair_base")
    cand = sp.load_agent(ROOT / "main.py", "gate_pair_cand")

    base_files, cand_files = ptcg_files_of(base), ptcg_files_of(cand)
    assert base_files and cand_files
    assert base_files.isdisjoint(cand_files), (
        "candidate and baseline share ptcg modules: "
        f"{sorted(base_files & cand_files)[:3]}")
    # Both must still see the SAME set of modules -- a baseline missing half the
    # package would also come out "disjoint", and would measure nothing either.
    assert ({f.name for f in base_files} == {f.name for f in cand_files})
    # And the state singletons stay separate, which is what wave 3 already fixed
    # and what this change must not undo.
    assert base.AGENT_STATE is not cand.AGENT_STATE
