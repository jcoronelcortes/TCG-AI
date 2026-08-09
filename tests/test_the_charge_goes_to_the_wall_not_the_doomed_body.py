"""The energy does not go to the body that dies before it can spend it twice.

Scenario (user, `records/registro_008_pasos_105_hasta_126.json` step 123, turn
8, episode 90875026 vs Mega Lucario ex + Cornerstone, LOST):

    US (6 prizes)                        RIVAL (3 prizes)
    active Fezandipiti ex 210/210,       active Mega Lucario ex 340+100/440
           one Grass, WEAK to {F}               (Hero's Cape), one {F}
    bench  Teal Mask Ogerpon ex, 2 Grass  bench  Riolu 80/80 on two {F}
           Hydrapple ex 330/330, BARE            + three more bodies
           Meowth ex, Ogerpon ex (1), Meganium

Mega Brave prints 270 for two energies; they have one and attach the second
next turn. Through the Fighting weakness of the Fezandipiti that is **540 on a
210 HP body** -- two prizes, and their count goes 3 -> 1. On the same board the
Hydrapple ex eats the very same attack whole: 270 against 330 HP, no weakness,
**it survives**.

The agent routed the turn's Ripening Charge INTO the doomed Fezandipiti and
spent it on a Cruel Arrow that sniped the Riolu: one prize for us (6 -> 5), two
for them on the reply (3 -> 1), and the 330 wall still sitting on the bench
bare. The line the board offered was the other one: charge the HYDRAPPLE,
retreat the Feza (cost 1) and promote the wall.

WHY THE RULE THAT EXISTS DID NOT SEE IT. That line is already written --
`_feza_lucario_wall` in main.py, added from log 86342087 step 130 for this exact
pair of cards, comment and all ("Mega Brave 270 x2 = 540, 2 prizes"). It never
fired once, because it was gated on `active_ko_likely`, and that flag is built
on `_op_best_damage_vs`, the helper that reads `card.attacks` entries as objects
when the simulator stores ints -- so it returns **0 for every opposing attack**
(the blindness is documented in `_op_active_attack_damage_to`'s own docstring).
The rule asked "is the active doomed?" of the one number that could not see the
card the rule is named after: 0 damage on a body it prices itself at 540.

Its own twin twenty lines above -- the deck-agnostic Ogerpon -> Hydrapple pivot
-- had already been migrated to the projector that resolves the attack table.
This is the same question asked of the same helper, plus two consequences:

  * the guard that was supposed to prove the wall SURVIVES read
    `(hp or 0) > _op_best_damage_vs(...)`, i.e. `330 > 0`, i.e. nothing. It now
    asks the real projection too;
  * the retreat only denies the two prizes if the body we hide SURVIVES on the
    bench, so the pivot passes through `_bench_cashable_after_retreat` like its
    twin.

`active_ko_likely` stays as an OR: no board that fired before stops firing.

Golden corpus: 1 flip in 133 historical decisions, this one. Suite green.
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
from cg.api import AreaType, OptionType
from ptcg.calc.damage import _op_active_attack_damage_to
from state_builder import G, Scenario, pk

_FIX123 = (ROOT / "tests" / "fixtures"
           / "lucario_the_charge_goes_to_the_wall_that_survives_step123.json")

FEZANDIPITI = m.Fezandipiti_ex          # 210 HP, weak {F}, retreat 1
HYDRAPPLE = m.Hydrapple_ex              # 330 HP, weak {R}: the wall
OGERPON = m.Teal_Mask_Ogerpon_ex
MEGA_LUCARIO = m.Mega_Lucario_ex        # Mega Brave 270 for two energies
RIOLU = m.Riolu                         # 80 HP: what Cruel Arrow snipes

CRUEL_ARROW = 183                       # Fezandipiti ex: 100 to any Pokemon
MEGA_BRAVE = 983


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
# 1. The board: without these numbers the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_a_doomed_ex_in_front_of_a_wall_that_survives():
    o = _obs(_FIX123)
    yo = o["current"]["yourIndex"]
    mine, rival = o["current"]["players"][yo], o["current"]["players"][1 - yo]

    active = mine["active"][0]
    assert active["id"] == FEZANDIPITI and active["hp"] == 210
    wall = [b for b in mine["bench"] if b and b["id"] == HYDRAPPLE][0]
    assert wall["hp"] == wall["maxHp"] == 330
    assert wall["energies"] == []                  # bare: this is the charge

    op_active = rival["active"][0]
    assert op_active["id"] == MEGA_LUCARIO
    assert m.attack_table[MEGA_BRAVE].damage == 270

    # The prize count is the whole reason the trade is bad: they need three.
    assert len(mine["prize"]) == 6 and len(rival["prize"]) == 3


def test_the_projection_condemns_the_active_and_clears_the_wall():
    """540 through the weakness on a 210 HP body; 270 on a 330 HP one. And the
    flag the rule used to read sees NEITHER of the two numbers."""
    o = _obs(_FIX123)
    m.agent(copy.deepcopy(o))              # loads the tables the projector uses

    class _P:
        def __init__(self, d):
            self.__dict__.update(d)

    yo = o["current"]["yourIndex"]
    mine, rival = o["current"]["players"][yo], o["current"]["players"][1 - yo]
    op_active = _P(rival["active"][0])
    op_active.tools = [_P(t) for t in rival["active"][0]["tools"]]
    feza = _P(mine["active"][0])
    wall = _P([b for b in mine["bench"] if b and b["id"] == HYDRAPPLE][0])

    hand = rival["handCount"]
    assert _op_active_attack_damage_to(op_active, feza, hand) == 540 > feza.hp
    assert _op_active_attack_damage_to(op_active, wall, hand) == 270 < wall.hp


# ---------------------------------------------------------------------------
# 2. The decision of the record
# ---------------------------------------------------------------------------

def test_the_charge_goes_to_the_wall_and_not_to_the_doomed_active():
    o = _obs(_FIX123)
    chosen = _chosen(o)
    assert chosen["area"] == int(AreaType.BENCH), (
        "la Planta no va al cuerpo que muere antes de gastarla: va al muro")
    wall_idx = [k for k, b in enumerate(o["current"]["players"]
                                        [o["current"]["yourIndex"]]["bench"])
                if b and b["id"] == HYDRAPPLE][0]
    assert chosen["index"] == wall_idx


# ---------------------------------------------------------------------------
# 3. The turn that charge opens, and its gates, on synthetic boards
# ---------------------------------------------------------------------------
#
# The board of step 124 as it would have been if the charge had gone where it
# belongs. It cannot come from the record -- the record charged the Feza -- so
# it is rebuilt: the same shape, no Meganium doubling the Grass, and the snipe
# that competes with the retreat is on the table (a Riolu of 80 HP that Cruel
# Arrow's 100 knocks out, the exact play the agent preferred).

def _lucario_board(active, *bench, op_active=None, menu="hand"):
    s = (Scenario(turn=8, step=124, tac=19, own_prizes=6,
                  supporter_played=True, energy_played=True)
         .my_active(active)
         .my_bench(*bench)
         .op_active(op_active if op_active is not None
                    else pk(MEGA_LUCARIO, energies=[G]))
         .op_bench(pk(RIOLU, energies=[G, G]))
         .op_zones(hand=5, deck=20, prizes=3)
         .my_hand()
         .deck()
         .rest_to_discard())
    if menu == "hand":
        return s.menu_hand(with_retreat=True, with_attack=True).build()
    return s.promote_after_retreat().build()


def test_with_the_wall_charged_the_turn_retreats_instead_of_sniping():
    """The other half of the same line. The Cruel Arrow is on the menu and it
    takes a prize; it is still not what the turn is for, because the body that
    fires it hands back two."""
    chosen = _chosen(_lucario_board(
        pk(FEZANDIPITI, energies=[G] * 3, fisicas=3),
        pk(HYDRAPPLE, energies=[G, G], fisicas=2)))
    assert chosen["type"] == int(OptionType.RETREAT), chosen


def test_and_the_promotion_brings_up_the_wall():
    chosen = _chosen(_lucario_board(
        pk(FEZANDIPITI, energies=[G] * 2, fisicas=2),
        pk(OGERPON, energies=[G, G], fisicas=2),
        pk(HYDRAPPLE, energies=[G, G], fisicas=2),
        menu="promote"))
    assert chosen["index"] == 1, "sube el muro de 330, no el Ogerpon de 210"


def test_control_with_no_wall_behind_it_the_turn_keeps_its_prize():
    """SCOPE. The doomed Feza, the same Mega Lucario, and an Ogerpon ex behind
    it instead of the Hydrapple: 270 goes through a 210 HP body too, so there is
    nothing to retreat INTO and the snipe is the whole turn. The pivot is not
    "the active is doomed", it is "the active is doomed AND a body survives"."""
    chosen = _chosen(_lucario_board(
        pk(FEZANDIPITI, energies=[G] * 3, fisicas=3),
        pk(OGERPON, energies=[G, G], fisicas=2)))
    assert chosen["type"] == int(OptionType.ATTACK), chosen
    assert chosen["attackId"] == CRUEL_ARROW


def test_control_a_wall_that_is_not_charged_yet_does_not_take_the_front():
    """The wall has to be able to ACT once it is up: a bare Hydrapple takes the
    hit and answers nothing. That is what the charge of step 123 is FOR, and
    until it lands the pivot stays off (the mute-survivor rule)."""
    chosen = _chosen(_lucario_board(
        pk(FEZANDIPITI, energies=[G] * 3, fisicas=3),
        pk(HYDRAPPLE)))
    assert chosen["type"] == int(OptionType.ATTACK), chosen


def test_control_a_wounded_wall_is_not_a_wall():
    """The healthy-body gate that was already there: a Hydrapple that has taken
    120 is at 210 and Mega Brave's 270 goes through it. Retreating into it
    concedes the same two prizes a turn later, so the turn keeps its prize."""
    chosen = _chosen(_lucario_board(
        pk(FEZANDIPITI, energies=[G] * 3, fisicas=3),
        pk(HYDRAPPLE, hp=210, energies=[G, G], fisicas=2)))
    assert chosen["type"] == int(OptionType.ATTACK), chosen
