"""The engine veto promoted a two-prize body at their match point.

Scenario (self-play mirror, game 276 turn 8; the board is
`tests/fixtures/mirror_t8_match_point_overrules_the_engine_veto.json`, dumped by
the promotion census written up in `log/perm_ties_main/FINDINGS.md`):

    US (4 prizes left)                   THEM (2 prizes left)
    bench  **Meganium 160/160, 4 Grass** active  Hydrapple ex 330/330, 4
           Meowth ex 170/170, 0          bench   Teal Mask Ogerpon ex 210/210, 6
           Meowth ex  50/170, 0                  Teal Mask Ogerpon ex 210/210, 4
           Applin     40/40,  0                  Tapu Bulu 140/140, 2
           Teal Mask Ogerpon ex 210, 0           Meganium, Meowth ex

We retreat, and this menu chooses who takes the front. They are TWO prizes from
the game, so every ex on our bench is the game itself. Read through the agent's
own projector, promoting each candidate in turn:

    Meganium              op_prizes_next=1  op_wins_next=False
    Meowth ex             op_prizes_next=2  op_wins_next=TRUE
    Meowth ex (50 HP)     op_prizes_next=2  op_wins_next=TRUE
    Applin                op_prizes_next=1  op_wins_next=False
    Teal Mask Ogerpon ex  op_prizes_next=2  op_wins_next=TRUE

The agent promoted the **Teal Mask Ogerpon ex at zero energy** -- a two-prize
body that cannot even attack -- while a Meganium with four Grass (one prize, and
Solar Beam costs two) sat next to it.

WHY IT FIRED. `ptcg/turn/options/card.py` protects the Wild Growth engine with a
blanket "the Meganium line does not go active" veto, `score = SCORE_NEVER`, with
narrow exemptions per matchup (Crustle/Cornerstone with four energy, Alakazam,
Neutralization Zone, the forced promotion that finishes). None of them is about
prizes, so in the mirror the veto stands and the charged one-prize body is
removed from the menu:

    #1 idx=4 score=193     Teal Mask Ogerpon ex
    #2 idx=1 score=51      Meowth ex
    #3 idx=3 score=42      Applin
    #4 idx=2 score=15      Meowth ex
    #5 idx=0 score=-10000  Meganium

The rule that should have decided is thirty lines above and had already fired:
"prize denial when promoting" adds +3000 to a body worth fewer prizes than they
still need. `score = SCORE_NEVER` is an ASSIGNMENT, so it overwrites it -- the
project's own recurring shape, a ceiling applied after everything else silently
overriding the rules above it (docs/improving-the-agent.md, step 4).

THE FIX. One more exemption, written with the same sentence the prize-denial
rule already uses (`op_prize <= 2 and prize_count(card) < op_prize`): when the
body that goes to the front decides the game, the engine is not what we are
protecting. It stays as narrow as the others -- their pile at two or less, the
Meganium able to attack THIS turn, and its own price leaving them short. With
their pile at ONE it does not fire, because there a one-prize body hands over
the game exactly like the ex, which is the sentence the measured rule carries.
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
            / "mirror_t8_match_point_overrules_the_engine_veto.json")

MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
APPLIN = m.Applin

# The bench at the promotion, in the order the menu offers it.
BENCH_MEGANIUM, BENCH_MEOWTH, BENCH_MEOWTH_HURT, BENCH_APPLIN, BENCH_OGERPON = range(5)


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _promotion():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return copy.deepcopy(data["sequence"][1]["observation"])


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _theirs(obs):
    cur = obs["current"]
    return cur["players"][1 - cur["yourIndex"]]


def _promoted(obs):
    """The card id the agent brings to the front."""
    choice = m.agent(obs)
    index = obs["select"]["option"][choice[0]]["index"]
    return _mine(obs)["bench"][index]["id"]


def test_the_board_is_the_one_described():
    """A guard on the fixture: if it drifts, every assertion below is measuring
    something else."""
    obs = _promotion()
    bench = _mine(obs)["bench"]
    assert [b["id"] for b in bench] == [MEGANIUM, MEOWTH, MEOWTH, APPLIN, OGERPON]
    assert len(bench[BENCH_MEGANIUM]["energies"]) == 4      # Solar Beam costs 2
    assert len(bench[BENCH_OGERPON]["energies"]) == 0       # it cannot attack
    assert len(_theirs(obs)["prize"]) == 2                  # their match point
    assert len(_mine(obs)["prize"]) == 4


def test_the_charged_one_prize_body_takes_the_front():
    """The whole finding: at their match point the front seat goes to the body
    whose price leaves them short."""
    assert _promoted(_promotion()) == MEGANIUM


def test_it_is_not_promoting_a_body_worth_the_game():
    obs = _promotion()
    assert OGERPON in m.OUR_EX_IDS          # two prizes, which is their whole pile
    assert MEGANIUM not in m.OUR_EX_IDS
    assert _promoted(obs) != OGERPON


def test_with_their_pile_at_three_the_engine_veto_stands():
    """The boundary above: one prize more and the ex in front no longer ends the
    game, so the Wild Growth engine keeps its protection."""
    obs = _promotion()
    _theirs(obs)["prize"] = [None] * 3
    assert _promoted(obs) != MEGANIUM


def test_with_their_pile_at_one_the_exemption_does_not_fire():
    """The boundary below, and it is the measured rule's own sentence: with their
    pile at ONE the one-prize body hands over the game exactly like the ex, so
    the denial buys nothing and the veto is not lifted for it."""
    obs = _promotion()
    _theirs(obs)["prize"] = [None]
    assert _promoted(obs) != MEGANIUM


def test_an_uncharged_meganium_is_still_vetoed():
    """The exemption is about the body that can ANSWER this turn. A Meganium
    that cannot attack is the engine and nothing else, and the veto owns it."""
    obs = _promotion()
    _mine(obs)["bench"][BENCH_MEGANIUM]["energies"] = []
    _mine(obs)["bench"][BENCH_MEGANIUM]["energyCards"] = []
    assert _promoted(obs) != MEGANIUM
