"""Cheap fodder is a property of the hand, not the name of a card.

Scenario (`records/registro_006_pasos_053_hasta_056.json`, episode 92216882,
step 53, turn 6 vs Archaludon ex, LOST):

    US (6 prizes)                        RIVAL (5 prizes)
    active Hydrapple ex 330/330,         active Archaludon ex 400/400 + tool
           2 Grass, no KO in sight       bench  Dudunsparce, Duraludon
    bench  Bayleef 110/110 (1 of 5)      stadium Full Metal Lab
    hand   ULTRA BALL, Hydrapple ex,
           Basic {G} Energy

The menu, with what the agent thought of each option and the tier it handed out:

    [1] Grass -> Bayleef       score  8000   tier 10
    [2] Ultra Ball             score 12400   tier  0
    [3] Ripening Charge        score 30000   tier 10   <-- played

`_ub_engine_refresh_pivot` is written for exactly this board -- an active that
does not knock out, one body on the bench, the turn's Supporter unspent, Meowth
ex and Lillie's Determination in the deck -- and it stayed silent for one
reason: it asked for two Basic {G} Energy in hand and the hand held one. So the
Ultra Ball kept its ordinary 12400 in tier 0, Ripening Charge took the ORDER
(tier 10 decides before any score is compared), the Grass went from the hand
onto the Bayleef, and with two cards left the Ultra Ball -- which discards TWO
-- was no longer on the menu at all. The turn ended with the second Hydrapple ex
and the Ultra Ball dead in hand and four empty bench seats, against a 400 HP
active we cannot answer.

The second card of surplus was there the whole time. That second Hydrapple ex
was unplayable cardboard: no Dipplin in play or in hand, and the one Hydrapple
ex the board can wear is already worn. `_ub_real_fodder` is the count that says
so -- it prices EVERY card in hand by what the DISCARD scorer would really let
go, keeping linked evolution pieces, the lone refill Supporter, a playable
Meowth ex and the Stamp -- and it is the same arithmetic `_ub_cancel_no_surplus`
already uses for the same question. Two energies were one instance of surplus,
not the definition of it.

The turn the fix makes possible is replayed below, link by link, so a later
change cannot quietly break one of them: Ultra Ball -> the cost eats the two
cards nothing was waiting on -> Meowth ex -> Last-Ditch Catch -> Lillie's
Determination.

Frame 53 is the record's own. The rest are built, because the real game spent
the Grass at 53 and the Ultra Ball was never legal again -- there are no real
frames for the turn that plays it. 90 and 91 are the two halves of the guard:
with no Ultra Ball on the menu the ability is not demoted by anything, and with
a live evolution piece where the dead one was the hand has no surplus and the
Ultra Ball is not a pivot at all.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "archaludon_t6_the_pivot_asked_for_two_energies.json")

ULTRA_BALL = m.Ultra_Ball
GRASS = m.Basic_Grass_Energy
HYDRAPPLE = m.Hydrapple_ex
BAYLEEF = m.Bayleef
MEGANIUM = m.Meganium
ARCHALUDON = 190

# What `_ub_engine_refresh_pivot` scores the Ultra Ball at, and the only reason
# a tier-0 item can outrank an ability: the pivot lifts it into `_TIER_ENERGY`.
PIVOT_SCORE = 31450


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
    return {item["step"]: item["observation"] for item in data["sequence"]}


def _replay(steps):
    """Answers the fixture's menus IN ORDER and returns (obs, choice) of the last.

    In order on purpose: the turn's plan and the per-turn flags are built by the
    first menu of the turn, and `_ub_engine_pivot_turn` -- the flag that makes
    the search choose Meowth ex -- is armed by the menu that plays the card.
    """
    frames = _frames()
    obs = choice = None
    for step in steps:
        obs = frames[step]
        choice = m.agent(obs)
    return obs, choice


def _hand_ids(obs):
    cur = obs["current"]
    return [c["id"] for c in cur["players"][cur["yourIndex"]]["hand"]]


def _scores_of(obs, warmup=()):
    """The per-option scores `finalizar` computed for this menu."""
    captured = {}

    def tracer(frame, event, arg):
        if frame.f_code.co_name != "finalizar":
            return None
        if event == "call":
            return tracer
        if event == "return":
            captured.setdefault("scores", list(frame.f_locals.get("scores") or []))
        return tracer

    frames = _frames()
    for step in warmup:
        m.agent(frames[step])
    # Keep and restore the tracer that was already installed: `None` would not
    # turn ours off, it would turn coverage's off for the whole process. See
    # `tests/test_no_test_uninstalls_the_tracer.py`.
    _previous_tracer = sys.gettrace()
    sys.settrace(tracer)
    try:
        m.agent(obs)
    finally:
        sys.settrace(_previous_tracer)
    return captured["scores"]


def _option_index(obs, **fields):
    for i, opt in enumerate(obs["select"]["option"]):
        if all(opt.get(k) == v for k, v in fields.items()):
            return i
    raise AssertionError(f"no option with {fields} in {obs['select']['option']}")


# ---------------------------------------------------------------------------
# 1. The board, and the arithmetic that makes the order matter
# ---------------------------------------------------------------------------

def test_the_board_is_the_one_from_the_record():
    obs = _frames()[53]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    op = cur["players"][1 - cur["yourIndex"]]

    assert _hand_ids(obs) == [HYDRAPPLE, GRASS, ULTRA_BALL], (
        "three cards, and the Ultra Ball costs TWO of the other two: spending "
        "either one of them makes the search illegal, not merely worse")
    assert len(mine["bench"]) == 1 and mine["bench"][0]["id"] == BAYLEEF
    assert mine["active"][0]["id"] == HYDRAPPLE
    assert op["active"][0]["id"] == ARCHALUDON and op["active"][0]["hp"] == 400
    assert cur["supporterPlayed"] is False, "the refill the chain buys is playable"


def test_the_hydrapple_in_hand_is_cardboard():
    """The card the old test would not count, and the reason it is surplus."""
    obs = _frames()[53]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    in_play = [p["id"] for p in mine["active"] + mine["bench"]]
    pre = [pe["id"] for p in mine["active"] + mine["bench"]
           for pe in p["preEvolution"]]
    assert HYDRAPPLE in _hand_ids(obs)
    assert m.Dipplin not in in_play and m.Dipplin not in _hand_ids(obs), (
        "with no Dipplin anywhere the second Hydrapple ex cannot be played "
        "this turn or any turn soon")
    assert m.Dipplin in pre and HYDRAPPLE in in_play, (
        "the one body that could wear it is already wearing one")


def test_the_pivot_prices_the_ultra_ball_as_the_engine():
    """The fix is read through the agent's own number, so that number is here."""
    obs = _frames()[53]
    scores = _scores_of(obs)
    ub = _option_index(obs, type=int(m.OptionType.PLAY))
    assert scores[ub] == PIVOT_SCORE, (
        "with two cards of real surplus the hand can pay for the search, so "
        "the Ultra Ball is the UB -> Meowth -> Lillie's engine and not an "
        f"ordinary item. It scored {scores[ub]}")


