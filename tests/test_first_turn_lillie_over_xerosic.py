"""On our first turn going second the Supporter slot belongs to Lillie's.

Scenario (`records/registro_002_pasos_010_hasta_017.json`, step 11, episode
89633820 vs Alakazam -- WON in spite of this):

    US                                    RIVAL (Alakazam)
    active  Fezandipiti ex 210 (1 energy)  active  Abra 60
    bench   --                             bench   Abra (1 energy), Abra, Abra
    hand    Ultra Ball, **Xerosic's Machinations**,
            Lillie's Determination, Lillie's Determination,
            Meganium, Meganium
    turn 2, they went first: OUR first turn, the Supporter is still free

The agent spent the turn's Supporter on Xerosic. The opponent went down from 5
cards to 3 -- and one of the two discarded happened to be an Alakazam ex, which
is what makes the play look good in the log and is pure luck: Xerosic discards
at random from a hand we cannot see. Then the Ultra Ball paid its cost with BOTH
Lillie's, and the turn ended with a hand of two Meganium, an empty board and the
whole draw engine in the discard pile.

Rule (user): **on our first turn, going second, Lillie's Determination has
priority over Xerosic's Machinations.** The exception is Xerosic being the only
Supporter we can reach -- no Lillie's in hand and no fetch that brings one.

Why the calendar decides here and not the matchup. Lillie's is at its maximum on
exactly this turn: with all six prizes untouched it draws EIGHT, and the board it
draws into is a lone active with an empty bench, so every basic, every energy and
every Ultra Ball it turns up has somewhere to go. Xerosic is at its minimum: the
opponent has just opened, their hand is the smallest it will ever be, and
Powerful Hand (20 x card in their hand) is not aimed at anything yet -- there is
no Alakazam in play on turn 2 and cannot be, since a Stage 2 cannot land on a
body played the same turn. Discarding cards from an opening hand only makes room
for the opponent to redraw them; the cap earns its Supporter later, once their
hand is inflated AND the Alakazam that punishes it is on the board.

Why no existing rule caught it. Both of the other Supporters that compete for
this turn ALREADY yield: Boss's Orders through `_boss_first_turn_yields` (a gust
takes no prize on the first turn) and Lillie's own `first_turn_always` scores
5000 unconditionally. Xerosic was the one Supporter with no first-turn clause, so
`alakazam_cap_the_hand` fired at 5950 and outbid the refill. The nearest existing
guard, `alakazam_yields_to_lillie_tiny_opponent_hand`, needs the opposing hand at
<= 4; here it was 5, and it is gated on the opposing hand rather than on the
turn, which is the wrong axis for this mistake.

The second exception is structural, not strategic. `do_not_shuffle_the_last_xerosic`
already vetoes Lillie's when playing it would shuffle our LAST Xerosic into the
deck with no way to re-search it. If Xerosic also yielded there, both would sit
at -1 and the Supporter slot would go unused -- the mutual-yield failure already
measured between Lillie's and Boss's
([[lillie-boss-se-ceden-el-turno-asimetria]]). The two rules therefore read the
SAME predicate, `_xr_last_copy_locked_in_hand`.

Implementation: `_xr_first_turn_yields_to_lillie` + the rule
`first_turn_yields_to_lillie` in `ptcg/decision/disruption.py`.
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
            / "alakazam_t1_going_second_lillie_over_xerosic_step11.json")

LILLIE = m.Lillie_Determination
XEROSIC = m.Xerosic_Machinations
ULTRA_BALL = m.Ultra_Ball
MEOWTH = m.Meowth_ex
MEGANIUM = m.Meganium


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    yield
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _idx_play(obs, card_id):
    """Index of the 'PLAY <card_id>' option in the main menu, or -1."""
    cur = obs["current"]
    hand = cur["players"][cur["yourIndex"]]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.PLAY) and hand[o["index"]]["id"] == card_id:
            return i
    return -1


class _Ctx:
    """The minimum `_xr_first_turn_yields_to_lillie` consults.

    The predicate reads the calendar, the hand and the fetch routes and nothing
    else, so the boundaries can be pinned without building a board. Same stub
    style as `tests/test_ultra_ball_does_not_burn_xerosic.py`.
    """

    def __init__(self, hand, deck=None, *, our_first_turn=True,
                 we_go_first=False, supporter_played=False, bench_count=0,
                 field=None, op_hand=5, alakazam=True,
                 meowth_ability_lock=False, meowth_ld_free=True):
        self.hand_counts = dict(hand)
        self.cards_in_deck = {cid: {m.ZONE_DECK: n} for cid, n in (deck or {}).items()}
        self.field_counts = dict(field or {})
        self.bench_count = bench_count
        self.our_first_turn = our_first_turn
        self.we_go_first = we_go_first
        self.op_hand_count = op_hand
        self.op_is_alakazam_deck = alakazam
        self.meowth_ability_lock = meowth_ability_lock
        self.meowth_ld_free = meowth_ld_free
        self.state = type("S", (), {"supporterPlayed": supporter_played,
                                    "turn": 2})()


# ---------------------------------------------------------------------------
# 1. The record: the scenario, and then the decision
# ---------------------------------------------------------------------------

def test_the_fixture_is_our_first_turn_going_second_with_both_supporters():
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]

    assert cur["turn"] == 2 and cur["firstPlayer"] != cur["yourIndex"], (
        "el escenario es NUESTRO primer turno saliendo segundos")
    assert cur["supporterPlayed"] is False, "el Supporter del turno sigue libre"
    assert [c["id"] for c in mine["hand"]] == [
        ULTRA_BALL, XEROSIC, LILLIE, MEGANIUM, MEGANIUM, LILLIE]
    assert cur["players"][1 - cur["yourIndex"]]["handCount"] == 5, (
        "mano rival de 5: fuera del veto por mano rival minima (<= 4)")
    assert _idx_play(o, XEROSIC) >= 0 and _idx_play(o, LILLIE) >= 0, (
        "el paso ofrecia jugar AMBOS Supporters: el menu mide la prioridad")


def test_the_first_turn_plays_lillie_not_xerosic():
    """The regression of the record: `alakazam_cap_the_hand` scored 5950 and
    outbid the 5000 of Lillie's `first_turn_always`."""
    o = _obs()
    assert m.agent(o) == [_idx_play(o, LILLIE)], (
        "en nuestro primer turno saliendo segundos el Supporter es para "
        "Lillie's Determination (roba OCHO con 6 premios), no para Xerosic")


