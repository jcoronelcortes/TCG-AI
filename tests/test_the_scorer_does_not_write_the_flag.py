"""`we_go_first` was set by the LAST option priced, not by the one chosen.

`ptcg/turn/options/minor.py`, the IS_FIRST branch, used to do this:

    if o.type == YES and context == IS_FIRST:   score = SCORE_VETO
                                                AGENT_STATE.we_go_first = True
    if o.type == NO  and context == IS_FIRST:   score = 2
                                                AGENT_STATE.we_go_first = False

A scorer is called ONCE PER OPTION, so the value that survived belonged to
whichever option the simulator happened to list last. It came out right by
accident: measured over 60 openings the menu is `(YES, NO)` every single time,
so NO was always priced last and left the flag False, which is what going second
means. Flip that order and every `we_go_first` branch in the tree inverts in
silence, with nothing going red -- and there are plenty, from
`_RULES_FOREST_PLAY[0] t1_going_first` to the opening attachments.

WHY THERE IS NOTHING TO REPLACE IT WITH. `we_go_first` is a MIRROR of the board
(that is the law the invariant monitor files it under), and a mirror has exactly
one honest writer: the code that reads the observation. `agent()` already does
it -- `if state.firstPlayer >= 0: we_go_first = (firstPlayer == yourIndex)` --
and the write in the scorer was trying to PREDICT that before the board knew.
Measured: `firstPlayer` is -1 in all 60 of those menus, because the coin has not
resolved. By our next decision it is set and the flag is right.

The window is empty of readers, and that is measured too: between the IS_FIRST
menu and our next decision only the OPPONENT decides (0 or 1 of their steps),
and even inside the same call the scoring context is snapshotted before the loop
-- so the write was already invisible to everything that runs after it.

WHAT KEEPS IT OUT: `utils/lint_architecture.py` R9, which forbids any module
under `ptcg/turn/options/` from assigning to `AGENT_STATE`. That closes the
class rather than this instance. `ptcg/turn/finalize.py` writes state freely and
is deliberately outside the rule -- it runs AFTER the choice, which is exactly
the difference.
"""

import copy
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import main as m
from cg.api import OptionType, SelectContext
from lint_architecture import rule_9_scorers_do_not_write_state

_FIXTURE = ROOT / "tests" / "fixtures" / "opening_is_first_menu.json"


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _tipos(obs):
    return [o["type"] for o in obs["select"]["option"]]


# ---------------------------------------------------------------------------
# 1. The board: the coin has not resolved, so nobody can know yet
# ---------------------------------------------------------------------------

def test_the_menu_is_the_opening_one_and_the_coin_is_undecided():
    obs = _obs()
    assert obs["select"]["context"] == int(SelectContext.IS_FIRST)
    assert _tipos(obs) == [int(OptionType.YES), int(OptionType.NO)]
    assert obs["current"]["firstPlayer"] == -1, (
        "si el motor ya supiera quien sale primero, agent() lo derivaria y este "
        "fichero no tendria objeto")


# ---------------------------------------------------------------------------
# 2. The policy: we take the first turn (user, August 2026)
# ---------------------------------------------------------------------------

def test_we_choose_to_go_first():
    """Reversed from going second on the deck owner's call. This menu is only
    shown to whoever won the coin, so it is the half of the seat we control."""
    obs = _obs()
    eleccion = m.agent(obs)
    assert len(eleccion) == 1
    assert obs["select"]["option"][eleccion[0]]["type"] == int(OptionType.YES)


# ---------------------------------------------------------------------------
# 3. The defect: the answer must not depend on the order of the menu
# ---------------------------------------------------------------------------

def _elegido(obs):
    eleccion = m.agent(obs)
    return obs["select"]["option"][eleccion[0]]["type"]


def test_the_choice_survives_the_menu_being_listed_backwards():
    """The simulator lists (YES, NO) today. It owes us nothing."""
    normal = _obs()
    m.AGENT_STATE.reset()
    invertido = _obs()
    invertido["select"]["option"] = list(reversed(invertido["select"]["option"]))
    assert _tipos(invertido) == [int(OptionType.NO), int(OptionType.YES)]

    a = _elegido(normal)
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    b = _elegido(invertido)
    assert a == b == int(OptionType.YES)


def test_the_flag_does_not_depend_on_the_order_either():
    """THE ACTUAL DEFECT. With the menu backwards, the old code priced YES last
    and left `we_go_first` True while choosing to go SECOND."""
    for opciones in ([int(OptionType.YES), int(OptionType.NO)],
                     [int(OptionType.NO), int(OptionType.YES)]):
        m.AGENT_STATE.reset()
        m._init_cards_tracking()
        obs = _obs()
        obs["select"]["option"] = [{"type": t} for t in opciones]
        m.agent(obs)
        assert m.AGENT_STATE.we_go_first is False, (
            f"con el menu listado {opciones} la bandera quedo en "
            f"{m.AGENT_STATE.we_go_first}: el puntuador vuelve a escribir estado")


def test_scoring_the_menu_leaves_the_flag_exactly_as_it_found_it():
    """Stronger than the two above, and the sentence R9 encodes: pricing these
    options is not supposed to touch the flag AT ALL, in either direction."""
    for inicial in (False, True):
        m.AGENT_STATE.reset()
        m._init_cards_tracking()
        m.AGENT_STATE.we_go_first = inicial
        m.agent(_obs())
        assert m.AGENT_STATE.we_go_first is inicial, (
            f"la bandera entro como {inicial} y salio como "
            f"{m.AGENT_STATE.we_go_first}: puntuar escribio estado")


# ---------------------------------------------------------------------------
# 4. R9, both halves -- the rule is what stops this class coming back
# ---------------------------------------------------------------------------

def _modulo(tmp, texto):
    (tmp / "puntuador.py").write_text(texto)
    return rule_9_scorers_do_not_write_state(tmp)


def test_r9_catches_a_scorer_that_writes_state():
    with tempfile.TemporaryDirectory() as d:
        fallos = _modulo(Path(d), "def score_play(tc, o, score):\n"
                                  "    AGENT_STATE.we_go_first = True\n"
                                  "    return score\n")
    assert len(fallos) == 1 and fallos[0][0] == "R9"


def test_r9_catches_the_augmented_form_too():
    with tempfile.TemporaryDirectory() as d:
        fallos = _modulo(Path(d), "def score_play(tc, o, score):\n"
                                  "    AGENT_STATE.counter += 1\n"
                                  "    return score\n")
    assert len(fallos) == 1


def test_r9_says_nothing_about_READING_the_state():
    """Scorers read AGENT_STATE constantly and must go on doing so: the rule is
    about the direction, not about the name."""
    with tempfile.TemporaryDirectory() as d:
        fallos = _modulo(Path(d), "def score_play(tc, o, score):\n"
                                  "    if AGENT_STATE.we_go_first:\n"
                                  "        return score + 1\n"
                                  "    return score\n")
    assert fallos == []


def test_the_tree_itself_is_clean():
    assert rule_9_scorers_do_not_write_state() == []
