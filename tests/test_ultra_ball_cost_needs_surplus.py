"""The Ultra Ball's two discards have to come out of SURPLUS.

Scenario (`records/registro_004_pasos_045_hasta_052.json`, step 48, episode
89624781 vs Dragapult ex -- WON in spite of this):

    US (6 prizes)                          OPPONENT (6 prizes)
    active  Teal Mask Ogerpon ex, 1 {G}    active  Dreepy 70
    bench   Teal Mask Ogerpon ex, 2 {G}    bench   Drakloak 90
            **Applin 40**
            Teal Mask Ogerpon ex, 1 {G}
    hand    Unfair Stamp, Meowth ex, Ultra Ball, **Hydrapple ex**
    the turn's Supporter: already spent

The agent played the Ultra Ball. Its cost of two could not touch the Unfair
Stamp (-10000, never discarded), so it took THE OTHER TWO cards, whatever they
were: the Meowth ex and the Hydrapple ex. What it fetched was a Dipplin -- the
intermediate piece of the line Applin -> Dipplin -> Hydrapple ex, that is, the
missing link of the very line whose Stage 2 it had just thrown in the bin.

The discard scorer was not the problem. It prices the Hydrapple ex at 3 and the
Meowth ex at 2 -- both protected, both KEPT before anything else -- and the
prompt still demanded exactly two of the three cards. The mistake was upstream:
playing an Ultra Ball at all out of a hand with nothing to spare.

Why nothing spoke. Every cost veto of the family protects ONE named card and
counts the real fodder around it: `_ub_cancel_lillie`, `_ub_cancel_xerosic`,
`_ub_cancel_meowth`, `_ub_cancel_stamp`, `_ub_cancel_fez`. The first three go
blind once the turn's Supporter is spent, which it was; `_ub_cancel_tomorrow_supporter`
covers a hand of three but only names Supporters, and neither the Meowth ex nor
the Hydrapple ex is one. Here the two cards that would pay were protected for
DIFFERENT reasons and no single one of them was "the" card at stake -- and that
is exactly a hand with no surplus, which is what the whole family exists for.

`_ub_cancel_no_surplus` states it with no card to name: fewer than two cards the
DISCARD scorer would really let go and the Ultra Ball is not played. The
arithmetic is `_ub_real_fodder`, the one the rest of the family already shares.

The spare copies of the Ultra Ball are added back. `_ub_real_fodder` skips every
Ultra Ball in hand -- for the vetoes it was written for, the card being played
must not pay its own cost -- but only one copy is played, and a duplicate is the
best fodder in the hand (the discard scorer prices it at 95). Without that,
holding two Ultra Balls plus one protected card was a false cancel; it was
measured on the first pass and it is pinned below.
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
            / "dragapult_t4_ultra_ball_without_surplus_step48.json")

ULTRA_BALL = m.Ultra_Ball
HYDRAPPLE = m.Hydrapple_ex
MEOWTH = m.Meowth_ex
STAMP = m.Unfair_Stamp
APPLIN = m.Applin
GRASS = m.Basic_Grass_Energy


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _idx_play(obs, card_id):
    cur = obs["current"]
    hand = cur["players"][cur["yourIndex"]]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.PLAY) and hand[o["index"]]["id"] == card_id:
            return i
    return -1


def _idx_type(obs, t):
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(t):
            return i
    return -1


class _Ctx:
    """The minimum `_ub_cancel_no_surplus` consults: it reads the hand, the
    board and the deck through `_ub_real_fodder` and nothing else."""

    def __init__(self, hand, field=None, *, bench_count=3,
                 supporter_played=False, ko_last_turn=False,
                 has_hydrapple=False, forest_in_play=False, deck=None):
        self.hand_counts = dict(hand)
        self.field_counts = dict(field or {})
        self.bench_count = bench_count
        self.ko_last_turn = ko_last_turn
        self.op_is_crustle_deck = False
        self.op_has_ex_immune_active = False
        self.op_has_ex_immune_bench = False
        self.has_hydrapple = has_hydrapple
        self.forest_in_play = forest_in_play
        self.meganium_in_play = False
        self.cards_in_deck = {cid: {m.ZONE_DECK: n} for cid, n in (deck or {}).items()}
        self.state = type("S", (), {"supporterPlayed": supporter_played})()
        # `_ub_cancel_tomorrow_supporter` measures the hand by its length.
        self.my_state = type("M", (), {
            "hand": [None] * sum(hand.values())})()


# ---------------------------------------------------------------------------
# 1. The record: the scenario, and then the decision
# ---------------------------------------------------------------------------

def test_the_fixture_is_a_hand_with_nothing_to_spare():
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]

    assert [c["id"] for c in mine["hand"]] == [STAMP, MEOWTH, ULTRA_BALL, HYDRAPPLE]
    assert cur["supporterPlayed"] is True, (
        "el Supporter del turno ya esta gastado: los vetos de coste que lo "
        "exigen libre estan ciegos")
    assert any(b["id"] == APPLIN for b in mine["bench"]), (
        "el Applin en banca es lo que PROTEGE al Hydrapple ex en el descartador")
    assert _idx_play(o, ULTRA_BALL) >= 0, "el paso ofrecia jugar la Ultra Ball"


def test_the_ultra_ball_is_not_played_when_its_cost_eats_the_line():
    """The regression of the record: it paid with the Meowth ex and the
    Hydrapple ex to fetch the Dipplin of that same line."""
    o = _obs()
    assert m.agent(o) != [_idx_play(o, ULTRA_BALL)], (
        "sin forraje real, el coste de la Ultra Ball sale de las cartas que el "
        "propio descartador esta protegiendo")


def test_with_nothing_else_to_do_the_turn_simply_ends():
    """The two cards are kept. Ending is not the goal -- it is what is left once
    the Ultra Ball stops being worth its cost."""
    o = _obs()
    assert m.agent(o) == [_idx_type(o, m.OptionType.END)]


# ---------------------------------------------------------------------------
# 2. The arithmetic, on the predicate
# ---------------------------------------------------------------------------

def test_the_record_hand_has_no_surplus():
    """Unfair Stamp is never discarded, the Hydrapple ex is protected by the
    Applin in play and the Meowth ex is protected while it can still be
    benched: zero real fodder."""
    assert m._ub_cancel_no_surplus(
        _Ctx({STAMP: 1, MEOWTH: 1, ULTRA_BALL: 1, HYDRAPPLE: 1},
             {APPLIN: 1}, supporter_played=True))


def test_two_spare_cards_are_enough():
    assert not m._ub_cancel_no_surplus(
        _Ctx({ULTRA_BALL: 1, GRASS: 2}, {APPLIN: 1}))


def test_one_spare_card_is_not():
    assert m._ub_cancel_no_surplus(
        _Ctx({ULTRA_BALL: 1, GRASS: 1, HYDRAPPLE: 1}, {APPLIN: 1}))


def test_a_second_ultra_ball_counts_as_fodder():
    """Measured on the first pass: `_ub_real_fodder` skips EVERY Ultra Ball, so
    the spare copies vanished from the count and hands that could pay perfectly
    well were cancelled. Only the copy being played does not pay its own cost.
    Same hand, same protected Hydrapple ex, one Ultra Ball apart."""
    two_balls = _Ctx({ULTRA_BALL: 2, GRASS: 1, HYDRAPPLE: 1}, {APPLIN: 1})
    assert not m._ub_cancel_no_surplus(two_balls)
    one_ball = _Ctx({ULTRA_BALL: 1, GRASS: 1, HYDRAPPLE: 1}, {APPLIN: 1})
    assert m._ub_cancel_no_surplus(one_ball)


def test_the_spare_copy_is_only_worth_one_card():
    """Two Ultra Balls and a protected Stage 2 still cancel: playing one leaves
    the other Ultra Ball AND the Hydrapple ex to pay the two discards."""
    assert m._ub_cancel_no_surplus(
        _Ctx({ULTRA_BALL: 2, HYDRAPPLE: 1}, {APPLIN: 1}))


def test_an_evolution_piece_with_no_pre_evolution_in_play_is_fodder():
    """The protection is not the card, it is the board: a Hydrapple ex with no
    Applin and no Dipplin anywhere is an ordinary card and pays."""
    assert not m._ub_cancel_no_surplus(
        _Ctx({ULTRA_BALL: 1, HYDRAPPLE: 2}, {}))


def test_it_lives_in_the_cost_family():
    """`_ub_cost_destroys_better_card` is what the rescues that resurrect vetoed
    Ultra Balls consult; a cost veto that stayed outside it would be revoked by
    the first sterile turn."""
    no_surplus = _Ctx({STAMP: 1, MEOWTH: 1, ULTRA_BALL: 1, HYDRAPPLE: 1},
                      {APPLIN: 1}, supporter_played=True)
    assert m._ub_cost_destroys_better_card(no_surplus)
