"""En un turno MUERTO, la recuperacion trae el motor de ROBO, no desarrollo.

Escenario (user, episodio 88704504, registro_008 pasos 66-67, turno 8 vs
Alakazam, PERDIDA):

    NOSOTROS                                    RIVAL
    activo  Teal Mask Ogerpon ex 210/210 0 {G}  activo  Alakazam 140/140 1 {G}
    banca   Dipplin 80  0 {G}                   banca   Fezandipiti ex 210,
            Bayleef 110 0 {G}                           Alakazam 140, Kadabra 80
    mano    Night Stretcher            <- UNA carta
    descarte  Meowth ex (recien noqueado), Meganium, 3 Plantas basicas...

Se jugo la Night Stretcher y se recupero el **Meganium**. Nada de eso se podia
jugar: el Bayleef estaba a 0 energias, asi que el Meganium no atacaba ni ese
turno ni el siguiente, y el turno acabo con **0 cartas en mano** y sin ningun
cuerpo capaz de atacar. El rival noqueaba al activo en su turno.

La carta que habia que recuperar era el **Meowth ex** que acababan de
noquearnos: bajarlo dispara Last-Ditch Catch -> busca un Supporter del mazo
(Lillie's Determination) -> se juega -> la mano entera se rehace. Un turno
muerto en ataque no se arregla con desarrollo; se arregla con cartas.

Por que fallaba: la tabla `ns->meganium` daba 990 (`bayleef_evolucionable`, que
solo mira que haya un Bayleef en juego sin evolucionar) y la de `ns->meowth`
como mucho 800 (`fetch_supporter_del_mazo`, acotada a `min(700, valor del mejor
Supporter del mazo)`). El desarrollo ganaba SIEMPRE.

Arreglo (deck-agnostico): `_sin_ataque_hoy` mide con `ATTACK_ENERGY_REQ` si
algun cuerpo llega a atacar hoy -- el activo tal cual, un atacante de banca al
que el activo pueda subir pagando su retirada, o cualquiera de los dos con UNA
energia mas si queda ruta de carga abierta. Si nadie llega y la mano queda seca
(<= 2 cartas), la regla `motor_de_robo_turno_muerto` pone al Meowth ex en 1250
y al Fezandipiti ex en 1200, por encima de todo el desarrollo (990 + 200 del
bonus por ultima copia = 1190) y por debajo de la energia que produce un ataque
HOY (1300/1400), que nunca coexiste con un turno muerto.

Orden entre los dos motores: primero Meowth ex (rehace la mano ENTERA via
Lillie's), despues Fezandipiti ex, y este ultimo SOLO si nos noquearon un
Pokemon en el turno anterior -- sin KO no hay Flip the Script y el cuerpo de 2
premios es un regalo.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_ns_motor_de_robo_turno_muerto_step67.json")

MEOWTH = m.Meowth_ex
MEGANIUM = m.Meganium
NIGHT_STRETCHER = m.Night_Stretcher


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
    m._ub_engine_pivot_turn = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _observaciones():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observaciones"])


def _carta_del_descarte(obs, eleccion):
    """Devuelve el id de la carta del DESCARTE que elige el agente."""
    o = obs["select"]["option"][eleccion[0]]
    assert o["type"] == int(m.OptionType.CARD), o
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["discard"][o["index"]]["id"]


def _reproducir(obs_list):
    """Reproduce el turno EN ORDEN; devuelve la eleccion del ultimo menu."""
    eleccion = None
    for o in obs_list:
        eleccion = m.agent(o)
    return eleccion


# ---------------------------------------------------------------------------
# 1. El turno real
# ---------------------------------------------------------------------------

def test_paso67_la_night_stretcher_recupera_el_meowth_no_el_meganium():
    obs_list = _observaciones()
    eleccion = _reproducir(obs_list)
    assert _carta_del_descarte(obs_list[-1], eleccion) == MEOWTH


def test_el_menu_ofrecia_de_verdad_las_dos_cartas():
    """Sin Meowth ex Y Meganium en el descarte el test no discrimina nada."""
    obs = _observaciones()[-1]
    yo = obs["current"]["yourIndex"]
    descarte = obs["current"]["players"][yo]["discard"]
    ofrecidas = {descarte[o["index"]]["id"]
                 for o in obs["select"]["option"]
                 if o["type"] == int(m.OptionType.CARD)}
    assert MEOWTH in ofrecidas, ofrecidas
    assert MEGANIUM in ofrecidas, ofrecidas


def test_el_paso66_si_juega_la_night_stretcher():
    """La cadena empieza jugando la carta: si el paso 66 terminara el turno,
    el paso 67 nunca existiria."""
    obs = _observaciones()[0]
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert o["type"] == int(m.OptionType.PLAY), o
    yo = obs["current"]["yourIndex"]
    assert obs["current"]["players"][yo]["hand"][o["index"]]["id"] == NIGHT_STRETCHER


# ---------------------------------------------------------------------------
# 2. El detector de turno muerto, aislado
# ---------------------------------------------------------------------------

def test_el_turno_esta_muerto_en_ataque():
    """Ogerpon ex pide 3 de energia efectiva y tiene 0; Teal Dance solo pone 1.
    Dipplin (1) y Bayleef (2) estan a 0 y el activo no paga su retirada."""
    obs_list = _observaciones()
    m.agent(obs_list[0])                      # calienta el estado del turno
    obs = m.to_observation_class(obs_list[-1])
    yo = obs.current.yourIndex
    my_state = obs.current.players[yo]
    field = {}
    for p in list(my_state.active or []) + list(my_state.bench or []):
        if p is not None:
            field[p.id] = field.get(p.id, 0) + 1
    assert m._sin_ataque_hoy(my_state, obs.current, field) is True


def test_una_energia_en_el_bayleef_resucita_el_turno():
    """El detector no es "no hay atacante": es "nadie llega HOY". Con el
    Bayleef a 1 energia efectiva, UNA Planta mas lo pone a 2 = su coste, asi
    que el turno ya NO esta muerto (aunque siga sin poder subirlo)."""
    obs_list = _observaciones()
    m.agent(obs_list[0])
    obs = m.to_observation_class(obs_list[-1])
    yo = obs.current.yourIndex
    my_state = obs.current.players[yo]
    field = {}
    for p in list(my_state.active or []) + list(my_state.bench or []):
        if p is not None:
            field[p.id] = field.get(p.id, 0) + 1
    # El activo paga su retirada (para poder SUBIR al de banca) y el Bayleef
    # queda a una energia de atacar.
    activo = my_state.active[0]
    activo.energies = [5] * m.RETREAT_COST.get(activo.id, 1)
    for b in my_state.bench:
        if b is not None and b.id == m.Bayleef:
            b.energies = [5]
    assert m._sin_ataque_hoy(my_state, obs.current, field) is False


# ---------------------------------------------------------------------------
# 3. Lo que NO se rompe
# ---------------------------------------------------------------------------

def test_con_lillie_ya_en_la_mano_el_motor_no_dispara():
    """Meowth ex vale por el Supporter que busca. Si el Supporter YA esta en la
    mano no hay nada que buscar y la recuperacion vuelve al desarrollo."""
    obs_list = _observaciones()
    m.agent(obs_list[0])
    fetch = obs_list[-1]
    yo = fetch["current"]["yourIndex"]
    fetch["current"]["players"][yo]["hand"] = [
        {"id": m.Lillie_Determination, "playerIndex": yo, "serial": 25}]
    fetch["current"]["players"][yo]["handCount"] = 1
    assert _carta_del_descarte(fetch, m.agent(fetch)) == MEGANIUM


def test_con_el_supporter_del_turno_ya_jugado_el_motor_no_dispara():
    """Sin hueco de Supporter, la Last-Ditch trae una carta injugable: el
    motor no produce nada y el desarrollo recupera la prioridad."""
    obs_list = _observaciones()
    m.agent(obs_list[0])
    fetch = obs_list[-1]
    fetch["current"]["supporterPlayed"] = True
    assert _carta_del_descarte(fetch, m.agent(fetch)) == MEGANIUM


def test_con_la_banca_llena_el_motor_no_dispara():
    """El Meowth ex recuperado hay que poder BAJARLO este turno."""
    obs_list = _observaciones()
    m.agent(obs_list[0])
    fetch = obs_list[-1]
    yo = fetch["current"]["yourIndex"]
    banca = fetch["current"]["players"][yo]["bench"]
    relleno = copy.deepcopy(banca[0])
    while len(banca) < 5:
        banca.append(copy.deepcopy(relleno))
    assert _carta_del_descarte(fetch, m.agent(fetch)) == MEGANIUM
