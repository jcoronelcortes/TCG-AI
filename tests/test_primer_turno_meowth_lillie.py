"""Regla del PRIMER TURNO: Meowth ex existe SOLO para traer Lillie's.

Origen (user, log 88461779 pasos 6-22 vs Alakazam, PERDIDA): en NUESTRO primer
turno el agente jugo Ultra Ball -> Meowth ex (correcto: no habia Lillie's
Determination en la mano) pero el Last-Ditch Catch se llevo un Xerosic's
Machinations en vez de la Lillie's -- con cuatro copias vivas en el mazo. El
turno 1 no ataca, no evoluciona y (saliendo primeros) ni siquiera ofrece jugar
Supporters: lo unico que decide es cuanta MANO tendremos el turno 2. Xerosic se
quedo muerto en la mano, y ademas habriamos tenido que barajarlo con la propia
Lillie's del turno siguiente. Se pago Ultra Ball + un cuerpo de 2 premios en
banca + el turno entero por nada.

Regla completa (deck-agnostica), tal y como la enuncio el user:

  * primer turno CON Lillie's en la mano  -> no se hace NADA por bajar ni por
    buscar un Meowth ex (ni desde la mano ni con Ultra Ball);
  * primer turno SIN Lillie's en la mano  -> si se puede bajar Meowth ex de la
    mano o cavarlo con Ultra Ball...
  * ...pero el fetch de Last-Ditch trae SIEMPRE Lillie's Determination.

Unica excepcion conservada: el guard anti-DONK (banca vacia + KO rival
proyectado sobre nuestro activo solitario), donde Meowth ex no se baja por su
busqueda sino como cuerpo que evita perder la partida en el acto
(`_meowth_antidonk_now`, ver tests del fixture Cinderace en test_main.py).
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

FIXTURES = ROOT / "tests" / "fixtures"


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
    m._ub_engine_pivot_turn = False
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _fixture_obs(nombre):
    with open(FIXTURES / nombre, encoding="utf-8") as f:
        return json.load(f)["observation"]


# ---------------------------------------------------------------------------
# El fallo del log: el fetch del primer turno
# ---------------------------------------------------------------------------

def test_last_ditch_del_primer_turno_trae_lillie_no_xerosic():
    """Paso 16 del log 88461779, reproducido tal cual."""
    obs = _fixture_obs("alakazam_t1_last_ditch_busca_lillie_step16.json")
    sel = obs["select"]
    mazo = sel["deck"]
    ofrecidas = [mazo[o["index"]]["id"] for o in sel["option"]]
    assert m.Lillie_Determination in ofrecidas and m.Xerosic_Machinations in ofrecidas

    result = m.agent(obs)
    traido = mazo[sel["option"][result[0]]["index"]]["id"]
    assert traido == m.Lillie_Determination, (
        f"en NUESTRO primer turno el Last-Ditch trae Lillie's Determination; "
        f"trajo {m.card_table[traido].name}({traido})")


def test_prediccion_del_fetch_en_primer_turno_apunta_a_lillie():
    """El helper que decide ANTES de gastar el Meowth ve lo mismo que el prompt
    (coherencia menu <-> prompt): con Lillie's viva en el mazo, el objetivo
    predicho del primer turno es Lillie's aunque el matchup sea Alakazam con la
    mano rival gorda y un atacante fuerte en juego (la rama que se llevo el
    Xerosic en el log)."""
    mazo = {m.Xerosic_Machinations: {m.ESTADO_MAZO: 2},
            m.Lillie_Determination: {m.ESTADO_MAZO: 4}}
    supp = {m.Xerosic_Machinations: 600, m.Lillie_Determination: 500}
    objetivo, _ = m._meowth_fetch_prediccion(
        {}, supp, 5, True, 8, False, False, False, False, False, True,
        mazo, first_turn=True)
    assert objetivo == m.Lillie_Determination


def test_fuera_del_primer_turno_el_fetch_conserva_la_rama_xerosic():
    """La regla es SOLO del primer turno: en turnos posteriores el motor
    anti-Alakazam (capar Powerful Hand) sigue mandando."""
    mazo = {m.Xerosic_Machinations: {m.ESTADO_MAZO: 2},
            m.Lillie_Determination: {m.ESTADO_MAZO: 4}}
    supp = {m.Xerosic_Machinations: 600, m.Lillie_Determination: 500}
    objetivo, _ = m._meowth_fetch_prediccion(
        {}, supp, 5, True, 8, False, False, False, False, False, True,
        mazo, first_turn=False)
    assert objetivo == m.Xerosic_Machinations


def test_sin_lillie_en_el_mazo_el_primer_turno_no_degrada_al_resto():
    """Deck-agnostico: si el mazo no tiene ninguna Lillie's alcanzable, la
    regla no capa a nadie y decide la escalera normal."""
    mazo = {m.Xerosic_Machinations: {m.ESTADO_MAZO: 2}}
    supp = {m.Xerosic_Machinations: 600}
    objetivo, valor = m._meowth_fetch_prediccion(
        {}, supp, 5, True, 8, False, False, False, False, False, True,
        mazo, first_turn=True)
    assert objetivo == m.Xerosic_Machinations and valor > 40


# ---------------------------------------------------------------------------
# No cavar Meowth ex con Ultra Ball si la Lillie's ya esta en la mano
# ---------------------------------------------------------------------------

def _ctx_ub_meowth(hand, turno=1, lillie_in_mazo=4):
    return m._CtxUBMeowth(
        hand=hand, campo={}, bench_count=1, turno=turno, watchtower=False,
        supp_values={m.Lillie_Determination: 900}, lillie_in_mazo=lillie_in_mazo,
        any_supp_in_mazo=True, prefer_meowth_develop=True,
        hydra_dead_prefer_meowth=False, mega_dead_prefer_meowth=False,
        no_attacker_prefer_meowth=False, t1_going_second_meowth=False,
        dipplin_priority=False, active_cant_attack=True,
        mega_line_active=False, dragapult=False)


def _valor_ub_meowth(ctx):
    valor, _ = m._resolver_reglas(m._REGLAS_UB_MEOWTH, [], ctx, 50)
    return valor


def test_ub_no_cava_meowth_en_primer_turno_con_lillie_en_mano():
    m.we_go_first = True
    m._ub_engine_pivot_turn = True   # ni el motor de pivote levanta la regla
    ctx = _ctx_ub_meowth({m.Lillie_Determination: 1, m.Ultra_Ball: 1})
    assert _valor_ub_meowth(ctx) <= 10


def test_ub_no_cava_meowth_en_primer_turno_sin_lillie_en_el_mazo():
    m.we_go_first = True
    ctx = _ctx_ub_meowth({m.Ultra_Ball: 1}, lillie_in_mazo=0)
    assert _valor_ub_meowth(ctx) <= 10


def test_ub_si_cava_meowth_en_primer_turno_sin_lillie_en_mano():
    """El caso legitimo del log: sin Lillie's en mano y con copias en el mazo,
    la cadena Ultra Ball -> Meowth ex -> Lillie's SI se monta."""
    m.we_go_first = True
    m._ub_engine_pivot_turn = True
    ctx = _ctx_ub_meowth({m.Ultra_Ball: 1})
    assert _valor_ub_meowth(ctx) >= 1000


# ---------------------------------------------------------------------------
# El motor de disrupcion no secuestra el primer turno
# ---------------------------------------------------------------------------

class _CtxXerosic:
    """Minimo que consulta `_alakazam_dig_xerosic_engine`."""

    class _State:
        def __init__(self, turn):
            self.turn = turn
            self.supporterPlayed = False

    def __init__(self, turn, we_go_first):
        self.op_is_alakazam_deck = True
        self.op_hand_count = 9
        self.state = self._State(turn)
        self.we_go_first = we_go_first
        self.hand_counts = {m.Ultra_Ball: 1}
        self.cartas_en_mazo = {m.Xerosic_Machinations: {m.ESTADO_MAZO: 2},
                               m.Meowth_ex: {m.ESTADO_MAZO: 1}}
        self.field_counts = {}
        self.bench_count = 1


@pytest.mark.parametrize("turno,primeros", [(1, True), (2, False)])
def test_motor_xerosic_no_arranca_en_nuestro_primer_turno(turno, primeros):
    assert not m._alakazam_dig_xerosic_engine(_CtxXerosic(turno, primeros))


def test_motor_xerosic_sigue_activo_en_turnos_posteriores():
    assert m._alakazam_dig_xerosic_engine(_CtxXerosic(4, True))
