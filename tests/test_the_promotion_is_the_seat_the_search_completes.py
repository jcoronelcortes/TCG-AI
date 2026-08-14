"""The promotion chooses a SEAT for tomorrow's body, and a search is a route to it.

Scenario (`records/registro_004_pasos_047_hasta_059.json` step 59, turn 4,
episode 92943959 vs Mega Lucario ex, LOST):

    US (6 prizes)                          RIVAL (5 prizes)
    active  -- just knocked out --         active  Mega Lucario ex 440/440,
    bench   **Dipplin 80, 0e**                     1 energy + tool
            Teal Mask Ogerpon ex 210, 3e           (its blow projects 270)
            Teal Mask Ogerpon ex 210, 0e   bench   Riolu x2, Solrock, Lucario x2
            Applin 40, 0e
    hand    **Dawn**, 2 Basic Grass, Bayleef

The agent promoted the charged Teal Mask Ogerpon ex. Their blow reads 270: the
Ogerpon does not survive it, it does not reach the 440 in front of it either
(Myriad Leaf Shower at 3 + 1 energy is 150), and it hands over TWO prizes plus
the three energies invested in it.

The line that was there: promote the **Dipplin**. Our turn resolves before their
next attack -- Dawn buys a Basic, a Stage 1 and a Stage 2 out of the deck, the
Hydrapple ex goes on top of the promoted Dipplin, and what the opponent finds in
front of them is a 330 HP body their 270 falls short of. The Dipplin is one
prize, and the charged Ogerpon stays on the bench with its energy intact.

Cause -- the promotion chain reads the hand as ENERGY (`_prom_can_attach`) and
as a CARD (`_ev_*` / `_evk_*` look for a direct evolution already in hand). It
never reads it as a ROUTE. Here nothing on the bench survives the projected hit,
so the evolution-survivor override (`_ev_*`) does open -- and then finds no
evolution in hand, because the Hydrapple ex is in the DECK and what the hand
holds is the tutor that reaches it.

Fix -- `main.py`, `_ev_*`: the evolutions a benched body can wear next turn are
the ones in HAND *plus* the ones a Pokemon-search Supporter in hand can still
pull out of the DECK (`POKEMON_SEARCH_SUPPORTER_IDS` + the tracker's
`ZONE_DECK`). The promotion resolves at the end of THEIR turn, so next turn's
Supporter slot is free by construction. Deck-agnostic: the stages come from
`card_table`/`_direct_evolution_ids` and the tutors from the group, so the
sentence holds for any line and any list that carries one.

A card in hand is a certainty and a search is a belief, so on equal survival the
hand route keeps the seat -- the search only ever ADDS candidates.
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
from ptcg.state.zones import ZONE_DECK

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "lucario_the_promotion_is_the_seat_the_search_completes_step59.json")

APPLIN = m.Applin
DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
GRASS = m.Basic_Grass_Energy
DAWN = m.Dawn
MEGA_LUCARIO = 678


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

def test_the_fixture_is_a_forced_promotion_with_the_evolution_in_the_deck():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mine, rival = o["current"]["players"][yo], o["current"]["players"][1 - yo]

    # Our active is empty: the promotion is FORCED, and it resolves on the
    # opponent's turn -- our turn (search, evolve, attach) comes next.
    assert mine["active"] == []
    assert o["select"]["context"] == int(SelectContext.TO_ACTIVE)
    assert all(x["type"] == int(OptionType.CARD) and x["area"] == int(AreaType.BENCH)
               for x in o["select"]["option"])

    bench = [b["id"] for b in mine["bench"] if b]
    assert bench == [DIPPLIN, OGERPON, OGERPON, APPLIN]

    # The Dipplin has been on the bench: it can be evolved next turn.
    dipplin = next(b for b in mine["bench"] if b and b["id"] == DIPPLIN)
    assert dipplin["appearThisTurn"] is False
    assert dipplin["hp"] == 80 and dipplin["energies"] == []

    # The hand holds the TUTOR, not the evolution.
    hand = [c["id"] for c in mine["hand"]]
    assert hand.count(DAWN) == 1 and HYDRAPPLE not in hand
    assert DAWN in m.POKEMON_SEARCH_SUPPORTER_IDS
    assert m.card_table[HYDRAPPLE].evolvesFrom == m.card_table[DIPPLIN].name

    # In front of us a Mega at full HP.
    act = rival["active"][0]
    assert act["id"] == MEGA_LUCARIO and act["hp"] == act["maxHp"] == 440


def test_the_tracker_believes_the_evolution_is_still_in_the_deck():
    o = _obs()
    m.agent(copy.deepcopy(o))
    assert m.AGENT_STATE.ACTIVE_CARDS_IN_DECK[HYDRAPPLE][ZONE_DECK] >= 1


# ---------------------------------------------------------------------------
# 2. The numbers that make the Ogerpon the wrong answer
# ---------------------------------------------------------------------------

def test_nothing_on_the_bench_survives_their_blow_but_the_evolution_does():
    from cg.api import to_observation_class

    o = _obs()
    m.agent(copy.deepcopy(o))
    st = to_observation_class(_obs()).current
    mine, rival = st.players[st.yourIndex], st.players[1 - st.yourIndex]
    opa = rival.active[0]

    for body in mine.bench:
        hit = m._op_active_attack_damage_to(opa, body, rival.handCount)
        assert hit >= (body.hp or 0), (body.id, hit, body.hp)

    # The body the search completes is the one their blow falls short of.
    hit = m._op_active_attack_damage_to(opa, m._ProjTarget(HYDRAPPLE), rival.handCount)
    assert hit < m.card_table[HYDRAPPLE].hp


def test_the_ogerpon_cannot_reach_the_mega_either():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mine, rival = o["current"]["players"][yo], o["current"]["players"][1 - yo]
    oger = next(b for b in mine["bench"] if b and b["id"] == OGERPON and b["energies"])
    # Myriad Leaf Shower counts the energy on BOTH actives.
    myriad = 30 + 30 * (len(oger["energies"]) + len(rival["active"][0]["energies"]))
    assert myriad < rival["active"][0]["hp"]


# ---------------------------------------------------------------------------
# 3. The decision
# ---------------------------------------------------------------------------

def test_the_seat_the_search_completes_comes_up_not_the_charged_ex():
    assert _promoted_id(_obs()) == DIPPLIN


# ---------------------------------------------------------------------------
# 4. Controls: the rule must not fire where its premise does not hold
# ---------------------------------------------------------------------------

def test_control_with_no_tutor_in_hand_the_normal_logic_decides():
    """Without Dawn the Dipplin is just an 80 HP body: nothing buys the evolution."""
    o = _obs()
    mine = _mine(o)
    mine["hand"] = [c for c in mine["hand"] if c["id"] != DAWN]
    mine["handCount"] = len(mine["hand"])
    assert _promoted_id(o) == OGERPON


def test_control_with_the_evolution_out_of_the_deck_it_does_not_fire():
    """The DISCARD is not a zone a search reaches: both copies gone, no route."""
    o = _obs()
    mine = _mine(o)
    mine["discard"] = mine["discard"] + [
        {"id": HYDRAPPLE, "playerIndex": 0, "serial": 900 + i} for i in range(2)]
    assert _promoted_id(o) == OGERPON


def test_control_a_body_that_already_knocks_out_keeps_the_spot():
    """A knockout on the board is a bird in the hand and does not spend the search.

    Dropping the Mega Lucario to 150 puts it inside Myriad Leaf Shower's reach,
    so the charged Ogerpon ex knocks out AS IT IS and the branch stays shut.
    """
    o = _obs()
    rival = o["current"]["players"][1 - o["current"]["yourIndex"]]
    rival["active"][0]["hp"] = 150
    assert _promoted_id(o) == OGERPON


def test_control_a_route_whose_evolution_dies_too_is_not_a_route():
    """Applin -> Dipplin is 80 HP against a 270 blow: the search buys nothing.

    With the Dipplin taken off the bench the only line the tutor could complete
    in ONE step ends in a body that dies exactly like the pre-evolution, so the
    override has nothing to say and the ordinary chain decides again.
    """
    o = _obs()
    mine = _mine(o)
    mine["bench"] = [b for b in mine["bench"] if b["id"] != DIPPLIN]
    assert _promoted_id(o) == OGERPON
