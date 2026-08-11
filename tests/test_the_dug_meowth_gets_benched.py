"""The Meowth ex the Ultra Ball dug out gets BENCHED, not shuffled back.

Scenario (`records/registro_004_pasos_048_hasta_077.json`, episode 91839511,
steps 56-59, turn 4 vs Alakazam, WON in spite of this):

    US                                     RIVAL
    active  Ralts line 60/70, 0 energy     active  Dunsparce 70/70
    bench   Meowth ex, Ogerpon ex (3       bench   Abra (1 energy), Kadabra x2,
            Grass: READY), Kadabra                 Ogerpon ex, Abra
    hand    Ultra Ball, Grass,             hand    **10 cards**
            **LILLIE'S DETERMINATION**,            -> Powerful Hand projects
            Grass, Dipplin                            20 x 10 = 200

The turn's plan was the one the matchup asks for and the agent started it
correctly: `_alakazam_dig_xerosic_engine` played the Ultra Ball (5950) to
assemble Ultra Ball -> Meowth ex -> Last-Ditch Catch (fetches Xerosic) -> play
Xerosic, which caps Powerful Hand. Two cards were discarded for it and the fetch
brought the Meowth ex (1300, `engine_pivot_turn`).

And then the next menu threw the whole thing away:

    * the Meowth ex PLAY, already lifted to 21000 by `_ub_meowth_pending` ("a
      card of ours spent itself this turn to put this body in hand"), was cut
      to SCORE_VETO by the rule "never bench a Meowth ex to fetch a Lillie's we
      already hold";
    * the Lillie's was itself vetoed by
      `alakazam_reserves_supporter_for_xerosic` ("the turn's Supporter is
      reserved for the cap");
    * with both plays at -1 the turn looked sterile, so the Lillie's rescue of
      `finalize.py` lifted it to 1500 -- and the refill shuffled the Meowth ex
      that had just cost two discards straight back into the deck.

Root cause: "a Lillie's Determination in hand" is a PROXY for "the Last-Ditch
would bring a copy of what I am already holding", and vs Alakazam with a fat
opposing hand the proxy is false -- the fetch points at the XEROSIC'S
MACHINATIONS still in the deck. `_meowth_fetch_already_in_hand` is now
subordinated to `_meowth_fetch_redundante`, the general, deck-agnostic form of
the same question, which replays `_RULES_MEOWTH_FETCH` over the Supporters left
in the deck and asks whether THAT card is the one in hand.

Both halves keep reading the same board predicate, so the invariant of
`test_alakazam_step16_the_meowth_engine_and_the_ability_do_not_contradict`
(if the body goes down, the ability is used) holds by construction.
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
            / "alakazam_t4_the_dug_meowth_gets_benched_step59.json")

MEOWTH = m.Meowth_ex
LILLIE = m.Lillie_Determination
XEROSIC = m.Xerosic_Machinations
ULTRA_BALL = m.Ultra_Ball


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
    yield
    m._init_cards_tracking()


def _frames():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return {item["step"]: copy.deepcopy(item["observation"])
            for item in data["sequence"]}


def _played_id(obs, choice):
    """Id of the card the main menu plays, or None if it is not a PLAY."""
    opt = obs["select"]["option"][choice[0]]
    if opt.get("type") != int(m.OptionType.PLAY):
        return None
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    return mine["hand"][opt["index"]]["id"]


def _replay_upto(step):
    """Replays the turn's menus in order and returns (obs, choice) of `step`."""
    frames = _frames()
    obs, choice = None, None
    for _s in sorted(frames):
        obs = frames[_s]
        choice = m.agent(obs)
        if _s == step:
            break
    return obs, choice


# ---------------------------------------------------------------------------
# 1. The board of the record
# ---------------------------------------------------------------------------

def test_the_board_of_step_56_is_the_one_from_the_record():
    obs = _frames()[56]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    op = cur["players"][1 - cur["yourIndex"]]

    # the turn's Supporter is free, their hand is deep in Powerful Hand range
    assert cur["supporterPlayed"] is False
    assert op["handCount"] == 10
    # the Ultra Ball and the Lillie's are BOTH in hand: that is the whole point
    hand = [c["id"] for c in mine["hand"]]
    assert ULTRA_BALL in hand and LILLIE in hand
    # ...and the Meowth ex is not (it has to be dug out)
    assert MEOWTH not in hand


# ---------------------------------------------------------------------------
# 2. The chain: the Ultra Ball is played and its fetch brings the Meowth ex
# ---------------------------------------------------------------------------

def test_the_ultra_ball_is_played_for_the_xerosic_engine():
    obs, choice = _replay_upto(56)
    assert _played_id(obs, choice) == ULTRA_BALL, (
        "vs Alakazam with 10 cards in their hand the turn is the cap: the "
        "Ultra Ball digs the Meowth ex that fetches the Xerosic")
    assert m.AGENT_STATE._ub_engine_pivot_turn is True


def test_the_search_brings_the_meowth_ex():
    obs, choice = _replay_upto(58)
    fetched = obs["select"]["deck"][
        obs["select"]["option"][choice[0]]["index"]]["id"]
    assert fetched == MEOWTH, (
        "the pivot is armed: the search has to bring the Meowth ex")
    assert m.AGENT_STATE._ub_meowth_pending is True


# ---------------------------------------------------------------------------
# 3. The fix: the body that was paid for goes DOWN, the refill waits
# ---------------------------------------------------------------------------

def test_the_dug_meowth_is_benched_instead_of_being_shuffled_away():
    obs, choice = _replay_upto(59)
    played = _played_id(obs, choice)
    assert played == MEOWTH, (
        "two discards were spent digging this Meowth ex out: benching it "
        "(Last-Ditch -> Xerosic) is the turn. Playing the Lillie's shuffles it "
        f"straight back into the deck; it played {m.card_table[played].name if played else choice}")


def test_the_fetch_this_turn_points_at_the_xerosic_not_at_a_second_lillies():
    """The premise of the lifted veto, checked on the fetch's own predictor."""
    obs, _ = _replay_upto(58)
    obs59 = _frames()[59]
    m.agent(obs59)
    # the Xerosic is still in the deck and not in hand -- the fetch has a target
    mine = obs59["current"]["players"][obs59["current"]["yourIndex"]]
    assert XEROSIC not in [c["id"] for c in mine["hand"]]
    assert m.AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
        XEROSIC, {}).get(m.ZONE_DECK, 0) > 0


def test_control_without_the_alakazam_hand_the_lillies_still_wins():
    """Counterfactual: with their hand SHORT the cap is worthless, the Last-
    Ditch would only bring a second Lillie's and the veto has to hold."""
    frames = _frames()
    for _s in sorted(frames):
        obs = frames[_s]
        op = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
        op["handCount"] = 3
        choice = m.agent(obs)
        if _s == 59:
            assert _played_id(obs, choice) == LILLIE, (
                "with the opposing hand at 3 there is nothing to cap: the "
                "Lillie's refill is the turn and the Meowth ex stays in hand")
