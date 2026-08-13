"""Replay a recorded game and ask the CURRENT agent what it would do now.

The debugging tool for "why did it play that". It walks a stored game log,
feeds each observation to `agent()` as it stands today, and compares the answer
against the move that was actually made when the log was recorded.

    python utils/log_replay.py <log.json>              # summary only
    python utils/log_replay.py <log.json> --verbose    # every decision
    python utils/log_replay.py <log.json> --interactive  # step through it

WHAT A MISMATCH MEANS, and it is not "a bug". The comparison is against the
PAST agent, so a mismatch is any behaviour change since the log was taken --
which is usually a fix working as intended. What the tool gives you is the
LOCATION: the step where today's agent diverges, which is where to point
`PTCG_DEBUG` or `tests/rule_trace.py` next.

THE ANSWER TO A MENU IS STORED ON THE NEXT STEP (user, records/registro_004
step 56, August 2026). A step of a Kaggle log carries the observation the agent
was given AND the `action` field -- but that action is the one that PRODUCED
this observation, not the one chosen from it. `_logged_answer` is the shift, and
until it existed this tool lined up every answer with the previous menu, so its
`mismatched` count was noise and its `--verbose` output accused the wrong step.

The records prove the alignment on their own, with no appeal to the engine.
Take any menu that demands exactly two picks (`minCount == 2`): its own step
stores a ONE-element action, which that menu could not have accepted, while the
next step stores a two-element one that matches the discard the log then writes
down. Across the fourteen records every such menu -- and only the shifted
reading -- fits. The first step of a file therefore stores an answer to a menu
that is not in the file, and the last menu of a file has no answer yet: both
count as `ignored`, which is what "not comparable" is for.

AGE THE LOG BEFORE BLAMING THE AGENT. A recorded game accuses whatever the code
looked like on the day it was recorded, so a divergence may be a defect that
has already been fixed. Check the log's date against the change first.

NOT EVERY STEP IS COMPARABLE. Observations with no `select` are skipped
entirely, and `_canonical_action` handles the case where the log stored an
empty action for a menu with a single forced option -- the engine records that
as "nothing chosen" while the agent returns the index. Steps it cannot put in
canonical form are counted as `ignored` rather than as mismatches: a
disagreement the tool is not sure about must not be reported as a finding.

Related tools: `utils/turn_explorer.py` searches for the line that WAS
available on a board, and `tests/rule_trace.py` names the rule that decided.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Run from anywhere: `python utils/log_replay.py <log>` has to find `main` the
# same way every other tool here does.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from main import agent  # noqa: E402  (after the sys.path line, on purpose)


def load_log(path: str) -> list[Any]:
    """Read a recorded game and return its `steps`. Raises if it is not one."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "steps" not in data:
        raise ValueError(f"Expected a JSON object with 'steps' in {path}")
    return data["steps"]


def _is_valid_selection(action: list[int], select: dict) -> bool:
    """Is `action` a usable list of indices into this menu's options?"""
    if not isinstance(action, list):
        return False
    if len(action) == 0:
        return False
    if not all(isinstance(i, int) for i in action):
        return False
    return all(0 <= i < len(select.get("option", [])) for i in action)


def _canonical_action(action: list[int], select: dict) -> list[int] | None:
    """The logged move in the same form the agent returns, or None.

    None means NOT COMPARABLE, and the caller counts those as ignored rather
    than as mismatches. The case that needs translating: a menu with a single
    forced option, which the log stores as an empty action while the agent
    returns the index -- comparing those raw would report a disagreement that
    does not exist.
    """
    if not isinstance(action, list):
        return None
    if len(action) > 0 and _is_valid_selection(action, select):
        return action
    if len(action) == 0 and len(select.get("option", [])) == 1:
        if select.get("minCount", 0) <= 1:
            return [0] if select.get("minCount", 0) >= 1 else []
    return None


def _logged_answer(steps: list[Any], step_index: int, item_index: int) -> Any:
    """The action that answered the menu at `steps[step_index][item_index]`.

    IT IS THE ONE STORED ON THE NEXT STEP -- see the module note. Same
    `item_index`, because each seat answers its own menus.

    `None` means the log does not hold the answer: the menu is the last one of
    the file, or that seat is not present on the following step. The caller
    hands it to `_canonical_action`, which returns `None` in turn, and the step
    is counted as ignored rather than as a disagreement.
    """
    nxt = step_index + 1
    if nxt >= len(steps):
        return None
    step = steps[nxt]
    if not isinstance(step, list) or item_index >= len(step):
        return None
    return step[item_index].get("action")


