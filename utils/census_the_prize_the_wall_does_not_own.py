"""How often the wall archetype was vetoing a knockout that was not the wall's.

THE BOARD IT COMES FROM (`records/registro_017_pasos_123_hasta_125.json`,
steps 123 and 125, turn 17, episode 93232495 vs Crustle / Mega Kangaskhan ex --
LOST):

    US (4 prizes)                          THEM (3 prizes)
    active  Tapu Bulu 30/140, 2 units      active  Mega Kangaskhan ex 80/300,
    bench   Meganium, 2x Ogerpon ex,               no energy
            Fezandipiti ex, Meowth ex      bench   Crustle 150
    hand    Poke Pad, Night Stretcher, Ogerpon ex, Xerosic's Machinations
    discard six Basic Grass Energy         the turn's attachment: UNSPENT

Wood Hammer costs four units and does 220 flat; Wild Growth makes one Grass card
two units. The Tapu Bulu sat at 2 of 4, so ONE Grass out of that discard both
paid for the attack and knocked out a Mega ex worth THREE prizes. The turn
closed with the Night Stretcher in hand.

WHAT WAS DECIDING. `_score_night_stretcher_play` REPLACES its scenario list
against a wall archetype -- `_ESC_NS_CRUSTLE` instead of
`_ESC_NS_RECUPERACION`, not on top of it -- and every scenario that prices a
recovered energy by "does it take a prize today" lives in the list that is
replaced. So against a Crustle or Cornerstone list the card could never be
played for a lethal energy, whoever was standing in the active spot. See
`tests/test_the_prize_today_is_not_the_walls_to_veto.py` for the full argument,
including why the FETCH half of the same card already scored that Grass at 1400.

WHAT THIS COUNTS, per MAIN menu of ours in which the Night Stretcher scorer runs
under the wall flag:

    ns_scored   the scorer ran (a Night Stretcher was in hand on our menu)
    remate      ...and one of the `_ESC_NS_REMATE_HOY` scenarios FIRED: the
                recovery is a proven knockout on the body actually in front
    flip        ...and it STRICTLY beat the Crustle whitelist, so the card's
                score is different from what the old code gave it. This is the
                population: the boards where the change changes something
    played      ...and the agent then really played the Night Stretcher on that
                menu (the ordering could still outrank it)

NOT A CONTROL GROUP. `flip` is a decision that changed, not a game that was won:
the winrate question needs its own A/B with a `--control` arm at the same N
([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]]).
What this answers is the question that comes first -- how wide the window is.

⚠️ THE CRITERION, written before this file was run and not moved afterwards:
`flip` at or above **0.10 per game** against the Crustle lists. One board in ten
games. The bar is a tenth of the Dwebble census's because what is on the table
is not one prize on a dead turn: every `flip` is by construction a knockout the
agent was declining to take, and here that was three prizes.

Usage:
    python utils/census_the_prize_the_wall_does_not_own.py --games 200
    python utils/census_the_prize_the_wall_does_not_own.py --games 100 \
        --opponent deck/real_opponents/crustle_wall_3.csv
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "tests", _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp                                   # noqa: E402
from autopsy import play_recording                      # noqa: E402
from cg.api import OptionType, SelectContext            # noqa: E402

DEFAULT_OPPONENT = "deck/real_opponents/crustle_wall_1.csv"


def _instrument(agent, seen):
    """Wrap `_score_night_stretcher_play` in the AGENT'S OWN module and note,
    for every call under the wall flag, what each of the two ballots would have
    said.

    Nothing in the tree is modified and the agent runs the code it always runs:
    the wrapper resolves the two lists itself -- both are pure, over the same
    `_CtxNSPlay` -- and then delegates. The rebinding is on the module object
    `utils/selfplay.load_agent` returned and on nothing else: that instance
    carries its own `ptcg/` tree, so patching the ambient `main` would
    instrument a different agent from the one playing. It lands because the
    scorer reaches the option branches through `ScoringCtx`, which main.py
    repopulates from its own `globals()` on every menu.
    """
    original = agent._score_night_stretcher_play

    def wrapper(ctx):
        if ctx.op_is_crustle_deck or ctx.op_is_cornerstone_deck:
            w = agent._CtxNSPlay(ctx)
            whitelist, _ = agent._resolve_max(agent._ESC_NS_CRUSTLE, w)
            remate, _ = agent._resolve_max(agent._ESC_NS_REMATE_HOY, w)
            seen.append((remate > 0, remate > whitelist))
        return original(ctx)

    agent._score_night_stretcher_play = wrapper
    return original


def census_game(m, decisiones, seen):
    """The four counts over one game. `seen` is consumed as we walk the
    decisions: the scorer fires once per Night Stretcher per MAIN menu, in menu
    order, so the queue lines up with the menus that offered the card."""
    out = Counter()
    for d in decisiones:
        obs = d["obs"]
        select = obs.get("select") or {}
        if select.get("context") != int(SelectContext.MAIN):
            continue
        cur = obs["current"]
        yo = cur["players"][cur["yourIndex"]]
        hand = yo.get("hand") or []
        ns_options = [i for i, o in enumerate(select.get("option") or [])
                      if o.get("type") == int(OptionType.PLAY)
                      and o.get("index") is not None
                      and o["index"] < len(hand)
                      and hand[o["index"]]["id"] == m.Night_Stretcher]
        if not ns_options or not seen:
            continue
        fired, flipped = seen.pop(0)
        out['ns_scored'] += 1
        if not fired:
            continue
        out['remate'] += 1
        if not flipped:
            continue
        out['flip'] += 1
        if d["eleccion"] and d["eleccion"][0] in ns_options:
            out['played'] += 1
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--opponent", default=DEFAULT_OPPONENT)
    ap.add_argument("--progress", type=int, default=50)
    args = ap.parse_args(argv)

    from opponent_bot import OpponentBot

    agent = sp.load_agent(_ROOT / "main.py", "arm_census_wall_prize")
    own_deck = sp.read_deck()
    opponent_deck = sp.read_deck(_ROOT / args.opponent)

    seen = []
    _instrument(agent, seen)

    counts = Counter()
    board = Counter()
    for i in range(args.games):
        seen.clear()
        result, decisiones, _final = play_recording(
            agent, OpponentBot(), own_deck, opponent_deck, seat=i % 2)
        board[result] += 1
        counts.update(census_game(agent, decisiones, seen))
        if args.progress and (i + 1) % args.progress == 0:
            print(f"  ... {i + 1}/{args.games}", flush=True)

    n = args.games or 1
    print(f"\n{args.games} games against {Path(args.opponent).stem}: "
          f"{dict(board)}")
    print(f"  menus where the Night Stretcher was scored  {counts['ns_scored']:6d} "
          f"({counts['ns_scored'] / n:7.2f}/game)")
    print(f"  ...and a REMATE HOY scenario fired          {counts['remate']:6d} "
          f"({counts['remate'] / n:7.2f}/game)")
    print(f"  ...and it BEAT the Crustle whitelist        {counts['flip']:6d} "
          f"({counts['flip'] / n:7.2f}/game)   <- THE WRITTEN CRITERION")
    print(f"  ...and the card was then really played      {counts['played']:6d} "
          f"({counts['played'] / n:7.2f}/game)")
    if counts['flip'] / n < 0.10:
        print("\nBELOW THE CRITERION (0.10/game, written before running this): "
              "the window is too narrow to justify the change on its own.")
    else:
        print("\nABOVE THE CRITERION: the window is real. The winrate still "
              "needs its own gate with a --control arm at the same N.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
