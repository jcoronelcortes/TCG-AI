"""PER-TURN probe of the jam behind the ex-immune wall (Crustle/Sylveon).

The census of `utils/autopsy.py` left the Crustle matchup located but not
solved: in the losses 64.3% of the turns close WITHOUT ATTACKING (41.7%
in the wins). This probe answers the next question, which is the one that
decides the SHAPE of the fix:

    on the turns that BEGIN with our ex blocked by the wall and with a
    non-ex answer already charged on the bench, how does the turn end?

It is measured PER TURN and not per select on purpose. A normal turn chains several
selects (attach, play a supporter and THEN retreat), so counting selects
throws into the "did nothing" bag the intermediate plays of a turn that did
end up pivoting: a first attempt counted 85 of 113 as "something else" and that number was
an artefact, not a finding.

The turns that end DRY are dumped (the complete observation of the first MAIN,
in the format of the tests/ fixtures) into records/wall_probe/ so the
decision can be reproduced with main.agent() and one can read what scored above the relief.

Usage:
    python utils/wall_probe.py --opponent deck/real_opponents/crustle_wall_2.csv
    python utils/wall_probe.py --opponent ... --games 80 --dump 15
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp
from opponent_bot import BotRival
from cg.api import OptionType, SelectContext

# Non-ex attackers that DO damage the wall (our ex do 0 to it).
def _respuesta_ids(m):
    return {m.Tapu_Bulu, m.Meganium, m.Dipplin}


def _es_main(obs):
    return (obs.get("select") or {}).get("context") == int(SelectContext.MAIN)


def _tipo_elegido(obs, choice):
    try:
        return ((obs.get("select") or {}).get("option") or [])[choice[0]].get("type")
    except (IndexError, TypeError, KeyError):
        return None


def _califica(m, obs, asiento):
    """Does this turn begin with the ex blocked and the answer ready on the bench?"""
    cur = obs["current"]
    yo = cur["players"][asiento]
    op = cur["players"][1 - asiento]
    act = (yo.get("active") or [None])[0]
    oact = (op.get("active") or [None])[0]
    if not act or not oact:
        return False
    if oact.get("id") not in m.EX_IMMUNE_IDS:
        return False
    if act.get("id") not in m.OUR_EX_IDS:
        return False
    respuestas = _respuesta_ids(m)
    for b in (yo.get("bench") or []):
        if not b or b.get("id") not in respuestas:
            continue
        req = m.ATTACK_ENERGY_REQ.get(b["id"]) or 99
        if len(b.get("energies") or []) * m._grass_mult() >= req:
            return True
    return False


def play(m, opponent_deck, games, dump, target_path):
    from cg import game

    summary = Counter()
    secos = []
    for i in range(games):
        asiento = i % 2
        d0 = sp.read_deck() if asiento == 0 else opponent_deck
        d1 = opponent_deck if asiento == 0 else sp.read_deck()
        obs, sd = game.battle_start(list(d0), list(d1))
        if obs is None:
            continue
        agentes = {asiento: m, 1 - asiento: BotRival()}
        steps = 0
        current_turn = None
        state = None  # the current turn's dict, if it qualifies
        try:
            while obs["current"]["result"] == -1 and steps < 3000:
                yi = obs["current"]["yourIndex"]
                turn = obs["current"]["turn"]
                if yi == asiento and _es_main(obs):
                    if turn != current_turn:
                        # It closes the previous turn before opening the new one.
                        if state is not None:
                            summary[state["desenlace"]] += 1
                            if state["desenlace"] == "seco" and len(secos) < dump:
                                secos.append(state["obs"])
                        current_turn = turn
                        state = ({"desenlace": "seco", "obs": obs}
                                  if _califica(m, obs, asiento) else None)
                try:
                    choice = agentes[yi].agent(obs)
                except Exception:
                    break
                if state is not None and yi == asiento and _es_main(obs):
                    t = _tipo_elegido(obs, choice)
                    if t == int(OptionType.ATTACK):
                        state["desenlace"] = "ataca"
                    elif t == int(OptionType.RETREAT) and state["desenlace"] == "seco":
                        # Retreating is the pivot; if it then attacks, "attacks" rules.
                        state["desenlace"] = "retira"
                try:
                    obs = game.battle_select(choice)
                except Exception:
                    break
                steps += 1
            if state is not None:
                summary[state["desenlace"]] += 1
                if state["desenlace"] == "seco" and len(secos) < dump:
                    secos.append(state["obs"])
        finally:
            game.battle_finish()

    if secos:
        target_path.mkdir(parents=True, exist_ok=True)
        for n, o in enumerate(secos, start=1):
            (target_path / f"seco_{n:03d}.json").write_text(
                json.dumps({"observation": o}, ensure_ascii=False), encoding="utf-8")
    return summary, len(secos)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--opponent", default=str(_ROOT / "deck" / "real_opponents"
                                           / "crustle_wall_2.csv"))
    ap.add_argument("--games", type=int, default=60)
    ap.add_argument("--dump", type=int, default=12,
                    help="how many DRY turns to dump to disk (0 = none)")
    ap.add_argument("--target", dest="target_path", default=str(_ROOT / "records" / "wall_probe"))
    args = ap.parse_args(argv)

    import main as m
    opponent_deck = sp.read_deck(args.opponent)
    summary, n_secos = play(m, opponent_deck, args.games, args.dump,
                             Path(args.target_path))

    total = sum(summary.values())
    print(f"opponent={Path(args.opponent).stem}  games={args.games}")
    print(f"turns that START stuck behind the wall with an answer ready: {total}")
    if not total:
        print("  (none: the state never happened, there is nothing to conclude)")
        return 0
    for k in ("ataca", "retira", "seco"):
        v = summary.get(k, 0)
        print(f"  {k:<7} {v:4d}  ({100 * v / total:5.1f}%)")
    if n_secos:
        print(f"\nvolcados {n_secos} dry turns in {args.target_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
