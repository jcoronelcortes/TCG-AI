"""Self-play gate for `AN_ITEM_UNDER_A_LOCK_IS_NOT_A_PLAYABLE_CARD`.

THE READING (user, episode 93229766 turn 14 vs a Budew/Dragapult deck, LOST).
Our active was a Chikorita with no energy and a retreat cost of one, so it could
neither attack nor step aside; the two Teal Mask Ogerpon ex carrying the turn's
energy sat on the bench, unreachable. The hand was nine cards, five of them
Items, and the opposing Budew had declared Itchy Pollen: not one of them could
be played. The one card that WAS playable was the Meowth ex, whose Last-Ditch
Catch fetches a Supporter -- and the Meowth branch of `play.py` vetoed it with

    elif _bcs_playable_in_hand and bench_count >= 1:   # "play the Set first"

deferring to a Bug Catching Set that the lock had taken off the table. Four
branches below sat the dead-turn rule (`_active_cant_attack_this_turn`, 21800)
written for exactly this board; it was never reached. The turn ended with END.

WHAT THE FLAG IS. `_bcs_playable_in_hand` asked two questions -- is there a Set
in hand, is there anything left in the deck for it to find -- and never the
third: can an Item be played this turn at all. The other two consumers of the
pair already ask it by hand (`attach.py:291` for the Set,
`ptcg/decision/bug_catching_set.py` for `pp_playable_in_hand`), so the lock now
lives in the FLAG and every reader inherits it, general rule before special case.

READ THE CORPUS FIRST. Over the 3 580 decisions of the frozen corpus this flips
ZERO, and over the local records exactly ONE -- the turn it was written for. At
that exposure a winrate cannot resolve it and is not expected to: `--control` is
the row that says so out loud, playing the flag against ITSELF so its delta is
the noise floor at the same N. A candidate row smaller than the control row is
noise ([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]]).

Usage:
    python utils/gate_an_item_under_a_lock_is_not_playable.py --games 1000 \
        --opponent deck/real_opponents/dragapult_1.csv
    python utils/gate_an_item_under_a_lock_is_not_playable.py --games 1000 \
        --opponent deck/real_opponents/dragapult_1.csv --control
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

FLAG = "AN_ITEM_UNDER_A_LOCK_IS_NOT_A_PLAYABLE_CARD"


def arm(name, rule):
    """One arm of the measurement: the whole tree, with the flag rebound.

    The flag is read from `main.py`'s own globals at decision time (it is not a
    keyword with a default and not a copy taken at import), so setting it on the
    loaded module is enough -- unlike the rules that live in a `ptcg` submodule
    and have to be reached through `__globals__`.
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
