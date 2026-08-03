"""PESCA DE REMATE: el ataque que hoy solo depende del ROBO.

Escenario (user, episodio 89328622, registro_004 paso 49 vs Marnie's
Grimmsnarl, PERDIDA):

    NOSOTROS (asiento 0)                     RIVAL (Marnie's Grimmsnarl)
    activo  Teal Mask Ogerpon ex 30/210      activo  Marnie's Grimmsnarl ex
            con 1 energia (Myriad pide 3)            320/320, 2 energias {D}
    banca   Meowth ex 170, Fezandipiti ex    banca   Morgrem 100 (2e),
            180 (1e), Applin 40, Ogerpon             Snorunt 70, Impidimp 70 (2e)
            ex 210 (0e), Bayleef 110 (0e)
    mano    Lillie's x2, Boss's, Hydrapple
            ex, Ultra Ball  (CERO energia)
    premios 6 - 6      mazo propio 38 cartas, 10 Plantas vivas

Ningun cuerpo podia atacar y no habia una sola Planta en la mano: el turno,
tal y como estaba, no hacia dano. Pero el remate SI existia, a dos cartas de
distancia:

    Lillie's Determination roba OCHO (6 premios intactos) -> 2 Plantas ->
    adjunte manual + Teal Dance -> Myriad Leaf Shower con 3 energias propias
    y 2 del rival = 30 + 30 x 5 = 180, x2 por DEBILIDAD Planta del Marnie's
    Grimmsnarl ex = 360 >= 320 PV. DOS premios.

Con 10 Plantas vivas en 42 cartas (38 de mazo + las 4 que Lillie's baraja),
robar 8 saca las 2 que faltan el **63%** de las veces.

El agente jugo Boss's Orders para arrastrar un Snorunt de 70 PV. El gusteo,
ademas de gastar el hueco de Supporter, DEGRADA el remate: Myriad Leaf Shower
escala con la energia de AMBOS activos, asi que cambiar un Grimmsnarl ex con
2 energias y debilidad Planta por un Snorunt pelado convierte un golpe de 360
en uno de 120. Y con el Supporter ya gastado las dos Lillie's se volvieron
carta muerta: la Ultra Ball las descarto para pagar su coste.

EL BUG: "cavar" no se medía, se asumía
--------------------------------------
Los vetos de orden de Lillie's (`ultra_ball_completa_linea`,
`cede_a_boss_ejecutable`) tratan el refresco como un desarrollo generico que
siempre puede esperar. Cuando el robo es la UNICA linea que ataca este turno,
eso es falso -- y cuanto vale depende de un numero que el agente nunca
calculaba: la probabilidad de que el robo traiga la energia.

EL ARREGLO: `_pesca_de_remate` + `_prob_al_menos`
-------------------------------------------------
`_pesca_de_remate` es el hermano CONSCIENTE DEL DANO de `_plan_de_planta`:
comparte su aritmetica de adjuntes (cuantas Plantas faltan, que vias pueden
apuntar a ese cuerpo hoy) y le anade a quien se ataca, cuanto dano sale y
cuantos premios cobra. `_prob_al_menos` (hipergeometrica sobre la creencia de
mazo) mide si el robo las trae. Con un KO de premios a >= `PESCA_PROB_MIN`,
Lillie's sube a `LILLIE_SCORE_PESCA_REMATE` (5900, por encima de todo el
ladder de Boss's que no gana la partida) y Boss's cede el turno.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Escenario, G, pk

OGERPON = m.Teal_Mask_Ogerpon_ex
LILLIE = m.Lillie_Determination
BOSS = m.Boss_Orders
GRASS = m.Basic_Grass_Energy

# Cartas del rival (no estan en nuestro deck.csv).
GRIMMSNARL = 648
MORGREM = 647
IMPIDIMP = 646
SNORUNT = 860
DARK = 7

_FIX = ROOT / "tests" / "fixtures" / "marnie_pesca_de_remate_step49.json"


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.meganium_in_play = False
    m.forest_in_play = False
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    yield
    m._init_cartas_tracking()


def _fixture():
    with open(_FIX, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _idx_play_de(obs, card_id):
    """Indice de la opcion PLAY que juega `card_id` de la mano."""
    yo = obs["current"]["yourIndex"]
    mano = obs["current"]["players"][yo]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o["type"] == int(m.OptionType.PLAY) and mano[o["index"]]["id"] == card_id:
            return i
    return -1


def _espiar_pesca(monkeypatch):
    """Captura el `_PescaRemate` que calcula el agente en la decision."""
    capturado = {}
    original = m._pesca_de_remate

    def espia(*args, **kwargs):
        plan = original(*args, **kwargs)
        capturado["plan"] = plan
        return plan

    monkeypatch.setattr(m, "_pesca_de_remate", espia)
    return capturado


# ---------------------------------------------------------------------------
# El tablero: que el remate existia de verdad, medido con el motor
# ---------------------------------------------------------------------------

def test_el_remate_existia_myriad_con_tres_energias_noquea_al_grimmsnarl():
    obs = m.to_observation_class(_fixture())
    st = obs.current
    yo, rival = st.players[0], st.players[1]

    activo = yo.active[0]
    assert activo.id == OGERPON and activo.hp == 30
    assert len(activo.energies) == 1, "1 de las 3 energias de Myriad"
    assert m.ATTACK_ENERGY_REQ[OGERPON] == 3
    assert not any(c["id"] == GRASS for c in _fixture()["current"]
                   ["players"][0]["hand"]), "ni una Planta en la mano"

    opa = rival.active[0]
    assert opa.id == GRIMMSNARL and opa.hp == 320
    assert m.prize_count_op(opa) == 2, "el Grimmsnarl ex vale DOS premios"

    # Myriad Leaf Shower con las 3 propias + las 2 del rival, y debilidad Planta.
    base = m._attacker_base_damage(OGERPON, opa, 3, grass_scale=3,
                                   teal_self_energy=3, bench_count=5)
    assert base == 180
    dano = m._our_effective_damage(activo, opa, base, False, False)
    assert dano == 360 >= (opa.hp or 0), "debilidad Planta: 180 x 2"


def test_el_gusteo_degrada_el_objetivo_del_remate():
    """Myriad escala con la energia de AMBOS activos: subir el Snorunt pelado
    cambia un golpe de 360 por uno de 120."""
    obs = m.to_observation_class(_fixture())
    rival = obs.current.players[1]
    activo = obs.current.players[0].active[0]
    snorunt = next(b for b in rival.bench if b is not None and b.id == SNORUNT)

    base_snorunt = m._attacker_base_damage(OGERPON, snorunt, 3, grass_scale=3,
                                           teal_self_energy=3, bench_count=5)
    dano_snorunt = m._our_effective_damage(activo, snorunt, base_snorunt,
                                           False, False)
    assert dano_snorunt == 120, "sin energia rival que sumar y sin debilidad"
    assert m.prize_count_op(snorunt) == 1 < 2


# ---------------------------------------------------------------------------
# La hipergeometrica
# ---------------------------------------------------------------------------

def test_prob_al_menos_reproduce_el_63_por_ciento_del_registro():
    # Realidad del registro: 10 Plantas vivas en el mazo de 42 (38 + las 4 que
    # Lillie's baraja), robo 8.
    assert m._prob_al_menos(10, 42, 8, 2) == pytest.approx(0.6257, abs=1e-4)
    assert m._prob_al_menos(10, 42, 8, 1) == pytest.approx(0.9109, abs=1e-4)
    assert m._prob_al_menos(10, 42, 8, 3) == pytest.approx(0.2802, abs=1e-4)
    # Lo que el agente puede SABER (creencia: mazo + premios boca abajo son
    # cartas no vistas): 11 en 48. Conservador, nunca optimista.
    assert m._prob_al_menos(11, 48, 8, 2) == pytest.approx(0.5976, abs=1e-4)


def test_prob_al_menos_fronteras():
    assert m._prob_al_menos(0, 40, 8, 1) == 0.0        # sin outs
    assert m._prob_al_menos(10, 40, 8, 0) == 1.0       # no hace falta nada
    assert m._prob_al_menos(1, 40, 8, 2) == 0.0        # menos copias que k
    assert m._prob_al_menos(10, 40, 1, 2) == 0.0       # menos robo que k
    assert m._prob_al_menos(40, 40, 8, 8) == 1.0       # mazo entero de outs


def test_el_robo_de_lillie_es_ocho_solo_con_los_seis_premios():
    assert m._robo_de_lillie(6) == 8
    assert m._robo_de_lillie(5) == 6
    assert m._robo_de_lillie(1) == 6


# ---------------------------------------------------------------------------
# La decision real del paso 49
# ---------------------------------------------------------------------------

def test_paso49_pesca_dos_cartas_por_dos_premios(monkeypatch):
    capturado = _espiar_pesca(monkeypatch)
    m.agent(_fixture())
    plan = capturado["plan"]

    assert plan is not None
    assert plan.atacante_id == OGERPON and not plan.desde_banca
    assert plan.cartas == 2, "faltan DOS Plantas (adjunte manual + Teal Dance)"
    assert plan.letal and plan.premios == 2
    assert plan.dano == 360
    # La creencia cuenta lo NO VISTO (mazo 38 + 6 premios): 11 Plantas en 48
    # cartas tras barajar las 4 de la mano. Estimacion conservadora del 0.63
    # real (10 Plantas vivas en el mazo de 42).
    assert plan.robo == 8 and plan.outs == 11 and plan.universo == 48
    assert plan.prob == pytest.approx(0.5976, abs=1e-4)


def test_paso49_juega_lillie_para_pescar_no_boss():
    obs = _fixture()
    eleccion = m.agent(obs)
    assert eleccion == [_idx_play_de(obs, LILLIE)], (
        "con el turno sin ataque posible y un KO de 2 premios a 2 cartas de "
        "distancia, el hueco de Supporter es de Lillie's")


def test_paso49_contrafactual_sin_pesca_vuelve_a_gustear(monkeypatch):
    """Control: si la pesca no se mide (umbral inalcanzable), reaparece el
    Boss's del registro. Es el cambio que la regla introduce, no otro."""
    monkeypatch.setattr(m, "PESCA_PROB_MIN", 1.1)
    obs = _fixture()
    assert m.agent(obs) == [_idx_play_de(obs, BOSS)]


