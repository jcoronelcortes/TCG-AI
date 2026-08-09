"""When promoting, the body that knocks out may be one evolution away in hand.

Scenario (`records/registro_009_pasos_105_hasta_120.json` step 120, turn 9,
episode 90978858 vs Mega Lopunny ex, WON in spite of this):

    US (2 prizes)                          RIVAL (3 prizes)
    active  -- just knocked out --         active  Mega Lopunny ex 330/330,
    bench   Teal Mask Ogerpon ex 210, 6e           1 Enriching Energy, Air Balloon
            Meowth ex 170, 0e                      (Spiky Hopper 160 at two energies)
            Meganium 160, 0e               bench   Mega Froslass ex x2, 2 basics
            Teal Mask Ogerpon ex 210, 6e
            **Dipplin 80, 0e**
    hand    **Hydrapple ex**, 2 Basic Grass, Night Stretcher, Boss's Orders

The agent brought up an Ogerpon ex. Myriad Leaf Shower with 6 of its own energy
and 1 on the opposing active is 240 against a 330 HP body: no knockout, and the
turn goes by. The Dipplin evolves into Hydrapple ex and Syrup Storm -- 30 plus
30 for each Grass on our field, twelve of them -- does 390. Mega Lopunny ex is a
Mega: three prizes, and we needed two. The knockout closes the game.

Cause -- the promotion reads every benched body as THE CARD IT IS NOW. The
candidate loop prices the Dipplin with its own attack (20 per benched body) and
its own 80 HP, and loses to any ex on the `_pb_hp` half of the key; the hand
only ever entered that loop as ENERGY (`_prom_can_attach`). The two overrides
that do read the hand cover the user's priority (2), "the body that best
ENDURES": `_rt_*` wants the tank already on the bench, and the
evolution-survivor override (`_ev_*`) is gated behind "nobody survives the hit
as it is" -- and here the Ogerpon ex does survive the projected 160, so it never
opened. Nothing covered priority (1), "a body that KNOCKS OUT", through an
evolution in hand.

Fix, in two halves because the decision has two halves:

1. `main.py`, `_evk_*`: after the survivor overrides (a knockout outranks
   enduring), if NOBODY on the bench knocks out as it is, look on the bench for
   a pre-evolution whose evolution is in hand, price the evolution's attack with
   the single source (`_attacker_base_damage` + `_our_effective_damage`) and the
   energy we can still attach, and promote it if it knocks out.

2. `ptcg/turn/options/card.py`: exempt that pre-evolution from
   PROMO_DOOMED_PENALTY via `_promo_evo_koer`. The penalty measures a hit the
   body never takes AS IT IS -- our turn evolves it first -- and without the
   exemption its 4453 fell to -1547, below the Ogerpon's 857.

Golden corpus: 1 flip, this one.
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
from cg.api import AreaType, OptionType, SelectContext

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "lopunny_the_evolution_in_hand_that_knocks_out_step120.json")

DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
MEGANIUM = m.Meganium
MEOWTH = m.Meowth_ex
GRASS = m.Basic_Grass_Energy
MEGA_LOPUNNY = 849


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


def _mine(o):
    return o["current"]["players"][o["current"]["yourIndex"]]


def _promoted_id(o):
    """The id of the benched body the agent chooses to bring up."""
    chosen = o["select"]["option"][m.agent(copy.deepcopy(o))[0]]
    return _mine(o)["bench"][chosen["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The board: without this, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_a_forced_promotion_with_the_evolution_in_hand():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mine, rival = o["current"]["players"][yo], o["current"]["players"][1 - yo]

    # Our active is empty: the promotion is FORCED, and it resolves on the
    # opponent's turn -- our turn (evolve, attach, attack) comes next.
    assert mine["active"] == []
    assert o["select"]["context"] == int(SelectContext.TO_ACTIVE)
    assert all(x["type"] == int(OptionType.CARD) and x["area"] == int(AreaType.BENCH)
               for x in o["select"]["option"])

    bench = [b["id"] for b in mine["bench"] if b]
    assert bench.count(OGERPON) == 2 and DIPPLIN in bench
    assert {MEOWTH, MEGANIUM} <= set(bench)

    # The Dipplin has been on the bench: it can be evolved next turn.
    dipplin = next(b for b in mine["bench"] if b and b["id"] == DIPPLIN)
    assert dipplin["appearThisTurn"] is False
    assert dipplin["hp"] == 80 and dipplin["energies"] == []

    # The hand holds the evolution and the two Grass that pay for its attack.
    hand = [c["id"] for c in mine["hand"]]
    assert hand.count(HYDRAPPLE) == 1 and hand.count(GRASS) == 2
    assert m.card_table[HYDRAPPLE].evolvesFrom == m.card_table[DIPPLIN].name
    assert m.ATTACK_ENERGY_REQ_BASE[HYDRAPPLE] == 2

    # In front of us a Mega at full HP: three prizes, and we only need two.
    act = rival["active"][0]
    assert act["id"] == MEGA_LOPUNNY and act["hp"] == act["maxHp"] == 330
    assert m.card_table[MEGA_LOPUNNY].megaEx is True
    assert len(mine["prize"]) == 2


# ---------------------------------------------------------------------------
# 2. The numbers that make the Ogerpon the wrong answer
# ---------------------------------------------------------------------------

def test_the_ogerpon_does_not_knock_out_and_the_hydrapple_does():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mine, rival = o["current"]["players"][yo], o["current"]["players"][1 - yo]
    op_hp = rival["active"][0]["hp"]

    # Myriad Leaf Shower counts the energy on BOTH actives: 6 + 1.
    oger = next(b for b in mine["bench"] if b and b["id"] == OGERPON)
    assert 30 + 30 * (len(oger["energies"]) + len(rival["active"][0]["energies"])) < op_hp

    # Syrup Storm counts every Grass on our field: two Ogerpon at six each.
    total_grass = sum(len(b["energies"]) for b in mine["bench"] if b)
    assert 30 + 30 * total_grass >= op_hp


# ---------------------------------------------------------------------------
# 3. The decision
# ---------------------------------------------------------------------------

def test_the_pre_evolution_of_the_finisher_comes_up_not_the_ogerpon():
    assert _promoted_id(_obs()) == DIPPLIN


# ---------------------------------------------------------------------------
# 4. Controls: the rule must not fire where its premise does not hold
# ---------------------------------------------------------------------------

def test_control_with_no_evolution_in_hand_the_normal_logic_decides():
    """Without the Hydrapple ex the Dipplin is just an 80 HP body."""
    o = _obs()
    mine = _mine(o)
    mine["hand"] = [c for c in mine["hand"] if c["id"] != HYDRAPPLE]
    mine["handCount"] = len(mine["hand"])
    assert _promoted_id(o) == OGERPON


def test_control_with_no_energy_to_pay_for_the_attack_it_does_not_fire():
    """The evolution that cannot attack knocks nobody out: it is not promoted.

    The Dipplin carries no energy and Syrup Storm costs two. Both routes to a
    Grass have to go: the ones in hand and the Night Stretcher that recovers one
    from the discard. (One Grass alone is enough while our Meganium is on the
    bench -- Wild Growth makes each one count double -- which is why removing
    only the two in hand is not a control.)
    """
    o = _obs()
    mine = _mine(o)
    mine["hand"] = [c for c in mine["hand"]
                    if c["id"] not in (GRASS, m.Night_Stretcher)]
    mine["handCount"] = len(mine["hand"])
    assert _promoted_id(o) == OGERPON


def test_control_a_body_that_already_knocks_out_keeps_the_spot():
    """A knockout in hand does not spend the evolution: the bird in the hand wins.

    Halving the Mega Lopunny's HP puts it inside Myriad Leaf Shower's 240, so
    the Ogerpon ex knocks out AS IT IS (`_best_promote_key[0] == 1`) and the
    branch must stay shut.
    """
    o = _obs()
    rival = o["current"]["players"][1 - o["current"]["yourIndex"]]
    rival["active"][0]["hp"] = 200
    assert _promoted_id(o) == OGERPON
