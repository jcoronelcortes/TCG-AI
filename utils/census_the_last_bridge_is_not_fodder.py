"""How often a cost is about to eat the LAST bridge of a line we can still build.

THE BOARD IT COMES FROM (user, `records/registro_006_pasos_047_hasta_073.json`
step 47, episode 93159383 vs Marnie -- LOST). Our turn 6, prizes 6-6, hand
{Bayleef, Bayleef, Ultra Ball} and a menu of exactly two options: play the Ultra
Ball, or end. The Ultra Ball's cost is two cards from hand, and the only two
cards it could take were both Bayleef -- the deck's only bridge between the
Chikorita and the Meganium whose *Wild Growth* is this deck's energy engine. It
took them, to fetch a Meowth ex.

They stayed in the discard from step 49 to step 190, the last of the game. A
Meganium reached hand fourteen steps later and sat there for 127 of the game's
191 steps; the Chikorita it was waiting for was benched on that same turn 6,
under our own Forest of Vitality -- which lets a Grass Pokemon evolve the turn it
is played, so Chikorita -> Bayleef -> Meganium was ONE turn's work -- and it was
still on the bench, unevolved, when the game ended.

WHAT IT COUNTS. `_evo_bridge_last_copies` is asked about a card in hand at two
places, and this census wraps the function itself so both are covered:

    asked      cards priced by the Ultra Ball's cost count or by the forced
               DISCARD scorer that are links of one of our lines
    bridge     ...and the copies in hand are the LAST ones any zone a draw or a
               search still reaches, on a line whose top and Basic are both
               still live. THIS is the population the rule is about: the card
               the cost was about to make unreachable.
And, on the Ultra Ball side, the cost arithmetic itself -- run TWICE on every
board, once with the reading on and once with `LAST_BRIDGE_IS_NOT_FODDER` off,
so the difference is measured on the same hand rather than across two runs:

    cost       calls to `_ub_real_fodder`, the count the whole `_ub_cancel_*`
               family divides against 2
    cheaper    ...that the reading makes smaller: a bridge it refuses to price
               as fodder
    veto       ...and that cross the threshold -- 2 or more without the reading,
               fewer than 2 with it. THIS is where the rule costs a PLAY rather
               than merely re-ordering a discard ranking: the Ultra Ball is
               cancelled because its cost can no longer be paid out of surplus.

WHY THE COUNT AND NOT ONLY A WINRATE. The rule is a strict no-op on every board
where the deck still holds a copy of the link, which is most of them: it can only
speak in the narrow window where the bridge's last copies are in hand and the
line is still worth finishing. A change that thin is measured by how often its
board comes up and what it does there; the gate
(`utils/gate_the_last_bridge_is_not_fodder.py`) answers the winrate half, with
its own `--control` arm for the noise floor.

Two sources, answering different questions:

    --records   the recorded games in `records/` (default). Exact and in slow
                motion: it replays our seat menu by menu with the agent as it
                stands today, and says which record fires.
    --games N   self-play. Wider, and the only way to see boards the corpus
                never recorded.

Usage:
    python utils/census_the_last_bridge_is_not_fodder.py
    python utils/census_the_last_bridge_is_not_fodder.py --verbose
    python utils/census_the_last_bridge_is_not_fodder.py --games 200
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(_ROOT / "tests"))
if str(_ROOT / "utils") not in sys.path:
    sys.path.insert(0, str(_ROOT / "utils"))


def _instrument(agent_module, counts):
    """Wrap the predicate in the two modules that CONSUME it.

    Each arm gets its own `ptcg` tree (`selfplay.load_agent`), so patching the
    ambient `ptcg.cards.lines` would instrument a copy nobody plays with and the
    census would report a confident zero. The two call sites import the function
    by name at module load, so the binding to rebind is the one in each
    CONSUMER's globals -- and if it is not there, this raises instead of
    reporting that zero.
    """
    # EVERY namespace is resolved BEFORE the first rebind. `ptcg.cards.lines` is
    # reached through `_evo_bridge_last_copies.__globals__`, and the moment that
    # name is rebound to this file's wrapper the hop lands here instead.
    ub = _module_of(agent_module, "ptcg.decision.ultra_ball")
    card = _module_of(agent_module, "ptcg.turn.options.card")
    lines = _module_of(agent_module, "ptcg.cards.lines")
    if not hasattr(lines, 'LAST_BRIDGE_IS_NOT_FODDER'):
        raise SystemExit("el censo no alcanza al interruptor: mediria cero")

    consumers = []
    for mod_name, mod in (("ptcg.decision.ultra_ball", ub),
                          ("ptcg.turn.options.card", card)):
        if getattr(mod, "_evo_bridge_last_copies", None) is None:
            raise SystemExit(
                f"el censo no alcanza a {mod_name}: mediria cero")
        consumers.append(mod)

    plain = consumers[0]._evo_bridge_last_copies

    def counted(card_id, hand_counts, field_counts, reachable_counts):
        out = plain(card_id, hand_counts, field_counts, reachable_counts)
        counts['asked'] += 1
        if out:
            counts['bridge'] += 1
            counts[f"bridge:{card_id}"] += 1
        return out

    for mod in consumers:
        mod._evo_bridge_last_copies = counted

    # THE COST ARITHMETIC ITSELF, both arms of it. `_ub_real_fodder` is the
    # number `_ub_cancel_no_surplus` and the whole `_ub_cancel_*` family divide
    # against 2, so running it twice -- once with the reading on, once with the
    # module switch off -- says exactly what the rule costs the Ultra Ball, and
    # says it on the same board rather than across two runs.
    plain_fodder = ub._ub_real_fodder

    def counted_fodder(ctx, protegida):
        out = plain_fodder(ctx, protegida)
        prev = lines.LAST_BRIDGE_IS_NOT_FODDER
        lines.LAST_BRIDGE_IS_NOT_FODDER = False
        try:
            without = plain_fodder(ctx, protegida)
        finally:
            lines.LAST_BRIDGE_IS_NOT_FODDER = prev
        counts['cost'] += 1
        if out != without:
            counts['cheaper'] += 1
            if without >= 2 > out:
                counts['veto'] += 1
        return out

    ub._ub_real_fodder = counted_fodder

    def restore():
        for mod in consumers:
            mod._evo_bridge_last_copies = plain
        ub._ub_real_fodder = plain_fodder

    return restore


def _module_of(agent_module, dotted):
    """The `dotted` module of THIS arm's own package tree.

    NOT THROUGH `sys.modules`. `selfplay.load_agent` deletes the arm's `ptcg`
    branch from `sys.modules` the moment the load finishes and puts the AMBIENT
    tree back, precisely so two arms cannot share a module object -- so a lookup
    by name hands back a copy nobody plays with and the census reports a
    confident zero (it did, on the first run of this file: 200 self-play games,
    every counter 0, while the same instrument over `records/` was counting
    fine).

    The arm's own modules are reached the only way that survives that: by
    walking the reference graph from the arm's `agent` function outwards.
    `agent.__globals__` is main.py's namespace, and main.py opens with
    `from ptcg.decision.ultra_ball import *` and `from ptcg.turn.scoring import
    score_option`, so every module this census needs is one or two `__globals__`
    hops away. If a hop fails this raises, rather than reporting the zero.
    """
    g = agent_module.agent.__globals__
    if dotted == "ptcg.decision.ultra_ball":
        return _globals_ns(g['_ub_real_fodder'].__globals__)
    if dotted == "ptcg.turn.options.card":
        scoring = g['score_option'].__globals__
        return _globals_ns(scoring['card'].__dict__)
    if dotted == "ptcg.cards.lines":
        ub = g['_ub_real_fodder'].__globals__
        return _globals_ns(ub['_evo_bridge_last_copies'].__globals__)
    raise SystemExit(f"el censo no sabe alcanzar {dotted}")


class _globals_ns:
    """A module's namespace DICT wearing an attribute interface.

    The instrument rebinds names inside a module the arm owns; `setattr` on a
    module object and item assignment on its `__dict__` are the same operation,
    and only the second one is available when the module object itself was never
    kept anywhere reachable.
    """

    def __init__(self, ns):
        object.__setattr__(self, '_ns', ns)

    def __getattr__(self, name):
        try:
            return object.__getattribute__(self, '_ns')[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name, value):
        object.__getattribute__(self, '_ns')[name] = value


def census_records(verbose):
    import golden_corpus as gc

    agent_module = gc._main_mod()
    counts = Counter()
    restore = _instrument(agent_module, counts)
    try:
        records = 0
        for path in gc.record_files():
            gc.reset_agent(agent_module)
            before = dict(counts)
            gc.replay_record(agent_module, path)
            records += 1
            if verbose:
                delta = {k: counts[k] - before.get(k, 0)
                         for k in ('asked', 'bridge', 'veto')}
                if delta['bridge']:
                    print(f"  {path.name:46s} preguntas {delta['asked']:5d}  "
                          f"ULTIMO PUENTE {delta['bridge']:4d}  "
                          f"veto {delta['veto']:3d}", flush=True)
    finally:
        restore()
    print(f"\nregistros: {records} ficheros")
    _report(counts, records, unit="registro")
    return 0


def census_selfplay(games, opponent, progress):
    import selfplay as sp
    from opponent_bot import OpponentBot

    agent_module = sp.load_agent(_ROOT / "main.py", "arm_census")
    counts = Counter()
    restore = _instrument(agent_module, counts)
    try:
        their = sp.read_deck(_ROOT / opponent) if opponent else None
        sp.torneo(agent_module, OpponentBot(), games,
                  progress=progress or None, deck_base=their)
    finally:
        restore()
    print(f"\nself-play: {games} partidas contra "
          f"{opponent or 'deck.csv (espejo del bot)'}")
    _report(counts, games, unit="partida")
    return 0


def _report(counts, denom, unit):
    asked, bridge = counts['asked'], counts['bridge']
    cost, cheaper, veto = counts['cost'], counts['cheaper'], counts['veto']
    denom = denom or 1
    print(f"  enlaces de linea preguntados por un coste  {asked:7d} "
          f"({asked / denom:8.2f}/{unit})")
    print(f"  ...y era el ULTIMO PUENTE de la linea      {bridge:7d} "
          f"({bridge / denom:8.2f}/{unit})")
    print(f"  cuentas de forraje de la Ultra Ball        {cost:7d} "
          f"({cost / denom:8.2f}/{unit})")
    print(f"  ...que la lectura hace mas CARAS           {cheaper:7d} "
          f"({cheaper / denom:8.2f}/{unit})")
    print(f"  ...y que cruzan el umbral de 2 -> VETO     {veto:7d} "
          f"({veto / denom:8.2f}/{unit})")
    for key in sorted(k for k in counts if str(k).startswith('bridge:')):
        print(f"      carta {str(key).split(':')[1]:>5}  {counts[key]:6d}")
    if bridge / denom < 0.01:
        print("\nAVISO: el evento es RARO. Con una exposicion asi el gate de "
              "self-play no resuelve la diferencia por muchas partidas que "
              "juegue; el informe honesto es este censo, no un winrate.")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=0,
                    help="self-play games; 0 = replay the records instead")
    ap.add_argument("--opponent", default=None,
                    help="deck csv for the opposing seat (self-play only)")
    ap.add_argument("--progress", type=int, default=250)
    ap.add_argument("--verbose", action="store_true",
                    help="one line per record that fires")
    args = ap.parse_args(argv)
    if args.games:
        return census_selfplay(args.games, args.opponent, args.progress)
    return census_records(args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
