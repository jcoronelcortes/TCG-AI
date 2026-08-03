"""El forraje real NO cuenta el Supporter de REFRESCO protegido.

Origen (user, registro_004 pasos 43-64 vs Alakazam, PERDIDA -- log 88910273).
Turno 4, mano {Boss's x2, Ultra Ball x2, Tapu Bulu, Lillie's Determination},
Supporter sin jugar, rival con 8 cartas (Powerful Hand proyectado 20 x 10 =
200). `_alakazam_dig_xerosic_engine` armo la cadena de disrupcion -- Ultra Ball
(5950) -> Meowth ex -> Last-Ditch Catch -> Xerosic -- POR ENCIMA de la Lillie's
(5000), que es exactamente lo que ese motor existe para no jugar. La cadena
funciono: el Xerosic acabo en la mano.

Y entonces el agente lo tiro a la basura. Con la mano en {Boss's, Lillie's,
Ultra Ball, Xerosic}:

  * `_ub_forraje_real(prot=Xerosic)` contaba **2** -- el Boss's y la Lillie's --
    asi que `_ub_cancel_xerosic` NO saltaba;
  * la SEGUNDA Ultra Ball puntuo 11400 (objetivo de valor 800, banda de item) y
    gano al Xerosic (7200);
  * su coste de 2 descartes se pago con el Boss's y con EL PROPIO XEROSIC,
    porque el bloque SelectContext.DISCARD puntua la Lillie's a 2 y el Xerosic
    a 5: la Lillie's NUNCA cae primero;
  * la Ultra Ball cavo un SEGUNDO Meowth ex, inservible -- su Last-Ditch ya
    estaba gastada por el primero;
  * y el turno cerro jugando la Lillie's, que barajo ese Meowth de vuelta al
    mazo.

Saldo: Tapu Bulu, dos Boss's Orders, el Xerosic y las dos Ultra Ball perdidos
para acabar jugando EXACTAMENTE el Supporter que toda la cadena existia para no
jugar, con la mano rival intacta.

La causa es una sola: `_ub_forraje_real` sobrecontaba. Ya excluia del forraje lo
que el scorer de DISCARD protege MAS que la carta protegida (piezas de
evolucion, Fezandipiti ex tras un KO, Meowth ex todavia jugable -- ver el ajuste
del log 86401283), pero no los **Supporter de refresco**: con el Supporter del
turno libre y una sola copia en mano, `_protect_refresh_supporter` puntua la
Lillie's a 2 y el Dawn a 3, por debajo de cualquier carta que estos vetos
protegen. Contarlos como forraje era prometer un pago que el scorer de descarte
no iba a hacer.
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
FIXTURE = "alakazam_step50_no_quemar_el_xerosic_recien_cavado.json"


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


def _fixture_obs():
    with open(FIXTURES / FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _id_de_opcion(obs, idx):
    """Id de la carta de mano detras de la opcion `idx` (somos yourIndex 1)."""
    cur = obs["current"]
    opt = cur and obs["select"]["option"][idx]
    if opt.get("type") != 7 or "index" not in opt:
        return None
    yo = cur["players"][cur["yourIndex"]]
    return yo["hand"][opt["index"]]["id"]


# ---------------------------------------------------------------------------
# El fallo del log, reproducido tal cual
# ---------------------------------------------------------------------------

def test_paso_50_juega_el_xerosic_y_no_la_segunda_ultra_ball():
    obs = _fixture_obs()
    cur = obs["current"]
    yo = cur["players"][cur["yourIndex"]]

    # La cadena ya se completo: Meowth ex en banca y Xerosic en la mano.
    assert sorted(c["id"] for c in yo["hand"]) == sorted(
        [m.Boss_Orders, m.Lillie_Determination, m.Ultra_Ball,
         m.Xerosic_Machinations])
    assert cur["supporterPlayed"] is False
    assert cur["players"][0]["handCount"] == 8
    assert any(p["id"] == m.Meowth_ex for p in yo["bench"])

    elegido = _id_de_opcion(obs, m.agent(obs)[0])
    assert elegido == m.Xerosic_Machinations, (
        "la cadena Ultra Ball -> Meowth ex -> Last-Ditch acaba de cavar el "
        "Xerosic: la segunda Ultra Ball solo se puede pagar quemandolo, porque "
        "la Lillie's esta mas protegida que el (2 vs 5) y no cae primero")


# ---------------------------------------------------------------------------
# El predicado, aislado
# ---------------------------------------------------------------------------

class _Ctx:
    """Minimo que consulta `_ub_forraje_real`."""

    class _State:
        def __init__(self, supporter_played):
            self.supporterPlayed = supporter_played
            self.turn = 4

    def __init__(self, hand, supporter_played=False, campo=None):
        self.hand_counts = dict(hand)
        self.field_counts = dict(campo or {})
        self.bench_count = 4
        self.state = self._State(supporter_played)
        self.ko_last_turn = False
        self.op_is_crustle_deck = False
        self.op_has_ex_immune_active = False
        self.op_has_ex_immune_bench = False
        self.has_hydrapple = False
        self.forest_in_play = False
        self.cartas_en_mazo = {}


def test_la_lillie_protegida_no_es_forraje():
    """La mano exacta del paso 50: el unico forraje real es el Boss's."""
    ctx = _Ctx({m.Boss_Orders: 1, m.Lillie_Determination: 1,
                m.Ultra_Ball: 1, m.Xerosic_Machinations: 1})
    assert m._ub_forraje_real(ctx, m.Xerosic_Machinations) == 1


def test_el_dawn_protegido_tampoco_es_forraje():
    """Dawn puntua 3 con `_protect_refresh_supporter`: tampoco cae antes."""
    ctx = _Ctx({m.Boss_Orders: 1, m.Dawn: 1,
                m.Ultra_Ball: 1, m.Xerosic_Machinations: 1})
    assert m._ub_forraje_real(ctx, m.Xerosic_Machinations) == 1


def test_con_el_supporter_del_turno_ya_jugado_si_es_forraje():
    """Jugado el Supporter, la Lillie's pierde su proteccion de refresco y
    vuelve a ser descartable: el veto no debe congelarse para siempre."""
    ctx = _Ctx({m.Boss_Orders: 1, m.Lillie_Determination: 1,
                m.Ultra_Ball: 1, m.Xerosic_Machinations: 1},
               supporter_played=True)
    assert m._ub_forraje_real(ctx, m.Xerosic_Machinations) == 2


def test_la_copia_sobrante_de_lillie_si_es_forraje():
    """`_protect_refresh_supporter` solo cubre UNA copia (las demas puntuan 72
    en el bloque de descarte): con dos Lillie's el forraje vuelve a contarlas."""
    ctx = _Ctx({m.Lillie_Determination: 2, m.Ultra_Ball: 1,
                m.Xerosic_Machinations: 1})
    assert m._ub_forraje_real(ctx, m.Xerosic_Machinations) == 2


def test_protegiendo_la_propia_lillie_el_dawn_sigue_siendo_forraje():
    """Con Lillie's + Dawn en mano ya no hay una sola copia de refresco: el
    scorer suelta el Dawn (55) antes que la Lillie's, asi que cuenta."""
    ctx = _Ctx({m.Lillie_Determination: 1, m.Dawn: 1,
                m.Boss_Orders: 1, m.Ultra_Ball: 1})
    assert m._ub_forraje_real(ctx, m.Lillie_Determination) == 2
