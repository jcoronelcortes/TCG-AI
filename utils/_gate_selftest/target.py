"""A module that exists only to be mutated, with a known right answer.

The gate cannot check itself against the agent: whether a line of `main.py` is
watched is the QUESTION, so it cannot also be the yardstick. This file is the
yardstick. It is small enough to reason about completely, its companion test
pins some of it and deliberately leaves one thing unpinned, and therefore the
gate's verdict on it is known in advance:

    every mutation site here must be KILLED, except exactly one -- the default
    of `unread_flag`, which nothing reads and nothing can watch.

That single expected survivor is what makes the check two-sided. A gate that
reported "no survivors anywhere" would pass a sensitivity test and still be
useless, because it would be passing by never finding anything.

The signature is written with BOTH flags on one line on purpose. It reproduces
the defect that made the first version of this gate lie: two mutants of one file
that differ in neither byte size nor whole-second mtime, so CPython hands the
second run the first one's cached bytecode and the second comes back a survivor.
`unread_flag=False` and `cautious=False` are the same length. If that bug ever
returns, this file reports two survivors instead of one and the run stops.

Nothing imports this outside the self-test, and `testpaths = tests` keeps its
companion out of the ordinary suite.
"""

WATCHED_THRESHOLD = 10


def decide(value, unread_flag=False, cautious=False):
    """"high" only when the caller asked for care AND the value is over the bar.

    `cautious` is read here and pinned by the test. `unread_flag` is read by
    nobody -- it is the deliberate blind spot.
    """
    if cautious and value >= WATCHED_THRESHOLD:
        return "high"
    return "low"
