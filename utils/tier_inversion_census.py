r"""Every menu where an ORDER beat a NUMBER, counted.

    _best_i = max(range(len(scores)), key=lambda i: (_play_order_tier[i], scores[i]))

That line, at the bottom of `ptcg/turn/finalize.py`, is the only place in this
project where a category decides before a value. It is deliberate and it is
load-bearing -- a winning attack has to be executed before the turn spends
itself, a search has to take the last bench seat before the body that would fill
it -- and on 12 August 2026 it produced TWO separate defects in one day:

  * `74f85f1`: `_TIER_ENERGY` (10) is handed to every ATTACH without asking what
    the attachment is worth. A Grass the energy scorer had ITSELF capped at 20
    (`SCORE_CHARGE_DOOMED`, the ceiling for a body the opponent cashes before our
    next turn) outranked an Ultra Ball at 11 900. The attachment left two cards
    in hand, the Ultra Ball discards two, and one action later the search was off
    the menu;
  * `fcfb17d`: a Pokemon drop lives in `_TIER_DEVELOP` (40) and an ordinary Ultra
    Ball in tier 0, so a Tapu Bulu that could not attack that turn took the fifth
    bench seat and the search that followed was vetoed by `full_bench`.

Both were found by a person reading a lost game. Neither could have been found
by the suite, because in both the agent did exactly what its tiers say. THE
DOCTRINE ALREADY EXISTED -- "the tier rules over the score" is written down in
this project's own notes -- and a doctrine without a population is a belief.
This counts the population.

WHAT IT COUNTS. On every MAIN menu, two winners are computed: the one the agent
plays (tier, then score) and the one the score alone would pick. When they
differ, the row is an INVERSION, and it is recorded as

    (winning tier -> losing tier)   how often   median gap   the two cards

An inversion is NOT a defect. The two examples above are the same shape as every
correct execution of a winning attack, and the overwhelming majority of the rows
here are the tier system doing precisely its job. What makes a row worth reading
is the GAP: an order that wins by 600 times the score it beat is a different
object from one that wins by 40.

AND THEN THE READING THAT DECIDES WHICH ONES COST ANYTHING. The tier decides
ORDER, so an outranked option is usually still on the NEXT menu of the same turn
and gets played there. Every inversion is therefore followed until the turn ends:

    recuperada   the outranked option was chosen later in the same turn
    perdida      the turn never came back to it

On the frozen corpus that is **280 inversions, of which 262 recovered and 18
were lost** -- 0.86% of MAIN menus, not 13%. Four of the eighteen sit under
`_TIER_WIN_ATTACK`, where the attack ended the turn and abandoning the rest was
the point. Without this reading the census reports 280 events and cannot say
which of them cost a thing, which is the difference between a worklist and a
scare.

THE REPORT IS A WORKLIST RANKED BY FREQUENCY x GAP, never a verdict.

Usage:
    python utils/tier_inversion_census.py --corpus
    python utils/tier_inversion_census.py --corpus --games 200
    python utils/tier_inversion_census.py --corpus --top 40 --dump out.json
    python utils/tier_inversion_census.py --self-test
"""

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "utils") not in sys.path:
    sys.path.insert(0, str(_ROOT / "utils"))

import selfplay as sp  # noqa: E402
# The namespace walk of the rule census: `sp.load_agent` gives each arm its own
# `ptcg` tree and restores `sys.modules`, so `ptcg.turn.finalize` is NOT
# reachable by name -- only through the objects the loaded agent holds. Reused
# rather than re-derived; it took two attempts to get right the first time.
from rule_census import espacios_del_agente  # noqa: E402

_FINALIZE = "ptcg.turn.finalize"
_SINK = "TIER_CENSUS_SINK"


def classify(scores, tiers):
    """(winning tier, losing tier, gap) if the ORDER beat the NUMBER, else None.

    The whole verdict of this instrument, in one pure function, so that the
    self-test can exercise THE CODE THAT RUNS instead of a copy of it. A
    self-test against a re-implementation proves the re-implementation.
    """
    if len(scores) < 2:
        return None
    played = max(range(len(scores)), key=lambda i: (tiers[i], scores[i]))
    by_score = max(range(len(scores)), key=lambda i: scores[i])
    if played == by_score or scores[by_score] <= scores[played]:
        return None
    if tiers[played] <= tiers[by_score]:
        return None                      # not the tier: the score comparison ran
    return (tiers[played], tiers[by_score],
            scores[by_score] - scores[played], played, by_score)