# ---------------------------------------------------------------------------
# Fronteras sinteticas (StateBuilder): probabilidad, energia en mano
# ---------------------------------------------------------------------------

def _escenario_paso49(grass_en_mazo=10, grass_en_mano=0, con_adjunte=False):
    """Replica sintetica del paso 49 con el mazo parametrizado.

    grass_en_mazo: Plantas VIVAS en el mazo (el resto va al descarte).
    grass_en_mano: Plantas ya en la mano (0 = como el real).
    """
    mano = [LILLIE, BOSS, LILLIE, m.Hydrapple_ex, m.Ultra_Ball]
    mano += [GRASS] * grass_en_mano

    esc = (Escenario(turno=4, paso=49, tac=1, primer_jugador=1)
           .mi_activo(pk(OGERPON, hp=30, energias=[G], fisicas=1))
           .mi_banca(pk(m.Meowth_ex),
                     pk(m.Fezandipiti_ex, hp=180, energias=[G], fisicas=1),
                     pk(m.Applin),
                     pk(OGERPON),
                     pk(m.Bayleef, pre_evo=[m.Chikorita]))
           .mi_mano(*mano)
           .op_activo(pk(GRIMMSNARL, hp=320, max_hp=320,
                         energias=[DARK, DARK], pre_evo=[IMPIDIMP]))
           .op_banca(pk(MORGREM, hp=100, max_hp=100, energias=[DARK, DARK],
                        pre_evo=[IMPIDIMP]),
                     pk(SNORUNT, hp=70, max_hp=70),
                     pk(IMPIDIMP, hp=70, max_hp=70, energias=[DARK, DARK]))
           .op_zonas(mano=5, mazo=32, premios=6))

    # Mazo: las Plantas vivas pedidas + relleno del pool (incluye el Dipplin
    # que hace que la Ultra Ball "complete linea", como en el registro).
    # `_pool` (privado) = lo que queda de deck.csv tras colocar campo y mano.
    # Las Plantas que no van al mazo se declaran en el DESCARTE (visible), para
    # que la creencia de mazo vea exactamente `grass_en_mazo` outs.
    n_grass = min(grass_en_mazo, esc._pool[GRASS])
    esc.mi_descarte(*([GRASS] * (esc._pool[GRASS] - n_grass)))
    relleno = [cid for cid in sorted(esc._pool.elements()) if cid != GRASS]
    # El mazo llega a 38 cartas (como el real) mientras haya relleno de sobra;
    # con muchas Plantas en el descarte se queda mas corto (siempre dejando 6
    # cartas para los premios).
    ids_mazo = ([GRASS] * n_grass
                + relleno[:max(0, min(38 - n_grass, len(relleno) - 6))])
    esc.mazo(*ids_mazo).resto_al_descarte()
    obs = esc.menu_mano(con_adjunte=con_adjunte).construir()
    # `menu_mano` emite un PLAY por CADA carta de la mano; el simulador no. Se
    # quitan las dos que en el paso real no estaban en el menu: el Hydrapple ex
    # (evolucion sin su Dipplin en juego -- justo lo que hace que la Ultra Ball
    # "complete linea" y vete a Lillie's) y las Plantas, que se juegan por
    # ATTACH, no por PLAY.
    mano_obs = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if not (o["type"] == int(m.OptionType.PLAY)
                and mano_obs[o["index"]]["id"] in (m.Hydrapple_ex, GRASS))]
    return obs


