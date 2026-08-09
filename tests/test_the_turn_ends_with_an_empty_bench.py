"""Holding the lone Meowth ex on turn one, and why that is not the bug it looks like.

THIS FILE STARTED LIFE AS A FALSE ALARM, and it is kept because the false alarm
is the lesson.

`utils/invariant_monitor.py` was built to check things that must never be true on
every decision of every game. Its first run reported 16 violations of "never end
a turn with an empty bench" in 500 games, all 16 with a Meowth ex still in hand,
all 16 reproducing deterministically. It looked like the first defect this
project had ever found without losing a game for it.

It was not a defect. All sixteen are OUR FIRST TURN HAVING GONE FIRST, and on
that board main.py holds the lone Meowth ex on purpose (`_ft_hold_lone_meowth`,
consumed by the anti-empty-bench net in ptcg/turn/finalize.py). The reasoning is
already written next to the exception: the opponent has not had a turn yet, and
nothing they can do on their first one reaches the 140-210 hp of our opener, so
there is no knockout to be promoted from and no danger to insure against. The
Meowth is worth more as the first half of Meowth -> Lillie's later than as a
body on the bench now.

THE BOARD, which is what this file actually pins:

    turn 1, we went first
    active  Tapu Bulu, no energy
    bench   EMPTY
    hand    Basic {G} x3, Meganium, Forest of Vitality, Lana's Aid, Meowth ex
    menu    3x ATTACH, 2x PLAY, END          -> the agent ends the turn

WHAT WAS LEARNED, and it now lives in the monitor as code rather than as a
comment: an invariant that flags correct play is not a weaker detector, it is a
broken one -- it buries the real finding it exists to surface. Three conditions
were added, each measured over 800 games:

    exception                         boards it explains
    ------------------------------------------------------------------
    our first turn going first        16 of 16 in the first run
    nothing playable at all           20 of 35 in the second
    only non-Pokemon plays offered    15 of 35 in the second

With all three encoded, END_EMPTY_BENCH reports ZERO violations over 800 games
and 102 234 decisions. The last-resort net holds. That zero is worth more than
the 16 it replaced, because the monitor's two self-tests show it can still fail.

So these tests guard the EXCEPTION. If someone reads the invariant, decides the
agent should always fill its bench, and deletes `_ft_hold_lone_meowth`, this file
goes red and explains why the obvious fix is wrong.
"""

import copy
import json
import sys
from pathlib import Path

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


def _chosen_types(board):
    import selfplay as sp
    mod = sp.load_agent(str(ROOT / "main.py"), "empty_bench_exception")
    sp._reset_si_aplica(mod)
    obs = board["observation"]
    choice = mod.agent(copy.deepcopy(obs))
    options = obs["select"]["option"]
    return [options[i].get("type") for i in choice]


def test_the_board_is_our_first_turn_having_gone_first():
    """The premise of the exception, on the board itself."""
    current = _board()["observation"]["current"]
    assert current["turn"] == 1
    assert current["firstPlayer"] == current["yourIndex"], "we went first"


def test_the_bench_is_empty_and_a_basic_is_in_hand():
    """Without both of these the exception would never be reached."""
    mine = _mine(_board())
    assert [b for b in (mine.get("bench") or []) if b] == []
    basics = [card_table.get(c["id"]) for c in (mine.get("hand") or [])]
    basics = [cd for cd in basics
              if cd is not None
              and getattr(cd, "cardType", None) == CardType.POKEMON
              and getattr(cd, "basic", False)]
    assert [getattr(cd, "name", "?") for cd in basics] == ["Meowth ex"]


def test_the_menu_does_offer_a_play_so_ending_is_a_choice():
    """Ending here is deliberate, not forced -- which is the whole point."""
    kinds = [o.get("type") for o in _board()["observation"]["select"]["option"]]
    assert int(OptionType.END) in kinds
    assert kinds.count(int(OptionType.PLAY)) >= 1


def test_the_agent_keeps_the_meowth_and_ends_the_turn():
    """The behaviour under test, live against main.py.

    Going red here means somebody removed the first-turn exception. Before
    'fixing' that, read the top of this file: the empty bench cannot be punished
    on a turn the opponent has not had yet.
    """
    assert int(OptionType.END) in _chosen_types(_board())
