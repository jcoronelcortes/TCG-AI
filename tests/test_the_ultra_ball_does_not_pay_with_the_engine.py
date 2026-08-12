"""The cost of an Ultra Ball ate the cap AND the refill, to fetch a Chikorita.

Scenario (user, `records/registro_006_pasos_062_hasta_085.json`, episode
91851762, step 81, turn 6 vs Alakazam -- LOST):

    US (6 prizes)                          RIVAL (5 prizes, TEN cards in hand)
    active  Tapu Bulu 140/140, NO energy   active  Dipplin 140
    bench   Ogerpon ex x2, Meowth ex,      bench   the Alakazam line
            Hydrapple ex
    hand    Xerosic's Machinations, Dawn,  (our Supporter ALREADY spent)
            Ultra Ball, Lillie's
            Determination

The menu was exactly {play Ultra Ball, end turn}. The Ultra Ball was played, its
two discards were paid with the **Xerosic's Machinations AND the Lillie's
Determination**, and of the whole deck it fetched a **Chikorita** -- a Basic,
benched on a turn that could not attack at all. The turn ended holding {Dawn,
Chikorita}, with the cap on a 240-damage Powerful Hand in the discard pile and
no refill left in hand.

CARD RULE, as stated by the user: an Ultra Ball NEVER discards a Xerosic's
Machinations or a Lillie's Determination, unless the Pokemon it is searching for
wins the game.

WHY NOTHING SPOKE. Three vetoes already protect exactly these two cards
(`_ub_cancel_xerosic`, `_ub_cancel_lillie`, `_ub_cancel_meowth`) and all three
open with `not state.supporterPlayed`: they were written to settle a competition
for TODAY'S Supporter slot, so once that slot is spent the whole family goes
blind. `_ub_cancel_tomorrow_supporter` exists for precisely that blindness and
is bounded at a hand of three; this hand had four. One card outside every net.

AND A SECOND HOLE, INDEPENDENT OF THE FIRST. `_ub_real_fodder` is asked about
ONE protected card at a time, so with both Supporters in hand each of them was
the other's proof that nothing was being burnt: `prot=Xerosic` counted the
Lillie's as fodder, `prot=Lillie's` counted the Xerosic. That is why
`_ub_cancel_engine_supporters` protects them as a SET -- and why `_ub_real_fodder`
now takes a collection.

WHAT IT IS NOT. It is not conservatism about Ultra Balls. It fires only when the
two discards cannot be found among the REST of the hand -- the same arithmetic
as the family it joins -- so a hand with two spare cards plays its Ultra Ball and
keeps the engine, both.

WHICH XEROSIC. A cap with nothing to cap is cardboard, and this is the measured
boundary (`tests/test_the_spare_stage_two_pays_the_ultra_ball.py`, registro_002
step 26 vs Marnie): there a dead Xerosic and a spare Stage 2 pay for the search
that opens the turn, and protecting it would have cancelled it. So the Xerosic
counts as engine only on the boards where the play scorer would spend a
Supporter on it -- `_xr_gate_alakazam`, or any deck with their hand at
`XEROSIC_BIG_HAND`. Both are readings of the BOARD, which is why they can be
asked here at all: unlike `_score_xerosic_play` they do not go silent the moment
this turn's Supporter is spent, and the turn after that one is the whole point.
The Lillie's needs no such test: this deck has no board on which drawing a fresh
hand is worth nothing.

THE EXCEPTION IS THE ONE THE USER NAMED: `plan_of(ctx).wins_this_turn`, the
project's own answer to "is there a lethal route today". A game that ends this
turn has no next turn to keep a Supporter for.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from ptcg.cards import ids
from ptcg.turn.game_plan import NO_PLAN, ROUTE_ACTIVE

XEROSIC = m.Xerosic_Machinations
LILLIE = m.Lillie_Determination
DAWN = m.Dawn
ULTRA_BALL = m.Ultra_Ball
MEGANIUM = m.Meganium
BAYLEEF = m.Bayleef
CHIKORITA = m.Chikorita
GRASS = m.Basic_Grass_Energy

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_step81_the_cost_does_not_eat_the_engine.json")


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


def _record_obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _hand_ids(obs):
    yo = obs["current"]["yourIndex"]
    return [c["id"] for c in obs["current"]["players"][yo]["hand"]]


def _chosen(obs, choice):
    return obs["select"]["option"][choice[0]]


class _State:
    def __init__(self, supporter_played):
        self.supporterPlayed = supporter_played


class _MyState:
    def __init__(self, hand_len, bench_max=5):
        self.hand = [None] * hand_len
        self.benchMax = bench_max


class _Ctx:
    """The fields `_ub_cancel_engine_supporters` and `_ub_real_fodder` read.

    `turn_plan` is left unset on purpose in most cases: `plan_of` answers
    `NO_PLAN` for a context without one, which is the "no lethal route" case."""

    def __init__(self, hand_counts, *, op_hand_count=10,
                 op_is_alakazam_deck=True, supporter_played=True,
                 field_counts=None, bench_count=2, turn_plan=None):
        self.hand_counts = hand_counts
        self.op_hand_count = op_hand_count
        self.op_is_alakazam_deck = op_is_alakazam_deck
        self.state = _State(supporter_played)
        self.my_state = _MyState(sum(hand_counts.values()))
        self.field_counts = field_counts if field_counts is not None else {}
        self.bench_count = bench_count
        self.ko_last_turn = False
        self.op_is_crustle_deck = False
        self.op_has_ex_immune_active = False
        self.op_has_ex_immune_bench = False
        self.has_hydrapple = False
        self.forest_in_play = False
        # Read by the sibling vetoes of the same family, so that the whole of
        # `_ub_cost_destroys_better_card` can be asked about this board.
        self.meganium_in_play = False
        self.cards_in_deck = {}
        if turn_plan is not None:
            self.turn_plan = turn_plan


_RECORD_HAND = {XEROSIC: 1, DAWN: 1, ULTRA_BALL: 1, LILLIE: 1}


# ---------------------------------------------------------------------------
# 1. The record's own board
# ---------------------------------------------------------------------------

def test_the_record_ends_the_turn_instead_of_burning_the_engine():
    obs = _record_obs()
    assert sorted(_hand_ids(obs)) == sorted([XEROSIC, DAWN, ULTRA_BALL, LILLIE])
    assert obs["current"]["supporterPlayed"] is True
    assert obs["current"]["players"][0]["handCount"] == 10

    assert _chosen(obs, m.agent(obs))["type"] == int(m.OptionType.END), (
        "la unica forma de pagar la Ultra Ball era con el cap y el refill: "
        "el turno se acaba y las dos cartas sobreviven")


def test_the_record_board_is_exactly_what_the_new_veto_answers():
    """The other six cost vetoes stay silent on it -- that is the hole."""
    ctx = _Ctx(_RECORD_HAND)
    assert m._ub_cancel_engine_supporters(ctx)
    assert not m._ub_cancel_xerosic(ctx)
    assert not m._ub_cancel_lillie(ctx)
    assert not m._ub_cancel_tomorrow_supporter(ctx)
    assert not m._ub_cancel_no_surplus(ctx)
    assert m._ub_cost_destroys_better_card(ctx)


def test_each_supporter_was_the_others_proof_that_nothing_burned():
    """Asked one at a time the count clears the trade; asked as a set it does
    not. Both readings on the record's own hand."""
    ctx = _Ctx(_RECORD_HAND)
    assert m._ub_real_fodder(ctx, XEROSIC) == 2      # sees Dawn + Lillie's
    assert m._ub_real_fodder(ctx, LILLIE) == 2       # sees Dawn + Xerosic
    assert m._ub_real_fodder(ctx, [XEROSIC, LILLIE]) == 1   # only the Dawn


