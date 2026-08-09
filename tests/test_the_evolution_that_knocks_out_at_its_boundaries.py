"""The `_evk_` block's thresholds, one board on each side of each of them.

WHY THIS FILE EXISTS. `tests/test_the_evolution_in_hand_that_knocks_out_comes_up.py`
already guards this rule, and it guards it well: it pins the board of the game
that produced it and asserts the agent brings up the Dipplin. Then the mutation
probe of 2026-08-09 rewrote the block one expression at a time and the suite
stayed green through **23 of them** -- more survivors than any other region of
the tree. `>=` became `>`, a `1` became a `2`, an `and` became an `or`, and
nothing went red.

That is not a gap in the other file, it is the ceiling of what a single board
can measure. One example fixes the output of a long chain of thresholds at ONE
point of its input space; move a threshold by one and the same board still
produces the same choice. This file is the other half: for each threshold, the
PAIR of boards that sit either side of it. A rule whose boundary is pinned at
n and n+1 cannot have its comparison rewritten without a test going red.

THE BLOCK. When a knockout forces a promotion and nobody on the bench knocks
back as they are, look for a benched pre-evolution whose evolution is in hand,
price the EVOLUTION's attack with the energy we can still attach next turn, and
promote the pre-evolution if that knocks out.

THE BOUNDARIES, all measured on the live agent rather than reasoned about:

    threshold                       one side          the other
    ---------------------------------------------------------------------
    damage >= what the body needs   390 hp -> Dipplin  391 hp -> Ogerpon
    the pre-evolution was already
      on the bench                  no      -> Dipplin  yes    -> Ogerpon
    Grass reachable for the attack   0 in hand, Night Stretcher + Grass in the
                                     discard -> Dipplin; drop either -> Ogerpon

A WORD ON HOW THESE WERE FOUND, because it is the point of the exercise. The
0-Grass arm was reasoned to be impossible -- with one Grass unit and a cost of
two the evolution cannot pay -- and tracing the live agent showed the block
firing anyway. The arithmetic was wrong and the trace was right. Every number in
the table above comes from running the agent, not from reading the source.
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
            / "lopunny_the_evolution_in_hand_that_knocks_out_step120.json")

DIPPLIN = m.Dipplin
OGERPON = m.Teal_Mask_Ogerpon_ex
GRASS = m.Basic_Grass_Energy
NIGHT_STRETCHER = m.Night_Stretcher

# Syrup Storm out of the evolution this board can reach, measured on the agent.
LETHAL_REACH = 390


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
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m.op_is_starmie_deck = False
    m._field_at_turn_start = {}
    yield
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _mine(o):
    return o["current"]["players"][o["current"]["yourIndex"]]


def _rival(o):
    return o["current"]["players"][1 - o["current"]["yourIndex"]]


def _promoted(o):
    chosen = o["select"]["option"][m.agent(copy.deepcopy(o))[0]]
    return _mine(o)["bench"][chosen["index"]]["id"]


def _set_rival_hp(o, hp):
    _rival(o)["active"][0]["hp"] = hp


def _keep_grass(o, n):
    hand = _mine(o)["hand"]
    others = [c for c in hand if c["id"] != GRASS]
    grass = [c for c in hand if c["id"] == GRASS][:n]
    _mine(o)["hand"] = others + grass


def _drop(o, card_id, zone="hand"):
    _mine(o)[zone] = [c for c in _mine(o)[zone] if c["id"] != card_id]


# ---------------------------------------------------------------------------
# The board still says what the other file says it says
# ---------------------------------------------------------------------------

def test_the_unmodified_board_promotes_the_pre_evolution():
    assert _promoted(_obs()) == DIPPLIN


# ---------------------------------------------------------------------------
# Boundary 1 -- the knockout. `_evk_dmg < _op_prom_remain` -> skip
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hp", [LETHAL_REACH - 1, LETHAL_REACH])
def test_it_promotes_while_the_evolution_still_reaches(hp):
    """Up to and INCLUDING the exact hp: the comparison is >=, not >."""
    o = _obs()
    _set_rival_hp(o, hp)
    assert _promoted(o) == DIPPLIN


@pytest.mark.parametrize("hp", [LETHAL_REACH + 1, LETHAL_REACH + 30])
def test_one_point_out_of_reach_and_the_branch_says_nothing(hp):
    """A single hit point past the reach and the whole branch goes quiet.

    This is the pair that a `>=` -> `>` rewrite cannot survive: at exactly
    LETHAL_REACH the rule must still fire, and at LETHAL_REACH+1 it must not.
    """
    o = _obs()
    _set_rival_hp(o, hp)
    assert _promoted(o) == OGERPON


# ---------------------------------------------------------------------------
# Boundary 2 -- the body has to have BEEN there. `appearThisTurn` -> skip
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("appeared,expected", [(False, DIPPLIN), (True, OGERPON)])
def test_a_body_that_came_down_this_turn_cannot_evolve_next_turn(appeared, expected):
    o = _obs()
    for body in _mine(o)["bench"]:
        if body and body["id"] == DIPPLIN:
            body["appearThisTurn"] = appeared
    assert _promoted(o) == expected


# ---------------------------------------------------------------------------
# Boundary 3 -- the Grass has to be REACHABLE, and the recovery route counts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("grass", [0, 1, 2])
def test_the_grass_in_hand_is_not_the_only_route(grass):
    """With a Night Stretcher and a Grass in the discard, an empty hand pays.

    All three arms promote, which is what makes the two tests below mean
    something: they change ONE thing each from the 0-Grass board.
    """
    o = _obs()
    _keep_grass(o, grass)
    assert _promoted(o) == DIPPLIN


def test_without_the_night_stretcher_the_empty_hand_cannot_pay():
    """Drop the recovery card and the same 0-Grass board flips."""
    o = _obs()
    _keep_grass(o, 0)
    _drop(o, NIGHT_STRETCHER)
    assert _promoted(o) == OGERPON


def test_a_night_stretcher_with_nothing_to_recover_does_not_count():
    """Keep the card, empty the discard: the route needs BOTH halves.

    This is the pair that kills an `and` -> `or` rewrite of the recovery
    condition -- either half alone must not be enough.
    """
    o = _obs()
    _keep_grass(o, 0)
    _drop(o, GRASS, zone="discard")
    assert _promoted(o) == OGERPON


# ---------------------------------------------------------------------------
# Boundary 4 -- which candidate wins when two of them are the same
# ---------------------------------------------------------------------------

def _second_dipplin_on_the_bench(o, at):
    """Copy the benched Dipplin into another seat, identical but for its id.

    The fixture offers exactly ONE candidate, which is why nothing in this file
    could reach the comparison that RANKS them. Two identical ones make the
    ranking the only thing left to decide the answer.
    """
    twin = copy.deepcopy(_mine(o)["bench"][4])
    twin["serial"] = 9999
    _mine(o)["bench"][at] = twin
    return o


def test_between_two_identical_candidates_the_first_one_keeps_the_seat():
    """`_evk_key > _evk_best_key`, and the `>` is load-bearing.

    With two Dipplins that evolve into the same Hydrapple ex, the ranking key
    -- prizes, then hp, then damage -- is EQUAL, and the only thing separating
    them is whether a later tie replaces an earlier one. It must not: rewriting
    that `>` as `>=` hands the seat to the last body the loop happens to see,
    which is the bench order and not a reason. The rest of this project treats a
    tie broken by option order as a defect (`utils/permutation_probe.py` exists
    to count them), so the stable answer is the correct one.

    Measured on the live agent: bench seat 1, the first of the two.
    """
    o = _second_dipplin_on_the_bench(_obs(), at=1)
    chosen = o["select"]["option"][m.agent(copy.deepcopy(o))[0]]
    assert _mine(o)["bench"][chosen["index"]]["id"] == DIPPLIN
    assert chosen["index"] == 1, "the earlier seat, not the later one"
