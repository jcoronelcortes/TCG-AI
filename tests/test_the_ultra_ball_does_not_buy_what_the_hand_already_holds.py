"""The Ultra Ball does not pay two cards for something the hand already holds.

Scenario (`records/registro_010_pasos_109_hasta_131.json`, episode 90878403,
step 112, turn 10 vs Mega Lucario ex -- WON in spite of this):

    US                                         RIVAL
    active  Hydrapple ex 300/300, 2 Grass      active  Mega Lucario ex 340/340
    bench   Meganium 130/130, 2 Grass          bench   Solrock, Meganium(?), ...
    hand    Ultra Ball, **Meowth ex**,         (the turn's Supporter still free)
            Night Stretcher x2, Meganium,
            Chikorita, Hydrapple ex, **Grass**

The agent played the Ultra Ball, discarded the **Meganium and the Chikorita of
our own evolution line**, and fetched a **SECOND Meowth ex** -- with one already
sitting in the hand, one card away from being played for free. The Grass in hand
had a use of its own: a Teal Mask Ogerpon ex (Teal Dance) turns it into damage.

Why it fired. The value branch (`_eval_ub_best_target`) and the fetch ladder
(`_RULES_UB_MEOWTH`) both ask the SAME two questions about the refill engine --
"is there a Meowth ex in PLAY?" and "is a Supporter alive in the DECK?" -- and
neither of them asks whether the card is already IN HAND. So the Meowth branch
scored at the height of the engine (~1000, over the Ogerpon at 750) and the
prompt, asked the same way, took the duplicate.

The evolution branches had already written the answer one line at a time ("if
the Bayleef / Meganium / Dipplin / Hydrapple ex is ALREADY in hand, the line
evolves without an Ultra Ball"). The fix lifts it to a rule with no card in it:

  * `_ub_target_covered_by_hand` -- do the copies in hand already cover
    everything the board can do with that card this turn? `_evo_copies_usable`
    answers it for the evolutions (what bounds a Stage is the number of BODIES
    underneath it), and outside our lines the answer is ONE.
  * `_eval_ub_best_target` routes EVERY target through it (`_offer`), so the
    Ultra Ball is never valued for a card the hand already has.
  * the `Ultra_Ball` fetch of `ptcg/turn/options/card.py` clamps the same
    targets to 10, so the two menus cannot disagree.

See [[ultraball-solo-si-el-objetivo-se-usa-este-turno]] and
[[coherencia-menu-prompt-habilidades-disponibles]].
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
import ptcg.decision.ultra_ball as ub_mod

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "lucario_the_ultra_ball_does_not_buy_what_the_hand_holds_step112.json")

ULTRA_BALL = m.Ultra_Ball
MEOWTH = m.Meowth_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
GRASS = m.Basic_Grass_Energy
MEGANIUM = m.Meganium
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
DIPPLIN = m.Dipplin
APPLIN = m.Applin
HYDRAPPLE = m.Hydrapple_ex


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
    yield
    m._init_cards_tracking()


def _frames():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return {item["step"]: copy.deepcopy(item["observation"])
            for item in data["sequence"]}


def _fetched_id(obs, choice):
    """Id of the card the deck-search prompt takes."""
    opt = obs["select"]["option"][choice[0]]
    return obs["select"]["deck"][opt["index"]]["id"]


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


# ---------------------------------------------------------------------------
# 1. The board that produced the mistake, read off the record
# ---------------------------------------------------------------------------

def test_the_board_of_step_112_is_the_one_from_the_record():
    obs = _frames()[112]
    mine = _mine(obs)
    hand = [c["id"] for c in mine["hand"]]

    # the Ultra Ball and the very card it went on to search for, side by side
    assert ULTRA_BALL in hand
    assert hand.count(MEOWTH) == 1
    # ...and there is no Meowth ex in play, which is all the old branch asked
    assert all(p["id"] != MEOWTH
               for p in mine["active"] + mine["bench"])
    # the loose Grass that a Teal Mask Ogerpon ex turns into damage
    assert GRASS in hand
    assert obs["current"]["supporterPlayed"] is False


def test_the_deck_still_holds_both_candidates():
    """Both targets are reachable: the choice is real, not forced."""
    obs = _frames()[114]
    deck_ids = [c["id"] for c in obs["select"]["deck"]]
    assert MEOWTH in deck_ids
    assert OGERPON in deck_ids


# ---------------------------------------------------------------------------
# 2. The fix: the search no longer buys the duplicate
# ---------------------------------------------------------------------------

def test_the_ultra_ball_does_not_fetch_a_meowth_already_in_hand():
    obs = _frames()[114]
    assert _fetched_id(obs, m.agent(obs)) != MEOWTH, (
        "con un Meowth ex YA en la mano, cavar el segundo paga dos descartes "
        "por un tablero que ya teniamos: solo hay un Last-Ditch Catch por turno")


def test_it_fetches_the_ogerpon_that_uses_the_energy_in_hand():
    """What the search takes now: the Teal Mask Ogerpon ex whose Teal Dance
    converts the loose Grass in hand into attack power."""
    obs = _frames()[114]
    assert _fetched_id(obs, m.agent(obs)) == OGERPON


def test_without_the_meowth_in_hand_the_refill_engine_comes_back():
    """Counterfactual, the same prompt: with NO Meowth ex in hand the engine is
    right and the Ultra Ball digs it exactly as it always did."""
    obs = _frames()[114]
    mine = _mine(obs)
    mine["hand"] = [c for c in mine["hand"] if c["id"] != MEOWTH]
    mine["handCount"] = len(mine["hand"])
    assert _fetched_id(obs, m.agent(obs)) == MEOWTH


# ---------------------------------------------------------------------------
# 3. The rule on its own: deck-agnostic, and it counts SEATS not copies
# ---------------------------------------------------------------------------

def _covered(cid, hand, field, free_bench=4):
    return m._ub_target_covered_by_hand(cid, hand, field, free_bench)


def test_a_card_that_is_not_in_hand_is_never_covered():
    assert _covered(MEOWTH, {}, {}) is False
    assert _covered(OGERPON, {GRASS: 3}, {OGERPON: 1}) is False


def test_one_copy_in_hand_covers_any_body():
    """A Basic is put down by taking it out of the hand: no board uses two
    copies of the same body for the same job in the same turn."""
    for cid in (MEOWTH, OGERPON, CHIKORITA, APPLIN, m.Tapu_Bulu,
                m.Pinsir, m.Fezandipiti_ex):
        assert _covered(cid, {cid: 1}, {}) is True


def test_an_evolution_is_covered_only_while_the_board_has_no_spare_seat():
    """`_evo_copies_usable` is the arithmetic: what bounds a Stage is the number
    of BODIES underneath it. One Applin on the bench wears ONE Dipplin, so the
    copy in hand covers the turn; with TWO Applins the second copy still has a
    seat and the search is worth paying for."""
    assert _covered(DIPPLIN, {DIPPLIN: 1}, {APPLIN: 1}) is True
    assert _covered(DIPPLIN, {DIPPLIN: 1}, {APPLIN: 2}) is False
    assert _covered(DIPPLIN, {DIPPLIN: 2}, {APPLIN: 2}) is True

    assert _covered(BAYLEEF, {BAYLEEF: 1}, {CHIKORITA: 1}) is True
    assert _covered(BAYLEEF, {BAYLEEF: 1}, {CHIKORITA: 2}) is False


def test_an_orphan_evolution_in_hand_is_covered_with_no_seat_at_all():
    """With nothing underneath it the piece is dead either way: a second copy
    cannot be worth two discards."""
    assert _covered(HYDRAPPLE, {HYDRAPPLE: 1}, {}, free_bench=0) is True


def test_the_line_basic_in_hand_counts_as_a_seat_when_the_bench_has_room():
    """An Applin in hand plus a free slot is a future body: the Dipplin in hand
    is not covering that seat as well, so the search still has something to
    bring (the same criterion as `_line_base_benchable`)."""
    assert _covered(DIPPLIN, {DIPPLIN: 1, APPLIN: 1}, {APPLIN: 1},
                    free_bench=1) is False
    assert _covered(DIPPLIN, {DIPPLIN: 1, APPLIN: 1}, {APPLIN: 1},
                    free_bench=0) is True


# ---------------------------------------------------------------------------
# 4. The value branch stops buying the Ultra Ball for a covered target
# ---------------------------------------------------------------------------

def test_the_valuation_drops_the_meowth_and_keeps_the_rest():
    """`_eval_ub_best_target` on the same board: every target goes through the
    gate, the Meowth ex is the only one it stops, and the branches that price
    the Ultra Ball for a card we do NOT hold (the Ogerpon that spends the Grass,
    the Fezandipiti ex after last turn's KO) are left alone."""
    obs = _frames()[112]
    seen = []
    real = ub_mod._ub_target_covered_by_hand

    def spy(cid, hand_counts, field_counts, free_bench=0):
        value = real(cid, hand_counts, field_counts, free_bench)
        seen.append((cid, value))
        return value

    ub_mod._ub_target_covered_by_hand = spy
    try:
        m.agent(obs)
    finally:
        ub_mod._ub_target_covered_by_hand = real

    assert seen, "the Ultra Ball's valuation never consulted the gate"
    covered = {cid for cid, value in seen if value}
    offered = {cid for cid, value in seen if not value}
    assert covered == {MEOWTH}, (
        "el unico objetivo que la mano ya cubre es el Meowth ex")
    assert OGERPON in offered
