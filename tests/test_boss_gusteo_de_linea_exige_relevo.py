"""Gusteo de LINEA EVOLUTIVA sin KO: solo si RELEVA a un atacante.

Generalizacion de [[boss-no-regalar-la-linea-alakazam]] (registro_002 paso 20) a
los otros seis mazos de linea. `evaluate_supporters` tenia seis ramas gemelas que
pagaban 690-730 por Boss's Orders **por el mero hecho de que hubiera una pieza de
su linea en la banca rival**, sin exigir NINGUN KO:

    op_has_dreepy_line          700   si `bench_stage > active_stage`
    op_has_typhlosion/ethan     700   si `bench_stage > active_stage`
    op_is_gardevoir_deck        730   si hay un Ralts/Kirlia en banca
    op_is_slowking_deck         710   si hay un Slowpoke en banca
    op_is_dragapult_dusknoir    700   si hay un Duskull/Dusclops en banca
    op_is_zoroark_deck          690   si hay un Zorua en banca

Las dos primeras eran las peores: `bench_stage > active_stage` PREFIERE subir la
pieza mas evolucionada, que es justo la que el rival quiere delante para
evolucionarla y atacar con ella. El caso limpio esta en el test de abajo: con su
**Dragapult ex atacando** y un **Drakloak** en la banca, el codigo viejo gastaba
el Supporter en cambiar el uno por el otro -- y el Drakloak evoluciona a otro
Dragapult ex en el activo.

Ahora las seis pasan por `_gust_releva_al_atacante`: sin KO, un gusteo solo le
cuesta un turno al rival cuando cambia un cuerpo que ATACA por uno que no puede
pagar su ataque. Se descartan como relevo los Dunsparce (objetivo prohibido) y
las pre-evoluciones de amenaza (evolucionan EN EL ACTIVO y atacan con el cuerpo
nuevo). Los gusteos que SI cobran siguen puntuandose aparte, con el KO ya
comprobado: `_bo_deny_evo_target` (965), `_bo_gust_key_bench` (975),
`_boss_ko_ex_value` (985) y `_boss_prize_rank`.

El predicado se mide por COSTE de ataque y nunca por dano: el dano IMPRESO miente
en este entorno -- Powerful Hand (Alakazam), Cruel Arrow (Fezandipiti ex) y los
dos ataques de Gardevoir ex figuran con 0 en `attack_table`.

Corpus dorado: 0 flips (ningun registro local tiene un tablero de estas lineas
con el gusteo en juego), por eso el escenario se FABRICA con StateBuilder.
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

OGERPON = m.Teal_Mask_Ogerpon_ex
BOSS = m.Boss_Orders
DRAGAPULT, DRAKLOAK, DREEPY = m.Dragapult_ex, m.Drakloak, m.Dreepy
DUSCLOPS = m.Dusclops
DUNSPARCE = 305


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


def _pkm(card_id, energias=0):
    return SimpleNamespace(id=card_id, energies=[1] * energias)


def _op(activo, banca):
    return SimpleNamespace(active=[activo] if activo else [], bench=list(banca))


# ---------------------------------------------------------------------------
# 1. El predicado de cuerpo: por COSTE, nunca por dano impreso
# ---------------------------------------------------------------------------

def test_el_dano_impreso_miente_y_por_eso_se_mide_el_coste():
    """Tres ataques REALES figuran con dano 0 en `attack_table`. Si el predicado
    mirase el dano, los tres cuerpos pasarian por inofensivos."""
    for cid in (m.Alakazam_ex, m.Fezandipiti_ex, m.Gardevoir_ex):
        datos = m.card_table[cid]
        assert all((m.attack_table[a].damage or 0) == 0 for a in datos.attacks)

    # Powerful Hand cuesta 1: un Alakazam pelado ataca en su proximo turno.
    assert not m._op_cuerpo_inofensivo(_pkm(m.Alakazam_ex, 0))
    # Cruel Arrow cuesta 3: un Fezandipiti ex pelado, no.
    assert m._op_cuerpo_inofensivo(_pkm(m.Fezandipiti_ex, 0))
    assert not m._op_cuerpo_inofensivo(_pkm(m.Fezandipiti_ex, 2))


def test_cuerpo_inofensivo_es_conservador_con_lo_que_no_sabe():
    assert not m._op_cuerpo_inofensivo(None)
    assert not m._op_cuerpo_inofensivo(_pkm(-12345, 0))     # carta desconocida
    # Budew ataca por coste 0: nunca es inofensivo.
    assert not m._op_cuerpo_inofensivo(_pkm(m.Budew, 0))
    # Una carta SIN `energies` (lo que puede devolver `get_card` fuera del
    # campo) no puede reventar: una excepcion en `agent()` es forfeit.
    assert not m._op_cuerpo_inofensivo(SimpleNamespace(id=m.Boss_Orders))
    assert m._op_cuerpo_inofensivo(SimpleNamespace(id=m.Fezandipiti_ex))


# ---------------------------------------------------------------------------
# 2. El relevo generico
# ---------------------------------------------------------------------------

def test_relevo_exige_atacante_delante_y_cuerpo_muerto_detras():
    # Su Dragapult ex ataca (Jet Headbutt cuesta 1) y el Dusclops de banca no
    # puede pagar su ataque de coste 2: cambiar uno por otro les cuesta el turno.
    assert m._gust_releva_al_atacante(
        _op(_pkm(DRAGAPULT, 1), [_pkm(DUSCLOPS)]))
    # Si su activo ya no ataca no hay nada que relevar (y el gusteo ademas le
    # regala la retirada gratis).
    assert not m._gust_releva_al_atacante(
        _op(_pkm(m.Fezandipiti_ex, 0), [_pkm(DUSCLOPS)]))


def test_una_preevo_de_amenaza_no_es_relevo():
    """El Drakloak no puede atacar hoy, pero evoluciona EN EL ACTIVO a otro
    Dragapult ex y ataca con el: es el mismo error del Abra -> Kadabra."""
    assert DRAKLOAK in m.EX_PREEVO_IDS
    assert not m._gust_releva_al_atacante(
        _op(_pkm(DRAGAPULT, 1), [_pkm(DRAKLOAK)]))
    # ...pero si detras hay ADEMAS un cuerpo muerto de verdad, el relevo existe.
    assert m._gust_releva_al_atacante(
        _op(_pkm(DRAGAPULT, 1), [_pkm(DRAKLOAK), _pkm(DUSCLOPS)]))


def test_dunsparce_nunca_es_relevo():
    assert not m._gust_releva_al_atacante(
        _op(_pkm(DRAGAPULT, 1), [_pkm(DUNSPARCE)]))


# ---------------------------------------------------------------------------
# 3. El tablero completo: la rama `op_has_dreepy_line`
# ---------------------------------------------------------------------------

def _tablero(banca_extra=()):
    """Nuestro turno sin atacante (Ogerpon ex a 1/3) y con Boss's Orders como
    unica carta de la mano: el menu es PLAY Boss's | END."""
    return (Escenario(turno=6, paso=70, tac=2, premios_propios=5)
            .mi_activo(pk(OGERPON, energias=[G], fisicas=1))
            .mi_banca(pk(OGERPON))
            .op_activo(pk(DRAGAPULT, hp=320, max_hp=320, energias=[G]))
            .op_banca(*([pk(DRAKLOAK, hp=90, max_hp=90)] + list(banca_extra)))
            .op_zonas(mano=5, mazo=30, premios=5)
            .mi_mano(BOSS)
            .mazo()
            .resto_al_descarte()
            .menu_mano()
            .construir())


