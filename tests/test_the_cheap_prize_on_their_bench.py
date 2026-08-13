"""A prize the agent cannot see, and the three vetoes that hide it.

THIS TEST PINS BEHAVIOUR IT DOES NOT ENDORSE. Everything asserted below is what
the agent does today, and the turn it describes threw a prize away. It is
written down rather than fixed because fixing it is a TRADE against rules that
each have their own lost game behind them -- the same call the file's note on
phase E4 of the Marnie plan makes (ptcg/turn/options/card.py) -- and because it
is not the kind of defect this project ships blind. When someone changes any of
the three, these tests fail and hand them the board and the arithmetic.

WHERE IT CAME FROM. The first run of `utils/sterile_turn_census.py` (24 dense
games, 180 of our turns) returned two candidate turns; this is the one that
survived reading. Our turn 20 against a Crustle deck, FIVE prizes to four DOWN:

    US                                        THEM
    active  Teal Mask Ogerpon ex 210/210      active  Mega Kangaskhan ex 300/300
            with TWO of Myriad Leaf                   with no energy
            Shower's three                    bench   Mega Kangaskhan ex 400 with
    bench   Ogerpon ex (2), Chikorita,                four, Crustle 170, DWEBBLE
            Hydrapple ex (0), Ogerpon ex (0),         70 with none, Kangaskhan 300
            Tapu Bulu (0)
    hand    ONE Basic {G} Energy, BOSS'S ORDERS, Xerosic, Meganium, Chikorita,
            Meowth ex, Hydrapple ex, Dipplin

The engine offered all three steps of the line: the attachment to the ACTIVE,
the Boss's Orders, and afterwards the attack. Attach (two to three), gust the
Dwebble, Myriad Leaf Shower for 30 + 30 x (3 + 0) = 120 against 70 HP: a prize,
while we are behind on prizes. The turn put the Grass on a BENCHED Hydrapple ex
at zero of two -- a body that cashes nothing this turn or the next -- and ended.

THE THREE VETOES, in the order they bite:

  1. THE CHARGE IS CAPPED BY MATCHUP. `_ripen_energy_capped` (ptcg/calc/energy.py)
     carries an anti-Crustle clause: `op_is_crustle_deck and phys >= 2` is capped.
     The Ogerpon's generic cap on this board is FOUR; the matchup clause is the
     whole of what brings it to two. It exists so we do not pour energy into an
     ex a Crustle wall shrugs off -- and here their active is a Kangaskhan and
     the target a Dwebble, neither of them immune.
  2. NOTHING VALUES A ONE-PRIZE BODY ON THEIR BENCH. The two gust projections
     are `_win_via_boss_gust`, which asks `my_prize <= prizes of the target` (we
     had five, the Dwebble gives one), and `_gust_2prize_via_boss`, which asks
     for `>= 2`. The agent knows how to close a game with a gust and how to hunt
     a two-prize ex on the bench. "Take a cheap prize off their bench" is not a
     thing it can think.
  3. AND THE DWEBBLE IS EXCLUDED BY NAME, twice, in both scans: "log 86339758
     step 98: Dwebble vetoed as a gust in a Crustle deck". This one is not what
     binds -- with five prizes against a one-prize body the two above already
     closed it -- but it is there and it would bite next.

So the Boss's comes back `gust_without_purpose` (there is no knockout until the
Grass lands) and the Grass comes back capped (the cap cannot see the knockout
the Boss's would make), which is the same circular block main.py documents
between Lillie's and the Ultra Ball, spread across two files.

WHY IT IS NOT SHIPPED. The engine contradicts nothing here: it offers all three
plays and the agent merely prices them low. That is a value judgement, not the
illegal reading that earns a neutral change its exception ("An energy that
reaches no cost", "A finisher the front cannot let through"). The rule it would
take has a narrow shape and is written down for whoever picks it up: ON A TURN
WITH NO ATTACK AVAILABLE AT ALL, a gust that takes any prize is worth the
Supporter slot, and a per-matchup cap yields to the charge that arms it.
"""

import copy
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
from golden_corpus import reset_agent
from patching import parcheado
from ptcg.calc.energy import _ogerpon_base_phys_cap, _ripen_energy_capped

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "crustle_step20_the_cheap_prize_on_their_bench.json")

DWEBBLE_HP = 70
OGERPON = m.Teal_Mask_Ogerpon_ex


@pytest.fixture(autouse=True)
def reset_main_state():
    reset_agent(m)
    yield
    reset_agent(m)


def _board():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _theirs(obs):
    return obs["current"]["players"][1 - obs["current"]["yourIndex"]]


