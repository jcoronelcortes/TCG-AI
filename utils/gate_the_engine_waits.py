"""Two-arm gate for "the engine waits for the turn that can run it", isolated to
THAT rule and nothing else in the working tree.

The rule: the ANTI-STERILE-TURN NET of `ptcg/turn/finalize.py` resurrects a
vetoed Ultra Ball at 200 to dig out a body whenever the turn would otherwise
die. `_ub_engine_waits_for_tomorrow` drops its BASIC branch when the board is
already the engine board of `_ub_engine_refresh_pivot` and the ONLY thing
missing is the Supporter slot this turn has spent -- because that slot comes
back by itself, and the same Ultra Ball then buys Meowth ex -> Last-Ditch ->
a refill Supporter -> a whole new hand instead of an inert body. Written off
`records/registro_002_pasos_011_hasta_018.json` (episode 91529732, turn 2 vs
Cynthia's Garchomp ex, LOST), see
`tests/test_the_engine_waits_for_the_turn_that_can_run_it.py`.

WHY NOT `selfplay.py --base HEAD`. Because the baseline it exports is the git
ref, and the working tree normally carries other work in progress: the delta
then answers "everything uncommitted", not "this rule". Here both arms are the
SAME tree, loaded twice, with the predicate switched off in one of them.

NOTHING ON DISK IS REWRITTEN. The neutralisation happens on the loaded module
object, so this harness is safe to leave running while other files are edited.

READ THE CENSUS FIRST (`--census`). It counts how often the rule changes a
decision at all, and that number is the ceiling of any effect. A rule written
off one record usually turns out rarer than fifty games can see; when the census
is zero the honest report is "the corpus proves it costs nothing elsewhere", not
a winrate.

ALWAYS RUN `--control` AT THE SAME N as the real arms. Both arms neutralised is
the same code twice, so whatever separation it shows is that run's noise floor,
measured rather than assumed. A delta that does not clear it is not a delta.

Usage:
    python utils/gate_the_engine_waits.py --census
    python utils/gate_the_engine_waits.py --games 6000 --opponent deck/opponents/<x>.csv
    python utils/gate_the_engine_waits.py --games 6000 --opponent <x> --control
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

# The rule is deck-agnostic. What it needs to be exercised is a matchup where
# our turn 2 goes second, spends its Supporter and cannot attack -- which is
# every deck that pressures early. These are the ones the record's own family of
# turn-2 findings came from.
DEFAULT_DECKS = (
    "deck/opponents/cynthia_garchomp.csv",       # the record's own matchup
    "deck/opponents/crustle_kangaskhan.csv",
)


def _finalize_module(agent_module):
    """The `ptcg.turn.finalize` object THIS arm is really calling.

    `sp.load_agent` restores `sys.modules` after loading, so the agent's own
    `ptcg` tree is not reachable by name -- it is reached through the objects
    the agent holds. It is the name INSIDE `finalize` that has to be rebound:
    `from ... import` binds a copy.
    """
    return agent_module.finalizar.__globals__


def neutralise(agent_module):
    """Switch the rule off in `agent_module`, permanently, in place."""
    _finalize_module(agent_module)['_ub_engine_waits_for_tomorrow'] = (
        lambda *a, **k: False)
    return agent_module


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    The gate has been blind before (`selfplay --base` used to share the whole
    `ptcg` package between arms, so any change there measured exactly zero), and
    "neutral" is the verdict that orders a revert in this project. So the arms
    are asked directly, on the record's own shape: the Supporter slot spent on a
    board the engine predicate accepts.
    """
    def fires(agent):
        """Does THIS arm's net still ask the question?

        The board is reduced to the only two things the predicate reads before
        delegating: a spent Supporter slot, and an engine that would say yes.
        The engine itself is stubbed inside the predicate's OWN module globals
        (the arm's `ptcg.decision.ultra_ball`), so the answer isolates the rule
        from whatever the engine happens to think of a real board.
        """
        eng = _finalize_module(agent)['_ub_engine_waits_for_tomorrow']
        ctx = SimpleNamespace(state=SimpleNamespace(supporterPlayed=True))
        own = getattr(eng, '__globals__', None)
        if own is None or '_ub_engine_refresh_pivot' not in own:
            return bool(eng(ctx))              # the neutralised lambda
        saved = own['_ub_engine_refresh_pivot']
        own['_ub_engine_refresh_pivot'] = lambda c: True
        try:
            return bool(eng(ctx))
        finally:
            own['_ub_engine_refresh_pivot'] = saved

    if candidate.finalizar is base.finalizar:
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
    print(f"CENSO sobre el corpus congelado: {changed} de {seen} "
          f"decisiones ({100 * changed / seen:.2f}%) en {len(records)} registros")
    for line in touched:
        print(line)
    if not changed:
        print("\nCERO. El evento no ocurre en estas partidas: la regla es un "
              "no-op historico y ninguna cantidad de self-play va a resolverle "
              "un winrate. Lo que si dice el corpus es que no se esta pagando "
              "con dano en otro sitio.")
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
                    help="csv of an opponent deck; repeatable via commas")
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
