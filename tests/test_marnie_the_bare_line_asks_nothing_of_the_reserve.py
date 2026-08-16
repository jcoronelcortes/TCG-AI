"""A Marnie's line at ZERO energy is not yet the thing our reserve has to answer,
so it does not get to send the engine to the back of the queue.

Scenario (user, `records/registro_007_pasos_049_hasta_053.json` step 49,
episode 93683313, turn 7, vs Marnie's Grimmsnarl ex, **WON** -- and the gust
still went to the Morgrem):

    US (seat 0, 5 prizes)                RIVAL (6 prizes)
    active Teal Mask Ogerpon ex, 3G      active Marnie's Impidimp 70/70, **0e**
    bench  Bayleef, Meowth ex,           bench  Snorunt, Snorunt,
           **Teal Mask Ogerpon ex, 2G**         **Morgrem 100/100, 0e**,
                                                **Munkidori 110/110, 1D**,
                                                Munkidori 110/110, 0e

Boss's Orders was already played; this is the TARGET select. The agent dragged
out the **Morgrem** and left the charged Munkidori -- the body that moves 30
damage wherever it closes a knockout, reloaded every checkup by their own
Froslass -- sitting on their bench.

WHY THE ENGINE LADDER DID NOT FIRE
----------------------------------
`marnie_engine_first` asks `_marnie_bench_answers_the_grimmsnarl`, and here it
reads **False**: our reserve is a second Teal Mask Ogerpon ex holding two Grass,
BELOW its own attack cost, so it prices at zero damage against a projected 320.
With the flag down the whole engine ladder stands aside and the scores are the
plain stage tiers:

    Snorunt          3200
    Snorunt          3200
    Morgrem          9600   <- chosen, `tier_ko` 9000 + the line band
    Munkidori 1D     6450
    Munkidori 0e     3450

THE PREMISE IT WAS DEFERRING TO WAS NEVER MADE
----------------------------------------------
The bench question is owed to `ex_preevo_takes_priority`: that rung pays 19500
for "a two-prize ex attacker we cannot answer decides the game on its own", and
it is what the engine must not outbid while our active is the only body covering
the Stage 2. But it demands a **CHARGED** pre-evolution (`c.energy >= 1`), and on
this board their whole line is at zero -- the Morgrem won on the generic stage
tier alone. There was no 19500 to protect. A line carrying no energy is not the
thing the reserve answers, so it is not owed the question.

`_marnie_line_is_bare` reads it off the SAME projection the reserve question
uses (`_marnie_grimmsnarl_projection` inherits the energy of the most-charged
body of the line), so the two halves cannot drift apart.

THE CONTROL, and it is the sibling record's board: put a single Darkness on
their Morgrem and the line stops being bare. `ex_preevo_takes_priority` comes
back with its 19500, our bench still does not cover the Stage 2, and cutting the
line is once again what keeps us alive -- the gust returns to the Morgrem.

Switch: `MARNIE_ENGINE_BARE_LINE_NEEDS_NO_RESERVE`. False restores exactly the
previous behaviour (the reserve question asked on every board), which is what
makes the two arms of this test one tree with one name rebound.
"""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from ptcg.state.agent_state import AGENT_STATE

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step49_la_linea_pelada_no_le_debe_nada_a_la_reserva.json")

IMPIDIMP = m.Marnies_Impidimp
MORGREM = m.Marnies_Morgrem
GRIMMSNARL = m.Grimmsnarl_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
# The print these lists actually play is the 70 HP one (`Snorunt_Ice`, 860), not
# the other Snorunt in the table -- both sit on the same rung of the ladder.
SNORUNT = m.Snorunt_Ice
MUNKIDORI = m.Munkidori
DARKNESS = m.DARKNESS_ENERGY_TYPE

# Their bench, by index, on the fixture.
CHARGED_MUNKIDORI = 3
BARE_MUNKIDORI = 4


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    AGENT_STATE.op_is_marnie_deck = False
    yield
    m._init_cards_tracking()
    AGENT_STATE.op_is_marnie_deck = False


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _me(o):
    return o["current"]["players"][o["current"]["yourIndex"]]


def _op(o):
    return o["current"]["players"][1 - o["current"]["yourIndex"]]


