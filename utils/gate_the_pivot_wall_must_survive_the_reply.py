"""Self-play gate for `THE_PIVOT_WALL_MUST_SURVIVE_THE_REPLY` (episode 93430769).

THE READING. `_hydra_pivot_active` (main.py) retreats a fragile active to promote
a benched Hydrapple ex that knocks the opposing active out. Its whole
justification is the wall -- 330 HP is very hard to knock out -- and it never
asked whether the wall stands. On step 119 of that episode it retreated a
Meganium at 160/160 whose Solar Beam already took the prize for free, into a
Hydrapple ex that their Powerful Hand projects 420 against: a one-prize corpse
swapped for a two-prize one, with the knockout given up on top. The rule asks the
pivot for the thing that pays for it: a body their projected attack does NOT
knock out, unless the knockout it delivers already ends the game.

THE ARMS ARE THE SAME TREE WITH THE FLAG REBOUND, loaded twice by
`selfplay.load_agent` so each arm gets its own `ptcg` package (a shared tree
measures exactly zero). Unlike its sibling gates the flag is read in `main.py`
itself, so the arm's own module namespace is where it is set.

READ THE CORPUS FIRST. Over the 3 580 decisions of the frozen corpus this flips
ZERO, and one in `records/` -- the board it was written from. At that exposure the
winrate cannot resolve it on its own: `--control` is the row that says so out
loud, playing the flag against ITSELF so its delta is the noise floor at the same
N. A candidate row smaller than the control row is noise
([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]]).

Usage:
    python utils/gate_the_pivot_wall_must_survive_the_reply.py --games 1500 \
        --opponent deck/real_opponents_500/alakazam_1.csv
    python utils/gate_the_pivot_wall_must_survive_the_reply.py --games 1500 \
        --opponent deck/real_opponents_500/alakazam_1.csv --control
"""

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "utils")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import selfplay as sp  # noqa: E402
from gate_the_reserve_does_not_take_the_front import wilson_delta  # noqa: E402

FLAG = "THE_PIVOT_WALL_MUST_SURVIVE_THE_REPLY"


def arm(name, guard):
    """The flag is consumed inside `agent()`, so the arm's own namespace is it."""
    mod = sp.load_agent(_ROOT / "main.py", name)
    setattr(mod, FLAG, guard)
    return mod


def _reads(mod):
    return getattr(mod, FLAG)


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
