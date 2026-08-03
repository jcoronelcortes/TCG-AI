"""vs Dragapult: la Ultra Ball se gasta HOY porque MAÑANA no habrá Objetos.

Escenario (`registros/registro_002_pasos_012_hasta_017.json`, paso 17, turno 2
saliendo segundos, PERDIDA vs Dragapult -- episodio 89079426):

    NOSOTROS (6 premios)                       RIVAL (6 premios)
    activo  Chikorita 70, 1 {G}                activo  **Budew 30**
    banca   Fezandipiti ex 210, **0 {G}**      banca   Dreepy, Dreepy,
    mano    Planta x3, Boss's x2,                      Munkidori 1 {G}
            **Ultra Ball**, Meganium, Forest
    (Lillie's Determination YA jugada este turno)

El agente **atacaba con el Chikorita** y cerraba el turno con la Ultra Ball en la
mano. Ese fue el último turno en que se podía jugar: el *Itchy Pollen* del Budew
—ataque de CERO energía— bloquea los Objetos durante nuestro turno siguiente, y
contra Dragapult el Budew no se va del campo. La única carta capaz de rehacer la
partida se quedó de adorno.

Y el tablero no daba para esperar: el Fezandipiti ex necesita 3 energías (una por
turno) y el Meganium de la mano no tenía Bayleef debajo -> **mañana tampoco se
ataca** (`_sin_atacante_para_manana`).

Regla (user): contra Dragapult (o con cualquier Budew en el campo rival), sin
mano que arranque el ataque, se juega la Ultra Ball para cavar **Meowth ex**. No
se baja hoy —el hueco de Supporter ya está gastado, así que su *Last-Ditch Catch*
no produciría nada y el cuerpo solo REGALARÍA dos premios en el turno rival—: se
baja MAÑANA, cuando su habilidad trae una **Lillie's Determination**. Ni los
Pokémon ni las habilidades ni los Supporters los bloquea el *Itchy Pollen*; los
Objetos sí.

Causa: `_eval_ub_best_target` devolvía 0 y la Ultra Ball caía a `SCORE_CANCEL`
(-100), por debajo del ataque del Chikorita (1000). Las dos ramas que podían
cavar el Meowth ex exigen `not supporterPlayed` —"la Ultra Ball solo se juega por
un Pokémon que vayamos a JUGAR este turno", `_ub_cavar_meowth_se_juega`—, y la
red de rescate del turno estéril, que SÍ conoce el bloqueo de Objetos, no se
enciende porque el turno no era estéril: había un ataque de verdad.

Arreglo: `_ub_meowth_para_manana`, la única rama que compra para el turno
siguiente, porque es la única en la que guardar la Ultra Ball equivale a tirarla.
Sus dos piezas nuevas se comparten con quien ya decidía lo mismo:

  * `_bloqueo_de_items_inminente` — Budew en el campo rival o mazo Dragapult; el
    mismo predicado que usaba inline la red del turno estéril;
  * `_sin_atacante_para_manana` — un turno más allá que `_sin_ataque_hoy`:
    cuenta el adjunte del próximo turno y las evoluciones que la mano completa.

El fetch tiene su propia mitad (`bloqueo_de_items_manana` en `_REGLAS_UB_MEOWTH`,
por encima de `last_ditch_no_produce`): sin ella la búsqueda ya pagada habría
traído cualquier otra cosa.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Escenario, pk, G

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "dragapult_ub_meowth_para_manana_step17.json")

CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
MEGANIUM = m.Meganium
APPLIN = m.Applin
DIPPLIN = m.Dipplin
OGERPON = m.Teal_Mask_Ogerpon_ex
FEZ = m.Fezandipiti_ex
MEOWTH = m.Meowth_ex
LILLIE = m.Lillie_Determination
BOSS = m.Boss_Orders
ULTRA_BALL = m.Ultra_Ball
FOREST = m.Forest_of_Vitality
GRASS = m.Basic_Grass_Energy
BUDEW = m.Budew
DREEPY = m.Dreepy
MUNKIDORI = m.Munkidori

TURNO = 2


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
    m._grass_attaches_this_turn = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _jugada(obs, eleccion):
    o = obs["select"]["option"][eleccion[0]]
    if o["type"] == int(m.OptionType.PLAY):
        yo = obs["current"]["yourIndex"]
        return ("PLAY", obs["current"]["players"][yo]["hand"][o["index"]]["id"])
    if o["type"] == int(m.OptionType.CARD):
        return ("CARTA", obs["select"]["deck"][o["index"]]["id"])
    return (int(o["type"]), None)


# ---------------------------------------------------------------------------
# 1. El paso real del registro
# ---------------------------------------------------------------------------

def test_paso17_juega_la_ultra_ball_en_vez_de_atacar_con_el_chikorita():
    with open(_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    assert _jugada(obs, m.agent(obs)) == ("PLAY", ULTRA_BALL), (
        "con Budew en el activo rival la Ultra Ball CADUCA este turno y el "
        "tablero no ataca mañana: se cava el Meowth ex antes de atacar")


# ---------------------------------------------------------------------------
# 2. El escenario sintético: los tres menús de la cadena
# ---------------------------------------------------------------------------
# El registro se corta en el paso 17 (el agente atacó), así que el fetch y el
# turno siguiente se FABRICAN con StateBuilder sobre el mismo tablero.

def _campo(esc, fez_energias=0, mano_extra=()):
    return (esc
            .mi_activo(pk(CHIKORITA, energias=[G], fisicas=1))
            .mi_banca(pk(FEZ, energias=[G] * fez_energias,
                         fisicas=fez_energias))
            .op_activo(pk(BUDEW))
            .op_banca(DREEPY, DREEPY, pk(MUNKIDORI, energias=[G], fisicas=0))
            .op_zonas(mano=5, mazo=43, premios=6))


# NOTA: `menu_mano()` emite una opcion PLAY por CADA carta de la mano, sin el
# filtro de legalidad del simulador. Por eso el Meganium del registro (Fase 2
# sin Bayleef debajo: el juego real NUNCA lo ofrece) se deja fuera de las manos
# de los menus MAIN sinteticos -- si no, el agente lo "juega" y el escenario
# mide otra cosa. En el menu de fetch sí puede estar: ahí la mano no se ofrece.
def _menu_main(fez_energias=0, mano=(GRASS, GRASS, GRASS, BOSS, BOSS,
                                     ULTRA_BALL, FOREST),
               op_generico=False, partidario_jugado=True):
    """Menú A: el MAIN del paso 17 (energía del turno ya adjuntada)."""
    esc = Escenario(turno=TURNO, paso=17, tac=6, primer_jugador=1,
                    energia_jugada=True,
                    partidario_jugado=partidario_jugado)
    esc = _campo(esc, fez_energias=fez_energias)
    if op_generico:
        # CONTROL: el mismo tablero sin ninguna pieza que amenace con bloquear
        # los Objetos (ni Budew ni línea Dreepy) -> la Ultra Ball se guarda.
        esc.op_activo(pk(MUNKIDORI))
        esc.op_banca(pk(MUNKIDORI), pk(MUNKIDORI))
    return (esc
            .mi_mano(*mano)
            .mazo(MEOWTH, LILLIE, BAYLEEF, OGERPON, APPLIN)
            .resto_al_descarte()
            .menu_mano(con_ataque=True)
            .construir())


def _menu_fetch():
    """Menú B: el fetch de la Ultra Ball recién jugada."""
    esc = Escenario(turno=TURNO, paso=18, tac=7, primer_jugador=1,
                    energia_jugada=True, partidario_jugado=True)
    return (_campo(esc)
            .mi_mano(GRASS, BOSS, BOSS, MEGANIUM, FOREST)
            .mazo(MEOWTH, LILLIE, BAYLEEF, OGERPON, APPLIN)
            .fetch_ultra_ball()
            .resto_al_descarte()
            .construir())


def _menu_manana():
    """Menú C: NUESTRO turno siguiente, ya con el Itchy Pollen encima. Los
    Objetos no se pueden jugar (por eso no hay ninguno en la mano) pero el
    Meowth ex sí: su Last-Ditch Catch trae la Lillie's."""
    obs = (Escenario(turno=TURNO + 2, paso=30, tac=1, primer_jugador=1)
           .mi_activo(pk(CHIKORITA, energias=[G], fisicas=1))
           .mi_banca(pk(FEZ))
           .op_activo(pk(BUDEW))
           .op_banca(DREEPY, DREEPY, pk(MUNKIDORI, energias=[G], fisicas=0))
           .op_zonas(mano=5, mazo=40, premios=6)
           .mi_mano(MEOWTH, GRASS, GRASS)
           .mazo(LILLIE, BAYLEEF, OGERPON, APPLIN)
           .resto_al_descarte()
           .menu_mano(con_ataque=True)
           .construir())
    # El Itchy Pollen del turno rival: `itchy_pollen_active` se deriva de los
    # logs de ATAQUE (ver el bloque "Bloqueo de ITEMS rival" de `agent()`).
    obs["logs"] = [{"type": int(m.LogType.ATTACK), "cardId": BUDEW,
                    "playerIndex": 1, "serial": 88}]
    return obs


