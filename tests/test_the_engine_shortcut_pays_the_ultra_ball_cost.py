"""The engine shortcuts of the Ultra Ball pay the same cost toll as everyone else.

Scenario (`records/registro_006_pasos_066_hasta_076.json`, step 68 = turn 6
action 3, episode 92863087 vs Alakazam -- LOST):

    US (6 prizes)                        OPPONENT (4 prizes)
    active  Teal Mask Ogerpon ex, 2 {G}  active  Teal Mask Ogerpon ex 210
    bench   Meowth ex (Last-Ditch free)  hand    8 cards
    hand    Boss's Orders, ULTRA BALL, UNFAIR STAMP
    our Dipplin was knocked out on their turn -> the Stamp is legal TODAY

        [0] Boss's Orders    -1   `yields_to_unfair_stamp` -- the Boss's DOES yield
        [2] Unfair Stamp   3100
        [1] Ultra Ball     5950                                       <-- played

The cost of two came out of a hand of three: Boss's Orders and the Unfair Stamp
into the discard pile, to dig out a second Meowth ex whose Last-Ditch fetched
Xerosic's Machinations. The Stamp is an ACE SPEC, one copy, unrecoverable by
this list, and legal ONLY on the turn after a knock-out -- it was burned on the
one turn it could be played. Xerosic left the opponent the three cards THEY
chose; the Stamp leaves them two at random, refills us to five and does not
spend the turn's Supporter (it is an Item).

WHY NOTHING SPOKE, and it was not for want of a rule. On this board
`_ub_cancel_stamp` and `_ub_cancel_no_surplus` are BOTH True. Neither ran: they
live in `_ub_score_before_overrides`, and `_alakazam_dig_xerosic_engine`
returns 5950 ABOVE it. The shortcut names what the Ultra Ball buys and never
what it costs.

The two protections that do exist are both downstream of the destruction:
  * the discard scorer prices Unfair Stamp at -10000 -- but the prompt it
    answers is `minCount=2` over the two cards left, a FORCED menu;
  * `the_stamp_shuffles_the_last_ditch_supporter` refuses to buy a body under a
    pending Stamp -- but by the time the fetch is asked, the Stamp is discarded.

So the fix is at the PLAY decision, in `_ub_engine_cost_bites`, and it is the
generic form: every engine shortcut asks the same eight cost questions the
ordinary route asks. It is a predicate and not a score because the ordinary
pipeline still has the last word -- `_ub_terminal_overrides` can lift a
cost-vetoed Ultra Ball back up in survival mode, and it must keep being able to.
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
from ptcg.decision.disruption import _stamp_pendiente

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_t6_the_engine_shortcut_eats_the_stamp_step68.json")

ULTRA_BALL = m.Ultra_Ball
STAMP = m.Unfair_Stamp
BOSS = m.Boss_Orders
MEOWTH = m.Meowth_ex
XEROSIC = m.Xerosic_Machinations
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


class _Ctx:
    """The fields the eight cost vetoes read, and nothing else."""

    def __init__(self, hand, field=None, *, bench_count=1,
                 supporter_played=False, ko_last_turn=True, deck=None):
        self.hand_counts = dict(hand)
        self.field_counts = dict(field or {})
        self.bench_count = bench_count
        self.ko_last_turn = ko_last_turn
        self.op_is_crustle_deck = False
        self.op_has_ex_immune_active = False
        self.op_has_ex_immune_bench = False
        self.has_hydrapple = False
        self.forest_in_play = False
        self.meganium_in_play = False
        self.cards_in_deck = {cid: {m.ZONE_DECK: n} for cid, n in (deck or {}).items()}
        self.state = type("S", (), {"supporterPlayed": supporter_played})()
        self.my_state = type("M", (), {"hand": [None] * sum(hand.values())})()


# ---------------------------------------------------------------------------
# 1. The board of the record
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_turn_the_stamp_was_legal():
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert [c["id"] for c in mine["hand"]] == [BOSS, ULTRA_BALL, STAMP]
    assert theirs["handCount"] == 8, (
        "su mano inflada es lo que arma el motor de Xerosic vs Alakazam")
    assert len(mine["prize"]) == 6 and len(theirs["prize"]) == 4, (
        "vamos por detras: el relleno de 5 cartas del Stamp es lo que "
        "necesita este tablero")
    assert _idx_play(o, STAMP) >= 0, (
        "el motor ofrecia el Unfair Stamp: nos mataron en su turno")
    assert _idx_play(o, ULTRA_BALL) >= 0


def test_the_cost_would_be_the_whole_hand():
    """Three cards: the Ultra Ball does not pay its own cost, so the two
    discards are the Boss's Orders and the Stamp. Nothing else exists."""
    o = _obs()
    cur = o["current"]
    assert len(cur["players"][cur["yourIndex"]]["hand"]) == 3


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_stamp_is_played_instead_of_the_ultra_ball():
    o = _obs()
    assert m.agent(o) == [_idx_play(o, STAMP)], (
        "el Unfair Stamp es la jugada: 2 cartas al azar para el rival, 5 para "
        "nosotros, y sin gastar la ranura de Supporter")


def test_the_ultra_ball_is_not_the_choice():
    """The regression of the record, stated as its own sentence: whatever else
    the turn does, it does not burn the Stamp as fodder."""
    o = _obs()
    assert m.agent(o) != [_idx_play(o, ULTRA_BALL)]


# ---------------------------------------------------------------------------
# 3. The predicate: WHICH rule decided, not which number came out
# ---------------------------------------------------------------------------

def test_the_price_bites_on_the_record_hand():
    ctx = _Ctx({BOSS: 1, ULTRA_BALL: 1, STAMP: 1},
               {MEOWTH: 1}, deck={MEOWTH: 1, XEROSIC: 1})
    assert m._ub_engine_cost_bites(ctx) is True
    assert m._ub_cancel_stamp(ctx) is True, "el Stamp no tiene con que pagarse"
    assert m._ub_cancel_no_surplus(ctx) is True, "no hay forraje real ninguno"


def test_the_price_does_not_bite_with_real_fodder_next_to_the_stamp():
    """The toll is about the COST, not about the Stamp: with two spare cards
    beside it the Ultra Ball pays without touching it and the engine runs."""
    ctx = _Ctx({BOSS: 1, ULTRA_BALL: 1, STAMP: 1, GRASS: 2},
               {MEOWTH: 1}, deck={MEOWTH: 1, XEROSIC: 1})
    assert m._ub_engine_cost_bites(ctx) is False


def test_the_stamp_is_pending_on_this_board_and_the_boss_already_yielded():
    """The contradiction the toll removes: within ONE decision the Boss's
    ladder stepped aside for the Stamp while the Ultra Ball ate it. Both sides
    now read the same board."""
    o = _obs()
    seen = {}
    orig = m._alakazam_dig_xerosic_engine

    def spy(c):
        seen.setdefault("stamp_pendiente", _stamp_pendiente(c))
        seen.setdefault("cost_bites", m._ub_engine_cost_bites(c))
        return orig(c)

    m._alakazam_dig_xerosic_engine = spy
    try:
        m.agent(o)
    finally:
        m._alakazam_dig_xerosic_engine = orig

    assert seen.get("stamp_pendiente") is True
    assert seen.get("cost_bites") is True