# ---------------------------------------------------------------------------
# 2. The order: the ability does not spend the card the search needs
# ---------------------------------------------------------------------------

def test_the_ability_does_not_eat_the_ultra_balls_fodder():
    obs, choice = _replay([53])
    opt = obs["select"]["option"][choice[0]]
    assert opt.get("type") != int(m.OptionType.ABILITY), (
        "Ripening Charge takes the Grass out of the hand, and with two cards "
        "left the Ultra Ball -- which discards two -- is off the menu")
    assert opt.get("type") == int(m.OptionType.PLAY)
    cur = obs["current"]
    played = cur["players"][cur["yourIndex"]]["hand"][opt["index"]]["id"]
    assert played == ULTRA_BALL


def test_the_cost_takes_the_two_cards_nothing_was_waiting_on():
    obs, choice = _replay([53, 54])
    cur = obs["current"]
    hand = cur["players"][cur["yourIndex"]]["hand"]
    taken = sorted(hand[obs["select"]["option"][i]["index"]]["id"] for i in choice)
    assert taken == sorted([HYDRAPPLE, GRASS]), (
        "the arithmetic, not a preference: the cost is two of two, and this "
        "pins that the pair the pivot called surplus is the pair that pays")


# ---------------------------------------------------------------------------
# 3. What the turn buys with the card it used to leave dead in hand
# ---------------------------------------------------------------------------

