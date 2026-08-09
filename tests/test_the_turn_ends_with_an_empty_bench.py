"""Ending turn one with an empty bench and a Meowth ex still in hand.

FOUND BY `utils/invariant_monitor.py`, and it is the first thing this project has
that finds a board NOBODY LOST A GAME ON. Every other file in tests/ is named
after a defeat; this one is named after an invariant that a machine checked on
63 769 decisions in an afternoon.

THE INVARIANT. Never end a turn with an empty bench. It needs no judgement about
the game to state: with nothing on the bench, the next knockout is not a prize,
it is the match.

THE BOARD (turn 1, ours):

    active  Tapu Bulu, no energy
    bench   EMPTY
    hand    Basic {G} x3, Meganium, Forest of Vitality, Lana's Aid, **Meowth ex**
    menu    3x ATTACH, 2x PLAY, END          -> the agent chooses END

Meowth ex is a Basic. Putting it down costs nothing, is offered on the menu, and
turns "the next knockout ends the match" into "the next knockout is one prize".

WHY IT IS A DEFECT AND NOT A JUDGEMENT CALL. main.py already carries a
last-resort net written for exactly this -- post-scoring, deliberately
independent of whether the individual vetoes misfire: if the bench is empty and
the best option is END or sterile, find something that develops the bench (an
Ultra Ball that can dig a Basic, or a Basic in hand) and force it above the best
score. The net exists, the board satisfies its premise, and it does not fire.

The most likely reason it does not is the Meowth veto: there is a separate rule
against putting Meowth ex down when the active is already a ready attacker, and
that rule was written about a healthy board where the bench is not empty. This
is the pattern the project keeps rediscovering -- a special case outliving the
general rule it was carved out of.

FREQUENCY, measured: 16 boards in 500 games, all 16 with Meowth ex as the card
left in hand, and all 16 reproduce deterministically when replayed through
main.py. A further 54 empty-bench endings in the same run were FORCED -- nothing
playable in hand -- and those are not defects; the monitor separates them.

The fix is behavioural and is not attempted here.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _extra in (str(ROOT), str(ROOT / "utils")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from cg.api import CardType, OptionType  # noqa: E402
from ptcg.cards.tables import card_table  # noqa: E402

FIXTURE = (ROOT / "tests" / "fixtures"
           / "the_turn_ends_with_an_empty_bench_and_a_meowth_in_hand.json")


def _board():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _mine(board):
    obs = board["observation"]
    return obs["current"]["players"][board["violation"]["seat"]]


def _agent():
    import selfplay as sp
    mod = sp.load_agent(str(ROOT / "main.py"), "empty_bench_regression")
    sp._reset_si_aplica(mod)
    return mod


def _chosen_types(board):
    mod = _agent()
    obs = board["observation"]
    choice = mod.agent(copy.deepcopy(obs))
    options = obs["select"]["option"]
    return [options[i].get("type") for i in choice]


def test_the_bench_is_empty_on_this_board():
    mine = _mine(_board())
    assert [b for b in (mine.get("bench") or []) if b] == []
    assert mine["active"], "there is an active, so this is not a promotion"


def test_a_basic_pokemon_is_sitting_in_hand():
    """The card that would fix the board is in hand and is a Basic."""
    mine = _mine(_board())
    basics = [card_table.get(c["id"]) for c in (mine.get("hand") or [])]
    basics = [cd for cd in basics
              if cd is not None
              and getattr(cd, "cardType", None) == CardType.POKEMON
              and getattr(cd, "basic", False)]
    assert [getattr(cd, "name", "?") for cd in basics] == ["Meowth ex"]


def test_the_menu_offers_something_other_than_ending():
    """This is what separates the defect from a forced ending.

    54 of the 70 empty-bench endings in the same 500-game run had nothing
    playable at all. On this board the menu offers two PLAY options, so ending
    is a choice.
    """
    options = _board()["observation"]["select"]["option"]
    kinds = [o.get("type") for o in options]
    assert int(OptionType.END) in kinds
    assert kinds.count(int(OptionType.PLAY)) >= 1


@pytest.mark.xfail(strict=True,
                   reason="open: the last-resort net for an empty bench does not "
                          "fire here; the fix is behavioural and needs a gate")
def test_the_agent_does_not_end_the_turn_with_an_empty_bench():
    """Live, against main.py, so it goes green the day the net is fixed."""
    assert int(OptionType.END) not in _chosen_types(_board())
