"""Two-arm gate for "the last bridge of a line is not fodder", isolated to THAT
reading and nothing else in the working tree.

THE RULE. A cost paid in cards from hand -- the Ultra Ball's two, a forced
discard -- prices an evolution piece against the BOARD: `_evo_copies_usable`
calls a link with no body under it zero usable copies, and the ladders hand the
surplus band to every copy in hand once there is more than one. Both readings
are right about a copy THE DECK CAN REPLACE and wrong about the last ones, and
the asymmetry is the whole rule: a missing seat is a card a search still buys,
while a bridge in the discard is gone from every zone a search reaches, and the
top of its line becomes cardboard everywhere at once.

`_evo_bridge_last_copies` asks the four questions that separate the two cases --
middle link, not already worn, its hand copies are the last reachable ones, and
the line's top and Basic are both still live -- and it names no card: the stages
come from `EVO_LINES`, so the Dipplin of the Applin line is covered on exactly
the same terms as the Bayleef of the Meganium one.

THE BOARD IT COMES FROM (user, `records/registro_006_pasos_047_hasta_073.json`
step 47, episode 93159383 vs Marnie -- LOST). Our turn 6, prizes 6-6, hand
{Bayleef, Bayleef, Ultra Ball}, and a menu of exactly two options: play the Ultra
Ball or end. The Ultra Ball's cost of two could be paid with nothing but both
Bayleef -- the deck's only bridge to the Meganium whose *Wild Growth* is this
deck's energy engine -- and it paid it, to fetch a Meowth ex. The two Bayleef sat
in the discard from step 49 to step 190, the last of the game. A Meganium reached
hand fourteen steps later and stayed for 127 of the game's 191 steps; the
Chikorita it needed was benched on that same turn 6 under our own Forest of
Vitality, which lets a Grass Pokemon evolve the turn it is played -- so
Chikorita -> Bayleef -> Meganium was one turn's work -- and it was still there,
unevolved, when the game ended.

WHAT THE READING COSTS, stated before the number exists. It makes a hand
POORER: a bridge the cost can no longer eat is one card less of surplus, and
`_ub_cancel_no_surplus` then cancels an Ultra Ball that would otherwise have been
played. On the very board above the cancelled Ultra Ball is the whole turn --
Ultra Ball -> Meowth ex -> Last-Ditch -> Lillie's Determination, an eight-card
refill -- so this is not a free protection and the gate is what arbitrates it.
The census measures the exposure: 1.55 last-bridge boards per self-play game,
of which 0.11 per game cross the threshold and cancel a play.

WHY NOT `selfplay.py --base HEAD`. The baseline it exports is the git ref, and
this working tree carries other work: the delta would answer "everything
uncommitted", not "this reading". Both arms here are the SAME tree loaded twice,
with `LAST_BRIDGE_IS_NOT_FODDER` switched off in one of them.

THE CRITERION, WRITTEN BEFORE THE NUMBER EXISTS.

  * run `--census` FIRST, and read it against the gate's own resolution.
  * ALWAYS run `--control` at the same n. Both arms neutralised is the same code
    twice, so whatever separation it shows is that run's noise floor -- and on
    this project the Marnie floor has measured 1.50 points at z=3.13 with
    identical code ([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]]).
    A delta that does not clear its own control is not a delta.
  * A LOSS that clears the floor orders the REVERT, and unlike most readings on
    this project that outcome is live here: the rule spends tempo for a card, so
    it can genuinely be wrong.
  * NEUTRAL orders the MARK, not the revert: the change is a strict no-op
    wherever the deck still holds a copy of the link, which the frozen corpus
    confirms (ONE flip, and it is two cards swapping places inside a single
    discard ranking that takes both).

WHAT IT MEASURED (15 August 2026, n=1000 on each of the four lists, so 4000
games an arm). The winrate half of this question is NOT RESOLVABLE at this
exposure, and the four rows are what says so rather than any one of them:

    regla completa        -1.10 pp   (z=-1.78 p=0.075)
    solo el descarte      -0.20 pp   (z=-0.34 p=0.736)
    solo la Ultra Ball    -0.10 pp   (z=-0.16 p=0.869)
    --control             -0.35 pp   (z=-0.57 p=0.572)

Read alone, the first row looks like a loss with the sign consistent across all
four lists, and the honest first reading of it was exactly that. THE SPLIT
REFUTES IT. Neither half reproduces the whole, and on two lists they do not even
point the same way as it:

    marnie_grimmsnarl     completa -1.70   descarte +1.50   busqueda +2.00
    crustle_kangaskhan    completa -1.70   descarte -2.60   busqueda -2.80

The halves are nested inside the whole -- every board the discard arm changes,
the full arm changes too -- so a whole that sits 3.2 points BELOW one half on
Marnie, and 1.1 points ABOVE both halves on Crustle, is not measuring the rule.
It is measuring the run. That is the wall
[[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]]
describes: on Marnie identical code has read 1.50 points at z=3.13.

So the pre-registered criterion resolves to NEUTRAL -> MARK, not to the revert
the first row on its own would have ordered. What the change enters on is the
census (1.55 last-bridge boards a game, 0.11 of them cancelling a play) and the
corpus (one flip, and it is two cards swapping places in a menu that takes
both). A LOSS still orders the revert here -- the rule genuinely spends tempo
for a card -- but this gate did not find one, and the four rows are kept
together so nobody re-reads the first one alone.

Usage:
    python utils/gate_the_last_bridge_is_not_fodder.py --census
    python utils/gate_the_last_bridge_is_not_fodder.py --games 1000
    python utils/gate_the_last_bridge_is_not_fodder.py --games 1000 --control
    python utils/gate_the_last_bridge_is_not_fodder.py --games 1000 --half discard
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

# THE POPULATION IS OUR OWN HAND, not a matchup: the reading fires on the shape
# of our deck's lines and never asks who is across the table. So the list here is
# a SPREAD rather than a target -- the deck that produced the board, two decks
# that pressure the hand from opposite directions (a disruptor that forces the
# discard, a wall that makes the Meganium line the answer) and a control.
DEFAULT_DECKS = (
    "deck/opponents/marnie_grimmsnarl.csv",
    "deck/opponents/alakazam.csv",
    "deck/opponents/crustle_kangaskhan.csv",
    "deck/opponents/dragapult.csv",
)


def _lines_ns(agent_module):
    """`ptcg.cards.lines` as THIS arm owns it, reached by reference.

    NOT through `sys.modules`: `selfplay.load_agent` deletes the arm's `ptcg`
    branch and restores the ambient tree as soon as the load finishes, so a
    lookup by name hands back a copy nobody plays with -- and a gate that
    neutralises the wrong copy measures its own noise floor and calls it a
    result. main.py opens with `from ptcg.decision.ultra_ball import *`, so the
    arm's own `lines` namespace is two `__globals__` hops from `agent`.
    """
    g = agent_module.agent.__globals__
    ub = g['_ub_real_fodder'].__globals__
    return ub['_evo_bridge_last_copies'].__globals__


def neutralise(agent_module):
    """Switch the reading off in `agent_module`, permanently, in place.

    ONE assignment covers both call sites: the Ultra Ball's cost count
    (`_ub_real_fodder`) and the forced-discard ladder
    (`DISCARD_LINK_LAST_BRIDGE`) both go through `_evo_bridge_last_copies`, and
    it returns False for everything while the switch is off.
    """
    _lines_ns(agent_module)['LAST_BRIDGE_IS_NOT_FODDER'] = False
    return agent_module


def half(agent_module, which):
    """Leave only ONE of the two call sites reading, in place.

    THE TWO HALVES DO NOT COST THE SAME, and the full gate cannot tell them
    apart. The forced-discard ladder only ever RE-RANKS a menu that is going to
    take `minCount` cards whatever the scores say, so it never costs a play; the
    Ultra Ball's cost count makes the hand POORER, and a hand that can no longer
    pay out of surplus cancels the search (`_ub_cancel_no_surplus`) -- 0.06 to
    0.11 times a game by the census. If the reading loses, that is where the
    tempo went, and the split is the measurement that says so.

    It is done by rebinding the name inside ONE consumer's namespace rather than
    by adding a second switch to the source: the two call sites import the
    predicate by name, so each namespace can be neutralised on its own without
    the agent carrying a knob that exists only for a gate.
    """
    g = agent_module.agent.__globals__
    ub = g['_ub_real_fodder'].__globals__
    card = g['score_option'].__globals__['card'].__dict__
    off = (lambda *_a, **_k: False)
    if which == 'discard':               # only the ladder reads
        ub['_evo_bridge_last_copies'] = off
    elif which == 'search':              # only the Ultra Ball's cost reads
        card['_evo_bridge_last_copies'] = off
    else:
        raise SystemExit(f"mitad desconocida: {which}")
    return agent_module


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    The gate has been blind before (`selfplay --base` used to share the whole
    `ptcg` package between arms, so any change there measured exactly zero), so
    the arms are asked directly for the flag the run will compare against -- and
    asked through the same reference walk `neutralise` writes through, so a
    resolution bug cannot pass this check and fail the measurement.
    """
    if candidate is base:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    _cand = _lines_ns(candidate)['LAST_BRIDGE_IS_NOT_FODDER']
    _base = _lines_ns(base)['LAST_BRIDGE_IS_NOT_FODDER']
    if _base:
        raise SystemExit("el brazo baseline NO esta neutralizado: no hay nada que medir")
    if _cand is bool(control):
        raise SystemExit("el brazo candidato no esta como dice estar "
                         f"(control={bool(control)}, lectura={_cand})")
    print(f"procedencia OK (candidato {'NEUTRALIZADO: control' if control else 'con la lectura'}, "
          f"baseline sin ella)\n", flush=True)


