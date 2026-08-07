"""Promotion after a KO: the one that CAN damage the rival active, even if it charges tomorrow.

Scenario (`records/registro_013_pasos_069_hasta_071.json`, step 71, turn 13,
LOST vs Crustle -- episode 88915875). Superb Scissors knocks out our
Dipplin and we have to promote:

    US (6 prizes)                               RIVAL (3 prizes)
    bench  Teal Mask Ogerpon ex 210, 2 eff.     active  Crustle **70**/150, 3 en.
           **Meganium 160, 2 effective**        bench   Mega Kangaskhan ex 300
           Chikorita 70, 0 en.
           Teal Mask Ogerpon ex 210, 2 eff.
           Fezandipiti ex 210, 0 en.
    hand   Dipplin, Xerosic's, Tapu Bulu, **1 Grass**

The agent brought up **Teal Mask Ogerpon ex**, which against this active is a mute
body: *Mysterious Rock Inn* cancels all the damage from the rival's Pokemon ex, so
Ogerpon ex and Fezandipiti ex hit the Crustle for **0**.

The only one that finishes it is **Meganium** (non-ex): it carries 1 Grass = **2 effective**
(its own Wild Growth) and there is another Grass left in hand -> next turn it
attaches (2+2 = **4**) and *Solar Beam* does **140** on a Crustle at **70 HP**.

Cause -- two measures of "ready to attack" that look at the wrong turn. The
forced promotion happens on the RIVAL's turn: the body that comes up **does not attack today**,
it attacks TOMORROW. `_best_promote_card` already got it right (it takes into account next turn's
attachment, ex immunity, ability immunity and weakness) and chose
Meganium... but two rules of the option loop knocked it down:

1. The veto "the Meganium line does not go to the active spot" (`SCORE_NEVER` = -10000, it protects
   the Wild Growth engine from the bench) was only lifted with `len(energies) >=
   4`, that is, TODAY's energy. Meganium at 2/4 ate it whole: -10000 + 150 +
   4000 from the best-promotable bonus = **-5850**.
2. The ex-immune-active branch gave its +6000 to the "non-ex attacker" measured with
   `_can_attack_now`; without it, the Ogerpon ex took the +3000 of *a wall with
   energy* and won the spot with **3343**.

Fix: in a FORCED promotion (`_forced_ko_promote`) both measures move to the
next turn -- the Meganium line's veto yields when the KO-aware
selector points at that body (`card is _best_promote_card`), and the non-ex attacker
against the immune wall is recognised with `_can_attack_with_attach`. Deck-agnostic:
it holds for any active that makes our ex immune (Crustle / Sylveon).

Golden corpus: a single flip, this step's.
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
            / "crustle_promover_meganium_step71.json")

MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex
FEZ = m.Fezandipiti_ex
CHIKORITA = m.Chikorita
CRUSTLE = m.Crustle_Grass


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


def _bench(obs):
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["bench"]


def _opt_de(obs, pred):
    bench = _bench(obs)
    return next(i for i, o in enumerate(obs["select"]["option"])
                if pred(bench[o["index"]]))


def _promovido(obs, accion):
    return _bench(obs)[obs["select"]["option"][accion[0]]["index"]]


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_forced_promotion_with_the_crustle_one_blow_away():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    # A forced promotion: we are left with no active.
    assert not mio["active"]
    assert o["select"]["context"] == 4

    # The rival active is the ex-immune wall, and it is ONE blow away.
    act = riv["active"][0]
    assert act["id"] == CRUSTLE and act["hp"] == 70

    # Meganium: 2 effective (1 Grass x Wild Growth) of the 4 Solar Beam asks for.
    meg = next(b for b in mio["bench"] if b["id"] == MEGANIUM)
    assert len(meg["energyCards"]) == 1 and len(meg["energies"]) == 2
    assert m.ATTACK_ENERGY_REQ[MEGANIUM] == 4

    # ...and the Grass it is missing is in hand: tomorrow it reaches 4 and does 140.
    assert sum(1 for c in mio["hand"] if c["id"] == m.Basic_Grass_Energy) >= 1

    # The ex on the bench are MUTE bodies against this active.
    assert any(b["id"] == OGERPON for b in mio["bench"])
    assert any(b["id"] == FEZ for b in mio["bench"])


def test_the_crustle_ability_cancels_the_damage_of_our_ex():
    """Why bringing up an ex gives away the turn: Mysterious Rock Inn."""
    o = _obs()
    m.agent(_obs())  # it leaves the global state in sync with the board
    assert OGERPON in m.OUR_EX_IDS and FEZ in m.OUR_EX_IDS
    assert CRUSTLE in m.EX_IMMUNE_IDS


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_it_promotes_meganium_not_the_mute_ex():
    o = _obs()
    accion = m.agent(_obs())
    pk = _promovido(o, accion)
    assert pk["id"] == MEGANIUM, (
        "contra un activo que inmuniza a nuestros ex hay que subir al no-ex que "
        "SI puede rematar el proximo turno, no un ex que hace 0")


def test_it_brings_up_neither_ogerpon_nor_fezandipiti_nor_chikorita():
    o = _obs()
    accion = m.agent(_obs())
    assert accion != [_opt_de(o, lambda b: b["id"] == OGERPON)]
    assert accion != [_opt_de(o, lambda b: b["id"] == FEZ)]
    # Chikorita can attack tomorrow (Seed Bomb, 2 effective) but for 30: it does not finish.
    assert accion != [_opt_de(o, lambda b: b["id"] == CHIKORITA)]


# ---------------------------------------------------------------------------
# 3. The limits of the rule
# ---------------------------------------------------------------------------

def test_with_no_grass_in_hand_meganium_does_not_get_there_and_is_not_forced():
    """Control: with the Grass removed from hand, Meganium stays at 2/4 -- it does not
    attack even tomorrow --, so the Meganium line's veto rules again and
    the promotion does not pick it."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    mio["hand"] = [c for c in mio["hand"] if c["id"] != m.Basic_Grass_Energy]
    mio["handCount"] = len(mio["hand"])
    accion = m.agent(o)
    assert _promovido(o, accion)["id"] != MEGANIUM


def test_without_the_immune_wall_in_front_the_promotion_keeps_its_criterion():
    """Control: with the Mega Kangaskhan ex active (it does not make our ex immune)
    the non-ex attacker bonus does not even apply; the promotion goes back to the
    general logic and is not dragged along by this fix."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    riv = o["current"]["players"][1 - yo]
    riv["active"], riv["bench"] = riv["bench"], riv["active"]
    accion = m.agent(o)
    assert _promovido(o, accion)["id"] != CHIKORITA
