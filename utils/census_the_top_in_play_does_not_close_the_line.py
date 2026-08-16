"""How often a copy of a line's TOP already in play switches off the search for
the SECOND one -- while a body on our board is standing there ready to wear it.

THE BOARD IT COMES FROM (user, `records/registro_007_pasos_060_hasta_074.json`
step 72, episode 93493222 vs Marnie -- WON in spite of this). Our turn 7, bench
FULL, Forest of Vitality ours and in play:

    US (5 prizes)                             RIVAL (6 prizes)
    active  Hydrapple ex 300/330, 2 eff.      active  Eevee 70, 1 energy
    bench   Meganium 160        Meowth ex     bench   Eevee 70, Sylveon 100
            Teal Mask Ogerpon ex x2 (4 eff.)
            **Dipplin 80, 2 effective**
    hand    Ultra Ball x2, Forest, Lillie's, {G}

The menu was four things: the two Ultra Balls, the attack, and pass. The agent
attacked. The second Hydrapple ex was in the DECK (`ACTIVE_CARDS_IN_DECK`
`{DECK: 1}`), the Dipplin under it had come down turns earlier and the Forest
lifts the evolution restriction anyway: Ultra Ball -> Hydrapple ex -> evolve was
one Item away from turning an 80 HP body into a second charged 330 HP attacker,
paid for with a spare Ultra Ball and a fourth Forest with the Forest already on
the field.

Traced, both Ultra Balls scored **-100** (`SCORE_CANCEL`), and NOT for their
price: every `_ub_cancel_*` came back False. `_eval_ub_best_target` returned 0 --
no target at all -- because the whole Applin/Dipplin/Hydrapple ladder hangs off
`if not has_hydrapple:` (`ptcg/decision/ultra_ball.py`), and `has_hydrapple` is
True for ANY Hydrapple ex on the board, active included. Its twin ladder hangs
off `meganium_in_play`, and a Meganium was on the bench. With the bench FULL
every remaining candidate is a Basic and dies on `_ub_target_has_no_seat`: an
evolution was the only thing an Ultra Ball could still buy, and both evolution
ladders were closed by "we already have one of those".

Counterfactual on that captured board: the same call with `has_hydrapple=False`
returns **950**.

WHAT IT COUNTS. The instrument wraps `_eval_ub_best_target` -- its only caller
is the PLAY branch (`main._ub_target_score`), so one call is one Ultra Ball
being priced in a real menu:

    asked      Ultra Balls priced
    top-in-play  ...on a board holding a card that is an EVOLUTION, has a copy
               of itself already in play (the thing that closes the ladder),
               none in hand, at least one still in the DECK, and a body that
               can WEAR it today (`_ub_wearable_bodies`, read body by body so a
               pre-evolution played this turn does not count unless a Forest is
               available). THIS is the population the claim is about.
    dead       ...and the evaluator returned 0, so the Ultra Ball was priced at
               `SCORE_CANCEL` and the turn could only attack or pass. Here the
               gate costs a PLAY, not a re-ordering.
    full bench ...and the bench was full, so no Basic target could have taken
               its place either: the Item is dead for the whole turn.
    flip       the same call with BOTH species gates lifted
               (`has_hydrapple=False`, `meganium_in_play=False`) returns a
               target where the real one returned none. Lifting them can only
               ADD evolution offers and can only LOWER the Tapu/Pinsir values,
               so against a real 0 this difference is the evolution ladder and
               nothing else.

READ THE TURNS, NOT THE PRICINGS. One board is priced once per Ultra Ball in
hand and again after every action of the turn that reopens the menu -- on the
step 72 board, eleven times. Counting pricings would report the same refusal
eleven times over, so the exposure line of the report is DISTINCT TURNS: the
number of turns in which an Ultra Ball died to this gate, which is the number
of plays it actually cost.

WHY THE COUNT AND NOT ONLY A WINRATE. The claim can only speak on a board that
already holds one copy of a line's top, still has another in the deck and has a
body ready to wear it. A change that narrow is reported by how often its board
comes up and what it does there; a self-play gate answers the other half and
needs its own `--control` arm for the noise floor.

Three sources, answering different questions:

    --records   the games in `records/` (default). Exact and in slow motion: it
                replays our seat menu by menu with today's agent and says which
                record fires.
    --frozen    the committed corpus (`tests/corpus/frozen_records.json.gz`),
                which survives a clean checkout and is the wider denominator.
    --games N   self-play. The only way to see boards no corpus recorded.

Usage:
    python utils/census_the_top_in_play_does_not_close_the_line.py
    python utils/census_the_top_in_play_does_not_close_the_line.py --frozen -v
    python utils/census_the_top_in_play_does_not_close_the_line.py --games 200
"""

import argparse
import inspect
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


