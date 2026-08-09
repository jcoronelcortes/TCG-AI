"""Every turn promise re-checks its premise where it is READ.

BACKGROUND. Five of the roughly twenty fixes of 7-8 August 2026 were one shape:
a flag on AGENT_STATE armed under some premise and consumed later in the same
turn, after that premise had died. `_ub_engine_pivot_turn` is the canonical one
-- armed while a bench seat was free, cleared only when the TURN changes, read
after a Pokemon had filled the bench.

`utils/invariant_monitor.py` was built to catch that class, and its verdict is
that the class is currently CLOSED: over 600 games it saw 743 reads of a promise
whose premise had died, and every one of them happened inside a compound
condition whose other terms re-check that premise. The flag lies; the condition
around it does not.

That is a property of how the consumers are written today, and nothing enforces
it. This file does. If one of these guards is deleted, the stale-promise class
re-opens silently -- the monitor cannot see the difference, because from outside
a read is just a read.

Each test reads the SOURCE rather than running the agent, because what is being
guarded is the shape of the condition, not the outcome of one board.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _condition_around(path, flag):
    """The text of the `if (...)` in which `flag` is read."""
    source = (ROOT / path).read_text(encoding="utf-8")
    hit = source.find(f"AGENT_STATE.{flag} and")
    assert hit != -1, f"{flag} is no longer read in {path}"
    start = source.rfind("if (", 0, hit)
    assert start != -1, f"the read of {flag} is not inside an `if (`"
    depth, i = 0, start + 2
    while i < len(source):
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
        i += 1
    raise AssertionError("unbalanced condition")


def test_the_meowth_promise_rechecks_a_free_bench_seat():
    cond = _condition_around("ptcg/turn/options/play.py", "_ub_meowth_pending")
    assert re.search(r"bench_count\s*<\s*5", cond), (
        "the Meowth promise is armed while a bench seat is free; without this "
        "term a stale flag puts a body where there is no room")


def test_the_meowth_promise_rechecks_the_unspent_supporter():
    cond = _condition_around("ptcg/turn/options/play.py", "_ub_meowth_pending")
    assert "not state.supporterPlayed" in cond, (
        "the Meowth is only worth putting down as the first half of "
        "Meowth -> Lillie's; with the Supporter spent the chain cannot happen")
