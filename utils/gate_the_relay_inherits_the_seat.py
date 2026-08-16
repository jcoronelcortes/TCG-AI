"""Self-play gate for `THE_RELAY_INHERITS_THE_SEAT` (episode 93486866).

THE READING. With our active locked in the front spot -- it neither attacks this
turn nor can pay its way out -- the gust-target ladder runs in NUISANCE mode,
which prices every candidate by what it would cost the opponent to ESCAPE it. On
step 72 of that episode that answered a bare Munkidori: retreat cost one, no
energy, its attack unpayable. The body it left behind was a Marnie's Grimmsnarl
ex with FIVE energies, worth two prizes, that a benched Teal Mask Ogerpon ex
already knocked out for 540 -- and it scored -200, last of the four.

The trap was the mistake and it is the same mistake twice. A jam costs the
opponent a turn, which is only a currency if WE can spend the one it buys, and
our hand was two Meganium with nothing under them. Worse: by never letting their
knockout come it kept three charged Ogerpon ex stuck behind a 20 HP Tapu Bulu.
THEIR KNOCKOUT WAS THE ONLY KEY TO OUR OWN SEAT.

`the_relay_inherits_the_seat` reads the third knockout route -- they knock our
active out, we PROMOTE, the promoted body attacks what we gusted -- and among the
bodies that OPEN that seat and that our bench cashes from it, takes the one worth
the most prizes.

THE ARMS ARE THE SAME TREE WITH THE FLAG REBOUND, loaded twice by
`selfplay.load_agent` so each arm gets its own `ptcg` package (a shared tree
measures exactly zero). The flag is imported BY VALUE into its consumer, so it is
set on that consumer's namespace, reached through the rule itself:

    THE_RELAY_INHERITS_THE_SEAT    ptcg/decision/boss_orders.py

READ THE CENSUS FIRST. The state this rule needs is narrow -- a locked active, a
charged bench, a Boss's Orders in hand and a target menu on the same turn -- so
the winrate needs `--control` to say what the noise floor is at the same N. A
candidate row smaller than the control row is noise
([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]]).

WHAT IT HAS READ (15 August 2026, n=1500, marnie_grimmsnarl_1):

    candidato  1464/1500 = 97.60%   delta +0.27 pp   z +0.46   p 0.642
    CONTROL    1460/1500 = 97.33%   delta +0.00 pp EXACTLY

The control row is the clean zero a paired-seed control is supposed to be -- both
arms landed on the identical 1460 -- so the candidate does clear its own floor.
It is still FOUR GAMES IN 1500 at p 0.64 against a list the reference bot already
loses 97% of, which is the saturation this whole instrument family exists around.
Positive in sign, NOT significant, and not what keeps the change: the corpus flip
is exactly the board that found it, and the census flips are 9 of 11 the rule's
own sentence.

Usage:
    python utils/gate_the_relay_inherits_the_seat.py --games 1500 \
        --opponent deck/real_opponents/marnie_grimmsnarl_1.csv
    python utils/gate_the_relay_inherits_the_seat.py --games 1500 \
        --opponent deck/real_opponents/marnie_grimmsnarl_1.csv --control
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

FLAG = "THE_RELAY_INHERITS_THE_SEAT"
RULE = "the_relay_inherits_the_seat"


def _boss_globals(mod):
    """The namespace of this arm's `ptcg/decision/boss_orders.py`.

    main.py re-exports the rule LIST, and every rung of it is a closure built in
    that module, so its `__globals__` IS the namespace the flag has to be set on.
    Going through the rule (and not through `sys.modules`) is what guarantees the
    namespace reached belongs to THIS arm's package copy.
    """
    for rule in mod._RULES_GUST_NUISANCE:
        if rule.name == RULE:
            return rule.when.__globals__
    raise SystemExit(f"la regla {RULE} no esta en _RULES_GUST_NUISANCE")


def arm(name, relay):
    mod = sp.load_agent(_ROOT / "main.py", name)
    _boss_globals(mod)[FLAG] = relay
    return mod


def _reads(mod):
    return _boss_globals(mod)[FLAG]


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
    # play THE SAME SEEDS, so the control row comes out at zero and any candidate
    # row that is not zero is the rule and nothing else.
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
