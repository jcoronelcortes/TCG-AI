"""Promotion after a KO: the HAND engine counts as an energy route.

Scenario (`registros/registro_007_pasos_101_hasta_127.json`, step 126, turn 7,
LOST vs Marnie's Grimmsnarl ex):

    US (3 prizes)                            RIVAL (5 prizes)
    active  -- (they have just knocked out   active  Marnie's Grimmsnarl ex
            our Hydrapple ex)                        310/320, 3 energies,
    bench   Ogerpon ex 2/3 energies                  **{G} weakness**
            Ogerpon ex 2/3 energies
            Ogerpon ex 0/3
            Tapu Bulu 1/4, 80 HP
    hand    Meowth ex + Meganium
    discard  1 Grass Energy

The promotion resolves at the END of the rival's turn: the next turn is OURS
and the body we bring up attacks FIRST. An Ogerpon ex at 2/3 is **one single**
energy away from *Myriad Leaf Shower* — 30+30·(3 ours + 3 of the rival) = 210, ×2 for
the Grass weakness = **420 ≥ 310**: it finishes off the Grimmsnarl ex and takes 2 prizes
(3 → 1). And that energy is reachable: playing **Meowth ex** fires *Last-Ditch
Catch*, which brings from the deck **Lana's Aid** (which picks up the Grass from the discard)
or Lillie's/Dawn.

The agent brought up the **Tapu Bulu** at 1/4: it cannot attack (*Wood Hammer* costs 4),
it cannot retreat (cost 3 with no energy to pay it) and it gives away the turn.

Two chained causes:

1. `_promote_setup_ko_attacker` (promote the near-ready attacker) required a
   draw Supporter **already in hand** (`Lillie's`/`Dawn`). A hand that only
   has the ENGINE that gets that Supporter — Meowth ex — was left out. All
   the real routes are now enumerated: a draw Supporter in hand, Lana's Aid
   in hand with a Grass in the discard, and the Meowth ex engine (a bench slot +
   a live ability + a useful Supporter still hidden in the deck/prizes).

2. Even when it fired, the TERMINAL promotion adjustment subtracted
   `PROMO_PRIZE_PENALTY` for being a 2-prize ex (9500 → 8000) and left it
   below the basic wall of `_ko_prefer_basic_general` (8500 + life/10 =
   8508). The premise of that penalty — "nobody survives, give away the fewest
   prizes" — does **not** apply to a body that finishes first: the rival does not get
   to hit it. It is exempted, just as the one that knocks out on the spot already is.

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
            / "marnie_promote_ogerpon_setup_ko_step126.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
MEOWTH = m.Meowth_ex
GRIMMSNARL = 648                # Marnie's Grimmsnarl ex, 320 HP, {G} weakness


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
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs(**mut):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    if mut.get("sin_meowth"):
        mio["hand"] = [c for c in mio["hand"] if c["id"] != MEOWTH]
        mio["handCount"] = len(mio["hand"])
    if mut.get("sin_supporter_alcanzable"):
        # The Meowth ex fetch cannot bring anything useful: the last Lillie's and
        # the Dawn are already in the discard and there is no Grass left to pick up with
        # Lana's Aid.
        mio["discard"] = [c for c in mio["discard"]
                          if c["id"] != m.Basic_Grass_Energy]
        for cid in (m.Lillie_Determination, m.Dawn):
            mio["discard"].append({"id": cid, "playerIndex": yo, "serial": 999})
    return o


def _elegido(obs, choice):
    """The bench card matching the chosen option."""
    yo = obs["current"]["yourIndex"]
    opt = obs["select"]["option"][choice[0]]
    return obs["current"]["players"][yo]["bench"][opt["index"]]


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_promotion_after_the_ko():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    rival = o["current"]["players"][1 - yo]

    assert not mio["active"]                       # they knocked out our active
    assert o["select"]["context"] == 4             # promotion menu
    assert rival["active"][0]["id"] == GRIMMSNARL
    assert rival["active"][0]["hp"] == 310

    # A Grass weakness: the Ogerpon ex hits double.
    assert m.card_table[GRIMMSNARL].weakness == m.card_table[OGERPON].energyType

    # The Ogerpon ex is ONE energy from Myriad; Tapu Bulu is three from Wood Hammer.
    oger = [b for b in mio["bench"] if b["id"] == OGERPON and len(b["energies"]) == 2]
    tapu = next(b for b in mio["bench"] if b["id"] == TAPU)
    assert oger, "el fixture debe tener un Ogerpon ex a 2/3"
    assert m.ATTACK_ENERGY_REQ[OGERPON] - 2 == 1
    assert m.ATTACK_ENERGY_REQ[TAPU] - len(tapu["energies"]) == 3
    # ...and on top of that the Tapu would be nailed down: retreat 3 with no energy to pay it.
    assert m.RETREAT_COST[TAPU] > len(tapu["energies"])

    # The hand engine: Meowth ex + a Grass in the discard.
    assert any(c["id"] == MEOWTH for c in mio["hand"])
    assert sum(1 for c in mio["discard"]
               if c["id"] == m.Basic_Grass_Energy) >= 1
    # No draw Supporter in hand: the old rule did not fire.
    assert not any(c["id"] in (m.Lillie_Determination, m.Dawn)
                   for c in mio["hand"])


def test_el_ogerpon_completado_remata_al_grimmsnarl():
    """The prize of the play: 30+30*(3+3) = 210, x2 for weakness = 420 >= 310."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    opponent_act_id = o["current"]["players"][1 - yo]["active"][0]
    base = 30 + 30 * (m.ATTACK_ENERGY_REQ[OGERPON] + len(opponent_act_id["energies"]))
    assert base * 2 >= opponent_act_id["hp"]


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_it_promotes_the_nearly_ready_ogerpon_not_the_nailed_down_tapu():
    obs = _obs()
    elegido = _elegido(obs, m.agent(obs))
    assert elegido["id"] == OGERPON
    assert len(elegido["energies"]) == 2       # the one that is ONE energy away


# ---------------------------------------------------------------------------
# 3. The limits: with no energy engine, the cheap wall is still right
# ---------------------------------------------------------------------------

def test_with_no_meowth_there_is_no_energy_route_and_the_1_prize_wall_returns():
    obs = _obs(sin_meowth=True)
    assert _elegido(obs, m.agent(obs))["id"] == TAPU


def test_with_no_useful_supporter_to_fetch_the_meowth_is_not_an_engine():
    obs = _obs(sin_supporter_alcanzable=True)
    assert _elegido(obs, m.agent(obs))["id"] == TAPU
