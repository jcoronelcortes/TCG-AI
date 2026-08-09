"""Assert the REASON a rule ladder gave, not just the number it came out with.

T1.1 of docs/testing-plan-2026-08.md, and the answer to the second structural
weakness of the estate: the oracle is the CHOICE, not the MECHANISM.

The typical test here says "on this board the agent picks option X". That pins
the output of a long chain of thresholds, tiers and tie-breaks at exactly ONE
point of that chain's input space. Move a threshold by one and the same board
still produces the same choice -- which is precisely why ten of fourteen mutants
survived on code that had just been written with a test. The assertion watches
the answer and not the thing that produced it.

The machinery to do better already existed and nothing used it. `_resolve_rules`
returns `(score, trace)`, where the trace names the rule that fired and every
adjustment that moved the score afterwards:

    ['winning_gust=42000', 'supporter_boost:42000->42200']

`_resolve_with_trace` throws that trace away unless `PTCG_DEBUG` is set, which
is why the ladders are tested through their numbers. This module hands the trace
back so a test can say WHICH rule decided:

    score, why = resolve(_RULES_BOSS_PLAY, [], ctx, default=0)
    assert_reason(why, "winning_gust")

WHY THIS IS WORTH MORE THAN THE NUMBER. A test that pins the score dies when the
band is renumbered and survives when the wrong rule fires at the right number --
exactly backwards. A test that pins the rule NAME survives a renumbering, dies
when a different rule takes over, and reads as the sentence the rule was written
to enforce. It also makes the mutation survivors of a ladder killable: rewriting
the guard of rule N so that rule N+1 fires instead changes the trace even when
the two happen to score the same.

WHAT THIS DELIBERATELY DOES NOT DO. It does not decide WHICH rule name a given
board ought to name -- that is a judgement about the game, and it belongs to
whoever writes the test. This is the plumbing.
"""

from ptcg.engine.rules import _resolve_max, _resolve_rules


def resolve(rules, adjustments, ctx, default=0):
    """`(score, trace)` for a fixed-rule ladder. The trace is a list of strings.

    The same call `_resolve_with_trace` makes, minus the discarding.
    """
    return _resolve_rules(rules, adjustments, ctx, default)


def resolve_max(scenarios, ctx):
    """`(value, trace)` for the ARGMAX ladders, whose trace is a single string."""
    value, trace = _resolve_max(scenarios, ctx)
    return value, [trace]


def reason(trace):
    """The name of the rule that FIRED, before any adjustment touched it.

    `'defecto'` when no rule applied, which is a reason too: it says the ladder
    had nothing to say about this board.
    """
    if not trace:
        return None
    return trace[0].split("=", 1)[0].split(":", 1)[0]


def adjustments(trace):
    """The names of the adjustments that ACTUALLY moved the score.

    An adjustment that fired without changing anything is recorded by the engine
    as `name(sin efecto)` and is not returned here: a test that asserts an
    adjustment applied means it wanted the number to move.
    """
    out = []
    for entry in trace[1:]:
        if "->" in entry:
            out.append(entry.split(":", 1)[0])
    return out


def assert_reason(trace, expected):
    """Fail unless `expected` is the rule that decided.

    The message prints the whole trace, because when this fails the useful
    information is which rule took over instead -- and that is one line away.
    """
    actual = reason(trace)
    assert actual == expected, (
        f"decidio '{actual}', se esperaba '{expected}'\n"
        f"  traza: {' | '.join(trace)}")


def assert_adjusted(trace, expected):
    """Fail unless `expected` moved the score after the rule fired."""
    moved = adjustments(trace)
    assert expected in moved, (
        f"el ajuste '{expected}' no movio la puntuacion "
        f"(movieron: {moved or 'ninguno'})\n"
        f"  traza: {' | '.join(trace)}")
