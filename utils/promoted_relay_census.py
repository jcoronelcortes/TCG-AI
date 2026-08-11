"""How often does "the prize is cashed by the body that outlasts" actually fire,
and what does it flip?

WHY A CENSUS AND NOT A WINRATE. The population this rule lives in was already
counted once, in `tests/test_the_reply_comes_from_their_bench.py`: over 2485
mirror decisions, "we take the knockout AND the promoted body replies AND that
closes their count AND a retreat is on the menu AND a surviving relay had the
same knockout" was TWO boards. A rule that fires in a fraction of a percent of
decisions has a ceiling of effect far below the noise floor of the self-play
gate (see the project's own measurement: a matchup delta of +-2-4 points in one
run is noise, and the Wilson interval understates the variance against a bot).
Asking the gate for a verdict there repeats an error the project has already
paid for twice.

So this tool asks the two questions the gate CAN answer:

  * FREQUENCY -- in how many decisions does the new reading change the retreat's
    score at all? That number is the ceiling of any effect, good or bad.
  * COLLATERAL DAMAGE -- of those, how many change the agent's CHOICE, and on
    what boards? A change that is surgical shows up as a tiny flip count with
    every flip legible.

HOW THE TWO ARMS ARE BUILT. Both live in ONE process: the same agent is asked
twice per observation, the second time with the change neutralised at its two
seams -- `_promoted_lethal_reply` forced to 0 (the reply comes off their active
again) and `_relay_reading` blind to `reachable_grass` (the relay is read at the
energy it already carries). That is exactly the pair of readings this change
adds, and nothing else differs, so no tree isolation is needed and no unrelated
edit in the working tree can contaminate the comparison.

Usage:
    python utils/promoted_relay_census.py --games 200
    python utils/promoted_relay_census.py --games 400 --opponents deck/real_opponents
"""

import argparse
import copy
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402


class Neutralised:
    """Context manager: the agent with the two new readings switched off."""

    def __init__(self, agent_module):
        # `sp.load_agent` restores `sys.modules` after loading, so the agent's
        # own `ptcg` tree is NOT reachable by name -- reach it through the
        # objects the agent actually holds. `score_option` lives in
        # ptcg/turn/scoring.py, whose globals bind the retreat module; the
        # retreat module's imported functions carry ptcg/calc/damage.py's
        # globals, and patching that dict is what `_relay_reading`'s callers
        # resolve against.
        self.retreat = agent_module.score_option.__globals__['retreat']
        self.damage = self.retreat._bench_finisher_upgrade.__globals__

    def __enter__(self):
        self._plr = self.retreat._promoted_lethal_reply
        self._rr = self.damage['_relay_reading']
        self.retreat._promoted_lethal_reply = lambda *a, **k: 0

        def blind(bp, target, bench_count, retreat_grass_after,
                  reachable_grass=None):
            return self._rr(bp, target, bench_count, retreat_grass_after, None)

        self.damage['_relay_reading'] = blind
        return self

    def __exit__(self, *exc):
        self.retreat._promoted_lethal_reply = self._plr
        self.damage['_relay_reading'] = self._rr
        return False


def census_game(agent, opponent, deck0, deck1, our_seat, max_steps=3000):
    from cg import game

    sp._reset_si_aplica(agent)
    obs, sd = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError(f"battle_start failed: {sd.errorType}")
    decisions, flips, steps = 0, [], 0
    while obs["current"]["result"] == -1 and steps < max_steps:
        seat = obs["current"]["yourIndex"]
        if seat == our_seat:
            choice = agent.agent(obs)
            decisions += 1
            with Neutralised(agent):
                before = agent.agent(copy.deepcopy(obs))
            if list(before) != list(choice):
                sel = obs.get("select") or {}
                flips.append({
                    "step": steps, "turn": obs["current"]["turn"],
                    "context": sel.get("context"),
                    "without": list(before), "with": list(choice),
                    "options": sel.get("option"),
                })
        else:
            choice = opponent.agent(obs)
        obs = game.battle_select(choice)
        steps += 1
    return decisions, flips


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--opponents", default="deck/real_opponents")
    ap.add_argument("--progress", type=int, default=20)
    args = ap.parse_args(argv)

    from opponent_bot import OpponentBot

    deck = sp.read_deck()
    # `pesos.csv` and friends are manifests, not decks: a deck file is 60 lines
    # of card ids and `read_deck` says so by raising on anything else.
    decks = []
    for _p in sorted((_ROOT / args.opponents).glob("*.csv")):
        try:
            sp.read_deck(_p)
        except (ValueError, IndexError):
            continue
        decks.append(_p)
    if not decks:
        print(f"no opposing decks in {args.opponents}")
        return 1
    agent = sp.load_agent(str(_ROOT / "main.py"), "census")
    bot = OpponentBot()

    total_dec, all_flips, played = 0, [], 0
    for i in range(args.games):
        path = decks[i % len(decks)]
        seat = i % 2
        their = sp.read_deck(path)
        d0, d1 = (deck, their) if seat == 0 else (their, deck)
        try:
            dec, flips = census_game(agent, bot, d0, d1, seat)
        except Exception as exc:            # a forfeit is not a measurement
            print(f"  game #{i} ({path.name}): {type(exc).__name__}: {exc}")
            continue
        total_dec += dec
        played += 1
        for f in flips:
            f["deck"] = path.name
        all_flips += flips
        if args.progress and (i + 1) % args.progress == 0:
            print(f"  ... {i+1}/{args.games}  decisions={total_dec} "
                  f"flips={len(all_flips)}")

    print(f"\nGames played: {played}/{args.games} over {len(decks)} decks")
    print(f"Our decisions: {total_dec}")
    pct = 100.0 * len(all_flips) / max(1, total_dec)
    print(f"FLIPS caused by the change: {len(all_flips)}  ({pct:.3f}% of decisions)")
    by_deck = {}
    for f in all_flips:
        by_deck[f["deck"]] = by_deck.get(f["deck"], 0) + 1
    for name, n in sorted(by_deck.items(), key=lambda kv: -kv[1]):
        print(f"  {name}: {n}")
    for f in all_flips[:15]:
        opts = f["options"] or []
        print(f"  turn {f['turn']} ctx={f['context']} {f['deck']}: "
              f"{f['without']} -> {f['with']}  "
              f"({[o.get('type') for o in opts]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
