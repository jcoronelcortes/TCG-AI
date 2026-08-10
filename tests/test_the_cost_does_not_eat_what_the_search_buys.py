"""The Ultra Ball's cost paid with the Meganium it was digging the Bayleef for.

Scenario (`records/registro_004_pasos_029_hasta_042.json`, step 33, turn 4 vs
Crustle, episode 91601506 -- WON in spite of this):

    US (6 prizes)                          OPPONENT (6 prizes)
    active  Teal Mask Ogerpon ex, 1 {G}    active  Crustle, 1 {G}
    bench   Teal Mask Ogerpon ex 1 {G},    bench   Dwebble 1 {G}
            Tapu Bulu 1 {G},               stadium OUR Forest of Vitality
            Chikorita, Chikorita,
            Meowth ex                      (bench 5/5, Supporter still free)
    hand    Fezandipiti ex, **Lillie's Determination**, **Meganium**,
            Boss's Orders
    played  **Ultra Ball** -- and its fetch will bring the **Bayleef**

Playing the Ultra Ball was right. Paying for it was not: the cost took the
**Meganium** (40) and the Fezandipiti ex (38) and kept the Boss's Orders (36).

Every branch was right about the board it was shown. The Meganium ladder asks
for a **Bayleef in play** and, failing that, drops to "there is another copy in
the deck" (40) -- the price of an ORPHAN, and its comment says so out loud:
"having only a Chikorita does NOT count, two evolutions are missing". But the
second evolution was the card being BOUGHT. `_RULES_UB_BAYLEEF` had scored that
very fetch 950 instead of 850 *because we were holding a Meganium in hand*
(`chikorita_evolvable` + Forest in play), and then the cost threw away the
reason for its own price. The two halves of one Ultra Ball contradicted each
other -- the same disagreement the Supporter block already forbids ("the card we
keep and the card we would play cannot disagree").

It matters most in exactly this matchup: Crustle is immune to our ex, Tapu Bulu
is the one body that breaks through, and Meganium's Wild Growth is what pays for
its attack. Behind it the hand also held the only refill left (Lillie's) and a
Boss's Orders that `_supp_values` had already priced at zero on that board.

Fix: `_evo_top_unlocked_by_the_search` (ptcg/cards/lines.py) puts the incoming
link on the board FIRST and only then asks the question -- an orphaned top of a
line whose missing link is `necesario` (its own pre-evolution already in play)
and still IN THE DECK is one evolution away, not cardboard. The
`SelectContext.DISCARD` scorer then keeps it at `DISCARD_LINK_THE_SEARCH_BUYS`
(3), the same score the "Bayleef already in play" branch uses, because it is the
same sentence. It names no card: the stages come from `EVO_LINES`.

WHAT IS DELIBERATELY *NOT* DONE: the rule is NOT mirrored into
`_ub_real_fodder`. That count exists to say what the discarder would let go, so
mirroring looks mandatory -- but the protection is a RANKING among the cards the
cost takes, not a claim that the piece is untouchable (the menu takes `minCount`
cards whatever the scores say). Fed to the veto family it becomes a veto, and
the veto cancels the very Ultra Ball that un-orphans the piece: measured on the
frozen corpus, three Ultra Balls died that way (registro_017 turn 8, registro_018
turn 6, registro_029 turn 6) with the rest of the hand perfectly able to pay. It
is the circularity `_line_base_benchable` already documents ("THE DECK IS NOT A
SEAT"), and the last test here is its guard.
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
            / "crustle_t4_the_cost_does_not_eat_what_the_search_buys_step33.json")
_FIXTURE_PLAY = (ROOT / "tests" / "fixtures"
                 / "crustle_t4_the_ultra_ball_is_the_play_step32.json")

APPLIN = m.Applin
BAYLEEF = m.Bayleef
BOSS = m.Boss_Orders
CHIKORITA = m.Chikorita
DIPPLIN = m.Dipplin
FEZ = m.Fezandipiti_ex
HYDRAPPLE = m.Hydrapple_ex
LILLIE = m.Lillie_Determination
MEGANIUM = m.Meganium
ULTRA_BALL = m.Ultra_Ball

SEAT = 1                       # our seat in the record


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
    m._field_at_turn_start = {}
    yield
    m._init_cards_tracking()


def _record_obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _discarded(obs):
    hand = obs["current"]["players"][SEAT]["hand"]
    sel = obs["select"]
    return [hand[sel["option"][i]["index"]]["id"] for i in m.agent(obs)]


# ---------------------------------------------------------------------------
# 1. The predicate on its own: which board makes an orphan a live piece
# ---------------------------------------------------------------------------

def test_the_orphan_top_whose_link_the_deck_still_holds():
    """The record's board: a Chikorita in play, no Bayleef anywhere, and a
    Bayleef still in the deck -- the Ultra Ball's fetch is the missing link."""
    assert m._evo_top_unlocked_by_the_search(
        MEGANIUM, {MEGANIUM: 1}, {CHIKORITA: 2}, {BAYLEEF: 2}) is True


def test_it_holds_for_the_other_line_without_naming_it():
    """Deck-agnostic: the stages come from `EVO_LINES`."""
    assert m._evo_top_unlocked_by_the_search(
        HYDRAPPLE, {HYDRAPPLE: 1}, {APPLIN: 1}, {DIPPLIN: 2}) is True


