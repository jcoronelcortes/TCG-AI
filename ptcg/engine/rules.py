"""Rules engine: fixed rules, adjustments and scenario resolution.

This is the VOCABULARY the whole `ptcg/decision/` layer is written in. A
decision here is never an `if/elif` ladder buried in a scorer: it is a LIST of
named rules, walked by one of the two resolvers below. That shape is what makes
the agent auditable -- `utils/rule_census.py` can walk every list and report
which rules ever fire, and `tests/rule_trace.py` can name the rule that decided
a given board. An `if` chain answers "what score", a rule list also answers
"WHICH RULE", and every measurement discipline in this repository depends on
that second answer.

THE TWO SHAPES A DECISION CAN TAKE

  * CHAIN (`_resolve_rules`) -- first rule whose `when` is true wins, the rest
    are never consulted, and `default` applies if none fires. This is the
    normal shape: the list is a PRIORITY ORDER, so the specific case is written
    above the general one. Related: the ordering trap is the most common defect
    in this repository -- a sound rule placed above a decisive one vetoes it
    (see `ptcg/turn/game_plan.py` for the loss that produced the turn plan).

  * ARGMAX (`_resolve_max`) -- every scenario is evaluated and the HIGHEST value
    wins. For accumulators of the form `best = max(best, ...)` over independent
    scenarios, where order must NOT matter. Note the asymmetry the census cares
    about: in a chain a rule below one that fires is dead code, in an argmax
    every rule is always asked.

AFTER the winner is picked, the `adjustments` run IN ORDER, each one free to
rewrite the score it receives. A rule answers "what is this worth"; an
adjustment answers "...but given the rest of the board, more or less than
that". Both halves are named, so both halves show up in the trace.

THE TRACE is the reason the resolvers return a second value nobody scores on.
Set `PTCG_DEBUG` and `_resolve_with_trace` prints the rule that fired and every
adjustment that touched the score, which is how a surprising decision gets read
back without a debugger.

Naming convention across the package: the rule lists are `_RULES_<topic>`, the
adjustment lists `_ADJUST_<topic>`, the predicates that make up a rule
`_v_<topic>_<case>`, and the context each one reads is a small `_Ctx*` object
built by a `_ctx_<topic>` function. A scorer PRICES an option and never writes
state -- rule R9 of `utils/lint_architecture.py` enforces it.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

import os


class _FixedRule:
    """One named rung of a decision: "in THIS case, the option is worth THAT".

    `name` is not decoration. It is what the trace prints, what
    `utils/rule_census.py` counts, and what a test asserts on when it wants to
    pin the rule that decided rather than the number it produced -- a score can
    be retuned without the decision changing, so a test written against the
    name survives the retune.

    In a CHAIN the position in the list is the priority; in an ARGMAX
    (`_resolve_max`) the position means nothing and only `value` competes.
    """

    __slots__ = ("name", "when", "value")

    def __init__(self, name, when, value):
        self.name = name
        self.when = when  # ctx -> bool: does this rule apply to the board?
        self.value = value    # ctx -> score: what the option is worth if it does


class _Adjustment:
    """A correction applied AFTER a rule has priced the option.

    The difference from `_FixedRule` is what each one gets to see: a rule reads
    the board and produces a score from nothing, an adjustment reads the board
    AND the score already on the table, and rewrites it. Use it for "worth this
    much, but not while X" -- a modifier that would otherwise have to be copied
    into every rung of the chain.

    Unlike rules, adjustments do NOT stop at the first match: every one whose
    `when` holds runs, in list order, each seeing the previous one's output.
    """

    __slots__ = ("name", "when", "apply")

    def __init__(self, name, when, apply):
        self.name = name
        self.when = when    # (ctx, score) -> bool: should this correction run?
        self.apply = apply  # (ctx, score) -> score: the corrected score


def _resolve_rules(rules, adjustments, ctx, default):
    """Walk a rule CHAIN: the first rule that applies decides, then adjust.

    The workhorse resolver. Rules are consulted in order and the walk STOPS at
    the first `when` that holds, so a list is a priority order and anything
    below a rule that always fires is dead code. If none fires the option is
    worth `default`. Every adjustment then runs in order on the surviving score.

    Returns `(score, trace)`, where the trace names the rule that decided and
    every adjustment that moved the number. Callers that only want the score go
    through `_resolve_with_trace`; tests and censuses read the trace.
    """
    traza = []
    score = default
    for r in rules:
        if r.when(ctx):
            score = r.value(ctx)
            traza.append(f"{r.name}={score}")
            break
    else:
        traza.append(f"defecto={default}")
    for a in adjustments:
        if a.when(ctx, score):
            nuevo = a.apply(ctx, score)
            traza.append(f"{a.name}:{score}->{nuevo}" if nuevo != score
                         else f"{a.name}(sin efecto)")
            score = nuevo
    return score, traza


def _resolve_with_trace(etiqueta, rules, adjustments, ctx, default):
    """`_resolve_rules` for callers that want the score and, on demand, the why.

    The score is all that is returned; the trace is PRINTED instead, and only
    when `PTCG_DEBUG` is set in the environment. `etiqueta` is the heading that
    identifies which decision the printed line belongs to, since a single turn
    resolves dozens of them.
    """
    score, traza = _resolve_rules(rules, adjustments, ctx, default)
    if os.environ.get("PTCG_DEBUG"):
        print(f"[reglas {etiqueta}]", " | ".join(traza))
    return score


def _resolve_max(scenarios, ctx):
    """ARGMAX mode of the engine: evaluates ALL scenarios (same shape as
    _FixedRule) and returns (best_value, trace). Unlike the
    first-one-that-applies chain, here every scenario that fires competes and
    the highest value wins (0 if none fires). For accumulators of the form
    `best = max(best, ...)` over independent scenarios."""
    best, winner, disparados = 0, None, 0
    for e in scenarios:
        if e.when(ctx):
            disparados += 1
            v = e.value(ctx)
            if v > best:
                best, winner = v, e.name
    traza = (f"max:{winner}={best} ({disparados} candidatos)"
             if winner else "max:ninguno=0")
    return best, traza


def _E(name, when, value):
    """Build a rule whose `value` may be a plain number instead of a callable.

    Most rules are worth a CONSTANT, and writing `lambda c: 300` at every rung
    buries the number in noise. `_E` accepts either and wraps the constant, so
    a list of rules reads as a table of scores. The default argument binding
    (`_v=value`) is what keeps each wrapped constant its own -- a bare closure
    over the loop variable would give every rule the last value.
    """
    return _FixedRule(name, when,
                      value if callable(value) else (lambda c, _v=value: _v))

__all__ = [
    '_FixedRule',
    '_Adjustment',
    '_resolve_rules',
    '_resolve_with_trace',
    '_resolve_max',
    '_E',
]