# ---------------------------------------------------------------------------
# 2. `_ub_real_fodder` takes one id, a collection, or nothing
# ---------------------------------------------------------------------------

def test_the_count_still_takes_a_single_id_and_none():
    ctx = _Ctx(_RECORD_HAND)
    assert m._ub_real_fodder(ctx, None) == 3         # Dawn + Lillie's + Xerosic
    assert m._ub_real_fodder(ctx, DAWN) == 2
    assert m._ub_real_fodder(ctx, (DAWN,)) == 2
    assert m._ub_real_fodder(ctx, []) == m._ub_real_fodder(ctx, None)


# ---------------------------------------------------------------------------
# 3. It is cost arithmetic, not conservatism
# ---------------------------------------------------------------------------

def test_a_hand_with_surplus_plays_its_ultra_ball():
    """Two spare cards pay for it and the engine is never touched."""
    ctx = _Ctx({XEROSIC: 1, LILLIE: 1, ULTRA_BALL: 1, GRASS: 2})
    assert m._ub_real_fodder(ctx, [XEROSIC, LILLIE]) == 2
    assert not m._ub_cancel_engine_supporters(ctx)


def test_the_orphan_stage_two_is_still_fodder_but_one_card_is_not_two():
    """A Meganium with no Bayleef in play pays, and gladly -- it is just not
    enough on its own."""
    ctx = _Ctx({XEROSIC: 1, LILLIE: 1, ULTRA_BALL: 1, MEGANIUM: 1})
    assert m._ub_real_fodder(ctx, [XEROSIC, LILLIE]) == 1
    assert m._ub_cancel_engine_supporters(ctx)
    ctx = _Ctx({XEROSIC: 1, LILLIE: 1, ULTRA_BALL: 1, MEGANIUM: 2})
    assert not m._ub_cancel_engine_supporters(ctx)


