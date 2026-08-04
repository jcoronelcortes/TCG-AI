"""The real fodder does NOT count the protected REFRESH Supporter.

Origin (user, registro_004 steps 43-64 vs Alakazam, LOST -- log 88910273).
Turn 4, hand {Boss's x2, Ultra Ball x2, Tapu Bulu, Lillie's Determination},
the Supporter unplayed, the rival with 8 cards (Powerful Hand projected at 20 x 10 =
200). `_alakazam_dig_xerosic_engine` set up the disruption chain -- Ultra Ball
(5950) -> Meowth ex -> Last-Ditch Catch -> Xerosic -- ABOVE the Lillie's
(5000), which is exactly what that engine exists to avoid playing. The chain
worked: the Xerosic ended up in hand.

And then the agent threw it in the bin. With the hand at {Boss's, Lillie's,
Ultra Ball, Xerosic}:

  * `_ub_forraje_real(prot=Xerosic)` counted **2** -- the Boss's and the Lillie's --
    so `_ub_cancel_xerosic` did NOT fire;
  * the SECOND Ultra Ball scored 11400 (a target worth 800, the item band) and
    beat the Xerosic (7200);
  * its cost of 2 discards was paid with the Boss's and with THE XEROSIC ITSELF,
    because the SelectContext.DISCARD block scores the Lillie's at 2 and the Xerosic
    at 5: the Lillie's NEVER falls first;
  * the Ultra Ball dug up a SECOND Meowth ex, useless -- its Last-Ditch was
    already spent by the first one;
  * and the turn closed by playing the Lillie's, which shuffled that Meowth back into the
    deck.

Balance: Tapu Bulu, two Boss's Orders, the Xerosic and both Ultra Balls lost
to end up playing EXACTLY the Supporter the whole chain existed to avoid
playing, with the rival hand intact.

The cause is a single one: `_ub_forraje_real` overcounted. It already excluded from the fodder
what the DISCARD scorer protects MORE than the protected card (evolution
pieces, Fezandipiti ex after a KO, a Meowth ex still playable -- see the adjustment
of log 86401283), but not the **refresh Supporters**: with the turn's Supporter
free and a single copy in hand, `_protect_refresh_supporter` scores the
Lillie's at 2 and the Dawn at 3, below any card these vetoes
protect. Counting them as fodder was promising a payment the discard scorer
was not going to make.
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
    """The id of the hand card behind option `idx` (we are yourIndex 1)."""
    cur = obs["current"]
    opt = cur and obs["select"]["option"][idx]
    if opt.get("type") != 7 or "index" not in opt:
        return None
    yo = cur["players"][cur["yourIndex"]]
    return yo["hand"][opt["index"]]["id"]


# ---------------------------------------------------------------------------
# The log's failure, reproduced as it stands
# ---------------------------------------------------------------------------

def test_paso_50_juega_el_xerosic_y_no_la_segunda_ultra_ball():
    obs = _fixture_obs()
    cur = obs["current"]
    yo = cur["players"][cur["yourIndex"]]

    # The chain is already complete: Meowth ex on the bench and Xerosic in hand.
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
# The predicate, in isolation
# ---------------------------------------------------------------------------

class _Ctx:
    """The minimum `_ub_forraje_real` consults."""

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
        self.cards_in_deck = {}


def test_la_lillie_protegida_no_es_forraje():
    """The exact hand of step 50: the only real fodder is the Boss's."""
    ctx = _Ctx({m.Boss_Orders: 1, m.Lillie_Determination: 1,
                m.Ultra_Ball: 1, m.Xerosic_Machinations: 1})
    assert m._ub_forraje_real(ctx, m.Xerosic_Machinations) == 1


def test_el_dawn_protegido_tampoco_es_forraje():
    """Dawn scores 3 with `_protect_refresh_supporter`: it does not fall first either."""
    ctx = _Ctx({m.Boss_Orders: 1, m.Dawn: 1,
                m.Ultra_Ball: 1, m.Xerosic_Machinations: 1})
    assert m._ub_forraje_real(ctx, m.Xerosic_Machinations) == 1


def test_con_el_supporter_del_turno_ya_jugado_si_es_forraje():
    """Once the Supporter is played, the Lillie's loses its refresh protection and
    goes back to being discardable: the veto must not freeze forever."""
    ctx = _Ctx({m.Boss_Orders: 1, m.Lillie_Determination: 1,
                m.Ultra_Ball: 1, m.Xerosic_Machinations: 1},
               supporter_played=True)
    assert m._ub_forraje_real(ctx, m.Xerosic_Machinations) == 2


def test_la_copia_sobrante_de_lillie_si_es_forraje():
    """`_protect_refresh_supporter` only covers ONE copy (the rest score 72
    in the discard block): with two Lillie's the fodder counts them again."""
    ctx = _Ctx({m.Lillie_Determination: 2, m.Ultra_Ball: 1,
                m.Xerosic_Machinations: 1})
    assert m._ub_forraje_real(ctx, m.Xerosic_Machinations) == 2


def test_protegiendo_la_propia_lillie_el_dawn_sigue_siendo_forraje():
    """With Lillie's + Dawn in hand there is no longer a single refresh copy: the
    scorer lets the Dawn go (55) before the Lillie's, so it counts."""
    ctx = _Ctx({m.Lillie_Determination: 1, m.Dawn: 1,
                m.Boss_Orders: 1, m.Ultra_Ball: 1})
    assert m._ub_forraje_real(ctx, m.Lillie_Determination) == 2