def _format_option(option: dict, index: int) -> str:
    keys = [k for k in ("type", "area", "index", "playerIndex", "attackId", "number") if k in option]
    props = ", ".join(f"{k}={option[k]}" for k in keys)
    return f"[{index}] {{ {props} }}"


def _format_select(select: dict) -> str:
    opts = select.get("option", [])
    return (
        f"type={select.get('type')} context={select.get('context')} "
        f"min={select.get('minCount')} max={select.get('maxCount')} opts={len(opts)}"
    )


def _format_options(select: dict, max_show: int = 10) -> str:
    opts = select.get("option", [])
    formatted = [ _format_option(opt, idx) for idx, opt in enumerate(opts[:max_show]) ]
    if len(opts) > max_show:
        formatted.append(f"... +{len(opts) - max_show} more options")
    return "\n    ".join(formatted)


def _step_prompt() -> bool:
    try:
        value = input("Press Enter to continue, 'q' to quit: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return value != "q"


def replay_log(path: str, max_items: int | None = None, verbose: bool = False, interactive: bool = False) -> dict:
    """Replay the whole log through today's agent and tally the comparison.

    Returns `{processed, compared, matched, mismatched, ignored}`. `compared`
    is the honest denominator -- `processed` counts every decision replayed,
    but only the steps `_canonical_action` could put in comparable form are
    scored. Read `mismatched` against `compared`, never against `processed`.
    """
    steps = load_log(path)
    processed = 0
    compared = 0
    matched = 0
    mismatched = 0
    ignored = 0
    last_turn = None

    for step_index, step in enumerate(steps):
        for item_index, item in enumerate(step):
            obs = item.get("observation")
            if not isinstance(obs, dict):
                continue
            select = obs.get("select")
            if select is None:
                continue
            current = obs.get("current")
            if current is None:
                continue

            processed += 1
            action = _logged_answer(steps, step_index, item_index)
            agent_choice = agent(obs)
            logged_choice = _canonical_action(action, select)
            current_turn = current.get("turn")

            if verbose or interactive:
                if current_turn != last_turn:
                    print(f"\n=== TURN {current_turn} ===")
                    last_turn = current_turn
                print(f"step={step_index} item={item_index} {_format_select(select)}")
                print("options:")
                print(f"    {_format_options(select)}")
                print(f"agent choice: {agent_choice}")
                print(f"logged action (stored on step {step_index + 1}): {action}")
                print(f"logged choice: {logged_choice}")
                print()

            if interactive:
                if not _step_prompt():
                    return {
                        "processed": processed,
                        "compared": compared,
                        "matched": matched,
                        "mismatched": mismatched,
                        "ignored": processed - compared,
                    }

            if logged_choice is not None:
                compared += 1
                if agent_choice == logged_choice:
                    matched += 1
                else:
                    mismatched += 1

            if max_items is not None and processed >= max_items:
                break
        if max_items is not None and processed >= max_items:
            break

    return {
        "processed": processed,
        "compared": compared,
        "matched": matched,
        "mismatched": mismatched,
        "ignored": processed - compared,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay a Kaggle PTCG AI game log and run the local agent on each observation."
    )
    parser.add_argument("logfile", help="Path to a game log JSON file.")
    parser.add_argument("--max-items", type=int, default=None, help="Stop after this many actionable observations.")
    parser.add_argument("--verbose", action="store_true", help="Print each actionable observation and agent decision.")
    parser.add_argument("--interactive", action="store_true", help="Step through each actionable observation interactively.")
    args = parser.parse_args()

    summary = replay_log(
        args.logfile,
        max_items=args.max_items,
        verbose=args.verbose,
        interactive=args.interactive,
    )
    print("Replay summary:")
    print(f"  processed: {summary['processed']}")
    print(f"  compared:  {summary['compared']}")
    print(f"  matched:   {summary['matched']}")
    print(f"  mismatched:{summary['mismatched']}")
    print(f"  ignored:   {summary['ignored']}")


if __name__ == "__main__":
    main()
