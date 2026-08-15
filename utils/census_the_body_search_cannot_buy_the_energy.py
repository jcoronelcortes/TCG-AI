"""How often the turn's Supporter is taken away from a search that buys BODIES.

THE BOARD IT COMES FROM (episode 93210930 vs Festival Lead, WON; drawn out in
full in `tests/test_the_body_search_cannot_buy_the_energy.py`), in one line:
step 116, turn 9 -- not one energy on our whole board and none in hand, so
nothing of ours could attack; the turn's only Supporter went to Dawn, which
buys a Basic, a Stage 1 and a Stage 2 and no energy, and the turn closed with
nothing attached and nothing attacked. The Ultra Ball beside it (12400 against
Dawn's 2680) was vetoed by a fodder count that was protecting that same Dawn as
"the last refill".

WHAT IS BEING COUNTED. The candidate arm drives the game; a NEUTRALISED copy of
the same tree is asked for its own choice on the same observation, exactly as
`utils/shadow.py` does, so both see the identical stream of frames and their
tracking evolves together. Per one of OUR decisions:

    ours        decisions the agent took (the denominator)
    dry         ...taken with NO energy anywhere on our side of the table and
                none in hand: the population the rule can even look at
    flip        ...where the neutralised copy would have played something ELSE.
                These are the boards where the rule changes a decision at all
    bought      ...and the flip is exactly this rule's sentence: the baseline
                plays a Supporter of `POKEMON_SEARCH_SUPPORTER_IDS` and the
                candidate plays the ULTRA BALL instead. A flip that is not is a
                knock-on (a turn that goes differently after the swap), and
                worth telling apart

NOT A CONTROL GROUP. `flip` is a decision that changed, not a game that was won:
the winrate question has its own two-arm gate with a `--control` row at the same
N (`utils/gate_the_body_search_cannot_buy_the_energy.py`).

⚠️ THE CRITERION, written before this file was run and not moved afterwards:
`bought` at or above **0.01 per game** -- one board in a hundred games -- and
`bought == flip` or close to it, since a rule that only lifts a cost veto should
not be reshaping turns it never spoke about. The prior that says this is the
right order of magnitude and not a bar drawn around a number already seen: the
frozen corpus flips ZERO of its 3 580 decisions (50 games) and the local records
flip ONE across fourteen, so the honest expectation is a rare board, and the
question the census answers is whether "rare" means "sometimes" or "never".

A ZERO IS A RESULT, and it has a name in this project: a rule that never fires
is not kept for its winrate, it is kept -- or reverted -- on whether the value it
corrects was WRONG (see `politica-neutro-se-revierte-salvo-valor-ilegal`).

Usage:
    python utils/census_the_body_search_cannot_buy_the_energy.py --games 200
    python utils/census_the_body_search_cannot_buy_the_energy.py --games 200 \
        --opponent deck/real_opponents/marnie_grimmsnarl_1.csv
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

import selfplay as sp                                              # noqa: E402
from cg.api import OptionType                                      # noqa: E402
from gate_the_body_search_cannot_buy_the_energy import arm         # noqa: E402
from ptcg.cards.groups import POKEMON_SEARCH_SUPPORTER_IDS         # noqa: E402
from ptcg.cards.ids import Basic_Grass_Energy, Ultra_Ball          # noqa: E402

DEFAULT_OPPONENT = "deck/real_opponents/festival_lead_1.csv"


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _dry_board(obs):
    """No energy attached to anything of ours, and no Basic {G} in hand."""
    mine = _mine(obs)
    bodies = [p for p in (list(mine.get("active") or [])
                          + list(mine.get("bench") or [])) if p]
    if any(p.get("energies") for p in bodies):
        return False
    return not any(c.get("id") == Basic_Grass_Energy
                   for c in (mine.get("hand") or []))


def _played_card(obs, choice):
    """The id of the card a PLAY choice puts down, or None."""
    if not choice:
        return None
    options = (obs.get("select") or {}).get("option") or []
    if choice[0] >= len(options):
        return None
    opt = options[choice[0]]
    if opt.get("type") != int(OptionType.PLAY):
        return None
    hand = _mine(obs).get("hand") or []
    idx = opt.get("index")
    if idx is None or idx >= len(hand):
        return None
    return hand[idx].get("id")


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
        if _dry_board(obs):
            counts['dry'] += 1
        if list(mirror) != list(choice):
            counts['flip'] += 1
            if (_played_card(obs, mirror) in POKEMON_SEARCH_SUPPORTER_IDS
                    and _played_card(obs, choice) == Ultra_Ball):
                counts['bought'] += 1
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
        # game (docs/improving-the-agent.md).
        d0, d1 = (own, theirs) if i % 2 == 0 else (theirs, own)
        census_game(driver, shadow, d0, d1, counts)
        if args.progress and (i + 1) % args.progress == 0:
            print(f"  ... {i + 1}/{args.games}", flush=True)

    n = args.games or 1
    print(f"\n{args.games} games against {Path(args.opponent).stem}")
    print(f"  our decisions                       {counts['ours']:6d} "
          f"({counts['ours'] / n:7.2f}/game)")
    print(f"  ...with NO energy in play or hand   {counts['dry']:6d} "
          f"({counts['dry'] / n:7.2f}/game)")
    print(f"  ...the neutral arm played OTHERWISE {counts['flip']:6d} "
          f"({counts['flip'] / n:7.2f}/game)")
    print(f"  ...and it was the body search we did{counts['bought']:6d} "
          f"({counts['bought'] / n:7.2f}/game)   <- THE WRITTEN CRITERION")
    rate = counts['bought'] / n
    print("\n" + ("BELOW the criterion (0.01/game, written before running this): "
                  "the rule corrects a valuation that is wrong, not a frequent one."
                  if rate < 0.01 else
                  "ABOVE the criterion. The winrate still needs its own gate "
                  "with a --control arm at the same N."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
