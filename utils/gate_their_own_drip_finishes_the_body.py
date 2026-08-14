"""Two-arm gate for "their own Freezing Shroud finishes the body in front",
isolated to THAT reading and nothing else in the working tree.

THE RULE. Freezing Shroud puts a counter on EACH Pokemon in play that has an
Ability, and their board is in play too: their Grimmsnarl ex (Punk Up) and their
Munkidori (Adrena-Brain) pay the same 10 per Froslass per checkup that our
bodies do. `_op_hp_for_our_ko` is that reading -- the HP our attack actually has
to cover, because the drip pays the rest at the checkup, BETWEEN turns, where
they can neither heal it nor move the damage off it with Adrena-Brain.

WHY IT WAS WORTH ASKING AT ALL. The frozen corpus flips exactly ONE decision --
the record that found it, `registro_006` step 90, where the forced promotion
read their 320 HP Grimmsnarl ex at its printed HP, decided the benched Meganium
did not knock it out (280 < 320), kept the Wild Growth veto up and brought a
mute Meowth ex to the front. Read with the two checkups that menu is followed by
it is 280 against 280: the exact hit, two prizes. What says this is not a corner
is the `--census`: how many knockout verdicts the reading changes per game
against the decks that actually play a Froslass.

WHY NOT `selfplay.py --base HEAD`. The baseline it exports is the git ref, and
the working tree normally carries other work: the delta then answers
"everything uncommitted", not "this reading". Here both arms are the SAME tree
loaded twice, with `SHROUD_KO_READING` switched off in one of them.

THE CRITERION, WRITTEN BEFORE THE NUMBER EXISTS. This is not a preference being
tuned, it is a rule of the game the model was only reading half of -- and the
estate already wrote the other half down, in the note next to
FREEZING_SHROUD_COUNTER ("their own Froslass loads 10 per checkup onto each
Munkidori AND onto the Grimmsnarl ex -- they all have an ability"), where it was
used only to count Adrena-Brain's ammunition. It is also a STRICT NO-OP on every
board without a Froslass in play, which the unit tests pin. So NEUTRAL DOES NOT
ORDER A REVERT here: it orders the mark. A LOSS that clears the noise floor does
order the revert.

ALWAYS RUN `--control` AT THE SAME N. Both arms neutralised is the same code
twice, so whatever separation it shows is that run's noise floor. A delta that
does not clear it is not a delta.

Usage:
    python utils/gate_their_own_drip_finishes_the_body.py --census
    python utils/gate_their_own_drip_finishes_the_body.py --games 1000
    python utils/gate_their_own_drip_finishes_the_body.py --games 1000 --control
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

# THE POPULATION IS THE DECKS THAT PLAY A FROSLASS, because everywhere else the
# reading is the printed HP by construction and both arms are the same agent.
# The record's own list first, then two of the harvested Marnie lists (the
# archetype is 15 of the 500-deck meta), and two controls where the rule cannot
# fire -- they are here to catch a change that leaks OUT of the matchup, which
# is the failure mode a no-op has.
DEFAULT_DECKS = (
    "deck/opponents/marnie_grimmsnarl.csv",
    "deck/real_opponents_500/marnie_grimmsnarl_1.csv",
    "deck/real_opponents_500/marnie_grimmsnarl_7.csv",
    "deck/opponents/crustle_kangaskhan.csv",
    "deck/opponents/alakazam.csv",
)


def neutralise(agent_module):
    """Switch the reading off in `agent_module`, permanently, in place.

    It is the flag inside `ptcg.calc.damage` that has to be rebound, not a copy:
    `_op_hp_for_our_ko` reads it out of its own module globals, and that same
    function object is the one main.py's star import bound. One assignment
    switches both halves.
    """
    dmg = agent_module._op_hp_for_our_ko.__globals__
    dmg['SHROUD_KO_READING'] = False
    return agent_module


def _reading_of(agent_module):
    return agent_module._op_hp_for_our_ko.__globals__['SHROUD_KO_READING']


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    The gate has been blind before (`selfplay --base` used to share the whole
    `ptcg` package between arms, so any change there measured exactly zero), so
    the arms are asked directly for the flag the net will compare against.
    """
    if candidate._op_hp_for_our_ko is base._op_hp_for_our_ko:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if _reading_of(base):
        raise SystemExit("el brazo baseline NO esta neutralizado: no hay nada que medir")
    if _reading_of(candidate) is bool(control):
        raise SystemExit("el brazo candidato no esta como dice estar "
                         f"(control={bool(control)}, lectura={_reading_of(candidate)})")
    print(f"procedencia OK (candidato {'NEUTRALIZADO: control' if control else 'con la lectura'}, "
          f"baseline sin ella)\n", flush=True)


def census(games, decks, progress):
    """HOW MANY KNOCKOUT VERDICTS THE READING CHANGES, per game.

    The corpus flips one decision, so the exposure has to be measured where the
    boards come from -- self-play. Every call to `_op_hp_for_our_ko` is counted,
    and separately the ones where the softened HP is strictly below the printed
    one AND the difference is what makes the target reachable at all. The first
    number is the population, the second is the window.
    """
    from opponent_bot import OpponentBot

    agent = sp.load_agent(_ROOT / "main.py", "arm_census")
    dmg = agent._op_hp_for_our_ko.__globals__
    plain = dmg['_op_hp_for_our_ko']
    counts = Counter()

    def counted(target, checkups=1):
        out = plain(target, checkups)
        hp = getattr(target, 'hp', 0) or 0
        counts['asked'] += 1
        if 0 < out < hp:
            counts['softened'] += 1
            counts[f'by{hp - out}'] += 1
        return out

    dmg['_op_hp_for_our_ko'] = counted
    # The star import in main.py bound the ORIGINAL object, so the copy that the
    # promotion and the attack loop call has to be rebound too.
    agent.__dict__['_op_hp_for_our_ko'] = counted
    try:
        total = 0
        for rel in decks:
            their = sp.read_deck(_ROOT / rel)
            counts.clear()
            sp.torneo(agent, OpponentBot(), games,
                      progress=progress or None, deck_base=their)
            asked, soft = counts['asked'], counts['softened']
            total += soft
            reparto = " ".join(f"-{k[2:]}:{n}" for k, n in sorted(counts.items())
                               if k.startswith('by'))
            print(f"{Path(rel).stem:38s} preguntado {asked:7d} "
                  f"({asked / games:7.2f}/partida)   ABLANDA {soft:6d} "
                  f"({soft / games:6.2f}/partida)   [{reparto}]", flush=True)
        print(f"\nCENSO DE ABLANDAMIENTO: {total / (games * len(decks)):.2f} "
              f"lecturas por partida de media.")
        if total / (games * len(decks)) < 0.01:
            print("AVISO: el evento es RARO. Con una exposicion asi el gate de "
                  "self-play puede no resolver la diferencia por muchas partidas "
                  "que juegue; el informe honesto es este censo, no un winrate.")
    finally:
        dmg['_op_hp_for_our_ko'] = plain
        agent.__dict__['_op_hp_for_our_ko'] = plain
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
    ap.add_argument("--progress", type=int, default=500)
    ap.add_argument("--opponent", default=None,
                    help="csv of an opponent deck; repeatable via commas")
    ap.add_argument("--control", action="store_true",
                    help="neutralise BOTH arms: the noise floor of this very run")
    ap.add_argument("--census", action="store_true",
                    help="how often the reading changes a verdict (run this first)")
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

    label_c = "con la lectura" + (" (NEUTRALIZADO: control)" if args.control else "")

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
