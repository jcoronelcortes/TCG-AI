"""The Ultra Ball is not paid for with the Xerosic (a COST veto vs Alakazam).

Origin (user, registro_006 step 56 vs Alakazam, LOST -- log 88501752). Hand
{Dawn, Xerosic's Machinations, Ultra Ball}, the Supporter unplayed, the rival with 11
cards in hand (their Alakazam ex projected 20 x (11+2) = 260 of Powerful Hand and
had just knocked out our Meowth ex). The agent played the Ultra Ball -- 11900,
the item band, well above the Xerosic at 6200 -- and paid the cost of discarding
2 with the ONLY two cards it had left: the Xerosic AND the Dawn. It brought a
Meganium to evolve a bench Bayleef and ended the turn with the hand at
0, the Supporter unplayed and the rival hand intact.

A double loss, and both avoidable:

  * the Xerosic was THE play of the turn (the rival 11 -> 3 cards: Powerful Hand from
    260 to 100);
  * the Meganium the Ultra Ball brought would have been brought FOR FREE by the Dawn itself
    (it searches the deck for a Basic + Stage 1 + Stage 2, discarding nothing) the next
    turn -- which is why the play would only be right with the DECK having nothing to
    search for.

The correction is a fifth cost veto, `_ub_cancel_xerosic`, sibling of the ones
that already protect Unfair Stamp / Fezandipiti ex / Lillie's / Meowth ex: if the
hand's real fodder (`_ub_forraje_real`) does not reach 2 cards without touching the
Xerosic, the Ultra Ball COSTS more than it brings and is vetoed. With 2+ filler cards
it does not fire: the Ultra Ball is an Item and coexists with the turn's Supporter.
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
# The log's failure, reproduced as it stands
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
# The predicate, in isolation
# ---------------------------------------------------------------------------

class _Ctx:
    """The minimum `_ub_cancel_xerosic` / `_ub_forraje_real` consult."""

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
    """{Dawn, Xerosic, Ultra Ball}: there is NO fodder (0 < 2).

    The Dawn does not count either: with the turn's Supporter free and a single refresh
    copy in hand, the SelectContext.DISCARD block scores it 3, BELOW
    the Xerosic vs Alakazam (5) -- it keeps it and lets the Xerosic go in its
    place. Before it counted as fodder (1); the veto fired anyway because
    1 < 2, but that same overcount DID let the Ultra Ball through when the
    hand held a Boss's on top of the refresh Supporter (registro_004 steps
    43-64 vs Alakazam)."""
    ctx = _Ctx({m.Dawn: 1, m.Xerosic_Machinations: 1, m.Ultra_Ball: 1})
    assert m._ub_forraje_real(ctx, m.Xerosic_Machinations) == 0
    assert m._ub_cancel_xerosic(ctx)
    assert m._ub_coste_destruye_carta_mejor(ctx)


def test_no_veta_si_hay_forraje_de_sobra():
    """With 2 filler energies the Ultra Ball is paid for without touching the Xerosic:
    an Item and a Supporter coexist in the same turn."""
    ctx = _Ctx({m.Xerosic_Machinations: 1, m.Ultra_Ball: 1,
                m.Basic_Grass_Energy: 2})
    assert m._ub_forraje_real(ctx, m.Xerosic_Machinations) == 2
    assert not m._ub_cancel_xerosic(ctx)


def test_no_veta_si_el_supporter_del_turno_ya_se_jugo():
    ctx = _Ctx({m.Dawn: 1, m.Xerosic_Machinations: 1, m.Ultra_Ball: 1},
               supporter_played=True)
    assert not m._ub_cancel_xerosic(ctx)


def test_no_veta_si_la_mano_rival_ya_esta_capada():
    """With the rival at 3 cards Xerosic takes nothing away: there is nothing to protect
    (the same gate as the Supporter's scorer)."""
    ctx = _Ctx({m.Dawn: 1, m.Xerosic_Machinations: 1, m.Ultra_Ball: 1},
               op_hand=3)
    assert not m._ub_cancel_xerosic(ctx)


def test_no_veta_fuera_del_matchup_alakazam():
    """With no Alakazam across the table and a normal rival hand (< 7) the Xerosic does not
    score above the last resort: the Ultra Ball rules."""
    ctx = _Ctx({m.Dawn: 1, m.Xerosic_Machinations: 1, m.Ultra_Ball: 1},
               op_hand=5, alakazam=False)
    assert not m._ub_cancel_xerosic(ctx)


def test_sin_xerosic_en_mano_no_hay_veto():
    ctx = _Ctx({m.Dawn: 1, m.Lillie_Determination: 1, m.Ultra_Ball: 1})
    assert not m._ub_cancel_xerosic(ctx)


# ---------------------------------------------------------------------------
# Extracting `_ub_forraje_real` does not change the Lillie's veto
# ---------------------------------------------------------------------------

def test_forraje_real_respeta_las_piezas_de_evolucion():
    """A Meganium with its Bayleef in play is NOT fodder: the DISCARD scorer
    keeps it and lets the Supporter go in its place."""
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
