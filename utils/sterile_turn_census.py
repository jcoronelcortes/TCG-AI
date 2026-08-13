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

WHAT IT SAID THE FIRST TIME (13-ago-2026, 24 dense games, 180 of our turns):

    attacked                                     101
    sterile (ended with no attack)                79
       ...with an attacking line available         6
       ...with a line that takes a PRIZE           2

Two turns in 180 is one in ninety, against the waste axis's one in 1017 -- and
the currency is prizes, which is what decides games. That is the whole case for
this tool: it has resolution where the winrate has none.

READ IT FROM A DENSE SOURCE. The same census over the frozen bundle answered 4
in 378 -- the same rate, and a CEILING rather than a number, because that bundle
stores no answers and the attack has to be inferred from the engine's logs. An
observation's `logs` cover everything since the previous RECORDED step, so where
the bundle skips, an attack thrown on turn 12 is credited to turn 14 and turn 12
reads sterile when it was not: it over-counted the sterile turns by a fifth and
the candidates by three times. `utils/record_corpus.py` now writes each step's
own answer under `chosen`, which is what makes the dense reading exact.

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
import re
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

# Menu option type of an attack, which is what a DENSE record lets us read
# directly off the answer instead of inferring it.
ATTACK_OPTION = 13


def load_records(path):
    """`{name: {"seat": int, "steps": [...]}}` from either shape of record.

    A DIRECTORY is a set of dense records from `utils/record_corpus.py`: every
    step, and every step's own answer under `chosen`. A `.json.gz` is the frozen
    bundle, which carries the seat but no answers at all. The difference decides
    how `our_turns` can tell whether the turn attacked, and it is the whole
    reason this tool has two readings of the same question.
    """
    p = Path(path)
    if p.is_dir():
        out = {}
        for f in sorted(p.glob("registro_*.json")):
            seat = re.search(r"_asiento(\d)", f.stem)
            out[f.name] = {"seat": int(seat.group(1)) if seat else 0,
                           "steps": json.loads(f.read_text())["steps"]}
        return out
    with gzip.open(p) as fh:
        return json.load(fh)


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
                    # DENSE: the answer to this very menu is on this very step,
                    # so "did the turn attack" stops being an inference.
                    options = obs["select"].get("option") or []
                    for i in item.get("chosen") or []:
                        if (isinstance(i, int) and i < len(options)
                                and options[i].get("type") == ATTACK_OPTION):
                            rec["attacked"] = True
                if "chosen" in item:
                    continue          # a dense record needs no log-reading
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
                    help="a .json.gz bundle or a FOLDER of dense records from "
                         "utils/record_corpus.py (default: the frozen corpus)")
    ap.add_argument("--max-nodes", type=int, default=3000,
                    help="explorer budget per turn (turn_explorer's own is 30000)")
    ap.add_argument("--detail", action="store_true",
                    help="print every candidate line, not just the counts")
    args = ap.parse_args(argv)

    records = load_records(args.records)
    dense = any("chosen" in step[0] for game in records.values()
                for step in game["steps"][:1])
    out = census(records, args.max_nodes)
    shape = ("DENSE -- the answer is read, not inferred" if dense
             else "no answers stored, the attack is inferred from the logs")
    print(f"source: {args.records}  ({shape})")

    print(f"our turns with a main menu : {out['turns']}")
    print(f"  attacked                 : {out['attacked']}")
    print(f"  STERILE                  : {out['sterile']}")
    print(f"    ...an attacking line was available : {len(out['with_attack'])}")
    bound = "" if dense else "   <- UPPER BOUND, see the module note"
    print(f"    ...and it took a PRIZE             : {len(out['with_prize'])}{bound}")
    print("\nEvery candidate is a board to READ and not a finding: the explorer "
          "is a v1 model\nand optimistic by construction.")
    if not dense:
        print("And on this source the attack is inferred from the logs, which "
              "credits it to a\nlater turn whenever the bundle skips steps: "
              "the count can only be too high.")
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