def test_sintetico_reproduce_la_decision_real(monkeypatch):
    capturado = _espiar_pesca(monkeypatch)
    obs = _escenario_paso49()
    assert m.agent(obs) == [_idx_play_de(obs, LILLIE)]
    assert capturado["plan"].premios == 2


def test_con_el_mazo_seco_de_plantas_la_pesca_no_pisa_los_vetos(monkeypatch):
    """Frontera: con una sola Planta viva el robo NO puede traer las dos que
    faltan (prob 0) y el refresco pierde el privilegio."""
    capturado = _espiar_pesca(monkeypatch)
    obs = _escenario_paso49(grass_en_mazo=1)
    assert capturado is not None
    eleccion = m.agent(obs)
    assert capturado["plan"] is None, "sin outs suficientes no hay pesca"
    assert eleccion != [_idx_play_de(obs, LILLIE)]


def test_frontera_de_probabilidad(monkeypatch):
    """La pesca dispara arriba del umbral y calla debajo, con el MISMO tablero:
    lo unico que cambia es cuantas Plantas quedan vivas."""
    vistos = {}
    for grass in (3, 10):
        m._init_cartas_tracking()
        m._cartas_first_scan_done = False
        m._cartas_prizes_identified = False
        m._cartas_last_turn = -1
        capturado = _espiar_pesca(monkeypatch)
        obs = _escenario_paso49(grass_en_mazo=grass)
        juega_lillie = (m.agent(obs) == [_idx_play_de(obs, LILLIE)])
        vistos[grass] = (capturado["plan"].prob, juega_lillie)

    assert vistos[3][0] < m.PESCA_PROB_MIN < vistos[10][0]
    assert vistos[3][1] is False, "3 Plantas de 42 robando 8: no paga barajar"
    assert vistos[10][1] is True


