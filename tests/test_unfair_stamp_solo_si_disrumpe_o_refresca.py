"""Unfair Stamp: solo se juega si DISRUMPE o si el REFRESCO sale barato.

Escenario (`registros/registro_006_pasos_085_hasta_108.json`, episodio 89215128,
paso 99, turno 6 vs Marnie's Grimmsnarl, GANADA):

    NOSOTROS                                  RIVAL
    activo  Hydrapple ex 260/330              activo  Marnie's Morgrem
    banca   Ogerpon ex, Meowth ex,            mano    **1 carta**
            Dipplin, Fezandipiti ex,
            Ogerpon ex
    mano    **Unfair Stamp**, Meganium,
            Bayleef, Ultra Ball, Planta       (5 cartas contando el Sello)

El Sello es un ACE SPEC (Item) con un texto simetrico y caro:

    "Each player shuffles their hand into their deck. Then, you draw 5 cards
     and your opponent draws 2 cards."

De ahi que solo tenga DOS formas de pagar, y la regla (user, agosto 2026) exige
que se cumpla al menos una:

  (1) **DISRUPCION** -- existe unicamente si al rival le QUITA cartas. Como lo
      deja exactamente en 2, con la mano rival <= 2 no le quita nada; en este
      paso el rival tenia **1** carta y el Sello le REGALO una.
  (2) **REFRESCO** -- robamos 5, pero antes barajamos TODA nuestra mano. Sale a
      cuenta mientras lo que se sacrifica (la mano SIN el propio Sello) sea
      <= 4 cartas. En el paso 99 se sacrificaban 4 -> el Sello **si** se juega,
      y de hecho el registro lo juega ahi (y gana la partida).

La regla es de CARTA, no de matchup: el Sello se comporta igual contra
cualquier mazo, asi que no lleva ninguna whitelist. En el propio registro se ve
el patron que ahora queda escrito: con la mano a 10, 9, 8, 7 y 6 cartas el Sello
NO debia jugarse (rival con 1 carta y demasiada mano propia que quemar); en
cuanto la mano baja a 5 jugando items, la clausula (2) se cumple y se juega.

Efecto colateral que habia que cerrar: media docena de vetos de ORDEN le ceden
el turno al Sello (Boss's, Lillie's, Lana's, Dawn, Xerosic, la cadena
Meowth ex -> Last-Ditch Catch y la habilidad de Fezandipiti). Si el Sello se
veta y esos vetos siguen mirando solo "nos noquearon + sigue en mano", el turno
se PARALIZA: se cede el paso a una carta que ya no se va a jugar. Por eso todos
comparten ahora el mismo predicado, `_stamp_pendiente`.
"""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from parcheo import instalar

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step99_sello_solo_si_disrumpe_o_refresca.json")

STAMP = m.Unfair_Stamp
PLANTA = m.Basic_Grass_Energy


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _cargar():
    with open(_FIXTURE, encoding="utf-8") as f:
        datos = json.load(f)
    return (copy.deepcopy(datos["observacion_previa"]),
            copy.deepcopy(datos["observation"]))


def _decision(mano_extra=0, op_hand=None):
    """Corre la decision real del paso 99 y devuelve (eleccion, score del Sello).

    `mano_extra` engorda NUESTRA mano con Energias Planta muertas (la energia
    del turno ya esta adjuntada): son exactamente las cartas que el Sello
    barajaria al mazo. Se anaden al FINAL para no descolocar los `index` de las
    opciones PLAY del menu.
    """
    previa, dec = _cargar()
    yo = dec["current"]["yourIndex"]
    mio = dec["current"]["players"][yo]
    for k in range(mano_extra):
        mio["hand"].append({"id": PLANTA, "playerIndex": yo, "serial": 900 + k})
    mio["handCount"] = len(mio["hand"])
    if op_hand is not None:
        dec["current"]["players"][1 - yo]["handCount"] = op_hand

    visto = {}
    original = m._score_unfair_stamp_play

    def espia(ctx):
        r = original(ctx)
        visto["stamp"] = r
        return r

    _rest_score_unfair_stamp_play = instalar("_score_unfair_stamp_play", espia)
    try:
        m.agent(previa)                     # trae la ventana del KO rival
        eleccion = m.agent(dec)
    finally:
        _rest_score_unfair_stamp_play()
    return eleccion, visto.get("stamp")


def _juega_el_sello(obs_eleccion):
    """La opcion 0 del menu del paso 99 es PLAY del Unfair Stamp."""
    return obs_eleccion == [0]


def _ctx(op_hand, mano, stamp=1, ko=True):
    return SimpleNamespace(ko_last_turn=ko,
                           hand_counts={STAMP: stamp},
                           op_hand_count=op_hand,
                           my_hand_len=mano)


# ---------------------------------------------------------------------------
# 1. El registro: mano de 5 (se sacrifican 4) -> el Sello SE JUEGA
# ---------------------------------------------------------------------------

