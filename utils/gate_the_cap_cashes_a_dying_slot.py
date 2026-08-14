"""Two-arm gate for "the cap is cashed when the slot dies with the attack",
isolated to THAT rule and nothing else in the working tree.

THE RULE. `finalizar` plays the turn's Supporter BEFORE the attack that closes
it, and refuses to do so for anything down in `SUPP_SCORE_LAST_RESORT_BAND` --
"the free slot is not a reason to spend the CARD, which keeps its value for
tomorrow". `OP_HAND_PRICED_PLAY_IDS` is the one exception: a play priced by the
size of THEIR hand does not keep a value we control, and with their hand at or
above `XEROSIC_FREE_SLOT_HAND` (the cap discards at least as many cards as it
leaves) it is cashed rather than buried with the turn.

WHY IT WAS WORTH ASKING AT ALL. The frozen corpus flips exactly ONE decision --
the record that found it, `registro_005` step 68 -- so the corpus cannot price
this. What says the window is not a corner is the SELF-PLAY firing census
(`--census`): the same board (slot free, attack winning the menu, their hand at
six or more, the cap in hand) shows up on its own in two other fixtures of the
estate, vs Dragapult and vs Mega Starmie.

WHY NOT `selfplay.py --base HEAD`. The baseline it exports is the git ref, and
the working tree normally carries other work: the delta then answers
"everything uncommitted", not "this rule". Here both arms are the SAME tree
loaded twice, with the exception switched off in one of them.

THE CRITERION, WRITTEN BEFORE THE NUMBER EXISTS. This rule removes a
contradiction the estate states in its own words -- the card we KEEP and the
card we would PLAY cannot disagree, and outside the Alakazam matchup the
discard scorer prices this same Xerosic at 60, the most throwable Supporter
band there is. It also removes an incoherence that has nothing to do with
keeping cards: at the band the cap IS spent by elimination whenever the menu is
{play it, END} (END scores 0), so whether the last resort got played depended on
whether our active happened to have an attack available. Both of those stand on
the game's own arithmetic, so NEUTRAL DOES NOT ORDER A REVERT here: it orders
the mark. A LOSS that clears the noise floor does order the revert.

ALWAYS RUN `--control` AT THE SAME N. Both arms neutralised is the same code
twice, so whatever separation it shows is that run's noise floor. A delta that
does not clear it is not a delta.

Usage:
    python utils/gate_the_cap_cashes_a_dying_slot.py --census
    python utils/gate_the_cap_cashes_a_dying_slot.py --games 1500
    python utils/gate_the_cap_cashes_a_dying_slot.py --games 1500 --control
"""

import argparse
import math
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402

# The matchup of the record FIRST (Mega Lopunny ex / Mega Froslass ex, the
# third list of the meta at 6.8 %), then the non-Alakazam decks the estate
# already gates on -- where the cap lives in the last-resort band and this rule
# is the only thing that ever plays it. Alakazam is deliberately absent: there
# the floor vetoes below and the cap scores in the thousands above, so the
# exception is unreachable by construction and would only dilute the read.
DEFAULT_DECKS = (
    "deck/real_opponents_500/mega_lopunny_mega_froslass_1.csv",
    "deck/opponents/marnie_grimmsnarl.csv",
    "deck/opponents/dragapult.csv",
    "deck/opponents/crustle_kangaskhan.csv",
)

# Out of reach of any hand the game can deal: the arm carrying this threshold
# can never cash the dying slot, which is the neutralisation. Rebinding the
# number rather than deleting the branch keeps the two arms structurally
# identical -- same code, same order, one constant out of reach.
IMPOSIBLE = 10 ** 6


def neutralise(agent_module):
    """Switch the exception off in `agent_module`, permanently, in place.

    It is the constant INSIDE `ptcg.turn.finalize` that has to be rebound, not
    the one in `ptcg.cards.ids`: `from ... import` binds a copy, and the copy in
    `finalize` is the one `_sba_price_is_theirs` compares against.
    """
    fin = agent_module.finalizar.__globals__
    fin['XEROSIC_FREE_SLOT_HAND'] = IMPOSIBLE
    return agent_module