def _charge(body, n=1):
    """Put `n` Darkness on one of THEIR bodies, in the shape the log writes."""
    body["energies"] = [DARKNESS] * n
    body["energyCards"] = [{"id": 8, "playerIndex": 1, "serial": 900 + i}
                           for i in range(n)]
    return body


def _boss_globals():
    """The namespace `ptcg/decision/boss_orders.py` reads its constants from.

    They are imported BY VALUE, so an arm that rebinds one has to rebind it
    there -- the same reach `utils/gate_marnie_the_engine_before_the_line.py`
    uses.
    """
    return m._ctx_gust_target.__globals__


def _state_pair(o):
    """`my_state` / `op_state` shaped the way the calculators read them."""
    def pk(d):
        return SimpleNamespace(id=d["id"], hp=d["hp"], maxHp=d["maxHp"],
                               energies=list(d["energies"]),
                               energyCards=d["energyCards"], tools=d["tools"],
                               serial=d["serial"])
    me, op = _me(o), _op(o)
    return (SimpleNamespace(active=[pk(me["active"][0])],
                            bench=[pk(b) for b in me["bench"]]),
            SimpleNamespace(active=[pk(op["active"][0])],
                            bench=[pk(b) for b in op["bench"]]))


def _grass(my_state):
    return sum(len(p.energies) for p in [my_state.active[0]] + my_state.bench)


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_target_select_of_step_49():
    o = _obs()
    assert o["current"]["turn"] == 7
    # Boss's Orders is already down: the menu is five bodies of THEIR bench.
    assert o["select"]["context"] == 3
    assert [op["index"] for op in o["select"]["option"]] == [0, 1, 2, 3, 4]
    assert all(op["playerIndex"] == 1 - o["current"]["yourIndex"]
               for op in o["select"]["option"])

    # Us: an Ogerpon ex in front on three Grass and a SECOND one behind it on
    # two -- below its own attack cost, which is why the reserve reads as none.
    assert _me(o)["active"][0]["id"] == OGERPON
    assert len(_me(o)["active"][0]["energies"]) == 3
    assert [b["id"] for b in _me(o)["bench"]][2] == OGERPON
    assert len(_me(o)["bench"][2]["energies"]) == 2

    # Them: the line (Impidimp active, Morgrem benched) and the engine -- and
    # NOTHING on the line carries energy.
    assert _op(o)["active"][0]["id"] == IMPIDIMP
    assert [b["id"] for b in _op(o)["bench"]] == [
        SNORUNT, SNORUNT, MORGREM, MUNKIDORI, MUNKIDORI]
    assert _op(o)["active"][0]["energies"] == []
    assert _op(o)["bench"][2]["energies"] == []
    # ...while one of the two Munkidori does, and they are otherwise identical.
    assert len(_op(o)["bench"][CHARGED_MUNKIDORI]["energies"]) == 1
    assert _op(o)["bench"][BARE_MUNKIDORI]["energies"] == []
    assert (_op(o)["bench"][CHARGED_MUNKIDORI]["hp"]
            == _op(o)["bench"][BARE_MUNKIDORI]["hp"] == 110)


# ---------------------------------------------------------------------------
# 2. The two readings, and the asymmetry between them
# ---------------------------------------------------------------------------

def test_our_reserve_does_not_cover_the_grimmsnarl_here():
    """THE READING THAT USED TO DECIDE ALONE. The benched Ogerpon ex holds two
    Grass, under the cost of Myriad Leaf Shower, so it does no damage at all
    against a projected 320."""
    o = _obs()
    my_state, op_state = _state_pair(o)
    assert not m._marnie_bench_answers_the_grimmsnarl(
        my_state, op_state, _grass(my_state), len(my_state.bench), False)


def test_the_projection_is_bare_because_their_whole_line_is():
    o = _obs()
    _, op_state = _state_pair(o)
    projected = m._marnie_grimmsnarl_projection(op_state)
    assert projected.id == GRIMMSNARL and projected.hp == 320
    assert list(projected.energies) == []
    assert m._marnie_line_is_bare(op_state)


def test_one_darkness_anywhere_on_the_line_ends_it():
    """The projection inherits the energy of the MOST charged body of the line,
    so a single Darkness on the Morgrem is enough."""
    o = _obs()
    _charge(_op(o)["bench"][2])
    _, op_state = _state_pair(o)
    assert not m._marnie_line_is_bare(op_state)


