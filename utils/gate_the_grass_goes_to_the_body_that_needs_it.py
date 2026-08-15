"""Self-play gate for the three readings of registro_005 (turn 5 vs Marnie).

THE ARMS ARE THE SAME TREE WITH THE FLAGS REBOUND, which is the only way to make
the rules the single difference between them: both arms are the working tree,
loaded twice by `selfplay.load_agent` so each gets its own `ptcg` package (a
shared tree measures exactly zero -- see `load_agent_from_git`).

The three flags are constants imported BY VALUE into the module that reads
them, so rebinding them on `ptcg.cards.ids` would change nothing. Each one is
set on its consumer, reached through the `__globals__` of a function that arm
exported -- the arm's own namespace, not the ambient one.

    CHARGE_THE_BODY_THAT_NEEDS_IT     ptcg/turn/energy.py
    DAWN_SEAT_WAITS_A_TURN            ptcg/decision/supporters.py
    FEZ_ABILITY_BEFORE_THE_KNOCKOUT   ptcg/turn/options/play.py

READ THE CORPUS FIRST. Over the 3 580 decisions of the frozen corpus the three
readings together flip ONE, and over the local records they flip the three the
record accuses. At that exposure a winrate cannot resolve them and this gate is
a HARM CHECK, not the evidence. `--control` is what says so out loud: it plays
the flags against THEMSELVES, so its delta is the noise floor at the same N and
any candidate row smaller than that row is noise.

Usage:
    python utils/gate_the_grass_goes_to_the_body_that_needs_it.py --games 400 \
        --opponent deck/opponents/marnie_grimmsnarl.csv
    python utils/gate_the_grass_goes_to_the_body_that_needs_it.py --games 400 --control
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

# flag -> the function whose module reads it.
FLAGS = {
    "CHARGE_THE_BODY_THAT_NEEDS_IT": "_energy_score_base_impl",
    "DAWN_SEAT_WAITS_A_TURN": "_dawn_seat_waits_a_turn",
    "FEZ_ABILITY_BEFORE_THE_KNOCKOUT": "_fez_flag_probe",
}


def _play_globals(mod):
    """The namespace of this arm's `ptcg/turn/options/play.py`.

    main.py re-exports no function of that module, so it is reached through the
    dispatch table `ptcg.turn.scoring` builds: `score_option` closes over
    `_TABLE`, whose PLAY entry IS this arm's `play.score_play`.
    """
    from cg.api import OptionType
    table = mod.score_option.__globals__["_TABLE"]
    return table[OptionType.PLAY].__globals__


def arm(name, value):
    mod = sp.load_agent(_ROOT / "main.py", name)
    mod._energy_score_base_impl.__globals__[
        "CHARGE_THE_BODY_THAT_NEEDS_IT"] = value
    mod._dawn_seat_waits_a_turn.__globals__["DAWN_SEAT_WAITS_A_TURN"] = value
    _play_globals(mod)["FEZ_ABILITY_BEFORE_THE_KNOCKOUT"] = value
    return mod


def _reads(mod):
    return (mod._energy_score_base_impl.__globals__[
                "CHARGE_THE_BODY_THAT_NEEDS_IT"],
            mod._dawn_seat_waits_a_turn.__globals__["DAWN_SEAT_WAITS_A_TURN"],
            _play_globals(mod)["FEZ_ABILITY_BEFORE_THE_KNOCKOUT"])


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent."""
    if candidate is base:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if any(_reads(base)):
        raise SystemExit("el brazo baseline NO esta neutralizado: nada que medir")
    if any(_reads(candidate)) is bool(control):
        raise SystemExit(
            f"el brazo candidato no esta como dice estar (control={bool(control)}, "
            f"lectura={_reads(candidate)})")
    print(f"procedencia OK (candidato "
          f"{'NEUTRALIZADO: control' if control else 'con las lecturas'}, "
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
    ap.add_argument("--games", type=int, default=400)
    ap.add_argument("--progress", type=int, default=100)
    ap.add_argument("--opponent", default=None)
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
        print(f"  {label:10s} {wins:5d}/{n} = {100 * wins / n:6.2f}%", flush=True)
        return wins

    with_rules = run(candidate, "candidato")
    without = run(arm("arm_control", False), "baseline")
    delta, z, p = wilson_delta(with_rules, n, without, n)
    print(f"\n{'CONTROL' if args.control else 'CANDIDATO'} "
          f"({args.opponent or 'deck.csv'}, n={n}): "
          f"delta {100 * delta:+.2f} pp   z {z:+.2f}   p {p:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
