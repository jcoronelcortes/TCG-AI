"""Things that must never be true, checked on every decision of every game.

T2.1 of docs/night-plan-2026-08-09.md, and the answer to the estate's oldest
structural weakness: the suite is a MEMORY. Almost every file in tests/ is named
after a game that was lost, which is why fixed mistakes stay fixed and why
nothing covers a board no game has produced yet. An invariant needs no human to
know the right play -- it only needs to know what is impossible -- so it can be
checked on thousands of games an hour and turn compute into fixtures.

WHAT IT WATCHES

  * `ILLEGAL_INDEX`    -- a choice outside the option list, or the wrong count.
                          An exception in the container costs a whole game
                          regardless of strategy.
  * `END_EMPTY_BENCH`  -- ending a turn with nothing on the bench, which loses
                          the game the moment the active falls. There is already
                          a last-resort net for this in main.py; this is the
                          check that it holds.
  * `STALE_FLAG`       -- see below. The big one.

STALE_FLAG, and why it is worth its own tool. Of the roughly twenty fixes made
on 7-8 August 2026, FIVE were one shape: a flag on AGENT_STATE armed under some
premise, and consumed later in the same turn after that premise had died. The
canonical one is `_ub_engine_pivot_turn`: main.py:2036 arms it while a bench seat
is free, main.py:3552 clears it only when the TURN changes, and in between a
Pokemon can come down and fill the bench. The flag does not notice. An Ultra Ball
then digs for a body that cannot be played -- two cards spent on a card that
sleeps in hand.

The premise is inside the agent and the flag is a bare bool, so there is nothing
to check unless the premise is written down. That is what `PROMISES` is: a
registry mapping each flag to a predicate over the OBSERVATION that must still
hold while the flag is up. It is seeded with the flags that have already failed,
and every run prints how many boolean flags on AGENT_STATE are NOT registered,
so the blind spot is a number rather than a silence.

VALIDATE IT BEFORE TRUSTING ITS ZERO -- both halves, because a detector has two
ways to be useless and only one of them looks like a result:

  * sensitivity: an injected violation must be caught;
  * specificity: an untouched run must not fire on the invariants that are
    structurally impossible for a correct agent (a legal index, chiefly).

Both run first by default and abort the run if they fail. The first version of
the differential oracle had only the sensitivity half and over-reported by three
orders of magnitude for hours before anyone noticed.

Usage:
    python utils/invariant_monitor.py --games 500
    python utils/invariant_monitor.py --games 2000 --opponent deck/opponents/marnie_grimmsnarl.csv
    python utils/invariant_monitor.py --games 200 --dump log/violations
    python utils/invariant_monitor.py --self-test-only
"""

import argparse
import copy
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402
from cg.api import OptionType  # noqa: E402

END_OPTION = int(OptionType.END)


# --------------------------------------------------------------------------
# Reading the board
# --------------------------------------------------------------------------

def my_side(obs):
    try:
        return obs["current"]["players"][obs["current"]["yourIndex"]]
    except (KeyError, IndexError, TypeError):
        return {}


def free_bench_seats(obs):
    side = my_side(obs)
    bench = [b for b in (side.get("bench") or []) if b]
    return max(0, (side.get("benchMax") or 5) - len(bench))


def supporter_spent(obs):
    return bool((obs.get("current") or {}).get("supporterPlayed"))


# --------------------------------------------------------------------------
# G-A: the premise each promise is written on
# --------------------------------------------------------------------------
#
# Each entry is (flag name, human premise, predicate over the observation that
# must hold WHILE the flag is up). A flag whose premise is false is a promise
# whose reason to exist has died, and the code that reads it cannot tell.

PROMISES = [
    ("_ub_engine_pivot_turn",
     "a free bench seat, so the body the Ultra Ball digs can actually come down",
     lambda obs: free_bench_seats(obs) >= 1),
    ("_ub_meowth_pending",
     "a free bench seat AND the turn's Supporter still unspent -- the Meowth is "
     "only worth digging as the first half of Meowth -> Lillie's",
     lambda obs: free_bench_seats(obs) >= 1 and not supporter_spent(obs)),
    ("_ub_fez_pending",
     "a free bench seat for the Fezandipiti",
     lambda obs: free_bench_seats(obs) >= 1),
]

