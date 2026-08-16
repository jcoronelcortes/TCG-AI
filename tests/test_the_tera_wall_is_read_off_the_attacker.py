"""Milotic ex: the wall that reads the ATTACKER'S TERA, and neither its ex nor its Ability.

Scenario (`records/registro_009_pasos_071_hasta_074.json` step 74 and
`records/registro_017_pasos_093_hasta_096.json` step 96, episode 93490495 vs a
Milotic ex / Sylveon list -- game WON, and the two turns below were given away
inside a game that was won anyway).

Milotic ex prints *Sparkling Scales*: "Prevent all damage from and effects of
attacks from your opponent's **Tera** Pokemon done to this Pokemon". Our only
Tera is Teal Mask Ogerpon ex -- the body four copies of this deck are built to
charge -- so a Milotic ex in the active spot switches off our main attacker and
NOTHING else: Hydrapple ex is an ex and damages it, Dipplin has an Ability and
damages it.

STEP 74, THE PROMOTION. Our Tapu Bulu took their Milotic ex to 50/270 and died
to its own Wood Hammer recoil, so the promotion is forced:

    US (5 prizes)                            RIVAL (6 prizes)
    bench  Teal Mask Ogerpon ex 210, 4 eff.  active  Milotic ex **50**/270, 0 en.
           **Dipplin 80, 2 effective**       bench   Eevee 70, Eevee 70
           Teal Mask Ogerpon ex 210, 4 eff.
           Meganium 160, 0 en.
           Meowth ex 170, 0 en.

The agent brought up a **Teal Mask Ogerpon ex**: `_our_effective_damage` priced
Myriad Leaf Shower at 30 + 30 x 4 = **150** against a body that takes **zero**
from it. The Dipplin next to it does *Do the Wave* for 20 x 4 benched = **80**
on a Milotic at **50**: the prize was on the board and the promotion could not
see it.

STEP 96, THE RETREAT. Three turns later the same wall, at 80/270 and still with
**no energy**, faces our Teal Mask Ogerpon ex at 4 effective while the bench
holds Tapu Bulu at 4 (Wood Hammer 220), Meganium at 4 (Solar Beam 140) and
Dipplin at 2 (Do the Wave 100) -- three separate knockouts. The menu offers
exactly three things: attack for 0, retreat, or pass. The agent attacked.

Fix: `TERA_IMMUNE_IDS` in `ptcg/cards/ids.py` and the zero in the canonical
model (`_our_effective_damage`), which is what the promotion consults; plus the
three inline copies that do not go through it -- the ATTACK menu, the gust's
price (`ptcg/turn/supporters.py`) and the wall region of main.py
(`_op_wall_active` / `_dmg_vs_wall` / `_active_blocked_by_wall`), which is what
turns "our Tera is stuck in front of it" into the retreat that promotes a body
that hits.

It enters as its own term everywhere instead of widening
`op_has_ex_immune_active`: swapping our ex out is the answer to Crustle, and
here it is the answer to nothing -- what has to leave the front is our TERA.

Self-play vs `deck/opponents/milotic_sylveon.csv` (the harvested list),
n=1000/arm: **94.4% vs 83.1%, +11.3 points**; prizes per game +3.61 vs +2.73.

Exposure: **0 of the 408 opposing lists** in the corpus play Milotic ex, and the
user still met it on the ladder. `utils/op_immunity_census.py` carries a fourth
claim for this shape so the next card that prints it is found by the census and
not by a lost game.
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
from main_support import make_pokemon
from patching import patch_name

_FIX_PROMOTE = (ROOT / "tests" / "fixtures"
                / "milotic_promote_the_non_tera_step74.json")
_FIX_RETREAT = (ROOT / "tests" / "fixtures"
                / "milotic_retreat_the_tera_step96.json")

MILOTIC = m.Milotic_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
DIPPLIN = m.Dipplin
TAPU = m.Tapu_Bulu
MEGANIUM = m.Meganium
HYDRAPPLE = m.Hydrapple_ex

_RETREAT = 12
_ATTACK = 13


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
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    yield
    m._init_cards_tracking()


def _obs(fixture):
    return copy.deepcopy(
        json.load(open(fixture, encoding="utf-8"))["observation"])


def _mine(o):
    return o["current"]["players"][o["current"]["yourIndex"]]


def _theirs(o):
    return o["current"]["players"][1 - o["current"]["yourIndex"]]


def _promoted(o, action):
    return _mine(o)["bench"][o["select"]["option"][action[0]]["index"]]


def _chosen_type(o, action):
    return o["select"]["option"][action[0]]["type"]


def _fake(card_id):
    """The minimal Pokemon `_our_effective_damage` reads."""
    return make_pokemon(card_id, hp=270, max_hp=270)


# ---------------------------------------------------------------------------
# 1. The card: what the ability actually reads
# ---------------------------------------------------------------------------

def test_sparkling_scales_reads_the_tera_and_nothing_else():
    """The three walls are three different questions about the ATTACKER."""
    milotic = _fake(MILOTIC)
    assert MILOTIC in m.TERA_IMMUNE_IDS

    # Our only Tera is switched off...
    assert m.OUR_TERA_IDS == {OGERPON}
    assert m._our_effective_damage(_fake(OGERPON), milotic, 150) == 0

    # ...and NOT our other ex (Hydrapple ex), nor a body with an Ability
    # (Dipplin has Festival Lead), nor the non-ex.
    assert HYDRAPPLE in m.OUR_EX_IDS
    assert m._our_effective_damage(_fake(HYDRAPPLE), milotic, 150) > 0
    assert DIPPLIN in m.OUR_ABILITY_IDS
    assert m._our_effective_damage(_fake(DIPPLIN), milotic, 80) > 0
    assert m._our_effective_damage(_fake(TAPU), milotic, 220) > 0


def test_it_is_not_the_ex_wall_nor_the_ability_wall():
    """If it were filed under either of the two existing tables it would be wrong."""
    assert MILOTIC not in m.EX_IMMUNE_IDS
    assert MILOTIC not in m.ABILITY_IMMUNE_IDS


# ---------------------------------------------------------------------------
# 2. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_promotion_fixture_is_the_prize_the_wall_hands_over():
    o = _obs(_FIX_PROMOTE)
    mine, theirs = _mine(o), _theirs(o)

    # A forced promotion: we are left with no active.
    assert not mine["active"]
    assert o["select"]["context"] == int(m.SelectContext.TO_ACTIVE)

    # The wall is one hit from falling, and it cannot hit back: 0 energy.
    wall = theirs["active"][0]
    assert wall["id"] == MILOTIC and wall["hp"] == 50
    assert wall["energyCards"] == []

    # Dipplin: Do the Wave is 20 x our bench AFTER the promotion (4 bodies).
    dipplin = next(b for b in mine["bench"] if b["id"] == DIPPLIN)
    assert len(dipplin["energies"]) >= m.ATTACK_ENERGY_REQ[DIPPLIN]
    assert 20 * (len(mine["bench"]) - 1) >= wall["hp"]

    # ...and the two Teal Mask Ogerpon ex are loaded, which is exactly why the
    # over-read chose one of them.
    ogerpons = [b for b in mine["bench"] if b["id"] == OGERPON]
    assert len(ogerpons) == 2
    assert all(len(b["energies"]) >= m.ATTACK_ENERGY_REQ[OGERPON]
               for b in ogerpons)


def test_the_retreat_fixture_is_swing_for_zero_retreat_or_pass():
    o = _obs(_FIX_RETREAT)
    mine, theirs = _mine(o), _theirs(o)

    active = mine["active"][0]
    assert active["id"] == OGERPON
    assert len(active["energies"]) >= m.ATTACK_ENERGY_REQ[OGERPON]

    wall = theirs["active"][0]
    assert wall["id"] == MILOTIC and wall["hp"] == 80
    assert wall["energyCards"] == []

    # The whole menu: attack for 0, retreat, end turn.
    assert sorted(x["type"] for x in o["select"]["option"]) == [12, 13, 14]

    # Three separate knockouts wait on the bench.
    ready = {b["id"] for b in mine["bench"]
             if len(b["energies"]) >= m.ATTACK_ENERGY_REQ.get(b["id"], 99)}
    assert {TAPU, MEGANIUM, DIPPLIN} <= ready


# ---------------------------------------------------------------------------
# 3. The decision
# ---------------------------------------------------------------------------

def test_it_promotes_the_dipplin_that_finishes_not_the_mute_tera():
    o = _obs(_FIX_PROMOTE)
    action = m.agent(_obs(_FIX_PROMOTE))
    assert _promoted(o, action)["id"] == DIPPLIN, (
        "contra un activo que anula nuestro Tera sube el cuerpo que SI le pega "
        "y ademas lo remata, no el Ogerpon cargado que hace 0")


def test_the_tera_stuck_in_front_retreats_instead_of_swinging_for_zero():
    o = _obs(_FIX_RETREAT)
    action = m.agent(_obs(_FIX_RETREAT))
    assert _chosen_type(o, action) == _RETREAT, (
        "con tres rematadores en banca, atacar con el Tera anulado regala el "
        "turno entero"
    )


# ---------------------------------------------------------------------------
# 4. The limits of the rule
# ---------------------------------------------------------------------------

def test_without_the_milotic_in_front_the_tera_attacks_again():
    """Control: the same board with their active swapped for its pre-evolution.

    Feebas prints no ability, so Myriad Leaf Shower lands and there is no
    reason to give up the front seat."""
    o = _obs(_FIX_RETREAT)
    wall = _theirs(o)["active"][0]
    wall["id"] = m.card_table[MILOTIC].evolvesFrom and 206  # Feebas
    action = m.agent(o)
    assert _chosen_type(o, action) == _ATTACK


def test_it_is_the_table_that_decides_and_not_the_board(monkeypatch):
    """The mutant this kills: a rule that fires on this board for another reason.

    Emptying `TERA_IMMUNE_IDS` in every module that holds a reference to it --
    the fix's four call sites live in four different files -- has to bring BOTH
    pre-fix decisions back, one for one.
    """
    assert patch_name(monkeypatch, "TERA_IMMUNE_IDS", frozenset()) >= 4

    o = _obs(_FIX_PROMOTE)
    assert _promoted(o, m.agent(_obs(_FIX_PROMOTE)))["id"] == OGERPON

    o = _obs(_FIX_RETREAT)
    assert _chosen_type(o, m.agent(_obs(_FIX_RETREAT))) == _ATTACK


def test_without_the_milotic_in_front_the_promotion_goes_back_to_the_ogerpon():
    """Control: the same forced promotion against a body that our Tera DOES hit.

    It pins the rule to the wall and not to the board: with Feebas in front the
    loaded Ogerpon ex is the promotion the agent already made."""
    o = _obs(_FIX_PROMOTE)
    wall = _theirs(o)["active"][0]
    wall["id"] = 206  # Feebas
    action = m.agent(o)
    assert _promoted(o, action)["id"] == OGERPON
