"""How often the Cubchoo lock leaves us muted with a prize on the bench, and
what the agent does about it.

WHY A CENSUS AND NOT A WINRATE. Against this deck the reference bot is a slow
control that cannot knock us out (*Snotted Up* does 10), so games against it end
saturated and a rule that changes one decision per turn moves the winrate by less
than its own noise floor -- the same wall
[[anti-cubchoo-no-retirada-pivote-conservar-energia]] hit when it measured 4
flips in 40 759 decisions and got -3.5 / -2.0 / +0.3 out of three self-play gates
of the same change. What arbitrates here is the FREQUENCY of the board and what
we did on it, which is what this counts.

WHAT IT COUNTS, per menu of ours where the matchup is on:

    mute       our active cannot attack (`can_attack` is False) -- the lock is
               actually on us, not merely present in their deck
    retreat    ...and RETREAT is on the menu, so a pivot is legal
    prize      ...and a benched body KNOCKS THEIR ACTIVE OUT (`_bdg_retreat_ko`):
               the turn has a prize in it
    vetoed     ...and the retreat scored <= 0 anyway. THIS is the population the
               reading is about: a prize on the table and the pivot priced below
               ending the turn.
    frozen     the same board handed over on CONSECUTIVE turns -- the shape that
               makes this expensive, since the lock does not move on its own and
               a board we pass on once we pass on forever.

Two sources, and they answer different questions:

    --records   the recorded games in `records/` (default). Slow-motion and
                exact: it replays our seat menu by menu with the agent as it
                stands today, so it also says WHICH turns froze.
    --games N   self-play against the Cubchoo lists. Wider, and the only way to
                see boards the corpus never recorded.

WHAT IT MEASURED (14 August 2026, episode 93149196, the game that produced the
rule -- `records/registro_010_pasos_079_hasta_081.json` step 81). 91 menus of
ours, 90 with the matchup on, 69 with the lock ON US, 18 of those with a retreat
legal and a prize on the bench:

    before      13 of the 18 vetoed. Turns 10, 12, 14, 16 and 18 are the same
                frozen board -- muted Teal Mask Ogerpon ex with 4 Grass, its twin
                charged on the bench, a 70 HP Cubchoo in front -- handed over
                five times, prizes stuck at 3-6.
    after       1 vetoed, and it is turn 10 action 1, where the twin is still one
                Teal Dance short of its attack cost: the agent dances first and
                retreats at the end of that same turn. Zero frozen turns.

Reproduce the "before" column by switching the reading off before the census
runs, which is what its named flag is for:

    python -c "import main; main.CUBCHOO_MUTE_ROTATION = False; \
        import sys; sys.argv = ['x', '--verbose']; \
        import utils.census_the_lock_charges_the_rotation as c; c.main()"

The wider exposure -- 7.4 boards with a prize on the bench PER GAME on both
Cubchoo lists and exactly 0 on lists without the card -- is measured by
`utils/gate_the_lock_charges_the_rotation.py --census`, which is where the
self-play half of this question lives.

Usage:
    python utils/census_the_lock_charges_the_rotation.py
    python utils/census_the_lock_charges_the_rotation.py --verbose
    python utils/census_the_lock_charges_the_rotation.py --games 100
"""

import argparse
import copy
import glob
import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import main as m  # noqa: E402
from patching import instalar  # noqa: E402
from ptcg.cards.tables import card_table  # noqa: E402

# The flags the census reads out of `agent()`. They are captured with a tracer
# rather than recomputed here for the reason every instrument in this directory
# repeats: a census that reimplements the reading measures the reimplementation.
_WATCH = ("op_is_cubchoo_deck", "can_attack", "_bdg_retreat_ko",
          "_cubchoo_lock_stuck", "_cubchoo_mute_cashes_prize",
          "_cubchoo_mute_rotates")


def _name(card_id):
    return getattr(card_table.get(card_id), "name", str(card_id))


def _reset():
    """The turn-scoped state `agent()` keeps between calls.

    Each observation is fed cold: the census asks "what would today's agent do on
    THIS board", not "how does a replayed game drift".
    """
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m.op_is_starmie_deck = False
    m._field_at_turn_start = {}
    m._grass_attaches_this_turn = 0


def _ask(obs):
    """Run one menu and return (choice, per-option scores, captured flags)."""
    seen = {}

    def spy(context, select, scores, obs_, my_index, top_n=3):
        seen["scores"] = list(scores)

    capt = {}

    def tracer(frame, event, arg):
        if frame.f_code.co_name != "agent":
            return None
        if event == "return":
            for k in _WATCH:
                if k in frame.f_locals:
                    capt[k] = frame.f_locals[k]
        return tracer

    orig = m._debug_log_decision
    instalar("_debug_log_decision", spy)
    prev_dbg = m.DEBUG_DECISIONS
    m.DEBUG_DECISIONS = True
    previous_tracer = sys.gettrace()
    sys.settrace(tracer)
    try:
        choice = m.agent(obs)
    finally:
        sys.settrace(previous_tracer)
        instalar("_debug_log_decision", orig)
        m.DEBUG_DECISIONS = prev_dbg
    return choice, seen.get("scores"), capt