class Registro:
    """(winning tier, losing tier) -> the gaps observed, plus one example."""

    def __init__(self):
        self.gaps = defaultdict(list)
        self.seats = defaultdict(list)
        # THE READING THAT TURNS A REORDERING INTO A LOSS. The tier decides
        # ORDER, so an option outranked in one menu is usually still on the next
        # one and gets played anyway. `recovered` counts the outranked options
        # that WERE chosen later in the same turn; `lost` counts the ones the
        # turn never came back to. Without this the census reports 280 events
        # and cannot say which of them cost anything.
        self.recovered = defaultdict(int)
        self.lost = defaultdict(int)
        self.pending = []
        self.turn_key = None
        self.lost_where = []
        self.example = {}
        self.menus = 0
        self.inversions = 0
        # Which record is being replayed. A worklist that says "somewhere in
        # 3580 decisions" is not a worklist: the row has to name a board.
        self.where = "?"

    def start_turn(self, key):
        """A new turn: whatever is still pending was never played."""
        if key == self.turn_key:
            return
        for row_key, _label, where in self.pending:
            self.lost[row_key] += 1
            self.lost_where.append((row_key, _label, where))
        self.pending = []
        self.turn_key = key

    def played_now(self, label):
        """The option this menu actually chose: it settles the pending losers."""
        still = []
        for row_key, loser, where in self.pending:
            if loser == label:
                self.recovered[row_key] += 1
            else:
                still.append((row_key, loser, where))
        self.pending = still

    def note(self, tier_win, tier_lose, gap, label_win, label_lose, seats=None):
        key = (tier_win, tier_lose)
        self.pending.append((key, label_lose, self.turn_key))
        self.gaps[key].append(gap)
        self.inversions += 1
        # THE SEAT IS WHAT SEPARATES A REORDERING FROM A LOSS. The tier decides
        # ORDER, and an option outranked in one menu is usually still on the
        # next -- so most inversions cost nothing. They cost something when the
        # play that goes first CONSUMES what the other one needed, and on this
        # board the resource is the bench seat: `fcfb17d` was exactly that, a
        # body taking the fifth seat from the search that decides what the seat
        # is for. `seats` is the FREE seats before the play; 1 means the winner
        # takes the last one.
        if seats is not None:
            self.seats[key].append(seats)
        # The example kept is the WIDEST gap of its row: the cheapest way to see
        # what a row is about is the worst thing it ever did.
        best = self.example.get(key)
        if best is None or gap > best[0]:
            self.example[key] = (gap, label_win, label_lose, self.where)

    def rows(self):
        out = []
        for key, gaps in self.gaps.items():
            gap, label_win, label_lose, where = self.example[key]
            out.append({
                "tier_win": key[0], "tier_lose": key[1],
                "n": len(gaps),
                "median_gap": int(statistics.median(gaps)),
                "max_gap": int(max(gaps)),
                "rank": len(gaps) * statistics.median(gaps),
                "worst_win": label_win, "worst_lose": label_lose,
                "worst_where": where,
                # How many of this row's inversions had the winner taking the
                # LAST free bench seat, and how many had room to spare.
                "takes_last_seat": sum(1 for s in self.seats[key] if s == 1),
                "seats_known": len(self.seats[key]),
                "recovered": self.recovered[key],
                "lost": self.lost[key],
            })
        out.sort(key=lambda r: -r["rank"])
        return out


def _label(select, obs, my_index, index, card_table, get_card, option_type):
    """`VERB card` -- and the VERB is the half that cannot be missing.

    The first run of this census printed `area=None` on 15 of its 18 rows: most
    menu options are not a card in an area (an ATTACK, an ABILITY, a RETREAT,
    END), so resolving only the card leaves the worklist unreadable exactly
    where the interesting tiers live. The type is always there.
    """
    try:
        option = select.option[index]
        verb = getattr(option_type(option.type), "name", "?")
    except Exception:
        verb = "?"
    try:
        card = get_card(obs, select.option[index].area,
                        select.option[index].index, my_index)
        if card is not None:
            data = card_table.get(card.id)
            name = getattr(data, "name", None) or f"id={card.id}"
            return f"{verb} {name}"
    except Exception:
        pass
    return verb