def test_a_charged_grimmsnarl_already_in_play_is_not_bare():
    o = _obs()
    _charge(_op(o)["bench"][2], 3)
    _op(o)["bench"][2].update(id=GRIMMSNARL, hp=120, maxHp=320)
    _, op_state = _state_pair(o)
    assert not m._marnie_line_is_bare(op_state)


def test_with_no_marnie_body_in_play_there_is_nothing_to_call_bare():
    """No line, no projection: the reading is False and not vacuously True, so
    it can never turn the engine ladder on outside the matchup."""
    o = _obs()
    _op(o)["active"][0].update(id=m.Dreepy, hp=60, maxHp=60)
    _op(o)["bench"][2].update(id=m.Drakloak, hp=90, maxHp=90, preEvolution=[])
    _, op_state = _state_pair(o)
    assert m._marnie_grimmsnarl_projection(op_state) is None
    assert not m._marnie_line_is_bare(op_state)


# ---------------------------------------------------------------------------
# 3. The decision
# ---------------------------------------------------------------------------

def test_the_gust_takes_the_charged_munkidori_and_not_the_morgrem():
    o = _obs()
    chosen = m.agent(o)
    assert chosen == [CHARGED_MUNKIDORI], (
        "con su linea a CERO energias no hay 19500 que proteger: el gusteo va "
        "al Munkidori CARGADO, que es el motor que nos esta ganando la partida")
    assert _op(o)["bench"][chosen[0]]["id"] == MUNKIDORI


def test_it_is_the_charged_copy_and_not_the_bare_twin():
    """The two Munkidori are the same species at the same HP: only the energy
    split (`_marnie_engine_rung`) separates them, and it has to survive this
    rung turning on."""
    o = _obs()
    assert m.agent(o) == [CHARGED_MUNKIDORI]


def test_the_control_one_darkness_on_the_line_brings_the_morgrem_back():
    """THE CONDITION, from the other side. Charge their Morgrem and the line is
    a real threat again: `ex_preevo_takes_priority` gets its 19500, our bench
    still does not cover the Stage 2, and cutting the line is the play."""
    o = _obs()
    _charge(_op(o)["bench"][2])
    chosen = m.agent(o)
    assert _op(o)["bench"][chosen[0]]["id"] == MORGREM, (
        "con la linea cargada y sin reserva en banca, la regla de la linea "
        "evolutiva sigue mandando")


def test_the_switch_off_restores_the_morgrem(monkeypatch):
    """THE BASELINE ARM. One name rebound and the tree is the previous one."""
    monkeypatch.setitem(_boss_globals(),
                        "MARNIE_ENGINE_BARE_LINE_NEEDS_NO_RESERVE", False)
    o = _obs()
    chosen = m.agent(o)
    assert _op(o)["bench"][chosen[0]]["id"] == MORGREM


def test_the_reading_does_not_leave_the_marnie_matchup():
    """It hangs off `op_is_marnie_deck` like the rest of the ladder: the same
    board with the Dragapult line in place of Marnie's stops firing."""
    o = _obs()
    _op(o)["active"][0].update(id=m.Dreepy, hp=60, maxHp=60)
    _op(o)["bench"][2].update(id=m.Drakloak, hp=90, maxHp=90, preEvolution=[])
    chosen = m.agent(o)
    assert _op(o)["bench"][chosen[0]]["id"] == m.Drakloak


# ---------------------------------------------------------------------------
# 4. The band: what turning the rung on must NOT outbid
# ---------------------------------------------------------------------------

def test_a_two_prize_knockout_still_outranks_the_engine_on_a_bare_line():
    """The bracket the engine floor has always carried. Put a Grimmsnarl ex we
    can finish on their bench, still carrying no energy -- the line is bare, so
    this rung is live -- and the TWO prizes win over the one-prize engine."""
    o = _obs()
    _op(o)["bench"][2].update(id=GRIMMSNARL, hp=60, maxHp=320)
    chosen = m.agent(o)
    assert _op(o)["bench"][chosen[0]]["id"] == GRIMMSNARL, (
        "dos premios siguen ganando al motor: el corchete de la escalera")
