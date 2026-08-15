"""Self-play gate for `THE_REFILL_BUYS_THE_WAVE`.

THE READING (episode 93378353, step 61, turn 6 vs Festival Lead -- LOST; the
board is drawn out in `tests/test_the_refill_buys_the_wave.py`). Their Festival
Grounds on the field, which arms OUR Dipplin too: Do the Wave, twice, and every
body they own is 100 HP or less. The Dipplin sat on our bench at zero energy
with no Grass in hand, and the turn evolved it into a Hydrapple ex that could
neither attack nor even use Ripening Charge that turn. What the hand DID hold
was Lillie's Determination with the Supporter slot free -- eight cards at six
prizes -- which is exactly the Grass and the bodies the wave was missing.

THE ARMS ARE THE SAME TREE WITH THE FLAG REBOUND, loaded twice by
`selfplay.load_agent` so each arm gets its own `ptcg` package (a shared tree
measures exactly zero). The flag is read inside `agent()`, so main.py's own
namespace is where it has to be set -- the copy the star import made is the one
the block reads.

READ THE CENSUS FIRST. `utils/census_the_refill_buys_the_wave.py` says how
often this is even asked, and the answer is "rarely, and only on the list that
brings the stadium". The wall is the one main.py names on
`switch_off_festival_lead`: the generic OpponentBot cannot pilot Festival Lead,
so most of these games never build the board. `--control` is the row that says
what the noise floor is at the same N, by playing the flag against ITSELF; a
candidate row smaller than the control row is not a reading
([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]]).

Usage:
    python utils/gate_the_refill_buys_the_wave.py --games 1000 \
        --opponent deck/real_opponents/festival_lead_1.csv
    python utils/gate_the_refill_buys_the_wave.py --games 1000 \
        --opponent deck/real_opponents/festival_lead_1.csv --control
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

FLAG = "THE_REFILL_BUYS_THE_WAVE"


def arm(name, rule):
    """One arm of the comparison, with the flag set on the namespace that reads it.

    The block guarded by this flag lives INSIDE `agent()`, so the namespace is
    main.py's own -- not `ptcg.cards.ids`, where the constant is declared. The
    star import made main a copy at load time and the copy is what runs.
    """
    mod = sp.load_agent(_ROOT / "main.py", name)
    setattr(mod, FLAG, rule)
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
    ap.add_argument("--progress", type=int, default=250)
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
    if args.control:
        print("Esta es la fila de CONTROL: el suelo de ruido a esta N. "
              "Una fila de candidato menor que ella no es una lectura.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
