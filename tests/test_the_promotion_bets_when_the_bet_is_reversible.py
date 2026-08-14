"""Promotion after a KO: the turn's own draw is a route when the bet is reversible.

Scenario (`records/registro_006_pasos_067_hasta_094.json`, step 94, turn 6,
episode 93022181, LOST vs Marnie's Grimmsnarl ex):

    US (5 prizes)                            RIVAL (3 prizes)
    active  -- (their Grimmsnarl ex has      active  Marnie's Grimmsnarl ex
            just knocked out our Ogerpon)            **310**/320, 2 energies,
    bench   Meganium 130, 0/4                        **{G} weakness**
            Teal Mask Ogerpon ex 180, **2/3**
            Teal Mask Ogerpon ex 180, **2/3**
            Tapu Bulu 140, **0/4**, retreat 3
    hand    Teal Mask Ogerpon ex, Hydrapple ex   (no Grass, no Supporter)

With Meganium's Wild Growth on the bench one attachment is worth TWO, so an
Ogerpon ex at 2/3 completes to four: Myriad Leaf Shower is 30+30x(4+2) = 210 and
the Grass weakness doubles it to **420 over 310** -- two prizes, on our turn,
before they can answer.

The agent promoted the **Tapu Bulu** (8514 against -1314): four energy needed,
none carried, three to retreat. Turn 7 opened by drawing a Bug Catching Set that
fetched **two Grass**; they went to the bench, the turn ended with no attack and
the game was lost.

`_promote_setup_ko_attacker` was the rule that should have spoken and its five
routes to the missing Grass were all dead: no draw Supporter in hand (a), no
Lana's Aid (b), no Meowth ex (c), no Fezandipiti ex (d), and our pile at five is
not match point (e). What every one of them asks for is a GUARANTEE, and this
board is the one that shows the guarantee was never the thing being paid for:

  * the promotion resolves at the END of their turn, so the promoted body is not
    exposed to anything before we act;
  * if the draw brings the Grass we take the prize;
  * if it does not, the Ogerpon **retreats** -- cost 1, and it carries two
    effective energies -- and the wall comes up THEN, before their reply.

So the failed bet costs one energy card and a turn the mute wall was going to
waste anyway. That is route **(f)**: `_ps_grass_reachable` (a copy still unseen),
not a wall matchup, a bench that survives the promotion, and -- the guard that
pays for the whole thing -- the candidate KEEPS ITS EXIT
(`_ps_keeps_its_way_out`, which asks `_retreat_payable`, the bill in CARDS).

Corpus: one flip locally (this step) and two on the frozen bundle, both the same
sentence -- a body one attachment from a knockout coming up instead of a mute
wall.
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
            / "marnie_promote_reversible_bet_step94.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
MEGANIUM = m.Meganium
GRIMMSNARL = 648                 # Marnie's Grimmsnarl ex, 320 HP, {G} weakness


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


def _grass_total():
    return sum(m.AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
        m.Basic_Grass_Energy, {}).values())


def _obs(sin_planta_oculta=False):
    """The board of step 94.

    `sin_planta_oculta` exhausts the deck: every Grass of the list is already
    VISIBLE (hand + discard + attached), so `_ps_grass_reachable` is False and
    there is nothing left for the draw to find. That is the control for route
    (f) -- with no copy to draw, the bet is not a bet.
    """
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    if sin_planta_oculta:
        visible = sum(1 for c in mio["discard"] if c["id"] == m.Basic_Grass_Energy)
        visible += sum(1 for c in mio["hand"] if c["id"] == m.Basic_Grass_Energy)
        for pk in list(mio["active"]) + list(mio["bench"]):
            visible += sum(1 for e in (pk.get("energyCards") or [])
                           if e["id"] == m.Basic_Grass_Energy)
        for i in range(max(0, _grass_total() - visible)):
            mio["discard"].append({"id": m.Basic_Grass_Energy,
                                   "playerIndex": yo, "serial": 900 + i})
    return o


def _elegido(obs, choice):
    """The benched card behind the chosen option."""
    yo = obs["current"]["yourIndex"]
    opt = obs["select"]["option"][choice[0]]
    return obs["current"]["players"][yo]["bench"][opt["index"]]


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_forced_promotion_after_the_ko():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    assert not mio["active"]                    # they knocked our active out
    assert o["select"]["context"] == 4          # promotion menu
    assert riv["active"][0]["id"] == GRIMMSNARL and riv["active"][0]["hp"] == 310
    assert len(mio["prize"]) == 5 and len(riv["prize"]) == 3

    # Not one of the five routes to the missing Grass is alive: the hand holds
    # two Pokemon and nothing else, and there is no Fezandipiti ex on the board.
    assert [c["id"] for c in mio["hand"]] == [OGERPON, m.Hydrapple_ex]
    for _route in (m.Lillie_Determination, m.Dawn, m.Lanas_Aid, m.Meowth_ex,
                   m.Basic_Grass_Energy):
        assert not any(c["id"] == _route for c in mio["hand"])
    assert not any(b["id"] == m.Fezandipiti_ex for b in mio["bench"])
    # ...and our pile at five is not match point either (route (e)).
    assert len(mio["prize"]) > 2

    # But the deck still holds Grass to draw: that is what route (f) bets on.
    visible = sum(1 for c in mio["discard"] if c["id"] == m.Basic_Grass_Energy)
    for pk in mio["bench"]:
        visible += sum(1 for e in (pk.get("energyCards") or [])
                       if e["id"] == m.Basic_Grass_Energy)
    assert _grass_total() - visible >= 1


def test_the_completed_ogerpon_finishes_the_grimmsnarl():
    """30+30x(4+2) = 210, doubled by the Grass weakness = 420 >= 310."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    riv_act = o["current"]["players"][1 - yo]["active"][0]
    assert m.card_table[GRIMMSNARL].weakness == m.card_table[OGERPON].energyType
    # Wild Growth: the Meganium on the bench makes each attachment worth two,
    # so 2/3 completes to FOUR.
    assert any(b["id"] == MEGANIUM for b in o["current"]["players"][yo]["bench"])
    assert (30 + 30 * (4 + len(riv_act["energies"]))) * 2 >= riv_act["hp"]


