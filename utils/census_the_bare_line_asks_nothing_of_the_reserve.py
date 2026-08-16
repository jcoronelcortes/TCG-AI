"""How often "their line is BARE" turns the Marnie engine ladder on by itself.

THE BOARD IT COMES FROM (episode 93683313 step 49, turn 7 vs Marnie -- game WON,
and the gust still went to the Morgrem; drawn out in full in
`tests/test_marnie_the_bare_line_asks_nothing_of_the_reserve.py`): Boss's Orders
already down, their line at ZERO energy (Impidimp active, Morgrem benched) and a
Munkidori carrying a Darkness two slots along. `marnie_engine_first` was false --
our reserve Ogerpon ex held two Grass, under its own attack cost, so it priced at
zero against a projected 320 -- and with the engine ladder down the plain stage
tier took the Morgrem at 9600 over the charged Munkidori at 6450.

The bench question is owed to `ex_preevo_takes_priority`, which demands a CHARGED
pre-evolution. With their whole line at zero that rung never fires, so there is
no 19500 to protect and the engine owes the gust to nobody:
`_marnie_line_is_bare` is the second way into `marnie_engine_first`.

WHAT IS BEING COUNTED. This switch neutralises ONLY the bare-line half of the
premise. The reserve question, the engine-vs-line reading it gates and the energy
split inside the ladder all keep their own files and their own switches
(`census_marnie_the_engine_before_the_line.py`,
`census_the_gust_reads_the_energy_not_the_hp.py`). The candidate arm drives the
game; a copy of the same tree with
`MARNIE_ENGINE_BARE_LINE_NEEDS_NO_RESERVE = False` -- the reserve question asked
on every board, which is the tree that let a bare Morgrem outbid the engine -- is
asked on every frame. Per one of OUR decisions:

    ours        decisions the agent took (the denominator)
    marnie      ...taken with `AGENT_STATE.op_is_marnie_deck` up
    gust        ...and the menu is a Boss's Orders TARGET select
    bare        ...and NO body of their line carried energy, which is the only
                shape either arm can disagree about
    flip        ...where the baseline arm brought up something ELSE. This is the
                population: the boards where the reading changes a decision

and the flips split so that a rule moving for some other reason cannot hide
inside the total:

    to_engine   the baseline took a body of their LINE, the candidate an engine
                body -- the record's own sentence
    in_engine   both took an engine body, a different one (a knock-on of the
                ladder's own order, not of this reading)
    other       a flip that is neither: a knock-on elsewhere, or the gust
                leaving the engine entirely

THE LEAKAGE HALF is the second row, against a list that is not Marnie's. The
whole reading hangs off `op_is_marnie_deck` through `marnie_engine_first`, so the
honest number there is ZERO and anything else is a rule reaching past its
matchup.

⚠️ THE CRITERION, written before this file was run and not moved afterwards:
`flip` at or above **0.01 per game** against the Marnie lists, and **0.00 per
game** on the list that is not Marnie's. Same bar as the sibling ladder, and for
the same reason: the parent reading (engine-before-the-line) was measured at 0.02
flips/game and is NOT a ceiling here -- this half fires exactly where the parent
did not -- but it is the right order of magnitude for a rung that needs a gust
menu, the Marnie matchup and an uncharged line all at once. A rate an order of
magnitude ABOVE it would be the alarming answer, not the good one: it would mean
the reading is firing on boards where their line is a real threat.

WHAT THE RECORDED GAMES SAID (16 agosto 2026, before any self-play):

    replay of every stored log   1 151 decisiones, 986 con el flag de Marnie,
                                 8 menus de gusteo -> **1 flip**, el del
                                 registro: Morgrem (idx 2) -> Munkidori
                                 CARGADO (idx 3).
    autopsy corpus, 25 rivales   4 285 observaciones -> **0 flips**. FUGA CERO.
    golden corpus                sin movimiento (`tests/test_golden_corpus.py`).

WHAT THIS FILE MEASURED (16 agosto 2026):

    vs marnie_grimmsnarl   n=200: 25 158 decisiones, 134 menus de gusteo, 46 de
                           ellos con su linea a CERO energias,
                           **5 flips = 0.03/partida** -- POR ENCIMA del criterio.
                           2 son "linea -> MOTOR" (la frase del registro) y 3
                           son "motor -> otro motor": el peldano llega antes que
                           el tier de etapa y reordena el propio motor, que es la
                           escalera haciendo su trabajo. CERO knock-ons.
    vs crustle_wall_1      n=100: 13 272 decisiones, 0 con el flag, 0 flips.
                           FUGA CERO.

The shape row is the one to read: 0.23 boards per game reach a bare line inside a
gust menu, and one flip in nine of them. The reading is narrow because the shape
is -- it needs the Marnie matchup, a Boss's Orders target menu, an uncharged line
AND an engine body we can finish, all on the same turn.

NOT A CONTROL GROUP. `flip` is a decision that changed, not a game that was won.
The winrate question against this deck has a ~1.5 point noise floor
([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos]]), which no rate of this
order can resolve; the census is the number that says whether there was anything
to measure in the first place.

Usage:
    python utils/census_the_bare_line_asks_nothing_of_the_reserve.py --games 200
    python utils/census_the_bare_line_asks_nothing_of_the_reserve.py --games 200 \
        --opponent deck/real_opponents/crustle_wall_1.csv   # the leakage half
"""

