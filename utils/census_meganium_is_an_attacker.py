"""How often the turn's Grass changes body once Meganium is read as an attacker.

THE BOARDS IT COMES FROM (episode 93251328 vs Crustle / Mega Kangaskhan ex,
LOST). Both are drawn out in full in
`tests/test_meganium_is_an_attacker_not_the_doubler.py`; in one line each:

    step 92,  turn 14   ONE Grass in hand, a Meganium on our bench at 0 of 4,
                        two Crustle waiting on theirs -- and the Grass went to
                        Teal Dance over a SECOND Teal Mask Ogerpon ex, against
                        the wall whose ability switches our ex off.
    step 137, turn 20   six Grass in hand, one prize from winning, Tapu Bulu
                        just knocked out -- and the turn's attachment went to an
                        APPLIN benched that very turn instead of the Meganium.

WHAT IS BEING COUNTED. The candidate arm drives the game; a NEUTRALISED copy of
the same tree is asked for its own choice on the same observation, exactly as
`utils/shadow.py` does, so both see the identical stream of frames and their
tracking evolves together. Per one of OUR decisions:

    ours        decisions the agent took (the denominator)
    wall        ...taken while `op_is_crustle_deck` is up
    flip        ...where the neutralised copy would have played something ELSE.
                This is the population: the boards where the reading changes a
                decision at all
    to_meganium ...and the candidate's choice lands the energy ON the Meganium.
                A flip that does not is a knock-on (the demoted dance freeing an
                option that outranks it), and worth telling apart

THE LEAKAGE HALF is the second run, against a list with no Crustle in it. Both
readings are inside `if AGENT_STATE.op_is_crustle_deck`, so the honest number
there is ZERO and anything else is a rule reaching past its matchup.

NOT A CONTROL GROUP. `flip` is a decision that changed, not a game that was won:
the winrate question has its own two-arm gate with a `--control` row at the same
N (`utils/gate_meganium_is_an_attacker_not_the_doubler.py`).

⚠️ THE CRITERION, written before this file was run and not moved afterwards:
`flip` at or above **0.20 per game** against the Crustle lists -- one board in
five games -- and **0.00 per game** on the list that carries no Crustle. The
prior that says the bar is the right order of magnitude, and not a bar drawn
around a number already seen: the frozen corpus flips 13 decisions across its 18
`crustle_wall` records, which is 0.72 a game, and every one of them inside those
records.

Usage:
    python utils/census_meganium_is_an_attacker.py --games 200
    python utils/census_meganium_is_an_attacker.py --games 200 \
        --opponent deck/real_opponents/crustle_wall_4.csv
    python utils/census_meganium_is_an_attacker.py --games 200 \
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

import selfplay as sp                                   # noqa: E402
from cg.api import AreaType, OptionType                 # noqa: E402
from gate_meganium_is_an_attacker_not_the_doubler import arm  # noqa: E402

DEFAULT_OPPONENT = "deck/real_opponents/crustle_wall_1.csv"


def _lands_on_meganium(m, obs, choice):
    """Does `choice` put energy on a Meganium of ours (attachment or ability)?"""
    if not choice:
        return False
    select = obs.get("select") or {}
    options = select.get("option") or []
    if choice[0] >= len(options):
        return False
    opt = options[choice[0]]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    if opt.get("type") != int(OptionType.ATTACH):
        return False
    area, index = opt.get("inPlayArea"), opt.get("inPlayIndex", 0)
    body = (mine["active"][0] if area == int(AreaType.ACTIVE)
            else (mine["bench"] or [])[index] if index < len(mine["bench"] or [])
            else None)
    return bool(body) and body["id"] == m.Meganium


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
        yi = obs["current"]["yourIndex"]
        choice = driver.agent(obs)
        mirror = shadow.agent(copy.deepcopy(obs))
        counts['ours'] += 1
        if driver.AGENT_STATE.op_is_crustle_deck:
            counts['wall'] += 1
        if list(mirror) != list(choice):
            counts['flip'] += 1
            if _lands_on_meganium(driver, obs, choice):
                counts['to_meganium'] += 1
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

    driver = arm("census_candidate", True, True)
    shadow = arm("census_baseline", False, False)

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
    print(f"  ...under the Crustle flag          {counts['wall']:6d} "
          f"({counts['wall'] / n:7.2f}/game)")
    print(f"  ...the neutral arm played OTHERWISE{counts['flip']:6d} "
          f"({counts['flip'] / n:7.2f}/game)   <- THE WRITTEN CRITERION")
    print(f"  ...and the energy went to Meganium {counts['to_meganium']:6d} "
          f"({counts['to_meganium'] / n:7.2f}/game)")
    rate = counts['flip'] / n
    print("\n" + ("BELOW the criterion (0.20/game, written before running this)."
                  if rate < 0.20 else
                  "ABOVE the criterion. The winrate still needs its own gate "
                  "with a --control arm at the same N."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