def test_the_bet_is_reversible_and_the_wall_is_not():
    """The Ogerpon can walk back; the Tapu Bulu cannot even do that."""
    o = _obs()
    mio = o["current"]["players"][o["current"]["yourIndex"]]
    oger = next(b for b in mio["bench"]
                if b["id"] == OGERPON and len(b["energies"]) == 2)
    tapu = next(b for b in mio["bench"] if b["id"] == TAPU)

    assert m.ATTACK_ENERGY_REQ[OGERPON] - len(oger["energies"]) == 1
    assert m.RETREAT_COST[OGERPON] <= len(oger["energies"])   # it keeps its exit
    assert m.ATTACK_ENERGY_REQ[TAPU] - len(tapu["energies"]) == 4
    assert m.RETREAT_COST[TAPU] > len(tapu["energies"])       # nailed down


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_it_promotes_the_almost_ready_ogerpon_not_the_mute_wall():
    obs = _obs()
    chosen = _elegido(obs, m.agent(obs))
    assert chosen["id"] == OGERPON
    assert len(chosen["energies"]) == 2       # the one that is ONE attachment away


# ---------------------------------------------------------------------------
# 3. The limits: what the bet is paying for
# ---------------------------------------------------------------------------

def test_with_no_grass_left_to_draw_the_cheap_wall_returns():
    """Control: exhaust the Grass and there is nothing to bet on."""
    obs = _obs(sin_planta_oculta=True)
    assert _elegido(obs, m.agent(obs))["id"] == TAPU


def test_a_candidate_that_cannot_retreat_is_not_bet_on(monkeypatch):
    """Control: the exit is what makes the failed draw free.

    With the same board and a retreat the Ogerpon cannot pay, promoting it is
    an irreversible bet -- if the Grass does not appear it is stuck in front
    handing over two prizes -- and the one-prize wall takes the slot back.
    """
    monkeypatch.setitem(m.RETREAT_COST, OGERPON, 6)
    obs = _obs()
    assert _elegido(obs, m.agent(obs))["id"] == TAPU
