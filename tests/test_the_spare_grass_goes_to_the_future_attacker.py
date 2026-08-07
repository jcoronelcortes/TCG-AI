"""Once the Teal Dance is spent, the Grass belongs to the body that will attack.

Record (user, episode 90591443 step 21, turn 2 vs Marnie's Grimmsnarl, LOST).
Our first turn, with the active Teal Mask Ogerpon ex's own Teal Dance already
used two steps earlier:

    US                                          RIVAL
    active  Teal Mask Ogerpon ex, 1 of 3        active  Impidimp
    bench   Chikorita, 0 energy                 bench   Impidimp, Grimmsnarl-line
    hand    Boss's Orders, Lillie's Determination,
            Night Stretcher, Bayleef, 1 Grass, Xerosic's

The turn's manual attachment had two destinations. The one on the active was
vetoed by the first-turn rule ("do not overcharge the opening attacker") and the
Chikorita -- the only target left -- took the Grass at 8400. A Chikorita with one
energy is not an attacker: the energy went to a body that was never going to use
it while the body that WAS going to attack sat in front at 1 of the 3 Myriad Leaf
Shower costs. Two steps later the Lillie's Determination shuffled the rest of the
hand into the deck.

THE RULE (`ptcg/turn/options/attach.py`), which only opens once no charging
ability can still attach this turn -- while a Teal Dance or a Ripening Charge is
alive it spends the same Grass for free and the existing precedence rules:

  * last Grass in hand and no route to a Lillie's Determination tomorrow (the
    Supporter itself, a Meowth ex or an Ultra Ball in hand) -> HOLD IT. Spending
    it on development today buys one energy on a body; holding it buys the same
    energy tomorrow via Teal Dance PLUS the card it draws.
  * a Lillie's route, or a second Grass in hand -> SPEND IT ON THE OGERPON ex
    (`SCORE_CHARGE_FUTURE_OGERPON`, the same 8800 rung the first-turn bench table
    already gives a benched Ogerpon ex). With a Lillie's coming, holding is not
    holding: the refill shuffles the hand into the deck, Grass included.

THE MATCHUP DECIDES WHO THE ATTACKER IS. Against Crustle and against Cornerstone
our ex does not damage the wall: there the Chikorita is the first rung of the
Meganium line, Tapu Bulu is the plan, and the behaviour is left exactly as it
was.

Coverage:
  * the record's board: the Grass goes to the active Ogerpon ex, not to the
    Chikorita (the decision the golden corpus already expected);
  * the hold branch -- the same board with no Lillie's route: no attachment at
    all, the Grass survives the turn;
  * the control on the hold branch -- a second Grass in hand and the attachment
    is back on;
  * the matchup control -- the same board with a Dwebble on their bench: the
    Grass goes back to the bench line and the rule never fires;
  * the two predicates, on the cases that decide them.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import AreaType, OptionType
from ptcg.turn.options.attach import _lillie_route_next_turn, _ogerpon_still_short

GRASS = m.Basic_Grass_Energy
OGERPON = m.Teal_Mask_Ogerpon_ex
CHIKORITA = m.Chikorita
LILLIE = m.Lillie_Determination
MEOWTH = m.Meowth_ex
ULTRA_BALL = m.Ultra_Ball

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step21_the_spare_grass_goes_to_the_ogerpon.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _data():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def _replay(sequence_key="sequence", observation_key=None):
    """Replays the turn and returns (choice, the observation decided on)."""
    data = _data()
    seq = data[sequence_key]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = data[observation_key] if observation_key else seq[-1]["observation"]
    return m.agent(obs), obs


def _attach_target(obs, choice):
    """The id the chosen ATTACH points at, or None if it is not an ATTACH."""
    assert choice, f"the agent returned nothing: {choice}"
    opt = obs["select"]["option"][choice[0]]
    if opt.get("type") != int(OptionType.ATTACH):
        return None
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    if opt.get("inPlayArea") == int(AreaType.ACTIVE):
        return mine["active"][0]["id"]
    return mine["bench"][opt["inPlayIndex"]]["id"]


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_step21_the_board_is_the_records_one():
    obs = _data()["sequence"][-1]["observation"]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]

    assert cur["turn"] == 2 and cur["firstPlayer"] == 1, "our first turn, going second"
    assert mine["active"][0]["id"] == OGERPON
    # The one energy is the one its own Teal Dance attached on step 20: the
    # ability is spent and the menu no longer offers it.
    assert len(mine["active"][0]["energies"]) == 1
    assert not any(o.get("type") == int(OptionType.ABILITY)
                   for o in obs["select"]["option"])
    assert [p["id"] for p in mine["bench"]] == [CHIKORITA]
    assert sum(1 for c in mine["hand"] if c["id"] == GRASS) == 1
    assert sum(1 for c in mine["hand"] if c["id"] == LILLIE) == 1, (
        "the refill route of the record: the Lillie's that two steps later "
        "shuffles the hand into the deck")


def test_step21_the_grass_goes_to_the_ogerpon_and_not_to_the_chikorita():
    choice, obs = _replay()
    assert _attach_target(obs, choice) == OGERPON, (
        f"with a Lillie's in hand the Grass is not held -- the refill would "
        f"shuffle it away -- and it belongs to the body that attacks, not to a "
        f"Chikorita that with one energy is not an attacker; got {choice}")


# ---------------------------------------------------------------------------
# 2. The other half: with no refill route the last Grass is not spent
# ---------------------------------------------------------------------------

def test_with_no_refill_route_the_last_grass_stays_in_hand():
    choice, obs = _replay(observation_key="synthetic_no_refill_route")
    assert _attach_target(obs, choice) is None, (
        "no Lillie's, no Meowth ex and no Ultra Ball in hand: the only Grass "
        "pays tomorrow's Teal Dance, which attaches the same energy AND draws")


def test_a_second_grass_in_hand_turns_the_attachment_back_on():
    choice, obs = _replay(
        observation_key="synthetic_two_grass_no_refill_route")
    assert _attach_target(obs, choice) == OGERPON, (
        "with two Grass one of them still pays tomorrow's Teal Dance: the "
        "other one charges the future attacker today")


# ---------------------------------------------------------------------------
# 3. The matchup control: against the ex-immune wall nothing changes
# ---------------------------------------------------------------------------

def test_against_the_crustle_wall_the_grass_stays_on_the_meganium_line():
    choice, obs = _replay(sequence_key="sequence_crustle")
    assert m.AGENT_STATE.op_is_crustle_deck, (
        "the synthetic board has to announce the wall, otherwise this test "
        "measures the same thing as the one above")
    assert _attach_target(obs, choice) == CHIKORITA, (
        "against Crustle our ex does not damage the wall: the Chikorita is the "
        "first rung of the Meganium line and the energy belongs to it")


# ---------------------------------------------------------------------------
# 4. The predicates
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hand, expected", [
    ({LILLIE: 1}, True),
    ({MEOWTH: 1}, True),
    ({ULTRA_BALL: 1}, True),
    ({GRASS: 3}, False),
    ({}, False),
])
def test_the_three_routes_to_a_lillie_tomorrow(hand, expected):
    assert _lillie_route_next_turn(hand) is expected


def test_an_ogerpon_that_already_covers_its_cost_is_not_short():
    class _Pk:
        def __init__(self, cid, energies):
            self.id = cid
            self.energies = [1] * energies

    class _State:
        def __init__(self, active, bench):
            self.active = active
            self.bench = bench

    ready = _Pk(OGERPON, 3)      # Myriad Leaf Shower costs 3
    short = _Pk(OGERPON, 1)
    assert _ogerpon_still_short(_State([short], [])) is True
    assert _ogerpon_still_short(_State([ready], [])) is False
    assert _ogerpon_still_short(_State([ready], [short])) is True, (
        "a charged Ogerpon does not hide the one on the bench that is not")
    assert _ogerpon_still_short(_State([_Pk(CHIKORITA, 0)], [])) is False, (
        "with no Ogerpon ex in play there is no Teal Dance to reserve for")