import argparse
import copy
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "tests", _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp                                          # noqa: E402
from cg.api import AreaType, OptionType, SelectContext          # noqa: E402
from ptcg.cards.ids import (MARNIE_ENGINE_GUST_RANK,            # noqa: E402
                            MARNIE_LINE_IDS)

DEFAULT_OPPONENT = "deck/opponents/marnie_grimmsnarl.csv"
LADDER = "MARNIE_ENGINE_BARE_LINE_NEEDS_NO_RESERVE"


def _boss_globals(mod):
    """The namespace of this arm's `ptcg/decision/boss_orders.py`.

    Same reach as `utils/gate_marnie_the_engine_before_the_line.py`: the
    constant is imported BY VALUE into the module that reads it, so it has to be
    rebound on THAT module's namespace, which `_ctx_gust_target.__globals__`
    hands over (main.py star-imports it).
    """
    return mod._ctx_gust_target.__globals__


def arm(name, ladder):
    mod = sp.load_agent(_ROOT / "main.py", name)
    _boss_globals(mod)[LADDER] = ladder
    return mod


def _is_gust_menu(obs):
    """Is this the TARGET select of a Boss's Orders already on the table?

    Recognised by shape and not by a card id: `SWITCH` context, options of type
    CARD over `AreaType.BENCH` belonging to the other seat.
    """
    sel = obs.get("select") or {}
    if sel.get("context") != int(SelectContext.SWITCH):
        return False
    options = sel.get("option") or []
    if not options:
        return False
    mine = obs["current"]["yourIndex"]
    return all(o.get("type") == int(OptionType.CARD)
               and o.get("area") == int(AreaType.BENCH)
               and o.get("playerIndex") == 1 - mine
               for o in options)


def _their_board(obs):
    mine = obs["current"]["yourIndex"]
    them = obs["current"]["players"][1 - mine]
    return list(them["active"] or []) + list(them["bench"] or [])


def _their_bench(obs):
    mine = obs["current"]["yourIndex"]
    return obs["current"]["players"][1 - mine]["bench"] or []


def _line_is_bare(obs):
    """No body of their Marnie's line carries energy -- the shape of the record.

    Read off the observation and not off the agent, so the census cannot inherit
    the bug it is measuring.
    """
    line = [b for b in _their_board(obs)
            if b is not None and b.get("id") in MARNIE_LINE_IDS]
    return bool(line) and not any(b.get("energies") for b in line)


