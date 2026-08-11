"""Two-arm gate for "the prize is cashed by the body that outlasts", isolated
to THAT change and nothing else in the working tree.

WHY NOT `selfplay.py --base HEAD`. Because the baseline it exports is the git
ref, and the working tree normally carries other work in progress: the delta
then answers "everything uncommitted", not "this rule". Here the baseline is
built from the SAME tree as the candidate, with only the change's two seams
switched off:

    _promoted_lethal_reply -> 0   the reply comes off their ACTIVE again, and
                                  the body they promote is invisible
    _relay_reading blind to        the benched relay is read at the energy it
    `reachable_grass`              already carries, not at what the turn can
                                   still put on it

Everything else -- both trees, both decks, both simulators -- is identical, so
the difference between the arms is the rule.

Read `utils/promoted_relay_census.py` FIRST. It counts how often the change
touches a decision at all, and that number is the ceiling of any effect: if the
event is rare enough, this gate cannot resolve it however many games it plays,
and the honest report is the census plus a clean corpus, not a winrate.

Usage:
    python utils/gate_promoted_relay.py --games 1200
    python utils/gate_promoted_relay.py --games 1200 --opponent deck/real_opponents/mega_starmie_1.csv
    python utils/gate_promoted_relay.py --games 1200 --control   # both arms neutralised
"""

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402


def neutralise(agent_module):
    """Switch the change off in `agent_module`, permanently, in place.

    `sp.load_agent` restores `sys.modules` after loading, so the agent's own
    `ptcg` tree is not reachable by name -- it is reached through the objects
    the agent holds. Each arm has its OWN module objects (that is the whole
    point of `load_agent`), so patching one does not touch the other.
    """
    retreat = agent_module.score_option.__globals__['retreat']
    damage = retreat._bench_finisher_upgrade.__globals__
    original = damage['_relay_reading']

    retreat._promoted_lethal_reply = lambda *a, **k: 0
    damage['_relay_reading'] = (
        lambda bp, target, bench_count, grass_after, reachable_grass=None:
        original(bp, target, bench_count, grass_after, None))
    return agent_module


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=1200)
    ap.add_argument("--progress", type=int, default=100)
    ap.add_argument("--opponent", default=None,
                    help="csv of an opponent deck: matchup mode against the bot")
    ap.add_argument("--control", action="store_true",
                    help="neutralise BOTH arms: the noise floor of this very run")
    args = ap.parse_args(argv)

    main_py = _ROOT / "main.py"
    candidate = sp.load_agent(main_py, "arm_with")
    base = neutralise(sp.load_agent(main_py, "arm_without"))
    if args.control:
        neutralise(candidate)

    label_c = "with the rule" + (" (NEUTRALISED: control)" if args.control else "")
    label_b = "without the rule"

    if args.opponent:
        from opponent_bot import OpponentBot
        their = sp.read_deck(_ROOT / args.opponent)
        for agent, label in ((candidate, label_c), (base, label_b)):
            stats = sp.torneo(agent, OpponentBot(), args.games,
                              progress=args.progress or None, deck_base=their)
            print(sp.informe(stats, label, f"bot+{args.opponent}"))
            print()
        return 0

    stats = sp.torneo(candidate, base, args.games,
                      progress=args.progress or None)
    print(sp.informe(stats, label_c, label_b))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
