"""Tests del StateBuilder (`Escenario`) y primer barrido parametrico de frontera.

Fase 1 de la arquitectura de mejora de estrategia: validar que el builder
produce observaciones que `main.agent()` procesa igual que las reales.

Validacion "contra la realidad": la replica sintetica del paso 69 de
registro_008 (vs Crustle/Kangaskhan) debe producir la MISMA decision que la
observacion real (Ultra Ball busca Hydrapple ex para evolucionar al Dipplin
activo condenado). A partir de ahi, el barrido parametrico fabrica variantes
que NUNCA ocurrieron en partidas (activo rival inmune, Dipplin sin energia)
y verifica las fronteras de la regla `_ub_evo_doomed_hittable`.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import C, G, Escenario, EstadoInconsistente, pk

# IDs que no estan en nuestro deck.csv (cartas del rival).
KANGASKHAN = 756
CRUSTLE = 345
DWEBBLE = 344
HEROS_CAPE = 1159


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


def _escenario_paso69(op_activo="kangaskhan", energia_dipplin=2):
    """Replica sintetica del paso 69 de registro_008 con variantes.

    op_activo: "kangaskhan" (golpeable por ex) o "crustle" (inmune a ex,
        con el Kangaskhan relegado a la banca).
    energia_dipplin: 2 = como el real (1 fisica x Meganium = [G, G], ataca
        tras evolucionar); 0 = sin energia (no ataca tras evolucionar).
    """
    kang = pk(KANGASKHAN, hp=160, max_hp=400, energias=[C, G, C, C],
              fisicas=4, tools=[HEROS_CAPE])
    crustle = pk(CRUSTLE, pre_evo=[DWEBBLE])
    if op_activo == "kangaskhan":
        activo_rival, banca_rival = kang, crustle
    else:
        activo_rival, banca_rival = crustle, kang

    if energia_dipplin == 2:
        dipplin = pk(m.Dipplin, energias=[G, G], fisicas=1,
                     pre_evo=[m.Applin])
    else:
        dipplin = pk(m.Dipplin, energias=[], fisicas=0, pre_evo=[m.Applin])

    esc = (Escenario(turno=8, paso=69, tac=3, primer_jugador=1)
           .mi_activo(dipplin)
           .mi_banca(pk(m.Meganium, pre_evo=[m.Chikorita, m.Bayleef]),
                     pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G], fisicas=1),
                     m.Meowth_ex)
           .mi_mano()
           .estadio(m.Forest_of_Vitality)
           .op_activo(activo_rival)
           .op_banca(banca_rival)
           .op_zonas(mano=9, mazo=37, premios=2)
           .op_descarte(m.Xerosic_Machinations, m.Lillie_Determination,
                        m.Lillie_Determination, 1264)
           # Mazo visible: composicion real del select.deck del paso 69.
           .mazo(m.Hydrapple_ex, m.Tapu_Bulu, m.Lillie_Determination,
                 m.Basic_Grass_Energy, m.Basic_Grass_Energy,
                 m.Basic_Grass_Energy, m.Basic_Grass_Energy,
                 m.Basic_Grass_Energy, m.Basic_Grass_Energy,
                 m.Teal_Mask_Ogerpon_ex, m.Hydrapple_ex, m.Chikorita,
                 m.Bug_Catching_Set, m.Night_Stretcher, m.Night_Stretcher,
                 m.Ultra_Ball, m.Boss_Orders, m.Xerosic_Machinations,
                 m.Lillie_Determination, m.Lillie_Determination,
                 m.Forest_of_Vitality, m.Forest_of_Vitality)
           # OJO: fetch_ultra_ball() ANTES de resto_al_descarte(), para que
           # la Ultra Ball "en efecto" se reserve del pool y no acabe en el
           # descarte (la contabilidad estricta lo detecta si se invierte).
           .fetch_ultra_ball()
           .resto_al_descarte())
    return esc.construir()


def _carta_elegida(obs, eleccion):
    assert eleccion, f"el agente cancelo el fetch: {eleccion}"
    opt = obs["select"]["option"][eleccion[0]]
    return obs["select"]["deck"][opt["index"]]["id"]


# ---------------------------------------------------------------------
# Validacion del builder contra la decision real (paso 69)
# ---------------------------------------------------------------------

def test_replica_sintetica_paso69_coincide_con_decision_real():
    obs = _escenario_paso69()
    eleccion = m.agent(obs)
    assert _carta_elegida(obs, eleccion) == m.Hydrapple_ex, (
        "la replica sintetica del paso 69 debe reproducir la decision del "
        "escenario real: buscar Hydrapple ex para evolucionar al Dipplin "
        "activo condenado")


# ---------------------------------------------------------------------
# Barrido de frontera de `_ub_evo_doomed_hittable` (estados que NUNCA
# ocurrieron en partidas reales)
# ---------------------------------------------------------------------

@pytest.mark.parametrize("op_activo,energia_dipplin,espera_hydrapple", [
    # activo rival golpeable + Dipplin ataca tras evolucionar -> excepcion
    ("kangaskhan", 2, True),
    # activo rival INMUNE a ex -> la excepcion no aplica, vuelve el clamp
    ("crustle", 2, False),
    # Dipplin sin energia: evoluciona pero NO ataca -> sin excepcion
    ("kangaskhan", 0, False),
])
def test_frontera_ub_evo_doomed(op_activo, energia_dipplin, espera_hydrapple):
    obs = _escenario_paso69(op_activo=op_activo,
                            energia_dipplin=energia_dipplin)
    eleccion = m.agent(obs)
    elegida = _carta_elegida(obs, eleccion)
    if espera_hydrapple:
        assert elegida == m.Hydrapple_ex, (
            f"con activo rival golpeable y Dipplin que ataca tras "
            f"evolucionar, el fetch debe ser Hydrapple ex; fue {elegida}")
    else:
        assert elegida != m.Hydrapple_ex, (
            f"({op_activo}, e={energia_dipplin}): la excepcion no aplica y "
            f"el clamp vs Crustle debe impedir el fetch de Hydrapple ex; "
            f"fue {elegida}")


# ---------------------------------------------------------------------
# La contabilidad del builder rechaza estados imposibles
# ---------------------------------------------------------------------

def test_builder_rechaza_mas_copias_que_el_mazo():
    esc = Escenario().mi_activo(pk(m.Dipplin, pre_evo=[m.Applin]))
    with pytest.raises(EstadoInconsistente):
        # deck.csv tiene 2 Hydrapple ex: la 3a copia debe fallar.
        esc.mazo(m.Hydrapple_ex, m.Hydrapple_ex, m.Hydrapple_ex)


def test_builder_rechaza_sobrante_distinto_de_premios():
    esc = (Escenario()
           .mi_activo(pk(m.Dipplin, pre_evo=[m.Applin]))
           .op_activo(pk(KANGASKHAN, hp=160, max_hp=400))
           # mazo declarado de 2 cartas: sobran ~50 sin colocar (mucho mas
           # que los 6 premios) -> la construccion debe fallar.
           .mazo(m.Hydrapple_ex, m.Tapu_Bulu)
           .fetch_ultra_ball())
    with pytest.raises(EstadoInconsistente):
        esc.construir()


# ---------------------------------------------------------------------
# Linea Meganium prioritaria vs Cornerstone Mask Ogerpon ex (user,
# registro_004 turno 4): su Cornerstone Stance anula el dano de TODOS
# nuestros Pokemon CON habilidad (Teal Mask Ogerpon ex, Hydrapple ex,
# Dipplin...), asi que el unico atacante real es Tapu Bulu. Meganium tampoco
# le hace dano -- tambien tiene habilidad -- pero su Wild Growth DUPLICA cada
# Planta, de modo que con el en juego Tapu ataca con 2 Plantas FISICAS en vez
# de 4. Montar la linea es por tanto prioritario en este matchup.
#
# Escenario SINTETICO (no existe en los registros vigentes: ninguno llega a
# jugar Ultra Ball frente a Cornerstone), justo el caso para el StateBuilder.
# ---------------------------------------------------------------------
CORNERSTONE = 117
CUBCHOO = 506


def _fetch_ub_vs(op_id):
    """Fetch de Ultra Ball con Chikorita en banca y la linea en el mazo."""
    obs = (Escenario(turno=6, paso=1, tac=1)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1))
           .mi_banca(pk(m.Chikorita))
           .mi_mano()
           .op_activo(pk(op_id, hp=210, max_hp=210))
           .op_zonas(mano=4, mazo=40, premios=6)
           .mazo(m.Meganium, m.Bayleef, m.Tapu_Bulu, m.Teal_Mask_Ogerpon_ex,
                 m.Hydrapple_ex, m.Applin, m.Chikorita, m.Meowth_ex)
           .fetch_ultra_ball()
           .resto_al_descarte()
           .construir())
    eleccion = m.agent(obs)
    sel = obs["select"]
    return sel["deck"][sel["option"][eleccion[0]]["index"]]["id"]


def test_cornerstone_prioriza_linea_meganium():
    elegida = _fetch_ub_vs(CORNERSTONE)
    assert elegida in (m.Meganium, m.Bayleef), (
        f"vs Cornerstone, Wild Growth deja a Tapu Bulu atacando con 2 Plantas "
        f"fisicas en vez de 4: completar la linea Meganium es la busqueda "
        f"prioritaria; obtuvo {m.card_table[elegida].name}")


def test_sin_cornerstone_la_busqueda_no_cambia():
    # Frontera: sin Cornerstone la prioridad de matchup no aplica y el fetch
    # conserva su comportamiento normal (Bayleef, evolucion inmediata).
    elegida = _fetch_ub_vs(CUBCHOO)
    assert elegida == m.Bayleef, (
        f"sin Cornerstone el fetch no debe cambiar; obtuvo "
        f"{m.card_table[elegida].name}")
