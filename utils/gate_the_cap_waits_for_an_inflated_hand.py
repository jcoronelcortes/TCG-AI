"""Two-arm gate for "the cap's floor moves with our prize counter", isolated to
THAT reading and nothing else in the working tree.

THE RULE (user, `records/registro_003_pasos_025_hasta_031.json`, episode
92856565, step 29, turn 3 vs Alakazam -- LOST). vs Alakazam the Xerosic cap used
to wait for SIX cards in the opposing hand, one number for the whole game. Six is
the size a hand simply IS after the draw, so on turn 3 the floor was measuring a
dealt hand and not an inflated one. It is now two numbers and OUR prize counter
picks between them (`_xr_alakazam_floor`): EIGHT while five or more of our prizes
are up, SIX from there on.

WHAT THE BASELINE ARM IS. The rule as it was: `XEROSIC_ALAKAZAM_FLOOR_EARLY`
rebound to the late floor, so both halves answer six. One number out of place and
nothing else -- same code, same order, same rule list -- because the arms have to
differ by the change under test and by nothing else.

WHY NOT `selfplay.py --base HEAD~1`. The baseline it exports is the git ref, and
the delta then answers "everything in that commit". Here both arms are the SAME
tree loaded twice with one constant rebound. Nothing on disk is rewritten, so it
is safe to leave running while other files are edited.

THE CRITERION, WRITTEN BEFORE THE NUMBER EXISTS. This is a CARD RULE stated by
the user off a lost record, not an estimated improvement queued by a census. So
neutral does NOT order a revert here: it orders the marking. A neutral result is
recorded as a user override (see the policy note
`un-override-del-usuario-no-es-una-excepcion-de-la-politica`) and the rule
stays. What the gate is really being asked is whether the change COSTS anything
-- a significant negative delta is the finding that would send it back.

THE EXPOSURE COMES FIRST. `--census` replays the frozen corpus through both arms
and counts the decisions that differ. Read it before any winrate: an event this
narrow can be invisible to self-play at any N it is worth paying for, and then
the honest report is the census plus a clean corpus, not a delta.

ALWAYS RUN `--control` AT THE SAME N. Both arms neutralised is the same code
twice, so whatever separation it shows is that run's noise floor. A delta that
does not clear it is not a delta. And the CONTROL DECK is the other half of the
same idea: against a deck with no Abra line the floor names nothing, so that
column has to come out at the noise floor whatever the Alakazam column says.

Usage:
    python utils/gate_the_cap_waits_for_an_inflated_hand.py --census
    python utils/gate_the_cap_waits_for_an_inflated_hand.py --games 1500
    python utils/gate_the_cap_waits_for_an_inflated_hand.py --games 1500 --control
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

# The matchup the card is in the deck for: the only board where the floor speaks.
DEFAULT_DECKS = ("deck/opponents/alakazam.csv",)

# The BLIND control: no Abra line across the table, so `_xr_alakazam_floor` is
# never even consulted. Whatever this column shows is what this run calls zero.
CONTROL_DECK = "deck/opponents/crustle_kangaskhan.csv"

# What "the rule as it was" is, in one number: the early floor collapsed onto the
# late one, so both halves answer six exactly as before the change.
FLOOR_BEFORE = 6


def _disruption_of(agent_module):
    """The arm's OWN `ptcg.decision.disruption` module dict.

    Reached through a function main.py star-imported from it, for the same
    reason the sibling gate reaches `card` that way: `sp.load_agent` builds a
    private `ptcg` tree per arm, and the module object has to come from the arm
    rather than from this process's import.
    """
    return agent_module._score_xerosic_play.__globals__


def neutralise(agent_module):
    """Put the floor back to the one number it used to be, in place."""
    g = _disruption_of(agent_module)
    g['XEROSIC_ALAKAZAM_FLOOR_EARLY'] = g['XEROSIC_ALAKAZAM_FLOOR_LATE']
    return agent_module


class _Ctx:
    """The one field the floor reads. Six prizes: the opening board, where the
    two arms are supposed to disagree."""
    my_prize = 6
    op_hand_count = 7
    op_is_alakazam_deck = True


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    The gate has been blind before (`selfplay --base` used to share the whole
    `ptcg` package between arms, so any change there measured exactly zero). So
    the arms are asked DIRECTLY for the number the ladder will compare against,
    on a six-prize board.
    """
    def floor(agent):
        return agent._xr_alakazam_floor(_Ctx())

    if candidate.score_option is base.score_option:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if floor(base) != FLOOR_BEFORE:
        raise SystemExit(f"el brazo baseline NO esta neutralizado (suelo "
                         f"{floor(base)}): no hay nada que medir")
    if (floor(candidate) == FLOOR_BEFORE) is not bool(control):
        raise SystemExit("el brazo candidato no esta como dice estar "
                         f"(control={bool(control)}, suelo={floor(candidate)})")
    # And the two arms have to disagree on a board the simulator actually deals:
    # a floor nobody reaches is the same blindness with a different face.
    if not control and floor(candidate) <= FLOOR_BEFORE:
        raise SystemExit(f"el suelo del candidato ({floor(candidate)}) no esta "
                         "por encima del viejo: el brazo no lleva la regla")
    print(f"procedencia OK (candidato suelo={floor(candidate)}"
          f"{' NEUTRALIZADO: control' if control else ''}, "
          f"baseline suelo={floor(base)})\n", flush=True)


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
    ap.add_argument("--games", type=int, default=1000)
    ap.add_argument("--progress", type=int, default=200)
    ap.add_argument("--opponent", default=None,
                    help="csv of an opponent deck; repeatable via commas. "
                         "Omitted: the Alakazam list the card is in the deck for")
    ap.add_argument("--no-control-deck", action="store_true",
                    help="skip the blind deck (no Abra line) run in the same session")
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
    if not args.no_control_deck and CONTROL_DECK not in decks:
        decks = decks + [CONTROL_DECK]
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
        # The blind deck is a CONTROL, not part of the verdict: it is reported
        # beside the matchup and never summed into it.
        if rel != CONTROL_DECK:
            totals[0] += wc; totals[1] += nc; totals[2] += wb; totals[3] += nb
        d, z, p = wilson_delta(wc, nc, wb, nb)
        tag = "  [CONTROL CIEGO]" if rel == CONTROL_DECK else ""
        print(f"{name:30s} {label_c} {100 * wc / nc:5.2f}%   sin ella "
              f"{100 * wb / nb:5.2f}%   delta {100 * d:+5.2f} pts  z={z:5.2f} p={p:.3f}   "
              f"premios {sp.prizes_per_game(stc)[0]:.2f} vs {sp.prizes_per_game(stb)[0]:.2f}   "
              f"forfeits {stc['errores_candidato']}/{stb['errores_candidato']}{tag}",
              flush=True)

    d, z, p = wilson_delta(*totals)
    print(f"\nAGREGADO ({totals[1]} partidas por brazo, sin el control ciego)  "
          f"{100 * totals[0] / totals[1]:.2f}% vs {100 * totals[2] / totals[3]:.2f}%   "
          f"DELTA {100 * d:+.2f} pts  z={z:.2f}  p={p:.3f} (cota optimista)")
    if args.control:
        print("Esto es el SUELO DE RUIDO: mismo codigo en los dos brazos. "
              "Un delta real tiene que superarlo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