def _target_body(obs, choice):
    """The body `choice` drags out of their bench, or None."""
    if not choice:
        return None
    options = (obs.get("select") or {}).get("option") or []
    if choice[0] >= len(options):
        return None
    bench = _their_bench(obs)
    index = options[choice[0]].get("index")
    if index is None or index >= len(bench):
        return None
    return bench[index]


def _classify(base_body, cand_body):
    """Which sentence does this flip say?"""
    b_id = (base_body or {}).get("id", 0)
    c_id = (cand_body or {}).get("id", 0)
    if b_id in MARNIE_LINE_IDS and c_id in MARNIE_ENGINE_GUST_RANK:
        return 'to_engine'
    if b_id in MARNIE_ENGINE_GUST_RANK and c_id in MARNIE_ENGINE_GUST_RANK:
        return 'in_engine'
    return 'other'


def census_game(driver, shadow, deck0, deck1, counts, max_steps=3000):
    """One game driven by `driver`, with `shadow` asked on every frame."""
    from cg import game

    for mod in (driver, shadow):
        sp._reset_si_aplica(mod)
    obs, sd = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError(f"battle_start failed: {sd.errorType}")
    steps = 0
    while obs["current"]["result"] == -1 and steps < max_steps:
        choice = driver.agent(obs)
        mirror = shadow.agent(copy.deepcopy(obs))
        counts['ours'] += 1
        gust = _is_gust_menu(obs)
        if driver.AGENT_STATE.op_is_marnie_deck:
            counts['marnie'] += 1
            if gust:
                counts['gust'] += 1
                if _line_is_bare(obs):
                    counts['bare'] += 1
        if list(mirror) != list(choice):
            counts['flip'] += 1
            if gust:
                counts[_classify(_target_body(obs, mirror),
                                 _target_body(obs, choice))] += 1
            else:
                counts['other'] += 1
        obs = game.battle_select(choice)
        steps += 1
    return obs["current"]["result"]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--opponent", default=DEFAULT_OPPONENT)
    ap.add_argument("--progress", type=int, default=50)
    args = ap.parse_args(argv)

    driver = arm("census_candidate", True)
    shadow = arm("census_baseline", False)
    if driver is shadow:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if _boss_globals(shadow)[LADDER]:
        raise SystemExit("el brazo baseline NO esta neutralizado: nada que medir")
    print("procedencia OK (candidato con la lectura, baseline sin ella)\n", flush=True)

    own = sp.read_deck()
    theirs = sp.read_deck(_ROOT / args.opponent)

    counts = Counter()
    for i in range(args.games):
        # The seat alternates: a census read off one half of the game is a
        # reading of the seat, not of the rule.
        d0, d1 = (own, theirs) if i % 2 == 0 else (theirs, own)
        census_game(driver, shadow, d0, d1, counts)
        if args.progress and (i + 1) % args.progress == 0:
            print(f"  ... {i + 1}/{args.games}", flush=True)

    n = args.games or 1
    print(f"\n{args.games} games against {Path(args.opponent).stem}")
    for label, key in (("our decisions                      ", 'ours'),
                       ("...with op_is_marnie_deck up       ", 'marnie'),
                       ("...and the menu is a gust TARGET   ", 'gust'),
                       ("...with their line at ZERO energy  ", 'bare')):
        print(f"  {label} {counts[key]:6d} ({counts[key] / n:7.2f}/game)")
    print(f"  ...the baseline played OTHERWISE   {counts['flip']:6d} "
          f"({counts['flip'] / n:7.2f}/game)   <- THE WRITTEN CRITERION")
    for label, key in (("      line -> ENGINE               ", 'to_engine'),
                       ("      engine -> another engine     ", 'in_engine'),
                       ("      neither (knock-on)           ", 'other')):
        print(f"  {label} {counts[key]:6d} ({counts[key] / n:7.2f}/game)")
    rate = counts['flip'] / n
    print("\n" + ("BELOW the criterion (0.01/game, written before running this):"
                  " there is not enough exposure for a winrate to resolve it."
                  if rate < 0.01 else
                  "AT or ABOVE the criterion. The winrate still needs its own "
                  "gate with a --control arm at the same N."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
