"""How often the ENERGY split inside the Marnie engine changes the gusted body.

THE BOARD IT COMES FROM (episode 93680377 step 173, turn 14 vs Marnie -- game
WON, and the gust still went to the wrong body; drawn out in full in
`tests/test_marnie_the_gust_reads_the_energy_not_the_hp.py`): Boss's Orders
already down, and on their bench TWO Munkidori at exactly 100/110, one carrying
a Darkness and one bare. `marnie_the_engine_before_the_line` lifted both to the
same 15600 -- same species, same HP -- and the argmax kept the first, which is
the bare one. The ladder now splits the species by ENERGY and puts the Froslass
between the halves:

    Munkidori WITH energy  >  Froslass  >  Munkidori WITHOUT energy  >  Snorunt

with the lowest current HP breaking ties INSIDE a rung and nowhere else.

WHAT IS BEING COUNTED. This is the census of the ladder INSIDE the engine, not
of the engine-vs-line question -- that one has its own file
(`census_marnie_the_engine_before_the_line.py`) and its own switch. The same
applies to the rung's presence in the JAM chain (the ladder that runs when our
active cannot attack): both halves of that hang off `marnie_engine_first` and
therefore off `MARNIE_ENGINE_BEFORE_THE_LINE`, so the parent census is what
measures them. This switch neutralises only the energy split and the tiebreak,
in whichever chain the board happens to route to. The
candidate arm drives the game; a copy of the same tree with
`MARNIE_ENGINE_READS_THE_ENERGY = False` (the flat per-species ranking, which is
the tree that let bench position decide) is asked on every frame. Per one of OUR
decisions:

    ours        decisions the agent took (the denominator)
    marnie      ...taken with `AGENT_STATE.op_is_marnie_deck` up
    gust        ...and the menu is a Boss's Orders TARGET select
    engine      ...and at least TWO engine bodies sat on their bench, which is
                the only shape either arm can disagree about
    flip        ...where the flat arm brought up something ELSE. This is the
                population: the boards where the ladder changes a decision

and the flips split into the three sentences the user stated, so a rule that
moves for some other reason cannot hide inside the total:

    e_split     the flat arm took a BARE Munkidori, the ladder a CHARGED one
    froslass    the flat arm took a bare Munkidori, the ladder the Froslass
    hp_tie      same species and same energy state, different HP -- the tiebreak
    other       a flip that is none of the three: a knock-on, or the gust
                leaving the engine entirely

THE LEAKAGE HALF is the second row, against a list that is not Marnie's. The
whole ladder hangs off `op_is_marnie_deck` through `marnie_engine_first`, so the
honest number there is ZERO and anything else is a rule reaching past its
matchup.

⚠️ THE CRITERION, written before this file was run and not moved afterwards:
`flip` at or above **0.01 per game** against the Marnie lists, and **0.00 per
game** on the list that is not Marnie's. The prior: the parent reading
(engine-before-the-line) was measured at 0.02 flips/game and is the CEILING of
this one -- the ladder can only move on a turn where that rung already fired.
Inside that ceiling it moves often rather than rarely, because the shape it
needs is the ordinary Marnie board: these lists play four Munkidori and two
Froslass, so a gust menu that reaches the engine usually offers more than one
engine body. Half the parent rate is therefore the honest bar. A rate ABOVE the
parent's 0.02 would be the alarming answer, not the good one: it would mean the
ladder is moving on boards where the engine rung never fired.

WHAT IT MEASURED (16 agosto 2026, n=300 per row):

    vs marnie_grimmsnarl   36 926 decisiones, 209 menus de gusteo, 136 de ellos
                           con dos o mas cuerpos del motor en banca,
                           2 flips = 0.007/partida -- LOS DOS son "Munkidori
                           pelado -> Froslass", CERO knock-ons.
    vs crustle_wall_1      39 742 decisiones, 0 con el flag, 0 flips. FUGA CERO.

BELOW THE WRITTEN BAR, and the interesting part is WHICH half is missing: not
one flip of the record's own sentence (`e_split`, bare -> charged Munkidori) in
300 games. The bot does not build that board -- it attaches to the Munkidori it
is about to attack with and leaves the spare bare on the bench only rarely, so
the two-copies-tied-on-HP shape that the real opponent of episode 93680377 put
up simply does not occur here. That is the same limit the parent gate already
documented from the other side: the matchup this harness simulates is not the
matchup the rule was written for. Against the RECORDED games the answer is
sharper -- replaying the three complete Marnie games plus episode 93680377
through both arms flips exactly ONE decision out of 377, the one the user
pointed at -- and the frozen golden corpus does not move at all.

NOT A CONTROL GROUP. `flip` is a decision that changed, not a game that was won.
The winrate question against this deck has a ~1.5 point noise floor
([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos]]), which no rate of this
order can resolve; the census is the number that says whether there was anything
to measure in the first place.

Usage:
    python utils/census_the_gust_reads_the_energy_not_the_hp.py --games 200
    python utils/census_the_gust_reads_the_energy_not_the_hp.py --games 200 \
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
                            Froslass, Munkidori)

DEFAULT_OPPONENT = "deck/opponents/marnie_grimmsnarl.csv"
LADDER = "MARNIE_ENGINE_READS_THE_ENERGY"


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


def _their_bench(obs):
    mine = obs["current"]["yourIndex"]
    return obs["current"]["players"][1 - mine]["bench"] or []


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


def _shape(body):
    """(card id, does it carry energy, current HP) -- the three the ladder reads."""
    if body is None:
        return (0, False, 0)
    return (body.get("id", 0), bool(body.get("energies")), body.get("hp", 0))


def _classify(base_body, cand_body):
    """Which of the user's three sentences does this flip say?"""
    b_id, b_charged, b_hp = _shape(base_body)
    c_id, c_charged, c_hp = _shape(cand_body)
    if b_id not in MARNIE_ENGINE_GUST_RANK or c_id not in MARNIE_ENGINE_GUST_RANK:
        return 'other'
    if b_id == Munkidori and not b_charged:
        if c_id == Munkidori and c_charged:
            return 'e_split'
        if c_id == Froslass:
            return 'froslass'
    if (b_id, b_charged) == (c_id, c_charged) and c_hp < b_hp:
        return 'hp_tie'
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
                engine = [b for b in _their_bench(obs)
                          if b is not None and b.get("id") in MARNIE_ENGINE_GUST_RANK]
                if len(engine) >= 2:
                    counts['engine'] += 1
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
    print("procedencia OK (candidato con la escalera, baseline plano)\n", flush=True)

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
                       ("...with >=2 engine bodies on bench ", 'engine')):
        print(f"  {label} {counts[key]:6d} ({counts[key] / n:7.2f}/game)")
    print(f"  ...the flat arm played OTHERWISE   {counts['flip']:6d} "
          f"({counts['flip'] / n:7.2f}/game)   <- THE WRITTEN CRITERION")
    for label, key in (("      bare -> CHARGED Munkidori    ", 'e_split'),
                       ("      bare Munkidori -> Froslass   ", 'froslass'),
                       ("      same rung, less HP           ", 'hp_tie'),
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