def census(games, decks, progress):
    """HOW OFTEN THE BOARD THE READING IS ABOUT ACTUALLY HAPPENS.

    Three nested numbers, and the gaps between them are the point:

      asked     line links priced by a cost at all;
      bridge    ...of those, the ones whose copies in hand are the LAST ones any
                zone a search still reaches, on a line still worth finishing.
                Everywhere above this line the two arms are identical;
      veto      ...and of THOSE, the ones where the poorer hand crosses the
                Ultra Ball's threshold of two and cancels the play. This is the
                only number that costs tempo, and it is the one the winrate half
                of this gate is actually measuring.
    """
    from opponent_bot import OpponentBot

    agent = sp.load_agent(_ROOT / "main.py", "arm_census")
    counts = Counter()

    g = agent.agent.__globals__
    ub_ns = g['_ub_real_fodder'].__globals__
    lines_ns = ub_ns['_evo_bridge_last_copies'].__globals__
    card_ns = g['score_option'].__globals__['card'].__dict__
    if 'LAST_BRIDGE_IS_NOT_FODDER' not in lines_ns:
        raise SystemExit("el censo no alcanza al interruptor: mediria cero")

    plain = ub_ns['_evo_bridge_last_copies']
    plain_fodder = ub_ns['_ub_real_fodder']

    def counted(card_id, hand_counts, field_counts, reachable_counts):
        out = plain(card_id, hand_counts, field_counts, reachable_counts)
        counts['asked'] += 1
        if out:
            counts['bridge'] += 1
        return out

    def counted_fodder(ctx, protegida):
        out = plain_fodder(ctx, protegida)
        prev = lines_ns['LAST_BRIDGE_IS_NOT_FODDER']
        lines_ns['LAST_BRIDGE_IS_NOT_FODDER'] = False
        try:
            without = plain_fodder(ctx, protegida)
        finally:
            lines_ns['LAST_BRIDGE_IS_NOT_FODDER'] = prev
        if without >= 2 > out:
            counts['veto'] += 1
        return out

    ub_ns['_evo_bridge_last_copies'] = counted
    card_ns['_evo_bridge_last_copies'] = counted
    ub_ns['_ub_real_fodder'] = counted_fodder
    try:
        total = vetoes = 0
        for rel in decks:
            their = sp.read_deck(_ROOT / rel)
            counts.clear()
            sp.torneo(agent, OpponentBot(), games,
                      progress=progress or None, deck_base=their)
            asked, bridge, veto = counts['asked'], counts['bridge'], counts['veto']
            total += bridge
            vetoes += veto
            print(f"{Path(rel).stem:32s} enlaces {asked:8d} "
                  f"({asked / games:8.2f}/partida)   ULTIMO PUENTE "
                  f"{bridge:6d} ({bridge / games:6.2f}/partida)   "
                  f"VETO {veto:5d} ({veto / games:5.2f}/partida)", flush=True)
        n = games * len(decks)
        print(f"\nCENSO DE DISPARO: {total / n:.2f} tableros de ultimo puente y "
              f"{vetoes / n:.2f} Ultra Ball canceladas por partida de media.")
        if vetoes / n < 0.01:
            print("AVISO: el evento es RARO. Con una exposicion asi el gate de "
                  "self-play puede no resolver la diferencia por muchas partidas "
                  "que juegue; el informe honesto es este censo, no un winrate.")
    finally:
        ub_ns['_evo_bridge_last_copies'] = plain
        card_ns['_evo_bridge_last_copies'] = plain
        ub_ns['_ub_real_fodder'] = plain_fodder
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
                    help="how often the board happens at all (run this first)")
    ap.add_argument("--half", choices=("discard", "search"), default=None,
                    help="leave only ONE call site reading: the forced-discard "
                         "ladder ('discard', which never cancels a play) or the "
                         "Ultra Ball's cost count ('search', which does)")
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
    # AFTER the provenance check, on purpose: `half` rebinds
    # `_evo_bridge_last_copies` inside one consumer, and that name is the hop
    # `_lines_ns` walks through to find the switch it verifies.
    if args.half and not args.control:
        half(candidate, args.half)
        print(f"MITAD medida: {args.half}\n", flush=True)

    tot_c = tot_b = 0
    for rel in decks:
        their = sp.read_deck(_ROOT / rel)
        c = sp.torneo(candidate, OpponentBot(), args.games,
                      progress=args.progress or None, deck_base=their)
        b = sp.torneo(base, OpponentBot(), args.games,
                      progress=args.progress or None, deck_base=their)
        cw, bw = c['candidate'], b['candidate']
        tot_c += cw
        tot_b += bw
        d, z, p = wilson_delta(cw, args.games, bw, args.games)
        # The PRIZE DIFFERENTIAL is the metric with resolution left once the
        # winrate saturates against the bot (docs/improving-the-agent.md), and
        # against a thin population it is the one that moves first.
        _cp = (c['premios_candidato'] - c['premios_base']) / max(1, c['partidas_con_premios'])
        _bp = (b['premios_candidato'] - b['premios_base']) / max(1, b['partidas_con_premios'])
        print(f"{Path(rel).stem:32s} con {cw:5d}/{args.games}  sin {bw:5d}/{args.games}  "
              f"delta {100 * d:+6.2f} pp  (z={z:+5.2f} p={p:.3f})   "
              f"premios {_cp:+.2f} vs {_bp:+.2f} ({_cp - _bp:+.2f})", flush=True)

    n = args.games * len(decks)
    d, z, p = wilson_delta(tot_c, n, tot_b, n)
    print(f"\nTOTAL  con {tot_c}/{n}  sin {tot_b}/{n}  "
          f"delta {100 * d:+.2f} pp  (z={z:+.2f} p={p:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
