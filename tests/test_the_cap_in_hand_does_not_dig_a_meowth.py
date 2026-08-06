"""The Supporter of the turn is already in hand: the Ultra Ball does not dig a
searcher for another one.

Scenario (`records/registro_004_pasos_032_hasta_051.json`, episode 90106609,
step 36, turn 4 vs Alakazam, LOST):

    US                                        RIVAL
    active  Ogerpon ex 200/210, 3 Grass       active  Dunsparce 70/70, 0 energy
            -> Myriad Leaf Shower is offered  bench   Kadabra, Kadabra,
    bench   Ogerpon ex (2 Grass: ONE short),          Abra, Abra (1 energy)
            Fezandipiti ex
    hand    Ultra Ball, Tapu Bulu,            hand    **10 cards**
            **XEROSIC'S MACHINATIONS**,               -> Powerful Hand projects
            Hydrapple ex, Night Stretcher                20 x 10 = 200+

The turn's Supporter was free and the answer to the matchup was in hand: play
Xerosic (they discard down to 3), cap Powerful Hand and attack. What the agent
did instead was the refill engine:

    Ultra Ball -> discard Tapu Bulu + Night Stretcher -> fetch Meowth ex ->
    play it (a 2-prize body on the bench) -> Last-Ditch fetches Lillie's ->
    `_ld_supp_comprometido` prices the fetched Lillie's at 8000 -> it takes the
    turn's Supporter over the Xerosic (6200) AND SHUFFLES THE XEROSIC BACK INTO
    THE DECK.

Balance of the turn: a 1-prize attacker (Tapu Bulu) and the Night Stretcher that
was one energy away from arming the second Ogerpon discarded, the Ultra Ball
spent, a 2-prize Meowth ex given to the bench, the cap gone -- and the opposing
hand still at ten.

The engine is right when we have ONE attacker and nothing on the bench: there
the refill is the turn. It is wrong here, and the reason it fired is that the
question "is what I already hold better than what the deck can bring?" was asked
with the wrong instrument. `_eval_ub_best_target` compares
`_best_supp_in_deck_val` against `_best_supp_in_hand_val`, and that census only
walks Boss's/Dawn/Lillie's/Lana's: a hand holding a Xerosic reads as ZERO, so the
deck always won. `_RULES_UB_MEOWTH` asked it by name
(`lillie_already_in_hand_redundant`) and Xerosic is not Lillie's.

Fix: `_supp_in_hand_takes_the_turn` (main.py) -- the same question
`_meowth_fetch_loses_the_turn` already asks about a Meowth ex ALREADY IN HAND,
moved one step earlier for the one still in the deck, and measured with the
scorers that really resolve the slot (`_supp_play_score`). It gates the Meowth
branch of the Ultra Ball's value AND its fetch ladder.
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
            / "alakazam_t4_the_cap_in_hand_does_not_dig_a_meowth_step36.json")

XEROSIC = m.Xerosic_Machinations
MEOWTH = m.Meowth_ex
CHIKORITA = m.Chikorita
ULTRA_BALL = m.Ultra_Ball
TAPU = m.Tapu_Bulu
NIGHT_STRETCHER = m.Night_Stretcher
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


def _played_id(obs, choice):
    """Id of the card the main menu plays, or None if it is not a PLAY."""
    opt = obs["select"]["option"][choice[0]]
    if opt.get("type") != int(m.OptionType.PLAY):
        return None
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    return mine["hand"][opt["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The board that produced the mistake, read off the record
# ---------------------------------------------------------------------------

def test_the_board_of_step_36_is_the_one_from_the_record():
    obs = _frames()[36]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    op = cur["players"][1 - cur["yourIndex"]]

    assert [c["id"] for c in mine["hand"]] == [
        ULTRA_BALL, TAPU, XEROSIC, HYDRAPPLE, NIGHT_STRETCHER]
    # the turn's Supporter is free and their hand is in Powerful Hand range
    assert cur["supporterPlayed"] is False
    assert op["handCount"] == 10
    # an attacker that is ready NOW and a second one one energy short
    assert len(mine["active"][0]["energies"]) == 3
    assert any(len(b["energies"]) == 2 and b["id"] == m.Teal_Mask_Ogerpon_ex
               for b in mine["bench"])
    # ...and attacking is on the menu
    assert any(o.get("type") == int(m.OptionType.ATTACK)
               for o in obs["select"]["option"])


# ---------------------------------------------------------------------------
# 2. The fix: the Ultra Ball no longer digs the Meowth ex
# ---------------------------------------------------------------------------

def test_the_ultra_ball_does_not_fetch_the_meowth_with_the_cap_in_hand():
    obs = _frames()[38]
    choice = m.agent(obs)
    assert _fetched_id(obs, choice) != MEOWTH, (
        "con el Xerosic en mano (6200, la jugada del turno) el Meowth ex solo "
        "traeria un Supporter que no se puede jugar hoy y que ademas le "
        "robaria el hueco al Xerosic; no debe cavarse")


def test_it_fetches_a_one_prize_body_instead():
    """What the search takes now: the Chikorita that starts the Meganium line,
    a 1-prize body -- the kind we want in front of an Alakazam."""
    obs = _frames()[38]
    assert _fetched_id(obs, m.agent(obs)) == CHIKORITA


def test_without_the_cap_in_hand_the_meowth_engine_comes_back():
    """Counterfactual, the same prompt: with NO Supporter in hand the refill
    engine is right and the Ultra Ball digs the Meowth ex as it always did."""
    obs = _frames()[38]
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    mine["hand"] = [c for c in mine["hand"] if c["id"] != XEROSIC]
    mine["handCount"] = len(mine["hand"])
    assert _fetched_id(obs, m.agent(obs)) == MEOWTH


# ---------------------------------------------------------------------------
# 3. The other half: the Supporter of the turn IS the Xerosic
# ---------------------------------------------------------------------------

def test_the_turn_supporter_is_the_cap_not_the_meowth_body():
    """Step 39 of the record, the menu the old line reached with the Meowth ex
    already in hand: the play is the Xerosic, not putting the body down."""
    obs = _frames()[39]
    choice = m.agent(obs)
    assert _played_id(obs, choice) == XEROSIC, (
        "el hueco de Supporter del turno es del Xerosic: bajar el Meowth ex "
        "regala 2 premios por una carta que no se puede jugar")


# ---------------------------------------------------------------------------
# 4. The predicate, on its own
# ---------------------------------------------------------------------------

def test_the_predicate_answers_on_the_play_scale():
    """`_supp_in_hand_takes_the_turn` is True on this board and reads the two
    scorers that really decide: the Xerosic in hand beats what the deck holds."""
    obs = _frames()[36]
    seen = []
    real = m._supp_in_hand_takes_the_turn

    def spy(ctx):
        value = real(ctx)
        seen.append((value, m._best_supporter_in_hand(ctx)))
        return value

    m._supp_in_hand_takes_the_turn = spy
    try:
        m.agent(obs)
    finally:
        m._supp_in_hand_takes_the_turn = real

    assert seen, "the Ultra Ball's valuation did not consult the predicate"
    value, (best_id, best_val) = seen[0]
    assert value is True
    assert best_id == XEROSIC
    assert best_val > m.SUPP_SCORE_LAST_RESORT_BAND
