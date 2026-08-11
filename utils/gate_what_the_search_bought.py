"""Two-arm gate for "the cost does not eat what the search ALREADY bought",
isolated to THAT rule and nothing else in the working tree.

The rule: when the discard menu is the cost of one of OUR OWN cards, a card an
earlier search of the SAME TURN put into this hand (`AGENT_STATE
._bought_this_turn`, taken off the MOVE_CARD logs) is kept at
`DISCARD_WHAT_THE_SEARCH_ALREADY_BOUGHT` instead of being priced by ladders that
cannot tell a purchase from a draw. Sibling of `gate_the_search_buys.py`, which
covers the card a search is ABOUT to buy.

WHY NOT `selfplay.py --base HEAD`. Because the baseline it exports is the git
ref, and the working tree normally carries other work in progress: the delta
then answers "everything uncommitted", not "this rule". Here both arms are the
SAME tree, loaded twice, with the predicate switched off in one of them.

NOTHING ON DISK IS REWRITTEN. The neutralisation happens on the loaded module
object, so this harness is safe to leave running while other files are edited.

READ THE CENSUS FIRST (`--census`). It counts how often the rule changes a
decision at all, and that number is the ceiling of any effect. On the frozen
corpus it is **0 of 3 580** -- fifty games in which no purchase of ours was ever
in danger, which is the honest reading of a rule written off ONE record: the
event is rarer than the corpus can see, and no number of self-play games will
resolve a winrate for it. What the corpus DOES buy is the other half: the rule
is a strict no-op on every historical decision, so it cannot be paying for
itself with damage elsewhere (`test_the_frozen_corpus_runs_on_a_clean_checkout`
is the gate for that, and it is green).

The two flips the rule produces WITHOUT its spares guard are the measurement
worth keeping from this tool -- see `--census --no-spares-guard`:

    registro_020 (Crustle wall) t4: discards a **Tapu Bulu** instead of a Grass
    registro_031 (Garchomp)     t6: discards a **Xerosic** instead of a Grass

Both are the same mistake in reverse: protecting the physical copy a search
recovered, while identical twins sat in the same hand, moved the cost onto a
card that mattered. That is why the purchase is a COUNT and not a serial.

ALWAYS RUN `--control` AT THE SAME N as the real arms. Both arms neutralised is
the same code twice, so whatever separation it shows is that run's noise floor,
measured rather than assumed. A delta that does not clear it is not a delta.

Usage:
    python utils/gate_what_the_search_bought.py --census
    python utils/gate_what_the_search_bought.py --census --no-spares-guard
    python utils/gate_what_the_search_bought.py --games 15000 --opponent deck/opponents/crustle_kangaskhan.csv
    python utils/gate_what_the_search_bought.py --games 15000 --opponent ... --control
"""

import argparse
import math
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402

# The rule is deck-agnostic, so the arms play the decks where a wasted search
# costs most: an ex-immune wall turns every Ultra Ball into a two-card payment
# for the one body that can break through.
DEFAULT_DECKS = (
    "deck/opponents/crustle_kangaskhan.csv",
    "deck/opponents/crustle_great_tusk_nz.csv",
    "deck/opponents/crustle_cubchoo_spheal.csv",
)


def _card_module(agent_module):
    """The `ptcg.turn.options.card` object THIS arm is really calling.

    `sp.load_agent` restores `sys.modules` after loading, so the agent's own
    `ptcg` tree is not reachable by name -- it is reached through the objects
    the agent holds. It is the name INSIDE `card` that has to be rebound, not
    the one in `ptcg.cards.scoring`: `from ... import` binds a copy.
    """
    return agent_module.score_option.__globals__['card']


def neutralise(agent_module):
    """Switch the rule off in `agent_module`, permanently, in place."""
    _card_module(agent_module)._purchase_of_this_turn = lambda *a, **k: 0
    return agent_module


def drop_spares_guard(agent_module):
    """Keep the rule but make it protect the SERIAL instead of the COUNT.

    Reports every copy of the card as bought, which is what "protect the copy
    the search brought" degrades to once the twins in hand are indistinguishable
    to the scorer. This is the arm that produced the two flips in the docstring.
    """
    card = _card_module(agent_module)
    real = card._purchase_of_this_turn

    def _all_copies(card_id, hand, bought_serials):
        n = real(card_id, hand, bought_serials)
        return sum(1 for c in hand
                   if getattr(c, 'id', None) == card_id) if n else 0

    card._purchase_of_this_turn = _all_copies
    return agent_module


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    The gate has been blind before (`selfplay --base` used to share the whole
    `ptcg` package between arms, so any change there measured exactly zero), and
    "neutral" is the verdict that orders a revert in this project. So the arms
    are asked directly, on the record's own shape: one copy in hand, bought.
    """
    def fires(agent):
        hand = [SimpleNamespace(id=7, serial=87)]
        return _card_module(agent)._purchase_of_this_turn(7, hand, {87}) > 0

    if candidate.score_option is base.score_option:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if fires(candidate) is bool(control):
        raise SystemExit("el brazo candidato no lleva la regla que dice llevar")
    if fires(base):
        raise SystemExit("el brazo baseline lleva la regla: no hay nada que medir")
    print(f"procedencia OK (candidato {'NEUTRALIZADO: control' if control else 'con la regla'}, "
          f"baseline sin ella)\n", flush=True)


def census(no_spares_guard=False):
    """How many decisions of the frozen corpus does the rule change at all?

    The ceiling of any winrate effect. It replays the committed bundle through
    both arms and compares choice by choice.
    """
    import golden_corpus as gc

    candidate = sp.load_agent(_ROOT / "main.py", "arm_with")
    if no_spares_guard:
        drop_spares_guard(candidate)
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
    label = " (SIN la guarda de sobrantes)" if no_spares_guard else ""
    print(f"CENSO sobre el corpus congelado{label}: {changed} de {seen} "
          f"decisiones ({100 * changed / seen:.2f}%) en {len(records)} registros")
    for line in touched:
        print(line)
    if not changed:
        print("\nCERO. El evento no ocurre en estas cincuenta partidas: la regla "
              "es un no-op historico y ninguna cantidad de self-play va a "
              "resolverle un winrate. Lo que si dice el corpus es que no se "
              "esta pagando con dano en otro sitio.")
    elif seen and changed / seen < 0.005:
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
                         "Omitted: the three ex-immune walls")
    ap.add_argument("--control", action="store_true",
                    help="neutralise BOTH arms: the noise floor of this very run")
    ap.add_argument("--census", action="store_true",
                    help="how many corpus decisions the rule changes (run this first)")
    ap.add_argument("--no-spares-guard", action="store_true",
                    help="census the rule protecting the SERIAL instead of the "
                         "COUNT: the two flips that justify the guard")
    args = ap.parse_args(argv)

    if args.census:
        return census(no_spares_guard=args.no_spares_guard)

    from opponent_bot import OpponentBot

    candidate = sp.load_agent(_ROOT / "main.py", "arm_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "arm_without"))
    if args.control:
        neutralise(candidate)
    provenance(candidate, base, args.control)

    decks = (args.opponent.split(",") if args.opponent else list(DEFAULT_DECKS))
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