def test_el_menu_ofrecia_el_sello_y_el_rival_tenia_una_carta():
    _, dec = _cargar()
    yo = dec["current"]["yourIndex"]
    mano = [c["id"] for c in dec["current"]["players"][yo]["hand"]]
    assert mano[0] == STAMP and len(mano) == 5, mano
    assert dec["current"]["players"][1 - yo]["handCount"] == 1
    assert dec["select"]["option"][0]["type"] == int(m.OptionType.PLAY)


def test_refresco_barato_el_sello_se_juega_como_en_el_registro():
    eleccion, score = _decision()
    assert score > 0, score
    assert _juega_el_sello(eleccion), (
        "sacrificando solo 4 cartas el refresco (robar 5) paga por si solo, "
        f"aunque el rival no pierda nada; jugo {eleccion}")


# ---------------------------------------------------------------------------
# 2. La conducta nueva: sin disrupcion y con la mano grande, el Sello ESPERA
# ---------------------------------------------------------------------------

def test_sin_disrupcion_y_con_mano_grande_el_sello_se_veta():
    eleccion, score = _decision(mano_extra=1)      # se sacrificarian 5
    assert score <= 0, score
    assert not _juega_el_sello(eleccion), (
        "con el rival a 1 carta el Sello no disrumpe, y barajar 5 cartas "
        f"propias por 5 nuevas quema recursos ya jugables; jugo {eleccion}")


def test_con_la_mano_rival_larga_el_sello_vuelve_aunque_sacrifiquemos_mucho():
    """La clausula (1) es independiente: si DISRUMPE, da igual la mano propia."""
    eleccion, score = _decision(mano_extra=4, op_hand=m.STAMP_MIN_OP_HAND)
    assert score > 0, score
    assert _juega_el_sello(eleccion), eleccion


# ---------------------------------------------------------------------------
# 3. Los dos bordes exactos
# ---------------------------------------------------------------------------

def test_borde_de_la_mano_propia():
    """Sacrificar 4 pasa; sacrificar 5 ya no (mano = sacrificio + el Sello)."""
    assert m._sello_merece_jugarse(1, m.STAMP_MAX_HAND_SACRIFICADA + 1)
    assert not m._sello_merece_jugarse(1, m.STAMP_MAX_HAND_SACRIFICADA + 2)


def test_borde_de_la_mano_rival():
    """El Sello deja al rival en 2: con 2 no le quita nada, con 3 le quita 1."""
    mano_grande = m.STAMP_MAX_HAND_SACRIFICADA + 5
    assert not m._sello_merece_jugarse(m.STAMP_MIN_OP_HAND - 1, mano_grande)
    assert m._sello_merece_jugarse(m.STAMP_MIN_OP_HAND, mano_grande)


def test_sin_datos_no_inventa_jugadas():
    """La regla solo RESTA: sin `op_hand_count` a mano se comporta como antes."""
    assert m._sello_merece_jugarse(None, 99)
    assert m._sello_merece_jugarse(99, None)


# ---------------------------------------------------------------------------
# 4. Es regla de CARTA: mismo veto contra cualquier mazo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("matchup", ["op_is_alakazam_deck",
                                     "op_is_control_deck",
                                     "op_is_gardevoir_deck",
                                     "op_is_zoroark_deck",
                                     "op_is_aggro_deck"])
def test_el_veto_no_lo_resucita_ningun_bonus_de_matchup(matchup):
    """`_AJUSTES_STAMP_PLAY` bonifica jugadas que se van a hacer (+250..+400 por
    matchup); ninguna debe sacar el veto (-1) a numeros positivos."""
    ctx = _ctx(op_hand=1, mano=m.STAMP_MAX_HAND_SACRIFICADA + 2)
    for campo in ("op_is_alakazam_deck", "op_is_control_deck",
                  "op_is_slowking_deck", "op_is_gardevoir_deck",
                  "op_is_zoroark_deck", "op_is_aggro_deck",
                  "op_is_beedrill_deck"):
        setattr(ctx, campo, campo == matchup)
    ctx.state = SimpleNamespace(turn=3, supporterPlayed=False,
                                energyAttached=False)
    ctx.my_prize, ctx.op_prize = 4, 2
    ctx.hand_counts = {STAMP: 1, PLANTA: 0}
    ctx.forest_in_play = False
    assert m._score_unfair_stamp_play(ctx) <= 0


# ---------------------------------------------------------------------------
# 5. Un Sello vetado NO paraliza el turno
# ---------------------------------------------------------------------------

def test_el_sello_vetado_deja_de_bloquear_los_supporters():
    """`_stamp_pendiente` es la fuente unica de los vetos de orden (Boss's,
    Lillie's, Lana's, Dawn, Xerosic, cadena Meowth y Flip the Script)."""
    espera = _ctx(op_hand=1, mano=m.STAMP_MAX_HAND_SACRIFICADA + 2)
    assert not m._stamp_pendiente(espera)

    juega = _ctx(op_hand=1, mano=m.STAMP_MAX_HAND_SACRIFICADA + 1)
    assert m._stamp_pendiente(juega)


def test_sin_ko_el_sello_nunca_esta_pendiente():
    assert not m._stamp_pendiente(_ctx(op_hand=8, mano=3, ko=False))
    assert not m._stamp_pendiente(_ctx(op_hand=8, mano=3, stamp=0))
