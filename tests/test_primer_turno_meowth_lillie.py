"""The FIRST TURN rule: Meowth ex exists ONLY to bring a Lillie's.

Origin (user, log 88461779 steps 6-22 vs Alakazam, LOST): on OUR first
turn the agent played Ultra Ball -> Meowth ex (correct: there was no Lillie's
Determination in hand) but the Last-Ditch Catch took a Xerosic's
Machinations instead of the Lillie's -- with four live copies in the deck. Turn
1 does not attack, does not evolve and (going first) does not even offer to play
Supporters: the only thing it decides is how much HAND we will have on turn 2. Xerosic
stayed dead in hand, and on top of that we would have had to shuffle it away with the
next turn's Lillie's itself. Ultra Ball + a 2-prize body on the
bench + the whole turn were paid for nothing.

The complete rule (deck-agnostic), as the user stated it:

  * a first turn WITH a Lillie's in hand -> NOTHING is done to play or to
    search for a Meowth ex (neither from hand nor with an Ultra Ball);
  * a first turn WITHOUT a Lillie's in hand -> a Meowth ex may be played from
    hand or dug with an Ultra Ball...
  * ...but the Last-Ditch fetch ALWAYS brings Lillie's Determination.

The only exception kept: the anti-DONK guard (an empty bench + a projected rival
KO on our lone active), where Meowth ex is played not for its
search but as a body that avoids losing the game on the spot
(`_meowth_antidonk_now`, see the tests of the Cinderace fixture in test_main.py).
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
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
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
    m._init_cards_tracking()


def _fixture_obs(name):
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)["observation"]


# ---------------------------------------------------------------------------
# The log's failure: the first turn's fetch
# ---------------------------------------------------------------------------

def test_last_ditch_del_primer_turno_trae_lillie_no_xerosic():
    """Step 16 of log 88461779, reproduced as it stands."""
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
    """The helper that decides BEFORE spending the Meowth sees the same as the prompt
    (menu <-> prompt coherence): with a live Lillie's in the deck, the predicted
    target of the first turn is Lillie's even if the matchup is Alakazam with a
    fat rival hand and a strong attacker in play (the branch that took the
    Xerosic in the log)."""
    mazo = {m.Xerosic_Machinations: {m.ZONE_DECK: 2},
            m.Lillie_Determination: {m.ZONE_DECK: 4}}
    supp = {m.Xerosic_Machinations: 600, m.Lillie_Determination: 500}
    objetivo, _ = m._meowth_fetch_prediccion(
        {}, supp, 5, True, 8, False, False, False, False, False, True,
        mazo, first_turn=True)
    assert objetivo == m.Lillie_Determination


def test_fuera_del_primer_turno_el_fetch_conserva_la_rama_xerosic():
    """The rule belongs ONLY to the first turn: in later turns the
    anti-Alakazam engine (capping Powerful Hand) still rules."""
    mazo = {m.Xerosic_Machinations: {m.ZONE_DECK: 2},
            m.Lillie_Determination: {m.ZONE_DECK: 4}}
    supp = {m.Xerosic_Machinations: 600, m.Lillie_Determination: 500}
    objetivo, _ = m._meowth_fetch_prediccion(
        {}, supp, 5, True, 8, False, False, False, False, False, True,
        mazo, first_turn=False)
    assert objetivo == m.Xerosic_Machinations


def test_sin_lillie_en_el_mazo_el_primer_turno_no_degrada_al_resto():
    """Deck-agnostic: if the deck has no reachable Lillie's, the
    rule caps nobody and the normal ladder decides."""
    mazo = {m.Xerosic_Machinations: {m.ZONE_DECK: 2}}
    supp = {m.Xerosic_Machinations: 600}
    objetivo, value = m._meowth_fetch_prediccion(
        {}, supp, 5, True, 8, False, False, False, False, False, True,
        mazo, first_turn=True)
    assert objetivo == m.Xerosic_Machinations and value > 40


# ---------------------------------------------------------------------------
# Not digging Meowth ex with an Ultra Ball if the Lillie's is already in hand
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
    value, _ = m._resolve_rules(m._REGLAS_UB_MEOWTH, [], ctx, 50)
    return value


def test_ub_no_cava_meowth_en_primer_turno_con_lillie_en_mano():
    m.we_go_first = True
    m._ub_engine_pivot_turn = True   # not even the pivot engine lifts the rule
    ctx = _ctx_ub_meowth({m.Lillie_Determination: 1, m.Ultra_Ball: 1})
    assert _valor_ub_meowth(ctx) <= 10


def test_ub_no_cava_meowth_en_primer_turno_sin_lillie_en_el_mazo():
    m.we_go_first = True
    ctx = _ctx_ub_meowth({m.Ultra_Ball: 1}, lillie_in_mazo=0)
    assert _valor_ub_meowth(ctx) <= 10


def test_ub_si_cava_meowth_en_primer_turno_sin_lillie_en_mano():
    """The log's legitimate case: with no Lillie's in hand and copies in the deck,
    the Ultra Ball -> Meowth ex -> Lillie's chain IS set up."""
    m.we_go_first = True
    m._ub_engine_pivot_turn = True
    ctx = _ctx_ub_meowth({m.Ultra_Ball: 1})
    assert _valor_ub_meowth(ctx) >= 1000


# ---------------------------------------------------------------------------
# The disruption engine does not hijack the first turn
# ---------------------------------------------------------------------------

class _CtxXerosic:
    """The minimum `_alakazam_dig_xerosic_engine` consults."""

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
        self.cards_in_deck = {m.Xerosic_Machinations: {m.ZONE_DECK: 2},
                               m.Meowth_ex: {m.ZONE_DECK: 1}}
        self.field_counts = {}
        self.bench_count = 1


@pytest.mark.parametrize("turno,primeros", [(1, True), (2, False)])
def test_motor_xerosic_no_arranca_en_nuestro_primer_turno(turno, primeros):
    assert not m._alakazam_dig_xerosic_engine(_CtxXerosic(turno, primeros))


def test_motor_xerosic_sigue_activo_en_turnos_posteriores():
    assert m._alakazam_dig_xerosic_engine(_CtxXerosic(4, True))
