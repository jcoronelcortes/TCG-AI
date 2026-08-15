"""Self-play gate for the two readings of episode 93251328 (vs Crustle).

THE ARMS ARE THE SAME TREE WITH THE FLAGS REBOUND, which is the only way to make
the rules the single difference between them: both arms are the working tree,
loaded twice by `selfplay.load_agent` so each gets its own `ptcg` package (a
shared tree measures exactly zero -- see `load_agent_from_git`).

The two flags are constants imported BY VALUE into the module that reads them,
so rebinding them on `ptcg.cards.ids` would change nothing. Each one is set on
its consumer, reached through the `__globals__` of a function that arm exported
-- the arm's own namespace, not the ambient one.

    MEGANIUM_IS_OWED_THE_LAST_GRASS     ptcg/turn/options/ability.py
    MEGANIUM_OUTRANKS_THE_DIPPLIN_LINE  ptcg/turn/energy.py

`--half` NEUTRALISES ONE CONSUMER, it does not add a third behaviour. The two
readings answer different questions on different boards -- the reservation moves
a menu that has ONE Grass in hand, the ladder moves one that has six -- and the
combined row cannot say which of them paid. Running each half against the same
baseline at the same N is what separates them
([[las-mitades-anidadas-de-un-gate-delatan-el-suelo-de-ruido]]).

READ THE CORPUS FIRST. Over the 3 580 decisions of the frozen corpus the two
readings together flip THIRTEEN, every one of them inside a `crustle_wall`
record, and over the local records they flip the two the game accuses. At that
exposure the winrate needs help to resolve them: `--control` is what says so out
loud, playing the flags against THEMSELVES so its delta is the noise floor at
the same N, and any candidate row smaller than that row is noise.

Usage:
    python utils/gate_meganium_is_an_attacker_not_the_doubler.py --games 1500 \
        --opponent deck/real_opponents/crustle_wall_1.csv
    python utils/gate_meganium_is_an_attacker_not_the_doubler.py --games 1500 \
        --opponent deck/real_opponents/crustle_wall_1.csv --half reserve
    python utils/gate_meganium_is_an_attacker_not_the_doubler.py --games 1500 \
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

RESERVE = "MEGANIUM_IS_OWED_THE_LAST_GRASS"
LADDER = "MEGANIUM_OUTRANKS_THE_DIPPLIN_LINE"


def _ability_globals(mod):
    """The namespace of this arm's `ptcg/turn/options/ability.py`.

    main.py re-exports no function of that module, so it is reached through the
    dispatch table `ptcg.turn.scoring` builds: `score_option` closes over
    `_TABLE`, whose ABILITY entry IS this arm's `ability.score_play`.
    """
    from cg.api import OptionType
    table = mod.score_option.__globals__["_TABLE"]
    return table[OptionType.ABILITY].__globals__


def arm(name, reserve, ladder):
    mod = sp.load_agent(_ROOT / "main.py", name)
    _ability_globals(mod)[RESERVE] = reserve
    mod._energy_score_base_impl.__globals__[LADDER] = ladder
    return mod


def _reads(mod):
    return (_ability_globals(mod)[RESERVE],
            mod._energy_score_base_impl.__globals__[LADDER])


def provenance(candidate, base, control, half):
    """Refuse to measure two arms that are secretly the same agent."""
    if candidate is base:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if any(_reads(base)):
        raise SystemExit("el brazo baseline NO esta neutralizado: nada que medir")
    expected = {None: (True, True), "reserve": (True, False),
                "ladder": (False, True)}[half]
    if control:
        expected = (False, False)
    if _reads(candidate) != expected:
        raise SystemExit(
            f"el brazo candidato no esta como dice estar (control={bool(control)}, "
            f"half={half}, esperado={expected}, lectura={_reads(candidate)})")
    print(f"procedencia OK (candidato "
          f"{'NEUTRALIZADO: control' if control else 'half=' + (half or 'ambas')}, "
          f"baseline sin ellas)\n", flush=True)


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
    ap.add_argument("--half", choices=("reserve", "ladder"), default=None,
                    help="neutralise the OTHER consumer and measure one alone")
    ap.add_argument("--control", action="store_true",
                    help="candidate arm NEUTRALISED: measures the noise floor")
    args = ap.parse_args(argv)

    reserve = args.half in (None, "reserve")
    ladder = args.half in (None, "ladder")
    if args.control:
        reserve = ladder = False

    candidate = arm("arm_candidate", reserve, ladder)
    base = arm("arm_base", False, False)
    provenance(candidate, base, args.control, args.half)

    # THE OPPOSING SEAT IS THE SAME AGENT WITH THE OTHER DECK, and the two arms
    # play THE SAME SEEDS, so the control row comes out at zero and any
    # candidate row that is not zero is the rules and nothing else.
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

    with_rules, prizes_c = run(candidate, "candidato")
    without, prizes_b = run(arm("arm_control", False, False), "baseline")
    delta, z, p = wilson_delta(with_rules, n, without, n)
    print(f"\n{'CONTROL' if args.control else 'CANDIDATO ' + (args.half or 'ambas')} "
          f"({args.opponent or 'deck.csv'}, n={n}): "
          f"delta {100 * delta:+.2f} pp   z {z:+.2f}   p {p:.3f}   "
          f"premios {prizes_c - prizes_b:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
