"""Unfair Stamp: it is not spent on a hand our OWN Xerosic has just capped.

Scenario (`records/registro_013_pasos_125_hasta_140.json`, episode 90215840,
turn 13 vs Alakazam, WON). The turn opens with one of our bodies knocked out,
so the Stamp is live, and their hand at SIXTEEN cards:

    US                                     RIVAL
    active  Ogerpon ex -> Hydrapple ex     active  Alakazam ex 140/140
    bench   Meowth ex, Tapu Bulu,          bench   Kadabra, three 1-prize
            Meganium, Ogerpon ex                   bodies (NO Fezandipiti ex)
    hand    **Unfair Stamp**, **Xerosic**, hand    16 cards -> 3 after Xerosic
            Boss's, Lana's, Forest,
            Ogerpon ex, Hydrapple ex

The ORDER was right and stays right: with 16 cards on their side
`yields_the_order_to_xerosic` holds the Stamp back, Xerosic discards thirteen
cards FOREVER (step 132) and the Stamp keeps its slot for the same turn -- the
Stamp only shuffles, so playing it first would have sent those thirteen cards
back to their deck.

What was wrong was the SECOND half of that sequence. Xerosic leaves them at
exactly three cards, and the Stamp leaves them at two: after our own cap it
denies ONE card. The agent played it anyway (step 136 of the record, with
`STAMP_MIN_OP_HAND` still at 3), shuffling a curated seven-card hand -- Boss's
Orders, Lana's Aid, Forest of Vitality, a spare Hydrapple ex -- to draw five
random ones, and burning the single copy of the ACE SPEC on one denied card.
Neither half of the card paid: it did not disrupt (3 -> 2) and it did not
refresh (7 -> 5).

The floor at `STAMP_MIN_OP_HAND` = 4 is what closes it, and the number is not a
coincidence: it sits one above `XEROSIC_HAND_CAP`, so a hand that our own
Xerosic capped can NEVER reach the disruption clause again. That invariant is
asserted below.

SUPERSEDED IN PART (user, registro_006 step 81, episode 91690421 vs Alakazam,
LOST): the refill clause used to be left open here on purpose -- "with a hand of
<= 5 the Stamp still pays, which is the case the clause exists for" -- and that
is the half that lost the later record, shuffling a Lillie's Determination and a
Hydrapple ex back into the deck for five random cards. After OUR OWN Xerosic the
Stamp is now kept for a later turn, both halves closed
(`_our_cap_already_spent`, tests/test_the_stamp_is_kept_after_our_own_xerosic.py).
What the clause below still says is the part that survives: the refill stays open
when the short opposing hand is NOT our own doing.
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
            / "alakazam_t13_the_stamp_does_not_follow_our_own_xerosic_step136.json")

STAMP = m.Unfair_Stamp
XEROSIC = m.Xerosic_Machinations


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


def _load():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return (copy.deepcopy(data["observacion_previa"]),
            copy.deepcopy(data["observation"]))


def _decision():
    """The turn as it was played: the first menu (their hand still at 16, where
    the Stamp yields the order to Xerosic) and then the menu of step 136, after
    Xerosic has capped them."""
    previa, dec = _load()
    m.agent(previa)
    return m.agent(dec)


# ---------------------------------------------------------------------------
# 1. The record: the board that produced the mistake
# ---------------------------------------------------------------------------

def test_the_menu_of_step_136_is_the_one_from_the_record():
    previa, dec = _load()
    cur = dec["current"]
    yo = cur["yourIndex"]
    mine, op = cur["players"][yo], cur["players"][1 - yo]

    # Xerosic is already gone (played this same turn) and left them at the cap
    assert previa["current"]["players"][1 - yo]["handCount"] == 16
    assert op["handCount"] == m.XEROSIC_HAND_CAP
    assert cur["supporterPlayed"] is True
    assert [c["id"] for c in mine["hand"]].count(XEROSIC) == 0
    assert [c["id"] for c in mine["hand"]].count(STAMP) == 1
    assert mine["handCount"] == 7

    # play a card x3 / attack / end -- option 0 is the Stamp
    assert [o["type"] for o in dec["select"]["option"]] == [
        int(m.OptionType.PLAY), int(m.OptionType.PLAY), int(m.OptionType.PLAY),
        int(m.OptionType.ATTACK), int(m.OptionType.END)]
    assert mine["hand"][dec["select"]["option"][0]["index"]]["id"] == STAMP

    # their board carries the Powerful Hand line but NO refill engine, so the
    # floor that decides is the plain one, not `STAMP_MIN_OP_HAND_VS_REFILL`
    bodies = [p["id"] for p in op["active"]] + [p["id"] for p in op["bench"]]
    assert m.Alakazam_ex in bodies and m.Kadabra in bodies
    assert m.Fezandipiti_ex not in bodies


def test_the_stamp_is_no_longer_played_at_step_136():
    choice = _decision()
    assert choice != [0], (
        "option 0 is PLAY of the Unfair Stamp: our own Xerosic had just capped "
        "them to 3, so the Stamp denies ONE card and shuffles a seven-card "
        f"hand away; chose {choice}")


def test_the_turn_attacks_instead():
    """The record's own continuation: Hydrapple ex knocks the Alakazam ex out
    (330 on a 140 HP body). The Stamp was not competing against nothing."""
    _, dec = _load()
    choice = _decision()
    assert len(choice) == 1
    assert dec["select"]["option"][choice[0]]["type"] == int(m.OptionType.ATTACK)


# ---------------------------------------------------------------------------
# 2. The invariant: the Stamp never disrupts a hand Xerosic capped
# ---------------------------------------------------------------------------

def test_the_disruption_floor_sits_above_the_xerosic_cap():
    """The two constants have to stay coupled: if the floor ever drops to the
    cap, the sequence Xerosic -> Stamp of this record comes straight back."""
    assert m.STAMP_MIN_OP_HAND > m.XEROSIC_HAND_CAP
    assert m.STAMP_MIN_OP_HAND_VS_REFILL >= m.STAMP_MIN_OP_HAND


def test_a_hand_capped_by_xerosic_never_reaches_the_disruption_clause():
    big_hand = m.STAMP_MAX_HAND_SACRIFICED + 3      # our 7 cards at step 136
    for op_hand in range(0, m.XEROSIC_HAND_CAP + 1):
        assert not m._stamp_worth_playing(op_hand, big_hand), op_hand


def test_the_refill_clause_only_stays_open_when_the_cap_is_not_ours():
    """With a hand the Stamp can afford to shuffle (<=
    `STAMP_MAX_HAND_SACRIFICED` cards beyond the Stamp itself) the refill half
    still pays against a short opposing hand -- but NOT when that hand is short
    because our own Xerosic made it so (registro_006 step 81; see
    `_our_cap_already_spent`)."""
    small_hand = m.STAMP_MAX_HAND_SACRIFICED + 1
    assert m._stamp_worth_playing(m.XEROSIC_HAND_CAP, small_hand)
    assert not m._stamp_worth_playing(m.XEROSIC_HAND_CAP, small_hand,
                                      our_cap_already_spent=True)
