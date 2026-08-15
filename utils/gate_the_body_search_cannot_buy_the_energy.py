"""Self-play gate for `THE_BODY_SEARCH_DOES_NOT_UNBLOCK_AN_ENERGYLESS_TURN`.

THE READING (episode 93210930, step 116, turn 9 vs Festival Lead -- WON in spite
of this; the board is drawn out in
`tests/test_the_body_search_cannot_buy_the_energy.py`). Not one energy on our
side of the table and none in hand, so nothing of ours could attack whatever the
turn did. The turn's one Supporter went to Dawn -- which buys a Basic, a Stage 1
and a Stage 2, and no energy -- and the turn closed without attaching or
attacking. The Ultra Ball beside it was already worth 12400 against Dawn's 2680;
what stood between them was `_ub_cancel_no_surplus`, whose fodder count protects
a lone refill Supporter, i.e. protected the one card that could not answer the
question the board was asking.

THE ARMS ARE THE SAME TREE WITH THE FLAG REBOUND, loaded twice by
`selfplay.load_agent` so each arm gets its own `ptcg` package (a shared tree
measures exactly zero). The flag is read from inside its own module, so it is
set on THAT namespace -- reached through the function's `__globals__`, since
main.py re-exports the name by value:

    THE_BODY_SEARCH_DOES_NOT_UNBLOCK_AN_ENERGYLESS_TURN   ptcg/decision/ultra_ball.py

READ THE CORPUS FIRST. Over the 3 580 decisions of the frozen corpus this flips
ZERO, and over the local records exactly ONE -- the step it was written for. At
that exposure a winrate cannot resolve it and is not expected to: `--control`
is the row that says so out loud, playing the flag against ITSELF so its delta
is the noise floor at the same N. A candidate row smaller than the control row
is noise ([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]]).

Usage:
    python utils/gate_the_body_search_cannot_buy_the_energy.py --games 1000 \
        --opponent deck/real_opponents/festival_lead_1.csv
    python utils/gate_the_body_search_cannot_buy_the_energy.py --games 1000 \
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

FLAG = "THE_BODY_SEARCH_DOES_NOT_UNBLOCK_AN_ENERGYLESS_TURN"


def _ub_globals(mod):
    """The namespace of this arm's `ptcg/decision/ultra_ball.py`.

    main.py imports that module with a star import, so the NAME it re-exports is
    a copy and rebinding it there would change nothing: the predicate reads the
    flag from its own module. The function object carried across by the import
    still points at the module it was defined in, which is this arm's copy.
    """
    return mod._the_body_search_cannot_buy_the_energy.__globals__


def arm(name, rule):
    mod = sp.load_agent(_ROOT / "main.py", name)
    _ub_globals(mod)[FLAG] = rule
    return mod


def _reads(mod):
    return _ub_globals(mod)[FLAG]


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
