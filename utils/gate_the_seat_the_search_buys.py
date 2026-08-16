"""Two-arm gate for "the seat a search buys is evolvable today", isolated to
THAT rule and nothing else in the working tree.

The rule: with Forest of Vitality available, the Poke Pad's ladders count the
BASIC still in the deck whose upper links the hand already holds. Two halves,
one sentence -- `rush_seat_the_hand_completes` in `_RULES_PP_FETCH` (which card
the Pad brings) and `_pp_seat_the_hand_completes` inside `_pp_evo_value` (what
the Pad is worth). Before it, that board fell through to `fb_applin` (650), the
lowest rung the fetch has, and lost to `fb_chikorita` (800).

WHY NOT `selfplay.py --base HEAD`: the same reason `gate_the_search_buys.py`
gives at length -- the git baseline carries every other uncommitted change, so
the delta answers "the working tree", not "this rule". Both arms here are the
SAME tree loaded twice, with the two halves switched off in one of them.

NOTHING ON DISK IS REWRITTEN. The neutralisation happens on the loaded module
objects, so this is safe to leave running while other files are edited.

BOTH HALVES ARE NEUTRALISED TOGETHER, and that is deliberate. They are one
reading with two call sites: switching off only the fetch would leave an arm
that pays 23000 for a Pad and then brings back the wrong card, which is a board
neither revision produces and therefore not a thing worth measuring.

READ THE CENSUS FIRST (`--census`). It is the ceiling of any winrate effect.

Usage:
    python utils/gate_the_seat_the_search_buys.py --census
    python utils/gate_the_seat_the_search_buys.py --games 1500
    python utils/gate_the_seat_the_search_buys.py --games 1500 --control
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

# The rule needs our own Forest on the field and a line half-held in hand, which
# is a DEVELOPMENT board and not a matchup one -- it happens against everyone.
# So the arms are played against a spread rather than against the decks a
# targeted rule would name, and there is no "control deck" that should show zero.
SPREAD_DECKS = (
    "deck/opponents/dragapult.csv",
    "deck/opponents/alakazam.csv",
    "deck/opponents/crustle_kangaskhan.csv",
)


def _pp_globals(agent_module):
    """The namespace of the agent's OWN `ptcg.decision.poke_pad`.

    `sp.load_agent` restores `sys.modules`, so the arm's copy of the module is
    NOT reachable by name -- `sys.modules['ptcg.decision.poke_pad']` is either
    absent or the outer process's. It is reached through an object the arm
    holds: a function's `__globals__` IS its module's dict, and rebinding a name
    in it is what every caller of that module resolves against, including the
    copy `ptcg/turn/options/play.py` imported.
    """
    return agent_module._score_poke_pad_play.__globals__


def neutralise(agent_module):
    """Switch both halves off in `agent_module`, permanently, in place.

    It is the name INSIDE `ptcg.decision.poke_pad` that has to be rebound: the
    ladder and `_pp_evo_value` both call `_pp_seat_the_hand_completes` /
    `_pp_fetch_seat_steps` through that module's own globals.
    """
    pp = _pp_globals(agent_module)
    pp['_pp_seat_the_hand_completes'] = lambda c: (0, None)
    pp['_pp_fetch_seat_steps'] = lambda c: 0
    return agent_module


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    Asked on the record's own board (registro_003 step 22, minus the item lock
    that made it unplayable there): Forest on the field, Dipplin and Hydrapple
    ex in hand, nothing of the line in play, a seat free.
    """
    class _Stub:
        turn = 5

    def fires(agent):
        pp = _pp_globals(agent)
        agent.AGENT_STATE.we_go_first = True
        agent.AGENT_STATE.forest_in_play = True
        agent.AGENT_STATE.meganium_in_play = False
        ctx = pp['_CtxPPFetch'](agent.Applin,
                                {agent.Dipplin: 1, agent.Hydrapple_ex: 1},
                                {agent.Teal_Mask_Ogerpon_ex: 3}, 2, _Stub())
        return pp['_pp_fetch_seat_steps'](ctx) >= 1

    if candidate.score_option is base.score_option:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if fires(candidate) is bool(control):
        raise SystemExit("el brazo candidato no lleva la regla que dice llevar")
    if fires(base):
        raise SystemExit("el brazo baseline lleva la regla: no hay nada que medir")
    print(f"procedencia OK (candidato {'NEUTRALIZADO: control' if control else 'con la regla'}, "
          f"baseline sin ella)\n", flush=True)


def census():
    """How many decisions of the frozen corpus does the rule change at all?"""
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
                         "Omitted: the spread in SPREAD_DECKS")
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

    decks = (args.opponent.split(",") if args.opponent else list(SPREAD_DECKS))
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
