"""What the TURN itself yields, on a board the winrate oracle cannot separate.

WHY THIS EXISTS. `utils/oracle_the_refill_buys_the_wave.py` grades a board by
rolling the whole game out from it, and on this board it comes back with both
arms winning the same number of rollouts: the position is decided by more than
one turn, and a saturated instrument is not a tie. What this rule changes is
what ONE TURN is worth -- two prizes instead of one, and a 1-prize body left in
the front spot instead of a 2-prize ex -- so that is what gets measured.

WHAT IS MEASURED. The same forced choice on the same board, then OUR OWN AGENT
plays the rest of **this turn only**, and the turn is scored by what it produced:

    prizes      prize cards taken during the turn (our pile 6 -> 4 is two)
    attached    energy cards that ended the turn on our bodies, minus what was
                already there
    hand        cards in hand when the turn ends
    front       the body left in the ACTIVE spot -- the other half of the
                sentence, because Do the Wave is thrown by a ONE-prize body and
                Syrup Storm by a two-prize one

THEIR ANSWERS INSIDE OUR TURN ARE PLAYED BY THE REFERENCE BOT, and they have to
be: Festival Lead only throws its second wave *after the opponent chooses a new
Active*, so a walk that stops at the first knockout measures exactly the half of
the turn this rule is about and reports one prize for both arms.

N determinizations, the SAME seed list for both arms, so the two see the same
sampled worlds (their hand and both prize sets are hidden; see
`search_oracle.determinize`). The agent's belief is reset before every walk.

THE CRITERION, written before running it: the reading is carried on this board
if it takes MORE prizes in the turn on the majority of the worlds where the two
differ, and never fewer on the average.

Usage:
    python utils/turn_yield_the_refill_buys_the_wave.py
    python utils/turn_yield_the_refill_buys_the_wave.py --n 20
"""

import argparse
import copy
import json
import random
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import search_oracle as so                                          # noqa: E402
import selfplay as sp                                               # noqa: E402
from cg import api                                                  # noqa: E402
from cg.api import OptionType                                       # noqa: E402

DEFAULT_RECORD = "records/registro_006_pasos_061_hasta_085.json"
DEFAULT_THEIRS = "deck/real_opponents/festival_lead_1.csv"


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _attached(obs, seat):
    """Energy CARDS on `seat`'s bodies (the `energies` counter doubles with Wild
    Growth, so the CARDS are what an attachment can be counted in).

    The seat is passed in and never read from `yourIndex`: the observation that
    closes the walk may be the one handed to the OPPONENT, and reading
    `yourIndex` there measures their board instead of ours.
    """
    mine = (obs.get("current") or {}).get("players") or []
    if seat >= len(mine):
        return 0
    bodies = [p for p in (list(mine[seat].get("active") or [])
                          + list(mine[seat].get("bench") or [])) if p]
    return sum(len(p.get("energyCards") or []) for p in bodies)


def _board(record):
    """The first ACTIVE frame of OUR seat in the record: the board being graded.

    The ACTIVE frame of a Kaggle log carries no `step` key -- only the inactive
    seat's copy does -- so the frame is found by seat and status, which is what
    the record actually guarantees.
    """
    data = json.loads(Path(_ROOT / record).read_text(encoding="utf-8"))
    for pair in data.get("steps", []):
        for item in pair:
            obs = item.get("observation") or {}
            if item.get("status") != "ACTIVE" or not obs.get("select"):
                continue
            return copy.deepcopy(obs)
    raise SystemExit(f"no hay ningun paso ACTIVO en {record}")