def test_menuA_la_ultra_ball_gana_al_ataque_del_chikorita():
    obs = _menu_main()
    assert _jugada(obs, m.agent(obs)) == ("PLAY", ULTRA_BALL)


def test_menuB_el_fetch_de_la_busqueda_pagada_trae_el_meowth_ex():
    obs = _menu_fetch()
    assert _jugada(obs, m.agent(obs)) == ("CARTA", MEOWTH), (
        "la Ultra Ball se pagó EXACTAMENTE por este cuerpo; sin la regla "
        "`bloqueo_de_items_manana` el veto `last_ditch_no_produce` la "
        "desviaba a otra carta")


def test_menuC_manana_el_meowth_ex_se_baja_bajo_el_bloqueo_de_objetos():
    obs = _menu_manana()
    assert _jugada(obs, m.agent(obs)) == ("PLAY", MEOWTH), (
        "bajo el Itchy Pollen los Pokémon y las habilidades SIGUEN jugándose: "
        "el Meowth ex cavado ayer baja y su Last-Ditch trae la Lillie's")


# ---------------------------------------------------------------------------
# 3. Controles: la regla no se dispara sin sus tres premisas
# ---------------------------------------------------------------------------

def test_control_sin_amenaza_de_bloqueo_la_ultra_ball_se_guarda():
    obs = _menu_main(op_generico=True)
    assert _jugada(obs, m.agent(obs)) != ("PLAY", ULTRA_BALL), (
        "sin Budew ni línea Dreepy enfrente la Ultra Ball NO caduca: sigue "
        "valiendo la regla general de no cavar lo que no se juega hoy")


