"""The card that opens the deck is counted as a prize while it is in the air.

FOUND BY `utils/invariant_monitor.py`, not by a lost game. The invariant is one
line long and needs nobody to know the right play: the tracker cannot place more
cards in the prizes than there are prizes still face down. It fired 5 074 times
in 300 games.

THE MECHANISM. `ptcg/state/tracking.py::_identify_prizes` runs whenever the
engine shows us the COMPLETE deck, which is the only moment we can tell a prize
from a card still in there. It reconciles by subtraction, per card id:

    hidden = total copies - HAND - BENCH - DISCARD
    prize  = hidden - (copies visible in the revealed deck)

The reveal is triggered by playing a card, and at that instant that card is in
none of those zones: it has left the hand and has not reached the discard yet.
So it counts as `hidden`, it is not in the deck view, and the subtraction files
it under PRIZE. Every full-deck search invents one prize, and it is always the
searcher itself.

THE BOARD BELOW. An Ultra Ball is being played. The deck it reveals holds 46
cards and THREE Ultra Balls; the deck has four. The fourth is the one in the
player's hand on its way to the discard -- and the tracker records it as prized,
which brings its total to seven cards in six prizes.

WHY IT IS NOT COSMETIC. `ACTIVE_CARDS_IN_DECK` is not bookkeeping, it is a
premise: `_gt_planes` and `_gt_wanted_basics` will not plan a line whose next
card shows `ZONE_DECK == 0`, and the Meowth -> Lillie's engine asks the same
question of both cards. A copy filed under PRIZE is a copy the deck no longer
has as far as every one of those rules is concerned. The error is also
self-renewing rather than self-correcting: the next full reveal fixes the
previous searcher and mis-files the new one, so there is always exactly one
card the agent believes it cannot draw.

SCOPE, measured rather than assumed: of the effects that reach the
reconciliation at all, only the ones that reveal the WHOLE deck do -- Ultra Ball
always, anything else only when `len(select.deck) == deckCount`. A "look at the
top 7" (Bug Catching Set) is skipped by that guard and cannot produce this.

FIXED, and the shape of the fix is the interesting part. The obvious version --
"if this is the effect's card and something is unaccounted, it is in flight" --
guesses, because from inside the loop a copy of the searcher sitting in a PRIZE
looks exactly like one in flight. Measured, that guess was wrong 65 times in
26 280 boards: it moved the error rather than removing it.

What the fix does instead is ask the ENGINE. There are exactly
`len(my_state.prize)` cards face down; if the reconciliation has placed more
than that, the belief is provably impossible and the surplus is the one card we
can name. Deciding against a count nobody can fudge can only fire when something
is definitely wrong, so it cannot invent the opposite error -- and it does not:
zero violations of either kind over 26 617 judged boards, where the old code had
3 281 of them.

The tests below now pin the fixed behaviour. The evidence of what it used to do
is kept in the fixture and in the first two, because the board is the finding.
"""

import json
from pathlib import Path

import main as m
from golden_corpus import reset_agent
from ptcg.state.zones import ZONE_DECK, ZONE_DISCARD, ZONE_PRIZE

FIXTURE = (Path(__file__).parent / "fixtures"
           / "the_ultra_ball_in_flight_becomes_a_prize.json")

ULTRA_BALL = 1121
COPIES_IN_THE_DECK = 4


def _board():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _prizes_face_down(observation):
    current = observation["current"]
    return len(current["players"][current["yourIndex"]]["prize"])


def _believed_prizes(belief):
    return sum(entry.get(ZONE_PRIZE, 0) for entry in belief.values())


def test_the_fixture_is_the_board_the_monitor_found():
    """Guard the evidence itself: these numbers are the finding."""
    finding = _board()["finding"]
    assert finding["kind"] == "DECK_BELIEF"
    assert finding["believed_prizes"] == 7
    assert finding["prizes_face_down"] == 6
    assert finding["effect_card_id"] == ULTRA_BALL


def test_the_reveal_is_complete_and_shows_three_of_the_four_ultra_balls():
    """The proof that the fourth copy is in flight and not in the prizes.

    The reveal covers the whole deck -- 46 cards for a `deckCount` of 46 -- so
    what it does not show is not in there. It shows three Ultra Balls out of the
    four the deck runs, and the missing one is the card producing this very
    effect.
    """
    finding = _board()["finding"]
    assert finding["cards_in_the_revealed_deck"] == finding["deck_count"]
    assert finding["ultra_balls_in_the_revealed_deck"] == 3
    assert m.my_deck.count(ULTRA_BALL) == COPIES_IN_THE_DECK


def test_the_agent_no_longer_places_seven_cards_in_six_prizes():
    """The live regression: the real agent, on the board that used to fail."""
    board = _board()
    reset_agent(m)
    m.agent(board["observation"])
    belief = m.AGENT_STATE.ACTIVE_CARDS_IN_DECK
    assert _prizes_face_down(board["observation"]) == 6
    assert _believed_prizes(belief) == 6, "seven, once"


def test_the_ultra_ball_in_flight_is_booked_where_it_is_going():
    """The mechanism, named, and now pointing at the right zone.

    Three copies in the revealed deck plus the one being played accounts for all
    four, and the fourth is not in the prizes -- it is on its way to the
    discard, which is where it is booked until the next decision syncs the zone
    from the observation. The five zones still add up to the four copies, which
    is the half the first attempt at this fix got wrong.
    """
    reset_agent(m)
    m.agent(_board()["observation"])
    entry = m.AGENT_STATE.ACTIVE_CARDS_IN_DECK[ULTRA_BALL]
    assert entry[ZONE_DECK] == 3
    assert entry[ZONE_PRIZE] == 0, "not a prize"
    assert entry[ZONE_DISCARD] == 1, "on its way to the discard"
    assert sum(entry.values()) == COPIES_IN_THE_DECK


def test_the_tracker_never_believes_more_prizes_than_are_face_down():
    """The invariant itself, which is what utils/invariant_monitor.py checks on
    every decision of every game, asserted here on the board that broke it."""
    board = _board()
    reset_agent(m)
    m.agent(board["observation"])
    believed = _believed_prizes(m.AGENT_STATE.ACTIVE_CARDS_IN_DECK)
    assert believed <= _prizes_face_down(board["observation"])
