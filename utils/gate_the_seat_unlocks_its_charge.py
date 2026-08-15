"""Self-play gate for `PROMOTE_SEAT_UNLOCKS_ITS_CHARGE`, with its own control.

THE ARMS ARE THE SAME TREE WITH THE FLAG REBOUND, which is the only way to make
the rule the single difference between them: both arms are `main.py` as it
stands, loaded twice by `selfplay.load_agent` so each gets its own `ptcg`
package (a shared tree measures exactly zero -- see `load_agent_from_git`).

READ THE CENSUS FIRST. `utils/census_the_seat_unlocks_its_charge.py` measures
the board this rule is about at 0.00-0.27 firings per game depending on the
opposing list, and the noise floor of this harness is around half a point: at
that exposure a winrate cannot resolve the change and this gate is a HARM CHECK,
not the evidence. The evidence is the census plus the single golden-corpus flip.
`--control` is what says so out loud: it plays the flag against ITSELF, so its
delta is the noise floor at the same N and any candidate row smaller than that
row is noise ([[el-suelo-de-ruido-del-grupo-de-control-ya-es-cero]]).

Usage:
    python utils/gate_the_seat_unlocks_its_charge.py --games 1000 \
        --opponent deck/opponents/mega_lucario.csv
    python utils/gate_the_seat_unlocks_its_charge.py --games 1000 --control
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

FLAG = "PROMOTE_SEAT_UNLOCKS_ITS_CHARGE"


def arm(name, value):
    mod = sp.load_agent(_ROOT / "main.py", name)
    setattr(mod, FLAG, value)
    return mod


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent."""
    if candidate is base:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if getattr(base, FLAG):
        raise SystemExit("el brazo baseline NO esta neutralizado: nada que medir")
    if bool(getattr(candidate, FLAG)) is bool(control):
        raise SystemExit(
            f"el brazo candidato no esta como dice estar (control={bool(control)}, "
            f"lectura={getattr(candidate, FLAG)})")
    print(f"procedencia OK (candidato "
          f"{'NEUTRALIZADO: control' if control else 'con la lectura'}, "
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
    ap.add_argument("--games", type=int, default=1000)
    ap.add_argument("--progress", type=int, default=500)
    ap.add_argument("--opponent", default=None)
    ap.add_argument("--control", action="store_true",
                    help="candidate arm NEUTRALISED: measures the noise floor")
    args = ap.parse_args(argv)

    candidate = arm("arm_candidate", not args.control)
    base = arm("arm_base", False)
    provenance(candidate, base, args.control)

    # THE OPPOSING SEAT IS THE SAME AGENT WITH THE OTHER DECK, and the two arms
    # play THE SAME SEEDS. Paired that way the engine deals the same games to
    # both, so the control row comes out at exactly zero and any candidate row
    # that is not zero is the rule and nothing else
    # ([[el-suelo-de-ruido-del-grupo-de-control-ya-es-cero]]).
    their = sp.read_deck(_ROOT / args.opponent) if args.opponent else None
    seeds = list(range(1, args.games + 1))
    n = args.games

    def run(mod, label):
        stats = sp.torneo(mod, base, n, progress=args.progress or None,
                          deck_base=their, seeds=seeds)
        wins = stats["candidate"]
        print(f"  {label:10s} {wins:5d}/{n} = {100 * wins / n:6.2f}%", flush=True)
        return wins

    with_rule = run(candidate, "candidato")
    without = run(arm("arm_control", False), "baseline")
    delta, z, p = wilson_delta(with_rule, n, without, n)
    print(f"\n{'CONTROL' if args.control else 'CANDIDATO'} "
          f"({args.opponent or 'deck.csv'}, n={n}): "
          f"delta {100 * delta:+.2f} pp   z {z:+.2f}   p {p:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
