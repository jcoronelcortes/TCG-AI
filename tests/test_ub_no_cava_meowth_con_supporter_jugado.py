"""La Ultra Ball solo se juega si hay algo que cavar Y ese algo se puede jugar.

Escenario (user, episodio 88693856, registro_006 pasos 98-104, turno 6 vs Mega
Lucario ex, PERDIDA):

    NOSOTROS                                    RIVAL
    activo  Hydrapple ex 330  2 {G}             activo  Mega Lucario ex 440/440
    banca   Teal Mask Ogerpon ex 2 {G}                  (con Hero's Cape)
            Fezandipiti ex 0 {G}                banca   Applin, Fezandipiti ex,
            Meganium 2 {G}                              Meowth ex, Meganium
    mano    Ultra Ball x2, Hydrapple ex, Lana's Aid, Dipplin, Boss's Orders,
            Forest of Vitality, Xerosic's Machinations, Basic {G} x2
    Supporter del turno: YA JUGADO (Lillie's Determination, accion 10)

El menu de la accion 16 solo ofrecia TRES cosas: las dos Ultra Ball, Syrup
Storm (30 + 30 por cada {G} del campo = 30 + 6x30 = **210 de dano**) y terminar.
El agente jugo las DOS Ultra Ball -descartando Forest of Vitality, Xerosic's
Machinations, Dipplin y Lana's Aid- para cavar los DOS Meowth ex del mazo... y
en la accion 22 lanzo el mismo Syrup Storm de 210 que podia haber lanzado en la
accion 16. Balance del turno: -4 cartas de mano y dos cuerpos de 2 PREMIOS
muertos en la mano, por exactamente cero.

Meowth ex vale EXCLUSIVAMENTE por su Last-Ditch Catch (buscar un Supporter).
Con el Supporter del turno ya jugado, el Supporter que traiga el fetch no se
puede jugar: la carta cavada nace muerta -- y la propia rama PLAY lo sabe
([[no-meowth-si-supporter-ya-jugado]]), tanto que vetaba bajar el Meowth (-1e5)
justo despues de haberlo cavado.

Fallaban TRES eslabones a la vez, y por eso ninguno de los vetos existentes
paraba la jugada:

  1. EL FETCH no comprobaba que la habilidad pudiera producir algo: la regla
     `lillie_en_mazo_refresco` daba 1000 a Meowth ex (ganando a Chikorita 30 /
     Meganium 25 / Bayleef 20) mirando solo si quedaba Lillie's en el mazo.
     Arreglo: `last_ditch_no_produce` (con el Supporter jugado o la Last-Ditch
     ya gastada, Meowth cae a 10, como con Watchtower).
  2. LA RED ANTI-TURNO-ESTERIL resucitaba la Ultra Ball vetada a 200 porque
     leia `scores[mejor] <= 0` como "el turno acaba en END". No es lo mismo: un
     ATAQUE normal puntua -1 por defecto, y los Items no consumen el ataque.
     Arreglo: un turno con un ataque que hace dano de verdad NO es esteril; y
     Meowth ex ya no cuenta como "basico util" si su Last-Ditch no produce.
  3. EL PISO DEL VETO era SCORE_VETO (-1), el mismo que el ataque, asi que en
     la accion 19 -con la red ya desactivada- la Ultra Ball ganaba el desempate
     por INDICE del menu. Arreglo: SCORE_CANCEL (-100) en los vetos de "esta
     Ultra Ball no aporta nada", que es justo para lo que existe esa constante.

Lo que NO cambia: la Ultra Ball sigue cavando Meowth ex cuando el hueco de
Supporter esta libre y la Last-Ditch disponible (motores UB->Meowth->Lillie's y
UB->Meowth->Xerosic, que ya exigian `not supporterPlayed`), y la red
anti-turno-esteril sigue rescatando los turnos que de verdad acaban en END.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

MEOWTH = m.Meowth_ex
CHIKORITA = m.Chikorita
ULTRA_BALL = m.Ultra_Ball
SYRUP_STORM = 195

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "lucario_ub_no_cava_meowth_con_supporter_jugado_step98.json")


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
    """Las 7 observaciones de NUESTRO turno 6 (turnActionCount 16..22)."""
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observaciones"]


def _por_accion(obs_list):
    return {o["current"]["turnActionCount"]: o for o in obs_list}


def _jugada(obs, eleccion):
    """('PLAY'|'CARTA', card_id) / ('ATTACK', attackId) / ('END', None)."""
    o = obs["select"]["option"][eleccion[0]]
    tipo = o["type"]
    yo = obs["current"]["yourIndex"]
    jugador = obs["current"]["players"][yo]
    if tipo == int(m.OptionType.PLAY):
        return ("PLAY", jugador["hand"][o["index"]]["id"])
    if tipo == int(m.OptionType.CARD):
        if o.get("area") == int(m.AreaType.DECK) and obs["select"].get("deck"):
            return ("CARTA", obs["select"]["deck"][o["index"]]["id"])
        return ("CARTA", None)
    if tipo == int(m.OptionType.ATTACK):
        return ("ATTACK", o.get("attackId"))
    if tipo == int(m.OptionType.END):
        return ("END", None)
    return (tipo, None)


def _jugadas(obs):
    return [_jugada(obs, [i]) for i in range(len(obs["select"]["option"]))]


def _reproducir(obs_list):
    """Reproduce el turno EN ORDEN y devuelve {turnActionCount: jugada}."""
    return {o["current"]["turnActionCount"]: _jugada(o, m.agent(o))
            for o in obs_list}


# ---------------------------------------------------------------------------
# 1. El turno real: se ataca en vez de encadenar dos Ultra Ball
# ---------------------------------------------------------------------------

def test_paso98_ataca_en_vez_de_cavar_un_meowth_que_no_se_puede_jugar():
    hecho = _reproducir(_observaciones())
    assert hecho[16] == ("ATTACK", SYRUP_STORM), hecho[16]


def test_paso101_la_segunda_ultra_ball_tampoco_se_juega():
    """El log real repite el error: con la 1a Ultra Ball ya gastada el menu
    vuelve a ofrecer Ultra Ball / Meowth ex / atacar, y se volvia a cavar."""
    hecho = _reproducir(_observaciones())
    assert hecho[19] == ("ATTACK", SYRUP_STORM), hecho[19]


def test_el_menu_ofrecia_de_verdad_las_dos_jugadas():
    """Sin la Ultra Ball Y el ataque en el menu el test no discrimina nada."""
    for tac in (16, 19):
        jugadas = _jugadas(_por_accion(_observaciones())[tac])
        assert ("PLAY", ULTRA_BALL) in jugadas, (tac, jugadas)
        assert ("ATTACK", SYRUP_STORM) in jugadas, (tac, jugadas)


# ---------------------------------------------------------------------------
# 2. Los tres eslabones, uno a uno
# ---------------------------------------------------------------------------

def test_el_fetch_no_elige_meowth_con_el_supporter_del_turno_jugado():
    """Si aun asi se jugara una Ultra Ball, el fetch NO trae Meowth ex: su
    Last-Ditch no puede producir un Supporter jugable este turno."""
    obs_list = _observaciones()
    hecho = {}
    for o in obs_list:
        # Se responde a TODOS los menus del registro (incluidos los de la Ultra
        # Ball que ya no jugariamos) para llegar al fetch con el estado tibio.
        hecho[o["current"]["turnActionCount"]] = _jugada(o, m.agent(o))
    assert hecho[18] == ("CARTA", CHIKORITA), hecho[18]
    assert hecho[21] == ("CARTA", CHIKORITA), hecho[21]


def test_la_ultra_ball_inutil_queda_por_debajo_del_piso_de_veto():
    """SCORE_CANCEL, no SCORE_VETO: si empatara con el ataque (-1) el
    desempate por indice del menu volveria a jugar la Ultra Ball."""
    visto = {}
    orig = m._score_ultra_ball_play

    def espia(ctx):
        r = orig(ctx)
        visto.setdefault(ctx.state.turnActionCount, []).append(r)
        return r

    m._score_ultra_ball_play = espia
    try:
        _reproducir(_observaciones())
    finally:
        m._score_ultra_ball_play = orig

    assert visto[16], visto
    for tac in (16, 19):
        for score in visto[tac]:
            assert score <= m.SCORE_CANCEL, (tac, score)
            assert score < m.SCORE_VETO, (tac, score)


def test_la_red_anti_turno_esteril_no_dispara_con_un_ataque_real():
    """El eslabon que resucitaba la Ultra Ball vetada a 200: un turno que acaba
    con Syrup Storm de 210 no es un turno muerto."""
    obs16 = _por_accion(_observaciones())[16]
    m.agent(obs16)
    # Si la red hubiera disparado, la Ultra Ball habria salido con 200 y el
    # agente la habria elegido; el ataque real es la prueba de que no lo hizo.
    assert _jugada(obs16, m.agent(obs16)) == ("ATTACK", SYRUP_STORM)


# ---------------------------------------------------------------------------
# 3. Lo que NO se rompe: con el hueco de Supporter libre, Meowth sigue siendo
#    el objetivo del fetch
# ---------------------------------------------------------------------------

def test_con_el_supporter_libre_el_fetch_sigue_eligiendo_meowth():
    """La regla nueva es un veto CONDICIONADO, no una prohibicion: el mismo
    menu de busqueda con `supporterPlayed` en False vuelve a traer Meowth ex
    (motor UB -> Meowth -> Last-Ditch -> Lillie's)."""
    obs_list = _observaciones()
    for o in obs_list[:2]:          # calienta el estado hasta el fetch
        m.agent(o)
    fetch = _por_accion(obs_list)[18]
    fetch = json.loads(json.dumps(fetch))
    fetch["current"]["supporterPlayed"] = False
    assert _jugada(fetch, m.agent(fetch)) == ("CARTA", MEOWTH)