_REGISTERED = {name for name, _why, _p in PROMISES}


def unregistered_flags(mod):
    """Boolean flags on AGENT_STATE with no premise written down."""
    try:
        state = vars(mod.AGENT_STATE)
    except (AttributeError, TypeError):
        return []
    return sorted(k for k, v in state.items()
                  if isinstance(v, bool) and k not in _REGISTERED)


# --------------------------------------------------------------------------
# The invariants
# --------------------------------------------------------------------------

def check_illegal_index(obs, choice):
    options = (obs.get("select") or {}).get("option") or []
    if choice is None:
        return "the agent returned None instead of a choice"
    if not isinstance(choice, (list, tuple)):
        return f"the choice is not a list: {type(choice).__name__}"
    for i in choice:
        if not isinstance(i, int) or i < 0 or i >= len(options):
            return f"index {i!r} outside an option list of {len(options)}"
    select = obs.get("select") or {}
    low = select.get("minCount")
    high = select.get("maxCount")
    if isinstance(low, int) and len(choice) < low:
        return f"chose {len(choice)} options with minCount {low}"
    if isinstance(high, int) and high >= 0 and len(choice) > high:
        return f"chose {len(choice)} options with maxCount {high}"
    return None


def check_end_with_empty_bench(obs, choice):
    options = (obs.get("select") or {}).get("option") or []
    ends = any(0 <= i < len(options)
               and options[i].get("type") == END_OPTION
               for i in (choice or []))
    if not ends:
        return None
    side = my_side(obs)
    bench = [b for b in (side.get("bench") or []) if b]
    if bench:
        return None
    return "ending the turn with an empty bench: the next knockout is the game"


def check_stale_flags(obs, mod):
    """G-A. A promise still up whose premise has died."""
    out = []
    try:
        state = mod.AGENT_STATE
    except AttributeError:
        return out
    for name, why, premise in PROMISES:
        if not getattr(state, name, False):
            continue
        try:
            alive = premise(obs)
        except Exception:
            continue
        if not alive:
            out.append(f"{name} is up but its premise died: {why}")
    return out


# --------------------------------------------------------------------------
# Driving
# --------------------------------------------------------------------------

def over_games(games, opponent=None, saboteur=None, progress=None):
    from cg import game

    agents = [sp.load_agent(str(_ROOT / "main.py"), "inv_p0"),
              sp.load_agent(str(_ROOT / "main.py"), "inv_p1")]
    deck = sp.read_deck()
    op_deck = sp.read_deck(opponent) if opponent else list(deck)

    stats = {"games": 0, "decisions": 0, "raised": 0}
    findings = []

    def record(kind, detail, obs, game_no, step, seat):
        findings.append({"kind": kind, "detail": detail, "game": game_no,
                         "step": step, "seat": seat, "observation": obs})

    for game_no in range(games):
        for m in agents:
            sp._reset_si_aplica(m)
        obs, _sd = game.battle_start(list(deck), list(op_deck))
        if obs is None:
            continue
        stats["games"] += 1
        steps = 0
        try:
            while obs and obs["current"]["result"] == -1 and steps < 3000:
                yi = obs["current"]["yourIndex"]
                mod = agents[yi]
                snapshot = copy.deepcopy(obs)
                try:
                    choice = mod.agent(obs)
                except Exception as exc:
                    stats["raised"] += 1
                    record("AGENT_RAISED", repr(exc), snapshot, game_no, steps, yi)
                    break
                if saboteur is not None:
                    saboteur(mod)

                bad = check_illegal_index(snapshot, choice)
                if bad:
                    record("ILLEGAL_INDEX", bad, snapshot, game_no, steps, yi)
                else:
                    bad = check_end_with_empty_bench(snapshot, choice)
                    if bad:
                        record("END_EMPTY_BENCH", bad, snapshot, game_no, steps, yi)
                for stale in check_stale_flags(snapshot, mod):
                    record("STALE_FLAG", stale, snapshot, game_no, steps, yi)

                if bad and "index" in (bad or ""):
                    break              # an illegal index cannot be resolved
                obs = game.battle_select(choice)
                stats["decisions"] += 1
                steps += 1
        finally:
            game.battle_finish()
        if progress and stats["games"] % progress == 0:
            print(f"  ... {stats['games']}/{games} partidas, "
                  f"{len(findings)} violaciones", flush=True)
    return stats, findings, agents[0]


