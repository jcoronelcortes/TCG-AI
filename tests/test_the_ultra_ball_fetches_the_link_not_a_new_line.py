"""With the bench full, the Ultra Ball fetches the LINK the board is missing,
not the Basic that would start a new one.

Scenario (`records/registro_004_pasos_055_hasta_078.json`, episode 90896936,
turn 4 vs Marnie -- WON in spite of this):

    US                                          RIVAL
    active Teal Mask Ogerpon ex 200/210, 1 G    active Marnie's Grimmsnarl ex 310/320
    bench  Meowth ex / Teal Mask Ogerpon ex x3   bench  Munkidori x2, Marnie's Impidimp x2,
           / **Chikorita** (played this turn)           Froslass
           -> **FULL**
    stadium **Forest of Vitality** (ours, played this same turn)
    hand   Ultra Ball x2, Dipplin x2, Hydrapple ex, Lillie's Determination

The Chikorita had just gone down and the Forest of Vitality lets a body that
came into play this turn evolve at once, so the ONE card the board could still
use was a **Bayleef** -- and both a Bayleef and an Applin were on the menu of
the deck search. The agent took the **Applin**, a Basic, with no seat for it;
the second Ultra Ball then discarded that very Applin to pay for itself and
fetched another one, and Lillie's Determination shuffled the survivor back into
the deck. Two Items, four cards (a spare Forest, a Tapu Bulu, a Dipplin and the
first Applin) for nothing, while the Chikorita stayed a Chikorita.

Why it fired -- and why the Alakazam record did not already cover it. The
number that beat the Bayleef comes from a DIFFERENT file and a different
ladder: `_v_ub_applin_arrancar` (`ptcg/decision/ultra_ball.py`) reads "Forest
available + Dipplin in hand + Hydrapple ex in hand" and answers **980**,
because in one turn that Applin would become Applin -> Dipplin -> Hydrapple ex.
The Bayleef, the missing intermediate link of a line already on the board, is
raised to **900** by `_evo_link_state`. 980 > 900, so the whole-line-in-a-turn
promise won -- and its premise, A FREE BENCH SEAT, was never checked. Every
Basic rung of the Ultra Ball prices the line the body would START; none of them
asked whether the body could be put down at all.

`_ub_target_has_no_seat` is what settles it, and it settles it for every target
of both menus: a card enters play by one of two doors and the card data says
which -- a Basic (`_evolution_stage == 0`) needs a free bench seat, an evolution
goes on top of a body already in play and a full bench does not shut that door.
The Applin drops to 10 and the Bayleef's 900 takes the search. Deck-agnostic: it
names no card, no line and no matchup, and it is asked of the CARD, so no
valuation and no engine flag can talk over it.

This test guards the `_v_ub_applin_arrancar` path specifically;
`tests/test_the_ultra_ball_does_not_buy_a_body_with_nowhere_to_sit.py` guards
the `_RULES_UB_MEOWTH` one. Same rule, two ladders that would each have to be
edited to break it.

See [[ub-el-cuerpo-sin-asiento-no-se-compra]],
[[ultra-ball-buscar-el-eslabon-que-falta]],
[[ultraball-solo-si-el-objetivo-se-usa-este-turno]] and
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

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_the_ultra_ball_fetches_the_link_not_a_new_line_step59.json")

ULTRA_BALL = m.Ultra_Ball
APPLIN = m.Applin
DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
MEGANIUM = m.Meganium
FOREST = m.Forest_of_Vitality
LILLIE = m.Lillie_Determination
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex

_FETCH_STEP = 59


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


def _replay_until(step):
    """The turn as it happened, action by action, up to `step`.

    A single frame will not do: the Forest of Vitality goes down at step 56 and
    the Chikorita at step 57 -- the stadium is what makes the Bayleef playable
    TODAY and the Chikorita is what makes it playable AT ALL, and both are state
    the agent builds as the turn runs.
    """
    frames = _frames()
    choice = None
    for st in sorted(frames):
        if st > step:
            break
        choice = m.agent(copy.deepcopy(frames[st]))
    return frames[step], choice


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _fetchable(obs):
    return [obs["select"]["deck"][o["index"]]["id"]
            for o in obs["select"]["option"]]


def _fetched_id(obs, choice):
    opt = obs["select"]["option"][choice[0]]
    return obs["select"]["deck"][opt["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The board that produced the mistake, read off the record
# ---------------------------------------------------------------------------

def test_the_bench_is_full_and_the_chikorita_is_the_body_that_needs_a_link():
    obs = _frames()[_FETCH_STEP]
    mine = _mine(obs)
    bench = [p["id"] for p in mine["bench"]]

    assert len(bench) == 5, "la banca esta LLENA: no cabe ningun Basico"
    assert CHIKORITA in bench, "el cuerpo al que le falta el eslabon"
    assert all(p["id"] != BAYLEEF for p in mine["active"] + mine["bench"])

    hand = [c["id"] for c in mine["hand"]]
    assert BAYLEEF not in hand, (
        "el Bayleef no esta en la mano: por eso hay algo que buscar")


def test_the_forest_is_in_play_so_the_chikorita_can_evolve_today():
    """Without the stadium the Bayleef would be development for tomorrow; with
    it the fetch completes the evolution in this same turn."""
    obs = _frames()[_FETCH_STEP]
    stadium = obs["current"]["stadium"]
    assert stadium and stadium[0]["id"] == FOREST


def test_the_hand_holds_the_promise_that_beat_the_bayleef():
    """`_v_ub_applin_arrancar` answers 980 for exactly this hand: Forest
    available + Dipplin + Hydrapple ex, i.e. "this Applin becomes a whole line
    in one turn". True with a seat, false without one."""
    obs = _frames()[_FETCH_STEP]
    hand = [c["id"] for c in _mine(obs)["hand"]]
    assert hand.count(DIPPLIN) >= 1 and HYDRAPPLE in hand


