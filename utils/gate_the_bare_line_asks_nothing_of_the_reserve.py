"""Self-play gate for "their BARE line is owed no reserve" (ep 93683313 p49, WON).

THE READING. `marnie_engine_first` asks whether a body on OUR BENCH already
covers a Marnie's Grimmsnarl ex, and while the answer is no the engine ladder
stands down so `ex_preevo_takes_priority` can keep its 19500. But that rung
demands a CHARGED pre-evolution (`c.energy >= 1`): with their whole line at zero
energy it never fires, there is no 19500 to protect, and the engine was yielding
the gust to a premise nobody had made. On the record the gust took a BARE Morgrem
(9600 of plain stage tier) over a Munkidori carrying a Darkness (6450).
`_marnie_line_is_bare` is the second way into the same field, read off the SAME
projection as the reserve question so the two halves cannot drift apart.

ONE SWITCH, AND IT IS NOT THE PARENT'S.
`MARNIE_ENGINE_BARE_LINE_NEEDS_NO_RESERVE` neutralises ONLY this half: the
reserve question, the engine-vs-line reading it gates and the energy split inside
the ladder each keep their own file and their own switch
(`gate_marnie_the_engine_before_the_line.py` and the two censuses). An arm that
moved more than one of them would not be measuring this sentence.

THE ARMS ARE THE SAME TREE WITH THE FLAG REBOUND, loaded twice by
`selfplay.load_agent` so each gets its own `ptcg` package (a shared tree measures
exactly zero). The constant is imported BY VALUE into the module that reads it,
so it is set on that module's namespace -- reached through the `__globals__` of
`_ctx_gust_target`, which main.py re-exports -- and not on `ptcg.cards.ids`.

READ THE EXPOSURE FIRST.
`utils/census_the_bare_line_asks_nothing_of_the_reserve.py` measured 0.03 flips
per game at n=200 (46 bare-line gust menus in 200 games, 5 of them decided
differently) and ZERO leakage outside the matchup. A reading that moves three
decisions in a hundred games cannot be resolved by a winrate at any N this
harness can afford, so `--control` plays the flag against ITSELF and its delta is
the noise floor at the same N: any candidate row smaller than that row is noise,
not a result. Vs this deck that floor has been measured at ~1.5 points
([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos]]).

WHAT IT MEASURED (16 agosto 2026, deck/opponents/marnie_grimmsnarl.csv, n=4000):

    CANDIDATO   3828/4000 = 95.70%   vs baseline 3828 = 95.70%
                delta +0.00 pp   z +0.00   p 1.000   premios +0.002
    CONTROL     delta +0.00 pp   z +0.00   p 1.000   premios +0.000

READ THE CONTROL ROW FIRST. It is EXACTLY zero -- same seeds, same tree, the flag
against itself -- so this harness has no noise floor of its own and the
candidate's numbers are the rules and nothing else. What the rules did is move
the PRIZE differential by +0.002 a game and not one game's winner: the census
says the reading flips ~0.03 decisions a game, so at this N it changed on the
order of a hundred boards and none of them changed who won. The row neither
supports the rule nor condemns it -- it says the winrate cannot resolve a reading
this narrow, which was written down before the gate ran.

WHICH IS THE HONEST STATE OF THIS READING, and it is the sibling's state for the
sibling's reason. It was found the way this repository finds things -- a human
reading a recorded game
([[el-canal-de-descubrimiento-es-un-humano-leyendo-una-partida-perdida]]) -- and
the pressure it answers is Adrena-Brain aiming 30 damage at the body that was
going to survive. The bot on the other seat does not play that card the way a
person does, so the matchup this gate simulates is not the matchup the rule was
written for, and a neutral winrate here is the expected result rather than a
verdict. Keep the switch: if a later measurement against a real opponent
disagrees, `MARNIE_ENGINE_BARE_LINE_NEEDS_NO_RESERVE = False` is the whole
revert.

Usage:
    python utils/gate_the_bare_line_asks_nothing_of_the_reserve.py --games 1500 \
        --opponent deck/opponents/marnie_grimmsnarl.csv
    python utils/gate_the_bare_line_asks_nothing_of_the_reserve.py --games 1500 \
        --opponent deck/opponents/marnie_grimmsnarl.csv --control
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

LADDER = "MARNIE_ENGINE_BARE_LINE_NEEDS_NO_RESERVE"


def _boss_globals(mod):
    """The namespace of this arm's `ptcg/decision/boss_orders.py`.

    main.py star-imports the module, so `_ctx_gust_target` -- the single place
    that reads the switch -- carries that arm's globals on its own function
    object.
    """
    return mod._ctx_gust_target.__globals__


def arm(name, ladder):
    mod = sp.load_agent(_ROOT / "main.py", name)
    _boss_globals(mod)[LADDER] = ladder
    return mod


def _reads(mod):
    return _boss_globals(mod)[LADDER]


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
    ap.add_argument("--games", type=int, default=1500)
    ap.add_argument("--progress", type=int, default=500)
    ap.add_argument("--opponent", default="deck/opponents/marnie_grimmsnarl.csv")
    ap.add_argument("--control", action="store_true",
                    help="candidate arm NEUTRALISED: measures the noise floor")
    args = ap.parse_args(argv)

    candidate = arm("arm_candidate", not args.control)
    base = arm("arm_base", False)
    provenance(candidate, base, args.control)

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
    without, prizes_b = run(arm("arm_control", False), "baseline")
    delta, z, p = wilson_delta(with_rules, n, without, n)
    print(f"\n{'CONTROL' if args.control else 'CANDIDATO'} "
          f"({args.opponent or 'deck.csv'}, n={n}): "
          f"delta {100 * delta:+.2f} pp   z {z:+.2f}   p {p:.3f}   "
          f"premios {prizes_c - prizes_b:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