# ---------------------------------------------------------------------------
# 2. The size of the opposing hand does not buy back the turn
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("op_hand", [5, 7, 9, 12])
def test_no_opposing_hand_makes_the_cap_worth_the_first_turn(op_hand):
    """`alakazam_cap_the_hand` scales with the opposing hand; on this turn none
    of its band wins, because the axis is the calendar and not the matchup."""
    o = _obs()
    o["current"]["players"][1 - o["current"]["yourIndex"]]["handCount"] = op_hand
    assert m.agent(o) == [_idx_play(o, LILLIE)]


def test_off_the_first_turn_the_cap_takes_the_supporter_again():
    """The other side of the boundary: the rule only speaks for one turn. With
    the same hand on turn 4 the opposing board is real and Xerosic wins."""
    o = _obs()
    o["current"]["turn"] = 4
    o["current"]["players"][1 - o["current"]["yourIndex"]]["handCount"] = 9
    assert m.agent(o) == [_idx_play(o, XEROSIC)]


# ---------------------------------------------------------------------------
# 3. The exceptions, on the predicate
# ---------------------------------------------------------------------------

def test_the_lillie_in_hand_is_the_common_route():
    assert m._xr_first_turn_yields_to_lillie(
        _Ctx({XEROSIC: 1, LILLIE: 1}, {XEROSIC: 1}))