def test_el_tablero_sintetico_no_tiene_ni_ko_ni_ataque():
    obs = _tablero()
    yo = obs["current"]["yourIndex"]
    mio = obs["current"]["players"][yo]
    riv = obs["current"]["players"][1 - yo]

    # Ningun cuerpo nuestro llega a las 3 energias de Myriad Leaf Shower.
    assert all(len(p["energies"]) < m.ATTACK_ENERGY_REQ[OGERPON]
               for p in mio["active"] + [b for b in mio["bench"] if b])
    # Su Dragapult ex SI ataca (Jet Headbutt cuesta 1) -> hay algo que relevar.
    assert not m._op_cuerpo_inofensivo(_pkm(DRAGAPULT, 1))
    assert riv["active"][0]["id"] == DRAGAPULT
    # El menu solo ofrece el Boss's (0) y el END (1).
    assert [o["type"] for o in obs["select"]["option"]] == [7, 14]


def test_no_se_cambia_su_dragapult_por_el_drakloak_que_lo_reemplaza():
    obs = _tablero()
    assert m.agent(copy.deepcopy(obs)) == [1], (
        "sin KO, subir el Drakloak solo adelanta su siguiente Dragapult ex: "
        "el Boss's se guarda")


def test_con_un_cuerpo_muerto_detras_el_relevo_si_se_juega():
    obs = _tablero(banca_extra=(pk(DUSCLOPS, hp=90, max_hp=90),))
    assert m.agent(copy.deepcopy(obs)) == [0], (
        "el Dusclops pelado no puede pagar su ataque de coste 2: subirlo manda "
        "a la banca al Dragapult ex energizado y les cuesta el turno")
