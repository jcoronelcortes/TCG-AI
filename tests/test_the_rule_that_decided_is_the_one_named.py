"""The trace helper, validated in both directions, and used on a real ladder.

`tests/rule_trace.py` is the plumbing for T1.1: it hands back the trace the
rules engine already builds so a test can assert WHICH rule decided rather than
what number came out. A helper that reports the wrong rule would silently make
every assertion built on it meaningless, so it is checked the way this project
checks every other detector -- it has to name the right rule AND it has to
refuse the wrong one.
"""

import pytest

from ptcg.engine.rules import _Adjustment, _E, _FixedRule
from rule_trace import (adjustments, assert_adjusted, assert_reason, reason,
                        resolve, resolve_max)

from ptcg.cards.ids import Applin as APPLIN  # noqa: E402
from ptcg.cards.ids import Chikorita as CHIKORITA  # noqa: E402,F401
from ptcg.cards.ids import Tapu_Bulu as TAPU  # noqa: E402


class _Ctx:
    """A context of one field, which is all these ladders need to be told."""

    def __init__(self, n):
        self.n = n


_LADDER = [
    _FixedRule("big", lambda c: c.n >= 10, lambda c: 100),
    _FixedRule("small", lambda c: c.n >= 1, lambda c: 10),
]

_BOOST = [
    _Adjustment("double_it", lambda c, s: c.n == 5, lambda c, s: s * 2),
    _Adjustment("never", lambda c, s: False, lambda c, s: 0),
    _Adjustment("no_effect", lambda c, s: True, lambda c, s: s),
]


# ---------------------------------------------------------------------------
# The helper names the rule that fired
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n,expected,score", [(10, "big", 100), (5, "small", 20),
                                              (1, "small", 10)])
def test_it_names_the_rule_that_fired(n, expected, score):
    value, trace = resolve(_LADDER, _BOOST, _Ctx(n), default=0)
    assert value == score
    assert_reason(trace, expected)


def test_no_rule_firing_is_itself_a_reason():
    """`defecto` is not the absence of an answer, it is one."""
    value, trace = resolve(_LADDER, [], _Ctx(0), default=7)
    assert value == 7
    assert reason(trace) == "defecto"


def test_it_refuses_a_rule_that_did_not_decide():
    """The half that makes the other half worth anything."""
    _value, trace = resolve(_LADDER, [], _Ctx(1))
    with pytest.raises(AssertionError) as caught:
        assert_reason(trace, "big")
    assert "small" in str(caught.value), "the message says who decided instead"


# ---------------------------------------------------------------------------
# Adjustments: only the ones that MOVED the score
# ---------------------------------------------------------------------------

def test_only_the_adjustment_that_moved_the_score_counts():
    _value, trace = resolve(_LADDER, _BOOST, _Ctx(5))
    assert adjustments(trace) == ["double_it"]
    assert_adjusted(trace, "double_it")
    with pytest.raises(AssertionError):
        assert_adjusted(trace, "no_effect")   # it fired, it changed nothing


def test_the_argmax_ladders_report_their_winner_too():
    """The other resolution mode: every scenario competes, the highest wins."""
    scenarios = [_E("cheap", lambda c: True, 10),
                 _E("dear", lambda c: c.n > 0, 90)]
    value, trace = resolve_max(scenarios, _Ctx(1))
    assert value == 90
    assert "dear" in trace[0]


# ---------------------------------------------------------------------------
# On a ladder of the agent, not a toy
# ---------------------------------------------------------------------------

def test_it_reads_a_real_ladder_of_the_agent():
    """The Poke Pad fetch order, asserted by REASON instead of by number.

    `tests/test_the_opening_puts_one_prize_in_front.py` already pins this ladder
    through its scores -- `_score(TAPU) > _score(APPLIN) > _score(CHIKORITA)`.
    That comparison survives a rewrite that makes a DIFFERENT rule produce the
    same ordering. This one does not: it names the rule.
    """
    from ptcg.decision.poke_pad import _CtxPPFetch, _RULES_PP_FETCH

    class _State:
        turn = 2

    def _trace(card_id, needs_body=True):
        return resolve(_RULES_PP_FETCH, [],
                       _CtxPPFetch(card_id, {}, {}, 1, _State, needs_body),
                       default=10)

    tapu_score, tapu_trace = _trace(TAPU)
    applin_score, _applin_trace = _trace(APPLIN)
    assert tapu_score > applin_score
    named = reason(tapu_trace)
    assert named and named != "defecto", (
        "the Tapu is fetched by a rule with a name, not by the default rung: "
        f"traza {tapu_trace}")
