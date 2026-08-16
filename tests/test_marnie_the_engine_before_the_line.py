"""The Marnie deck does not win with its line -- it wins with the two abilities
behind it, and the gust goes there once the line has an answer.

Scenario (user, `records/registro_008_pasos_108_hasta_114.json` step 110,
episode 93525290, turn 8, vs Marnie's Grimmsnarl ex, **LOST**):

    US (seat 1, 4 prizes)                  RIVAL (5 prizes)
    active  Hydrapple ex 270/330, 2G       active  Marnie's Impidimp 70/70, 2D
    bench   **Ogerpon ex 4G**, Meowth ex,  bench   Froslass, **Morgrem 100 HP,
            Ogerpon ex 3G, Ogerpon ex 2G,          Stage 1, 2D**, Froslass,
            Fezandipiti ex                         Impidimp 1D, **Munkidori 1D**

Boss's Orders was already played; this is the TARGET select. The agent dragged
out the **Morgrem** and knocked it out, which is what
`ex_preevo_takes_priority` is written to do: the highest link of an ex line, with
energy, is lifted to an effective 19500 (12000 of `tier_ko` + the rung), against
6450 for the Munkidori. One prize, the line rebuilt next turn, and the game lost.

WHY THE LINE RULE IS THE WRONG READING HERE
-------------------------------------------
That rung is priced for the premise "a two-prize ex attacker we cannot answer
decides the game on its own". Against this list the premise is false:

  * Marnie's Grimmsnarl ex is 320 HP and **weak to Grass** (`weakness == 1` in
    the card data), so Myriad Leaf Shower doubles into it;
  * the **benched** Teal Mask Ogerpon ex carrying four Grass reads 150-210 base
    -> **300-420** after weakness, against an effective **300** -- their own
    Freezing Shroud takes 20 off any body that prints an Ability, and Punk Up
    is an Ability.

So the answer to the Stage 2 was already parked on our bench. What was never
answered is the pair of abilities that had been grinding the board down all
game and that no evolution step gates:

  * **Froslass**, *Freezing Shroud*: 1 counter on EVERY Pokemon with an Ability
    at BOTH checkups. Our whole board has abilities -> 20 per round per copy,
    and their bench had two.
  * **Munkidori**, *Adrena-Brain*: once per turn per copy it MOVES up to 3
    counters from one of THEIR Pokemon onto any one of OURS. 30 aimed wherever
    it closes a knockout, reloaded every checkup by their own Froslass.

Munkidori is the more dangerous of the two because it AIMS. The drip is
arithmetic we can plan around; the move is what turns a body we had counted as
surviving into a corpse. Hence the order: Munkidori, then the Froslass that
feeds it, then the Snorunt that becomes the next Froslass.

THE CONDITION, AND WHY IT IS A CONDITION
-----------------------------------------
`marnie_engine_first` is only true while a body on OUR BENCH answers the
Grimmsnarl ex. With our ACTIVE as the only answer the line rule keeps its 19500
and its reason: the active can be knocked out, and then nothing covers the
Stage 2. The bench and not the whole board is the point -- an answer that has to
stay in the active spot to exist is not a reserve.

THE BAND. 15000 sits between the one-prize knockout tiers (a charged Stage 1 is
12700 once the ex-preevo rung stands down) and a genuine TWO-prize knockout
(21000): if the Grimmsnarl ex is itself on their bench and we can finish it, two
prizes still win. It is applied with `max` so the order among the three engine
bodies is absolute and not the stage table's.

Measurement: **1 flip** in the whole golden corpus -- this step -- plus the
target of `tests/test_boss_gust_the_high_step_of_the_bench.py` step 136, the
other recorded loss to this list, which moves the same way for the same reason.
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
            / "marnie_step110_el_motor_antes_que_la_linea.json")

IMPIDIMP = m.Marnies_Impidimp
MORGREM = m.Marnies_Morgrem
GRIMMSNARL = m.Grimmsnarl_ex
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
FROSLASS = m.Froslass
MUNKIDORI = m.Munkidori


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


def _strip_the_bench(o):
    """Take the reserve away: with no charged body behind it, our ACTIVE is the
    only thing that covers a Grimmsnarl ex."""
    for b in _me(o)["bench"]:
        b["energies"], b["energyCards"] = [], []
    return o


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

def test_the_fixture_is_the_target_select_of_step_110():
    o = _obs()
    assert o["current"]["turn"] == 8
    # Boss's Orders is already down: the menu is five bodies of THEIR bench.
    assert o["select"]["context"] == 3
    assert [op["index"] for op in o["select"]["option"]] == [0, 1, 2, 3, 4]
    assert all(op["playerIndex"] == 1 - o["current"]["yourIndex"]
               for op in o["select"]["option"])

    # Us: a Hydrapple ex in front and THREE charged Ogerpon ex behind it.
    assert _me(o)["active"][0]["id"] == HYDRAPPLE
    assert [b["id"] for b in _me(o)["bench"]] == [
        OGERPON, m.Meowth_ex, OGERPON, OGERPON, m.Fezandipiti_ex]
    assert len(_me(o)["bench"][0]["energies"]) == 4

    # Them: the line (Impidimp active, a charged Morgrem benched) plus the
    # engine (two Froslass and a Munkidori).
    assert _op(o)["active"][0]["id"] == IMPIDIMP
    assert [b["id"] for b in _op(o)["bench"]] == [
        FROSLASS, MORGREM, FROSLASS, IMPIDIMP, MUNKIDORI]
    assert len(_op(o)["bench"][1]["energies"]) == 2


def test_the_grimmsnarl_is_weak_to_grass_which_is_the_whole_premise():
    from ptcg.cards.tables import card_table
    from cg.api import EnergyType
    data = card_table.get(GRIMMSNARL)
    assert data.hp == 320 and data.ex
    assert data.weakness == EnergyType.GRASS


# ---------------------------------------------------------------------------
# 2. The reading: does our BENCH answer the Grimmsnarl ex?
# ---------------------------------------------------------------------------

def test_the_bench_ogerpon_covers_the_grimmsnarl():
    o = _obs()
    my_state, op_state = _state_pair(o)
    assert m._marnie_bench_answers_the_grimmsnarl(
        my_state, op_state, _grass(my_state), len(my_state.bench), False)


def test_without_energy_on_the_bench_it_does_not():
    o = _strip_the_bench(_obs())
    my_state, op_state = _state_pair(o)
    assert not m._marnie_bench_answers_the_grimmsnarl(
        my_state, op_state, _grass(my_state), len(my_state.bench), False)


def test_the_projection_inherits_the_energy_of_the_line():
    """No Grimmsnarl ex is in play, so the reading projects the one Punk Up is a
    step away from putting down: full HP, carrying what the most charged body of
    the line already holds (the Morgrem's two Darkness)."""
    _, op_state = _state_pair(_obs())
    projected = m._marnie_grimmsnarl_projection(op_state)
    assert projected.id == GRIMMSNARL
    assert projected.hp == projected.maxHp == 320
    assert len(projected.energies) == 2


def test_a_grimmsnarl_already_in_play_is_read_off_the_board():
    """When it has already evolved there is nothing to project: its real HP and
    its real energy are what our bench has to cover."""
    o = _obs()
    _op(o)["bench"][1].update(id=GRIMMSNARL, hp=120, maxHp=320)
    _, op_state = _state_pair(o)
    projected = m._marnie_grimmsnarl_projection(op_state)
    assert projected.id == GRIMMSNARL and projected.hp == 120


def test_with_no_marnie_body_in_play_there_is_nothing_to_project():
    o = _obs()
    for b in _op(o)["bench"]:
        b["id"] = FROSLASS
    _op(o)["active"][0]["id"] = FROSLASS
    _, op_state = _state_pair(o)
    assert m._marnie_grimmsnarl_projection(op_state) is None


# ---------------------------------------------------------------------------
# 3. The decision
# ---------------------------------------------------------------------------

def test_the_gust_takes_the_munkidori_and_not_the_morgrem():
    o = _obs()
    chosen = m.agent(o)
    assert _op(o)["bench"][chosen[0]]["id"] == MUNKIDORI, (
        "con la respuesta al Grimmsnarl ex ya en banca, el gusteo va primero "
        "al Munkidori: mueve 30 de dano donde cierra un KO y su municion se "
        "recarga sola con su propia Froslass")


def test_without_the_munkidori_it_takes_a_froslass():
    """"...y si no esta disponible, por Froslass": the ladder is Munkidori ->
    Froslass -> Snorunt, and it steps down when a rung is missing."""
    o = _obs()
    _op(o)["bench"][4].update(id=FROSLASS, hp=90, maxHp=90)
    chosen = m.agent(o)
    assert _op(o)["bench"][chosen[0]]["id"] == FROSLASS


def test_without_the_engine_at_all_it_goes_back_to_the_line():
    """The ladder names three bodies. With none of them on their bench there is
    nothing to reorder and the line rung decides as it always did."""
    o = _obs()
    for i in (0, 2, 4):
        _op(o)["bench"][i].update(id=IMPIDIMP, hp=70, maxHp=70)
    chosen = m.agent(o)
    assert _op(o)["bench"][chosen[0]]["id"] == MORGREM


def test_the_control_the_active_alone_keeps_the_line_rule():
    """THE CONDITION. Strip the reserve and `ex_preevo_takes_priority` comes
    back with its 19500: our active covers the Grimmsnarl ex and nothing else
    does, so cutting the line is still what keeps us alive."""
    o = _strip_the_bench(_obs())
    chosen = m.agent(o)
    assert _op(o)["bench"][chosen[0]]["id"] == MORGREM, (
        "sin reserva en banca, la regla de la linea evolutiva sigue mandando")


def test_the_ladder_does_not_leave_the_marnie_matchup():
    """It is the ONE per-deck rung in this chain, so it has to be provably
    inert everywhere else: the same board with the Dragapult line in place of
    Marnie's stops firing, and the Munkidori is not gusted."""
    o = _obs()
    _op(o)["active"][0].update(id=m.Dreepy, hp=60, maxHp=60)
    _op(o)["bench"][1].update(id=m.Drakloak, hp=90, maxHp=90, preEvolution=[])
    _op(o)["bench"][3].update(id=m.Dreepy, hp=60, maxHp=60)
    chosen = m.agent(o)
    assert _op(o)["bench"][chosen[0]]["id"] == m.Drakloak


# ---------------------------------------------------------------------------
# 4. The band: what the rung must NOT outbid
# ---------------------------------------------------------------------------

def test_the_rung_sits_between_a_one_prize_and_a_two_prize_knockout():
    assert m.prize_count_op(SimpleNamespace(
        id=MUNKIDORI, energies=[], energyCards=[], tools=[])) == 1
    # A one-prize Stage 1 knockout tops out at 12000 + its line band; a
    # two-prize ex knockout starts at tier 7 = 21000.
    top_of_the_one_prize_band = 4 * 3000 + 1100
    floor_of_the_two_prize_band = 7 * 3000
    rung = m.BOSS_SCORE_MARNIE_ENGINE_FIRST + max(
        m.MARNIE_ENGINE_GUST_RANK.values())
    assert top_of_the_one_prize_band < rung < floor_of_the_two_prize_band


def test_the_ladder_order_is_munkidori_then_froslass_then_snorunt():
    rank = m.MARNIE_ENGINE_GUST_RANK
    assert rank[MUNKIDORI] > rank[FROSLASS] > rank[m.Snorunt]
    # Both prints of Snorunt: the lists actually play the 70 HP one (it is the
    # `preEvolution` of both Froslass in this very record).
    assert rank[m.Snorunt] == rank[m.Snorunt_Ice]
    assert {b["preEvolution"][0]["id"] for b in _op(_obs())["bench"]
            if b["id"] == FROSLASS} == {m.Snorunt_Ice}
