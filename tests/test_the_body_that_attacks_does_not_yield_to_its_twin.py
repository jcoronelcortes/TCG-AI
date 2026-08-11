"""The body that can attack does not hand the front spot to its own copy.

Scenario (user, `records/registro_004_pasos_030_hasta_057.json` step 55, turn 4,
episode 91530672 vs Mega Abomasnow ex, LOST):

    US (6 prizes)                          RIVAL (5 prizes)
    active Teal Mask Ogerpon ex 210/210     active Mega Abomasnow ex 350/350
           on 4 Grass -- Myriad Leaf                on 2 energy, hits for 200
           Shower is ON THE MENU
    bench  Meganium 160, Meowth ex 170,
           Applin 40, Fezandipiti ex 210,
           Teal Mask Ogerpon ex 210 on 2   <- the twin, and it cannot attack
    hand   Boss's Orders, 2x Lillie's, Hydrapple ex, Lana's Aid

The agent RETREATED. The fee discarded a Grass, the promotion brought up the
OTHER Ogerpon ex -- correctly, by its own criteria: at 200 damage the only
bodies that endure are the two 210s and the twin scored highest among them --
and the turn ended with the same 210 HP ex in front, one energy poorer and
unable to attack. The attack it had was thrown away for nothing.

WHY THE TWIN RULE THAT EXISTS DID NOT SEE IT. Cases (a)-(c) of
`_same_species_retreat` all answer the question "will the twin be the body that
comes up?", and they only answer it where the twin is the ONLY body the
promotion may take (see `test_the_retreat_does_not_swap_a_body_for_its_twin`).
Here it was one candidate among five, so none of them fired.

WHAT THE NEW CASE (d) ASKS INSTEAD. Not who comes up -- on this board no answer
was worth the fee, because THE FRONT SPOT CANNOT BE UPGRADED: nothing behind
attacks, nothing behind is bigger, the active endures the hit it is facing, and
one of the bodies back there is the active's own copy. Whatever the promotion
picks, the turn gives back the attack it already had and gets no more body for
it.

AND WHY THE RETREAT WAS SCORED SO HIGH IN THE FIRST PLACE. `_raging_sac_pivot`,
the prize-mismatch sacrifice, is written on the sentence "their attacker
one-shots any of ours, so whoever is in front is going to fall" -- a claim about
the BOARD that the flag only checked as a MATCHUP. Their Mega Abomasnow ex hits
for 200 and our active had 210: it endured, there was no prize to save, and the
sacrifice sacrificed nothing. It now reads the board the same way its
deck-agnostic twin `_doomed_ex_sac_pivot` does, the opponent's unplayed
evolution included.

Both fixes are in `ptcg/turn/options/retreat.py` and either one alone turns this
decision into the attack; the tests below pin each of them separately.
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
from cg.api import OptionType, Pokemon
from state_builder import G, Scenario, pk

_FIX55 = (ROOT / "tests" / "fixtures"
          / "abomasnow_the_body_that_attacks_does_not_yield_to_its_twin_step55.json")
# The same episode, turn 10: the sacrifice pivot with NO twin anywhere, which
# is where the premise fix has to answer on its own.
_FIX108 = (ROOT / "tests" / "fixtures"
           / "abomasnow_the_prize_sacrifice_needs_a_doomed_body_step108.json")

APPLIN = m.Applin
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU_BULU = m.Tapu_Bulu

MYRIAD_LEAF_SHOWER = 120     # Ogerpon ex: the attack the record threw away

MEGA_ABOMASNOW = 723         # 350 HP, hits for 200
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


def _obs(fixture=_FIX55):
    return copy.deepcopy(json.load(open(fixture, encoding="utf-8"))["observation"])


def _pokemon(raw):
    """The observation's raw dict as the `Pokemon` the calculators take."""
    fields = ("id", "serial", "hp", "maxHp", "appearThisTurn", "energies",
              "energyCards", "tools", "preEvolution")
    return Pokemon(**{k: raw[k] for k in fields})


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _chosen(obs):
    return obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]


# ---------------------------------------------------------------------------
# 1. The board: without this, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_an_ogerpon_that_attacks_in_front_of_its_own_copy():
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    rival = cur["players"][1 - cur["yourIndex"]]

    active = mine["active"][0]
    assert active["id"] == OGERPON and active["hp"] == 210
    assert len(active["energies"]) == 4        # Myriad Leaf Shower needs 3

    bench = [b for b in mine["bench"] if b]
    twin = [b for b in bench if b["id"] == OGERPON]
    assert len(twin) == 1, "the twin has to be there or there is no rule to test"
    assert twin[0]["hp"] == active["hp"] == 210     # neither exception applies:
    assert len(twin[0]["energies"]) == 2            # and it cannot attack

    # Nothing behind is bigger, so the front spot cannot be upgraded by a body
    # either -- 210 is the ceiling of the whole bench.
    assert max(b["hp"] for b in bench) == active["hp"]

    # And the promotion had FOUR bodies of another species to choose from, which
    # is exactly what cases (a)-(c) of the twin rule cannot see.
    assert len([b for b in bench if b["id"] != OGERPON]) == 4

    # The turn's attachment is spent: nothing is going to charge the twin.
    assert cur["energyAttached"] is True

    # The opponent hits for 200 and the active has 210: it ENDURES, so no prize
    # sacrifice is being bought here -- and every body on the bench that would
    # concede one prize instead of two dies to that same 200.
    assert rival["active"][0]["id"] == MEGA_ABOMASNOW
    _hit = m._op_active_attack_damage_to(
        _pokemon(rival["active"][0]), _pokemon(active), rival["handCount"])
    assert _hit == 200 < active["hp"]
    # ...and the only bodies behind that endure that same 200 are two ex, so
    # there was no cheaper body to hand over either: the prize sacrifice had
    # nothing to buy on this board.
    endure = [b["id"] for b in bench if b["hp"] > _hit]
    assert endure == [m.Fezandipiti_ex, OGERPON]
    assert all(i in m.OUR_EX_IDS for i in endure)

    types = [x["type"] for x in o["select"]["option"]]
    assert int(OptionType.RETREAT) in types
    assert int(OptionType.ATTACK) in types


