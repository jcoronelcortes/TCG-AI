"""What the turn ITSELF yields, on a board the winrate oracle cannot separate.

WHY THIS EXISTS. `utils/oracle_the_body_search_cannot_buy_the_energy.py` grades
a board by rolling the whole game out from it, and on the second board of this
sentence -- `records/registro_005_pasos_035_hasta_044.json` step 35, episode
93224301 turn 5 vs Dragapult -- it comes back blind:

    con la lectura  PLAY Ultra Ball -> 100/100  margen +5.94
    sin ella        PLAY Dawn       -> 100/100  margen +5.96
    delta +0 pp / -0.02   suelo del tablero 0 pp / 0.06  -> dentro del suelo

Both arms win every rollout because the POSITION is already winning, not
because the two choices are worth the same. A saturated board is not a tie: it
is an instrument at its ceiling, and the honest answer is to ask a question the
ceiling does not swallow.

WHAT IS MEASURED. The same forced choice, then OUR OWN AGENT plays the rest of
**this turn only**, and the turn is scored by what it actually produced:

    prizes      prize cards taken during the turn (our pile 6 -> 4 is two)
    attached    energy cards that ended the turn on our bodies, minus what was
                already there: an energyless turn that stays energyless is the
                whole complaint
    hand        cards in hand when the turn ends -- the refill the Supporter
                slot was being spent on
    attacked    whether the turn ended in an attack at all

N determinizations, the SAME seed list for both arms, so the two see the same
sampled worlds (their hand and both prize sets are hidden; see
`search_oracle.determinize`). The agent's belief is reset before every walk.

THE CRITERION, written before running it: the reading is carried on this board
if it takes MORE prizes in the turn on the majority of worlds and never fewer
on the average. A refill that buys a fresh hand but no prizes would show up as
`hand` up and `prizes` flat, and that is a different claim from the one the
docs make -- so the columns are printed apart rather than summed into a score.

Usage:
    python utils/turn_yield_the_body_search_cannot_buy_the_energy.py
    python utils/turn_yield_the_body_search_cannot_buy_the_energy.py --n 30
"""

import argparse
import copy
import json
import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import search_oracle as so                                          # noqa: E402
import selfplay as sp                                               # noqa: E402
from cg import api                                                  # noqa: E402
from cg.api import OptionType                                       # noqa: E402

DEFAULT_RECORD = "records/registro_005_pasos_035_hasta_044.json"
DEFAULT_STEP = 35
DEFAULT_THEIRS = "deck/real_opponents/dragapult_1.csv"


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _attached(obs, seat):
    """Energy CARDS on `seat`'s bodies (the counter `energies` doubles with Wild
    Growth, so the CARDS are what an attachment can be counted in).

    The seat is passed in and never read from `yourIndex`: the observation that
    closes the walk is the one handed to the OPPONENT, and reading `yourIndex`
    there measures their board instead of ours -- which is exactly what this
    printed until it was caught (-2.00 attached on a turn that attached one).
    """
    mine = (obs.get("current") or {}).get("players") or []
    if seat >= len(mine):
        return 0
    bodies = [p for p in (list(mine[seat].get("active") or [])
                          + list(mine[seat].get("bench") or [])) if p]
    return sum(len(p.get("energyCards") or []) for p in bodies)


def _board(record, step):
    data = json.loads(Path(_ROOT / record).read_text(encoding="utf-8"))
    for pair in data.get("steps", []):
        for item in pair:
            obs = item.get("observation") or {}
            if obs.get("step") == step and item.get("status") == "ACTIVE":
                return copy.deepcopy(obs)
    raise SystemExit(f"no hay paso {step} ACTIVO en {record}")


def walk_turn(obs0, our_deck, their_deck, forced, seed, agent, max_steps=80):
    """Force `forced`, then let `agent` finish THIS turn. Returns the yield."""
    rng = random.Random(seed)
    det = so.determinize(obs0, None, our_deck, their_deck, rng=rng)
    us = obs0["current"]["yourIndex"]
    turn0 = obs0["current"]["turn"]
    prizes0 = len(_mine(obs0).get("prize") or [])
    att0 = _attached(obs0, us)

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
        if cur.get("yourIndex") != us or cur.get("turn") != turn0:
            break                       # the turn is over: the opponent is up
        if not (obs.get("select") or {}).get("option"):
            break
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
    return {
        "prizes": prizes0 - len(mine.get("prize") or []),
        "attached": _attached(obs, us) - att0,
        "hand": int(mine.get("handCount") or 0),
        "attacked": attacked,
    }


def _arms():
    import gate_the_body_search_cannot_buy_the_energy as gate
    candidate = gate.arm("turn_yield_with", True)
    base = gate.arm("turn_yield_without", False)
    gate.provenance(candidate, base, control=False)
    return candidate, base


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=50, help="worlds per arm")
    ap.add_argument("--record", default=DEFAULT_RECORD)
    ap.add_argument("--step", type=int, default=DEFAULT_STEP)
    ap.add_argument("--opponent", default=DEFAULT_THEIRS)
    args = ap.parse_args(argv)

    import local_engine
    local_engine.load()

    candidate, base = _arms()
    obs0 = _board(args.record, args.step)
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

    print(f"{args.record} paso {args.step} vs {Path(args.opponent).stem}, "
          f"{args.n} mundos por brazo\n")
    rows = {}
    try:
        for name, choice, agent in (("con la lectura", with_choice, candidate),
                                    ("sin ella", without_choice, base)):
            out = []
            for i in range(args.n):
                sp._reset_si_aplica(agent)
                out.append(walk_turn(obs0, our_deck, their_deck, choice,
                                     1000 + i, agent))
            rows[name] = out
    finally:
        api.search_end()

    print(f"{'':16s} {'premios':>9s} {'energia':>9s} {'mano':>7s} {'ataco':>7s}")
    for name, label in (("con la lectura", label_with), ("sin ella", label_without)):
        out = rows[name]
        n = len(out) or 1
        print(f"{name:16s} {sum(r['prizes'] for r in out) / n:9.2f} "
              f"{sum(r['attached'] for r in out) / n:9.2f} "
              f"{sum(r['hand'] for r in out) / n:7.2f} "
              f"{100 * sum(1 for r in out if r['attacked']) / n:6.0f}%   {label}")

    a, b = rows["con la lectura"], rows["sin ella"]
    better = sum(1 for x, y in zip(a, b) if x["prizes"] > y["prizes"])
    worse = sum(1 for x, y in zip(a, b) if x["prizes"] < y["prizes"])
    print(f"\npor mundo: {better}/{args.n} con MAS premios, {worse}/{args.n} con menos")
    print("EL CRITERIO (escrito antes de correrlo): mas premios en la mayoria de "
          "los mundos y nunca menos de media." )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
