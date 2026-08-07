"""A WOUNDED wall is not a wall: what is measured is CURRENT life, not printed HP.

Scenario (`records/registro_014_pasos_160_hasta_173.json`, step 166, turn 14,
WON vs Alakazam -- episode 88911400):

    US (3 prizes)                           RIVAL (2 prizes)
    active  Teal Mask Ogerpon ex            active  Alakazam 140/140, 1 energy
            **210/210**, 4 energies                 (Powerful Hand: 20 x hand)
    bench   Hydrapple ex **90/330**, 2 en.  bench   Shaymin 80, Dunsparce 70,
            Meowth ex x2, Fezandipiti ex,           Abra 50, Abra 50
            Meganium

The agent **retreated the 210/210 Ogerpon** -- discarding an energy to pay
the cost -- and promoted the **Hydrapple ex at 90 HP** to attack with it. Both
knock out the Alakazam (Myriad Leaf Shower: 30 + 30*(4+1) = 180; Syrup Storm: 150),
both are 2-prize ex: the swap gains nothing and leaves in front the body that
dies the next turn. The right thing was to **attack with the Ogerpon**.

Cause: THREE places took for granted that "Hydrapple ex is the 330 HP wall" using
the **PRINTED HP**, which is a constant of the card and knows nothing about the damage
already taken:

  1. The `base_score` of the attacker's greedy loop: +200 to Hydrapple ex and -100 to Teal
     Mask Ogerpon ex. Those 300 points beat the +220 of "I am the active"
     and the plan chose the BENCH attacker by 78 points (13342 vs 13264). With
     `plan.attacker >= 1` the active's attack is VETOED.
  2. `_promote_hydra = _hydra_can_ko or (not _act_can_ko)`: if the bench Hydrapple
     knocks out, promote -- even if the active also knocks out.
  3. `_active_ex_fragile_pivot` (score 9000 of the RETREAT): it measures the active's
     fragility with `maxHp < 330`, never with the candidate's life.

Fix: in all three, the comparison is made with CURRENT life and STRICT improvement
is required -- the swap also costs the retreat's energy. The first two also
require that the relief does not DENY prizes (`prize_count`), so that a bench non-ex
can go on relieving an active ex even if it survives less: there the worse
body is paid for with 1 prize instead of 2 (`_alakazam_pivot_1prize`).

What does NOT change: with a HEALTHY Hydrapple the pivot is still alive (330 > 210), which is
the case that created it (log 86412738 p145 vs Hops, log 86505760 p55 vs Alakazam). And
the STALLED-active branch (`not _act_can_ko`) is untouched: there the pivot buys
the KO we did not have.

Golden corpus: a single flip, this step's (RETREAT -> ATTACK id120).
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

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_no_retirar_ogerpon_sano_por_hydrapple_a_90_step166.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
ALAKAZAM = 743  # Alakazam Stage 2 (non-ex): 140 HP, Powerful Hand


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
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _opcion(obs, tipo):
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o.get("type") == tipo)


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_wounded_wall_at_90_hp():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    active = mio["active"][0]
    hydra = next(b for b in mio["bench"] if b and b["id"] == HYDRAPPLE)

    # The one in front is INTACT; the bench "wall" is at 90 of 330.
    assert active["id"] == OGERPON and active["hp"] == active["maxHp"] == 210
    assert hydra["maxHp"] == 330 and hydra["hp"] == 90

    # Both can attack NOW: Ogerpon with 4 energies (req 3), Hydrapple with 2.
    assert len(active["energies"]) == 4
    assert len(hydra["energies"]) == 2

    # Both are ex: the swap DENIES no prize (2 in both cases).
    clase = m.to_observation_class(o)
    assert m.prize_count(clase.current.players[yo].active[0]) == 2
    assert m.prize_count(
        next(b for b in clase.current.players[yo].bench
             if b is not None and b.id == HYDRAPPLE)) == 2

    # Their Alakazam dies to Myriad Leaf Shower: 30 + 30*(4 ours + 1 theirs) = 180.
    opponent = riv["active"][0]
    assert opponent["id"] == ALAKAZAM and opponent["hp"] == 140
    assert 30 + 30 * (4 + len(opponent["energies"])) >= opponent["hp"]


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_intact_ogerpon_does_not_retreat():
    o = _obs()
    retreat = _opcion(o, int(m.OptionType.RETREAT))
    assert m.agent(o) != [retreat], (
        "el activo de 210/210 ya noquea al Alakazam; retirarlo para subir un "
        "Hydrapple ex a 90 PV cuesta una energia, no niega ningun premio y "
        "deja delante el cuerpo que muere")


def test_it_attacks_with_the_active_ogerpon():
    o = _obs()
    attack = _opcion(o, int(m.OptionType.ATTACK))
    assert m.agent(o) == [attack]
    # And the plan points at the ACTIVE (index 0): with `plan.attacker >= 1` the
    # scorer VETOES the active's attack and the turn goes through the retreat.
    assert m.plan.attacker == 0
    assert m.plan.remain_hp is not None and m.plan.remain_hp <= 0


# ---------------------------------------------------------------------------
# 3. The discriminator: CURRENT life, not printed HP
# ---------------------------------------------------------------------------

def test_with_a_healthy_hydrapple_the_pivot_stays_alive():
    """The real wall (330 > 210) still relieves the fragile ex."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    hydra = next(b for b in o["current"]["players"][yo]["bench"]
                 if b and b["id"] == HYDRAPPLE)
    hydra["hp"] = 330  # healed: now it DOES survive more than the 210 Ogerpon

    retreat = _opcion(o, int(m.OptionType.RETREAT))
    assert m.agent(o) == [retreat], (
        "con el Hydrapple ex a 330 el pivote es el de siempre: mismo KO pero "
        "deja delante al cuerpo que aguanta mas")


def test_tied_on_life_the_retreat_is_not_paid_for():
    """STRICT improvement: at equal life, the swap only costs an energy."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    hydra = next(b for b in o["current"]["players"][yo]["bench"]
                 if b and b["id"] == HYDRAPPLE)
    hydra["hp"] = o["current"]["players"][yo]["active"][0]["hp"]  # 210 = 210

    retreat = _opcion(o, int(m.OptionType.RETREAT))
    assert m.agent(o) != [retreat]
