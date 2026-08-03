"""Objetivo del gusteo SIN KO: sube el cuerpo que NO puede atacar.

Tercera pieza de la familia de [[boss-no-regalar-la-linea-alakazam]]. Las dos
anteriores arreglaron CUANDO se juega Boss's Orders; esta arregla A QUIEN sube
cuando ya se juega y no hay KO.

Las dos bandas de `_gust_linea_rival` puntuaban al reves:

  * `_gust_linea_evolutiva` da **800 a la EVOLUCION FINAL** (Dragapult ex,
    Typhlosion, Alakazam) sin KO -- por encima de los 700 de la Fase 1 clavada,
    que su PROPIO docstring llama "mejor objetivo de disrupcion";
  * `_gust_tiers_genericos` da **250 a un ex ENERGIZADO**, el techo de su banda
    sin KO, por encima de cualquier cuerpo trabado.

Sin KO eso es ponerle delante -- y gratis, porque Boss's le paga la retirada --
justo el cuerpo con el que queria atacar. Y contradecia al detector que
JUSTIFICA la jugada: el gusteo DEFENSIVO (`_bo_defensive_gust`, 940) vale porque
EXISTE en su banca un cuerpo que no puede rematarnos... y despues el selector
subia otro.

`sin_ko_prefiere_cuerpo_muerto` (+1500, en los DOS modos) pone por delante al
cuerpo que no puede pagar su ataque ni adjuntandole una energia. +1500 supera
toda la banda sin KO (100-1200) y no toca los tiers de KO (>= 3000), que van
gateados por `can_ko`.

`GUST_TRAMPA_IDS` es la excepcion obligatoria: Crustle, Sylveon, Cornerstone e
Iron Thorns ex tienen ataques de **coste 3**, asi que pelados pasan por
"inofensivos" -- y son justo los cuerpos que NO queremos delante (anulan a
nuestros atacantes o apagan nuestras habilidades desde el activo).

Corpus dorado: 0 flips (los registros locales apenas llegan al prompt de
objetivo), por eso el escenario se FABRICA con StateBuilder.
"""

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Escenario, pk, G

DRAGAPULT, DRAKLOAK, DREEPY = m.Dragapult_ex, m.Drakloak, m.Dreepy
DUSCLOPS = m.Dusclops
BAYLEEF, CHIKORITA = m.Bayleef, m.Chikorita


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


def _stub(card_id, energia=0):
    """Pokemon minimo que entienden `prize_count_op` y `_op_cuerpo_inofensivo`."""
    return SimpleNamespace(id=card_id, energies=[1] * energia,
                           energyCards=[], tools=[])


def _ctx(card_id, energia=0, can_ko=False, op_linea_dragapult=False):
    """`_CtxGustObjetivo` con los datos DERIVADOS de la carta real, para que el
    test no se quede pegado a numeros inventados."""
    d = m.card_table.get(card_id)
    return m._CtxGustObjetivo(
        card_id=card_id, energia=energia,
        rc0=m.RETREAT_COST.get(card_id, 0), rc1=m.RETREAT_COST.get(card_id, 1),
        stall_diff=m.RETREAT_COST.get(card_id, 0) - energia,
        is_ex=bool(getattr(d, 'ex', False)), is_exmega=bool(getattr(d, 'ex', False)),
        is_megaex=bool(getattr(d, 'megaEx', False)),
        prizes=m.prize_count_op(_stub(card_id, energia)),
        wins_now=False,
        is_stage1=bool(getattr(d, 'stage1', False)),
        is_stage2=bool(getattr(d, 'stage2', False)),
        tiene_tool=False, can_ko=can_ko, tier_ko=5 if can_ko else 0,
        plan_target_match=False, regust_energized=False,
        linea_rank=0, linea_can_ko=False, op_alakazam=False,
        op_latias=False, op_linea_dragapult=op_linea_dragapult,
        op_linea_typhlosion=False,
        cuerpo_inofensivo=m._op_cuerpo_inofensivo(_stub(card_id, energia)))


def _ofensivo(ctx):
    score, _ = m._resolver_reglas([], m._AJUSTES_GUST_OFENSIVO, ctx, defecto=0)
    return score


def _estorbo(ctx):
    score, _ = m._resolver_reglas(m._REGLAS_GUST_ESTORBO,
                                 m._AJUSTES_GUST_ESTORBO, ctx, defecto=-200)
    return score


# ---------------------------------------------------------------------------
# 1. La banda vieja prefería la pieza más gorda: el control del test
# ---------------------------------------------------------------------------

def test_la_banda_sin_ko_premiaba_a_la_evolucion_final():
    """`_gust_linea_evolutiva` sigue dando 800 al final y 700 a la Fase 1
    clavada: la contribucion NO se ha tocado, se ha superpuesto."""
    final = m._gust_linea_evolutiva(_ctx(DRAGAPULT, energia=1),
                                    DRAGAPULT, DRAKLOAK, DREEPY)
    medio = m._gust_linea_evolutiva(_ctx(DRAKLOAK), DRAGAPULT, DRAKLOAK, DREEPY)
    assert final == 800 and medio == 700


