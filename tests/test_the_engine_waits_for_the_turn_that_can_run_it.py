"""The Ultra Ball was spent on a body the turn could no longer charge.

Scenario (user, `records/registro_002_pasos_011_hasta_018.json`, episode
91529732, turn 2 vs Cynthia's Garchomp ex -- LOST):

    US (6 prizes)                          RIVAL (6 prizes)
    active  Tapu Bulu 140, NO energy       active  a 140 HP basic, no energy
    bench   Applin 40, 1 {G}               bench   --
    hand    Bayleef, Grass, ULTRA BALL,
            Meganium, Hydrapple ex, Grass  (our Supporter slot: SPENT)

Our first turn of action, going second. The Lillie's Determination of the turn
had already been played and the attachment already made. The three evolution
pieces in hand are DEAD cards: Bayleef and Meganium want a Chikorita that is
neither in play nor in hand, and Hydrapple ex wants a Dipplin that does not
exist yet -- the Applin was benched this very turn, so it cannot even evolve.
Stripped of decoration the hand is one Ultra Ball and its two energies.

The menu was exactly two options: play the Ultra Ball, or end the turn.

`_score_ultra_ball_play` got it RIGHT and vetoed the Ultra Ball (-1; the
first-turn gate refuses it when there is no chain to run today), and END scored
0. What played the card was the ANTI-STERILE-TURN NET in `ptcg/turn/finalize.py`,
which resurrects a vetoed Ultra Ball at 200 whenever the turn would otherwise
die and there is a deployable body in the deck. It dug out a Teal Mask Ogerpon
ex, and its cost took the two Grass Energies -- the only fuel that body has.
The turn ended with a 210 HP Pokemon that cannot be charged, a hand of three
cards that cannot be played, and no energy: the next turn depended entirely on
the card drawn.

WHAT THE NET NEVER ASKS IS *WHEN* THE ULTRA BALL IS WORTH MOST. It compares "a
body versus nothing", and that is not the choice. An Ultra Ball is not consumed
by ending the turn: it is still there the next one, when the Supporter slot has
come back by itself -- and on this exact board, with the slot free, it is the
engine `_ub_engine_refresh_pivot` already prices at 31450: Ultra Ball -> Meowth
ex -> Last-Ditch Catch -> a refill Supporter -> a whole new hand. Every other
condition of that engine is met here (an underdeveloped bench, two cheap
energies to pay the cost, Meowth ex and Lillie's Determination alive in the
deck, an active that cannot knock anything out). The real choice is "a body now
versus the same search tomorrow, plus the two cards it costs, plus the Supporter
it fetches" -- and it is not close.

THE FIX. `_ub_engine_waits_for_tomorrow` asks the engine predicate on a view of
the state whose Supporter slot is free (`_CtxSupporterFree`), and the net drops
its BASIC branch when the answer is yes. It names no matchup and no target of
its own -- the only cards in it are the ones OUR refill chain is made of, which
is the same list `_ub_engine_refresh_pivot` already reads: any board where
waiting one turn turns the search into a refill answers True, whoever is sitting
across the table. It is the SECOND question the net asks and it only ever
subtracts -- the
bench-depth reading it was measured with is untouched, the empty-bench net runs
first (with no bench the body has to land today or a knockout ends the game),
the evolution branch is untouched (completing a line is an action TODAY) and the
item lock is excluded by the caller (with Budew about to shut the Items off
there is no tomorrow to wait for). The four controls below are those four
boundaries.

Measured: it flips ZERO of the frozen corpus's decisions
(`tests/corpus/frozen_decisions.json`, the whole suite is green with it in) and
`utils/gate_the_engine_waits.py --census` counts how rare the board is.

THE SECOND HALF OF THIS RECORD IS NOT FIXED HERE, on purpose. Once the Ultra
Ball was played, the `SelectContext.DISCARD` ladder paid its cost with the two
Grass (score 80 each) while holding Bayleef (50) and Meganium (40) -- two cards
that cannot enter play for at least two turns. The energy that fuels the body a
search is buying is fodder ranked ABOVE cards that are dead on this board, which
is the same disagreement `DISCARD_LINK_THE_SEARCH_BUYS` and
`DISCARD_WHAT_THE_SEARCH_ALREADY_BOUGHT` already close for the bought card
itself, asked of its FUEL. That is a ladder change with its own blast radius and
its own measurement, and it is written down as pending rather than smuggled in
here: with this rule in, the record's Ultra Ball is not played at all.
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
            / "garchomp_t2_the_engine_waits_for_the_turn_that_can_run_it"
              "_step14.json")

SEAT = 1                 # our seat in the record
DECISION_STEP = 14       # the menu {play the Ultra Ball, end the turn}

APPLIN = m.Applin
BAYLEEF = m.Bayleef
BUDEW = m.Budew
GRASS = m.Basic_Grass_Energy
HYDRAPPLE = m.Hydrapple_ex
LILLIE = m.Lillie_Determination
MEGANIUM = m.Meganium
MEOWTH = m.Meowth_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU_BULU = m.Tapu_Bulu
ULTRA_BALL = m.Ultra_Ball


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _turn():
    """Every menu of our turn 2, in the order the game asked them."""
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observaciones"]


def _menu(menus, step):
    for obs in menus:
        if obs["step"] == step:
            return obs
    raise AssertionError(f"step {step} is not in the fixture")


def _decision(menus, step=DECISION_STEP):
    """Replays the turn up to `step` and returns (choice, option type).

    The whole turn is replayed and not just the one board: the net reads state
    the earlier menus of the same turn build (what is left in the deck, the
    bodies that appeared this turn), so a fixture holding only the decision
    would not exercise the fact.
    """
    for obs in menus:
        if obs["step"] > step:
            break
        choice = m.agent(copy.deepcopy(obs))
        if obs["step"] == step:
            picked = obs["select"]["option"][choice[0]]
            return choice, picked.get("type")
    raise AssertionError(f"step {step} is not in the fixture")


def _played_card(menus, choice, step=DECISION_STEP):
    obs = _menu(menus, step)
    idx = obs["select"]["option"][choice[0]].get("index")
    if idx is None:
        return None
    return obs["current"]["players"][SEAT]["hand"][idx]["id"]


# ---------------------------------------------------------------------------
# 1. The record: the board that produced the mistake
# ---------------------------------------------------------------------------

def test_the_menu_is_the_one_from_the_record():
    obs = _menu(_turn(), DECISION_STEP)
    cur = obs["current"]
    mine = cur["players"][SEAT]

    assert cur["turn"] == 2 and cur["firstPlayer"] == 0      # we go SECOND
    # the two things this turn has already spent: the Supporter and the attach
    assert cur["supporterPlayed"] is True
    assert cur["energyAttached"] is True

    # an active that cannot attack and a bench of exactly one body
    assert mine["active"][0]["id"] == TAPU_BULU
    assert mine["active"][0]["energies"] == []
    assert [p["id"] for p in mine["bench"]] == [APPLIN]
    # ...benched THIS turn, so the line cannot be evolved either
    assert mine["bench"][0]["appearThisTurn"] is True

    # the hand: the Ultra Ball, its two energies, and three dead cards
    assert [c["id"] for c in mine["hand"]] == [
        BAYLEEF, GRASS, ULTRA_BALL, MEGANIUM, HYDRAPPLE, GRASS]

    # and the menu really is only these two plays
    assert [o.get("type") for o in obs["select"]["option"]] == [
        int(m.OptionType.PLAY), int(m.OptionType.END)]


def test_the_engine_the_turn_is_waiting_for_is_alive_in_the_deck():
    """The deferral is not conservatism: there is something to defer TO."""
    _decision(_turn())
    deck = m.AGENT_STATE.ACTIVE_CARDS_IN_DECK
    assert deck.get(MEOWTH, {}).get(m.ZONE_DECK, 0) >= 1
    assert deck.get(LILLIE, {}).get(m.ZONE_DECK, 0) >= 1


# ---------------------------------------------------------------------------
# 2. The fix: the turn ends and the Ultra Ball is kept
# ---------------------------------------------------------------------------

def test_the_turn_ends_instead_of_buying_a_body_it_cannot_charge():
    choice, kind = _decision(_turn())
    assert kind == int(m.OptionType.END), (
        f"it played {_played_card(_turn(), choice)} instead of ending the turn")


def test_the_ultra_ball_is_still_vetoed_by_its_own_scorer():
    """The net is what changed, not the scorer: the Ultra Ball was always -1.

    Written down because it is the whole reason the fix belongs in
    `finalize.py`: raising the Ultra Ball's own score would have been fixing a
    branch that was already right.
    """
    menus = _turn()
    seen = {}
    original = m._score_ultra_ball_play

    def spy(ctx):
        value = original(ctx)
        seen["score"] = value
        return value

    m._score_ultra_ball_play = spy
    try:
        _decision(menus)
    finally:
        m._score_ultra_ball_play = original
    assert seen.get("score") == m.SCORE_VETO


# ---------------------------------------------------------------------------
# 3. The four boundaries: what the rule must NOT touch
# ---------------------------------------------------------------------------

def test_control_with_the_supporter_slot_free_the_dig_still_happens():
    """The deferral is about the SLOT and nothing else.

    Same board, same hand, same deck -- only the Supporter of the turn unspent.
    Now the chain runs TODAY (`_ub_engine_refresh_pivot`, 31450) and the Ultra
    Ball is the play. If this control ever ends the turn, the rule stopped being
    about timing and became plain conservatism.
    """
    menus = _turn()
    _menu(menus, DECISION_STEP)["current"]["supporterPlayed"] = False
    choice, kind = _decision(menus)
    assert kind == int(m.OptionType.PLAY)
    assert _played_card(menus, choice) == ULTRA_BALL


def test_the_turn_we_defer_to_is_the_one_that_buys_the_meowth():
    """WHAT we are waiting for, end to end -- otherwise this is just passing.

    The same eight menus with the Supporter slot free (which is what the next
    turn looks like on this board): the Ultra Ball is played and its fetch, out
    of a whole deck, takes the **Meowth ex** -- the body whose Last-Ditch Catch
    brings the refill Supporter back. That is the trade the rule is defending.
    """
    menus = _turn()
    for obs in menus:
        obs["current"]["supporterPlayed"] = False

    fetched = None
    for obs in menus:
        sel = obs["select"]
        choice = m.agent(copy.deepcopy(obs))
        if sel.get("deck") and sel["context"] == int(m.SelectContext.TO_HAND):
            fetched = [sel["deck"][sel["option"][i]["index"]]["id"] for i in choice]
    assert fetched == [MEOWTH], f"the search bought {fetched} instead of the Meowth ex"


def test_control_with_an_empty_bench_the_body_still_has_to_land_today():
    """With no bench a knockout on the active ENDS THE GAME.

    There is no tomorrow to keep the card for, and the anti-empty-bench net --
    which runs before this one -- must keep the last word.
    """
    menus = _turn()
    for obs in menus:
        obs["current"]["players"][SEAT]["bench"] = []
    choice, kind = _decision(menus)
    assert kind == int(m.OptionType.PLAY)
    assert _played_card(menus, choice) == ULTRA_BALL


def test_control_with_the_items_about_to_be_locked_it_is_now_or_never():
    """Budew on their field: next turn there are no Items. The card expires."""
    menus = _turn()
    for obs in menus:
        obs["current"]["players"][1 - SEAT]["bench"].append({
            "appearThisTurn": False, "energies": [], "energyCards": [],
            "hp": 40, "id": BUDEW, "maxHp": 40, "playerIndex": 1 - SEAT,
            "preEvolution": [], "serial": 950, "tools": []})
    choice, kind = _decision(menus)
    assert kind == int(m.OptionType.PLAY)
    assert _played_card(menus, choice) == ULTRA_BALL


def test_control_a_line_that_can_be_completed_today_is_not_deferred():
    """The evolution branch of the net is untouched: evolving is an action TODAY.

    Same board with the Applin SETTLED (it did not appear this turn), so the
    Dipplin the deck still holds can be searched for and played on the spot.
    """
    menus = _turn()
    for obs in menus:
        for body in obs["current"]["players"][SEAT]["bench"]:
            if body["id"] == APPLIN:
                body["appearThisTurn"] = False
    choice, kind = _decision(menus)
    assert kind == int(m.OptionType.PLAY)
    assert _played_card(menus, choice) == ULTRA_BALL


# ---------------------------------------------------------------------------
# 4. The predicate on its own
# ---------------------------------------------------------------------------

def test_the_supporter_free_view_only_rewrites_the_slot():
    """`_CtxSupporterFree` is a VIEW: everything else has to answer the truth."""
    obs = _menu(_turn(), DECISION_STEP)
    m.agent(copy.deepcopy(obs))

    class _Fake:
        pass

    real_state = _Fake()
    real_state.supporterPlayed = True
    real_state.turn = 2
    real_state.energyAttached = True
    ctx = _Fake()
    ctx.state = real_state
    ctx.bench_count = 1

    view = m._CtxSupporterFree(ctx)
    assert view.state.supporterPlayed is False
    assert view.state.turn == 2
    assert view.state.energyAttached is True
    assert view.bench_count == 1
    # the real state is not touched
    assert real_state.supporterPlayed is True
