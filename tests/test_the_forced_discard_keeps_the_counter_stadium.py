"""A forced discard keeps ONE counter-stadium, and drops the body with no seat.

Scenario (`records/registro_006_pasos_077_hasta_100.json`, episode 91519548,
step 99, turn 6 vs Alakazam -- LOST). We are `playerIndex` 1:

    US                                        RIVAL
    active  Hydrapple ex 330/330              active  Kadabra 140/140
    bench   Meganium, Teal Mask Ogerpon ex,   bench   Kadabra, Kadabra, and
            Meowth ex, Fezandipiti ex,                three more 1-prize
            Tapu Bulu   -- FULL, 5/5                  bodies. NOT ONE ex.
    hand    Meganium, Night Stretcher,        stadium **Neutralization Zone**
            Lana's Aid, Teal Mask Ogerpon              (theirs)
            ex, **Forest of Vitality x2**

Their Xerosic's Machinations cut that hand of six down to three. The agent
discarded **Meganium and BOTH Forest of Vitality**, keeping Night Stretcher,
Lana's Aid and the Teal Mask Ogerpon ex.

Two mistakes in one menu.

1. THE COUNTER-STADIUM KEPT ZERO COPIES. Under their Neutralization Zone our ex
   do 0 damage to a body without a rule box (`_our_effective_damage`), and their
   whole board is 1-prize bodies: our active Hydrapple ex, the Ogerpon ex and
   the Meowth ex on the bench were all mute. The only card in the deck that
   lifts the Zone is our own stadium -- and we held two of them. The DISCARD
   branch protects the Forest as the critical counter-stadium, but it gated that
   protection on `hand_counts[Forest_of_Vitality] <= 1`, so it switched OFF
   exactly when we held more than one out: both copies fell through to the
   spare-copy score (88) and both went to the discard pile. The `<= 1` guard was
   reading "spare copies are cheap" -- true -- and answering "so throw away the
   only out too". The surplus is what is cheap; the FIRST copy is the out.

2. THE BODY WITH NOWHERE TO SIT WAS KEPT OVER THE CARDS THAT STILL DO SOMETHING.
   With the bench at 5/5 the second Teal Mask Ogerpon ex could not be played
   that turn, nor the next, nor any turn until the opponent knocked something
   out -- and one was already on the bench. It still scored 25 ("only one in
   play") and so outranked the Night Stretcher (30) and the Lana's Aid (35),
   the two cards that buy bodies and energy back out of the discard.

Hence the rule (user, August 2026): the counter-stadium protects ONE copy and
lets the surplus go, and a Pokemon that BOTH has no bench seat AND already has a
copy in play is a duplicate of the plan, not the plan -- it falls below every
card the turn can still use. The second half asks for both halves on purpose:
a full bench is a snapshot, not a sentence, and with only the seat question the
frozen corpus started throwing away a Tapu Bulu against ex-immune walls, where
it is the one body that can break through.

Neither rule names a card, a line or a matchup: the seat comes from
`_ub_target_has_no_seat` (the stage is read off the card data) and the hostile
stadium from `_counter_stadium_urgent`, so both hold for any deck.csv.
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
            / "alakazam_t6_forced_discard_keeps_the_counter_stadium_step99.json")

FOREST = m.Forest_of_Vitality
MEGANIUM = m.Meganium
NS = m.Night_Stretcher
LANA = m.Lanas_Aid
OGERPON = m.Teal_Mask_Ogerpon_ex

# The hand of the record, in the order the select offers it.
_HAND = [MEGANIUM, NS, LANA, FOREST, OGERPON, FOREST]


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


def _discarded_ids():
    previa, dec = _load()
    m.agent(previa)              # brings the tracking of the opposing turn
    action = m.agent(dec)
    hand = dec["current"]["players"][1]["hand"]
    return [hand[i]["id"] for i in action], action


# ---------------------------------------------------------------------------
# 1. The record: the board that produced the mistake
# ---------------------------------------------------------------------------

def test_the_menu_of_step_99_is_the_one_from_the_record():
    _, dec = _load()
    cur = dec["current"]
    assert cur["yourIndex"] == 1
    us = cur["players"][1]
    assert [c["id"] for c in us["hand"]] == _HAND
    # Their Xerosic's Machinations: three of the six go.
    assert dec["select"]["effect"]["id"] == m.Xerosic_Machinations
    assert dec["select"]["effect"]["playerIndex"] == 0
    assert dec["select"]["minCount"] == dec["select"]["maxCount"] == 3
    # Their Neutralization Zone is the stadium on the field.
    assert [s["id"] for s in cur["stadium"]] == [m.Neutralization_Zone]
    assert cur["stadium"][0]["playerIndex"] == 0
    # Our bench is FULL: the second Ogerpon ex has nowhere to sit, and one is
    # already on it.
    assert len(us["bench"]) == us["benchMax"] == 5
    assert m.Teal_Mask_Ogerpon_ex in [b["id"] for b in us["bench"]]


def test_not_one_body_of_theirs_carries_a_rule_box():
    """Which is why the Zone muted every ex we had: the Forest was the only out."""
    _, dec = _load()
    them = dec["current"]["players"][0]
    for body in them["active"] + them["bench"]:
        data = m.card_table.get(body["id"])
        assert data is not None
        assert not (getattr(data, "ex", False) or getattr(data, "megaEx", False))


# ---------------------------------------------------------------------------
# 2. The rules
# ---------------------------------------------------------------------------

def test_the_forced_discard_keeps_one_forest_of_vitality():
    discarded, _ = _discarded_ids()
    assert discarded.count(FOREST) == 1, (
        "with a hostile Neutralization Zone up, the only card that lifts it "
        f"cannot be thrown away wholesale: discarded {discarded}")


def test_the_surplus_forest_is_still_fodder():
    """One copy is the out; the second is a spare and pays the cost."""
    discarded, _ = _discarded_ids()
    assert FOREST in discarded


def test_the_seatless_duplicate_ex_goes_before_the_recovery_cards():
    discarded, _ = _discarded_ids()
    assert OGERPON in discarded, (
        "a second Teal Mask Ogerpon ex with one already in play and a FULL "
        f"bench cannot be played at all: discarded {discarded}")
    assert NS not in discarded
    assert LANA not in discarded


def test_the_whole_discard_is_the_one_the_record_should_have_made():
    discarded, _ = _discarded_ids()
    assert sorted(discarded) == sorted([MEGANIUM, OGERPON, FOREST]), (
        f"expected Meganium + the spare Ogerpon ex + one Forest, got {discarded}")


def test_the_record_choice_is_no_longer_produced():
    """The record threw away Meganium and BOTH Forests (action `[0, 3, 5]`)."""
    _, action = _discarded_ids()
    assert sorted(action) != [0, 3, 5]
