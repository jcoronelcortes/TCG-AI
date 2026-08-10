"""Two-arm gate for "the cost could not see the card the search was buying",
isolated to THAT rule and nothing else in the working tree.

The rule (commit 5040fa9): when the discard menu is the cost of OUR OWN Ultra
Ball, `_evo_top_unlocked_by_the_search` puts the incoming link on the board
FIRST and only then prices the hand, so the orphaned top of a line whose missing
link the search will supply stops being fodder.

WHY NOT `selfplay.py --base HEAD`. Because the baseline it exports is the git
ref, and the working tree normally carries other work in progress: the delta
then answers "everything uncommitted", not "this rule". Here both arms are the
SAME tree, loaded twice, with the predicate switched off in one of them.

NOTHING ON DISK IS REWRITTEN. The neutralisation happens on the loaded module
object, so this harness is safe to leave running while other files are edited --
unlike the mutation/A-B-by-swap harnesses, which ARE the tree during a run.

READ THE CENSUS FIRST (`--census`). It counts how often the rule changes a
decision at all, and that number is the ceiling of any effect: if the event is
rare enough, no number of games resolves it, and the honest report is the census
plus a clean corpus rather than a winrate. On the frozen corpus at the time of
the commit it was 4 decisions in 3 580 -- 0.11%.

WHAT THE FIRST RUN MEASURED (18 000 games, 0 forfeits):

    affected (3 Crustle decks + a repeat, n=6000/arm)  81.03% vs 79.48%  +1.55
    control  (alakazam, dragapult,       n=3000/arm)   97.80% vs 97.80%  +0.00
    aggregate                            n=9000/arm    86.60% vs 85.60%  +1.00

Not resolved: at n=1500/arm the SE of a per-matchup delta is ~1.7 points, so no
single delta in that table says anything -- and the Wilson interval understates
the variance in matchup mode anyway, because the bot has randomness of its own
and the games are not the independent Bernoulli it assumes. To halve that SE the
games have to quadruple: ~15 000/arm per matchup buys SE ~0.5.

ALWAYS RUN `--control` AT THE SAME N as the real arms. Both arms neutralised is
the same code twice, so whatever separation it shows is that run's noise floor,
measured rather than assumed. A delta that does not clear it is not a delta.

Usage:
    python utils/gate_the_search_buys.py --census
    python utils/gate_the_search_buys.py --games 15000 --opponent deck/opponents/crustle_kangaskhan.csv
    python utils/gate_the_search_buys.py --games 15000 --opponent ... --control
"""

import argparse
import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402

# The three decks the rule was written against: an ex-immune wall is where the
# Meganium it saves pays for the Tapu Bulu that breaks through. The controls are
# kept in the docstring's table, not here, because a control deck is only worth
# playing when there is a reason to expect zero from it.
WALL_DECKS = (
    "deck/opponents/crustle_kangaskhan.csv",
    "deck/opponents/crustle_great_tusk_nz.csv",
    "deck/opponents/crustle_cubchoo_spheal.csv",
)


