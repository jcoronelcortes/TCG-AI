"""Tests del motor de Grand Tree (estadio ACE SPEC id 1249).

Grand Tree deja a CADA jugador, una vez por turno, buscar en su baraja una
Fase 1 que evolucione de uno de sus Basicos y, si evoluciono asi, tambien la
Fase 2 correspondiente. Es un estadio COMPARTIDO: si lo baja el rival, nosotros
tambien lo usamos.

Cubre las reglas pedidas por el user:
  * con el estadio en mesa se usa su habilidad (prioridad de desarrollo);
  * con Meganium en juego se completa Hydrapple ex, con Hydrapple ex en juego
    se completa Meganium, y con AMBOS en juego se hace un segundo Hydrapple ex;
  * si falta el Basico raiz, se busca en el mazo / se recupera del descarte;
  * con Forest of Vitality en la mano, PRIMERO la habilidad y DESPUES el
    reemplazo del estadio.

Y las restricciones de la propia carta: nada en nuestro primer turno, nada
sobre un Basico puesto en juego este mismo turno.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import (FOREST_OF_VITALITY, GRAND_TREE, G, Escenario,
                           pk)

APPLIN = m.Applin
DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
ULTRA_BALL = m.Ultra_Ball
GRASS = m.Basic_Grass_Energy

KANGASKHAN = 756


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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


# ---------------------------------------------------------------------------
# Tablas derivadas del mazo (deck-agnosticas)
# ---------------------------------------------------------------------------

def test_cadenas_derivadas_del_mazo():
    """Las cadenas se leen de `evolvesFrom`, no de una lista escrita a mano."""
    assert (APPLIN, DIPPLIN, HYDRAPPLE) in m._CADENAS_MAZO
    assert (CHIKORITA, BAYLEEF, MEGANIUM) in m._CADENAS_MAZO
    assert m._GT_BASICOS_CON_CADENA == frozenset({APPLIN, CHIKORITA})


def test_valor_cuerpo_prefiere_hydrapple_sobre_meganium():
    """Hydrapple ex (330 PV + habilidad) es el mejor cuerpo del mazo: es el que
    manda cuando la diversificacion no aplica (ambas Etapas 2 ya en juego)."""
    assert m._gt_valor_cuerpo(HYDRAPPLE) > m._gt_valor_cuerpo(MEGANIUM)


# ---------------------------------------------------------------------------
# Eleccion del objetivo: la regla de prioridad del user
# ---------------------------------------------------------------------------

def _planes(activo, banca, mano=(), mazo=None, veta_ex=False,
            primer_turno=False):
    """Ejecuta `_gt_planes` sobre un tablero sintetico minimo."""
    esc = (Escenario(turno=8, paso=40)
           .mi_activo(activo)
           .mi_banca(*banca)
           .mi_mano(*mano)
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, premios=4))
    if mazo is not None:
        esc = esc.mazo(*mazo).resto_al_descarte()
    obs = esc.menu_grand_tree().construir()
    m.agent(obs)  # sincroniza el tracking de cartas del modulo
    estado = obs["current"]["players"][0]
    from cg.api import to_observation_class
    my_state = to_observation_class(obs).current.players[0]
    field = {}
    for p in [estado["active"][0]] + estado["bench"]:
        if p is not None:
            field[p["id"]] = field.get(p["id"], 0) + 1
    return m._gt_planes(my_state, m.CARTAS_ACTIVAS_EN_MAZO, field,
                        primer_turno, veta_etapa_ex=veta_ex)


def test_con_meganium_en_juego_se_completa_hydrapple():
    """Regla del user: teniendo Meganium, la cadena que se construye es la de
    Hydrapple ex (diversificar)."""
    planes = _planes(
        activo=pk(OGERPON, energias=[G, G, G]),
        banca=[pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
               pk(APPLIN), pk(CHIKORITA)])
    assert planes
    assert planes[0].basic_id == APPLIN
    assert planes[0].stage2_id == HYDRAPPLE


def test_con_hydrapple_en_juego_se_completa_meganium():
    """Regla espejo: teniendo Hydrapple ex, se construye Meganium."""
    planes = _planes(
        activo=pk(OGERPON, energias=[G, G, G]),
        banca=[pk(HYDRAPPLE, pre_evo=[APPLIN, DIPPLIN]),
               pk(APPLIN), pk(CHIKORITA)])
    assert planes
    assert planes[0].basic_id == CHIKORITA
    assert planes[0].stage2_id == MEGANIUM


def test_con_ambos_en_juego_se_hace_un_segundo_hydrapple():
    """Regla del user: con Meganium Y Hydrapple ex en mesa, la copia extra que
    interesa es la de Hydrapple ex (el cuerpo mas fuerte)."""
    planes = _planes(
        activo=pk(OGERPON, energias=[G, G, G]),
        banca=[pk(HYDRAPPLE, pre_evo=[APPLIN, DIPPLIN]),
               pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
               pk(APPLIN), pk(CHIKORITA)])
    assert planes
    assert planes[0].basic_id == APPLIN
    assert planes[0].stage2_id == HYDRAPPLE


def test_matchup_anti_ex_prefiere_la_linea_no_ex():
    """Contra un rival que inmuniza a los ex, la Etapa 2 ex se descarta y gana
    la cadena no-ex (Meganium): construir un ex de 2 premios que no puede danar
    al muro es peor que no hacerlo."""
    planes = _planes(
        activo=pk(OGERPON, energias=[G, G, G]),
        banca=[pk(APPLIN), pk(CHIKORITA)],
        veta_ex=True)
    assert planes
    assert planes[0].basic_id == CHIKORITA
    assert planes[0].stage2_id == MEGANIUM
    # La cadena de Applin sigue existiendo pero se detiene en Fase 1.
    applin = [p for p in planes if p.basic_id == APPLIN]
    assert applin and applin[0].stage2_id == 0


def test_basico_que_salio_este_turno_no_es_objetivo():
    """La carta prohibe evolucionar un Basico puesto en juego este turno."""
    planes = _planes(
        activo=pk(OGERPON, energias=[G, G, G]),
        banca=[pk(APPLIN, aparecio=True), pk(CHIKORITA)])
    assert all(p.basic_id != APPLIN for p in planes)
    assert any(p.basic_id == CHIKORITA for p in planes)


def test_primer_turno_sin_planes():
    """La carta prohibe evolucionar Basicos en nuestro primer turno."""
    planes = _planes(
        activo=pk(OGERPON, energias=[G]),
        banca=[pk(APPLIN), pk(CHIKORITA)],
        primer_turno=True)
    assert planes == []


def test_prefiere_banca_con_el_activo_condenado():
    """Con el activo a punto de morir, convertirlo en un cuerpo de MAS premios
    cede el turno a un Basico de banca."""
    esc = (Escenario(turno=8, paso=40)
           .mi_activo(pk(APPLIN, hp=10))
           .mi_banca(pk(APPLIN))
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, premios=4))
    obs = esc.menu_grand_tree().construir()
    m.agent(obs)
    from cg.api import to_observation_class
    my_state = to_observation_class(obs).current.players[0]
    field = {APPLIN: 2}
    planes = m._gt_planes(my_state, m.CARTAS_ACTIVAS_EN_MAZO, field, False,
                          activo_condenado=True)
    assert planes
    assert planes[0].area == m.AreaType.BENCH


# ---------------------------------------------------------------------------
# La habilidad se USA (menu principal)
# ---------------------------------------------------------------------------

def _obs_menu(mano=(), banca=None, con_forest=False, mazo=None, turno=8):
    banca = banca if banca is not None else [pk(APPLIN), pk(CHIKORITA)]
    esc = (Escenario(turno=turno, paso=40)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(*banca)
           .mi_mano(*mano)
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, premios=4))
    if mazo is not None:
        esc = esc.mazo(*mazo).resto_al_descarte()
    return esc.menu_grand_tree(con_forest=con_forest).construir()


def test_se_usa_la_habilidad_del_estadio_rival():
    """El estadio es compartido: con Grand Tree del rival en mesa, la mejor
    jugada del turno es su habilidad (cadena gratis)."""
    obs = _obs_menu()
    eleccion = m.agent(obs)
    assert obs["select"]["option"][eleccion[0]]["type"] == int(m.OptionType.ABILITY)


def test_la_habilidad_precede_al_reemplazo_por_forest():
    """Regla del user: con Forest of Vitality en la mano, PRIMERO la habilidad
    de Grand Tree y DESPUES el reemplazo del estadio."""
    obs = _obs_menu(mano=[FOREST_OF_VITALITY], con_forest=True)
    eleccion = m.agent(obs)
    elegida = obs["select"]["option"][eleccion[0]]
    assert elegida["type"] == int(m.OptionType.ABILITY)


def test_sin_plan_ejecutable_el_forest_se_juega():
    """Sin Basico evolucionable (los dos salieron este turno) la habilidad no
    retiene nada: el Forest reemplaza el estadio rival con normalidad."""
    obs = _obs_menu(mano=[FOREST_OF_VITALITY], con_forest=True,
                    banca=[pk(APPLIN, aparecio=True),
                           pk(CHIKORITA, aparecio=True)])
    eleccion = m.agent(obs)
    elegida = obs["select"]["option"][eleccion[0]]
    assert elegida["type"] == int(m.OptionType.PLAY)


def test_la_habilidad_precede_a_evolucionar_desde_la_mano():
    """Grand Tree no gasta carta de la mano: se cobra antes que la evolucion
    manual, que sigue disponible despues."""
    esc = (Escenario(turno=8, paso=40)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(APPLIN), pk(CHIKORITA))
           .mi_mano(BAYLEEF)
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, premios=4))
    obs = esc.menu_grand_tree(con_evolucion_mano=True).construir()
    eleccion = m.agent(obs)
    assert obs["select"]["option"][eleccion[0]]["type"] == int(m.OptionType.ABILITY)


# ---------------------------------------------------------------------------
# Sub-selecciones de la habilidad
# ---------------------------------------------------------------------------

def test_seleccion_del_pokemon_a_evolucionar_sigue_al_plan():
    """Con Meganium en juego, la sub-seleccion elige el Applin (cadena de
    Hydrapple ex), no el Chikorita."""
    esc = (Escenario(turno=8, paso=41)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(APPLIN), pk(CHIKORITA))
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, premios=4))
    obs = esc.seleccion_grand_tree_en_juego().construir()
    eleccion = m.agent(obs)
    elegida = obs["select"]["option"][eleccion[0]]
    banca = obs["current"]["players"][0]["bench"]
    assert elegida["area"] == int(m.AreaType.BENCH)
    assert banca[elegida["index"]]["id"] == APPLIN


def test_seleccion_de_carta_del_mazo_sigue_al_plan():
    """Ofrecidas Dipplin y Bayleef, se trae el eslabon del plan (Dipplin)."""
    esc = (Escenario(turno=8, paso=41)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(APPLIN), pk(CHIKORITA))
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, premios=4)
           .mazo(DIPPLIN, BAYLEEF, HYDRAPPLE, GRASS)
           .resto_al_descarte())
    obs = esc.seleccion_grand_tree_mazo(DIPPLIN, BAYLEEF).construir()
    eleccion = m.agent(obs)
    elegida = obs["select"]["option"][eleccion[0]]
    assert obs["select"]["deck"][elegida["index"]]["id"] == DIPPLIN


def test_paso_2_trae_la_etapa_2_aunque_el_plan_ya_no_apunte_al_basico():
    """Resuelto el paso 1, el Basico ya es Fase 1 y `_gt_plan` deja de
    apuntarlo; el criterio deck-agnostico (evolucion cuya pre-evolucion esta en
    juego) sigue trayendo el Hydrapple ex."""
    esc = (Escenario(turno=8, paso=42)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(DIPPLIN, pre_evo=[APPLIN]))
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, premios=4)
           .mazo(HYDRAPPLE, GRASS)
           .resto_al_descarte())
    obs = esc.seleccion_grand_tree_mazo(HYDRAPPLE).construir()
    eleccion = m.agent(obs)
    elegida = obs["select"]["option"][eleccion[0]]
    assert obs["select"]["deck"][elegida["index"]]["id"] == HYDRAPPLE


# ---------------------------------------------------------------------------
# Conseguir la raiz: fetch en mazo / descarte
# ---------------------------------------------------------------------------

def test_ultra_ball_busca_el_basico_raiz_si_no_hay_ninguno():
    """Regla del user: sin Basico raiz en juego, la busqueda del turno trae el
    que abre la cadena de Grand Tree."""
    esc = (Escenario(turno=8, paso=30)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(TAPU, energias=[G, G]))
           .mi_mano(GRASS, GRASS)
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, premios=4)
           .mazo(APPLIN, DIPPLIN, HYDRAPPLE, CHIKORITA, BAYLEEF, MEGANIUM,
                 GRASS, GRASS)
           .fetch_ultra_ball()
           .resto_al_descarte())
    obs = esc.construir()
    eleccion = m.agent(obs)
    elegida = obs["select"]["option"][eleccion[0]]
    assert obs["select"]["deck"][elegida["index"]]["id"] == APPLIN


def test_sin_grand_tree_el_bono_de_fetch_no_existe():
    """El motor entero es INERTE sin el estadio en mesa: el mismo tablero sin
    Grand Tree no fuerza la busqueda del Basico raiz."""
    def _fetch(estadio):
        esc = (Escenario(turno=8, paso=30)
               .mi_activo(pk(OGERPON, energias=[G, G, G]))
               .mi_banca(pk(TAPU, energias=[G, G]))
               .mi_mano(GRASS, GRASS)
               .op_activo(pk(KANGASKHAN, hp=400))
               .op_zonas(mano=5, mazo=30, premios=4))
        if estadio is not None:
            esc = esc.estadio(estadio, del_rival=True)
        obs = (esc.mazo(APPLIN, DIPPLIN, HYDRAPPLE, CHIKORITA, BAYLEEF,
                        MEGANIUM, GRASS, GRASS)
               .fetch_ultra_ball()
               .resto_al_descarte()
               .construir())
        eleccion = m.agent(obs)
        elegida = obs["select"]["option"][eleccion[0]]
        return obs["select"]["deck"][elegida["index"]]["id"]

    con = _fetch(GRAND_TREE)
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._field_at_turn_start = {}
    sin = _fetch(None)
    # Con el estadio manda la regla nueva; sin el, la busqueda vuelve a lo que
    # decidian las reglas preexistentes (aqui, el motor de refresco: Meowth ex
    # no esta en el mazo declarado, asi que gana la Etapa 2 de siempre).
    assert con == APPLIN
    assert sin != APPLIN


def test_con_raiz_en_juego_no_se_fuerza_la_busqueda():
    """Con un Applin ya en banca la raiz existe: el bono no se aplica y manda
    el resto de prioridades del mazo."""
    esc = (Escenario(turno=8, paso=30)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(APPLIN, aparecio=True))
           .mi_mano(GRASS, GRASS)
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, premios=4)
           .mazo(APPLIN, DIPPLIN, HYDRAPPLE, CHIKORITA, BAYLEEF, MEGANIUM,
                 GRASS, GRASS)
           .fetch_ultra_ball()
           .resto_al_descarte())
    obs = esc.construir()
    m.agent(obs)  # no debe reventar; la eleccion la deciden las reglas previas
    ranking = m._gt_basicos_deseados(m.CARTAS_ACTIVAS_EN_MAZO,
                                     {OGERPON: 1, APPLIN: 1})
    assert APPLIN in ranking and CHIKORITA in ranking
