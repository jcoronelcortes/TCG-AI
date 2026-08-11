"""Unfair Stamp: once OUR OWN Xerosic has capped their hand, the Stamp is KEPT.

Scenario (user, `records/registro_006_pasos_074_hasta_087.json`, episode
91690421, turn 6 vs Alakazam, LOST). One of our bodies was knocked out the turn
before, so the ACE SPEC is live, and Flip the Script had just drawn us the two
disruption cards at once:

    US                                       RIVAL
    active  Teal Mask Ogerpon ex 210 (3 {G})  active  Alakazam ex 140/140
    bench   Fezandipiti ex, Ogerpon ex,       bench   Fezandipiti ex, Kadabra x2,
            Meowth ex                                Alakazam ex, Abra
    hand    Lillie's Determination,           hand    10 cards -> 3 after Xerosic
            Hydrapple ex, **Unfair Stamp**

The ORDER was right and stays right: Xerosic goes FIRST (step 75/77) because it
DISCARDS -- seven of their ten cards to the discard forever -- while the Stamp
only SHUFFLES. What was wrong is the SECOND half. Six actions later, at the menu
of step 81, our hand was down to three cards and the agent played the Stamp:

  * as DISRUPTION it denied ONE card (3 -> 2) and handed them two fresh ones off
    the top of their deck -- with their own Fezandipiti ex on the bench ready to
    refund three more the moment we took the KO we were about to take;
  * as REFILL it shuffled Lillie's Determination (the Supporter for the next
    turn) and the Hydrapple ex that evolves our Dipplin back into the deck to
    draw five random cards.

Neither half paid, and the single copy of the ACE SPEC was gone. The card's whole
value is the resources it denies, and that value is measured against a FAT
opposing hand: our own Xerosic had just removed it.

RULE (user): once Xerosic has been played, the Unfair Stamp is NOT played that
turn -- not even with a body of ours knocked out the turn before. It waits for a
turn where there is a hand left to deny.

The fix is `_our_cap_already_spent`: it closes BOTH halves of
`_stamp_worth_playing`. The disruption half was already unreachable
(`STAMP_MIN_OP_HAND` = 4 > `XEROSIC_HAND_CAP` = 3, the invariant
`test_the_stamp_does_not_follow_our_own_xerosic` pins); the REFILL half is the
one this record lost, and it is what closes here.

It is read off the PLAY LOG of the turn, not off the board, because the board
cannot date it: `supporterPlayed` does not say WHICH Supporter went down, and a
Xerosic in the discard may be one we played three turns ago or one an Ultra Ball
threw away. Deck-agnostic -- it reads OUR play, not their archetype -- and it
auto-expires with the turn.
"""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_t6_the_stamp_is_kept_after_our_own_xerosic_step81.json")

STAMP = m.Unfair_Stamp
XEROSIC = m.Xerosic_Machinations
LILLIE = m.Lillie_Determination
HYDRA = m.Hydrapple_ex


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _turn():
    """Every menu of our turn 6, in the order the game asked them."""
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f))


def _replay(upto=81):
    """Feeds the turn's menus to the agent and returns the choice made at `upto`.

    The whole turn is replayed on purpose: the PLAY log of our Xerosic arrives in
    the batch of step 77 and the decision under test is six menus later, so a
    fixture holding only the last board would not exercise the fact at all.
    """
    data = _turn()
    choice = None
    for obs in data["observaciones"]:
        choice = m.agent(copy.deepcopy(obs))
        if obs["step"] == upto:
            return choice
    raise AssertionError(f"step {upto} is not in the fixture")


def _menu(step):
    for obs in _turn()["observaciones"]:
        if obs["step"] == step:
            return obs
    raise AssertionError(f"step {step} is not in the fixture")


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _op(obs):
    return obs["current"]["players"][1 - obs["current"]["yourIndex"]]


# ---------------------------------------------------------------------------
# 1. The record: the board that produced the mistake
# ---------------------------------------------------------------------------

def test_the_menu_of_step_81_is_the_one_from_the_record():
    obs = _menu(81)
    mine, op = _mine(obs), _op(obs)

    # Xerosic is gone from hand (played this same turn) and left them at the cap
    assert obs["current"]["supporterPlayed"] is True
    assert op["handCount"] == m.XEROSIC_HAND_CAP
    hand = [c["id"] for c in mine["hand"]]
    assert hand.count(XEROSIC) == 0
    assert hand.count(STAMP) == 1
    # the two live cards the refill would have shuffled back into the deck
    assert LILLIE in hand and HYDRA in hand
    assert mine["handCount"] == 3

    # play the Stamp / attack / ability / end -- option 0 is the Stamp
    opts = obs["select"]["option"]
    assert [o["type"] for o in opts][:2] == [int(m.OptionType.PLAY),
                                            int(m.OptionType.ATTACK)]
    assert mine["hand"][opts[0]["index"]]["id"] == STAMP

    # their board carries BOTH the Powerful Hand line and the refill engine, so
    # the floor that applies is `STAMP_MIN_OP_HAND_VS_REFILL`
    bodies = [p["id"] for p in op["active"]] + [p["id"] for p in op["bench"]]
    assert m.Alakazam_ex in bodies and m.Kadabra in bodies
    assert m.Fezandipiti_ex in bodies