class _globals_ns:
    """A module's namespace DICT wearing an attribute interface.

    Same reason as in `census_the_last_bridge_is_not_fodder`: each self-play arm
    owns its own `ptcg` tree and `selfplay.load_agent` drops it from
    `sys.modules`, so the arm's modules are reached by walking `__globals__` from
    its `agent`, never by name.
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


def _instrument(agent_module, counts):
    """Wrap `_eval_ub_best_target` in the namespace that CONSUMES it.

    That namespace is main.py's own globals: `_ub_target_score` lives there and
    resolves the name at call time, and main.py binds it with
    `from ptcg.decision.ultra_ball import *`. Rebinding the definition inside
    `ptcg.decision.ultra_ball` would leave main's binding untouched and the
    census would report a confident zero -- so this rebinds the consumer, and
    raises if the name is not where it is expected.
    """
    main_ns = agent_module.agent.__globals__
    plain = main_ns.get('_eval_ub_best_target')
    if plain is None:
        raise SystemExit(
            "el censo no alcanza a _eval_ub_best_target: mediria cero")

    ub = _globals_ns(plain.__globals__)
    for _name in ('_ub_wearable_bodies', '_evo_body_in_play', '_evolution_stage',
                  'Forest_of_Vitality', 'ZONE_DECK', 'AGENT_STATE'):
        if not hasattr(ub, _name):
            raise SystemExit(f"el censo no alcanza a {_name}: mediria cero")

    # THE CENSUS ALWAYS MEASURES THE EXPOSURE, never the fix. `_eval_ub_best_target`
    # now answers this question itself (`TOP_IN_PLAY_DOES_NOT_CLOSE_THE_LINE`), so
    # left alone the instrument would report the population as empty the day the
    # reading shipped -- and a census that quietly measures the post-fix world is
    # a census that says "this never happens" about the board it was written for.
    # The switch is held OFF for the whole run and restored afterwards.
    if not hasattr(ub, 'TOP_IN_PLAY_DOES_NOT_CLOSE_THE_LINE'):
        raise SystemExit("el censo no alcanza al interruptor: mediria cero")
    _switch_was = ub.TOP_IN_PLAY_DOES_NOT_CLOSE_THE_LINE
    ub.TOP_IN_PLAY_DOES_NOT_CLOSE_THE_LINE = False

    sig = inspect.signature(plain)
    # DISTINCT TURNS, reset by the caller between games: the same board is
    # priced once per Ultra Ball in hand and again after every action that
    # reopens the menu, so the pricing count is not an exposure.
    seen = {'top': set(), 'dead': set(), 'last': None}

    def _tops_in_play(call, out):
        """The cards this board is refusing to search for, and only those.

        Deck-agnostic on purpose: it names no line. The stage and the
        pre-evolution come from the card data, and the "already in play" half is
        read off `field_counts` -- which is the generic form of what
        `has_hydrapple` and `meganium_in_play` each say about one line.
        """
        field = call['field_counts'] or {}
        hand = call['hand_counts'] or {}
        cards = call.get('cards_in_deck') or ub.AGENT_STATE.ACTIVE_CARDS_IN_DECK
        forest = call['forest_in_play']

        # `_ub_wearable_bodies` exactly as the evaluator reads it (its own
        # lines): the start-of-turn snapshot unless a Forest is in play, and the
        # board itself for the body-by-body question.
        snapshot = ub.AGENT_STATE._field_at_turn_start
        evolvable = snapshot if (not forest and snapshot) else field
        state = call['state']
        players = getattr(state, 'players', None)
        seat = getattr(state, 'yourIndex', None)
        mine = None
        if players and isinstance(seat, int) and 0 <= seat < len(players):
            mine = players[seat]
        forest_available = (forest
                            or hand.get(ub.Forest_of_Vitality, 0) >= 1)
        wearable = ub._ub_wearable_bodies(mine, field, evolvable,
                                          forest_available)

        hits = []
        for cid, zones in (cards or {}).items():
            if field.get(cid, 0) < 1:
                continue                      # no copy in play: nothing to close
            if hand.get(cid, 0) >= 1:
                continue                      # the hand already covers it
            if (zones or {}).get(ub.ZONE_DECK, 0) < 1:
                continue                      # not searchable
            if not ub._evolution_stage(cid):
                continue                      # None (not a Pokemon) or 0 (Basic)
            if not ub._evo_body_in_play(cid, wearable):
                continue                      # nothing can wear it today
            hits.append(cid)
        return hits

    def counted(*a, **k):
        out = plain(*a, **k)
        counts['asked'] += 1
        bound = sig.bind(*a, **k)
        bound.apply_defaults()
        call = bound.arguments

        # A NEW GAME resets the turn counter, and self-play never announces one:
        # a turn number that goes BACKWARDS is the announcement. Without this the
        # sets below would read turn 7 of the second game as already seen.
        turn = getattr(call['state'], 'turn', None)
        if (turn is not None and seen['last'] is not None
                and turn < seen['last']):
            seen['top'].clear()
            seen['dead'].clear()
        seen['last'] = turn

        hits = _tops_in_play(call, out)
        if hits:
            counts['top_in_play'] += 1
            if turn not in seen['top']:
                seen['top'].add(turn)
                counts['turns_top'] += 1
            for cid in hits:
                counts[f"card:{cid}"] += 1
            if out == 0:
                counts['dead'] += 1
                if call['bench_count'] >= (call.get('bench_max') or 5):
                    counts['dead_full_bench'] += 1
                lifted = dict(call)
                lifted['has_hydrapple'] = False
                lifted['meganium_in_play'] = False
                if plain(**lifted) > 0:
                    counts['flip'] += 1
                    if turn not in seen['dead']:
                        seen['dead'].add(turn)
                        counts['turns_dead'] += 1
        return out

    main_ns['_eval_ub_best_target'] = counted

    def restore():
        main_ns['_eval_ub_best_target'] = plain
        ub.TOP_IN_PLAY_DOES_NOT_CLOSE_THE_LINE = _switch_was

    def new_game():
        seen['top'].clear()
        seen['dead'].clear()
        seen['last'] = None

    restore.new_game = new_game
    return restore


def census_records(verbose):
    import golden_corpus as gc

    agent_module = gc._main_mod()
    counts = Counter()
    restore = _instrument(agent_module, counts)
    try:
        records = 0
        for path in gc.record_files():
            gc.reset_agent(agent_module)
            restore.new_game()
            before = dict(counts)
            gc.replay_record(agent_module, path)
            records += 1
            if verbose:
                delta = {k: counts[k] - before.get(k, 0)
                         for k in ('asked', 'top_in_play', 'dead', 'flip')}
                if delta['top_in_play']:
                    print(f"  {path.name:46s} tasaciones {delta['asked']:4d}  "
                          f"CIMA EN MESA {delta['top_in_play']:3d}  "
                          f"muertas {delta['dead']:3d}  "
                          f"flip {delta['flip']:3d}", flush=True)
    finally:
        restore()
    print(f"\nregistros: {records} ficheros")
    _report(counts, records, unit="registro")
    return 0


def census_frozen(verbose):
    import golden_corpus as gc

    bundle = gc.frozen_records()
    if not bundle:
        raise SystemExit("no hay corpus congelado: tests/corpus/"
                         "frozen_records.json.gz no existe")
    agent_module = gc._main_mod()
    counts = Counter()
    restore = _instrument(agent_module, counts)
    try:
        for name, data in sorted(bundle.items()):
            restore.new_game()
            before = dict(counts)
            gc.replay_data(agent_module, data)
            if verbose:
                delta = {k: counts[k] - before.get(k, 0)
                         for k in ('asked', 'top_in_play', 'dead', 'flip')}
                if delta['top_in_play']:
                    print(f"  {name:46s} tasaciones {delta['asked']:4d}  "
                          f"CIMA EN MESA {delta['top_in_play']:3d}  "
                          f"muertas {delta['dead']:3d}  "
                          f"flip {delta['flip']:3d}", flush=True)
    finally:
        restore()
    print(f"\ncorpus congelado: {len(bundle)} partidas")
    _report(counts, len(bundle), unit="partida")
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
    asked = counts['asked']
    top = counts['top_in_play']
    turns_top, turns_dead = counts['turns_top'], counts['turns_dead']
    dead, full, flip = counts['dead'], counts['dead_full_bench'], counts['flip']
    denom = denom or 1
    print(f"  Ultra Balls tasadas en un menu real       {asked:7d} "
          f"({asked / denom:8.2f}/{unit})")
    print(f"  ...con la CIMA de una linea ya en mesa,   {top:7d} "
          f"({top / denom:8.2f}/{unit})")
    print(f"     otra en mazo y un cuerpo que la viste")
    print(f"  ...y el tasador devolvio 0 -> CANCEL      {dead:7d} "
          f"({dead / denom:8.2f}/{unit})")
    print(f"  ...y ademas con la banca LLENA            {full:7d} "
          f"({full / denom:8.2f}/{unit})")
    print(f"  ...y sin los dos candados habria objetivo {flip:7d} "
          f"({flip / denom:8.2f}/{unit})")
    print(f"  TURNOS distintos con la cima en mesa      {turns_top:7d} "
          f"({turns_top / denom:8.2f}/{unit})")
    print(f"  ...y con la Ultra Ball MUERTA por el candado {turns_dead:6d} "
          f"({turns_dead / denom:8.2f}/{unit})")
    for key in sorted(k for k in counts if str(k).startswith('card:')):
        print(f"      carta {str(key).split(':')[1]:>5}  {counts[key]:6d}")
    if turns_dead / denom < 0.01:
        print("\nAVISO: el evento es RARO. Con una exposicion asi el gate de "
              "self-play no resuelve la diferencia por muchas partidas que "
              "juegue; el informe honesto es este censo, no un winrate.")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=0,
                    help="self-play games; 0 = replay a corpus instead")
    ap.add_argument("--frozen", action="store_true",
                    help="replay the committed corpus instead of records/")
    ap.add_argument("--opponent", default=None,
                    help="deck csv for the opposing seat (self-play only)")
    ap.add_argument("--progress", type=int, default=250)
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="one line per game that fires")
    args = ap.parse_args(argv)
    if args.games:
        return census_selfplay(args.games, args.opponent, args.progress)
    if args.frozen:
        return census_frozen(args.verbose)
    return census_records(args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