# ---------------------------------------------------------------------------
# 2. Modo OFENSIVO
# ---------------------------------------------------------------------------

def test_sin_ko_el_cuerpo_muerto_gana_a_la_evolucion_final():
    # Su 2o Dragapult ex con 1 energia YA ataca (Jet Headbutt cuesta 1).
    atacante = _ctx(DRAGAPULT, energia=1, op_linea_dragapult=True)
    # El Dusclops pelado no puede pagar su ataque de coste 2.
    muerto = _ctx(DUSCLOPS, op_linea_dragapult=True)
    assert not atacante.cuerpo_inofensivo and muerto.cuerpo_inofensivo
    assert _ofensivo(muerto) > _ofensivo(atacante)


def test_con_ko_mandan_los_tiers_y_el_cuerpo_muerto_no_los_pisa():
    """El bono va gateado por `not can_ko`: noquear un ex de 2 premios sigue
    ganando a subir un cuerpo muerto."""
    ko_ex = _ctx(DRAGAPULT, energia=1, can_ko=True, op_linea_dragapult=True)
    muerto = _ctx(DUSCLOPS, op_linea_dragapult=True)
    assert _ofensivo(ko_ex) > _ofensivo(muerto)


def test_los_muros_y_el_locker_no_cobran_el_bono():
    """Coste 3 => pelados pasan por inofensivos, pero subirlos es la trampa:
    anulan a nuestros atacantes o apagan nuestras habilidades desde el activo."""
    for trampa in sorted(m.GUST_TRAMPA_IDS):
        c = _ctx(trampa)
        assert c.cuerpo_inofensivo, f"{trampa} deberia ser 'inofensivo' por coste"
        sin_bono = _ofensivo(c)
        assert sin_bono < _ofensivo(_ctx(DUSCLOPS)), (
            f"{trampa} esta en GUST_TRAMPA_IDS: no puede cobrar los +1500")


# ---------------------------------------------------------------------------
# 3. Modo ESTORBO
# ---------------------------------------------------------------------------

def test_estorbo_desempata_hacia_el_que_no_puede_atacar():
    """`traba_neta` solo mira quien no puede pagar su RETIRADA. Con la misma
    traba (ambos retirada 2, sin energia), decide quien no puede pagar su
    ATAQUE: el Gardevoir ex ataca por 1, el Dusclops necesita 2."""
    assert m.RETREAT_COST[m.Gardevoir_ex] == m.RETREAT_COST[DUSCLOPS] == 2
    ataca = _ctx(m.Gardevoir_ex)
    muerto = _ctx(DUSCLOPS)
    assert not ataca.cuerpo_inofensivo and muerto.cuerpo_inofensivo
    assert _estorbo(muerto) > _estorbo(ataca)


def test_estorbo_no_rescata_un_objetivo_prohibido():
    """El guard `s > 0`: un Budew (retirada gratis) sigue PROHIBIDO aunque el
    bono existiera."""
    assert _estorbo(_ctx(m.Budew)) == m.SCORE_FORBID


# ---------------------------------------------------------------------------
# 4. El tablero completo
# ---------------------------------------------------------------------------

def _tablero(energias_activo):
    """Bayleef activo (60 de dano: no noquea nada del tablero) contra un
    Dragapult ex. En su banca, otro Dragapult ex con 1 energia -- listo para
    atacar -- y un Dusclops pelado."""
    return (Escenario(turno=8, paso=80, tac=4, premios_propios=4)
            .mi_activo(pk(BAYLEEF, energias=[G] * energias_activo,
                          fisicas=energias_activo, pre_evo=[CHIKORITA]))
            .mi_banca(pk(CHIKORITA))
            .op_activo(pk(DRAGAPULT, hp=320, max_hp=320, energias=[G, G]))
            .op_banca(pk(DRAGAPULT, hp=320, max_hp=320, energias=[G]),
                      pk(DUSCLOPS, hp=90, max_hp=90))
            .op_zonas(mano=5, mazo=25, premios=4)
            .mazo()
            # `menu_gusteo()` consume una Boss's Orders del pool (la carta "en
            # efecto"), asi que va ANTES de `resto_al_descarte()`.
            .menu_gusteo()
            .resto_al_descarte()
            .construir())


def test_el_tablero_sintetico_no_tiene_ningun_ko():
    obs = _tablero(2)
    assert m.ATTACK_ENERGY_REQ[BAYLEEF] == 2      # con 2 energias SI ataca
    # 60 de dano no noquea ni al Dragapult ex (320) ni al Dusclops (90).
    riv = obs["current"]["players"][1]
    assert [p["hp"] for p in riv["bench"]] == [320, 90]
    # El menu ofrece los dos cuerpos de su banca.
    assert [o["index"] for o in obs["select"]["option"]] == [0, 1]


def test_se_sube_el_dusclops_y_no_el_segundo_dragapult():
    assert m.agent(copy.deepcopy(_tablero(2))) == [1], (
        "con nuestro activo atacando pero sin KO, subir su 2o Dragapult ex le "
        "pone delante el cuerpo con el que ataca; el Dusclops pelado no puede")


def test_en_modo_estorbo_tambien():
    assert m.agent(copy.deepcopy(_tablero(1))) == [1]
