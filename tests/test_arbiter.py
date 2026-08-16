"""The arbiter's exits, each one forced: verdict, floor, deadline, exception.

The arbiter is pure control flow with the rollout machinery injected, so
every branch is reachable with a fake `rollout_one` and no engine.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ptcg.search.arbiter import K_FLOOR, arbitrate  # noqa: E402


def worlds(margin, won=True):
    def rollout_one(option, i):
        return {"won": won, "margin": margin(option, i)}
    return rollout_one


def test_a_clear_gap_returns_the_best_option():
    idx, diag = arbitrate(
        3, worlds(lambda option, i: [0.0, 3.0, 1.0][option]))
    assert idx == 1
    assert diag["reason"] == "verdict"


def test_identical_options_are_no_opinion():
    idx, diag = arbitrate(2, worlds(lambda option, i: 1.0))
    assert idx is None
    assert diag["reason"] == "floor"


def test_a_gap_below_the_boards_own_floor_is_no_opinion():
    # Option margins differ by 0.4, but the same option re-batched drifts by
    # more than that: the board is noisier than the preference.
    def margin(option, i):
        if option == 1 and i >= K_FLOOR:  # the floor batch
            return 2.4 - 1.0
        return [2.0, 2.4][option]
    idx, diag = arbitrate(2, worlds(margin))
    assert idx is None
    assert diag["reason"] == "floor"


def test_a_margin_tie_falls_to_the_win_flag():
    def rollout_one(option, i):
        return {"won": option == 0, "margin": 1.0}
    idx, diag = arbitrate(2, rollout_one)
    assert idx == 0
    assert diag["reason"] == "verdict"


def test_an_exception_inside_a_rollout_is_invisible():
    def rollout_one(option, i):
        raise RuntimeError("the engine hiccuped")
    idx, diag = arbitrate(2, rollout_one)
    assert idx is None
    assert diag["reason"].startswith("exception")


def test_worlds_that_refuse_to_build_are_an_abstention():
    idx, diag = arbitrate(2, lambda option, i: None)
    assert idx is None
    assert diag["reason"] == "no_worlds"


def test_the_deadline_cuts_before_the_next_rollout():
    now = [0.0]

    def clock():
        now[0] += 0.2
        return now[0]

    calls = []

    def rollout_one(option, i):
        calls.append((option, i))
        return {"won": True, "margin": 1.0}

    idx, diag = arbitrate(2, rollout_one, wall_s=1.0, clock=clock)
    assert idx is None
    assert diag["reason"] == "deadline"
    assert len(calls) < 2 * K_FLOOR


def test_k_is_floored_at_fifty():
    counted = []

    def rollout_one(option, i):
        counted.append(i)
        return {"won": True, "margin": float(option)}

    arbitrate(2, rollout_one, k=10)
    # two options at K>=50 each, plus the floor batch
    assert len(counted) >= 3 * K_FLOOR
