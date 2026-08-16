"""Two-arm gate for "the gust that ends the game is not a jam", isolated to
THAT rung and nothing else in the working tree.

The rule: `gust_wins_the_game` in `_ADJUST_GUST_NUISANCE`. When our active
cannot attack this turn, `ptcg/turn/options/card.py` aims the Boss's Orders with
the JAM ladder, which is prize-blind by construction -- its only knockout-aware
rung is gated on `line_rank >= 1`, so a two-prize BASIC we can knock out is
invisible to it. The rung says the thing the offensive chain already says: a
knockout that takes our LAST prizes is not a preference to be outbid.

Origin: `records/registro_010_pasos_129_hasta_137.json` step 131 vs Dragapult.
Two prizes left, a Meganium stuck at two of the four energies Petal Dance costs
but able to pay its retreat, a Teal Mask Ogerpon ex at eight effective energies
on the bench, and a bare Fezandipiti ex on theirs at 210 HP -- 270 damage, two
prizes, the game. The agent gusted a Drakloak (9050 as a jam) over the ex (600),
took one prize and played on.

WHY NOT `selfplay.py --base HEAD`: the same reason every gate in this directory
gives -- the git baseline carries every other uncommitted change, so the delta
answers "the working tree" and not "this rung". Both arms here are the SAME tree
loaded twice, with the rung removed from one of them.

NOTHING ON DISK IS REWRITTEN. The neutralisation mutates the loaded list object
in place, so this is safe to leave running while other files are edited.

READ THE CENSUS FIRST (`--census`). It is the ceiling of any winrate effect, and
for this rung the ceiling is expected to be LOW: it needs a turn that is
simultaneously the last one (`prizes >= my_prize`), played with a stuck active,
and holding a Boss's Orders. Its value is not frequency -- it is that every
firing is a game won a turn earlier, which is the one thing a rare rule can be
worth. A census this thin is reported as a census, not as a winrate.

Usage:
    python utils/gate_the_gust_that_ends_the_game.py --census
    python utils/gate_the_gust_that_ends_the_game.py --games 1500
    python utils/gate_the_gust_that_ends_the_game.py --games 1500 --control
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

RULE = "gust_wins_the_game"

# The rung reads our prize count, our bench's damage and their body's HP. It
# names no matchup, so the arms are played against a spread rather than against
# the decks a targeted rule would name. The Dragapult list is the record's own
# and goes first; the other two are there so a deck-shaped effect would show up
# as a disagreement between rows.
SPREAD_DECKS = (
    "deck/opponents/dragapult.csv",
    "deck/opponents/alakazam.csv",
    "deck/opponents/crustle_kangaskhan.csv",
)


def _nuisance_list(agent_module):
    """The arm's OWN `_ADJUST_GUST_NUISANCE`, the object every caller holds.

    `sp.load_agent` restores `sys.modules`, so the arm's copy of
    `ptcg.decision.boss_orders` is not reachable by name. It is reached through
    the agent module, which re-exports the list -- and it is the SAME list
    object `ptcg/turn/options/card.py` imported, so mutating it in place reaches
    the resolver without rebinding anything anywhere.
    """
    return agent_module._ADJUST_GUST_NUISANCE


def neutralise(agent_module):
    """Remove the rung from `agent_module`, permanently, in place."""
    rules = _nuisance_list(agent_module)
    rules[:] = [a for a in rules if a.name != RULE]
    return agent_module


def carries_the_rule(agent_module):
    return any(a.name == RULE for a in _nuisance_list(agent_module))


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent."""
    if candidate.score_option is base.score_option:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if _nuisance_list(candidate) is _nuisance_list(base):
        raise SystemExit("los dos brazos comparten la lista de ajustes: "
                         "neutralizar uno neutraliza los dos")
    if carries_the_rule(candidate) is bool(control):
        raise SystemExit("el brazo candidato no lleva la regla que dice llevar")
    if carries_the_rule(base):
        raise SystemExit("el brazo baseline lleva la regla: no hay nada que medir")
    print(f"procedencia OK (candidato {'NEUTRALIZADO: control' if control else 'con la regla'}, "
          f"baseline sin ella)\n", flush=True)