# ---------------------------------------------------------------------------
# 2. The decision of the record
# ---------------------------------------------------------------------------

def test_the_ogerpon_does_not_retreat_for_the_other_ogerpon():
    chosen = _chosen(_obs())
    assert chosen["type"] != int(OptionType.RETREAT), (
        "cambiar un Ogerpon de 210 que ataca por otro de 210 que no ataca no "
        "compra nada y la tasa quema una Planta")


def test_and_the_turn_keeps_myriad_leaf_shower():
    chosen = _chosen(_obs())
    assert chosen["type"] == int(OptionType.ATTACK), chosen
    assert chosen["attackId"] == MYRIAD_LEAF_SHOWER


# ---------------------------------------------------------------------------
# 3. The sacrifice pivot still fires -- on the board it was written for
# ---------------------------------------------------------------------------

def test_the_prize_sacrifice_comes_back_when_the_ex_really_is_doomed():
    """The same board with the active below their 200: there the ex DOES fall,
    conceding one prize instead of two is what the pivot buys, and it retreats.
    This is the half of `_raging_sac_pivot` the fix must not take away."""
    o = _obs()
    _mine(o)["active"][0]["hp"] = 180
    assert _chosen(o)["type"] == int(OptionType.RETREAT), (
        "con el activo condenado el sacrificio de premio sigue siendo la jugada")


def test_the_sacrifice_without_a_twin_anywhere_still_needs_a_doomed_body():
    """Turn 10 of the same episode, and the board where the twin rule cannot
    speak at all: no copy of the active on the bench, and a 330 HP Hydrapple ex
    behind it, so both of case (d)'s own clauses fail.

        US (3 prizes)                       RIVAL (1 prize -- match point)
        active Fezandipiti ex 210/210 on 4  active Mega Abomasnow ex 350, 200
        bench  Meganium 160, Meowth ex 170,        bench EMPTY
               Ogerpon ex 110/210 on 4,
               Tapu Bulu 140 on 2, Hydrapple ex 330

    The prize sacrifice fired here too, and here it was worse than useless: the
    ex in front ENDURES the 200, every one-prize body behind it dies to it, and
    the opponent needed exactly one more prize. Retreating handed them the body
    that loses the game and gave back the attack. Only the premise fix answers
    this board."""
    chosen = _chosen(_obs(_FIX108))
    assert chosen["type"] == int(OptionType.ATTACK), chosen


def test_and_on_that_same_board_a_doomed_ex_does_retreat():
    """The other half: drop the same active under their 200 and the sacrifice
    is a sacrifice again."""
    o = _obs(_FIX108)
    _mine(o)["active"][0]["hp"] = 190
    assert _chosen(o)["type"] == int(OptionType.RETREAT), (
        "el sacrificio de premio no se ha perdido: solo exige que el cuerpo de "
        "delante caiga de verdad")


# ---------------------------------------------------------------------------
# 4. The gates, one board each, on a deck-agnostic opponent
# ---------------------------------------------------------------------------
#
# The record's shape rebuilt with StateBuilder against a Basic whose line ends
# there, so nothing below can be read as a rule about Mega Abomasnow ex. The
# hand is EMPTY and the turn's attachment already spent: what is measured is
# retreat-versus-the-rest, with no card competing for the turn.

def _board(active, *bench):
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


def test_the_rule_itself_a_twin_among_candidates_the_promotion_may_take():
    """The gap cases (a)-(c) leave open: the bench holds a body of ANOTHER
    species the promotion is free to take -- so none of them fires -- but it is
    WOUNDED down to the active's own life, so the front spot gains nothing by
    the swap either. Nothing behind attacks, the active endures, and its copy is
    sitting there: the attack stays."""
    chosen = _chosen(_board(pk(APPLIN, energies=[G], fisicas=1),
                            pk(TAPU_BULU, hp=40), pk(APPLIN)))
    assert chosen["type"] == int(OptionType.ATTACK), chosen


def test_control_a_healthy_body_behind_still_earns_the_front_spot():
    """SCOPE, and the clause that tells the record apart from a good retreat:
    the SAME board with the Tapu Bulu at full life. 140 in front of 40 is a real
    upgrade even though neither body attacks, so the retreat is a play again."""
    chosen = _chosen(_board(pk(APPLIN, energies=[G], fisicas=1),
                            pk(TAPU_BULU), pk(APPLIN)))
    assert chosen["type"] == int(OptionType.RETREAT), chosen


def test_control_a_body_behind_that_can_attack_still_earns_the_front_spot():
    """The other escape: the wounded Tapu Bulu is charged, so the retreat is
    buying an attack the body in front does not have."""
    chosen = _chosen(_board(pk(APPLIN, energies=[G], fisicas=1),
                            pk(TAPU_BULU, hp=40, energies=[G] * 4, fisicas=4),
                            pk(APPLIN)))
    assert chosen["type"] == int(OptionType.RETREAT), chosen


def test_control_with_no_twin_on_the_bench_nothing_changes():
    """The null control: the same wounded Tapu Bulu, no second Applin, and the
    retreat is untouched -- the case reads the TWIN, not the bench's life."""
    chosen = _chosen(_board(pk(APPLIN, energies=[G], fisicas=1),
                            pk(TAPU_BULU, hp=40)))
    assert chosen["type"] == int(OptionType.RETREAT), chosen