def _fetched_id(obs, choice):
    return obs["select"]["deck"][
        obs["select"]["option"][choice[0]]["index"]]["id"]


def test_the_search_buys_the_refill_engine():
    obs, choice = _replay([53, 54, 55])
    got = _fetched_id(obs, choice)
    assert got == m.Meowth_ex, (
        "`_ub_engine_pivot_turn` is armed by the play, so the search is the "
        f"engine's and not a body's. It fetched {m.card_table[got].name}")


def test_the_body_the_ultra_ball_paid_for_goes_down():
    obs, choice = _replay([53, 54, 55, 56])
    opt = obs["select"]["option"][choice[0]]
    cur = obs["current"]
    assert opt.get("type") == int(m.OptionType.PLAY)
    played = cur["players"][cur["yourIndex"]]["hand"][opt["index"]]["id"]
    assert played == m.Meowth_ex, (
        "its Last-Ditch Catch is the only reason it was bought, and the "
        "Supporter slot of the turn is still free")


def test_the_last_ditch_fetches_the_refill():
    obs, choice = _replay([53, 54, 55, 56, 57])
    got = _fetched_id(obs, choice)
    assert got == m.Lillie_Determination, (
        f"the hand the turn was about. It fetched {m.card_table[got].name}")


def test_and_then_the_refill_is_played():
    obs, choice = _replay([53, 54, 55, 56, 57, 58])
    opt = obs["select"]["option"][choice[0]]
    cur = obs["current"]
    assert opt.get("type") == int(m.OptionType.PLAY)
    played = cur["players"][cur["yourIndex"]]["hand"][opt["index"]]["id"]
    assert played == m.Lillie_Determination, (
        "the turn that used to end with an Ultra Ball and a Hydrapple ex dead "
        "in hand ends with a body on the bench and a whole new hand instead")


# ---------------------------------------------------------------------------
# 4. The two halves of the guard
# ---------------------------------------------------------------------------

def test_the_ability_still_takes_the_turn_with_no_search_waiting():
    """Nothing is cancelled: the Ultra Ball is what the ability was yielding to.

    Same board, same hand, minus the Ultra Ball. With no search on the menu the
    free attachment of the turn is the best thing the turn can do, and it is
    still done -- the regression this fix would most easily cause.
    """
    obs, choice = _replay([90])
    opt = obs["select"]["option"][choice[0]]
    assert opt.get("type") == int(m.OptionType.ABILITY), (
        "Ripening Charge is demoted by nothing here; it is the turn")


def test_a_live_evolution_piece_is_not_surplus():
    """Specificity: the count has to say NO on the hand that has no surplus.

    The same three cards, except the second one is a Meganium and our bench is
    wearing its Bayleef. The cost would eat an evolution the board can put on
    today, so the hand cannot pay for the search out of surplus, the cost vetoes
    speak, and the Ultra Ball is not the engine.
    """
    obs = _frames()[91]
    assert MEGANIUM in _hand_ids(obs) and obs["current"]["players"][0][
        "bench"][0]["id"] == BAYLEEF
    scores = _scores_of(obs)
    ub = _option_index(obs, type=int(m.OptionType.PLAY))
    assert scores[ub] != PIVOT_SCORE, (
        "with one card of real fodder the pivot must stay silent -- otherwise "
        "the search pays for itself with the line it exists to build")
    assert scores[ub] <= 0, (
        "and the cost vetoes that share the count cancel it outright")