def neutralise(agent_module):
    """Switch the rule off in `agent_module`, permanently, in place.

    `sp.load_agent` restores `sys.modules` after loading, so the agent's own
    `ptcg` tree is not reachable by name -- it is reached through the objects
    the agent holds. Each arm has its OWN module objects (that is the whole
    point of `load_agent`), so patching one does not touch the other.

    It is the NAME INSIDE `ptcg.turn.options.card` that has to be rebound, not
    the one in `ptcg.cards.lines`: `from ... import` binds a copy, and the copy
    in `card` is the one the discard scorer calls.
    """
    card = agent_module.score_option.__globals__['card']
    card._evo_top_unlocked_by_the_search = lambda *a, **k: False
    return agent_module


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    The gate has been blind before (`selfplay --base` used to share the whole
    `ptcg` package between arms, so any change there measured exactly zero), and
    "neutral" is the verdict that orders a revert in this project. So the arms
    are asked directly, on the record's own board: a Meganium in hand, two
    Chikorita in play, a Bayleef still in the deck.
    """
    def fires(agent):
        card = agent.score_option.__globals__['card']
        return card._evo_top_unlocked_by_the_search(
            agent.Meganium, {agent.Meganium: 1}, {agent.Chikorita: 2},
            {agent.Bayleef: 2})

    if candidate.score_option is base.score_option:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if fires(candidate) is bool(control):
        raise SystemExit("el brazo candidato no lleva la regla que dice llevar")
    if fires(base):
        raise SystemExit("el brazo baseline lleva la regla: no hay nada que medir")
    print(f"procedencia OK (candidato {'NEUTRALIZADO: control' if control else 'con la regla'}, "
          f"baseline sin ella)\n", flush=True)


def census():
    """How many decisions of the frozen corpus does the rule change at all?

    The ceiling of any winrate effect. It replays the committed bundle through
    both arms and compares choice by choice.
    """
    import golden_corpus as gc

    candidate = sp.load_agent(_ROOT / "main.py", "arm_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "arm_without"))
    provenance(candidate, base, control=False)

    records = gc.frozen_records()
    if not records:
        raise SystemExit("no hay corpus congelado en tests/corpus/")

    seen = changed = 0
    touched = []
    for name, data in sorted(records.items()):
        with_rule = gc.replay_data(candidate, data)
        without = gc.replay_data(base, data)
        for a, b in zip(with_rule, without):
            seen += 1
            if a["eleccion"] != b["eleccion"]:
                changed += 1
                touched.append(f"  {name} turno {a['turno']} accion {a['accion']}: "
                               f"{b['detalle']} -> {a['detalle']}")
    print(f"CENSO sobre el corpus congelado: {changed} de {seen} decisiones "
          f"({100 * changed / seen:.2f}%) en {len(records)} registros")
    for line in touched:
        print(line)
    if seen and changed / seen < 0.005:
        print("\nAVISO: el evento es RARO. Con una exposicion asi, el gate de "
              "self-play puede no resolver nunca la diferencia por muchas "
              "partidas que juegue; el informe honesto es este censo mas un "
              "corpus limpio, no un winrate.")
    return 0


def wilson_delta(w1, n1, w2, n2):
    """Two-proportion z test. It ASSUMES independent Bernoulli, which the bot
    does not honour -- so read the p it prints as an optimistic bound."""
    if not n1 or not n2:
        return 0.0, 0.0, 1.0
    p1, p2 = w1 / n1, w2 / n2
    p = (w1 + w2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) or 1e-9
    z = (p1 - p2) / se
    return p1 - p2, z, 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=1500)
    ap.add_argument("--progress", type=int, default=250)
    ap.add_argument("--opponent", default=None,
                    help="csv of an opponent deck; repeatable via commas. "
                         "Omitted: the three ex-immune walls the rule targets")
    ap.add_argument("--control", action="store_true",
                    help="neutralise BOTH arms: the noise floor of this very run")
    ap.add_argument("--census", action="store_true",
                    help="how many corpus decisions the rule changes (run this first)")
    args = ap.parse_args(argv)

    if args.census:
        return census()

    from opponent_bot import OpponentBot

    candidate = sp.load_agent(_ROOT / "main.py", "arm_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "arm_without"))
    if args.control:
        neutralise(candidate)
    provenance(candidate, base, args.control)

    decks = (args.opponent.split(",") if args.opponent else list(WALL_DECKS))
    label_c = "con la regla" + (" (NEUTRALIZADO: control)" if args.control else "")

    totals = [0, 0, 0, 0]                      # wins_c, n_c, wins_b, n_b
    for rel in decks:
        their = sp.read_deck(_ROOT / rel)
        name = Path(rel).stem
        rows = []
        for agent in (candidate, base):
            st = sp.torneo(agent, OpponentBot(), args.games,
                           progress=args.progress or None, deck_base=their)
            rows.append((st["candidate"], st["candidate"] + st["base"], st))
        (wc, nc, stc), (wb, nb, stb) = rows
        totals[0] += wc; totals[1] += nc; totals[2] += wb; totals[3] += nb
        d, z, p = wilson_delta(wc, nc, wb, nb)
        print(f"{name:30s} {label_c} {100 * wc / nc:5.2f}%   sin ella "
              f"{100 * wb / nb:5.2f}%   delta {100 * d:+5.2f} pts  z={z:5.2f} p={p:.3f}   "
              f"premios {sp.prizes_per_game(stc)[0]:.2f} vs {sp.prizes_per_game(stb)[0]:.2f}   "
              f"forfeits {stc['errores_candidato']}/{stb['errores_candidato']}",
              flush=True)

    d, z, p = wilson_delta(*totals)
    print(f"\nAGREGADO ({totals[1]} partidas por brazo)  "
          f"{100 * totals[0] / totals[1]:.2f}% vs {100 * totals[2] / totals[3]:.2f}%   "
          f"DELTA {100 * d:+.2f} pts  z={z:.2f}  p={p:.3f} (cota optimista)")
    if args.control:
        print("Esto es el SUELO DE RUIDO: mismo codigo en los dos brazos. "
              "Un delta real tiene que superarlo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
