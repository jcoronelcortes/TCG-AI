"""Invariantes del agente con property-based testing (hypothesis).

Fase 5 de la arquitectura de mejora de estrategia: en vez de un fixture por
bug, hypothesis genera CIENTOS de estados validos (via el StateBuilder, que
garantiza consistencia con deck.csv) y verifica propiedades que deben
cumplirse en TODOS:

  1. ROBUSTEZ: main.agent() nunca lanza excepcion ni devuelve una eleccion
     invalida ante estados legales arbitrarios (una excepcion en produccion
     es un forfeit: partida perdida en el acto).
  2. VETO APPLIN: nunca se adjunta una 2a energia a un Applin que ya tiene
     una (memoria applin-max-una-energia), salvo sus excepciones
     documentadas (evolucion completa en mano / Hydrapple ex en juego),
     que los generadores excluyen a proposito.

`derandomize=True`: los ejemplos son deterministas por version del codigo
(la suite nunca "flakea"); si un invariante cae, hypothesis reduce el
contraejemplo al estado minimo que lo viola.

Requiere `hypothesis` (pip install hypothesis).
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

# Roster propio SIN Meganium (su Wild Growth duplica la energia efectiva y
# los specs sinteticos con arrays explicitos se volverian ambiguos) y SIN
# Hydrapple ex (excepcion documentada del veto Applin).
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
# Invariante 1: robustez del fetch de la Ultra Ball ante estados arbitrarios
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
               # el mazo siempre lleva un Pokemon buscable + extras al azar
               .mazo(m.Teal_Mask_Ogerpon_ex, *mazo_extra)
               .fetch_ultra_ball()
               .resto_al_descarte())
        obs = esc.construir()
    except EstadoInconsistente:
        assume(False)  # composicion imposible: descartar el ejemplo
        return
    eleccion = m.agent(obs)
    _eleccion_valida(obs, eleccion)


# ---------------------------------------------------------------------
# Invariante 2: veto a la 2a energia del Applin (y robustez del menu MAIN)
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
               .mi_mano(m.Basic_Grass_Energy)  # sin Dipplin+Hydrapple: no
               # aplica la excepcion de evolucion completa este turno
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
    if opt.get("type") != 8:  # no adjunto (END): el veto se respeto
        return
    if pos_applin[0] == "activo":
        es_applin = (opt.get("inPlayArea") == 4)
    else:
        es_applin = (opt.get("inPlayArea") == 5
                     and opt.get("inPlayIndex") == pos_applin[1])
    assert not es_applin, (
        f"2a energia adjuntada a un Applin que ya tenia una (sin Hydrapple "
        f"ex en juego ni evolucion completa en mano): {eleccion} -> {opt}")
