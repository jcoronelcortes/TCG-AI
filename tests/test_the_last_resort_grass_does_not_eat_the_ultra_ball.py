"""The attachment its own scorer called a last resort does not take the order.

Scenario (`records/registro_006_pasos_053_hasta_059.json`, episode 92239504,
step 54, turn 6 vs Marnie's Grimmsnarl ex, LOST):

    US (5 prizes)                       RIVAL (5 prizes)
    active Teal Mask Ogerpon ex         active Marnie's Grimmsnarl ex 300/320
           190/210, 4 effective         bench  2x Munkidori, 2x Froslass,
    bench  Meganium 130/160 (1 of 5)           Marnie's Impidimp
    hand   ULTRA BALL, Applin,          stadium Spikemuth Gym
           Basic {G} Energy

The menu, with what the agent thought of each option and the tier it then
handed out:

    [0] Ultra Ball          score 11900   tier  0
    [3] Grass -> Meganium   score    20   tier 10   <-- played
    [5] stadium ability     score 29000   tier  0
    [6] attack              score  1100   tier  0

That 29000 is now a VETO, and the note belongs here because this menu is where
the number was first written down. The stadium was their Spikemuth Gym --
"search your deck for a Marnie's Pokemon" -- and this deck has none: firing it
shuffles our deck and does nothing else. It scored 29000 for the same reason
Academy at Night did (see `tests/test_their_academy_at_night_does_not_eat_our_supporter.py`):
the ABILITY scorer priced every stadium it had never been taught at the band of
a real play. The ORDER argument below is unchanged -- the Ultra Ball at 11900
was always the play the tier was burying.

Twenty. `energy_score` had already answered out loud: `SCORE_CHARGE_DOOMED` is
the ceiling it puts on a body the opponent can cash in before our next turn, and
its own comment reads "if there is nothing better left, the energy still lands
here". There was something better left, six hundred times better -- but
`_TIER_ENERGY` (10) is handed to every ATTACH without asking what it is worth,
and a tier decides before any score is compared.

The Grass was not merely wasted. Ultra Ball costs TWO cards from hand: with
three in hand it was legal, the attachment left two, and one action later the
Ultra Ball was no longer on the menu at all. The turn attacked -- it did knock
the Grimmsnarl ex out -- and ended with the Ultra Ball and the Applin dead in
hand and four empty bench seats.

This is the law the Supporters already have (`SUPP_SCORE_LAST_RESORT_BAND`, the
height at which a scorer says "play me only if nothing else scores"), read for
the first time by the energy tier. It YIELDS the order, it is not cancelled:
turn-closers are excluded from the comparison, so once the real plays are gone
the attachment returns to `_TIER_ENERGY` and still goes down ahead of the
attack -- which is what step 90 below pins.

What the turn buys with the card it had thrown away needs no rule of its own:
Ultra Ball -> Meowth ex -> Last-Ditch Catch -> Lillie's Determination -> six
cards, every link already scored for by rules that were there all along
(`no_attacker_prefers_meowth`, 1250, over the second Ogerpon ex at 700). The
whole chain is replayed below so a later change cannot quietly break a link of
it: this is the turn the fix exists to make possible.

Frames 53 and 54 are the record's own. 55-60 and 90 are built, because the real
game attached the Grass at 54 and the Ultra Ball was never legal again -- there
are no real frames for the turn that plays it.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402
from ptcg.cards.ids import SCORE_CHARGE_DOOMED  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_t6_the_last_resort_grass_ate_the_ultra_ball.json")

ULTRA_BALL = m.Ultra_Ball
GRASS = m.Basic_Grass_Energy
APPLIN = m.Applin
MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex
GRIMMSNARL = 648


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
    first menu of the turn, and the tier is recomputed on every one of them.
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


# ---------------------------------------------------------------------------
# 1. The board, and the arithmetic that makes the order matter
# ---------------------------------------------------------------------------

def test_the_board_is_the_one_from_the_record():
    obs = _frames()[54]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    op = cur["players"][1 - cur["yourIndex"]]

    assert _hand_ids(obs) == [ULTRA_BALL, APPLIN, GRASS], (
        "three cards, and the Ultra Ball costs TWO of the other two: spending "
        "either one of them makes the search illegal, not merely worse")
    assert len(mine["bench"]) == 1 and mine["bench"][0]["id"] == MEGANIUM
    assert mine["active"][0]["id"] == OGERPON
    assert op["active"][0]["id"] == GRIMMSNARL and op["active"][0]["hp"] == 300
    assert cur["energyAttached"] is False, "the turn's attachment is unspent"


def test_the_attachment_is_priced_in_the_last_resort_band():
    """The fix reads the agent's own number, so that number is the test."""
    obs = _frames()[54]
    scores = _scores_of(obs)
    attach = [i for i, o in enumerate(obs["select"]["option"])
              if o.get("type") == int(m.OptionType.ATTACH)
              and o.get("inPlayArea") == int(m.AreaType.BENCH)]
    assert attach, "the Grass can go on the benched Meganium"
    assert 0 < scores[attach[0]] < SCORE_CHARGE_DOOMED + 1, (
        "`energy_score` caps a doomed body at SCORE_CHARGE_DOOMED (20) -- "
        f"it scored {scores[attach[0]]}")
    ultra = next(i for i, o in enumerate(obs["select"]["option"])
                 if o.get("type") == int(m.OptionType.PLAY)
                 and _hand_ids(obs)[o["index"]] == ULTRA_BALL)
    assert scores[ultra] == max(scores) > 100 * scores[attach[0]], (
        "and the same menu holds a play the same agent priced two orders of "
        "magnitude higher: the Ultra Ball")