def test_la_pesca_exitosa_se_convierte_en_ataque():
    """Cierre del bucle: con las 3 energias ya puestas (la pesca salio) y la
    mano vacia, el Ogerpon ex de 30 PV ATACA -- no retira ni cierra el turno."""
    esc = (Escenario(turno=4, paso=49, tac=6, primer_jugador=1,
                     energia_jugada=True, partidario_jugado=True)
           .mi_activo(pk(OGERPON, hp=30, energias=[G, G, G], fisicas=3))
           .mi_banca(pk(m.Meowth_ex),
                     pk(m.Fezandipiti_ex, hp=180, energias=[G], fisicas=1),
                     pk(m.Applin),
                     pk(OGERPON),
                     pk(m.Bayleef, pre_evo=[m.Chikorita]))
           .op_activo(pk(GRIMMSNARL, hp=320, max_hp=320,
                         energias=[DARK, DARK], pre_evo=[IMPIDIMP]))
           .op_banca(pk(MORGREM, hp=100, max_hp=100, energias=[DARK, DARK],
                        pre_evo=[IMPIDIMP]),
                     pk(SNORUNT, hp=70, max_hp=70))
           .op_zonas(mano=5, mazo=32, premios=6))
    esc.mazo(*sorted(esc._pool.elements())[:34]).resto_al_descarte()
    obs = esc.menu_mano(con_retirada=True, con_ataque=True).construir()
    eleccion = m.agent(obs)
    assert (obs["select"]["option"][eleccion[0]]["type"]
            == int(m.OptionType.ATTACK))


def test_con_la_energia_ya_en_mano_no_se_baraja_la_mano(monkeypatch):
    """Control critico: si la MANO ya trae las 2 Plantas que faltan, jugar
    Lillie's las devolveria al mazo. Ahi NO hay pesca: se carga."""
    capturado = _espiar_pesca(monkeypatch)
    obs = _escenario_paso49(grass_en_mano=2, con_adjunte=True)
    eleccion = m.agent(obs)

    assert capturado["plan"] is None, (
        "con la energia en la mano no se pesca: se adjunta")
    tipo = obs["select"]["option"][eleccion[0]]["type"]
    assert tipo == int(m.OptionType.ATTACH), (
        "la jugada es cargar al Ogerpon, no barajar la mano")
