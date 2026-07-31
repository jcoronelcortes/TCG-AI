"""Lana's Aid: lo que se levanta del descarte lo decide LA MESA, no la forma
de las lineas evolutivas.

Escenario (user, episodio 88776459 registro_018 paso 118 vs Crustle, PERDIDA):

    NOSOTROS                                RIVAL
    activo  Tapu Bulu   140/140  2e         activo  Crustle  270/290
    banca   Meganium    160/160  2e         (banca llena de cuerpos cargados)
            Meowth ex    50/170  2e
            Meganium    160/160  0e
            Ogerpon ex   90/210  2e
            Ogerpon ex  210/210  0e   <- banca LLENA (5/5)
    mano    Hydrapple ex
    descarte  4x Basic Grass, 2x Applin, 1x Dipplin (+ items)
    energia del turno SIN jugar

El agente jugo **Lana's Aid** -- la carta correcta, como confirma el user -- y
levanto **2 Applin + 1 Dipplin**. Con la banca LLENA un Basico no entra de
ninguna forma, y el Dipplin no tiene ningun Applin en juego sobre el que
evolucionar: tres cartas MUERTAS. El turno murio sin atacar.

Lo que la mesa pedia era **energia**:

- con dos Meganium en juego (*Wild Growth*) UNA Planta fisica vale {G}{G}, asi
  que `_grass_attach_unit()` = 2;
- el Tapu Bulu ACTIVO tiene 2 efectivas y Wood Hammer pide 4
  (`ATTACK_ENERGY_REQ`): **una sola Planta lo pone a atacar ESTE turno**, y el
  adjunte manual seguia sin gastarse;
- las otras dos Plantas cargan a los Meganium para el turno siguiente (los dos
  Ogerpon ex en juego dejan ademas dos *Teal Dance* vivas).

Causa raiz: Lana's Aid no tenia rama propia en el contexto `TO_HAND` y caia al
scorer generico de recuperacion, que solo sabe leer FORMAS de linea evolutiva
("¿me falta este eslabon?") y no mira ni la energia ni el hueco de banca. Sus
numeros -- Applin 260 > Dipplin 250 > Planta 240 -- decidian el menu.

Arreglo, en dos piezas que comparten la MISMA lectura de mesa:

 1. `_plan_de_planta`: recorre los `MAIN_ATTACKERS` en juego, mide su deficit
    en CARTAS de Planta (`ceil((req - efectiva) / unidad)`) y cuenta las vias de
    adjunte reales del turno (manual + `_grass_ability_slots`: Teal Dance solo
    carga a su portador, Ripening Charge a cualquiera). Devuelve `demanda` y
    `desbloquea_hoy`/`cartas_para_atacar`.
 2. La rama `Lanas_Aid` del contexto `TO_HAND`, en tres bandas
    (`LANA_SEL_PLANTA_DESBLOQUEA` > `LANA_SEL_PLANTA_DEMANDA` > desarrollo >
    `LANA_SEL_PLANTA_SOBRANTE`/`LANA_SEL_INJUGABLE`), con el ordinal
    `_lana_orden_planta` para que solo las PRIMERAS `demanda` Plantas cobren la
    banda alta -- si no, cuatro copias empatadas se llevarian las 3 elecciones
    aunque la mesa solo supiera usar una.

De paso, `_lana_energy_enables_attack` (capa de JUGADA, decide si Lana's Aid
merece los 950 puntos frente a Lillie's) pasa a usar el mismo
`_plan_de_planta`: antes solo sabia mirar a Hydrapple ex y por eso callaba con
un Tapu Bulu a una Planta de disparar.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Escenario, pk

GRASS = m.Basic_Grass_Energy
TAPU = m.Tapu_Bulu                 # Wood Hammer: 4 energias efectivas
MEGANIUM = m.Meganium              # Wild Growth: cada Planta fisica vale {G}{G}
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
HYDRAPPLE = m.Hydrapple_ex
APPLIN = m.Applin
DIPPLIN = m.Dipplin
CHIKORITA = m.Chikorita
LANA = m.Lanas_Aid
CRUSTLE = m.Crustle_Grass
DWEBBLE = m.Dwebble_Grass

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "crustle_lana_levanta_energia_no_basicos_step118.json")


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
    m._grass_attaches_this_turn = 0
    yield
    m._init_cartas_tracking()


def _cartas_elegidas(obs, eleccion):
    """Ids de descarte que devuelve la seleccion, en orden de preferencia."""
    descarte = obs["current"]["players"][obs["current"]["yourIndex"]]["discard"]
    return [descarte[obs["select"]["option"][i]["index"]]["id"] for i in eleccion]


# ---------------------------------------------------------------------------
# El paso 118 real
# ---------------------------------------------------------------------------

def test_paso118_levanta_las_tres_energias():
    with open(_FIXTURE, encoding="utf-8") as f:
        fixture = json.load(f)
    obs = fixture["observation"]

    # El menu real ofrecia 4 Plantas, 2 Applin y 1 Dipplin.
    ofrecidas = _cartas_elegidas(obs, range(len(obs["select"]["option"])))
    assert sorted(ofrecidas) == sorted([GRASS] * 4 + [APPLIN] * 2 + [DIPPLIN])
    assert obs["select"]["maxCount"] == 3

    # Lo que se jugo en la partida (y perdio el turno).
    assert _cartas_elegidas(obs, fixture["recorded_action"]) == [APPLIN, APPLIN,
                                                                 DIPPLIN]

    assert _cartas_elegidas(obs, m.agent(obs)) == [GRASS, GRASS, GRASS]


def test_paso118_una_planta_pone_a_atacar_al_tapu_bulu():
    """El nucleo de la lectura de mesa: con Meganium en juego el Tapu Bulu esta
    a UNA carta de Planta de poder atacar, y el adjunte del turno sigue libre."""
    with open(_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m.agent(obs)  # fija los globales del turno (meganium_in_play, ...)

    o = m.to_observation_class(obs)
    mi = o.current.players[o.current.yourIndex]
    campo = {}
    for p in mi.active + mi.bench:
        if p is not None:
            campo[p.id] = campo.get(p.id, 0) + 1
    mano = {}
    for c in (mi.hand or []):
        mano[c.id] = mano.get(c.id, 0) + 1

    assert m.meganium_in_play and m._grass_attach_unit() == 2
    tapu = mi.active[0]
    assert tapu.id == TAPU
    assert len(tapu.energies) == 2 and m.ATTACK_ENERGY_REQ[TAPU] == 4

    plan = m._plan_de_planta(mi, o.current, campo, mano)
    assert plan.desbloquea_hoy
    assert plan.cartas_para_atacar == 1
    assert plan.demanda == 3          # los Meganium/Ogerpon piden el resto


def test_paso118_applin_y_dipplin_son_cartas_muertas():
    """Banca 5/5 y ningun Applin en juego: ni el Basico entra ni la Fase 1
    evoluciona nada."""
    with open(_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    o = m.to_observation_class(obs)
    mi = o.current.players[o.current.yourIndex]
    campo = {}
    for p in mi.active + mi.bench:
        if p is not None:
            campo[p.id] = campo.get(p.id, 0) + 1
    banca = len([p for p in mi.bench if p is not None])

    assert banca == mi.benchMax
    assert m._pokemon_injugable(APPLIN, campo, banca, mi.benchMax)
    assert m._pokemon_injugable(DIPPLIN, campo, banca, mi.benchMax)
    assert not m._pokemon_injugable(GRASS, campo, banca, mi.benchMax)


# ---------------------------------------------------------------------------
# `_plan_de_planta`: la lectura de mesa, aislada
# ---------------------------------------------------------------------------

def _plan(activo, banca=(), mano=(), energia_jugada=False, cambio=False):
    obs = (Escenario(turno=10, energia_jugada=energia_jugada)
           .mi_activo(activo)
           .mi_banca(*banca)
           .mi_mano(*mano)
           .op_activo(pk(CRUSTLE))
           .op_zonas(mano=5, mazo=30, premios=6)
           .menu_mano()
           .construir())
    o = m.to_observation_class(obs)
    mi = o.current.players[o.current.yourIndex]
    campo = {}
    for p in mi.active + mi.bench:
        if p is not None:
            campo[p.id] = campo.get(p.id, 0) + 1
    m.meganium_in_play = campo.get(MEGANIUM, 0) >= 1
    m._grass_attaches_this_turn = 0
    cuentas = {}
    for c in (mi.hand or []):
        cuentas[c.id] = cuentas.get(c.id, 0) + 1
    return m._plan_de_planta(mi, o.current, campo, cuentas,
                             puede_cambiar=cambio)


def test_plan_todos_cargados_no_hay_demanda():
    """Sin deficit no hay demanda: la energia deja de valer aunque queden
    adjuntes libres."""
    plan = _plan(pk(TAPU, energias=[G] * 4, fisicas=4),
                 banca=[pk(OGERPON, energias=[G] * 3, fisicas=3)])
    assert plan.demanda == 0
    assert not plan.desbloquea_hoy


def test_plan_sin_adjunte_libre_no_desbloquea_pero_sigue_habiendo_demanda():
    """Gastado el adjunte manual y sin habilidades de carga, la Planta no llega
    al campo HOY -- pero va a la mano y el atacante la sigue pidiendo."""
    plan = _plan(pk(TAPU, energias=[G] * 2, fisicas=2), energia_jugada=True)
    assert not plan.desbloquea_hoy
    assert plan.demanda >= 1


def test_plan_la_planta_de_la_mano_ya_desbloquea():
    """Con la Planta ya en la mano, recuperar otra no desbloquea nada: el
    detector no puede cobrar dos veces por el mismo ataque."""
    plan = _plan(pk(TAPU, energias=[G] * 2, fisicas=2), mano=[GRASS])
    assert not plan.desbloquea_hoy


def test_plan_atacante_de_banca_solo_desbloquea_si_podemos_cambiar():
    banca = [pk(MEGANIUM, energias=[G] * 2, fisicas=1)]
    activo = pk(MEOWTH)               # Meowth ex no es un MAIN_ATTACKER
    assert not _plan(activo, banca=banca).desbloquea_hoy
    assert _plan(activo, banca=banca, cambio=True).desbloquea_hoy


def test_plan_con_las_habilidades_apagadas_solo_queda_el_adjunte_manual():
    """Bajo Watchtower / Iron Thorns (`meowth_ability_lock`) no hay Teal Dance
    ni Ripening Charge: dar por vivas esas vias inventa desbloqueos que no
    existen (medido: -3.9 puntos de winrate vs el mazo de Iron Thorns)."""
    activo = pk(OGERPON, energias=[G], fisicas=1)      # 1 de 3 efectivas
    banca = [pk(OGERPON, energias=[G] * 2, fisicas=2)]

    obs = (Escenario(turno=10)
           .mi_activo(activo).mi_banca(*banca)
           .op_activo(pk(CRUSTLE)).op_zonas(mano=5, mazo=30, premios=6)
           .menu_mano().construir())
    o = m.to_observation_class(obs)
    mi = o.current.players[o.current.yourIndex]
    campo = {OGERPON: 2}
    m.meganium_in_play = False
    m._grass_attaches_this_turn = 0

    # Con las habilidades vivas: adjunte manual + 2 Teal Dance -> 3 slots, y el
    # activo (1 de 3) llega a 3 con 2 Plantas.
    vivas = m._plan_de_planta(mi, o.current, campo, {})
    assert vivas.slots_hoy == 3 and vivas.desbloquea_hoy

    # Con el lock puesto solo queda el adjunte manual: 1 Planta no basta.
    apagadas = m._plan_de_planta(mi, o.current, campo, {},
                                 habilidades_apagadas=True)
    assert apagadas.slots_hoy == 1 and not apagadas.desbloquea_hoy


def test_plan_los_no_atacantes_no_inventan_demanda():
    """Chikorita y Applin tienen coste en `ATTACK_ENERGY_REQ` pero no estan en
    `MAIN_ATTACKERS`: con ellos de banca la mesa no pide energia."""
    plan = _plan(pk(TAPU, energias=[G] * 4, fisicas=4),
                 banca=[pk(CHIKORITA), pk(APPLIN)])
    assert plan.demanda == 0


# ---------------------------------------------------------------------------
# `_pokemon_injugable`: el piso de carta muerta
# ---------------------------------------------------------------------------

def test_injugable_con_hueco_en_banca_nada_esta_muerto():
    campo = {MEGANIUM: 1}
    assert not m._pokemon_injugable(APPLIN, campo, 3, 5)
    assert not m._pokemon_injugable(DIPPLIN, campo, 3, 5)


def test_injugable_banca_llena_la_evolucion_vive_si_su_preevo_esta_en_juego():
    """El Dipplin sigue siendo jugable con la banca llena si hay un Applin en
    juego: evoluciona sobre el, no ocupa hueco."""
    campo = {APPLIN: 1, MEGANIUM: 4}
    assert not m._pokemon_injugable(DIPPLIN, campo, 5, 5)
    assert m._pokemon_injugable(APPLIN, campo, 5, 5)


def test_injugable_no_aplica_a_lo_que_no_es_pokemon():
    assert not m._pokemon_injugable(GRASS, {}, 5, 5)
    assert not m._pokemon_injugable(LANA, {}, 5, 5)


# ---------------------------------------------------------------------------
# La seleccion, en sintetico
# ---------------------------------------------------------------------------

def _seleccion_lana(activo, banca, descarte, mano=(), energia_jugada=False):
    obs = (Escenario(turno=10, partidario_jugado=True,
                     energia_jugada=energia_jugada)
           .mi_activo(activo)
           .mi_banca(*banca)
           .mi_mano(*mano)
           .mi_descarte(*descarte)
           .op_activo(pk(CRUSTLE))
           .op_banca(pk(DWEBBLE))
           .op_zonas(mano=5, mazo=30, premios=6)
           .fetch_descarte(LANA, cuantas=3, solo=(GRASS, APPLIN, DIPPLIN,
                                                  CHIKORITA))
           .construir())
    return obs, _cartas_elegidas(obs, m.agent(obs))


def test_seleccion_banca_llena_la_energia_gana_al_desarrollo():
    """El registro_018 en sintetico."""
    _, elegidas = _seleccion_lana(
        activo=pk(TAPU, energias=[G] * 2, fisicas=1),
        banca=[pk(MEGANIUM, energias=[G] * 2, fisicas=1), pk(MEOWTH),
               pk(MEGANIUM), pk(OGERPON, energias=[G] * 2, fisicas=1),
               pk(OGERPON)],
        descarte=[GRASS, GRASS, GRASS, APPLIN, APPLIN, DIPPLIN])
    assert elegidas == [GRASS, GRASS, GRASS]


def test_seleccion_sin_demanda_de_energia_vuelve_el_desarrollo():
    """Frontera: con el activo YA cargado y hueco en banca, la energia sobra y
    la recuperacion vuelve a ser de desarrollo (arrancar la linea Hydrapple)."""
    _, elegidas = _seleccion_lana(
        activo=pk(TAPU, energias=[G] * 4, fisicas=4),
        banca=[pk(MEOWTH)],
        descarte=[GRASS, GRASS, GRASS, APPLIN, DIPPLIN],
        energia_jugada=True)
    assert APPLIN in elegidas, elegidas


def test_seleccion_solo_la_planta_que_hace_falta_cobra_la_banda_alta():
    """Con demanda de UNA Planta y hueco en banca, la SEGUNDA eleccion ya es
    desarrollo: el ordinal impide que cuatro copias empatadas se lleven el menu
    entero (las Plantas sobrantes caen a `LANA_SEL_PLANTA_SOBRANTE`, por debajo
    del Applin que arranca la linea Hydrapple)."""
    obs, elegidas = _seleccion_lana(
        activo=pk(TAPU, energias=[G] * 2, fisicas=1),
        banca=[pk(MEGANIUM, energias=[G] * 4, fisicas=2), pk(MEOWTH)],
        descarte=[GRASS, GRASS, GRASS, GRASS, APPLIN, CHIKORITA])
    assert elegidas[:2] == [GRASS, APPLIN], elegidas