def test_control_con_atacante_a_una_energia_la_ultra_ball_se_guarda():
    # Fezandipiti ex a 2 energías: el adjunte del próximo turno lo pone a
    # atacar (Cruel Arrow, 3) -> `_sin_atacante_para_manana` es False.
    obs = _menu_main(fez_energias=2)
    assert _jugada(obs, m.agent(obs)) != ("PLAY", ULTRA_BALL)


def test_control_con_lillie_en_mano_no_hay_nada_que_cavar():
    obs = _menu_main(mano=(GRASS, GRASS, BOSS, LILLIE, ULTRA_BALL, FOREST),
                     partidario_jugado=False)
    assert _jugada(obs, m.agent(obs)) != ("PLAY", ULTRA_BALL), (
        "el Meowth ex vale por la Lillie's que busca; con la Lillie's ya en "
        "la mano el rodeo no compra nada")


# ---------------------------------------------------------------------------
# 4. Los predicados nuevos, por separado
# ---------------------------------------------------------------------------

def test_bloqueo_de_items_inminente_cubre_budew_y_la_linea_dragapult():
    assert m._bloqueo_de_items_inminente(True, False, False) is True   # Budew
    assert m._bloqueo_de_items_inminente(False, True, False) is True   # Dragapult ex
    assert m._bloqueo_de_items_inminente(False, False, True) is True   # Dreepy
    assert m._bloqueo_de_items_inminente(False, False, False) is False


def test_sin_atacante_para_manana_no_cuenta_al_chikorita_ni_a_los_basicos():
    from types import SimpleNamespace as NS
    _pk = lambda cid, e=0: NS(id=cid, energies=[G] * e)
    tablero = NS(active=[_pk(CHIKORITA, 1)], bench=[_pk(FEZ, 0)])

    # Chikorita ataca, pero no es un MAIN_ATTACKER; el Fezandipiti ex está a 3
    # energías y solo se adjunta UNA por turno. Un Tapu Bulu en la mano (4
    # energías) tampoco es "empezar a atacar mañana".
    assert m._sin_atacante_para_manana(tablero, {m.Tapu_Bulu: 1}, {}) is True

    # Con el Fezandipiti a 2, el adjunte de mañana lo pone a atacar.
    cargado = NS(active=[_pk(CHIKORITA, 1)], bench=[_pk(FEZ, 2)])
    assert m._sin_atacante_para_manana(cargado, {}, {}) is False

    # Una evolución de la mano sobre su pre-evo en mesa también cuenta: hereda
    # la energía del cuerpo y ataca.
    assert m._sin_atacante_para_manana(
        tablero, {MEGANIUM: 1}, {BAYLEEF: 1}) is False
