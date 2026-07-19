import argparse
import json
from typing import Any

from main import agent


def load_log(path: str) -> list[Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "steps" not in data:
        raise ValueError(f"Expected a JSON object with 'steps' in {path}")
    return data["steps"]


def _is_valid_selection(action: list[int], select: dict) -> bool:
    if not isinstance(action, list):
        return False
    if len(action) == 0:
        return False
    if not all(isinstance(i, int) for i in action):
        return False
    return all(0 <= i < len(select.get("option", [])) for i in action)


def _canonical_action(action: list[int], select: dict) -> list[int] | None:
    if not isinstance(action, list):
        return None
    if len(action) > 0 and _is_valid_selection(action, select):
        return action
    if len(action) == 0 and len(select.get("option", [])) == 1:
        if select.get("minCount", 0) <= 1:
            return [0] if select.get("minCount", 0) >= 1 else []
    return None


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
            action = item.get("action")
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
                print(f"logged action: {action}")
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