def test_the_only_supporter_with_no_fetch_keeps_the_turn():
    """The user's exception: no Lillie's in hand and nothing that brings one --
    Xerosic is the whole Supporter slot, so it is played."""
    assert not m._xr_first_turn_yields_to_lillie(
        _Ctx({XEROSIC: 1}, {LILLIE: 2}))


def test_the_meowth_fetch_counts_as_a_route_from_hand():
    """Meowth ex's Last-Ditch Catch searches for a Supporter: with the Meowth in
    hand and Lillie's in the deck there IS a route, so Xerosic waits."""
    assert m._xr_first_turn_yields_to_lillie(
        _Ctx({XEROSIC: 1, MEOWTH: 1}, {LILLIE: 2}))


def test_the_meowth_fetch_counts_as_a_route_through_the_ultra_ball():
    """The full chain: Ultra Ball digs out the Meowth, the Meowth fetches the
    Lillie's."""
    assert m._xr_first_turn_yields_to_lillie(
        _Ctx({XEROSIC: 1, ULTRA_BALL: 1}, {LILLIE: 2, MEOWTH: 2}))


def test_no_route_without_a_lillie_left_in_the_deck():
    """A Meowth with nothing to fetch is not a route."""
    assert not m._xr_first_turn_yields_to_lillie(
        _Ctx({XEROSIC: 1, MEOWTH: 1}, {}))


@pytest.mark.parametrize("kwargs", [
    {"meowth_ability_lock": True},          # Watchtower / Iron Thorns
    {"meowth_ld_free": False},              # the Last-Ditch of the turn is spent
    {"bench_count": 5},                     # nowhere to put the Meowth
    {"field": {MEOWTH: 2}},                 # both copies already down
])
def test_the_fetch_route_needs_the_last_ditch_to_be_real(kwargs):
    assert not m._xr_first_turn_yields_to_lillie(
        _Ctx({XEROSIC: 1, MEOWTH: 1}, {LILLIE: 2}, **kwargs))


def test_going_first_there_is_no_slot_to_argue_over():
    """The player going first may not play a Supporter on their first turn."""
    assert not m._xr_first_turn_yields_to_lillie(
        _Ctx({XEROSIC: 1, LILLIE: 1}, {XEROSIC: 1}, we_go_first=True))


def test_off_the_first_turn_the_predicate_is_silent():
    assert not m._xr_first_turn_yields_to_lillie(
        _Ctx({XEROSIC: 1, LILLIE: 1}, {XEROSIC: 1}, our_first_turn=False))


def test_with_the_supporter_already_spent_there_is_nothing_to_yield():
    assert not m._xr_first_turn_yields_to_lillie(
        _Ctx({XEROSIC: 1, LILLIE: 1}, {XEROSIC: 1}, supporter_played=True))


# ---------------------------------------------------------------------------
# 4. The structural exception: the two rules may not yield to each other
# ---------------------------------------------------------------------------

def test_the_last_xerosic_is_played_instead_of_being_shuffled_away():
    """`do_not_shuffle_the_last_xerosic` vetoes the Lillie's here (it would send
    our only access to the cap into the deck). If Xerosic yielded as well, the
    turn's Supporter would go unplayed."""
    locked = _Ctx({XEROSIC: 1, LILLIE: 1}, {LILLIE: 1})   # no 2nd Xerosic, no Meowth
    assert m._xr_last_copy_locked_in_hand(locked), "el escenario no mide nada"
    assert not m._xr_first_turn_yields_to_lillie(locked)


def test_a_second_copy_in_the_deck_unlocks_the_yield():
    """With a copy left to draw, shuffling the one in hand loses nothing: the
    Lillie's veto lifts and so does Xerosic's guard. It is the case of the
    record."""
    spare = _Ctx({XEROSIC: 1, LILLIE: 1}, {XEROSIC: 1, LILLIE: 1})
    assert not m._xr_last_copy_locked_in_hand(spare)
    assert m._xr_first_turn_yields_to_lillie(spare)