def _floor_of(agent_module):
    return agent_module.finalizar.__globals__['XEROSIC_FREE_SLOT_HAND']


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    The gate has been blind before (`selfplay --base` used to share the whole
    `ptcg` package between arms, so any change there measured exactly zero), so
    the arms are asked directly for the number the net will compare against.
    """
    if candidate.finalizar is base.finalizar:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if _floor_of(base) != IMPOSIBLE:
        raise SystemExit("el brazo baseline NO esta neutralizado: no hay nada que medir")
    if (_floor_of(candidate) == IMPOSIBLE) is not bool(control):
        raise SystemExit("el brazo candidato no esta como dice estar "
                         f"(control={bool(control)}, suelo={_floor_of(candidate)})")
    # And the rule has to be REACHABLE: a floor no hand meets is the same
    # blindness with a different face.
    if not control and _floor_of(candidate) > 20:
        raise SystemExit(f"el suelo del candidato ({_floor_of(candidate)}) no lo "
                         "alcanza ninguna mano: el brazo no lleva la regla")
    print(f"procedencia OK (candidato {'NEUTRALIZADO: control' if control else 'con la regla'}, "
          f"baseline sin ella)\n", flush=True)


def census(games, decks, progress):
    """HOW OFTEN the exception is even asked, and with which hand.

    The corpus flips one decision, so the exposure has to be measured where the
    boards come from -- self-play. The sink in `finalizar` is handed every board
    on which the net reaches a card of `OP_HAND_PRICED_PLAY_IDS` down in the
    band with the slot dying: that is the population, and the hand count says
    which side of the floor each one fell.
    """
    from opponent_bot import OpponentBot

    agent = sp.load_agent(_ROOT / "main.py", "arm_census")
    # The arm's OWN module namespace, not `sys.modules`: each arm is loaded in
    # isolation precisely so the two cannot share `ptcg`, so the globals dict of
    # its `finalizar` is the only handle on the copy that is going to run.
    fin = agent.finalizar.__globals__
    manos = Counter()

    def sink(_card_id, op_hand, _fires):
        manos[op_hand] += 1

    fin['DYING_SLOT_CENSUS_SINK'] = sink
    try:
        total = 0
        for rel in decks:
            their = sp.read_deck(_ROOT / rel)
            manos.clear()
            sp.torneo(agent, OpponentBot(), games,
                      progress=progress or None, deck_base=their)
            asked = sum(manos.values())
            fired = sum(n for h, n in manos.items()
                        if h >= _floor_of(agent))
            total += fired
            reparto = " ".join(f"{h}:{n}" for h, n in sorted(manos.items()))
            print(f"{Path(rel).stem:38s} preguntado {asked:5d} "
                  f"({asked / games:.2f}/partida)   DISPARA {fired:5d} "
                  f"({fired / games:.2f}/partida)   manos [{reparto}]",
                  flush=True)
        print(f"\nCENSO DE DISPARO: {total / (games * len(decks)):.2f} "
              f"decisiones por partida de media.")
        if total / (games * len(decks)) < 0.01:
            print("AVISO: el evento es RARO. Con una exposicion asi el gate de "
                  "self-play puede no resolver la diferencia por muchas partidas "
                  "que juegue; el informe honesto es este censo, no un winrate.")
    finally:
        fin['DYING_SLOT_CENSUS_SINK'] = None
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
    ap.add_argument("--progress", type=int, default=500)
    ap.add_argument("--opponent", default=None,
                    help="csv of an opponent deck; repeatable via commas")
    ap.add_argument("--control", action="store_true",
                    help="neutralise BOTH arms: the noise floor of this very run")
    ap.add_argument("--census", action="store_true",
                    help="how often the exception is asked at all (run this first)")
    args = ap.parse_args(argv)

    decks = (args.opponent.split(",") if args.opponent else list(DEFAULT_DECKS))

    if args.census:
        return census(args.games, decks, args.progress)

    from opponent_bot import OpponentBot

    candidate = sp.load_agent(_ROOT / "main.py", "arm_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "arm_without"))
    if args.control:
        neutralise(candidate)
    provenance(candidate, base, args.control)

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
        print(f"{name:38s} {label_c} {100 * wc / nc:5.2f}%   sin ella "
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
