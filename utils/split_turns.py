"""Utilitario para dividir un log de partida en turnos de juego.

Un log es un JSON con la clave ``steps``: una lista de pasos que ejecuta la
logica del juego. Cada paso es a su vez una lista de items (una perspectiva por
jugador). El turno al que pertenece un paso se obtiene del mayor valor de
``observation.current.turn`` entre sus items, es decir, el turno del jugador que
esta actuando en ese momento.

No recibe parametros: toma automaticamente el unico JSON de la carpeta ``log/``
(debe haber uno y solo un archivo JSON) y lo divide COMPLETO, del primer al
ultimo turno, generando un ``registro_xxx_pasos_aaa_hasta_bbb.json`` por turno
(``xxx`` = turno, ``aaa``/``bbb`` = primer/ultimo paso del turno). Los registros
se escriben en ``registros/``, carpeta que se LIMPIA de registros antiguos antes
de generar los nuevos.
"""

import json
import os
from typing import Any

# Raiz del proyecto (carpeta padre de utils/) y carpetas de trabajo por defecto.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT_DIR, "log")
REGISTROS_DIR = os.path.join(ROOT_DIR, "registros")


def find_single_log(log_dir: str) -> str:
    """Devuelve el unico archivo JSON de ``log_dir``.

    Falla (SystemExit) si la carpeta no existe, si no hay ningun JSON o si hay
    mas de uno (en ese caso informa cuantos y cuales).
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
    """Borra los registros antiguos (``registro_*.json``) de ``out_dir``.

    Devuelve cuantos archivos se eliminaron. No toca otros archivos.
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
    """Carga el log completo y valida que contenga la lista de pasos."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "steps" not in data:
        raise ValueError(f"Se esperaba un objeto JSON con 'steps' en {path}")
    return data


def step_turn(step: Any) -> int | None:
    """Devuelve el turno de juego de un paso (el turno del jugador activo).

    Se toma el mayor ``current.turn`` entre los items del paso. Devuelve ``None``
    cuando el paso no tiene informacion de turno (p.ej. el paso inicial 0).
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
    """Devuelve el numero de paso global (``observation.step``).

    Si ningun item lo expone, se usa ``fallback`` (normalmente el indice).
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
    """Devuelve los pares ``(indice, paso)`` que pertenecen a ``turn``."""
    result = []
    for index, step in enumerate(steps):
        if step_turn(step) == turn:
            result.append((index, step))
    return result


def build_turn_record(data: dict[str, Any], turn: int, selected: list[tuple[int, Any]]) -> dict[str, Any]:
    """Construye el JSON de salida para un turno.

    Conserva todas las claves de nivel superior del log original (salvo
    ``steps``, que se reemplaza por los pasos del turno) para que el registro
    siga siendo compatible con el resto de herramientas.
    """
    record = {key: value for key, value in data.items() if key != "steps"}
    record["turn"] = turn
    record["source_step_numbers"] = [step_number(step, index) for index, step in selected]
    record["steps"] = [step for _, step in selected]
    return record


def write_turn(data: dict[str, Any], turn: int, out_dir: str) -> str:
    """Escribe ``registro_xxx.json`` con todos los pasos del turno indicado."""
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
    """Divide el log completo, del primer al ultimo turno, sin parametros.

    Toma automaticamente el unico JSON de ``log/``, limpia ``registros/`` de
    registros antiguos y genera un ``registro_xxx_pasos_aaa_hasta_bbb.json`` por
    cada turno.
    """
    logfile = find_single_log(LOG_DIR)
    out_dir = REGISTROS_DIR

    data = load_log(logfile)
    steps = data["steps"]

    # Limpiar registros antiguos antes de generar los nuevos.
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
