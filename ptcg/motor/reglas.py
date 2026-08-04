"""Rules engine: fixed rules, adjustments and scenario resolution.

Extracted VERBATIM from main.py by utils/extraer_definiciones.py
(docs/project-history.md). Its purity is verified by
utils/pureza.py: nothing here touches mutable state or the runtime tables.
"""

import os


class _FixedRule:
    __slots__ = ("name", "when", "value")

    def __init__(self, name, when, value):
        self.name = name
        self.when = when  # ctx -> bool
        self.value = value    # ctx -> score


class _Adjustment:
    __slots__ = ("name", "when", "apply")

    def __init__(self, name, when, apply):
        self.name = name
        self.when = when    # (ctx, score) -> bool
        self.apply = apply  # (ctx, score) -> score


def _resolve_rules(rules, adjustments, ctx, default):
    """Returns (score, trace). First rule that applies + adjustments, in order."""
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
    score, traza = _resolve_rules(rules, adjustments, ctx, default)
    if os.environ.get("PTCG_DEBUG"):
        print(f"[reglas {etiqueta}]", " | ".join(traza))
    return score


def _resolve_max(escenarios, ctx):
    """ARGMAX mode of the engine: evaluates ALL scenarios (same shape as
    _ReglaFija) and returns (best_value, trace). Unlike the
    first-one-that-applies chain, here every scenario that fires competes and
    the highest value wins (0 if none fires). For accumulators of the form
    `best = max(best, ...)` over independent scenarios."""
    best, winner, disparados = 0, None, 0
    for e in escenarios:
        if e.when(ctx):
            disparados += 1
            v = e.value(ctx)
            if v > best:
                best, winner = v, e.name
    traza = (f"max:{winner}={best} ({disparados} candidatos)"
             if winner else "max:ninguno=0")
    return best, traza


def _E(name, when, value):
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
