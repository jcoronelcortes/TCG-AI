"""Properties that must hold on boards nobody designed.

T2.3 of docs/testing-plan-2026-08.md, second file. `tests/test_invariants.py`
has the first two properties; these are the ones that need no expected answer at
all, which is what lets hypothesis generate the board instead of a person.

WHY THESE FOUR AND NOT THE OTHER SEVEN THE PLAN LISTS. The plan's remaining
candidates -- "a strictly better board never produces a strictly worse plan
mode", "removing an opposing threat never makes the agent more defensive" -- are
MONOTONICITY claims, and every one of them needs a judgement about what "better"
and "more defensive" mean in this game. That judgement is exactly the thing a
property test is supposed to avoid needing, and getting it slightly wrong
produces a generator that reports correct play as a violation. Three detectors
in this repository have already done that this week. The four below are
mechanical: they can be checked without knowing a single rule of Pokemon.

EVERY ONE WAS MEASURED BEFORE IT WAS ASSERTED, on 40 real boards from
tests/fixtures/: determinism 40/40, no mutation 40/40. A property is a claim
about the code, and claiming one that does not hold turns the suite red for a
reason nobody can act on.

ONE THAT IS DELIBERATELY NOT HERE, with its number. "The tracker never believes
more prizes than are face down" -- the invariant behind the Ultra Ball fix -- is
checked on every decision of every game by utils/invariant_monitor.py and reads
ZERO over 26 617 live boards. It is NOT asserted over frozen fixtures, because
replaying a mid-game board cold makes `_first_turn_scan` treat the current hand
as an opening hand: 1 of those same 40 fixtures fails it for that reason and not
because of the agent. A property that only holds when the history is real
belongs to the monitor, which has the history.
"""

import copy
import json
import os
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import main as m  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402
from state_builder import InconsistentState, Scenario, pk  # noqa: E402

EXAMPLES = int(os.environ.get("PTCG_HYPOTHESIS_EXAMPLES", "40"))

SETTINGS = dict(max_examples=EXAMPLES, deadline=None, derandomize=True,
                suppress_health_check=[HealthCheck.filter_too_much,
                                       HealthCheck.too_slow])

OWN_ROSTER = [m.Dipplin, m.Chikorita, m.Bayleef, m.Teal_Mask_Ogerpon_ex,
              m.Tapu_Bulu, m.Meowth_ex]
HAND_CARDS = [m.Basic_Grass_Energy, m.Lillie_Determination, m.Boss_Orders,
              m.Night_Stretcher, m.Dipplin, m.Ultra_Ball]
KANGASKHAN = 756


def _board(active_id, energies, bench, hand, turn):
    """A self-consistent board, or `assume(False)` if the draw is impossible."""
    try:
        return (Scenario(turn=turn, step=1, tac=0)
                .my_active(pk(active_id, energies=energies))
                .my_bench(*bench)
                .my_hand(m.Basic_Grass_Energy, *hand)
                .op_active(pk(KANGASKHAN, hp=160, max_hp=400))
                .op_zones(hand=5, deck=30, prizes=6)
                .menu_attach_energy()
                .build())
    except InconsistentState:
        assume(False)


GENERATED = dict(
    active_id=st.sampled_from([m.Dipplin, m.Applin, m.Chikorita,
                               m.Teal_Mask_Ogerpon_ex, m.Tapu_Bulu]),
    energies=st.integers(min_value=0, max_value=2),
    bench=st.lists(st.sampled_from(OWN_ROSTER), max_size=3),
    hand=st.lists(st.sampled_from(HAND_CARDS), max_size=4),
    turn=st.integers(min_value=2, max_value=10),
)


@settings(**SETTINGS)
@given(**GENERATED)
def test_the_same_board_twice_gives_the_same_answer(active_id, energies, bench,
                                                    hand, turn):
    """Determinism. It is not free here, and that is why it is worth asserting.

    `AGENT_STATE` is a module-level singleton that survives between calls and
    carries turn flags, the card tracker and the turn plan. If any of it leaked
    into a decision that should not depend on it, the agent would answer one
    thing on a fresh process and another after a game, and no example-based test
    would notice because they all run on a fresh reset.
    """
    obs = _board(active_id, energies, bench, hand, turn)
    reset_agent(m)
    first = m.agent(copy.deepcopy(obs))
    reset_agent(m)
    second = m.agent(copy.deepcopy(obs))
    assert first == second, f"la misma observacion dio {first} y luego {second}"


@settings(**SETTINGS)
@given(**GENERATED)
def test_the_agent_does_not_write_on_the_board_it_is_given(active_id, energies,
                                                           bench, hand, turn):
    """The observation is the container's, not ours.

    The agent receives a dict it does not own. Writing into it would be
    invisible in this repository -- every test passes a fresh copy -- and would
    corrupt the state of whatever calls it next: the self-play harness, the
    shadow harness, the differential oracle, all of which reuse the observation
    around the call.
    """
    obs = _board(active_id, energies, bench, hand, turn)
    before = json.dumps(obs, sort_keys=True)
    reset_agent(m)
    m.agent(obs)
    assert json.dumps(obs, sort_keys=True) == before


@settings(**SETTINGS)
@given(**GENERATED)
def test_the_answer_is_always_a_legal_index(active_id, energies, bench, hand,
                                            turn):
    """The weakest claim there is, on the widest board space available.

    An index outside the option list is an exception inside the container, which
    is the game lost on the spot regardless of how well everything else played.
    """
    obs = _board(active_id, energies, bench, hand, turn)
    reset_agent(m)
    choice = m.agent(copy.deepcopy(obs))
    select = obs["select"]
    assert isinstance(choice, list), f"no es una lista: {choice!r}"
    assert all(isinstance(i, int) for i in choice), f"indices no enteros: {choice!r}"
    assert all(0 <= i < len(select["option"]) for i in choice), (
        f"indice fuera de rango: {choice} sobre {len(select['option'])} opciones")
    assert len(set(choice)) == len(choice), f"indices repetidos: {choice}"
    assert select["minCount"] <= len(choice) <= select["maxCount"], (
        f"cantidad fuera de [{select['minCount']}, {select['maxCount']}]: {choice}")


@settings(**SETTINGS)
@given(**GENERATED)
def test_it_never_raises(active_id, energies, bench, hand, turn):
    """Separated from the one above on purpose.

    "Returns something legal" and "does not blow up" fail differently and are
    worth distinguishing in the report: a legality failure names a rule, an
    exception names a line.
    """
    obs = _board(active_id, energies, bench, hand, turn)
    reset_agent(m)
    try:
        m.agent(copy.deepcopy(obs))
    except Exception as exc:      # noqa: BLE001 -- that IS the property
        pytest.fail(f"el agente lanzo {exc!r} sobre un tablero legal")
