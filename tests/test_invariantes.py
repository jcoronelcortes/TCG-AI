"""Agent invariants with property-based testing (hypothesis).

Phase 5 of the strategy improvement architecture: instead of one fixture per
bug, hypothesis generates HUNDREDS of valid states (via the StateBuilder, which
guarantees consistency with deck.csv) and checks properties that must
hold in ALL of them:

  1. ROBUSTNESS: main.agent() never raises an exception or returns an invalid
     choice on arbitrary legal states (an exception in production
     is a forfeit: the game lost on the spot).
  2. APPLIN VETO: a 2nd energy is never attached to an Applin that already has
     one (the applin-max-una-energia memory), except for its documented
     exceptions (a complete evolution in hand / a Hydrapple ex in play),
     which the generators exclude on purpose.

`derandomize=True`: the examples are deterministic per code version
(the suite never "flakes"); if an invariant falls, hypothesis shrinks the
counterexample to the minimal state that violates it.

Requires `hypothesis` (pip install hypothesis).
"""

import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import main as m
from golden_corpus import reset_agente
from state_builder import C, G, Escenario, EstadoInconsistente, pk

KANGASKHAN = 756
CRUSTLE = 345
DWEBBLE = 344

# Our own roster WITHOUT Meganium (its Wild Growth doubles the effective energy and
# the synthetic specs with explicit arrays would become ambiguous) and WITHOUT
# Hydrapple ex (a documented exception to the Applin veto).
ROSTER_PROPIO = [m.Dipplin, m.Chikorita, m.Bayleef, m.Teal_Mask_Ogerpon_ex,
                 m.Tapu_Bulu, m.Meowth_ex]
ROSTER_RIVAL = [
    pk(KANGASKHAN, hp=160, max_hp=400, energias=[C, G], fisicas=2),
    pk(CRUSTLE, pre_evo=[DWEBBLE]),
    pk(DWEBBLE),
]

AJUSTES = dict(
    max_examples=60, deadline=None, derandomize=True,
    suppress_health_check=[HealthCheck.filter_too_much,
                           HealthCheck.too_slow])


def _eleccion_valida(obs, eleccion):
    sel = obs["select"]
    assert isinstance(eleccion, list), f"no es lista: {eleccion!r}"
    assert all(isinstance(i, int) for i in eleccion), f"indices no int: {eleccion!r}"
    assert sel["minCount"] <= len(eleccion) <= sel["maxCount"], (
        f"cantidad fuera de [{sel['minCount']},{sel['maxCount']}]: {eleccion}")
    assert all(0 <= i < len(sel["option"]) for i in eleccion), (
        f"indice fuera de rango: {eleccion} (n={len(sel['option'])})")
    assert len(set(eleccion)) == len(eleccion), f"indices repetidos: {eleccion}"


# ---------------------------------------------------------------------
# Invariant 1: robustness of the Ultra Ball fetch against arbitrary states
# ---------------------------------------------------------------------

@settings(**AJUSTES)
@given(
    activo_id=st.sampled_from([m.Dipplin, m.Applin, m.Chikorita,
                               m.Teal_Mask_Ogerpon_ex, m.Tapu_Bulu]),
    energias_activo=st.integers(min_value=0, max_value=2),
    banca=st.lists(st.sampled_from(ROSTER_PROPIO), max_size=3),
    mano=st.lists(st.sampled_from(
        [m.Basic_Grass_Energy, m.Lillie_Determination, m.Boss_Orders,
         m.Night_Stretcher, m.Dipplin]), max_size=3),
    mazo_extra=st.lists(st.sampled_from(
        [m.Hydrapple_ex, m.Tapu_Bulu, m.Meganium, m.Chikorita,
         m.Basic_Grass_Energy, m.Lillie_Determination, m.Ultra_Ball,
         m.Forest_of_Vitality]), max_size=6),
    rival=st.sampled_from(ROSTER_RIVAL),
    turno=st.integers(min_value=2, max_value=10),
)
def test_invariante_fetch_ub_robusto(activo_id, energias_activo, banca,
                                     mano, mazo_extra, rival, turno):
    reset_agente(m)
    try:
        esc = (Escenario(turno=turno, paso=1, tac=1)
               .mi_activo(pk(activo_id, energias=energias_activo))
               .mi_banca(*banca)
               .mi_mano(*mano)
               .op_activo(rival)
               .op_zonas(mano=5, mazo=30, premios=6)
               # the deck always carries a searchable Pokemon + random extras
               .mazo(m.Teal_Mask_Ogerpon_ex, *mazo_extra)
               .fetch_ultra_ball()
               .resto_al_descarte())
        obs = esc.construir()
    except EstadoInconsistente:
        assume(False)  # an impossible composition: discard the example
        return
    eleccion = m.agent(obs)
    _eleccion_valida(obs, eleccion)


# ---------------------------------------------------------------------
# Invariant 2: the veto on the Applin's 2nd energy (and MAIN menu robustness)
# ---------------------------------------------------------------------

@settings(**AJUSTES)
@given(
    applin_en_activo=st.booleans(),
    companiero=st.sampled_from(ROSTER_PROPIO),
    banca_extra=st.lists(st.sampled_from(ROSTER_PROPIO), max_size=2),
    energias_comp=st.integers(min_value=0, max_value=2),
    rival=st.sampled_from(ROSTER_RIVAL),
    turno=st.integers(min_value=2, max_value=10),
)
def test_invariante_applin_max_una_energia(applin_en_activo, companiero,
                                           banca_extra, energias_comp,
                                           rival, turno):
    reset_agente(m)
    applin = pk(m.Applin, energias=[G], fisicas=1)
    comp = pk(companiero, energias=energias_comp)
    try:
        esc = Escenario(turno=turno, paso=1, tac=0)
        if applin_en_activo:
            esc.mi_activo(applin).mi_banca(comp, *banca_extra)
            pos_applin = ("activo", None)
        else:
            esc.mi_activo(comp).mi_banca(applin, *banca_extra)
            pos_applin = ("banca", 0)
        obs = (esc
               .mi_mano(m.Basic_Grass_Energy)  # without Dipplin+Hydrapple: no
               # the complete-evolution-this-turn exception applies
               .op_activo(rival)
               .op_zonas(mano=5, mazo=30, premios=6)
               .menu_attach_energia()
               .construir())
    except EstadoInconsistente:
        assume(False)
        return
    eleccion = m.agent(obs)
    _eleccion_valida(obs, eleccion)

    opt = obs["select"]["option"][eleccion[0]]
    if opt.get("type") != 8:  # nothing attached (END): the veto was respected
        return
    if pos_applin[0] == "activo":
        es_applin = (opt.get("inPlayArea") == 4)
    else:
        es_applin = (opt.get("inPlayArea") == 5
                     and opt.get("inPlayIndex") == pos_applin[1])
    assert not es_applin, (
        f"2a energia adjuntada a un Applin que ya tenia una (sin Hydrapple "
        f"ex en juego ni evolucion completa en mano): {eleccion} -> {opt}")