def census():
    """How many decisions of the frozen corpus does the rung change at all?"""
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
              "corpus limpio, no un winrate. Lo que la regla compra no es "
              "frecuencia: es que cada disparo cierra la partida un turno antes.")
    return 0


def live_census(games, decks, progress):
    """How often does the SITUATION arise in games actually played?

    The frozen-corpus census answers "how many of these 3580 recorded decisions
    move", and for a rung that needs a match-point turn it answers zero without
    saying whether the board ever happens. This one plays fresh games and counts
    the firings of the rung's own guard -- `wins_now` while the jam ladder is
    the one resolving -- which is the exposure the winrate gate would have to
    resolve, measured instead of assumed.

    It counts the guard and NOT the flip, deliberately: a firing where the jam
    ladder happened to prefer the same body is still a turn on which the game
    was one gust from over, and lumping the two together is what turns a
    frequency into a claim it cannot support. The flips are the corpus's job.

    THE DENOMINATOR IS COUNTED TOO, and that is the half a zero needs. The
    rung's guard is asked once per candidate the JAM ladder prices, so counting
    the calls and the hits separately tells apart the two ways of reading a
    zero: "the ladder runs and never at match point" from "the ladder never
    runs here at all". An instrument that cannot say which it means is not
    reporting a frequency, it is reporting its own blind spot.
    """
    from opponent_bot import OpponentBot

    agent_module = sp.load_agent(_ROOT / "main.py", "arm_live")
    rung = next((a for a in _nuisance_list(agent_module) if a.name == RULE), None)
    if rung is None:
        raise SystemExit("el arbol cargado no lleva la regla: nada que censar")

    fired = [0]
    priced = [0]
    real_when = rung.when

    def counting_when(c, s):
        priced[0] += 1
        hit = real_when(c, s)
        if hit:
            fired[0] += 1
        return hit

    rung.when = counting_when

    total_games = 0
    for rel in decks:
        their = sp.read_deck(_ROOT / rel)
        before_f, before_p = fired[0], priced[0]
        sp.torneo(agent_module, OpponentBot(), games,
                  progress=progress or None, deck_base=their)
        total_games += games
        print(f"{Path(rel).stem:30s} {fired[0] - before_f:5d} disparos / "
              f"{priced[0] - before_p:6d} candidatos tasados por la escalera de "
              f"estorbo en {games} partidas "
              f"({(fired[0] - before_f) / games:.3f} y "
              f"{(priced[0] - before_p) / games:.2f} por partida)", flush=True)

    print(f"\nCENSO EN VIVO: {fired[0]} disparos en {total_games} partidas "
          f"({fired[0] / total_games:.3f}/partida) sobre {priced[0]} candidatos "
          f"tasados por la escalera de estorbo "
          f"({priced[0] / total_games:.2f}/partida)")
    print("Un disparo es un turno en el que la escalera de ESTORBO estaba "
          "resolviendo el gusteo y habia en su banca un cuerpo cuyo KO cerraba "
          "la partida. No todos cambian la eleccion; los que la cambian los "
          "cuenta el corpus. Si el denominador tambien es cero, lo que el censo "
          "dice es que el gusteo no llega a esa escalera en estas partidas, no "
          "que la regla sea inerte.")
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
                    help="how many corpus decisions the rung changes (run this first)")
    ap.add_argument("--live-census", action="store_true",
                    help="how often the SITUATION arises in games played now")
    args = ap.parse_args(argv)

    if args.census:
        return census()

    if args.live_census:
        return live_census(
            args.games,
            args.opponent.split(",") if args.opponent else list(SPREAD_DECKS),
            args.progress)

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