def instrument(agent, registro):
    """Plants the sink in the loaded agent's own `finalize` namespace."""
    spaces = {name: space for name, space in espacios_del_agente(agent)}
    space = spaces.get(_FINALIZE)
    if space is None:
        raise SystemExit(
            f"no se alcanza {_FINALIZE} desde el agente cargado: sin costura, "
            "no hay censo (y un censo que no puede ver es peor que ninguno)")
    if _SINK not in space:
        raise SystemExit(
            f"{_FINALIZE} no expone {_SINK}: la costura no esta en este arbol")

    card_table = space["card_table"]
    get_card = space["get_card"]
    select_context = space["SelectContext"]
    option_type = space["OptionType"]
    card_type = space["CardType"]

    def seat_cost(select, obs, my_index, index):
        """Free bench slots before the play -- but only if the play TAKES one.

        The first version of this reading counted free seats whichever option
        won, and reported a stadium and an energy attachment as "taking the last
        seat". Only a POKEMON play consumes one, so anything else answers None
        and stays out of the count: a metric that inflates the interesting band
        is worse than no metric.
        """
        try:
            option = select.option[index]
            if option_type(option.type) != option_type.PLAY:
                return None
            # A PLAY option indexes THE HAND, not an area -- `get_card` answers
            # None for it, which is why the first version of this reading found
            # no Pokemon plays at all and reported every row as costing no seat.
            me = obs.current.players[my_index]
            card = (me.hand or [])[option.index]
            data = card_table.get(card.id) if card is not None else None
            if data is None or data.cardType != card_type.POKEMON:
                return None
            return int(me.benchMax) - len(me.bench or [])
        except Exception:
            return None

    def sink(context, select, scores, tiers, obs, my_index):
        if context != select_context.MAIN:
            return
        registro.menus += 1
        try:
            registro.start_turn((registro.where, obs.current.turn))
        except Exception:
            pass
        chosen = max(range(len(scores)), key=lambda i: (tiers[i], scores[i]))
        registro.played_now(_label(select, obs, my_index, chosen, card_table,
                                   get_card, option_type))
        verdict = classify(scores, tiers)
        if verdict is None:
            return
        tier_win, tier_lose, gap, played, by_score = verdict
        registro.note(
            tier_win, tier_lose, gap,
            _label(select, obs, my_index, played, card_table, get_card, option_type),
            _label(select, obs, my_index, by_score, card_table, get_card, option_type),
            seats=seat_cost(select, obs, my_index, played))

    previous = space[_SINK]
    space[_SINK] = sink
    return lambda: space.__setitem__(_SINK, previous)


# --------------------------------------------------------------------------
# workloads


def pass_corpus(agent, registro):
    import golden_corpus as gc

    records = gc.frozen_records()
    if not records:
        raise SystemExit("no hay corpus congelado en tests/corpus/")
    decisions = 0
    for name, data in sorted(records.items()):
        registro.where = name
        decisions += len(gc.replay_data(agent, data))
    return f"corpus congelado: {decisions} decisiones en {len(records)} registros"


def pass_games(agent, games, decks):
    from opponent_bot import OpponentBot

    played = 0
    for relative in decks:
        path = _ROOT / relative
        if not path.exists():
            continue
        stats = sp.torneo(agent, OpponentBot(), games,
                          deck_base=sp.read_deck(path))
        played += stats["candidate"] + stats["base"]
    return f"self-play: {played} partidas contra {len(decks)} mazos"


_DECKS = ("deck/opponents/alakazam.csv", "deck/opponents/marnie_grimmsnarl.csv",
          "deck/opponents/crustle_kangaskhan.csv", "deck/opponents/archaludon.csv")


# --------------------------------------------------------------------------
# the two halves


def self_test(verbose=True):
    """Sensitivity: a planted inversion is seen. Specificity: none is invented.

    The plant does not go through the engine -- it feeds `classify`, which IS
    the verdict the sink applies, four hand-built menus. Three of them are the
    real boards of 12 August, to the number. A plant that went through the whole
    engine would be testing the engine; what has to be proved here is that the
    COUNTER is right, and that it stays quiet when the score comparison ran.
    """
    # sensitivity: the Grass of 20 in tier 10 against the Ultra Ball of 11 900
    # (`74f85f1`, registro_006 step 54) and the develop tier over the search
    # (`fcfb17d`, registro_010 step 137).
    grass = classify([20, 11900], [10, 0])
    develop = classify([8900, 11900], [40, 0])
    sensitivity = (grass is not None and grass[:3] == (10, 0, 11880)
                   and develop is not None and develop[:3] == (40, 0, 3000))

    # specificity: a tier that ALSO wins on score is not an inversion, and
    # neither is a menu decided inside one tier.
    quiet = [classify([30000, 1100], [10, 0]), classify([11900, 20], [0, 0])]
    specificity = all(v is None for v in quiet)

    if verbose:
        print("autotest del censo de inversiones tier-vs-score")
        print(f"  sensibilidad   los dos tableros del 12-ago (74f85f1, fcfb17d)"
              f" -> {grass[:3] if grass else None} / {develop[:3] if develop else None}"
              f"   {'OK' if sensitivity else 'FALLA'}")
        print(f"  especificidad  el tier que ademas gana, y el menu de un solo "
              f"tier -> {quiet}   {'OK' if specificity else 'FALLA'}")
        if not (sensitivity and specificity):
            print("  EL DETECTOR NO IMPRIME.")
        print()
    return sensitivity and specificity


