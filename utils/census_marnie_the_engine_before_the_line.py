"""How often the Marnie gust ladder actually changes a decision.

THE BOARD IT COMES FROM (`registro_008` step 110, episode 93525290, turn 8 vs
Marnie's Grimmsnarl ex, LOST; drawn out in full in
`tests/test_marnie_the_engine_before_the_line.py`): Boss's Orders already down,
their bench holding a charged Morgrem and a Munkidori, and OUR bench holding a
Teal Mask Ogerpon ex on four Grass -- which one-shots a 320 HP Grimmsnarl ex
through its Grass weakness. The agent gusted the Morgrem, cut a line that was
rebuilt the next turn, and lost to the Froslass/Munkidori drip it never touched.

WHAT IS BEING COUNTED. The candidate arm drives the game; a NEUTRALISED copy of
the same tree (`MARNIE_ENGINE_BEFORE_THE_LINE = False`) is asked for its own
choice on the same observation, exactly as `utils/shadow.py` does, so both see
the identical stream of frames and their tracking evolves together. Per one of
OUR decisions:

    ours        decisions the agent took (the denominator)
    marnie      ...taken with `AGENT_STATE.op_is_marnie_deck` up -- the only
                place the reading lives
    gust        ...and the menu is a Boss's Orders TARGET select, which is the
                only menu either half of the reading can move
    flip        ...where the neutralised copy would have played something ELSE.
                This is the population: the boards where the rule changes a
                decision at all
    engine      ...and the flip is exactly this rule's sentence: the baseline
                aims at the Marnie LINE and the candidate at the
                Munkidori/Froslass/Snorunt engine. A flip that is not is a
                knock-on (a turn that goes differently after a target it did not
                take), and worth telling apart

THE LEAKAGE HALF is the second run, against a list that is not Marnie's. The
whole reading is gated on `op_is_marnie_deck`, so the honest number there is
ZERO and anything else is a rule reaching past its matchup.

NOT A CONTROL GROUP. `flip` is a decision that changed, not a game that was won:
the winrate question has its own two-arm gate with a `--control` row at the same
N (`utils/gate_marnie_the_engine_before_the_line.py`), and against this deck the
noise floor is ~1.5 points, so the census is the number that says whether there
was anything to measure in the first place.

⚠️ THE CRITERION, written before this file was run and not moved afterwards:
`flip` at or above **0.02 per game** against the Marnie lists, and **0.00 per
game** on the list that is not Marnie's. The prior that says the bar is the
right order of magnitude and is not drawn around a number already seen: the
reading needs three things to coincide on one turn -- the matchup, a Boss's
Orders being played, and a charged reserve on our bench -- and the frozen corpus
flips 1 decision in 3 580, while BOTH local Marnie records flip their gust.
A rate far ABOVE this bar would be the alarming answer, not the good one: it
would mean the gate is measuring something wider than the sentence.

WHAT IT MEASURED (16 agosto 2026, n=300 per row):

    vs marnie_grimmsnarl   36 379 decisiones, 206 menus de gusteo,
                           7 flips = 0.02/partida, y 6 de los 7 son la frase
                           exacta (linea -> motor). El septimo es un knock-on.
    vs crustle_wall_1      39 781 decisiones, 0 con el flag, 0 flips. FUGA CERO.

RE-MEASURED the same day, after the rung was given to the JAM chain as well
(`_ADJUST_GUST_NUISANCE`, together with the bracket that keeps a bigger prize
above it). The reading used to hold only while our active happened to be able to
attack, because that is what decides which chain resolves the menu; now it holds
on both, and the exposure roughly doubled:

    vs marnie_grimmsnarl   36 673 decisiones, 201 menus de gusteo,
                           11 flips = 0.04/partida, y 10 de los 11 son la frase
                           exacta (antes 6 de 7).
    vs crustle_wall_1      39 840 decisiones, 0 con el flag, 0 flips. FUGA CERO.

Not a strict A/B of the jam half alone -- the two runs are different games, not
the same seeds with one rung moved -- so read the doubling as an order of
magnitude and not as a delta. What it does settle is that the jam chain was
never a rare corner of this matchup: it was carrying about half of it.

...and the three complete Marnie games in `records/marnie/` flip NOTHING across
their 296 decisions, which is the same answer from the other side: the three
conditions rarely coincide. At 0.02 flips a game the winrate cannot resolve this
reading -- the gate's own control row is the proof, not an excuse -- so what
justifies the rule is the census and the two records it is written from.

Usage:
    python utils/census_marnie_the_engine_before_the_line.py --games 200
    python utils/census_marnie_the_engine_before_the_line.py --games 200 \
        --opponent deck/real_opponents/marnie_grimmsnarl_3.csv
    python utils/census_marnie_the_engine_before_the_line.py --games 200 \
        --opponent deck/real_opponents/crustle_wall_1.csv   # the leakage half
"""

