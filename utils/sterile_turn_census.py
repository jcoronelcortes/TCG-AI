"""Turns that ended WITHOUT ATTACKING while a line that attacked was available.

WHY IT EXISTS. The self-play gate cannot arbitrate turn quality: the bot loses
about one game in twenty however we spend the turn, so a rule that throws away a
knockout and a rule that cashes it measure the same. Six neutral changes in a
row in August 2026 were that, and four more in August 13th's session. What is
missing is not a better rule, it is a number that MOVES when turn quality does.

This is that number, and it is deliberately not the one
`utils/turn_waste_census.py` already exhausted. That tool counts resources
OFFERED and declined -- the attachment, the Supporter slot, a body for the bench
-- and its own docstring records the negative result: the agent is not leaving
resources unspent, and three rules written against that axis came back neutral.
Its closing line points here: "what is left to gain is in WHICH of several
legal, scored plays it picks". So this counts OUTCOMES, not spend. One turn, one
question: did it end with an attack, and if not, was there a line that attacked?

HOW IT ANSWERS THE TWO HALVES.

  * DID IT ATTACK -- off the engine's own log, not off the agent. A `type: 15`
    entry (`attackId`) with our `playerIndex` is an attack that happened. The
    frozen corpus stores observations WITHOUT actions, so nothing else in the
    record says what we chose; the log says what the engine did.
  * WAS THERE A LINE -- `utils/turn_explorer.py` over the FIRST main menu of the
    turn, with `respetar_menu` on so the root actions are the ones the simulator
    really offered.

WHAT IT SAID THE FIRST TIME (13-ago-2026, the 50 games of the frozen corpus,
378 of our turns):

    attacked                                     191
    sterile (ended with no attack)               187
       ...with an attacking line available        33
       ...with a line that takes a PRIZE           4

Four turns in 378 is one in 95, against the waste axis's one in 1017 -- and the
currency is prizes, which is what decides games. That is the whole case for this
tool: it has resolution where the winrate has none.

AND THAT FOUR IS AN UPPER BOUND, because of the corpus it was read from. The
frozen records are SPARSE -- one game that reached turn 18 is stored in 78
steps, where a dense record spends 26 on a single turn -- so an observation's
`logs` cover everything since the PREVIOUS RECORDED one, which can span turns.
An attack thrown on turn 12 is then credited to the next turn that has a menu,
and turn 12 reads sterile when it was not. The count can only be too high.

The fix is not in this file: it is a recorder that stores every step and the
action taken, which is also what `utils/log_replay.py` needs to compare against
anything but the fourteen hand-split records. Until then, treat the candidates
as a reading queue and the number as a ceiling that only falls.

READ THE FOUR, DO NOT TRUST THEM. The explorer is a v1 MODEL and it is
optimistic by construction: after the first transition legality goes back to its
own rules, it does not know every lock, and it does not model draws. So each
candidate is a BOARD TO READ, not a confirmed miss -- which is the same discovery
channel every rule in this repo came from. The number's job is to rank the
reading, and to move when a fix lands.

Usage:
    python utils/sterile_turn_census.py                  # the frozen corpus
    python utils/sterile_turn_census.py --detail         # plus every candidate
    python utils/sterile_turn_census.py --max-nodes 8000 # a deeper search
"""

import argparse
import copy
import gzip
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import turn_explorer as te  # noqa: E402  (after the sys.path lines, on purpose)

FROZEN = _ROOT / "tests" / "corpus" / "frozen_records.json.gz"

# Engine log type of an attack. `{'type': 15, 'playerIndex': 0, 'cardId': 920,
# 'serial': 23, 'attackId': 1326}` -- the only entry that says an attack was
# thrown, and the only witness available in a record that stores no actions.
ATTACK_LOG = 15


def our_turns(records):
    """`{(game, turn): {"first": obs, "attacked": bool}}` for OUR seat.

    `first` is the turn's first MAIN menu, which is where the explorer is asked;
    `attacked` comes off the engine's log. An attack ends the turn, so its entry
    lands on an observation that may already belong to the next one -- it is
    therefore credited to the last turn in which our seat held a menu.
    """
    turns = {}
    for name, game in records.items():
        seat = game["seat"]
        last = None
        for step in game["steps"]:
            for item in step:
                obs = item.get("observation") or {}
                current = obs.get("current")
                if current is None:
                    continue
                if current.get("yourIndex") == seat and obs.get("select"):
                    last = (name, current["turn"])
                    rec = turns.setdefault(last, {"first": None, "attacked": False})
                    if (rec["first"] is None
                            and obs["select"].get("context") == 0):
                        rec["first"] = obs
                for log in obs.get("logs") or []:
                    if (log.get("type") == ATTACK_LOG
                            and log.get("playerIndex") == seat and last):
                        turns[last]["attacked"] = True
    return turns


def census(records, max_nodes=3000):
    turns = our_turns(records)
    usable = [(k, v) for k, v in turns.items() if v["first"] is not None]
    attacked = [k for k, v in usable if v["attacked"]]
    sterile = [(k, v) for k, v in usable if not v["attacked"]]

    with_attack, with_prize = [], []
    for key, rec in sterile:
        try:
            score, line, _ = te.explore(copy.deepcopy(rec["first"]),
                                        max_nodes=max_nodes, respetar_menu=True)
        except Exception:
            continue          # a board the v1 model cannot walk is not a finding
        if not line or line[-1] != "ATTACK":
            continue
        with_attack.append((key, score, line))
        if score and score[1] > 0:
            with_prize.append((key, score, line))
    return {
        "turns": len(usable), "attacked": len(attacked),
        "sterile": len(sterile),
        "with_attack": with_attack, "with_prize": with_prize,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", default=str(FROZEN),
                    help="a .json.gz of records (default: the frozen corpus)")
    ap.add_argument("--max-nodes", type=int, default=3000,
                    help="explorer budget per turn (turn_explorer's own is 30000)")
    ap.add_argument("--detail", action="store_true",
                    help="print every candidate line, not just the counts")
    args = ap.parse_args(argv)

    with gzip.open(args.records) as fh:
        records = json.load(fh)
    out = census(records, args.max_nodes)

    print(f"our turns with a main menu : {out['turns']}")
    print(f"  attacked                 : {out['attacked']}")
    print(f"  STERILE                  : {out['sterile']}")
    print(f"    ...an attacking line was available : {len(out['with_attack'])}")
    print(f"    ...and it took a PRIZE             : {len(out['with_prize'])}"
          "   <- UPPER BOUND, see the module note")
    print("\nTwo reasons every candidate is a board to READ and not a finding: "
          "the explorer is a\nv1 model and optimistic by construction, and a "
          "sparse record credits an attack to a\nlater turn than the one that "
          "threw it.")
    for key, score, line in out["with_prize"]:
        print(f"  {key[0]} turn {key[1]}  prizes={score[1]} damage={score[2]}")
        print(f"      {' -> '.join(line)}")
    if args.detail:
        print("\n-- sterile turns with an attacking line but no prize --")
        for key, score, line in out["with_attack"]:
            if (key, score, line) in out["with_prize"]:
                continue
            print(f"  {key[0]} turn {key[1]}  damage={score[2]}: "
                  f"{' -> '.join(line)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