def _scores_of(obs):
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

    m.agent(_frames()[53])
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


# ---------------------------------------------------------------------------
# 2. The order: the Grass does not go down while a real play is waiting
# ---------------------------------------------------------------------------

def test_the_last_resort_grass_does_not_take_the_turns_order():
    obs, choice = _replay([53, 54])
    opt = obs["select"]["option"][choice[0]]
    assert opt.get("type") != int(m.OptionType.ATTACH), (
        "an attachment its own scorer priced at 20 cannot outrank an 11900 "
        "Ultra Ball by ORDER alone")


def test_the_ultra_ball_survives_the_menu_that_used_to_eat_it():
    obs, _ = _replay([53, 54])
    assert GRASS in _hand_ids(obs), "sanity: the fixture frame still holds it"
    nxt = _frames()[55]
    assert _hand_ids(nxt) == [ULTRA_BALL, APPLIN, GRASS], (
        "with the Grass unspent the hand still has the two cards the Ultra "
        "Ball discards, so the search is still legal")


def test_and_then_the_ultra_ball_is_the_play():
    obs, choice = _replay([53, 54, 55])
    opt = obs["select"]["option"][choice[0]]
    assert opt.get("type") == int(m.OptionType.PLAY)
    cur = obs["current"]
    played = cur["players"][cur["yourIndex"]]["hand"][opt["index"]]["id"]
    assert played == ULTRA_BALL, (
        "the card the whole turn was about: it was the second best number on "
        f"the menu all along. It played {m.card_table[played].name}")


# ---------------------------------------------------------------------------
# 3. It yields the order, it is not cancelled
# ---------------------------------------------------------------------------

def test_the_grass_still_goes_down_before_the_attack():
    """The demotion lasts only while a real play is waiting.

    This is the regression the fix is most likely to cause and the reason
    turn-closers are excluded from the comparison: dropped flat into tier 0 the
    attachment would lose to the attack (1100 > 20) and the turn's
    non-accumulating energy would be lost outright.
    """
    obs, choice = _replay([53, 54, 90])
    opt = obs["select"]["option"][choice[0]]
    assert opt.get("type") == int(m.OptionType.ATTACH), (
        "with the Ultra Ball and the ability spent nothing on the menu "
        "outscores the attachment any more, so it returns to `_TIER_ENERGY` "
        "and goes down AHEAD of the attack, exactly as it always did")


# ---------------------------------------------------------------------------
# 4. What the turn buys with the card it used to throw away
# ---------------------------------------------------------------------------

def _fetched_id(obs, choice):
    return obs["select"]["deck"][
        obs["select"]["option"][choice[0]]["index"]]["id"]


def test_the_search_buys_the_refill_engine_and_not_a_second_body():
    obs, choice = _replay([53, 54, 55, 56])
    got = _fetched_id(obs, choice)
    assert got == m.Meowth_ex, (
        "`no_attacker_prefers_meowth` (1250) over the second Teal Mask "
        "Ogerpon ex (`energy_for_teal_dance`, 700): the deepest look at the "
        f"deck wins the search. It fetched {m.card_table[got].name}")


def test_the_body_the_ultra_ball_paid_for_goes_down():
    obs, choice = _replay([53, 54, 55, 56, 57])
    opt = obs["select"]["option"][choice[0]]
    cur = obs["current"]
    assert opt.get("type") == int(m.OptionType.PLAY)
    played = cur["players"][cur["yourIndex"]]["hand"][opt["index"]]["id"]
    assert played == m.Meowth_ex, (
        "its Last-Ditch Catch is the only reason it was bought, and the "
        "Supporter slot of the turn is still free")


def test_the_last_ditch_fetches_the_refill():
    obs, choice = _replay([53, 54, 55, 56, 57, 58])
    got = _fetched_id(obs, choice)
    assert got == m.Lillie_Determination, (
        f"six cards. It fetched {m.card_table[got].name}")


def test_the_grass_goes_down_before_the_refill_shuffles_it_away():
    """Lillie's Determination shuffles the hand into the deck and draws six.

    So the order is not a preference: an attachment left in hand while the
    refill resolves is an attachment shuffled into the deck.
    """
    obs, choice = _replay([53, 54, 55, 56, 57, 58, 59])
    opt = obs["select"]["option"][choice[0]]
    assert opt.get("type") == int(m.OptionType.ATTACH), (
        "with the Supporter in hand the last-resort band no longer decides "
        "anything: what decides is that the hand is about to be shuffled")
    assert opt.get("inPlayArea") == int(m.AreaType.ACTIVE), (
        "and it goes on the body that attacks, not on the doomed Meganium")


def test_and_then_the_refill_is_played():
    obs, choice = _replay([53, 54, 55, 56, 57, 58, 59, 60])
    opt = obs["select"]["option"][choice[0]]
    cur = obs["current"]
    assert opt.get("type") == int(m.OptionType.PLAY)
    played = cur["players"][cur["yourIndex"]]["hand"][opt["index"]]["id"]
    assert played == m.Lillie_Determination, (
        "the whole point of the chain: the turn that used to end with an "
        "Ultra Ball dead in hand ends with six fresh cards instead")