def test_the_deck_is_the_only_zone_a_search_reaches():
    """With no copy of the link left in the deck there is nothing to buy: the
    piece goes back to being the orphan every branch already prices."""
    assert m._evo_top_unlocked_by_the_search(
        MEGANIUM, {MEGANIUM: 1}, {CHIKORITA: 2}, {BAYLEEF: 0}) is False


def test_a_link_already_ours_is_not_something_the_search_supplies():
    """Bayleef in hand, or on the bench: the ordinary branches answer this and
    the rule stays out of it."""
    assert m._evo_top_unlocked_by_the_search(
        MEGANIUM, {MEGANIUM: 1, BAYLEEF: 1}, {CHIKORITA: 2}, {BAYLEEF: 1}) is False
    assert m._evo_top_unlocked_by_the_search(
        MEGANIUM, {MEGANIUM: 1}, {CHIKORITA: 1, BAYLEEF: 1}, {BAYLEEF: 1}) is False


def test_a_line_with_no_body_at_all_is_not_one_evolution_away():
    """No Chikorita in play: the Bayleef would arrive with nothing to sit on, so
    it is not `necesario` and the Meganium is a real orphan."""
    assert m._evo_top_unlocked_by_the_search(
        MEGANIUM, {MEGANIUM: 1}, {}, {BAYLEEF: 2}) is False


def test_only_the_top_of_the_line_asks_this_question():
    """A Bayleef in hand is missing a Chikorita, which is a BASIC and enters
    play through the other door (a bench seat, `_ub_target_has_no_seat`)."""
    assert m._evo_top_unlocked_by_the_search(
        BAYLEEF, {BAYLEEF: 1}, {}, {CHIKORITA: 2}) is False


# ---------------------------------------------------------------------------
# 2. The record's step: who pays for the Ultra Ball
# ---------------------------------------------------------------------------

def test_step33_pays_with_the_fezandipiti_and_the_boss_not_with_the_meganium():
    obs = _record_obs()
    hand = [c["id"] for c in obs["current"]["players"][SEAT]["hand"]]
    assert sorted(hand) == sorted([FEZ, LILLIE, MEGANIUM, BOSS])
    chosen = _discarded(obs)
    assert sorted(chosen) == sorted([FEZ, BOSS]), (
        f"el coste sale del Fezandipiti y del Boss's Orders; descarto {chosen}")
    assert MEGANIUM not in chosen, (
        "la Ultra Ball esta cavando el Bayleef: descartar el Meganium tira el "
        "motivo de su propia compra, y contra el muro Crustle ese Meganium es "
        "lo que paga el ataque del Tapu Bulu")
    assert LILLIE not in chosen, (
        "el unico Supporter de refresco que queda no paga costes")


def test_with_the_bayleef_out_of_the_deck_the_meganium_goes_back_to_fodder():
    """CONTROL: the protection is not about the Meganium, it is about the link
    the search can still buy. With both Bayleef gone -- here, into the discard
    pile -- there is nothing to fetch and the orphan pays the cost again."""
    obs = _record_obs()
    me = obs["current"]["players"][SEAT]
    me["discard"] = me["discard"] + [
        {"id": BAYLEEF, "playerIndex": SEAT, "serial": 200},
        {"id": BAYLEEF, "playerIndex": SEAT, "serial": 201}]
    assert MEGANIUM in _discarded(obs), (
        "sin Bayleef en el mazo la Ultra Ball no puede desorfanar nada")


def test_with_a_bayleef_already_on_the_bench_nothing_changes():
    """CONTROL: the ordinary branch already covered this board (score 3). The
    new rule must be a no-op where the old one was already right."""
    obs = _record_obs()
    me = obs["current"]["players"][SEAT]
    me["bench"][2] = {"appearThisTurn": False, "energies": [], "energyCards": [],
                      "hp": 110, "id": BAYLEEF, "maxHp": 110,
                      "playerIndex": SEAT, "serial": 202,
                      "preEvolution": [{"id": CHIKORITA, "playerIndex": SEAT,
                                        "serial": 68}], "tools": []}
    assert MEGANIUM not in _discarded(obs)


def test_a_discard_forced_by_their_card_buys_nothing():
    """CONTROL: the whole rule hangs on the cost being OURS. Under an opposing
    hand-cutter no search is coming and the orphan is an orphan again."""
    obs = _record_obs()
    obs["select"]["effect"] = {"id": m.Xerosic_Machinations,
                               "playerIndex": 1 - SEAT, "serial": 300}
    assert MEGANIUM in _discarded(obs)


# ---------------------------------------------------------------------------
# 3. The guard: the protection must NOT become a veto
# ---------------------------------------------------------------------------

def test_the_ultra_ball_is_still_played_at_all():
    """The step BEFORE the cost, on the same board: the Ultra Ball is the play
    of the turn and it stays that way.

    This is the guard, not a formality. If `_ub_real_fodder` ever learns this
    rule, the cost vetoes start cancelling the very search that un-orphans the
    piece and we end up with neither the Bayleef nor the Meganium on the board.
    """
    with open(_FIXTURE_PLAY, encoding="utf-8") as f:
        obs = copy.deepcopy(json.load(f)["observation"])
    me = obs["current"]["players"][SEAT]
    picked = obs["select"]["option"][m.agent(obs)[0]]
    assert picked.get("type") == int(m.OptionType.PLAY) and (
        me["hand"][picked["index"]]["id"] == ULTRA_BALL), (
        f"la Ultra Ball sigue siendo la jugada del turno; eligio {picked}")
