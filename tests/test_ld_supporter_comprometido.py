"""El Supporter que trajo el Last-Ditch Catch SE JUEGA.

Escenario (user, episodio 88786171, registro_002 pasos 18-22, turno 2 vs
Alakazam, GANADA con error):

    NOSOTROS                                RIVAL
    activo  Fezandipiti ex 210 0e           activo  Chikorita 50 1e
    banca   Applin (y el Meowth ex que      banca   Chikorita
            se baja en este mismo turno)
    mano    Forest of Vitality, Xerosic's Machinations, Dawn, Basic {G} Energy
    premios restantes: 6 - 6      (es NUESTRO primer turno)

Secuencia registrada del turno 2:

    Poke Pad -> Applin | Bug Catching Set | baja el Applin | **Ultra Ball
    (descarta 2 Plantas) -> Meowth ex** | **baja el Meowth ex** | **Last-Ditch
    Catch -> Lillie's Determination** | adjunta energia | ... y acto seguido
    juega el **DAWN** que ya tenia en la mano.

La cadena estaba bien pensada hasta el ultimo paso: se pagaron dos cartas de
descarte por la Ultra Ball y un cuerpo de 2 PREMIOS en la banca (el Meowth ex)
para traer la Lillie's -- que en nuestro primer turno con 6 premios roba OCHO
cartas -- y despues se gasto el unico hueco de Supporter del turno en otra
carta. La Lillie's se quedo muerta en la mano y el Meowth ex quedo en la banca
regalado, gratis, para nada.

Causa: NADIE obligaba a cobrar la busqueda.

  * `_meowth_fetch_pierde_el_turno` PREDICE, antes de bajar el Meowth, que el
    fetch se llevara el hueco de Supporter -- pero no se evalua en NUESTRO
    PRIMER TURNO (la linea anti-donk baja el Meowth igual) y, sobre todo, no
    obliga a nada DESPUES del fetch;
  * con la mano nueva el scorer de jugada volvia a decidir desde cero y ahi
    gobernaba un veto de TABLERO -- `no_barajar_ultimo_xerosic` (-1), que
    protege el acceso al Xerosic's Machinations vs Alakazam -- que no sabe nada
    de que la Lillie's ya esta PAGADA con un cuerpo de 2 premios.

Arreglo: `_ld_supp_comprometido`, hermano de `_ub_meowth_pending` /
`_ub_fez_pending`. Cuando el Last-Ditch de un Meowth ex bajado ESTE turno
(`appearThisTurn`: el cuerpo esta pagado) elige un Supporter, ese id se queda
con el hueco del turno: piso de score por encima de cualquier otro Supporter
(`SCORE_LD_SUPP_COMPROMETIDO`) y veto para el resto de `_SUPP_PLAY_IDS` de la
mano. Es una regla de COMPROMISO, no de valor: el recurso ya se gasto.

Lo que NO cambia: el Last-Ditch de un Meowth ex de turnos ANTERIORES es gratis
y no compromete nada (puede guardar el Supporter para el turno siguiente, mismo
criterio que `_meowth_skip_fetch`); el piso se aplica con `max()`, asi que un
Boss's ganador conserva su score; y el compromiso se resetea por turno.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from parcheo import instalar
from state_builder import C, G, Escenario, pk

MEOWTH = m.Meowth_ex
LILLIE = m.Lillie_Determination
DAWN = m.Dawn
XEROSIC = m.Xerosic_Machinations
BOSS = m.Boss_Orders
FOREST = m.Forest_of_Vitality
FEZ = m.Fezandipiti_ex
APPLIN = m.Applin
OGERPON = m.Teal_Mask_Ogerpon_ex
ENERGIA = m.Basic_Grass_Energy

CHIKORITA_RIVAL = 917               # activo/banca rival del registro
ABRA = 843                          # basico de la linea Alakazam (sintetico)

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_ld_supporter_comprometido_step22.json")


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


def _observaciones():
    """Las 5 observaciones de NUESTRO turno 2 (turnActionCount 9..13)."""
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observaciones"]


def _por_accion(obs_list):
    return {o["current"]["turnActionCount"]: o for o in obs_list}


def _jugada(obs, eleccion):
    """('PLAY'|'CARTA', card_id) / ('ATTACH'|'RETREAT'|'END', None)."""
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
    if tipo == int(m.OptionType.ATTACH):
        return ("ATTACH", None)
    if tipo == int(m.OptionType.RETREAT):
        return ("RETREAT", None)
    if tipo == int(m.OptionType.END):
        return ("END", None)
    return (tipo, None)


def _jugadas(obs):
    return [_jugada(obs, [i]) for i in range(len(obs["select"]["option"]))]


def _reproducir(obs_list):
    """Reproduce el turno EN ORDEN y devuelve {turnActionCount: jugada}."""
    hecho = {}
    for obs in obs_list:
        hecho[obs["current"]["turnActionCount"]] = _jugada(obs, m.agent(obs))
    return hecho


# ---------------------------------------------------------------------------
# 1. El turno real: la cadena se cobra
# ---------------------------------------------------------------------------

def test_paso22_juega_la_lillie_que_trajo_el_last_ditch():
    hecho = _reproducir(_observaciones())
    # La cadena, paso a paso: se baja el Meowth ex...
    assert hecho[9] == ("PLAY", MEOWTH)
    # ...su Last-Ditch Catch busca la Lillie's...
    assert hecho[11] == ("CARTA", LILLIE)
    # ...y el hueco de Supporter del turno es SUYO (antes: Dawn).
    assert hecho[13] == ("PLAY", LILLIE)


def test_paso22_el_menu_ofrecia_de_verdad_las_dos_jugadas():
    """Sin las dos en el menu el test no discriminaria nada."""
    obs13 = _por_accion(_observaciones())[13]
    jugadas = _jugadas(obs13)
    assert ("PLAY", LILLIE) in jugadas, jugadas
    assert ("PLAY", DAWN) in jugadas, jugadas
    assert ("PLAY", XEROSIC) in jugadas, jugadas


def test_paso22_el_compromiso_es_lo_unico_que_decide():
    """Documenta el estado que hacia inevitable el error: con el tablero de ese
    menu, el scorer de Lillie's la VETA (`no_barajar_ultimo_xerosic`) y el de
    Dawn puntua positivo. Sin el compromiso gana Dawn."""
    obs_list = _observaciones()
    visto = {}
    orig = m._score_dawn_play

    def espia(ctx):
        visto["ctx"] = ctx
        return orig(ctx)

    _rest_score_dawn_play = instalar("_score_dawn_play", espia)
    try:
        _reproducir(obs_list)
    finally:
        _rest_score_dawn_play()
    ctx = visto["ctx"]
    assert m._score_lillie_determination_play(ctx) == m.SCORE_VETO
    assert orig(ctx) > 0
    # Y el compromiso quedo armado con la carta que trajo el fetch.
    assert m._ld_supp_comprometido == LILLIE


# ---------------------------------------------------------------------------
# 2. El compromiso solo nace del cuerpo PAGADO
# ---------------------------------------------------------------------------

def test_el_last_ditch_gratis_no_compromete_el_turno():
    """Un Meowth ex de turnos ANTERIORES busca gratis: puede guardarse el
    Supporter para el turno siguiente y el resto de la mano manda. Se replica
    apagando `appearThisTurn` del Meowth de la banca."""
    obs_list = _observaciones()
    for obs in obs_list:
        for pkm in obs["current"]["players"][obs["current"]["yourIndex"]]["bench"]:
            if pkm["id"] == MEOWTH:
                pkm["appearThisTurn"] = False
    hecho = _reproducir(obs_list)
    assert hecho[11] == ("CARTA", LILLIE)      # el fetch no cambia
    assert m._ld_supp_comprometido == 0        # pero no compromete el turno
    assert hecho[13] == ("PLAY", DAWN)         # decide el scorer, como antes


def test_el_compromiso_se_resetea_por_turno():
    """El Supporter comprometido vale para ESTE turno: si el turno cambia sin
    haberlo jugado, el compromiso se cae (no arrastra vetos al turno siguiente).
    """
    obs_list = _observaciones()
    _reproducir(obs_list)
    assert m._ld_supp_comprometido == LILLIE
    siguiente = json.loads(json.dumps(_por_accion(obs_list)[13]))
    siguiente["current"]["turn"] += 2
    siguiente["current"]["turnActionCount"] = 1
    m.agent(siguiente)
    assert m._ld_supp_comprometido == 0


# ---------------------------------------------------------------------------
# 3. Generalizacion sintetica: la regla no nombra cartas
# ---------------------------------------------------------------------------

def _menu_sintetico(mano):
    """Tablero neutro (turno medio, sin matchup especial) con `mano` en la mano
    y un menu de PLAY por carta."""
    return (Escenario(turno=8, paso=60, tac=4)
            .mi_activo(pk(OGERPON, energias=[G, G]))
            .mi_banca(pk(MEOWTH, aparecio=True), APPLIN)
            .mi_mano(*mano)
            .op_activo(pk(CHIKORITA_RIVAL, energias=[C]))
            .op_banca(pk(ABRA, hp=70, max_hp=70))
            .op_zonas(mano=5, mazo=30, premios=5)
            .menu_mano()
            .construir())


def _armar(obs, sid):
    """Deja el compromiso armado sobre `sid` para ESTE turno.

    La primera llamada a `agent` consume el reset por turno (que pone el
    compromiso a 0); el flag se arma despues, como en la partida real, donde lo
    escribe el propio fetch a mitad del turno."""
    m.agent(obs)
    m._ld_supp_comprometido = sid


def test_el_compromiso_gana_el_hueco_a_cualquier_otro_supporter():
    """Con el compromiso armado, cualquier OTRO Supporter de la mano cede el
    hueco -- se prueba con un par de cartas distinto al del registro."""
    obs = _menu_sintetico([BOSS, XEROSIC])
    jugadas = _jugadas(obs)
    assert ("PLAY", BOSS) in jugadas, jugadas
    assert ("PLAY", XEROSIC) in jugadas, jugadas

    _armar(obs, BOSS)
    assert _jugada(obs, m.agent(obs)) == ("PLAY", BOSS)

    m._ld_supp_comprometido = XEROSIC
    assert _jugada(obs, m.agent(obs)) == ("PLAY", XEROSIC)


def test_el_piso_esta_por_encima_de_la_banda_normal_de_supporters():
    """La regla es UN SOLO gesto (piso con `max()`), sin vetar al resto: eso
    solo funciona si el piso supera la banda normal de cualquier Supporter.
    Fijar el margen aqui evita que un scorer futuro lo adelante en silencio.

    Su contrapartida es la valvula de seguridad medida en el gate: un Supporter
    DECISIVO (score > piso, p.ej. un Boss's que gana la partida) sigue pudiendo
    quedarse con el turno. Anadir el veto costaba -0.67 puntos de winrate
    (6000 partidas por variante); solo el piso da +0.40."""
    obs = _menu_sintetico([BOSS, XEROSIC])
    m.agent(obs)                      # deja el ctx del turno construido
    visto = {}
    orig = m._score_xerosic_play

    def espia(ctx):
        visto["ctx"] = ctx
        return orig(ctx)

    _rest_score_xerosic_play = instalar("_score_xerosic_play", espia)
    try:
        m.agent(obs)
    finally:
        _rest_score_xerosic_play()
    ctx = visto["ctx"]
    for sid in m._SUPP_PLAY_IDS:
        assert m._supp_play_score(ctx, sid) < m.SCORE_LD_SUPP_COMPROMETIDO


def test_el_compromiso_no_aplica_con_el_hueco_ya_gastado():
    """`supporterPlayed` manda: el compromiso no resucita un hueco gastado."""
    obs = _menu_sintetico([BOSS, XEROSIC])
    obs["current"]["supporterPlayed"] = True
    _armar(obs, BOSS)
    assert _jugada(obs, m.agent(obs))[1] != BOSS


def test_el_compromiso_se_desarma_si_su_carta_ya_no_esta_ofrecida():
    """Si el Supporter comprometido desaparece de la mano (coste de una Ultra
    Ball, barajado...) la regla no debe dejar vetado al resto del menu."""
    obs = _menu_sintetico([XEROSIC, m.Ultra_Ball])
    sin_compromiso = _jugada(obs, m.agent(obs))

    _armar(obs, BOSS)                     # comprometido... y ya no en la mano
    assert _jugada(obs, m.agent(obs)) == sin_compromiso
