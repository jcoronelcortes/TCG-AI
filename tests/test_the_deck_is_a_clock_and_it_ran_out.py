"""Four prizes to take and two cards left: the refill comes before the attack.

Scenario (user, episode 90321662, turn 30 vs a Crustle / Great Tusk deck, LOST).
The board at step 132 is winning:

    US                                       RIVAL
    active  Tapu Bulu 110/140, 4 energies    active  Great Tusk 140/140, 2 energies
    bench   Teal Mask Ogerpon ex  2/3        prizes  6 left
            Teal Mask Ogerpon ex  2/3        deck    12
            Meowth ex             0
            Dipplin               1/1
            Dipplin               1/1
    hand    Lillie's Determination, 3 Ultra Ball, Dawn, Hydrapple ex,
            2 Meganium, Tapu Bulu, Fezandipiti ex          (10 cards)
    prizes  4 left        deck  2

Tapu Bulu knocks the Great Tusk out for a prize. Three would still be left, so
three more turns of ours -- and the deck pays for two. The game was already lost
on time, and the agent attacked. It attacked again on turn 32 and on turn 34, and
lost by deck-out with two prizes still on the table and a board it was winning.

The Lillie's Determination sat unplayed in that hand the whole time. It shuffles
the other nine cards back and draws six: the deck goes 2 -> 5, which is exactly
the three turns the win was missing. And it costs nothing at all -- a Supporter
does not end the turn, so the Tapu attacks afterwards just the same.

What silenced it was `line_pending` ("evolve first, THEN refill"): a Hydrapple ex
in hand with a Dipplin on the bench. That veto is about VALUE -- it assumes there
is a later turn to refill in. `_deck_clock_runs_out` is the case where there is
not, and the new rule sits above every veto that merely postpones the refill.

The arithmetic is deck-agnostic and both halves are needed:
  * `_deck_clock_runs_out(deck, prizes)` -- one card drawn per turn, at best one
    prize per turn, so `deck <= prizes` means the race is lost on time;
  * `_refill_deck_delta(...) > 0` -- with a SHORT hand Lillie's burns deck
    instead of returning it, and firing there would bring the end closer.

Coverage:
  * the record's board: Lillie's takes the turn, not the attack;
  * the arithmetic actually lands on 5 cards;
  * once the Supporter is spent, the same turn still closes by attacking;
  * controls -- a deck that covers the prizes leaves the attack alone, and a
    short hand (where the refill would BURN deck) does not fire the rule either.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, str(_p))

import main as m
from cg.api import OptionType

LILLIE = m.Lillie_Determination
TAPU = m.Tapu_Bulu
HYDRAPPLE = m.Hydrapple_ex
DIPPLIN = m.Dipplin
GRASS = m.Basic_Grass_Energy

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "great_tusk_step132_the_deck_clock_runs_out.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._prev_op_prize = 6
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _chosen(obs, choice):
    assert choice, f"the agent returned nothing: {choice}"
    return obs["select"]["option"][choice[0]]


def _is_play_of(obs, opt, card_id):
    if opt["type"] != int(OptionType.PLAY):
        return False
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    return mine["hand"][opt["index"]]["id"] == card_id


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_step132_the_board_is_the_records_one():
    obs = _obs()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]

    assert mine["active"][0]["id"] == TAPU
    assert len(mine["active"][0]["energies"]) == 4, "ready to attack"
    assert mine["deckCount"] == 2
    assert len(mine["prize"]) == 4
    assert len(mine["hand"]) == 10
    assert sum(1 for c in mine["hand"] if c["id"] == LILLIE) == 1
    assert cur["supporterPlayed"] is False
    # The veto that silenced it: a Hydrapple ex in hand over a benched Dipplin.
    assert sum(1 for c in mine["hand"] if c["id"] == HYDRAPPLE) == 1
    assert any(p["id"] == DIPPLIN for p in mine["bench"])
    # And the attack really was available -- this is not "it had nothing to do".
    assert any(o["type"] == int(OptionType.ATTACK)
               for o in obs["select"]["option"])


def test_step132_the_refill_takes_the_turn_before_the_attack():
    obs = _obs()
    opt = _chosen(obs, m.agent(obs))
    assert _is_play_of(obs, opt, LILLIE), (
        f"expected Lillie's Determination -- the only play that buys the turns "
        f"the win still needs -- and got {opt}")


def test_the_arithmetic_is_the_three_turns_that_were_missing():
    obs = _obs()
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    deck, hand, prizes = mine["deckCount"], len(mine["hand"]), len(mine["prize"])

    assert m._deck_clock_runs_out(deck, prizes), (
        "two cards do not cover four prizes: the race is lost on time")
    assert m._refill_deck_delta(deck, hand, prizes) == 3
    assert deck + m._refill_deck_delta(deck, hand, prizes) == 5, (
        "nine cards back, six drawn: the deck ends at five")


# ---------------------------------------------------------------------------
# 2. The refill costs nothing: the same turn still attacks
# ---------------------------------------------------------------------------

def _after_the_refill():
    """The same turn once Lillie's has resolved: the Supporter is spent, the
    deck is at 5 and the hand is the six cards it drew. The board is untouched
    -- which is the whole point."""
    obs = copy.deepcopy(_obs())
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    cur["supporterPlayed"] = True
    mine["deckCount"] = 5
    mine["hand"] = [c for c in mine["hand"] if c["id"] != LILLIE][:6]
    mine["handCount"] = len(mine["hand"])
    # The menu the engine emits next: the same one without the Lillie's PLAY.
    keep = []
    for o in obs["select"]["option"]:
        if o["type"] == int(OptionType.PLAY) and o["index"] >= len(mine["hand"]):
            continue
        keep.append(o)
    obs["select"]["option"] = keep
    return obs


def test_once_the_supporter_is_spent_the_turn_still_attacks():
    obs = _after_the_refill()
    opt = _chosen(obs, m.agent(obs))
    assert opt["type"] == int(OptionType.ATTACK), (
        f"the refill does not end the turn: the Tapu Bulu still knocks the "
        f"Great Tusk out. Got {opt}")


# ---------------------------------------------------------------------------
# 3. Controls: the rule is the clock, not a new preference for Lillie's
# ---------------------------------------------------------------------------

def test_a_deck_that_covers_the_prizes_leaves_the_attack_alone():
    obs = copy.deepcopy(_obs())
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    mine["deckCount"] = 20        # the only change
    opt = _chosen(obs, m.agent(obs))
    assert opt["type"] == int(OptionType.ATTACK), (
        f"with the clock covering the race the previous ladder rules and the "
        f"turn closes by attacking. Got {opt}")


def test_a_short_hand_does_not_fire_it_because_the_refill_burns_deck():
    """With four cards in hand the refill puts three back and draws six: the
    deck goes 2 -> -1. Firing the rule there would bring the end CLOSER."""
    obs = copy.deepcopy(_obs())
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    lillie = next(c for c in mine["hand"] if c["id"] == LILLIE)
    mine["hand"] = [lillie] + [c for c in mine["hand"] if c["id"] != LILLIE][:3]
    mine["handCount"] = 4
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if o["type"] != int(OptionType.PLAY) or o["index"] < 4]

    assert m._refill_deck_delta(2, 4, 4) == -3, "it burns three cards of deck"
    opt = _chosen(obs, m.agent(obs))
    assert not _is_play_of(obs, opt, LILLIE), (
        f"a refill that shortens the clock is not the answer to the clock. "
        f"Got {opt}")


def test_the_clock_reading_itself():
    # deck <= prizes: equality only survives a perfect game (a prize every turn
    # and not one card spent on searching or charging).
    assert m._deck_clock_runs_out(2, 4) is True
    assert m._deck_clock_runs_out(4, 4) is True
    assert m._deck_clock_runs_out(5, 4) is False
    assert m._deck_clock_runs_out(30, 6) is False
    # The draw is 8 only while all six prizes are untouched.
    assert m._refill_deck_delta(2, 10, 4) == 3
    assert m._refill_deck_delta(2, 10, 6) == 1
