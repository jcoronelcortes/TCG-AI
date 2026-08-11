"""A rule can be dead in four different ways, and only one of them is obvious.

THE BUG THIS COMES FROM. `_protect_last_supporter` was gated on `not
state.supporterPlayed`, and Xerosic's Machinations IS a Supporter, so on every
forced discard that card can produce the flag was already True. It was not
misfiring; it was UNREACHABLE, and it had been since the day it was written.
Reviving it (93a27eb) exposed two further defects that had been hiding behind
it. Every ingredient needed to find it was already in the repository --- each
rule carries a NAME, and every chain resolves through one choke point in
`ptcg/engine/rules.py` --- and nobody counted.

`utils/rule_census.py` counts. This file pins the part of it that decides what
a number MEANS, because that is where a census of this shape goes wrong: not in
the counting, in the reading.

THE FOUR WAYS, and why they are not the same finding:

  * the CHAIN never ran at all --- says nothing about the rule, everything
    about the workload;
  * the chain ran and the rule was NEVER EVALUATED --- something above it always
    decides first. Dead by ORDERING, and the fix is usually to move it;
  * it was evaluated and NEVER FIRED --- its condition never held on a real
    board. Dead by CONDITION. This is the `_protect_last_supporter` band;
  * it fired and never decided --- alive, but never load-bearing.

AND THE ONE THAT ALREADY BIT. In an ARGMAX chain (`_resolve_max`) EVERY rule
that fires calls `value`, so a `value` call there does not mean the rule
decided --- it means it competed. The first run of the census's own self-test
failed on exactly that: `_ESC_NS_RECUPERACION.energia_teal_dance` was flagged as
having "decided" while the bands, correctly, called it a rule that always loses.
The self-test caught the detector, which is what a self-test is for, and
`Contadores.mando()` is the repair. The last test here is the one that would
notice if that distinction were ever flattened again.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from rule_census import Contadores, Registro, bandas


class ReglaFalsa:
    """Stands in for `_FixedRule`/`_Adjustment`: the bands only read the counters."""

    def __init__(self, name):
        self.name = name


def _registro(**reglas):
    """reglas: name -> (kind, dict of counter values)."""
    registro = Registro()
    for nombre, (kind, valores) in reglas.items():
        regla = ReglaFalsa(nombre)
        registro.anota(regla, "prueba", "_RULES_PRUEBA", 0, kind)
        contador = registro.contador(regla)
        for campo, valor in valores.items():
            setattr(contador, campo, valor)
    return registro


def _banda_de(registro, nombre):
    for banda, claves in bandas(registro).items():
        for clave in claves:
            if registro.donde[clave][3] == nombre:
                return banda
    return None


def test_una_cadena_que_nunca_corre_no_acusa_a_sus_reglas():
    # The workload never reached this scorer. That is a fact about the games
    # played, not about the rule, and it has to be readable as such.
    registro = _registro(pinsir=("regla", dict(cadena=0)))
    assert _banda_de(registro, "pinsir") == "CADENA NUNCA RESUELTA"


def test_la_regla_que_nadie_llega_a_preguntar_es_muerta_por_ORDEN():
    registro = _registro(tapada=("regla", dict(cadena=890, evaluada=0)))
    assert _banda_de(registro, "tapada") == "NUNCA EVALUADA"


def test_la_regla_preguntada_que_nunca_dispara_es_la_del_bug():
    # `_protect_last_supporter` in miniature: asked on every single resolution,
    # true on none of them.
    registro = _registro(protege=("regla", dict(cadena=1309, evaluada=1309, disparada=0)))
    assert _banda_de(registro, "protege") == "EVALUADA, NUNCA DISPARA"


def test_la_regla_que_dispara_y_siempre_pierde_en_una_cadena():
    registro = _registro(perdedora=("regla", dict(cadena=100, evaluada=100,
                                                  disparada=7, decidio=0)))
    assert _banda_de(registro, "perdedora") == "DISPARA, NUNCA DECIDE"


def test_una_regla_que_decide_no_sale_en_ninguna_banda():
    # The specificity half. A detector that reports a live rule reports noise,
    # and noise here costs a rule somebody then deletes.
    registro = _registro(viva=("regla", dict(cadena=100, evaluada=100,
                                             disparada=40, decidio=40)))
    assert _banda_de(registro, "viva") is None


def test_un_ajuste_que_siempre_aplica_y_nunca_cambia_el_score():
    # Its own band: an adjustment that returns what it was given every time is a
    # rule nobody applies, and it reads as alive on every other counter.
    registro = _registro(inerte=("ajuste", dict(cadena=164, evaluada=164,
                                                disparada=164, decidio=164, cambio=0)))
    assert _banda_de(registro, "inerte") == "DISPARA, NUNCA CAMBIA EL SCORE"

    registro = _registro(util=("ajuste", dict(cadena=164, evaluada=164,
                                              disparada=164, decidio=164, cambio=9)))
    assert _banda_de(registro, "util") is None


def test_en_ARGMAX_llamar_a_value_no_es_decidir():
    # The one the census's own self-test caught. In a max chain every rule that
    # fires calls `value`; only the winner decides. Read `decidio` as a decision
    # there and a rule that always loses looks alive.
    compite = dict(cadena=224, evaluada=224, disparada=8, decidio=8, gano=0, modo="max")
    registro = _registro(pierde_siempre=("regla", compite))
    assert _banda_de(registro, "pierde_siempre") == "DISPARA, NUNCA GANA"
    assert registro.contador(next(iter(registro.objetos.values()))).mando() == 0

    gana = dict(compite, gano=3)
    registro = _registro(a_veces_gana=("regla", gana))
    assert _banda_de(registro, "a_veces_gana") is None


def test_cada_regla_cae_en_una_sola_banda():
    # Bands that overlap turn a worklist into a guess about which line to read.
    registro = _registro(
        muda=("regla", dict(cadena=10, evaluada=10, disparada=0)),
        tapada=("regla", dict(cadena=10, evaluada=0)),
        sin_cadena=("regla", dict(cadena=0)),
        maxima=("regla", dict(cadena=10, evaluada=10, disparada=2, decidio=2, modo="max")),
    )
    todas = [clave for claves in bandas(registro).values() for clave in claves]
    assert len(todas) == len(set(todas)) == 4