def test_the_choice_was_real_both_bodies_were_on_the_menu():
    obs = _frames()[_FETCH_STEP]
    fetchable = _fetchable(obs)
    assert APPLIN in fetchable, "lo que el registro se llevo"
    assert BAYLEEF in fetchable, "lo que el tablero necesitaba"


# ---------------------------------------------------------------------------
# 2. The fix: the search brings the missing link
# ---------------------------------------------------------------------------

def test_the_search_does_not_fetch_the_basic_with_the_bench_full():
    obs, choice = _replay_until(_FETCH_STEP)
    assert _fetched_id(obs, choice) != APPLIN, (
        "con la banca LLENA el Applin no puede bajar: el Ultra Ball estaria "
        "pagando dos cartas por un cuerpo sin asiento")


def test_the_search_fetches_the_bayleef_the_chikorita_is_waiting_for():
    obs, choice = _replay_until(_FETCH_STEP)
    assert _fetched_id(obs, choice) == BAYLEEF, (
        "el unico objetivo que el tablero puede usar hoy es el eslabon que le "
        "falta a la linea que YA esta en juego")


def test_whatever_it_fetches_is_a_card_that_can_enter_play_today():
    """The general form of the assertion above: with no seat left, only an
    evolution has a door open."""
    obs, choice = _replay_until(_FETCH_STEP)
    assert m._evolution_stage(_fetched_id(obs, choice)) >= 1


# ---------------------------------------------------------------------------
# 3. The rule on its own: it is the SEAT, not the card
# ---------------------------------------------------------------------------

def test_the_line_starting_promise_is_only_vetoed_by_the_missing_seat():
    """The Applin is not a bad target here because it is an Applin: with one
    free seat the very same board would be right to take it (Applin -> Dipplin
    -> Hydrapple ex in one turn). What kills it is that there is nowhere to put
    it."""
    assert m._ub_target_has_no_seat(APPLIN, 0) is True
    assert m._ub_target_has_no_seat(APPLIN, 1) is False
    # the link, on the other hand, never needs a seat
    assert m._ub_target_has_no_seat(BAYLEEF, 0) is False
    assert m._ub_target_has_no_seat(MEGANIUM, 0) is False


def test_the_valuation_of_the_link_outranks_a_seatless_basic_for_any_line():
    """Deck-agnostic check of the ordering the fix restores: an intermediate
    link whose pre-evolution is in play is `necesario`, the stage 2 above it is
    an orphan, and the Basic that would start the OTHER line has no seat."""
    field = {OGERPON: 4, MEOWTH: 1, CHIKORITA: 1}
    hand = {ULTRA_BALL: 1, DIPPLIN: 2, LILLIE: 1, HYDRAPPLE: 1}
    necesarios, huerfanos = m._evo_link_state(hand, field)

    assert BAYLEEF in necesarios, (
        "el Chikorita esta en juego y no hay Bayleef ni en mano ni en mesa")
    assert MEGANIUM in huerfanos and DIPPLIN in huerfanos
    assert APPLIN not in necesarios, "un Basico nunca es un eslabon"
