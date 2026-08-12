"""How often does "the last prize is cashed by a body that is still there"
actually fire, and what does it flip?

WHY A CENSUS AND NOT A WINRATE. The board this rule lives on is the rarest shape
the turn plan knows how to name: our attack takes the knockout, the body they
PROMOTE knocks our active out in reply, those prizes CLOSE their count, a retreat
is on the menu and a benched body takes the SAME knockout and outlasts that
reply. `TurnPlan.op_wins_after_ko` -- the first of those clauses -- was already
counted by `utils/promoted_reply_census.py`, and it is a fraction of a per cent
of decisions; this rule is a subset of that subset. A population that size has a
ceiling of effect far below the noise floor of the self-play gate, and asking the
gate for a verdict there repeats an error the project has already paid for twice
(see `TurnPlan.denial_saves_the_game`).

So this tool asks the two questions the gate CAN answer:

  * FREQUENCY -- in how many decisions does the rule set the retreat's score at
    all, and in how many does that retreat then WIN the menu? That is the
    ceiling of any effect, good or bad.
  * COLLATERAL DAMAGE -- of those, how many change the agent's CHOICE, and on
    which boards? A surgical change shows up as a tiny flip count with every
    flip legible.

HOW FREQUENCY IS COUNTED, and why it is not counted by differencing. 8860 is
this rule's own score and nothing else in the menu produces it, so a spy on
`score_option` answers "did it fire" exactly, on ONE pass of the agent, with no
second call and no state to perturb.

HOW THE TWO ARMS ARE BUILT, for the flips. Both live in ONE process: the same
agent is asked twice per observation, the second time with the rule neutralised
at its single seam. `_promoted_reply_damage` is imported into
`ptcg/turn/options/retreat.py` for this rule and for nothing else, so forcing it
to a number no body survives switches `_relay_saves_the_game` off and leaves
every other rule in the file -- `_relay_finisher_pivot` included, which reads its
reply through `_promoted_lethal_reply` -- exactly as it was.

THAT SECOND CALL HAS A NOISE FLOOR, and `--control` is what measures it: the
agent carries state across observations (card tracking, the open turn plan), so
asking it twice about the same board perturbs what it answers about the NEXT
one. Run with `--control` and the neutralisation becomes a no-op: every flip it
still reports is that noise and nothing else. Read the flip column of a real run
against that floor, never against zero.

MEASURED, 300 games over deck/real_opponents, both arms:

    the change   19 632 decisions   1 firing (0.005%), 0 of them won the menu
                                    15 flips (0.076%)
    --control    20 410 decisions   0 firings
                                     9 flips (0.044%)

Usage:
    python utils/relay_saves_the_game_census.py --games 200
    python utils/relay_saves_the_game_census.py --games 200 --control
    python utils/relay_saves_the_game_census.py --games 400 --opponents deck/real_opponents
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

# Bigger than any printed HP in the format: no benched body clears it, so
# `_bench_finisher_that_survives` finds no relay and the flag stays False.
_NO_BODY_SURVIVES = 10 ** 9

# The score `_relay_saves_the_game` hands the retreat, and nothing else in the
# menu produces it. See ptcg/turn/options/retreat.py.
_SCORE = 8860


def _retreat_module(agent_module):
    """`ptcg/turn/options/retreat.py` as the LOADED agent holds it.

    `sp.load_agent` restores `sys.modules` after loading, so the agent's own
    `ptcg` tree is not reachable by name -- reach it through the objects the
    agent actually holds. `score_option` lives in ptcg/turn/scoring.py, whose
    globals bind the retreat module. `_census_original` is what makes this work
    while the firing spy is installed: the spy's own globals are THIS file's.
    """
    fn = agent_module.score_option
    return getattr(fn, '_census_original', fn).__globals__['retreat']


class Neutralised:
    """Context manager: the agent with the new reading switched off."""

    def __init__(self, agent_module):
        self.retreat = _retreat_module(agent_module)

    def __enter__(self):
        self._prd = self.retreat._promoted_reply_damage
        self.retreat._promoted_reply_damage = \
            lambda *a, **k: _NO_BODY_SURVIVES
        return self

    def __exit__(self, *exc):
        self.retreat._promoted_reply_damage = self._prd
        return False


class NoNeutralisation:
    """`--control`: the same double call with NOTHING switched off, so every
    flip it reports is the state the second call perturbs."""

    def __init__(self, agent_module):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Firings:
    """Spy on `score_option`: did the rule set the retreat's score this turn?"""

    def __init__(self, agent_module):
        self.module = agent_module
        self.original = agent_module.score_option
        self.fired = False

    def install(self):
        def spy(tc, o, score):
            result = self.original(tc, o, score)
            if o.type == self.module.OptionType.RETREAT and result == _SCORE:
                self.fired = True
            return result

        spy._census_original = self.original
        self.module.score_option = spy
        return self

    def restore(self):
        self.module.score_option = self.original


