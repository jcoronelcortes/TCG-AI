"""Unfair Stamp: one card denied is not disruption, and it is not worth the
last Xerosic.

Scenario (`records/registro_006_pasos_075_hasta_103.json`, episode 90092191,
step 88, turn 6 vs Alakazam, LOST):

    US                                        RIVAL
    active  Ogerpon ex, 3 Grass               active  Alakazam 140/140, 1 energy
    bench   Ogerpon ex, Ogerpon ex,           bench   Kadabra, Kadabra,
            Dipplin, Meowth ex                        **Fezandipiti ex**, x2
    hand    **Unfair Stamp**, **Xerosic**,    hand    **3 cards**
            1 Grass
    supporter of the turn: SPENT              (Xerosic capped them 14 -> 3
    energy of the turn: ATTACHED               the action before)

The menu offered exactly four things: play the Stamp, attack, retreat, end. The
agent played the Stamp, and the three clauses it paid for all read against it:

  * DISRUPTION. The Stamp leaves them at 2, so on a hand of 3 it denies ONE
    card -- and their Fezandipiti ex draws three back with Flip the Script on
    the turn after we take a KO, which is the turn the Stamp is played by
    definition (the card needs one of OUR bodies to have been knocked out).
  * REFILL. It shuffled our hand -- and with it the SECOND Xerosic, the deck's
    only remaining copy (both were drawn, zero left in the deck). Against
    Powerful Hand (20 x card in their hand) that is the answer, and it never
    came back: two Bug Catching Sets dug fourteen cards afterwards without
    finding it.
  * And the turn did not need any of it: Myriad Leaf Shower was already lethal
    on their active, 30 + 30 x (3 own + 1 theirs) = 150 on a 140 HP body. The
    line actually played spent the ACE SPEC, two Bug Catching Sets, the
    evolution to Hydrapple ex and a retreat that DISCARDED an energy, to land
    the same knock out.

Hence the two clauses added to `_stamp_worth_playing` (user, August 2026):
`STAMP_MIN_OP_HAND` rises to 4 (two cards denied), 6 when their board carries a
refill engine, and the refill clause no longer buys five cards with the last
Xerosic.
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
            / "alakazam_t6_the_stamp_does_not_bury_the_last_xerosic_step88.json")

STAMP = m.Unfair_Stamp
XEROSIC = m.Xerosic_Machinations
GRASS = m.Basic_Grass_Energy


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
    previa, dec = _load()
    m.agent(previa)          # it brings the KO window of the opposing turn
    return m.agent(dec)


# ---------------------------------------------------------------------------
# 1. The record: the board that produced the mistake
# ---------------------------------------------------------------------------

def test_the_menu_of_step_88_is_the_one_from_the_record():
    _, dec = _load()
    cur = dec["current"]
    yo = cur["yourIndex"]
    mine, op = cur["players"][yo], cur["players"][1 - yo]

    assert [c["id"] for c in mine["hand"]] == [STAMP, XEROSIC, GRASS]
    assert op["handCount"] == 3
    assert cur["supporterPlayed"] is True and cur["energyAttached"] is True
    # play the Stamp / attack / retreat / end
    assert [o["type"] for o in dec["select"]["option"]] == [
        int(m.OptionType.PLAY), int(m.OptionType.ATTACK),
        int(m.OptionType.RETREAT), int(m.OptionType.END)]
    # their board carries BOTH reasons: the Powerful Hand line and the refill engine
    bodies = [p["id"] for p in op["active"]] + [p["id"] for p in op["bench"]]
    assert m.Alakazam_ex in bodies and m.Kadabra in bodies
    assert m.Fezandipiti_ex in bodies


def test_the_stamp_is_no_longer_played_at_step_88():
    choice = _decision()
    assert choice != [0], (
        "option 0 is PLAY of the Unfair Stamp: with the rival at 3 cards it "
        "denies ONE, their Fezandipiti ex draws three back, and it buries our "
        f"last Xerosic; eligio {choice}")


def test_the_last_xerosic_really_is_the_last_one():
    """The veto's premise, read off the record: both copies had been drawn (one
    played, one in hand) so the deck had none left."""
    _, dec = _load()
    cur = dec["current"]
    yo = cur["yourIndex"]
    mine = cur["players"][yo]
    en_mano = [c["id"] for c in mine["hand"]].count(XEROSIC)
    en_descarte = [c["id"] for c in mine["discard"]].count(XEROSIC)
    assert en_mano == 1 and en_descarte == 1


# ---------------------------------------------------------------------------
# 2. The clauses, one by one
# ---------------------------------------------------------------------------

def _op_board(*ids):
    """Their board as the predicates read it: active + bench."""
    return SimpleNamespace(
        active=[SimpleNamespace(id=ids[0], preEvolution=[])] if ids else [],
        bench=[SimpleNamespace(id=i, preEvolution=[]) for i in ids[1:]])


def test_one_card_denied_is_not_disruption():
    """The Stamp leaves them at 2: the floor is now 2 cards denied."""
    big_hand = m.STAMP_MAX_HAND_SACRIFICED + 5
    assert not m._stamp_worth_playing(3, big_hand)      # denies 1
    assert m._stamp_worth_playing(4, big_hand)          # denies 2


def test_a_refill_engine_on_their_board_raises_the_floor():
    big_hand = m.STAMP_MAX_HAND_SACRIFICED + 5
    for op_hand in range(4, m.STAMP_MIN_OP_HAND_VS_REFILL):
        assert not m._stamp_worth_playing(op_hand, big_hand,
                                          op_refill_engine=True), op_hand
    assert m._stamp_worth_playing(m.STAMP_MIN_OP_HAND_VS_REFILL, big_hand,
                                  op_refill_engine=True)


def test_the_refill_does_not_pay_for_the_last_xerosic():
    """A cheap refill (we sacrifice <= 4) no longer passes if what it buries is
    the last Xerosic; a big opposing hand still does."""
    assert m._stamp_worth_playing(2, 3)
    assert not m._stamp_worth_playing(2, 3, buries_the_last_xerosic=True)
    assert m._stamp_worth_playing(12, 3, buries_the_last_xerosic=True)


def test_the_board_predicates_read_the_board():
    assert m._op_refill_engine(_op_board(m.Alakazam_ex, m.Fezandipiti_ex))
    assert not m._op_refill_engine(_op_board(m.Alakazam_ex, m.Kadabra))
    assert m._op_powerful_hand_line(_op_board(m.Kadabra))
    assert not m._op_powerful_hand_line(_op_board(m.Fezandipiti_ex))
    # the pre-evolution of a stack counts too
    apilado = SimpleNamespace(
        active=[SimpleNamespace(id=999, preEvolution=[SimpleNamespace(id=m.Abra)])],
        bench=[])
    assert m._op_powerful_hand_line(apilado)
    # with no board neither of them invents anything
    assert not m._op_refill_engine(None)
    assert not m._op_powerful_hand_line(None)


def test_the_bury_veto_needs_all_three_conditions():
    board = _op_board(m.Alakazam_ex)
    sin_mazo = {XEROSIC: {m.ZONE_DECK: 0}}
    assert m._stamp_buries_the_last_xerosic({XEROSIC: 1}, sin_mazo, True, board)
    # ...the supporter of the turn is still free: it can be played NOW
    assert not m._stamp_buries_the_last_xerosic({XEROSIC: 1}, sin_mazo, False, board)
    # ...another copy is drawable
    assert not m._stamp_buries_the_last_xerosic(
        {XEROSIC: 1}, {XEROSIC: {m.ZONE_DECK: 1}}, True, board)
    # ...no Xerosic in hand
    assert not m._stamp_buries_the_last_xerosic({}, sin_mazo, True, board)
    # ...no Powerful Hand line on their board: the Xerosic is one more card
    assert not m._stamp_buries_the_last_xerosic(
        {XEROSIC: 1}, sin_mazo, True, _op_board(m.Fezandipiti_ex))


# ---------------------------------------------------------------------------
# 3. A vetoed Stamp does not paralyse the turn
# ---------------------------------------------------------------------------

def test_the_vetoed_stamp_stops_blocking_the_order_of_the_turn():
    """`_stamp_pendiente` is the single source of the ordering vetoes (Boss's,
    Lillie's, Lana's, Dawn, Xerosic, the Meowth chain and Flip the Script): if
    it stayed True the turn would yield the way to a card that is no longer
    going to be played."""
    ctx = SimpleNamespace(
        ko_last_turn=True,
        hand_counts={STAMP: 1, XEROSIC: 1},
        cards_in_deck={XEROSIC: {m.ZONE_DECK: 0}},
        op_hand_count=3,
        my_hand_len=3,
        state=SimpleNamespace(supporterPlayed=True),
        op_state=_op_board(m.Alakazam_ex, m.Fezandipiti_ex))
    assert not m._stamp_worth_playing_ctx(ctx)
    assert not m._stamp_pendiente(ctx)
    assert m._score_unfair_stamp_play(
        SimpleNamespace(**{**ctx.__dict__})) <= 0
