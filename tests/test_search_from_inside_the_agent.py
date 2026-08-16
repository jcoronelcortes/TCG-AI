"""S0.2: a search opened from inside a live game must not perturb the game.

Question S0.2 of docs/plan-la-busqueda-en-juego-2026-08-15.md §3: the whole
play-time search plan dies here if `search_begin` from within a running battle
changes that battle. The test plays the SAME seeded game twice on the local
engine -- the second run opens a full rollout-to-verdict search at three
different decisions -- and asserts the trace of (seat, choice) pairs and the
final result are identical.

The configuration is the one every oracle already runs: the battle on the
LOCAL seeded engine, the search on the SHIPPED binary (`cg/api.py`'s own
`lib`). Two separate loaded binaries, so cross-talk would have to travel
through this process's memory -- which is exactly the channel the arbiter
will use in a real game.

⚠️ Measured while writing this (night of 16 August): pointing the search at
the LOCAL build (`api.lib = local_engine.load()`, one binary for both) is a
HARD CRASH -- segfault, not an exception. The local build's search arena has
never been exercised before tonight; the shipped binary's has. Nothing in the
plan needs the local search arena (the container runs the official binary,
and S0.3 is the container probe), but whoever builds on it should know.

Skip guard: the local engine is a gitignored build (`cg/build/`), absent on a
clean checkout -- same reasoning as the R6 guards for `records/`.
"""

import random
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import local_engine  # noqa: E402

pytestmark = pytest.mark.skipif(
    not local_engine.library_path().exists(),
    reason="local engine not built (cg/build/ is gitignored)")

import search_oracle as so  # noqa: E402
from cg import api  # noqa: E402
from cg.battle import Battle  # noqa: E402

SEED = 23
POLICY_SEED = 5
# On this seed the determinizer refuses to close at decisions 2, 3, 11 and 21
# (the mid-effect class its guard exists for), so the probes sit elsewhere:
# a refusal happens BEFORE search_begin and would make the test vacuous.
SEARCH_AT = (6, 13, 20)
MAX_DECISIONS = 400


def _deck():
    lines = (_ROOT / "deck.csv").read_text().split("\n")
    return [int(lines[i]) for i in range(60)]


def _play(lib, deck, with_search):
    """One seeded mirror game; optionally search at three decisions."""
    rng = random.Random(POLICY_SEED)
    battle = Battle(deck, deck, seed=SEED, lib=lib)
    trace, rollouts = [], []
    try:
        decision = 0
        while battle.result == -1 and decision < MAX_DECISIONS:
            obs = battle.obs
            choice = so._choose(obs, rng, "random", None)
            if choice is None:
                break
            if with_search and decision in SEARCH_AT:
                try:
                    rollouts.append(so.rollout(
                        obs, None, deck, deck, choice,
                        seed=1234 + decision, policy="random",
                        max_steps=120))
                finally:
                    api.search_end()
            trace.append((obs["current"]["yourIndex"], tuple(choice)))
            battle.select(choice)
            decision += 1
        return trace, battle.result, rollouts
    finally:
        battle.finish()


def test_a_search_inside_a_live_game_does_not_perturb_it():
    # A fresh REAL arena, whatever earlier tests cached: `api.agent_ptr` is a
    # process global and a monkeypatched fake that outlives its test is a
    # segfault here, not an assertion (found the night this test was written).
    if hasattr(api, "agent_ptr"):
        del api.agent_ptr
    lib = local_engine.load()
    deck = _deck()
    trace_plain, result_plain, _ = _play(lib, deck, with_search=False)
    trace_search, result_search, rollouts = _play(lib, deck,
                                                  with_search=True)

    # The searches actually ran: an interleaving of nothing proves nothing.
    assert len(rollouts) == len(SEARCH_AT)
    assert all(r["steps"] > 0 for r in rollouts)

    # And the battle never noticed them.
    assert trace_search == trace_plain
    assert result_search == result_plain