# --------------------------------------------------------------------------
# Validating the monitor
# --------------------------------------------------------------------------

def _sabotage_arm_every_promise(mod):
    """Hold every promise up permanently. Its premise must die eventually."""
    for name, _why, _p in PROMISES:
        try:
            setattr(mod.AGENT_STATE, name, True)
        except AttributeError:
            pass


def self_test(games=8, opponent=None):
    print("Auto-test 1/2 (sensibilidad): se dejan las promesas armadas a la fuerza ...",
          flush=True)
    _stats, findings, _m = over_games(games, opponent=opponent,
                                      saboteur=_sabotage_arm_every_promise)
    stale = [f for f in findings if f["kind"] == "STALE_FLAG"]
    if not stale:
        print("AUTO-TEST FALLIDO: una promesa sin premisa no se detecto.",
              file=sys.stderr)
        return False
    print(f"  OK: {len(stale)} STALE_FLAG sobre el sabotaje.", flush=True)

    print("Auto-test 2/2 (especificidad): sin sabotaje no puede haber indices ilegales ...",
          flush=True)
    stats, honest, _m = over_games(games, opponent=opponent)
    illegal = [f for f in honest if f["kind"] in ("ILLEGAL_INDEX", "AGENT_RAISED")]
    if illegal:
        print(f"AUTO-TEST FALLIDO: {len(illegal)} indices ilegales o excepciones "
              f"en una corrida limpia -- o el agente esta roto, o el checker lo esta.",
              file=sys.stderr)
        for f in illegal[:3]:
            print(f"    {f['kind']}: {f['detail']}", file=sys.stderr)
        return False
    print(f"  OK: {stats['decisions']} decisiones limpias, 0 ilegales.\n", flush=True)
    return True


def dump(findings, where):
    out = Path(where)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for n, f in enumerate(findings):
        name = f"{f['kind'].lower()}_g{f.get('game', 0)}_s{f.get('step', 0)}_{n}.json"
        path = out / name
        path.write_text(json.dumps({"observation": f.pop("observation", None),
                                    "violation": f}, indent=1), encoding="utf-8")
        written.append(str(path))
    return written


def report(stats, findings, mod):
    print("\nMonitor de invariantes")
    print(f"Partidas: {stats['games']}   decisiones: {stats['decisions']}")
    pending = unregistered_flags(mod)
    print(f"Promesas con premisa escrita: {len(PROMISES)}   "
          f"banderas booleanas SIN premisa: {len(pending)}")
    if pending:
        print(f"  (sin vigilar: {', '.join(pending)})")
    by_kind = {}
    for f in findings:
        by_kind.setdefault(f["kind"], []).append(f)
    if not findings:
        print("\nViolaciones: NINGUNA. (Los dos auto-tests confirman que el "
              "monitor sabe fallar y sabe callarse.)")
        return
    print("\nViolaciones:")
    for kind, items in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        print(f"  {kind}: {len(items)}")
        for f in items[:4]:
            print(f"    partida {f.get('game')} paso {f.get('step')}: {f['detail']}")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--opponent", default=None)
    parser.add_argument("--dump", default=None)
    parser.add_argument("--progress", type=int, default=None)
    parser.add_argument("--no-self-test", action="store_true")
    parser.add_argument("--self-test-only", action="store_true")
    args = parser.parse_args(argv)

    if not args.no_self_test:
        if not self_test(opponent=args.opponent):
            return 2
        if args.self_test_only:
            return 0

    stats, findings, mod = over_games(args.games, opponent=args.opponent,
                                      progress=args.progress)
    report(stats, findings, mod)
    if args.dump and findings:
        written = dump(findings, args.dump)
        print(f"\n{len(written)} observaciones escritas en {args.dump}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