def walk_turn(obs0, our_deck, their_deck, forced, seed, agent, max_steps=90):
    """Force `forced`, then let `agent` finish THIS turn. Returns the yield."""
    from opponent_bot import OpponentBot

    rng = random.Random(seed)
    det = so.determinize(obs0, None, our_deck, their_deck, rng=rng)
    us = obs0["current"]["yourIndex"]
    turn0 = obs0["current"]["turn"]
    prizes0 = len(_mine(obs0).get("prize") or [])
    att0 = _attached(obs0, us)
    them = OpponentBot()

    root = api.search_begin(api.to_observation_class(obs0),
                            det["your_deck"], det["your_prize"],
                            det["opponent_deck"], det["opponent_prize"],
                            det["opponent_hand"], det["opponent_active"])
    attacked = False
    state = so._step_raw(root.searchId, list(forced))
    obs = state["observation"]
    steps = 1
    while steps < max_steps:
        cur = obs.get("current") or {}
        if cur.get("result", -1) != -1:
            break
        if cur.get("turn") != turn0:
            break                       # the turn is over: the opponent is up
        if not (obs.get("select") or {}).get("option"):
            break
        if cur.get("yourIndex") != us:
            # Their forced answers INSIDE our turn -- promoting after a
            # knockout, which is what lets Festival Lead throw the second wave.
            choice = list(them.agent(obs))
        else:
            choice = list(agent.agent(obs))
            opts = obs["select"]["option"]
            if choice and choice[0] < len(opts):
                if opts[choice[0]].get("type") == int(OptionType.ATTACK):
                    attacked = True
        state = so._step_raw(state["searchId"], choice)
        obs = state["observation"]
        steps += 1

    cur = obs.get("current") or {}
    mine = (cur.get("players") or [{}, {}])[us] if cur.get("players") else {}
    front = [p for p in (mine.get("active") or []) if p]
    return {
        "prizes": prizes0 - len(mine.get("prize") or []),
        "attached": _attached(obs, us) - att0,
        "hand": int(mine.get("handCount") or 0),
        "attacked": attacked,
        "front": front[0].get("id") if front else 0,
    }


def _arms():
    import gate_the_refill_buys_the_wave as gate
    candidate = gate.arm("turn_yield_with", True)
    base = gate.arm("turn_yield_without", False)
    gate.provenance(candidate, base, control=False)
    return candidate, base


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=40, help="worlds per arm")
    ap.add_argument("--record", default=DEFAULT_RECORD)
    ap.add_argument("--opponent", default=DEFAULT_THEIRS)
    args = ap.parse_args(argv)

    import local_engine
    local_engine.load()

    candidate, base = _arms()
    obs0 = _board(args.record)
    our_deck = sp.read_deck()
    their_deck = sp.read_deck(_ROOT / args.opponent)

    # The choice each arm makes on this very board, asked and not assumed.
    with_choice = list(candidate.agent(copy.deepcopy(obs0)))
    without_choice = list(base.agent(copy.deepcopy(obs0)))
    if with_choice == without_choice:
        raise SystemExit("los dos brazos eligen lo mismo: no hay tablero que medir")

    import golden_corpus as gc
    label_with = [gc.describe_option(candidate, obs0, i) for i in with_choice]
    label_without = [gc.describe_option(base, obs0, i) for i in without_choice]

    print(f"{args.record} vs {Path(args.opponent).stem}, "
          f"{args.n} mundos por brazo\n")
    rows = {}
    try:
        for name, choice, agent in (("con la lectura", with_choice, candidate),
                                    ("sin ella", without_choice, base)):
            out = []
            for i in range(args.n):
                sp._reset_si_aplica(agent)
                out.append(walk_turn(copy.deepcopy(obs0), our_deck, their_deck,
                                     choice, 1000 + i, agent))
            rows[name] = out
    finally:
        api.search_end()

    print(f"{'':16s} {'premios':>9s} {'energia':>9s} {'mano':>7s} "
          f"{'ataco':>7s}  frente / jugada")
    for name, label in (("con la lectura", label_with), ("sin ella", label_without)):
        out = rows[name]
        n = len(out) or 1
        front = Counter(r["front"] for r in out).most_common(3)
        print(f"{name:16s} {sum(r['prizes'] for r in out) / n:9.2f} "
              f"{sum(r['attached'] for r in out) / n:9.2f} "
              f"{sum(r['hand'] for r in out) / n:7.2f} "
              f"{100 * sum(1 for r in out if r['attacked']) / n:6.0f}%  "
              f"{front}  {label}")

    a, b = rows["con la lectura"], rows["sin ella"]
    better = sum(1 for x, y in zip(a, b) if x["prizes"] > y["prizes"])
    worse = sum(1 for x, y in zip(a, b) if x["prizes"] < y["prizes"])
    print(f"\npor mundo: {better}/{args.n} con MAS premios, {worse}/{args.n} con menos")
    print("EL CRITERIO (escrito antes de correrlo): mas premios en la mayoria "
          "de los mundos en que difieren y nunca menos de media.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
