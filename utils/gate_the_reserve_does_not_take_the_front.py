"""Self-play gate for `THE_RESERVE_DOES_NOT_TAKE_THE_FRONT` (episode 93210034).

THE READING. The two retreat branches that hand the front spot to the anti-wall
attacker (score 3400 in `ptcg/turn/options/retreat.py`) were guarded by the
ARCHETYPE plus "the active does not knock out". On step 58 of that episode both
were true with a Mega Kangaskhan ex 300/300 in front and the Crustle on their
BENCH: the agent retreated a Teal Mask Ogerpon ex that hits for 150, paid an
energy card, and attacked for 140 with the only body of ours that can ever hurt
the wall -- into 200 damage that kills it. The rule asks the swap for the one
thing that pays for it: MORE damage this turn than the body going down.

THE ARMS ARE THE SAME TREE WITH THE FLAG REBOUND, loaded twice by
`selfplay.load_agent` so each arm gets its own `ptcg` package (a shared tree
measures exactly zero). The flag is imported BY VALUE into its consumer, so it
is set on that consumer's namespace, reached through the dispatch table:

    THE_RESERVE_DOES_NOT_TAKE_THE_FRONT    ptcg/turn/options/retreat.py

READ THE CORPUS FIRST. Over the 3 580 decisions of the frozen corpus this flips
TWO, both inside `crustle_wall` records and both of the same class (an Ogerpon
ex that was already attacking, retreated for a body that hits for less). At that
exposure the winrate needs help to resolve it: `--control` is the row that says
so out loud, playing the flag against ITSELF so its delta is the noise floor at
the same N. A candidate row smaller than the control row is noise
([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]]).

Usage:
    python utils/gate_the_reserve_does_not_take_the_front.py --games 1500 \
        --opponent deck/real_opponents/crustle_wall_1.csv
    python utils/gate_the_reserve_does_not_take_the_front.py --games 1500 \
        --opponent deck/real_opponents/crustle_wall_1.csv --control
"""

import argparse
import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "utils")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import selfplay as sp  # noqa: E402

FLAG = "THE_RESERVE_DOES_NOT_TAKE_THE_FRONT"


def _retreat_globals(mod):
    """The namespace of this arm's `ptcg/turn/options/retreat.py`.

    main.py re-exports no function of that module, so it is reached through the
    dispatch table `ptcg.turn.scoring` builds: `score_option` closes over
    `_TABLE`, whose RETREAT entry IS this arm's `retreat.score_play`.
    """
    from cg.api import OptionType
    table = mod.score_option.__globals__["_TABLE"]
    return table[OptionType.RETREAT].__globals__


def arm(name, reserve):
    mod = sp.load_agent(_ROOT / "main.py", name)
    _retreat_globals(mod)[FLAG] = reserve
    return mod


def _reads(mod):
    return _retreat_globals(mod)[FLAG]


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent."""
    if candidate is base:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if _reads(base):
        raise SystemExit("el brazo baseline NO esta neutralizado: nada que medir")
    expected = not control
    if _reads(candidate) != expected:
        raise SystemExit(
            f"el brazo candidato no esta como dice estar (control={bool(control)}, "
            f"esperado={expected}, lectura={_reads(candidate)})")
    print(f"procedencia OK (candidato "
          f"{'NEUTRALIZADO: control' if control else 'con la regla'}, "
          f"baseline sin ella)\n", flush=True)


def wilson_delta(w1, n1, w2, n2):
    """Two-proportion z test. It ASSUMES independent Bernoulli, which the bot
    does not honour -- read the p it prints as an optimistic bound."""
    if not n1 or not n2:
        return 0.0, 0.0, 1.0
    p1, p2 = w1 / n1, w2 / n2
    p = (w1 + w2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) or 1e-9
    z = (p1 - p2) / se
    return p1 - p2, z, 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=1500)
    ap.add_argument("--progress", type=int, default=500)
    ap.add_argument("--opponent", default=None)
    ap.add_argument("--control", action="store_true",
                    help="candidate arm NEUTRALISED: measures the noise floor")
    args = ap.parse_args(argv)

    candidate = arm("arm_candidate", not args.control)
    base = arm("arm_base", False)
    provenance(candidate, base, args.control)

    # THE OPPOSING SEAT IS THE SAME AGENT WITH THE OTHER DECK, and the two arms
    # play THE SAME SEEDS, so the control row comes out at zero and any
    # candidate row that is not zero is the rule and nothing else.
    their = sp.read_deck(_ROOT / args.opponent) if args.opponent else None
    seeds = list(range(1, args.games + 1))
    n = args.games

    def run(mod, label):
        stats = sp.torneo(mod, base, n, progress=args.progress or None,
                          deck_base=their, seeds=seeds)
        wins = stats["candidate"]
        _pc, _pb, diff = sp.prizes_per_game(stats)
        print(f"  {label:10s} {wins:5d}/{n} = {100 * wins / n:6.2f}%"
              + (f"   premios {diff:+.3f}" if diff is not None else ""),
              flush=True)
        return wins, (diff or 0.0)

    with_rule, prizes_c = run(candidate, "candidato")
    without, prizes_b = run(arm("arm_control", False), "baseline")
    delta, z, p = wilson_delta(with_rule, n, without, n)
    print(f"\n{'CONTROL' if args.control else 'CANDIDATO'} "
          f"({args.opponent or 'deck.csv'}, n={n}): "
          f"delta {100 * delta:+.2f} pp   z {z:+.2f}   p {p:.3f}   "
          f"premios {prizes_c - prizes_b:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
