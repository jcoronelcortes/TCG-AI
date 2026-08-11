"""Two-arm gate for "the cap outside its matchup is priced by their hand",
isolated to THAT reading and nothing else in the working tree.

THE RULE. In the DISCARD ladder, Xerosic's Machinations outside the Alakazam
matchup was a FIXED 60 -- fodder of middling price with their hand at twelve and
with their hand at four. The PLAY scorer has never agreed: at or above
`XEROSIC_BIG_HAND` it prices the same card `XEROSIC_SCORE_GENERIC` (3380) and
below it drops to `XEROSIC_SCORE_LAST_RESORT` (20). The reading is asked SECOND
and only subtracts: with a fat opposing hand the 60 falls to
`DISCARD_XEROSIC_CAPS_A_FAT_HAND` (22), the height of a single Boss's Orders.

WHY IT WAS WORTH ASKING AT ALL. `utils/rule_census.py` and the discard capture
say the fixed branch is not a corner: 34 of the 40 Xerosic options priced across
the 50 frozen records take it, in 25 different games. That is EXPOSURE, not
effect -- which is what `--census` below is for.

WHY NOT `selfplay.py --base HEAD`. The baseline it exports is the git ref, and
the working tree normally carries other work: the delta then answers "everything
uncommitted", not "this rule". Here both arms are the SAME tree loaded twice,
with the reading switched off in one of them. Nothing on disk is rewritten, so
it is safe to leave running while other files are edited.

THE CRITERION, WRITTEN BEFORE THE NUMBER EXISTS. This rule removes a
contradiction between two scorers of the same card -- the doctrine the Supporter
block already applies to the other four -- but the note that queued it decided
in advance that it is an ESTIMATED improvement rather than a contradiction that
stands on its own, and that neutral therefore means REVERT. That is the
criterion this gate is read against, and it is not to be renegotiated after
seeing the delta.

ALWAYS RUN `--control` AT THE SAME N. Both arms neutralised is the same code
twice, so whatever separation it shows is that run's noise floor. A delta that
does not clear it is not a delta.

Usage:
    python utils/gate_the_cap_reads_their_hand.py --census
    python utils/gate_the_cap_reads_their_hand.py --games 15000
    python utils/gate_the_cap_reads_their_hand.py --games 15000 --control
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

# Decks that are NOT Alakazam -- where the branch changes nothing by
# construction -- and that hold a hand big enough for the threshold to be
# reached. The corpus names them: crustle, cynthia, festival, dragapult and
# marnie are where the 34 fixed-price options live.
DEFAULT_DECKS = (
    "deck/opponents/crustle_kangaskhan.csv",
    "deck/opponents/marnie_grimmsnarl.csv",
    "deck/opponents/festival_lead.csv",
)

# Out of reach of any hand the simulator deals: the arm that carries this
# threshold can never protect the cap, which is the neutralisation.
IMPOSIBLE = 10 ** 6


def neutralise(agent_module):
    """Switch the reading off in `agent_module`, permanently, in place.

    It is the constant INSIDE `ptcg.turn.options.card` that has to be rebound,
    not the one in `ptcg.cards.ids`: `from ... import` binds a copy, and the copy
    in `card` is the one the discard scorer compares against. Rebinding the
    threshold rather than deleting the branch keeps the two arms structurally
    identical -- same code, same order, one number out of reach.
    """
    card = agent_module.score_option.__globals__['card']
    card.XEROSIC_BIG_HAND = IMPOSIBLE
    return agent_module


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    The gate has been blind before (`selfplay --base` used to share the whole
    `ptcg` package between arms, so any change there measured exactly zero), and
    "neutral" is the verdict that orders a revert here. So the arms are asked
    directly for the threshold the discard scorer will compare against.
    """
    def umbral(agent):
        return agent.score_option.__globals__['card'].XEROSIC_BIG_HAND

    if candidate.score_option is base.score_option:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if umbral(base) != IMPOSIBLE:
        raise SystemExit("el brazo baseline NO esta neutralizado: no hay nada que medir")
    if (umbral(candidate) == IMPOSIBLE) is not bool(control):
        raise SystemExit("el brazo candidato no esta como dice estar "
                         f"(control={bool(control)}, umbral={umbral(candidate)})")
    # And the reading has to be REACHABLE: a threshold nobody meets is the same
    # blindness with a different face.
    if not control and umbral(candidate) > 20:
        raise SystemExit(f"el umbral del candidato ({umbral(candidate)}) no lo "
                         "alcanza ninguna mano: el brazo no lleva la regla")
    print(f"procedencia OK (candidato {'NEUTRALIZADO: control' if control else 'con la regla'}, "
          f"baseline sin ella)\n", flush=True)


def census():
    """How many decisions of the frozen corpus does the reading change at all?

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
        print("\nAVISO: el evento es RARO. Con una exposicion asi el gate de "
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
                         "Omitted: three non-Alakazam decks that hold a big hand")
    ap.add_argument("--control", action="store_true",
                    help="neutralise BOTH arms: the noise floor of this very run")
    ap.add_argument("--census", action="store_true",
                    help="how many corpus decisions the reading changes (run this first)")
    args = ap.parse_args(argv)

    if args.census:
        return census()

    from opponent_bot import OpponentBot

    candidate = sp.load_agent(_ROOT / "main.py", "arm_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "arm_without"))
    if args.control:
        neutralise(candidate)
    provenance(candidate, base, args.control)

    decks = (args.opponent.split(",") if args.opponent else list(DEFAULT_DECKS))
    label_c = "con la regla" + (" (NEUTRALIZADO: control)" if args.control else "")

    totals = [0, 0, 0, 0]
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
