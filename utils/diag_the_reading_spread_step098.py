"""WHY THE READING NOW REACHES A SECOND BOARD (registro_007 step 98).

`test_the_reading_does_not_spread` asserts a property, not a decision: forcing
`_promoted_lethal_reply` to zero may change AT MOST a board somebody has read.
On 15 August 2026 it failed on `registro_007` step 98, turn 7 of episode
93173834.

⚠️ THE FIRST ANSWER THIS SCRIPT GAVE WAS THAT THE PREMISE WAS WRONG, and it is
worth stating because the mistake is cheap to repeat. The merge that closed the
day looked like the cause -- the flip is in the very game its three fixes came
from -- and a worktree at the previous commit "passed". It passed because
`records/` is git-ignored: the worktree had no records at all and the test
SKIPPED. Copy the records in and `2442f27` fails identically. **Nothing that day
shipped put the board there; `utils/split_turns.py` did, by re-cutting the
corpus onto a new episode at 00:31.** A control arm that cannot run the
measurement is not a control arm.

This does not make the flip a bug either, and that is the whole point of the
script: before any guard is relaxed or any switch is bounded, three questions
have to be answered in order, and each one can close the file on its own.

  1. IS IT THE LIST? A replay seeds its deck belief from `deck.csv`
     (`main.py:165`), so a record played with another sixty can move a decision
     with no rule having changed ([[una-repeticion-es-una-partida-de-la-lista-de-su-dia]]).
     Answered by replaying the same step under `deck_of_record()`.
  2. WHICH SWITCH OWNS IT? The merge shipped three, each behind a name. Turning
     them off one at a time says which one put the board within reach of the
     reading -- and a flip nobody can attribute is not a finding, it is a
     coincidence with a line number.
  3. WHAT DOES EACH READING ACTUALLY CHOOSE? The menu, both answers, and the
     board they are answered on, printed rather than summarised.

Usage:
    python utils/diag_the_reading_spread_step098.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import main as m                                    # noqa: E402
from ptcg.turn.options import retreat as R          # noqa: E402

RECORD = ROOT / "records" / "registro_007_pasos_092_hasta_103.json"
STEP = 98

#: The three switches the merge of 15 August shipped, each with the value that
#: turns it off. `main` re-exports the two that live in `ptcg/`, so the module
#: that OWNS the name is what gets patched.
SWITCHES = [
    ("CHARGE_THE_BODY_THAT_NEEDS_IT", "ptcg.turn.energy", False),
    ("DAWN_SEAT_WAITS_A_TURN", "ptcg.decision.supporters", False),
    ("FEZ_ABILITY_BEFORE_THE_KNOCKOUT", "ptcg.turn.options.play", False),
]


def _observation(step_no=STEP):
    with open(RECORD, encoding="utf-8") as f:
        data = json.load(f)
    for step in data.get("steps", []):
        for item in step:
            obs = item.get("observation") or {}
            if (item.get("status") == "ACTIVE" and obs.get("select")
                    and obs.get("step") == step_no
                    and (obs.get("current") or {}).get("yourIndex") is not None):
                return obs
    raise SystemExit(f"step {step_no} no esta en {RECORD.name}")


def _decide(obs, reading):
    """One decision, from a state reset the way the test resets it."""
    original = R._promoted_lethal_reply
    R._promoted_lethal_reply = reading
    try:
        m.AGENT_STATE.reset()
        m._init_cards_tracking()
        return list(m.agent(json.loads(json.dumps(obs))))
    finally:
        R._promoted_lethal_reply = original


def _flips(obs):
    """(with the reading, with it off) -- the test's own comparison."""
    off = lambda *a, **k: 0            # noqa: E731 -- the reply comes off their active
    return _decide(obs, R._promoted_lethal_reply), _decide(obs, off)


def _describe(obs):
    cur = obs.get("current") or {}
    mine = (obs.get("yourState") or obs.get("my") or {})
    print(f"  turn {cur.get('turn')}  step {obs.get('step')}  "
          f"yourIndex {cur.get('yourIndex')}")
    sel = obs.get("select") or {}
    print(f"  menu (context {sel.get('context')}): "
          f"{json.dumps(sel.get('option'))}")
    if mine:
        print(f"  our keys: {sorted(mine)[:12]}")


def main():
    obs = _observation()
    print("=" * 72)
    print(f"BOARD  {RECORD.name} step {STEP}")
    print("=" * 72)
    _describe(obs)

    with_reading, without = _flips(obs)
    print(f"\n  with the reading : {with_reading}")
    print(f"  reading forced 0 : {without}")
    print(f"  FLIPS: {with_reading != without}")

    # 1. Is it the list?
    print("\n" + "=" * 72)
    print("1. UNDER THE LIST OF THE RECORD")
    print("=" * 72)
    try:
        from recorded_deck import deck_of_record
        with deck_of_record():
            a, b = _flips(obs)
        print(f"  with the reading : {a}")
        print(f"  reading forced 0 : {b}")
        print(f"  FLIPS: {a != b}"
              + ("   <- the flip is the LIST, not a rule" if a == b else
                 "   <- survives the record's own list: it is a rule"))
    except Exception as exc:                              # noqa: BLE001
        print(f"  no se pudo replayar bajo la lista del registro: {exc!r}")

    # 2. Which switch owns it?
    print("\n" + "=" * 72)
    print("2. ATTRIBUTION -- one switch off at a time")
    print("=" * 72)
    import importlib
    for name, modname, off_value in SWITCHES:
        mod = importlib.import_module(modname)
        if not hasattr(mod, name):
            print(f"  {name:38s} NO ESTA en {modname}")
            continue
        original = getattr(mod, name)
        setattr(mod, name, off_value)
        try:
            a, b = _flips(obs)
        finally:
            setattr(mod, name, original)
        print(f"  {name:38s} off -> flips: {a != b}"
              + ("   <- ESTE lo trae" if a == b else ""))


if __name__ == "__main__":
    main()
