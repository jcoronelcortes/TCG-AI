"""Two-arm gate for "the promotion is the seat the search completes",
isolated to THAT rule and nothing else in the working tree.

The rule (`PROMOTE_SEAT_THE_SEARCH_COMPLETES`): the evolution-survivor
promotion (`_ev_*` in `main.py`) counts the evolutions a benched body can wear
next turn as the ones in HAND *plus* the ones a Pokemon-search Supporter in hand
can still buy out of the DECK. Written from `records/registro_004` step 59 vs
Mega Lucario ex (episode 92943959, LOST): nothing on the bench survived their
270, so the block opened -- and found no evolution in hand, because the
Hydrapple ex was in the deck and what the hand held was the Dawn that reaches
it. The charged Ogerpon ex came up, could not touch the 440 in front of it, and
paid two prizes.

WHY NOT `selfplay.py --base HEAD`. Because the baseline it exports is the git
ref, and the working tree normally carries other work in progress: the delta
then answers "everything uncommitted", not "this rule". Here both arms are the
SAME tree, loaded twice, with the flag switched off in one of them.

NOTHING ON DISK IS REWRITTEN. The neutralisation happens on the loaded module
object, so this harness is safe to leave running while other files are edited.

READ THE CENSUS FIRST (`--census`). It counts how often the rule changes a
decision at all, and that number is the ceiling of any effect: if the event is
rare enough, no number of games resolves it, and the honest report is the census
plus a clean corpus plus the rules oracle
(`utils/oracle_the_promotion_is_the_seat_the_search_completes.py`), not a
winrate.

THE PREMISE IS FOUR THINGS AT ONCE, which is why the event is rare: our active
knocked out, NOTHING on the bench surviving their projected blow, a
pre-evolution that has been down a turn, and the tutor in hand with a copy of
its evolution still in the deck.

ALWAYS RUN `--control` AT THE SAME N as the real arms. Both arms neutralised is
the same code twice, so whatever separation it shows is that run's noise floor,
measured rather than assumed. A delta that does not clear it is not a delta.

Usage:
    python utils/gate_the_promotion_is_the_seat_the_search_completes.py --census
    python utils/gate_the_promotion_is_the_seat_the_search_completes.py --games 3000
    python utils/gate_the_promotion_is_the_seat_the_search_completes.py --games 3000 --control
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

# The deck the rule was written against, plus two controls the premise cannot
# reach as often: the rule needs a blow that one-shots our whole bench.
TARGET_DECKS = (
    "deck/opponents/mega_lucario.csv",
    "deck/opponents/mega_lucario_cornerstone.csv",
)


def neutralise(agent_module):
    """Switch the SEARCH route off in `agent_module`, in place.

    The flag is read from main.py's own globals inside the `_ev_*` block, so
    rebinding the module attribute leaves the route already in HAND exactly as
    it was -- which is the whole point: the two arms differ in one sentence.
    """
    agent_module.PROMOTE_SEAT_THE_SEARCH_COMPLETES = False
    return agent_module


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent."""
    if candidate is base:
        raise SystemExit("los dos brazos son el MISMO modulo")
    if bool(candidate.PROMOTE_SEAT_THE_SEARCH_COMPLETES) is bool(control):
        raise SystemExit("el brazo candidato no lleva la regla que dice llevar")
    if base.PROMOTE_SEAT_THE_SEARCH_COMPLETES:
        raise SystemExit("el brazo baseline lleva la regla: no hay nada que medir")
    print(f"procedencia OK (candidato "
          f"{'NEUTRALIZADO: control' if control else 'con la regla'}, "
          f"baseline sin ella)\n", flush=True)


def census():
    """How many decisions of the corpora does the rule change at all?

    The ceiling of any winrate effect. It replays both bundles -- the frozen
    fifty and the live records -- through both arms and compares choice by
    choice.
    """
    import golden_corpus as gc
    import json

    candidate = sp.load_agent(_ROOT / "main.py", "arm_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "arm_without"))
    provenance(candidate, base, control=False)

    bundles = {"tests/corpus/ (los cincuenta congelados)": gc.frozen_records()}
    vivos = {p.name: json.loads(p.read_text(encoding="utf-8"))
             for p in gc.record_files()}
    if vivos:
        bundles["records/ (los registros vivos)"] = vivos

    total_seen = total_changed = 0
    for label, records in bundles.items():
        if not records:
            print(f"{label}: vacio")
            continue
        seen = changed = 0
        touched = []
        for name, data in sorted(records.items()):
            with_rule = gc.replay_data(candidate, data)
            without = gc.replay_data(base, data)
            for a, b in zip(with_rule, without):
                seen += 1
                if a["eleccion"] != b["eleccion"]:
                    changed += 1
                    touched.append(f"    {name} turno {a['turno']} accion "
                                   f"{a['accion']}: {b['detalle']} -> {a['detalle']}")
        print(f"{label}: {changed} de {seen} decisiones "
              f"({100 * changed / seen:.2f}%) en {len(records)} registros")
        for line in touched:
            print(line)
        total_seen += seen
        total_changed += changed

    if total_seen and total_changed / total_seen < 0.005:
        print("\nAVISO: el evento es RARO. Con una exposicion asi, el gate de "
              "self-play puede no resolver nunca la diferencia por muchas "
              "partidas que juegue; el informe honesto es este censo mas un "
              "corpus limpio y el oraculo de reglas, no un winrate.")
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
                         "Omitted: the Mega Lucario lists the rule was written on")
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

    decks = (args.opponent.split(",") if args.opponent else list(TARGET_DECKS))
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
