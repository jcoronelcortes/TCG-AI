"""La Planta paga la RETIRADA del activo para que ataque el rematador de banca.

Escenario (user, registro_006 paso 101, episodio 88492701 vs Alakazam, PERDIDA):
turno 6 con un **Applin ACTIVO a 0 energias** (coste de retirada 1) y un **Teal
Mask Ogerpon ex de banca a 6 energias efectivas** que NOQUEA al Alakazam activo
(Myriad Leaf Shower 240 sobre 140 PV). El adjunte manual ya estaba gastado, pero
quedaba viva la habilidad de carga del Hydrapple ex de banca y una Planta en la
mano. La linea correcta era de tres pasos:

    Ripening Charge -> Planta al ACTIVO -> RETIRAR -> promover al Ogerpon -> KO

El agente activo la habilidad, mando la Planta a un Ogerpon de BANCA y cerro el
turno sin atacar, con el rematador atrapado detras del Applin.

Dos fallos encadenados, ambos deck-agnosticos:

1. `_grass_unlocks_active_retreat` abortaba la linea entera con
   `_can_attack_eff(activo, e + 1)`: como el Applin "llega a su coste de ataque"
   con una Planta, el detector daba (False, False) -- y eso que el modelo de dano
   no le concede NI UN PUNTO al Applin. Ahora se comparan DANOS.
2. `energy_score` -- que decide a QUE Pokemon va la energia, tanto en el adjunte
   manual como en el objetivo de las habilidades (SelectContext.ATTACH_FROM) --
   no tenia ninguna rama para esta linea: el ACTIVO caia en la banda generica de
   desarrollo (~8000) y cualquier cuerpo de banca le ganaba. De propina, el foco
   de carga de Ogerpon (41700) apuntaba a un SEGUNDO rematador igual de atrapado.

Los tests son deck-agnosticos a proposito: el activo atrapado y el rematador de
banca se parametrizan, y el caso central usa un activo (Applin) cuyo "ataque" es
justo lo que enganaba al detector.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Escenario, pk

APPLIN = m.Applin                   # activo atrapado: 0 energias, coste 1
DIPPLIN = m.Dipplin
OGERPON = m.Teal_Mask_Ogerpon_ex    # rematador de banca (Myriad Leaf Shower)
TAPU = m.Tapu_Bulu                  # rematador SIN habilidad de carga
HYDRAPPLE = m.Hydrapple_ex          # portador de Ripening Charge
MEOWTH = m.Meowth_ex
ULTRA_BALL = m.Ultra_Ball
GRASS = m.Basic_Grass_Energy

FEZANDIPITI = m.Fezandipiti_ex      # activo atrapado del episodio 88603018
MEGANIUM = m.Meganium

ALAKAZAM = 743                      # 140 PV: el activo rival del registro
KADABRA = 742
ABRA = 741
DUNSPARCE = 305
SHAYMIN = 343                       # 80 PV: el activo rival del 88603018


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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _escenario(activo=None, banca=None, mano=(GRASS, ULTRA_BALL),
               energia_jugada=True, op_hp=140, op_energias=1):
    """El tablero del registro: activo atrapado + rematador de banca listo."""
    activo = activo if activo is not None else pk(APPLIN)
    banca = banca if banca is not None else [
        pk(OGERPON, energias=[G] * 6, fisicas=3),   # YA letal: 30+30*(6+1)=240
        pk(HYDRAPPLE),                              # portador de Ripening Charge
        pk(MEOWTH),
    ]
    return (Escenario(turno=6, paso=101, energia_jugada=energia_jugada)
            .mi_activo(activo)
            .mi_banca(*banca)
            .mi_mano(*mano)
            .op_activo(pk(ALAKAZAM, hp=op_hp, energias=[G] * op_energias))
            .op_zonas(mano=6, mazo=20, premios=3))


def _destino(obs, eleccion):
    """Area del Pokemon elegido como destino de la carga."""
    o = obs["select"]["option"][eleccion[0]]
    return o.get("area", o.get("inPlayArea"))


# ---------------------------------------------------------------------------
# El fallo del registro: objetivo de la HABILIDAD de carga (ATTACH_FROM)
# ---------------------------------------------------------------------------

def test_la_habilidad_de_carga_pone_la_planta_en_el_activo_atrapado():
    """El caso exacto del paso 101: la Planta de Ripening Charge va al ACTIVO
    para pagar su retirada, no a un cuerpo de banca."""
    obs = _escenario().objetivo_carga_habilidad(banca_idx=1).construir()
    assert _destino(obs, m.agent(obs)) == int(m.AreaType.ACTIVE)


def test_el_foco_de_ogerpon_no_roba_la_planta_de_la_retirada():
    """Regresion directa: con un SEGUNDO Ogerpon a medio cargar, el foco de
    carga letal (41700) se llevaba la Planta y dejaba a los dos rematadores
    atrapados detras del activo. Mientras la retirada no este pagada, cargar
    banca no promueve a nadie."""
    banca = [pk(OGERPON, energias=[G] * 6, fisicas=3),
             pk(HYDRAPPLE),
             pk(OGERPON, energias=[G, G], fisicas=1)]   # el cebo del foco
    obs = _escenario(banca=banca).objetivo_carga_habilidad(banca_idx=1).construir()
    assert _destino(obs, m.agent(obs)) == int(m.AreaType.ACTIVE)


def test_deck_agnostico_cualquier_rematador_de_banca_sirve():
    """La linea no depende de Ogerpon ni de su habilidad: con un Tapu Bulu ya
    cargado (220 >= 140) la Planta debe ir igualmente al ACTIVO."""
    banca = [pk(TAPU, energias=[G] * 4), pk(HYDRAPPLE), pk(MEOWTH)]
    obs = _escenario(banca=banca).objetivo_carga_habilidad(banca_idx=1).construir()
    assert _destino(obs, m.agent(obs)) == int(m.AreaType.ACTIVE)


# ---------------------------------------------------------------------------
# Misma linea por el adjunte MANUAL
# ---------------------------------------------------------------------------

def test_el_adjunte_manual_tambien_va_al_activo_atrapado():
    obs = (_escenario(energia_jugada=False)
           .menu_mano(con_adjunte=True).construir())
    eleccion = m.agent(obs)
    o = obs["select"]["option"][eleccion[0]]
    assert o["type"] == int(m.OptionType.ATTACH)
    assert o["inPlayArea"] == int(m.AreaType.ACTIVE)


# ---------------------------------------------------------------------------
# Misma linea con MEGANIUM en juego (episodio 88603018 paso 106, vs Alakazam)
# ---------------------------------------------------------------------------
#
# El tablero de produccion que hacia falta pinar: Fezandipiti ex ACTIVO a 0
# energias (coste 1), Meganium de banca doblando cada Planta con Wild Growth,
# TRES Ogerpon ex ya cargados detras y una sola Planta en la mano. La build
# subida mando la energia al MEGANIUM y cerro el turno sin atacar.
#
# Meganium en juego importa porque abre una rama entera de `energy_score`
# (el reparto de Planta por la banca, con Meganium en su tabla de prioridad)
# que compite con el destino ACTIVO de esta linea. Ninguno de los tests de
# arriba lo tenia en la mesa.


def _escenario_meganium(activo=None, mano=(GRASS, ULTRA_BALL)):
    activo = activo if activo is not None else pk(FEZANDIPITI)
    return (Escenario(turno=10, paso=106, energia_jugada=False)
            .mi_activo(activo)
            .mi_banca(pk(MEGANIUM, energias=[G, G], fisicas=1),
                      pk(OGERPON, energias=[G] * 6, fisicas=3),
                      pk(OGERPON, energias=[G] * 4, fisicas=2),
                      pk(MEOWTH),
                      pk(OGERPON, hp=70, energias=[G] * 6, fisicas=3))
            .mi_mano(*mano)
            .op_activo(pk(SHAYMIN))
            .op_banca(pk(KADABRA, pre_evo=[ABRA]), pk(DUNSPARCE), pk(ABRA),
                      pk(DUNSPARCE))
            .op_zonas(mano=8, mazo=20, premios=5))


def test_con_meganium_en_juego_la_planta_sigue_yendo_al_activo_atrapado():
    """Regresion del episodio 88603018 paso 106: con Wild Growth activo y la
    banca llena de Ogerpon cargados, la unica Planta debe pagar la retirada del
    Fezandipiti ex -- no engordar al Meganium."""
    obs = _escenario_meganium().menu_mano(con_adjunte=True).construir()
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert o["type"] == int(m.OptionType.ATTACH)
    assert o["inPlayArea"] == int(m.AreaType.ACTIVE)


def test_con_meganium_el_detector_ve_la_linea_letal():
    obs = _escenario_meganium().menu_mano(con_adjunte=True).construir()
    assert _detector(obs) == (True, False)


def test_con_meganium_el_activo_que_ya_se_retira_no_dispara_la_linea():
    """Frontera del detector: con una Planta fisica encima, el Fezandipiti ex ya
    paga su retirada de coste 1 y no hay nada que desbloquear.

    Ojo al leerlo: el adjunte SIGUE yendo al activo en ese tablero, pero por otra
    regla (`_carga_activo_remata`) -- con 4 unidades efectivas Cruel Arrow pasa a
    ser jugable y noquea al Shaymin de 80 PV. Atacar gana a pivotar."""
    obs = (_escenario_meganium(activo=pk(FEZANDIPITI, energias=[G, G], fisicas=1))
           .menu_mano(con_adjunte=True).construir())
    assert _detector(obs) == (False, False)


def test_con_meganium_sin_nada_que_desbloquear_la_planta_vuelve_a_la_banca():
    """Frontera del DESTINO: el activo no gana por ser el activo. Con el
    Fezandipiti ex ya capaz de retirarse Y de atacar, la Planta no desbloquea
    nada y vuelve al reparto normal de banca."""
    obs = (_escenario_meganium(activo=pk(FEZANDIPITI, energias=[G] * 4, fisicas=2))
           .menu_mano(con_adjunte=True).construir())
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert o["type"] == int(m.OptionType.ATTACH)
    assert o["inPlayArea"] == int(m.AreaType.BENCH)


# ---------------------------------------------------------------------------
# Cierre de la cadena: con la energia puesta, se retira y se promueve
# ---------------------------------------------------------------------------

def test_con_la_planta_puesta_el_activo_se_retira():
    obs = (_escenario(activo=pk(APPLIN, energias=[G]), mano=(ULTRA_BALL,))
           .menu_mano(con_retirada=True).construir())
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert o["type"] == int(m.OptionType.RETREAT)


def test_al_promover_sube_el_rematador():
    obs = (_escenario(activo=pk(APPLIN, energias=[G]), mano=(ULTRA_BALL,))
           .promocion_desde_banca().construir())
    idx = obs["select"]["option"][m.agent(obs)[0]]["index"]
    assert obs["current"]["players"][0]["bench"][idx]["id"] == OGERPON


# ---------------------------------------------------------------------------
# Fronteras del detector (`_grass_unlocks_active_retreat`)
# ---------------------------------------------------------------------------

def _detector(obs):
    """(ko, chip) del nucleo compartido sobre el estado construido."""
    o = m.to_observation_class(obs)
    st = o.current
    mio, rival = st.players[0], st.players[1]
    m.meganium_in_play = False
    total_grass = sum(len(p.energies)
                      for p in ([mio.active[0]] if mio.active else []) + list(mio.bench)
                      if p is not None)
    return m._grass_unlocks_active_retreat(
        mio, rival, False, total_grass, len(mio.bench), False, False)


def test_detector_ve_la_linea_letal():
    obs = _escenario().objetivo_carga_habilidad(banca_idx=1).construir()
    assert _detector(obs) == (True, False)


def test_si_el_activo_remata_con_esa_planta_no_se_retira():
    """Frontera: atacar con el activo es lo primero. Con un Dipplin activo cuyo
    ataque (20 x banca) noquea al rival, la linea de retirada NO se activa."""
    obs = (_escenario(activo=pk(DIPPLIN), op_hp=60)
           .objetivo_carga_habilidad(banca_idx=1).construir())
    assert _detector(obs) == (False, False)


def test_sin_rematador_de_banca_no_hay_linea():
    """Frontera: si en la banca no hay nadie listo, la Planta no tiene por que
    ir al activo (no hay nada que promover)."""
    banca = [pk(OGERPON), pk(HYDRAPPLE), pk(MEOWTH)]
    obs = _escenario(banca=banca).objetivo_carga_habilidad(banca_idx=1).construir()
    assert _detector(obs) == (False, False)


def test_si_el_activo_ya_paga_su_retirada_no_hay_nada_que_desbloquear():
    obs = (_escenario(activo=pk(APPLIN, energias=[G]))
           .objetivo_carga_habilidad(banca_idx=1).construir())
    assert _detector(obs) == (False, False)


# ---------------------------------------------------------------------------
# El tablero de produccion del episodio 88631738 paso 77 (GANADA, con el turno
# 8 regalado): Meowth ex ACTIVO a 0 energias (coste de retirada 1) que no puede
# atacar, Hydrapple ex de banca a 4 efectivas que NOQUEA al Mega Starmie ex, el
# adjunte manual YA gastado y dos Plantas en la mano. La build subida cerro el
# turno (END) con el remate de 3 premios en la mesa: la unica via viva era la
# HABILIDAD (Ripening Charge no consume el adjunte del turno).
# ---------------------------------------------------------------------------

MEGA_STARMIE = 1031                 # 330 PV, a 240 en el registro


def _escenario_88631738(activo=None, mano=(GRASS, GRASS, ULTRA_BALL),
                        energia_jugada=True):
    activo = activo if activo is not None else pk(MEOWTH, hp=50)
    return (Escenario(turno=8, paso=77, energia_jugada=energia_jugada,
                      partidario_jugado=True)
            .mi_activo(activo)
            .mi_banca(pk(OGERPON, energias=[G] * 4, fisicas=2),
                      pk(HYDRAPPLE, hp=280, energias=[G] * 4, fisicas=2),
                      pk(FEZANDIPITI),
                      pk(MEGANIUM),
                      pk(OGERPON, energias=[G] * 2, fisicas=1))
            .mi_mano(*mano)
            .op_activo(pk(MEGA_STARMIE, hp=240))
            .op_banca(pk(1030))
            .op_zonas(mano=2, mazo=39, premios=4))


def test_88631738_la_habilidad_carga_al_activo_con_el_adjunte_ya_gastado():
    """El fallo del registro: con `energyAttached` puesto, la unica ruta viva es
    Ripening Charge -- y su Planta tiene que ir al ACTIVO para pagar la
    retirada, no a un Ogerpon de banca."""
    obs = _escenario_88631738().objetivo_carga_habilidad(banca_idx=1).construir()
    assert _destino(obs, m.agent(obs)) == int(m.AreaType.ACTIVE)


def test_88631738_con_la_planta_puesta_el_activo_se_retira():
    obs = (_escenario_88631738(activo=pk(MEOWTH, hp=50, energias=[G, G],
                                         fisicas=1),
                               mano=(ULTRA_BALL,))
           .menu_mano(con_retirada=True).construir())
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert o["type"] == int(m.OptionType.RETREAT)


def test_88631738_al_promover_sube_el_hydrapple_que_remata():
    obs = (_escenario_88631738(activo=pk(MEOWTH, hp=50, energias=[G, G],
                                         fisicas=1),
                               mano=(ULTRA_BALL,))
           .promocion_desde_banca().construir())
    idx = obs["select"]["option"][m.agent(obs)[0]]["index"]
    assert obs["current"]["players"][0]["bench"][idx]["id"] == HYDRAPPLE


# ---------------------------------------------------------------------------
# PRESUPUESTO de carga: la retirada de 2 o 3 simbolos tambien se paga
# ---------------------------------------------------------------------------
#
# El detector media exactamente UNA Planta (`e + unit < rc` -> sin linea), asi
# que un activo atrapado con coste de retirada >1 era invisible aunque las vias
# vivas del turno lo cubriesen de sobra. Ahora se mide el PRESUPUESTO real de
# carga hacia el ACTIVO (adjunte manual libre + `_grass_ability_slots_activo`,
# acotado por las Plantas de la mano), igual que `_carga_activo_remata` para el
# coste de ATAQUE.


def _detector_presupuesto(obs, budget):
    o = m.to_observation_class(obs)
    st = o.current
    mio, rival = st.players[0], st.players[1]
    m.meganium_in_play = False
    total_grass = sum(len(p.energies)
                      for p in ([mio.active[0]] if mio.active else []) + list(mio.bench)
                      if p is not None)
    return m._grass_unlocks_active_retreat(
        mio, rival, False, total_grass, len(mio.bench), False, False,
        budget=budget)


def _escenario_coste_3(activo_e=1, mano=(GRASS, GRASS, ULTRA_BALL),
                       energia_jugada=False):
    """Activo con coste de retirada 3 (Tapu Bulu) a `activo_e` energias: le
    faltan DOS Plantas, y hay dos vias vivas (adjunte manual + Ripening)."""
    return (Escenario(turno=8, paso=40, energia_jugada=energia_jugada)
            .mi_activo(pk(TAPU, energias=[G] * activo_e))
            .mi_banca(pk(OGERPON, energias=[G] * 6, fisicas=3),
                      pk(HYDRAPPLE),
                      pk(MEOWTH))
            .mi_mano(*mano)
            .op_activo(pk(ALAKAZAM, hp=140, energias=[G]))
            .op_zonas(mano=6, mazo=20, premios=3))


def test_con_presupuesto_de_una_planta_no_hay_linea():
    """Frontera preservada: si solo cabe UNA Planta, dos simbolos de retirada
    siguen siendo inalcanzables."""
    obs = _escenario_coste_3().menu_mano(con_adjunte=True).construir()
    assert _detector_presupuesto(obs, 1) == (False, False)


def test_con_presupuesto_de_dos_plantas_el_detector_ve_la_linea():
    obs = _escenario_coste_3().menu_mano(con_adjunte=True).construir()
    assert _detector_presupuesto(obs, 2) == (True, False)


def test_el_adjunte_manual_abre_la_retirada_de_dos_simbolos():
    """La cadena completa, paso 1: con el adjunte manual libre y un Hydrapple ex
    de banca (Ripening Charge) la retirada de 3 simbolos es pagable, asi que la
    primera Planta va al ACTIVO -- no a engordar la banca."""
    obs = _escenario_coste_3().menu_mano(con_adjunte=True).construir()
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert o["type"] == int(m.OptionType.ATTACH)
    assert o["inPlayArea"] == int(m.AreaType.ACTIVE)


def test_la_habilidad_remata_la_segunda_planta_en_el_activo():
    """Paso 2: con el adjunte ya gastado y el activo a una Planta del coste,
    Ripening Charge apunta otra vez al ACTIVO."""
    obs = (_escenario_coste_3(activo_e=2, mano=(GRASS, ULTRA_BALL),
                              energia_jugada=True)
           .objetivo_carga_habilidad(banca_idx=1).construir())
    assert _destino(obs, m.agent(obs)) == int(m.AreaType.ACTIVE)


def test_sin_plantas_suficientes_en_la_mano_no_se_abre_la_linea():
    """El presupuesto lo acota la MANO: con una sola Planta no se puede pagar
    una retirada de dos, y la energia no se malgasta en el activo atrapado."""
    obs = (_escenario_coste_3(mano=(GRASS, ULTRA_BALL))
           .menu_mano(con_adjunte=True).construir())
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert not (o["type"] == int(m.OptionType.ATTACH)
                and o["inPlayArea"] == int(m.AreaType.ACTIVE))


WATCHTOWER = m.Team_Rockets_Watchtower   # apaga nuestras habilidades de carga


def test_con_las_habilidades_apagadas_el_presupuesto_vuelve_a_una_planta():
    """Frontera del presupuesto: con Team Rocket's Watchtower en mesa, Ripening
    Charge esta apagada, asi que la segunda via NO existe y la primera Planta no
    debe quedarse tirada en un activo que seguira sin poder retirarse."""
    obs = (_escenario_coste_3()
           .estadio(WATCHTOWER, del_rival=True)
           .menu_mano(con_adjunte=True).construir())
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert not (o["type"] == int(m.OptionType.ATTACH)
                and o["inPlayArea"] == int(m.AreaType.ACTIVE))