# ---------------------------------------------------------------------------
# 4. WHICH Xerosic is an engine
# ---------------------------------------------------------------------------

def test_a_cap_with_nothing_to_cap_is_not_protected():
    """The measured boundary: outside the Alakazam matchup and below
    `XEROSIC_BIG_HAND` the card is fodder, and the search that needs it goes
    ahead (registro_002 step 26 vs Marnie)."""
    _dead = _Ctx({XEROSIC: 1, ULTRA_BALL: 1, MEGANIUM: 1},
                 op_hand_count=ids.XEROSIC_BIG_HAND - 1,
                 op_is_alakazam_deck=False)
    assert m._ub_engine_supporters_held(_dead) == []
    assert not m._ub_cancel_engine_supporters(_dead)


def test_the_generic_fat_hand_protects_it_in_any_deck():
    _fat = _Ctx({XEROSIC: 1, ULTRA_BALL: 1, MEGANIUM: 1},
                op_hand_count=ids.XEROSIC_BIG_HAND,
                op_is_alakazam_deck=False)
    assert m._ub_engine_supporters_held(_fat) == [XEROSIC]
    assert m._ub_cancel_engine_supporters(_fat)


def test_the_alakazam_floor_is_the_gate_below_seven():
    """vs Alakazam the cap is an engine from its own floor of six, one card
    below the generic threshold: `_xr_gate_alakazam`, not a number of its own."""
    _six = _Ctx({XEROSIC: 1, ULTRA_BALL: 1, MEGANIUM: 1}, op_hand_count=6)
    assert m._ub_engine_supporters_held(_six) == [XEROSIC]
    _five = _Ctx({XEROSIC: 1, ULTRA_BALL: 1, MEGANIUM: 1}, op_hand_count=5)
    assert m._ub_engine_supporters_held(_five) == []


def test_the_refill_needs_no_such_test():
    """There is no board on which drawing a fresh hand is worth nothing."""
    _quiet = _Ctx({LILLIE: 1, ULTRA_BALL: 1, MEGANIUM: 1},
                  op_hand_count=1, op_is_alakazam_deck=False)
    assert m._ub_engine_supporters_held(_quiet) == [LILLIE]
    assert m._ub_cancel_engine_supporters(_quiet)


# ---------------------------------------------------------------------------
# 5. The exception the user named
# ---------------------------------------------------------------------------

def test_a_turn_that_wins_pays_with_whatever_it_has_to():
    winning = NO_PLAN.__class__(
        my_prize=1, op_prize=6, win_route=ROUTE_ACTIVE,
        win_needs_supporter=False, win_needs_charge=False, prizes_today=1,
        op_prizes_next=0, op_wins_next=False, mode='WIN_NOW')
    assert winning.wins_this_turn
    assert not m._ub_cancel_engine_supporters(
        _Ctx(_RECORD_HAND, turn_plan=winning))
    # ...and without a lethal route the same hand is vetoed again.
    assert m._ub_cancel_engine_supporters(_Ctx(_RECORD_HAND))


def test_a_context_without_a_plan_reads_as_no_lethal_route():
    """`plan_of` answers `NO_PLAN` for the dozens of hand-built contexts in this
    suite: the veto must not depend on a field they never set."""
    ctx = _Ctx(_RECORD_HAND)
    assert not hasattr(ctx, 'turn_plan')
    assert not NO_PLAN.wins_this_turn
    assert m._ub_cancel_engine_supporters(ctx)


# ---------------------------------------------------------------------------
# 6. It is not revoked when the turn comes out sterile
# ---------------------------------------------------------------------------

def test_it_joins_the_family_the_rescues_must_consult():
    """Cost arithmetic, like the rest of `_ub_cost_destroys_better_card`: the
    nets that resurrect a vetoed Ultra Ball out of boredom have to see it."""
    assert m._ub_cost_destroys_better_card(_Ctx(_RECORD_HAND))
    assert not m._ub_cost_destroys_better_card(
        _Ctx({XEROSIC: 1, LILLIE: 1, ULTRA_BALL: 1, GRASS: 2}))