def test_our_xerosic_of_this_turn_is_seen_in_the_logs():
    """The fact is dated off the PLAY log, and it is STICKY for the rest of the
    turn: it arrives in the batch of step 77 and still holds at step 81."""
    data = _turn()
    seen = {}
    for obs in data["observaciones"]:
        m.agent(copy.deepcopy(obs))
        seen[obs["step"]] = m.AGENT_STATE._xerosic_played_this_turn

    assert seen[74] is False and seen[75] is False
    assert seen[77] is True, "the PLAY log of our Xerosic travels in this batch"
    assert all(seen[s] for s in (78, 79, 80, 81)), seen


def test_the_stamp_is_not_played_at_step_81():
    obs, choice = _menu(81), _replay()
    assert choice != [0], (
        "option 0 is PLAY of the Unfair Stamp: our own Xerosic had already "
        "capped them to 3 this turn, so the Stamp denies ONE card and shuffles "
        f"Lillie's and the Hydrapple ex away; chose {choice}")
    assert obs["select"]["option"][choice[0]]["type"] != int(m.OptionType.PLAY)


def test_the_turn_attacks_instead():
    """The record's own continuation: the charged Ogerpon ex knocks the Alakazam
    ex out (180 on a 140 HP body). The Stamp was not competing against nothing."""
    obs, choice = _menu(81), _replay()
    assert len(choice) == 1
    assert obs["select"]["option"][choice[0]]["type"] == int(m.OptionType.ATTACK)


# ---------------------------------------------------------------------------
# 2. The rule, deck-agnostic and on both halves of the card
# ---------------------------------------------------------------------------

def _ctx(**kw):
    base = dict(ko_last_turn=True,
                hand_counts={STAMP: 1},
                cards_in_deck={},
                op_hand_count=m.XEROSIC_HAND_CAP,
                my_hand_len=3,
                state=SimpleNamespace(supporterPlayed=True),
                op_state=None,
                our_xerosic_capped_this_turn=True)
    base.update(kw)
    return SimpleNamespace(**base)


def test_our_cap_closes_the_refill_clause():
    """The half this record lost: a hand small enough for the refill to look
    cheap (`my_hand_len - 1 <= STAMP_MAX_HAND_SACRIFICED`) no longer buys the
    play once we have capped them ourselves."""
    cheap = m.STAMP_MAX_HAND_SACRIFICED       # a hand the refill can afford
    assert m._stamp_worth_playing(m.XEROSIC_HAND_CAP, cheap)
    assert not m._stamp_worth_playing(m.XEROSIC_HAND_CAP, cheap,
                                      our_cap_already_spent=True)


def test_our_cap_closes_the_disruption_clause_too():
    """It is stated on BOTH halves: the rule is about the card, not about the
    floor. Their hand cannot grow past the cap on our own turn, so this is
    belt-and-braces -- but a future card that hands them cards must not reopen
    the Stamp either."""
    big = m.STAMP_MIN_OP_HAND_VS_REFILL + 6
    assert m._stamp_worth_playing(big, 9)
    assert not m._stamp_worth_playing(big, 9, our_cap_already_spent=True)


def test_the_clause_is_off_by_default():
    """Callers that do not carry the datum keep the behaviour they had: the rule
    only SUBTRACTS plays, it never invents one."""
    assert m._stamp_worth_playing(m.STAMP_MIN_OP_HAND, 9)
    assert not m._our_cap_already_spent(SimpleNamespace())
    assert not m._our_cap_already_spent(_ctx(our_xerosic_capped_this_turn=False))
    assert m._our_cap_already_spent(_ctx())


def test_the_vetoed_stamp_does_not_paralyse_the_turn():
    """`_stamp_pendiente` is the single source of the ordering vetoes (Boss's,
    Lillie's, Lana's, Dawn, Xerosic, the Meowth chain and Flip the Script). A
    Stamp that is going to wait must not collect their yields: after our own cap
    the turn carries on with the cards that CAN still be played -- which at step
    81 was the attack."""
    ctx = _ctx()
    assert not m._stamp_worth_playing_ctx(ctx)
    assert not m._stamp_pendiente(ctx)
    assert m._score_unfair_stamp_play(ctx) <= 0


def test_the_veto_is_named_in_its_own_rule():
    """It sits ABOVE the value clause so the trace says WHY: what closed the
    Stamp was a card WE played, not a thin opposing hand."""
    names = [r.name for r in m._RULES_STAMP_PLAY]
    assert names[0] == "our_xerosic_already_capped_them"
    assert names.index("our_xerosic_already_capped_them") < names.index(
        "no_disruption_no_refresh")


# ---------------------------------------------------------------------------
# 3. It expires with the turn
# ---------------------------------------------------------------------------

def test_the_cap_of_the_turn_does_not_survive_the_turn():
    """Their hand refills between turns, so the flag is PER TURN: the Stamp is
    fully available again on the next one. Without this the single copy would be
    frozen in hand for the rest of the game."""
    data = _turn()
    for obs in data["observaciones"]:
        m.agent(copy.deepcopy(obs))
    assert m.AGENT_STATE._xerosic_played_this_turn is True

    # the same last menu, one turn later: no Xerosic in this turn's logs
    later = copy.deepcopy(_menu(81))
    later["current"]["turn"] += 2
    later["logs"] = []
    m.agent(later)
    assert m.AGENT_STATE._xerosic_played_this_turn is False