def _our_menus_from_records(paths):
    """Every menu of OURS in the given records, in turn order, deduplicated.

    The records overlap at their edges -- a step can appear as the tail of one
    file and the head of the next -- so a menu is keyed by (turn, action) and the
    first copy wins. Observations with no `select` are not decisions.
    """
    by_key = {}
    for path in paths:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for pair in data.get("steps", []):
            for slot in pair:
                obs = slot.get("observation") or {}
                if slot.get("status") != "ACTIVE" or not obs.get("select"):
                    continue
                cur = obs.get("current") or {}
                if cur.get("yourIndex") != 1:
                    continue
                by_key.setdefault(
                    (cur.get("turn"), cur.get("turnActionCount")),
                    (Path(path).name, obs))
    return [(k, v[0], v[1]) for k, v in sorted(by_key.items())]


def census_records(paths, verbose):
    counts = Counter()
    rows = []
    _reset()
    for (turn, action), fname, obs in _our_menus_from_records(paths):
        try:
            choice, scores, capt = _ask(copy.deepcopy(obs))
        except Exception as exc:                      # a menu we cannot replay
            counts["unreadable"] += 1
            if verbose:
                print(f"  [!] {fname} turn {turn} action {action}: {exc}")
            continue
        counts["menus"] += 1
        if not capt.get("op_is_cubchoo_deck"):
            continue
        counts["matchup"] += 1
        if capt.get("can_attack"):
            continue
        counts["mute"] += 1
        types = [o["type"] for o in obs["select"]["option"]]
        if int(m.OptionType.RETREAT) not in types:
            continue
        counts["retreat"] += 1
        ri = types.index(int(m.OptionType.RETREAT))
        if not capt.get("_bdg_retreat_ko"):
            continue
        counts["prize"] += 1
        vetoed = scores[ri] <= 0
        if vetoed:
            counts["vetoed"] += 1
        cur = obs["current"]
        mine, opp = cur["players"][1], cur["players"][0]
        act = mine["active"][0]
        rows.append(dict(turn=turn, action=action, vetoed=vetoed,
                         active=_name(act["id"]),
                         cards=len(act.get("energyCards") or []),
                         score=scores[ri],
                         chose=m.OptionType(
                             obs["select"]["option"][choice[0]]["type"]).name,
                         op=_name(opp["active"][0]["id"]),
                         op_hp=opp["active"][0]["hp"],
                         prizes=f'{len(mine["prize"])}-{len(opp["prize"])}'))

    # A turn is FROZEN when its last menu handed the turn over with the prize
    # still on the bench. Consecutive frozen turns are the expensive shape: the
    # lock does not move on its own.
    last_of_turn = {}
    for r in rows:
        if r["vetoed"] or last_of_turn.get(r["turn"], {}).get("action", -1) < r["action"]:
            last_of_turn.setdefault(r["turn"], r)
    frozen = sorted(t for t, r in last_of_turn.items()
                    if all(x["vetoed"] for x in rows if x["turn"] == t))

    if verbose and rows:
        print(f"{'turn':>4} {'act':>4} {'our active':22} {'crd':>3} "
              f"{'retreat':>9} {'chose':8} {'their active':14} {'hp':>4} pr")
        for r in rows:
            print(f"{r['turn']:>4} {r['action']:>4} {r['active']:22} "
                  f"{r['cards']:>3} {str(r['score']):>9} {r['chose']:8} "
                  f"{r['op']:14} {r['op_hp']:>4} {r['prizes']}")
        print()

    print(f"  menus replayed          {counts['menus']}")
    print(f"  vs the Cubchoo lock     {counts['matchup']}")
    print(f"  ...and we are MUTED     {counts['mute']}")
    print(f"  ...and RETREAT is legal {counts['retreat']}")
    print(f"  ...and a PRIZE is there {counts['prize']}")
    print(f"  ...and we pass anyway   {counts['vetoed']}")
    print(f"  turns handed over frozen: {frozen or 'none'}")
    if counts["unreadable"]:
        print(f"  (unreadable menus: {counts['unreadable']})")
    return counts


def census_games(games, decks, verbose):
    """The same population, over self-play instead of the recorded games.

    Wider than the corpus and the only way to see boards no record holds, at the
    price of the opponent being the reference bot and not a human.
    """
    import selfplay as sp
    from opponent_bot import OpponentBot

    agent = sp.load_agent(_ROOT / "main.py", "arm_census")
    counts = Counter()
    plain = agent.score_option

    def counted(tc, option, score):
        out = plain(tc, option, score)
        if getattr(tc, "op_is_cubchoo_deck", False):
            counts["matchup"] += 1
            if tc.can_attack is False:
                counts["mute"] += 1
                if option.type == int(m.OptionType.RETREAT):
                    counts["retreat"] += 1
                    if tc._bdg_retreat_ko:
                        counts["prize"] += 1
                        if out <= 0:
                            counts["vetoed"] += 1
        return out

    agent.score_option = counted
    for deck in decks:
        sp.play_games(agent, OpponentBot(deck), games, progress=verbose)
    for k in ("matchup", "mute", "retreat", "prize", "vetoed"):
        print(f"  {k:22} {counts[k]}")
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records", nargs="*", default=None,
                    help="record files to replay (default: every records/registro_*.json)")
    ap.add_argument("--games", type=int, default=0,
                    help="instead of the records, N self-play games per Cubchoo list")
    ap.add_argument("--decks", nargs="*",
                    default=["deck/opponents/cornerstone_cubchoo.csv",
                             "deck/opponents/crustle_cubchoo_spheal.csv"])
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    if args.games:
        return census_games(args.games, args.decks, args.verbose)
    paths = args.records or sorted(
        glob.glob(str(_ROOT / "records" / "registro_*.json")))
    if not paths:
        raise SystemExit("no records to replay")
    return census_records(paths, args.verbose)


if __name__ == "__main__":
    main()
