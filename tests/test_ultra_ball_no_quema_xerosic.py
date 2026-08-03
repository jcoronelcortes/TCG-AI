"""La Ultra Ball no se paga con el Xerosic (veto por COSTE vs Alakazam).

Origen (user, registro_006 paso 56 vs Alakazam, PERDIDA -- log 88501752). Mano
{Dawn, Xerosic's Machinations, Ultra Ball}, Supporter sin jugar, rival con 11
cartas en mano (su Alakazam ex proyectaba 20 x (11+2) = 260 de Powerful Hand y
acababa de noquear a nuestro Meowth ex). El agente jugo la Ultra Ball -- 11900,
banda de item, muy por encima del Xerosic a 6200 -- y pago el coste de descartar
2 con las DOS unicas cartas que le quedaban: el Xerosic Y el Dawn. Trajo un
Meganium para evolucionar un Bayleef de banca y termino el turno con la mano a
0, el Supporter sin jugar y la mano rival intacta.

Doble perdida, y las dos evitables:

  * el Xerosic era LA jugada del turno (rival 11 -> 3 cartas: Powerful Hand de
    260 a 100);
  * el Meganium que trajo la Ultra Ball lo habria traido GRATIS el propio Dawn
    (busca Basico + Fase 1 + Fase 2 del mazo, sin descartar nada) al turno
    siguiente -- por eso la jugada solo seria correcta con el MAZO sin nada que
    buscar.

La correccion es un quinto veto por coste, `_ub_cancel_xerosic`, hermano de los
que ya protegen Unfair Stamp / Fezandipiti ex / Lillie's / Meowth ex: si el
forraje real de la mano (`_ub_forraje_real`) no llega a 2 cartas sin tocar el
Xerosic, la Ultra Ball CUESTA mas de lo que trae y se veta. Con 2+ cartas de
relleno no salta: la Ultra Ball es un Item y convive con el Supporter del turno.
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
FIXTURE = "alakazam_step56_xerosic_no_ultra_ball.json"


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
    opt = obs["select"]["option"][idx]
    if opt.get("type") != 7 or "index" not in opt:
        return None
    return obs["current"]["players"][0]["hand"][opt["index"]]["id"]


# ---------------------------------------------------------------------------
# El fallo del log, reproducido tal cual
# ---------------------------------------------------------------------------

def test_paso_56_juega_xerosic_y_no_la_ultra_ball():
    obs = _fixture_obs()
    mano = [c["id"] for c in obs["current"]["players"][0]["hand"]]
    assert sorted(mano) == sorted([m.Dawn, m.Xerosic_Machinations, m.Ultra_Ball])
    assert obs["current"]["supporterPlayed"] is False
    assert obs["current"]["players"][1]["handCount"] == 11

    elegido = _id_de_opcion(obs, m.agent(obs)[0])
    assert elegido == m.Xerosic_Machinations, (
        "con la mano rival a 11 cartas el turno es de Xerosic; la Ultra Ball "
        "solo se puede pagar quemando el propio Xerosic y el Dawn")


# ---------------------------------------------------------------------------
# El predicado, aislado
# ---------------------------------------------------------------------------

class _Ctx:
    """Minimo que consultan `_ub_cancel_xerosic` / `_ub_forraje_real`."""

    class _State:
        def __init__(self, supporter_played):
            self.supporterPlayed = supporter_played
            self.turn = 6

    class _Poke:
        def __init__(self, cid, hp):
            self.id, self.hp = cid, hp
            self.energies = []

    def __init__(self, hand, op_hand=11, supporter_played=False,
                 alakazam=True, campo=None, mazo=None):
        self.hand_counts = dict(hand)
        self.field_counts = dict(campo or {})
        self.bench_count = 3
        self.state = self._State(supporter_played)
        self.op_hand_count = op_hand
        self.op_is_alakazam_deck = alakazam
        self.ko_last_turn = False
        self.op_is_crustle_deck = False
        self.op_has_ex_immune_active = False
        self.op_has_ex_immune_bench = False
        self.has_hydrapple = False
        self.forest_in_play = False
        self.meganium_in_play = False
        self.cartas_en_mazo = dict(mazo or {})
        self.win_via_boss_gust = False
        self.active_cant_attack = False
        self.supporter_boost = 0
        self.my_state = type("S", (), {"active": [self._Poke(m.Applin, 40)]})()
        self.op_state = type("S", (), {
            "active": [self._Poke(m.Alakazam_ex, 140)]})()


def test_veto_con_la_mano_del_log():
    """{Dawn, Xerosic, Ultra Ball}: NO hay forraje (0 < 2).

    El Dawn tampoco cuenta: con el Supporter del turno libre y una sola copia
    de refresco en mano, el bloque SelectContext.DISCARD lo puntua 3, POR
    DEBAJO del Xerosic vs Alakazam (5) -- lo conserva y suelta el Xerosic en su
    lugar. Antes se contaba como forraje (1); el veto saltaba igual porque
    1 < 2, pero la misma sobrecuenta SI dejaba pasar la Ultra Ball cuando en la
    mano habia un Boss's ademas del Supporter de refresco (registro_004 pasos
    43-64 vs Alakazam)."""
    ctx = _Ctx({m.Dawn: 1, m.Xerosic_Machinations: 1, m.Ultra_Ball: 1})
    assert m._ub_forraje_real(ctx, m.Xerosic_Machinations) == 0
    assert m._ub_cancel_xerosic(ctx)
    assert m._ub_coste_destruye_carta_mejor(ctx)


def test_no_veta_si_hay_forraje_de_sobra():
    """Con 2 energias de relleno la Ultra Ball se paga sin tocar el Xerosic:
    Item y Supporter conviven en el mismo turno."""
    ctx = _Ctx({m.Xerosic_Machinations: 1, m.Ultra_Ball: 1,
                m.Basic_Grass_Energy: 2})
    assert m._ub_forraje_real(ctx, m.Xerosic_Machinations) == 2
    assert not m._ub_cancel_xerosic(ctx)


def test_no_veta_si_el_supporter_del_turno_ya_se_jugo():
    ctx = _Ctx({m.Dawn: 1, m.Xerosic_Machinations: 1, m.Ultra_Ball: 1},
               supporter_played=True)
    assert not m._ub_cancel_xerosic(ctx)


def test_no_veta_si_la_mano_rival_ya_esta_capada():
    """Con el rival a 3 cartas Xerosic no quita nada: no hay nada que proteger
    (mismo gate que el scorer del Supporter)."""
    ctx = _Ctx({m.Dawn: 1, m.Xerosic_Machinations: 1, m.Ultra_Ball: 1},
               op_hand=3)
    assert not m._ub_cancel_xerosic(ctx)


def test_no_veta_fuera_del_matchup_alakazam():
    """Sin Alakazam enfrente y con la mano rival normal (< 7) el Xerosic no
    puntua por encima del ultimo recurso: la Ultra Ball manda."""
    ctx = _Ctx({m.Dawn: 1, m.Xerosic_Machinations: 1, m.Ultra_Ball: 1},
               op_hand=5, alakazam=False)
    assert not m._ub_cancel_xerosic(ctx)


def test_sin_xerosic_en_mano_no_hay_veto():
    ctx = _Ctx({m.Dawn: 1, m.Lillie_Determination: 1, m.Ultra_Ball: 1})
    assert not m._ub_cancel_xerosic(ctx)


# ---------------------------------------------------------------------------
# La extraccion de `_ub_forraje_real` no cambia el veto de Lillie's
# ---------------------------------------------------------------------------

def test_forraje_real_respeta_las_piezas_de_evolucion():
    """Un Meganium con su Bayleef en juego NO es forraje: el scorer de DISCARD
    lo conserva y suelta el Supporter en su lugar."""
    ctx = _Ctx({m.Meganium: 1, m.Basic_Grass_Energy: 1,
                m.Lillie_Determination: 1, m.Ultra_Ball: 1},
               campo={m.Bayleef: 1})
    assert m._ub_forraje_real(ctx, m.Lillie_Determination) == 1
    assert m._ub_cancel_lillie(ctx)


def test_forraje_real_no_cuenta_el_unfair_stamp():
    ctx = _Ctx({m.Unfair_Stamp: 1, m.Basic_Grass_Energy: 1,
                m.Lillie_Determination: 1, m.Ultra_Ball: 1})
    assert m._ub_forraje_real(ctx, m.Lillie_Determination) == 1
    assert m._ub_cancel_lillie(ctx)
