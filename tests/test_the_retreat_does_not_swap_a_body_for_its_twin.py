"""A retreat that hands the front spot to the same species buys nothing.

Scenario (user, `records/registro_002_pasos_012_hasta_023.json` step 20, turn 2,
episode 91055891 vs Marnie's Grimmsnarl ex, WON):

    US (6 prizes)                        RIVAL (6 prizes)
    active Applin 40/40, ONE Grass       active Marnie's Impidimp 70/70, no energy
           (Tumbling Attack, 10, is      bench  Munkidori 110/110 on one Darkness
            already payable)                    Snorunt 70/70
    bench  Chikorita 70/70, no energy
           Applin 40/40, no energy -- just played this turn
    hand   2x Ultra Ball, Hydrapple ex, Meowth ex, Boss's Orders, Dipplin,
           Xerosic's Machinations   (the Lillie's went on step 19)

The agent RETREATED. The fee discarded the only Grass on the board -- the one
that made the active's attack payable -- and the promotion brought up the OTHER
APPLIN: the same 40 HP in the same spot, now bare, with the attack of the turn
thrown away with the energy that paid for it.

WHY THE RULE THAT EXISTS DID NOT SEE IT. `_same_species_retreat` had already
been written for this mistake (log 86510119 step 26) but it only recognised the
twin in two shapes: when EVERY bench body is the twin, and when a Lillie's
Determination in hand turns the promotion into "prefer a one-prize basic". Here
the bench also held a Chikorita and the Lillie's had been spent one step
earlier, so neither fired -- and the twin came up anyway.

WHY IT CAME UP. Not because it was preferred: because the Chikorita was
REFUSED. The Meganium line does not go active with more than one body on the
bench (the `SCORE_NEVER` of `ptcg/turn/options/card.py`, which protects Wild
Growth from the front spot), so the menu of step 22 had exactly one body it was
allowed to choose, and it was the twin. That is the premise the new case reads:
the veto only fires where the twin is CERTAIN to be what comes up, and it is
certain when the promotion has no other body it can take.

THE TWO EXCEPTIONS THE RULE NAMES (user), both about the twin itself:

  * it ATTACKS AND KNOCKS THE OPPONENT OUT -- then the swap is not a swap, it is
    a prize the body in front cannot take and the one behind can;
  * it HAS LESS LIFE LEFT than the active -- the two copies hand over the same
    prize, so the front spot is paid with the copy already spent and the healthy
    one is kept behind for its evolution.

Fix: case (c) of `_same_species_retreat` in `ptcg/turn/options/retreat.py`.

Suite 1751 green, architecture lint clean, golden corpus: 0 flips.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import OptionType
from state_builder import G, Scenario, pk

_FIX20 = (ROOT / "tests" / "fixtures"
          / "marnie_the_retreat_does_not_swap_a_body_for_its_twin_step20.json")
_FIX22 = (ROOT / "tests" / "fixtures"
          / "marnie_the_promotion_had_no_other_body_step22.json")

APPLIN = m.Applin
CHIKORITA = m.Chikorita
DIPPLIN = m.Dipplin
TAPU_BULU = m.Tapu_Bulu
GRASS = m.Basic_Grass_Energy

TUMBLING_ATTACK = 114        # Applin: 10 damage for one energy

IMPIDIMP = 646               # Marnie's Impidimp, 70 HP
FARFETCHD = 123              # a Basic whose line ends there, 70 HP


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
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m.op_is_starmie_deck = False
    m._field_at_turn_start = {}
    yield
    m._init_cards_tracking()


def _obs(fixture):
    return copy.deepcopy(json.load(open(fixture, encoding="utf-8"))["observation"])


def _chosen(obs):
    return obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]


# ---------------------------------------------------------------------------
# 1. The board: without this, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_an_applin_in_front_of_an_applin():
    o = _obs(_FIX20)
    yo = o["current"]["yourIndex"]
    mine, rival = o["current"]["players"][yo], o["current"]["players"][1 - yo]

    active = mine["active"][0]
    assert active["id"] == APPLIN and active["hp"] == 40
    assert len(active["energies"]) == 1           # the fee the retreat burns
    assert m.RETREAT_COST[APPLIN] == 1

    bench = [b for b in mine["bench"] if b]
    assert [b["id"] for b in bench] == [CHIKORITA, APPLIN]
    twin = bench[1]
    assert twin["hp"] == active["hp"] == 40        # neither exception applies:
    assert twin["energies"] == []                  # it cannot attack either

    # The turn's attachment is spent, so nothing is going to charge the twin.
    assert o["current"]["energyAttached"] is True

    # And in front of us a body the active's 10 damage does not remotely kill,
    # so nothing about this is a finisher argument.
    assert rival["active"][0]["id"] == IMPIDIMP
    assert rival["active"][0]["hp"] == 70
    assert m.attack_table[TUMBLING_ATTACK].damage == 10

    types = [x["type"] for x in o["select"]["option"]]
    assert int(OptionType.RETREAT) in types
    assert int(OptionType.ATTACK) in types


def test_the_premise_the_promotion_had_no_other_body_to_take():
    """Step 22 of the same record, the menu the retreat opens: the Chikorita is
    on it and is not chosen. The Meganium line does not go active with a bench
    of two, so the only body the promotion could take was the twin -- which is
    what makes the veto safe to apply from the retreat."""
    o = _obs(_FIX22)
    mine = o["current"]["players"][o["current"]["yourIndex"]]
    assert [b["id"] for b in mine["bench"] if b] == [CHIKORITA, APPLIN]
    assert len(o["select"]["option"]) == 2         # both bodies are offered

    assert m.agent(copy.deepcopy(o)) == [1], (
        "la promocion sube el gemelo: el Chikorita no es preferido, esta "
        "VETADO (la linea Meganium no va al activo con banca de dos)")


# ---------------------------------------------------------------------------
# 2. The decision of the record
# ---------------------------------------------------------------------------

def test_the_applin_does_not_retreat_for_the_other_applin():
    chosen = _chosen(_obs(_FIX20))
    assert chosen["type"] != int(OptionType.RETREAT), (
        "cambiar un Applin de 40 por otro Applin de 40 no compra nada y la "
        "tasa quema la unica Planta del tablero")


def test_and_the_turn_keeps_the_attack_the_fee_would_have_burnt():
    chosen = _chosen(_obs(_FIX20))
    assert chosen["type"] == int(OptionType.ATTACK), chosen
    assert chosen["attackId"] == TUMBLING_ATTACK, (
        "la Planta que la retirada descartaba es exactamente la que paga el "
        "ataque del activo")


# ---------------------------------------------------------------------------
# 3. The gates, one board each, on a deck-agnostic opponent
# ---------------------------------------------------------------------------
#
# The same shape rebuilt with StateBuilder against a Basic whose line ends
# there, so nothing below can be read as a rule about Marnie's Grimmsnarl ex.
# The hand is EMPTY and the turn's attachment already spent: what is measured
# is retreat-versus-the-rest, with no card competing for the turn.

def _twin_board(active, *bench):
    return (Scenario(turn=6, step=60, tac=3, own_prizes=6,
                     supporter_played=True, energy_played=True)
            .my_active(active)
            .my_bench(*bench)
            .op_active(pk(FARFETCHD))
            .op_bench(pk(FARFETCHD))
            .op_zones(hand=5, deck=25, prizes=6)
            .my_hand()
            .deck()
            .rest_to_discard()
            .menu_hand(with_retreat=True, with_attack=True)
            .build())


def test_the_rule_itself_the_twin_and_a_bench_the_promotion_refuses():
    """The record's shape, rebuilt: the only other body is a Chikorita, which
    the promotion will not put in front, so the twin is what comes up."""
    chosen = _chosen(_twin_board(pk(APPLIN, energies=[G], fisicas=1),
                                 pk(CHIKORITA), pk(APPLIN)))
    assert chosen["type"] == int(OptionType.ATTACK), chosen


def test_control_a_body_of_another_species_the_menu_can_take():
    """SCOPE. Swap the Chikorita for a Tapu Bulu -- outside the Meganium line,
    so the promotion is free to take it -- and the retreat is a real play
    again: this veto only speaks where the twin is the only body available."""
    chosen = _chosen(_twin_board(pk(APPLIN, energies=[G], fisicas=1),
                                 pk(TAPU_BULU), pk(APPLIN)))
    assert chosen["type"] == int(OptionType.RETREAT), chosen


def test_control_a_twin_already_damaged_still_takes_the_front():
    """LIFE gate (the user's second exception). Both copies hand over the same
    prize, so the spot is paid with the one that is already spent."""
    chosen = _chosen(_twin_board(pk(APPLIN, energies=[G], fisicas=1),
                                 pk(CHIKORITA), pk(APPLIN, hp=20)))
    assert chosen["type"] == int(OptionType.RETREAT), chosen


def test_control_a_twin_that_knocks_the_opponent_out_still_takes_the_front():
    """PRIZE gate (the user's first exception). A bare Tapu Bulu in front and
    its twin on four Grass behind it: 220 through a 70 HP body is a prize the
    active cannot take, and the fee buys it."""
    chosen = _chosen(_twin_board(pk(TAPU_BULU, energies=[G], fisicas=1),
                                 pk(CHIKORITA),
                                 pk(TAPU_BULU, energies=[G] * 4, fisicas=4)))
    assert chosen["type"] == int(OptionType.RETREAT), chosen


def test_control_with_no_twin_on_the_bench_nothing_changes():
    """The null control: the same refused Chikorita, no second Applin, and the
    retreat is untouched -- the new case reads the TWIN, not the Chikorita."""
    chosen = _chosen(_twin_board(pk(APPLIN, energies=[G], fisicas=1),
                                 pk(CHIKORITA)))
    assert chosen["type"] == int(OptionType.RETREAT), chosen