def _scores(obs):
    seen = {}

    def spy(context, select, scores, o, my_index, top_n=3):
        seen.setdefault("scores", list(scores))

    with parcheado("_debug_log_decision", spy):
        choice = m.agent(obs)
    return seen["scores"], choice


def _option(obs, predicate):
    for i, o in enumerate(obs["select"]["option"]):
        if predicate(o):
            return i
    raise AssertionError("no such option on this menu")


# ---------------------------------------------------------------------------
# 0. The board, and that the prize is real
# ---------------------------------------------------------------------------

def test_the_board_is_the_one_the_census_found():
    obs = _board()
    mine, theirs = _mine(obs), _theirs(obs)
    active = mine["active"][0]
    assert active["id"] == OGERPON and len(active["energies"]) == 2, (
        "the body in front is one Grass from Myriad Leaf Shower")
    assert sum(1 for c in mine["hand"] if c["id"] == m.Basic_Grass_Energy) == 1
    assert any(c["id"] == m.Boss_Orders for c in mine["hand"]), (
        "the gust that reaches the Dwebble has to be in hand")
    assert any(b and b["hp"] == DWEBBLE_HP for b in theirs["bench"])
    assert (sum(1 for p in mine["prize"] if p is None)
            > sum(1 for p in theirs["prize"] if p is None)), (
        "we are BEHIND on prizes, which is what makes a cheap one worth taking")


def test_the_target_is_not_immune_and_the_attack_reaches_it():
    """The one way the line could be a mirage, closed: Dwebble is not on the
    ex-immunity list, and three energies clear 70 HP with room to spare."""
    obs = _board()
    dwebble = [b for b in _theirs(obs)["bench"] if b and b["hp"] == DWEBBLE_HP][0]
    assert dwebble["id"] not in m.EX_IMMUNE_IDS, (
        "only Crustle and Sylveon are immune to our ex; the Dwebble is not")
    assert 30 + 30 * (3 + 0) >= DWEBBLE_HP, "Myriad Leaf Shower at three energies"


# ---------------------------------------------------------------------------
# 1. Veto one: the charge that arms it is capped BY MATCHUP
# ---------------------------------------------------------------------------

def test_the_matchup_clause_is_the_whole_of_the_cap():
    """Without the anti-Crustle clause this Ogerpon could hold four."""
    obs = _board()
    m.agent(copy.deepcopy(obs))          # so AGENT_STATE reads the matchup
    assert m.AGENT_STATE.op_is_crustle_deck is True
    assert _ogerpon_base_phys_cap(m.AGENT_STATE.meganium_in_play, False) == 4, (
        "the generic cap is four: the two comes from the matchup clause alone")

    active = _mine(obs)["active"][0]

    class _Body:
        id = active["id"]
        energies = active["energies"]

    assert _ripen_energy_capped(_Body(), 4) is True, (
        "at two physical against a Crustle deck the charge is refused")


def test_the_charge_onto_the_active_is_vetoed():
    obs = _board()
    scores, _ = _scores(obs)
    idx = _option(obs, lambda o: (o.get("type") == int(OptionType.ATTACH)
                                  and o.get("inPlayArea") == int(AreaType.ACTIVE)))
    assert scores[idx] <= 0, (
        "the engine offers this attachment and the agent refuses it; it is the "
        "one that arms the only prize on the board")


# ---------------------------------------------------------------------------
# 2. Veto two: the gust has no purpose until the charge lands
# ---------------------------------------------------------------------------

def test_the_gust_is_vetoed_because_the_knockout_does_not_exist_yet():
    obs = _board()
    scores, _ = _scores(obs)
    hand = _mine(obs)["hand"]
    idx = _option(obs, lambda o: (o.get("type") == int(OptionType.PLAY)
                                  and hand[o["index"]]["id"] == m.Boss_Orders))
    assert scores[idx] <= 0, (
        "`gust_without_purpose`: there is no knockout while the Grass sits in "
        "hand, and the cap keeps it there")


# ---------------------------------------------------------------------------
# 3. What the turn does instead
# ---------------------------------------------------------------------------

def test_the_grass_goes_to_a_body_that_cannot_cash_it():
    """A benched Hydrapple ex at zero of Syrup Storm's two: it does not attack
    this turn, it is not in front, and the turn ends with no attack at all."""
    obs = _board()
    _, choice = _scores(obs)
    option = obs["select"]["option"][choice[0]]
    assert option["type"] == int(OptionType.ATTACH)
    assert option["inPlayArea"] == int(AreaType.BENCH)
    target = _mine(obs)["bench"][option["inPlayIndex"]]
    assert target["id"] == m.Hydrapple_ex and len(target["energies"]) == 0
