"""Utility to split a game log into game turns.

A log is a JSON with the key ``steps``: a list of steps the game
logic executes. Each step is itself a list of items (one perspective per
player). The turn a step belongs to is obtained from the highest value of
``observation.current.turn`` among its items, that is, the turn of the player who
is acting at that moment.

It takes no parameters: it automatically picks the only JSON in the ``log/`` folder
(there must be one and only one JSON file) and splits it COMPLETELY, from the first to the
last turn, generating one ``registro_xxx_pasos_aaa_hasta_bbb.json`` per turn
(``xxx`` = the turn, ``aaa``/``bbb`` = the first/last step of the turn). The records
are written into ``registros/``, a folder that is CLEARED of old records before
the new ones are generated.
"""

import json
import os
from typing import Any

# The project root (the parent folder of utils/) and the default working folders.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT_DIR, "log")
REGISTROS_DIR = os.path.join(ROOT_DIR, "registros")


def find_single_log(log_dir: str) -> str:
    """Returns the only JSON file in ``log_dir``.

    It fails (SystemExit) if the folder does not exist, if there is no JSON or if there is
    more than one (in that case it reports how many and which).
    """
    if not os.path.isdir(log_dir):
        raise SystemExit(f"No existe la carpeta de logs: {log_dir}")
    jsons = sorted(
        name for name in os.listdir(log_dir)
        if name.lower().endswith(".json")
        and os.path.isfile(os.path.join(log_dir, name))
    )
    if not jsons:
        raise SystemExit(f"No hay ningun archivo JSON en {log_dir}.")
    if len(jsons) > 1:
        raise SystemExit(
            f"Existe mas de un archivo JSON en {log_dir} "
            f"({len(jsons)}: {', '.join(jsons)}); debe haber uno y solo uno."
        )
    return os.path.join(log_dir, jsons[0])


def clean_registros(out_dir: str) -> int:
    """Deletes the old records (``registro_*.json``) from ``out_dir``.

    It returns how many files were removed. It does not touch other files.
    """
    if not os.path.isdir(out_dir):
        return 0
    removed = 0
    for name in os.listdir(out_dir):
        if name.startswith("registro_") and name.lower().endswith(".json"):
            os.remove(os.path.join(out_dir, name))
            removed += 1
    return removed


def load_log(path: str) -> dict[str, Any]:
    """Loads the complete log and validates that it contains the list of steps."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "steps" not in data:
        raise ValueError(f"Se esperaba un objeto JSON con 'steps' en {path}")
    return data


def step_turn(step: Any) -> int | None:
    """Returns the game turn of a step (the active player's turn).

    The highest ``current.turn`` among the step's items is taken. It returns ``None``
    when the step has no turn information (e.g. the initial step 0).
    """
    turns = []
    if isinstance(step, list):
        items = step
    else:
        items = [step]
    for item in items:
        if not isinstance(item, dict):
            continue
        current = item.get("observation", {}).get("current")
        if isinstance(current, dict) and isinstance(current.get("turn"), int):
            turns.append(current["turn"])
    return max(turns) if turns else None


def step_number(step: Any, fallback: int) -> int:
    """Returns the global step number (``observation.step``).

    If no item exposes it, ``fallback`` is used (normally the index).
    """
    if isinstance(step, list):
        items = step
    else:
        items = [step]
    for item in items:
        if not isinstance(item, dict):
            continue
        obs = item.get("observation")
        if isinstance(obs, dict) and isinstance(obs.get("step"), int):
            return obs["step"]
    return fallback


def steps_of_turn(steps: list[Any], turn: int) -> list[tuple[int, Any]]:
    """Returns the ``(index, step)`` pairs that belong to ``turn``."""
    result = []
    for index, step in enumerate(steps):
        if step_turn(step) == turn:
            result.append((index, step))
    return result


def build_turn_record(data: dict[str, Any], turn: int, selected: list[tuple[int, Any]]) -> dict[str, Any]:
    """Builds the output JSON for a turn.

    It keeps every top-level key of the original log (except
    ``steps``, which is replaced by the turn's steps) so the record
    stays compatible with the rest of the tools.
    """
    record = {key: value for key, value in data.items() if key != "steps"}
    record["turn"] = turn
    record["source_step_numbers"] = [step_number(step, index) for index, step in selected]
    record["steps"] = [step for _, step in selected]
    return record


def write_turn(data: dict[str, Any], turn: int, out_dir: str) -> str:
    """Writes ``registro_xxx.json`` with every step of the given turn."""
    selected = steps_of_turn(data["steps"], turn)
    if not selected:
        raise ValueError(f"El turno {turn} no tiene pasos en el log")

    os.makedirs(out_dir, exist_ok=True)
    step_numbers = [step_number(step, index) for index, step in selected]
    first_step = min(step_numbers)
    last_step = max(step_numbers)
    filename = f"registro_{turn:03d}_pasos_{first_step:03d}_hasta_{last_step:03d}.json"
    out_path = os.path.join(out_dir, filename)
    record = build_turn_record(data, turn, selected)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return out_path


def main() -> None:
    """Splits the complete log, from the first to the last turn, with no parameters.

    It automatically takes the only JSON in ``log/``, clears ``registros/`` of
    old records and generates one ``registro_xxx_pasos_aaa_hasta_bbb.json`` per
    turn.
    """
    logfile = find_single_log(LOG_DIR)
    out_dir = REGISTROS_DIR

    data = load_log(logfile)
    steps = data["steps"]

    # Clear the old records before generating the new ones.
    removed = clean_registros(out_dir)
    if removed:
        print(f"Limpieza: {removed} registro(s) antiguo(s) eliminado(s) de {out_dir}.")

    print(f"Log: {logfile}")
    turnos = sorted({t for t in (step_turn(s) for s in steps) if t is not None})
    for turn in turnos:
        path = write_turn(data, turn, out_dir)
        count = len(steps_of_turn(steps, turn))
        print(f"Turno {turn}: {count} pasos -> {path}")
    print(f"Total: {len(turnos)} turnos extraidos.")


if __name__ == "__main__":
    main()
