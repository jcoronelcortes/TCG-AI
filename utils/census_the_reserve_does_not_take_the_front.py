"""How often the anti-wall reserve is kept on the bench instead of taking the front.

THE BOARD IT COMES FROM (episode 93210034 vs Crustle / Mega Kangaskhan ex, WON;
drawn out in full in
`tests/test_the_reserve_against_the_wall_is_not_todays_attacker.py`), in one
line: step 58, turn 6 -- their Crustle on the BENCH and a Mega Kangaskhan ex
300/300 in front, our Teal Mask Ogerpon ex active with Myriad Leaf Shower at
150, and the agent retreated it (paying an energy card) to attack for 140 with
the Meganium, the only body of ours that can ever hurt that wall, leaving it in
front of a 200-damage attack that kills it.

WHAT IS BEING COUNTED. The candidate arm drives the game; a NEUTRALISED copy of
the same tree is asked for its own choice on the same observation, exactly as
`utils/shadow.py` does, so both see the identical stream of frames and their
tracking evolves together. Per one of OUR decisions:

    ours        decisions the agent took (the denominator)
    wall        ...taken while `op_is_crustle_deck` or `op_is_cornerstone_deck`
                is up -- the only place the guard lives
    flip        ...where the neutralised copy would have played something ELSE.
                This is the population: the boards where the rule changes a
                decision at all
    kept        ...and the flip is exactly this rule's sentence: the baseline
                RETREATS and the candidate does something else instead. A flip
                that is not is a knock-on (a turn that goes differently after
                the swap it did not make), and worth telling apart

THE LEAKAGE HALF is the second run, against a list with no wall in it. The guard
sits inside branches gated on those two flags, so the honest number there is
ZERO and anything else is a rule reaching past its matchup.

NOT A CONTROL GROUP. `flip` is a decision that changed, not a game that was won:
the winrate question has its own two-arm gate with a `--control` row at the same
N (`utils/gate_the_reserve_does_not_take_the_front.py`).

⚠️ THE CRITERION, written before this file was run and not moved afterwards:
`flip` at or above **0.05 per game** against the Crustle lists -- one board in
twenty games -- and **0.00 per game** on the list that carries no wall. The
prior that says the bar is the right order of magnitude, and not a bar drawn
around a number already seen: the frozen corpus flips 2 decisions across its 18
`crustle_wall` records, which is 0.11 a record, and both of them inside those
records.

Usage:
    python utils/census_the_reserve_does_not_take_the_front.py --games 200
    python utils/census_the_reserve_does_not_take_the_front.py --games 200 \
        --opponent deck/real_opponents/crustle_wall_4.csv
    python utils/census_the_reserve_does_not_take_the_front.py --games 200 \
        --opponent deck/real_opponents/marnie_grimmsnarl_1.csv   # the leakage half
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

import selfplay as sp                                    # noqa: E402
from cg.api import OptionType                            # noqa: E402
from gate_the_reserve_does_not_take_the_front import arm  # noqa: E402

DEFAULT_OPPONENT = "deck/real_opponents/crustle_wall_1.csv"


def _is_retreat(obs, choice):
    """Does `choice` retreat the active?"""
    if not choice:
        return False
    options = (obs.get("select") or {}).get("option") or []
    if choice[0] >= len(options):
        return False
    return options[choice[0]].get("type") == int(OptionType.RETREAT)


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
        state = driver.AGENT_STATE
        if state.op_is_crustle_deck or state.op_is_cornerstone_deck:
            counts['wall'] += 1
        if list(mirror) != list(choice):
            counts['flip'] += 1
            if _is_retreat(obs, mirror) and not _is_retreat(obs, choice):
                counts['kept'] += 1
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
    print(f"  our decisions                      {counts['ours']:6d} "
          f"({counts['ours'] / n:7.2f}/game)")
    print(f"  ...under the wall flags            {counts['wall']:6d} "
          f"({counts['wall'] / n:7.2f}/game)")
    print(f"  ...the neutral arm played OTHERWISE{counts['flip']:6d} "
          f"({counts['flip'] / n:7.2f}/game)   <- THE WRITTEN CRITERION")
    print(f"  ...and it was a RETREAT we did not {counts['kept']:6d} "
          f"({counts['kept'] / n:7.2f}/game)")
    rate = counts['flip'] / n
    print("\n" + ("BELOW the criterion (0.05/game, written before running this)."
                  if rate < 0.05 else
                  "ABOVE the criterion. The winrate still needs its own gate "
                  "with a --control arm at the same N."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