import argparse
import copy
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "tests", _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp                                          # noqa: E402
from cg.api import AreaType, OptionType, SelectContext          # noqa: E402
from ptcg.cards.ids import (MARNIE_ENGINE_GUST_RANK,            # noqa: E402
                            MARNIE_LINE_IDS)
from gate_marnie_the_engine_before_the_line import arm          # noqa: E402

DEFAULT_OPPONENT = "deck/opponents/marnie_grimmsnarl.csv"


def _is_gust_menu(obs):
    """Is this the TARGET select of a Boss's Orders already on the table?

    The menu is bodies of THEIR bench, so it is recognised by its shape and not
    by a card id: `SWITCH` context, options of type CARD over `AreaType.BENCH`
    belonging to the other seat.
    """
    sel = obs.get("select") or {}
    if sel.get("context") != int(SelectContext.SWITCH):
        return False
    options = sel.get("option") or []
    if not options:
        return False
    mine = obs["current"]["yourIndex"]
    return all(o.get("type") == int(OptionType.CARD)
               and o.get("area") == int(AreaType.BENCH)
               and o.get("playerIndex") == 1 - mine
               for o in options)


def _target_id(obs, choice):
    """The card id `choice` drags out of their bench, or 0."""
    if not choice:
        return 0
    sel = obs.get("select") or {}
    options = sel.get("option") or []
    if choice[0] >= len(options):
        return 0
    mine = obs["current"]["yourIndex"]
    bench = obs["current"]["players"][1 - mine]["bench"] or []
    index = options[choice[0]].get("index")
    if index is None or index >= len(bench) or bench[index] is None:
        return 0
    return bench[index].get("id", 0)


def census_game(driver, shadow, deck0, deck1, counts, max_steps=3000):
    """One game driven by `driver`, with `shadow` asked on every frame."""
    from cg import game

    for mod in (driver, shadow):
        sp._reset_si_aplica(mod)
    obs, sd = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError(f"battle_start failed: {sd.errorType}")
    steps = 0
    while obs["current"]["result"] == -1 and steps < max_steps:
        choice = driver.agent(obs)
        mirror = shadow.agent(copy.deepcopy(obs))
        counts['ours'] += 1
        if driver.AGENT_STATE.op_is_marnie_deck:
            counts['marnie'] += 1
            if _is_gust_menu(obs):
                counts['gust'] += 1
        if list(mirror) != list(choice):
            counts['flip'] += 1
            if (_target_id(obs, mirror) in MARNIE_LINE_IDS
                    and _target_id(obs, choice) in MARNIE_ENGINE_GUST_RANK):
                counts['engine'] += 1
        obs = game.battle_select(choice)
        steps += 1
    return obs["current"]["result"]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--opponent", default=DEFAULT_OPPONENT)
    ap.add_argument("--progress", type=int, default=50)
    args = ap.parse_args(argv)

    driver = arm("census_candidate", True)
    shadow = arm("census_baseline", False)

    own = sp.read_deck()
    theirs = sp.read_deck(_ROOT / args.opponent)

    counts = Counter()
    for i in range(args.games):
        # The seat alternates so the census is not a reading of one half of the
        # game (docs/improving-the-agent.md: the seat is worth a point where the
        # winrate saturates and five in the contested matchups).
        d0, d1 = (own, theirs) if i % 2 == 0 else (theirs, own)
        census_game(driver, shadow, d0, d1, counts)
        if args.progress and (i + 1) % args.progress == 0:
            print(f"  ... {i + 1}/{args.games}", flush=True)

    n = args.games or 1
    print(f"\n{args.games} games against {Path(args.opponent).stem}")
    print(f"  our decisions                       {counts['ours']:6d} "
          f"({counts['ours'] / n:7.2f}/game)")
    print(f"  ...with op_is_marnie_deck up        {counts['marnie']:6d} "
          f"({counts['marnie'] / n:7.2f}/game)")
    print(f"  ...and the menu is a gust TARGET    {counts['gust']:6d} "
          f"({counts['gust'] / n:7.2f}/game)")
    print(f"  ...the neutral arm played OTHERWISE {counts['flip']:6d} "
          f"({counts['flip'] / n:7.2f}/game)   <- THE WRITTEN CRITERION")
    print(f"  ...and it was line -> engine        {counts['engine']:6d} "
          f"({counts['engine'] / n:7.2f}/game)")
    rate = counts['flip'] / n
    print("\n" + ("BELOW the criterion (0.02/game, written before running this):"
                  " there is not enough exposure for a winrate to resolve it."
                  if rate < 0.02 else
                  "AT or ABOVE the criterion. The winrate still needs its own "
                  "gate with a --control arm at the same N."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
