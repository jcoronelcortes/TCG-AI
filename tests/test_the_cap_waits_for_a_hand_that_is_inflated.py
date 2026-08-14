"""Six cards is the hand a player HAS, not an inflated one: the floor moves with
our prize counter.

Scenario (user, `records/registro_003_pasos_025_hasta_031.json`, episode
92856565, step 29, turn 3 vs Alakazam -- LOST):

    US (6 prizes, seat 0)                      RIVAL (Alakazam, 6 prizes)
    active Tapu Bulu 130/140, 1 {G}            active 305, 70 HP
    bench  Teal Mask Ogerpon ex x2 (1 {G}      bench  Abra x4, Fezandipiti ex
           each), Chikorita, Applin            hand   SIX cards
    hand   Lana's Aid, **Xerosic's             discard 2
           Machinations**, Lillie's
           Determination, Meganium,
           Teal Mask Ogerpon ex

The menu was {play Xerosic, play Lillie's Determination, play Ogerpon ex, end
turn} and the turn's Supporter went on the **Xerosic**: their hand 6 -> 3, three
cards discarded on turn 3, and Powerful Hand (20 x card in their hand) down from
160 to 100 for exactly as long as it took them to draw again.

WHY IT FIRED, and it is not a bug in the old rule: the floor of six
(`alakazam_needs_the_hand_floor`, bought by step 17 of the same record) was
cleared by exactly one card. Six is the number a hand REACHES on its own -- draw
a card a turn from an opening seven and the opponent sits at six most of the
early game -- so on turn 3 the floor was not measuring an inflated hand, it was
measuring a dealt one.

CARD RULE (user, august 2026): vs Alakazam the floor is TWO numbers, and OUR
prize counter picks between them.

  * FIVE OR MORE of our prizes still up -> the opposing hand has to reach
    **EIGHT**. There is a whole game left in which Powerful Hand will be
    projecting 200+ and the single copy of the cap is the matchup's only answer
    to it; spending it on a hand that merely got dealt buys three cards their
    deck gives straight back.
  * FEWER THAN FIVE left -> **SIX**, the floor exactly as it was written. From
    the fifth prize on there is no "later" to save the card for: the cap only
    has to buy the turns that remain.

The rule lives in `_xr_alakazam_floor` and is read by everything that decides
about this card -- the play ladder (`alakazam_needs_the_hand_floor`,
`_xr_gate_alakazam`), the Last-Ditch fetch
(`alakazam_xerosic_needs_the_hand_floor`, `xerosic_alakazam`) and the Ultra Ball
engine that digs for it (`_alakazam_dig_xerosic_engine`) -- because a card the
play side will not play is not a card worth searching for.

See `tests/test_the_cap_waits_until_their_hand_is_worth_capping.py` for the
shape of the floor (a veto, asked before the search, one matchup only) and
[[la-observacion-manda-en-la-vida-nosotros-solo-calculamos-el-dano]] for the
damage model behind Powerful Hand.
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
from ptcg.cards import ids
from ptcg.decision.disruption import (_xr_alakazam_floor,
                                      _xr_below_the_alakazam_floor)

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_the_cap_waits_for_an_inflated_hand_step29.json")

XEROSIC = m.Xerosic_Machinations
LILLIE = m.Lillie_Determination
OGERPON = m.Teal_Mask_Ogerpon_ex
ABRA = m.Abra
TAPU = m.Tapu_Bulu

_END_TURN = 14      # OptionType.END_TURN
_PLAY = 7           # OptionType.PLAY


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    yield
    m._init_cards_tracking()


def _obs(op_hand=None, my_prizes=None):
    obs = copy.deepcopy(
        json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    cur = obs["current"]
    if op_hand is not None:
        cur["players"][1 - cur["yourIndex"]]["handCount"] = op_hand
    if my_prizes is not None:
        cur["players"][cur["yourIndex"]]["prize"] = [None] * my_prizes
    return obs


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _played(obs, choice):
    """The card id the chosen option plays, or None if it plays nothing."""
    opt = obs["select"]["option"][choice[0]]
    if opt.get("type") != _PLAY:
        return None
    return [c["id"] for c in _mine(obs)["hand"]][opt["index"]]


# ---------------------------------------------------------------------------
# 1. The record: the board, and then the decision
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_menu_that_spent_the_supporter():
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    op = cur["players"][1 - cur["yourIndex"]]

    assert cur["turn"] == 3
    assert cur["supporterPlayed"] is False, "el Supporter del turno sigue libre"
    assert len(mine["prize"]) == 6 and len(op["prize"]) == 6, (
        "seis premios cada uno: el tablero de salida")
    assert op["handCount"] == 6, "su mano: SEIS cartas, las que se reparten"
    assert XEROSIC in [c["id"] for c in mine["hand"]]
    assert any(p["id"] == ABRA for p in op["bench"]), (
        "la linea Alakazam en su banca es lo que enciende el matchup")
    assert mine["active"][0]["id"] == TAPU
    assert [opt.get("type") for opt in o["select"]["option"]] == [
        _PLAY, _PLAY, _PLAY, _END_TURN]


def test_the_cap_is_not_spent_on_a_hand_that_was_merely_dealt():
    """The regression of the record: their hand at six on turn 3 with all six of
    our prizes up cleared the old floor by one card."""
    o = _obs()
    assert _played(o, m.agent(o)) != XEROSIC, (
        "con 6 premios nuestros y su mano en 6 el tope se guarda: seis cartas "
        "es la mano repartida, no una mano inflada")


def test_and_the_supporter_goes_to_the_refill_instead():
    """The turn is not wasted -- it is the same slot, spent on the card that
    develops. The floor moves the cap out of the way, it does not end the turn."""
    o = _obs()
    assert _played(o, m.agent(o)) == LILLIE


# ---------------------------------------------------------------------------
# 2. The two numbers, on the record's own board
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("op_hand", [6, 7])
def test_early_the_floor_is_eight(op_hand):
    o = _obs(op_hand)
    assert _played(o, m.agent(o)) != XEROSIC, (
        f"mano rival {op_hand} < 8 con 6 premios: por debajo del suelo")


@pytest.mark.parametrize("op_hand", [8, 10])
def test_early_the_cap_is_played_from_eight(op_hand):
    """Powerful Hand projecting 20 x (8 + 2) = 200: that is an inflated hand,
    and the cap takes it to 100."""
    o = _obs(op_hand)
    assert _played(o, m.agent(o)) == XEROSIC


def test_from_the_fifth_prize_on_six_is_the_floor_again():
    """Same board, our prize counter moved: with four prizes left there is no
    later turn to save the card for and six cards pay for the Supporter."""
    o = _obs(op_hand=6, my_prizes=4)
    assert _played(o, m.agent(o)) == XEROSIC


def test_and_under_that_floor_it_still_waits():
    o = _obs(op_hand=5, my_prizes=4)
    assert _played(o, m.agent(o)) != XEROSIC


# ---------------------------------------------------------------------------
# 3. The predicate itself: one function, read by every scorer of this card
# ---------------------------------------------------------------------------

class _Ctx:
    """The three fields the floor reads."""

    def __init__(self, my_prize, op_hand_count=0, alakazam=True):
        self.my_prize = my_prize
        self.op_hand_count = op_hand_count
        self.op_is_alakazam_deck = alakazam


@pytest.mark.parametrize("my_prize,floor", [(6, 8), (5, 8), (4, 6), (2, 6),
                                            (1, 6)])
def test_the_floor_by_prize(my_prize, floor):
    assert _xr_alakazam_floor(_Ctx(my_prize)) == floor


def test_the_numbers_are_constants_and_not_literals():
    assert ids.XEROSIC_ALAKAZAM_FLOOR_EARLY == 8
    assert ids.XEROSIC_ALAKAZAM_FLOOR_LATE == 6
    assert ids.XEROSIC_ALAKAZAM_EARLY_PRIZES == 5


def test_the_floor_defaults_to_the_opening_board():
    """A context that does not carry the prize counter is answered as the start
    of a game -- the strict end of the floor -- so no caller can lose the rule
    by forgetting to pass it."""

    class _NoPrize:
        op_hand_count = 7
        op_is_alakazam_deck = True

    assert _xr_alakazam_floor(_NoPrize()) == ids.XEROSIC_ALAKAZAM_FLOOR_EARLY
    assert _xr_below_the_alakazam_floor(_NoPrize())


@pytest.mark.parametrize("my_prize", [6, 4])
def test_outside_the_alakazam_matchup_the_floor_says_nothing(my_prize):
    assert not _xr_below_the_alakazam_floor(
        _Ctx(my_prize, op_hand_count=1, alakazam=False))