# --------------------------------------------------------------------------

def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", action="store_true",
                        help="replay del corpus congelado (determinista)")
    parser.add_argument("--games", type=int, default=0,
                        help="ademas, N partidas contra cada mazo de control")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--dump", default=None, help="volcar las filas crudas")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--no-self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return 0 if self_test() else 1
    if not args.no_self_test and not self_test():
        return 1
    if not args.corpus and not args.games:
        raise SystemExit("nada que medir: usa --corpus y/o --games N")

    agent = sp.load_agent(_ROOT / "main.py", "censo_tier")
    registro = Registro()
    restore = instrument(agent, registro)
    loads = []
    try:
        if args.corpus:
            loads.append(pass_corpus(agent, registro))
        if args.games:
            loads.append(pass_games(agent, args.games, _DECKS))
    finally:
        restore()

    for line in loads:
        print(line)
    rows = registro.rows()
    print(f"\n{registro.menus} menus MAIN, {registro.inversions} inversiones "
          f"({100.0 * registro.inversions / max(1, registro.menus):.2f}%), "
          f"{len(rows)} pares de tier\n")
    print(f"{'tier gana':>9} {'tier pierde':>11} {'n':>6} {'hueco med':>10} "
          f"{'hueco max':>10}   el peor caso")
    for row in rows[:args.top]:
        print(f"{row['tier_win']:>9} {row['tier_lose']:>11} {row['n']:>6} "
              f"{row['median_gap']:>10} {row['max_gap']:>10}   "
              f"{row['worst_win']} sobre {row['worst_lose']}")
        _seat = (f"{row['takes_last_seat']}/{row['seats_known']} bajan un "
                 f"POKEMON al ULTIMO asiento" if row['seats_known'] else
                 "el ganador no gasta asiento")
        print(f"{'':>39}   en {row['worst_where']}   {_seat}")
        print(f"{'':>39}   el apartado se jugo despues {row['recovered']} veces"
              f", NUNCA {row['lost']}")
    if len(rows) > args.top:
        print(f"... y {len(rows) - args.top} pares mas")

    _rec = sum(r["recovered"] for r in rows)
    _lost = sum(r["lost"] for r in rows)
    print(f"\nDE LAS {registro.inversions} INVERSIONES, el orden solo COSTO algo "
          f"en {_lost}: en las otras {_rec} la opcion apartada se jugo mas tarde "
          f"en el mismo turno ({100.0*_lost/max(1,_lost+_rec):.1f}% de perdida "
          f"real, {100.0*_lost/max(1,registro.menus):.2f}% de los menus).")
    print("\nLAS QUE NO VOLVIERON (tier 70 = el ataque cerro el turno, y "
          "abandonarlas era lo correcto):")
    from collections import Counter as _C
    for (key, loser, where), n in _C(registro.lost_where).most_common(12):
        print(f"  tier {key[0]:>3} sobre {key[1]:<3}  {loser:<34} "
              f"{where[0] if where else '?'} t{where[1] if where else '?'}"
              + (f"  x{n}" if n > 1 else "")
              + ("   <- el ataque cerro el turno" if key[0] == 70 else ""))

    print("\nUNA INVERSION NO ES UN DEFECTO: es la forma que tiene el tier de "
          "hacer su trabajo, y la mayoria de estas filas son correctas. Lo que "
          "se lee es el HUECO -- un orden que gana por 600 veces la puntuacion "
          "que aparta no es el mismo objeto que uno que gana por 40.")

    if args.dump:
        Path(args.dump).write_text(json.dumps(rows, indent=1, ensure_ascii=False),
                                   encoding="utf-8")
        print(f"\nfilas crudas -> {args.dump}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
