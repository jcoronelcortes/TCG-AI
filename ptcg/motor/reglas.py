"""Rules engine: fixed rules, adjustments and scenario resolution.

Extracted VERBATIM from main.py by utils/extraer_definiciones.py
(docs/project-history.md). Its purity is verified by
utils/pureza.py: nothing here touches mutable state or the runtime tables.
"""

import os


class _ReglaFija:
    __slots__ = ("nombre", "cuando", "valor")

    def __init__(self, nombre, cuando, valor):
        self.nombre = nombre
        self.cuando = cuando  # ctx -> bool
        self.valor = valor    # ctx -> score


class _Ajuste:
    __slots__ = ("nombre", "cuando", "aplicar")

    def __init__(self, nombre, cuando, aplicar):
        self.nombre = nombre
        self.cuando = cuando    # (ctx, score) -> bool
        self.aplicar = aplicar  # (ctx, score) -> score


def _resolver_reglas(reglas, ajustes, ctx, defecto):
    """Returns (score, trace). First rule that applies + adjustments, in order."""
    traza = []
    score = defecto
    for r in reglas:
        if r.cuando(ctx):
            score = r.valor(ctx)
            traza.append(f"{r.nombre}={score}")
            break
    else:
        traza.append(f"defecto={defecto}")
    for a in ajustes:
        if a.cuando(ctx, score):
            nuevo = a.aplicar(ctx, score)
            traza.append(f"{a.nombre}:{score}->{nuevo}" if nuevo != score
                         else f"{a.nombre}(sin efecto)")
            score = nuevo
    return score, traza


def _resolver_con_traza(etiqueta, reglas, ajustes, ctx, defecto):
    score, traza = _resolver_reglas(reglas, ajustes, ctx, defecto)
    if os.environ.get("PTCG_DEBUG"):
        print(f"[reglas {etiqueta}]", " | ".join(traza))
    return score


def _resolver_max(escenarios, ctx):
    """ARGMAX mode of the engine: evaluates ALL scenarios (same shape as
    _ReglaFija) and returns (best_value, trace). Unlike the
    first-one-that-applies chain, here every scenario that fires competes and
    the highest value wins (0 if none fires). For accumulators of the form
    `best = max(best, ...)` over independent scenarios."""
    mejor, ganador, disparados = 0, None, 0
    for e in escenarios:
        if e.cuando(ctx):
            disparados += 1
            v = e.valor(ctx)
            if v > mejor:
                mejor, ganador = v, e.nombre
    traza = (f"max:{ganador}={mejor} ({disparados} candidatos)"
             if ganador else "max:ninguno=0")
    return mejor, traza


def _E(nombre, cuando, valor):
    return _ReglaFija(nombre, cuando,
                      valor if callable(valor) else (lambda c, _v=valor: _v))

__all__ = [
    '_ReglaFija',
    '_Ajuste',
    '_resolver_reglas',
    '_resolver_con_traza',
    '_resolver_max',
    '_E',
]
