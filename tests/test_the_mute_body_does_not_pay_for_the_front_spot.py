"""A doomed active that cannot attack hands the front spot over -- and the
Grass that buys it nothing does not go on it.

Scenario (`records/registro_004_pasos_050_hasta_063.json` step 62, turn 4,
episode 90871654 vs Mega Lucario ex, LOST):

    US (6 prizes)                          RIVAL (6 prizes)
    active  Teal Mask Ogerpon ex           active  Mega Lucario ex 340/340
            **20/210**, 1 Grass                    (it has just hit for 190)
    bench   Hydrapple ex 330/330 (0 en.)
            Hydrapple ex 330/330 (0 en.)
    hand    1 Basic Grass, Forest, Lillie's, Meowth ex, Tapu Bulu, Meganium

Myriad Leaf Shower costs three and the Ogerpon has one, so the body in front
is MUTE; its retreat costs ONE and it already pays it. Two things were wrong
and the second is the one that lost the two prizes:

1. The manual attachment on the active scored **31210** -- the band of "the
   charge that pays the retreat" -- although the retreat was already paid. The
   Grass could neither make it attack nor buy anything: it went to the discard
   with the retreat and it was the same card the fresh benched Ogerpon's Teal
   Dance needed.

2. `_teal_wall_pivot`, the pivot that puts the 330 HP wall in front, required a
   Grass IN HAND (its story was "Teal Dance pays the retreat and THEN we
   retreat"). Spending that Grass switched the pivot off, the retreat scored
   -1 and the turn ENDED with a 2-prize body at 20 HP in front.

The general rule, of which the pivot above is a case: a doomed active that
cannot attack today, whose retreat is ALREADY payable, hands the front spot to
a bench body that costs the opponent more -- fewer prizes, or the same prizes
and it SURVIVES their hit. `_doomed_mute_pivot`, deck-agnostic: nothing in it
is card or matchup data.

Golden corpus: 4 flips, all of them wanted (this turn's two, and the two of
`registro_006` turn 6 -- the same board with the Ogerpon still healthy).
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Scenario, pk

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "lucario_mute_ogerpon_hands_over_the_front_step62.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
MEGA_LUCARIO = 678
RIOLU = 677


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


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _index_of(obs, **match):
    for i, o in enumerate(obs["select"]["option"]):
        if all(o.get(k) == v for k, v in match.items()):
            return i
    raise AssertionError(f"no option matches {match}")


# ---------------------------------------------------------------------------
# 1. The board: without this, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_mute_ogerpon_in_front_of_the_lucario():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mine, opponent = o["current"]["players"][yo], o["current"]["players"][1 - yo]

    active = mine["active"][0]
    assert active["id"] == OGERPON and active["hp"] == 20

    # MUTE: Myriad costs 3 effective and there is one Grass on it. Even the
    # single Grass left in hand does not get it there.
    assert m.ATTACK_ENERGY_REQ_BASE[OGERPON] == 3
    assert len(active["energies"]) == 1
    assert sum(1 for c in mine["hand"] if c["id"] == m.Basic_Grass_Energy) == 1

    # The retreat is ALREADY paid: cost 1, one energy on it.
    assert m.RETREAT_COST[OGERPON] == 1

    # The relief costs the same 2 prizes and SURVIVES what killed the active.
    bench = [b for b in mine["bench"] if b]
    wall = next(b for b in bench if b["id"] == HYDRAPPLE)
    assert wall["hp"] == wall["maxHp"] == 330
    assert opponent["active"][0]["id"] == MEGA_LUCARIO

    # And the menu really does offer both plays we are choosing between.
    assert any(x.get("type") == int(m.OptionType.RETREAT)
               for x in o["select"]["option"])


# ---------------------------------------------------------------------------
# 2. The two decisions of the turn
# ---------------------------------------------------------------------------

def test_the_grass_does_not_go_on_the_body_that_dies_with_it():
    """The attachment on the active bought nothing: the retreat was paid."""
    o = _obs()
    on_the_active = _index_of(o, type=int(m.OptionType.ATTACH),
                              inPlayArea=int(m.AreaType.ACTIVE))
    chosen = m.agent(o)
    assert chosen != [on_the_active], (
        "el Ogerpon a 20 PV no ataca ni con la Planta encima y su retirada ya "
        "estaba pagada: la energia solo viaja al descarte con el cuerpo")
    # It goes to a body that can still use it: a benched Hydrapple ex.
    assert o["select"]["option"][chosen[0]]["type"] == int(m.OptionType.ATTACH)
    assert (o["select"]["option"][chosen[0]]["inPlayArea"]
            == int(m.AreaType.BENCH))


def test_once_the_grass_is_spent_the_wall_still_comes_up():
    """The turn as it was actually played: with the hand out of Grass the
    retreat must still happen. This is the step the record ENDED on."""
    o = _obs()
    mine = o["current"]["players"][o["current"]["yourIndex"]]
    grass = next(i for i, c in enumerate(mine["hand"])
                 if c["id"] == m.Basic_Grass_Energy)
    mine["hand"].pop(grass)
    mine["handCount"] = len(mine["hand"])
    o["current"]["energyAttached"] = True
    o["select"]["option"] = [
        x for x in o["select"]["option"]
        if x.get("type") in (int(m.OptionType.RETREAT), int(m.OptionType.END))]

    retreat = _index_of(o, type=int(m.OptionType.RETREAT))
    assert m.agent(o) == [retreat], (
        "sin Planta en mano la retirada seguia siendo gratis y el cuerpo de 2 "
        "premios a 20 PV no tiene por que quedarse delante")


# ---------------------------------------------------------------------------
# 3. Deck-agnostic: the same sentence read off other bodies
# ---------------------------------------------------------------------------

#
# The four gates, one control each. All of them were checked against the
# PREVIOUS version of the tree: on the first board it answers END and on the
# four controls it already answers what is asserted here, so the controls
# really do isolate this rule and are not watching somebody else's play
# ([[corpus-dorado-registros-que-no-vigilaban-nada]]).
#
# There is NO Grass in hand on any of them: that is what keeps the narrow
# `_teal_wall_pivot` -- which requires one -- out of the measurement.

LUCARIO_IN_FRONT = dict(hp=340, max_hp=340, energies=[G, G, G])


def _closing_turn(active, bench, op_active):
    """A closing turn whose menu only offers RETREAT and END."""
    esc = (Scenario(turn=8, step=80, tac=9, first_player=1,
                    supporter_played=True, energy_played=True)
           .my_active(active)
           .my_bench(*bench)
           .my_hand(m.Ultra_Ball)
           .op_active(op_active)
           .op_bench(pk(RIOLU, hp=80, max_hp=80)))
    esc.deck(*sorted(esc._pool.elements())[:34]).rest_to_discard()
    obs = esc.menu_hand(with_retreat=True).build()
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if o["type"] in (int(m.OptionType.RETREAT), int(m.OptionType.END))]
    return obs


def _lucario():
    return pk(MEGA_LUCARIO, pre_evo=[RIOLU], **LUCARIO_IN_FRONT)


def _chosen(obs):
    return obs["select"]["option"][m.agent(obs)[0]]["type"]


def test_the_wall_comes_up_with_no_grass_anywhere_in_hand():
    """The rule, on a board the narrow pivot cannot see: the hand holds no
    Grass, so the only thing that pays the retreat is the energy already on
    the body."""
    obs = _closing_turn(pk(OGERPON, hp=70, energies=[G], fisicas=1),
                        [pk(HYDRAPPLE, hp=330, max_hp=330)],
                        _lucario())
    assert _chosen(obs) == int(m.OptionType.RETREAT)


def test_a_body_that_is_not_doomed_stays_in_front():
    """Control, DOOMED gate: the same board with the active out of their reach.
    Retreating would pay an energy to buy nothing."""
    obs = _closing_turn(pk(OGERPON, hp=210, energies=[G], fisicas=1),
                        [pk(HYDRAPPLE, hp=330, max_hp=330)],
                        pk(RIOLU, hp=80, max_hp=80, energies=[G]))
    assert _chosen(obs) == int(m.OptionType.END)


def test_a_body_that_can_still_attack_stays_in_front():
    """Control, MUTE gate: the same doomed body with Myriad Leaf Shower paid
    for. A body that attacks does not hand the spot over."""
    obs = _closing_turn(pk(OGERPON, hp=70, energies=[G, G, G], fisicas=3),
                        [pk(HYDRAPPLE, hp=330, max_hp=330)],
                        _lucario())
    assert _chosen(obs) == int(m.OptionType.END)


def test_a_retreat_that_is_not_paid_for_is_not_a_play():
    """Control, PAID gate: the same board with the active at zero energy. This
    rule does not buy the retreat, it only cashes one that is already paid --
    the charge that BUYS it has its own bands (41000 / 31250)."""
    obs = _closing_turn(pk(OGERPON, hp=70),
                        [pk(HYDRAPPLE, hp=330, max_hp=330)],
                        _lucario())
    assert _chosen(obs) == int(m.OptionType.END)


def test_without_a_body_worth_relieving_it_stays_in_front():
    """Control, RELIEF gate: the bench only holds a body of the SAME price
    that does NOT survive either. Swapping corpses is not a play."""
    obs = _closing_turn(pk(OGERPON, hp=70, energies=[G], fisicas=1),
                        [pk(OGERPON, hp=70, max_hp=210)],
                        _lucario())
    assert _chosen(obs) == int(m.OptionType.END)
