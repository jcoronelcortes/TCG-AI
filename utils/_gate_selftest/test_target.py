"""The pins that make `target.py`'s mutation verdict a known answer.

One test per thing the gate has to be able to notice, and NOTHING for
`unread_flag`, which is the one survivor the gate is expected to report.

This is not part of the suite: `testpaths = tests` in pytest.ini keeps it out,
and it is run only by `utils/gate_mutation.py --self-test`, which passes its
path explicitly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from target import decide  # noqa: E402


def test_over_the_bar_with_care_is_high():
    """The boundary, from below: at exactly 10 it still fires."""
    assert decide(10, cautious=True) == "high"


def test_one_under_the_bar_is_low():
    """The other side of the same boundary.

    The pair is what refuses both `>= -> >` and `10 -> 11`: with either rewrite
    one of these two boards changes its answer.
    """
    assert decide(9, cautious=True) == "low"


def test_without_care_the_value_does_not_matter():
    """Refuses `and -> or`: with `or`, a value over the bar would be enough."""
    assert decide(10, cautious=False) == "low"


def test_care_is_off_unless_the_caller_asks():
    """Refuses `cautious=False -> True` in the signature.

    The default is a claim of its own, separate from the False arm above, and
    it is the half that the real gate's last survivor turned out to be about.
    """
    assert decide(10) == "low"