def census_game(agent, opponent, deck0, deck1, our_seat, neutraliser,
                max_steps=3000):
    from cg import game

    sp._reset_si_aplica(agent)
    obs, sd = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError(f"battle_start failed: {sd.errorType}")
    spy = Firings(agent).install()
    decisions, firings, taken, flips, steps = 0, 0, 0, [], 0
    try:
        while obs["current"]["result"] == -1 and steps < max_steps:
            seat = obs["current"]["yourIndex"]
            if seat == our_seat:
                spy.fired = False
                choice = agent.agent(obs)
                decisions += 1
                if spy.fired:
                    firings += 1
                    sel = obs.get("select") or {}
                    options = sel.get("option") or []
                    if any(0 <= i < len(options)
                           and (options[i] or {}).get("type")
                           == int(agent.OptionType.RETREAT)
                           for i in choice):
                        taken += 1
                with neutraliser(agent):
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
    finally:
        spy.restore()
    return decisions, firings, taken, flips


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--opponents", default="deck/real_opponents")
    ap.add_argument("--progress", type=int, default=20)
    ap.add_argument("--control", action="store_true",
                    help="neutralise nothing: measures the noise floor of the "
                         "second call")
    args = ap.parse_args(argv)
    neutraliser = NoNeutralisation if args.control else Neutralised

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

    total_dec, total_fire, total_taken, all_flips, played = 0, 0, 0, [], 0
    for i in range(args.games):
        path = decks[i % len(decks)]
        seat = i % 2
        their = sp.read_deck(path)
        d0, d1 = (deck, their) if seat == 0 else (their, deck)
        try:
            dec, fire, taken, flips = census_game(agent, bot, d0, d1, seat,
                                                  neutraliser)
        except Exception as exc:            # a forfeit is not a measurement
            print(f"  game #{i} ({path.name}): {type(exc).__name__}: {exc}")
            continue
        total_dec += dec
        total_fire += fire
        total_taken += taken
        played += 1
        for f in flips:
            f["deck"] = path.name
        all_flips += flips
        if args.progress and (i + 1) % args.progress == 0:
            print(f"  ... {i+1}/{args.games}  decisions={total_dec} "
                  f"firings={total_fire} flips={len(all_flips)}")

    print(f"\nGames played: {played}/{args.games} over {len(decks)} decks")
    print(f"Our decisions: {total_dec}")
    fpct = 100.0 * total_fire / max(1, total_dec)
    print(f"FIRINGS (the rule scored the retreat): {total_fire}  "
          f"({fpct:.3f}% of decisions)")
    print(f"  ... and the retreat WON the menu: {total_taken}")
    pct = 100.0 * len(all_flips) / max(1, total_dec)
    label = "NOISE FLOOR (--control)" if args.control else "FLIPS caused by the change"
    print(f"{label}: {len(all_flips)}  ({pct:.3f}% of decisions)")
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
