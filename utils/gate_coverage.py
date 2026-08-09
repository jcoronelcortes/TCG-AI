"""Per-module coverage floors: new code cannot land unwatched.

T0.2 of docs/testing-plan-2026-08.md. The measurement that motivated it:
`ptcg/turn/options/evolve.py` reached SIX PER CENT covered without anyone
noticing, and the diff being written that week touched it. Six of the seven
files modified that day sat in the 26-45 % band, which is the opposite of where
a suite should be strong -- new rules were being written into the least watched
part of the tree.

WHAT THIS IS NOT. It is not a claim that 51 % of the agent is tested. The unit
suite is one of four gates: the golden corpus replays real games, self-play
plays thousands more, and both execute code this number never sees. The floor
is a RATCHET on the unit net specifically -- it stops that net from being
loosened -- and nothing more.

WHY FLOORS RATHER THAN A SINGLE TARGET. A global percentage hides exactly the
case that hurt: a 3 000-statement module going up two points while a 200-line
decision module goes to zero nets out flat. Per module, the drop is visible and
it is attributable to the diff that caused it.

THE TOLERANCE. Coverage is deterministic for a given (code, suite) pair, but a
refactor that deletes covered statements moves the percentage without anyone
testing less. So the gate allows a drop of TOLERANCE points before it fails, and
a real regression is far larger than that. Raise the floors with `--update`
whenever the measurement improves; lowering one is a judgement call that belongs
in a commit message, not in a flag.

Usage:
    python -m pytest -q --cov=main --cov=ptcg --cov-report=json:coverage.json
    python utils/gate_coverage.py --check coverage.json
    python utils/gate_coverage.py --update coverage.json
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
FLOORS = _ROOT / "coverage-floors.json"

# Points a module may drop before the gate fails. See "THE TOLERANCE" above.
TOLERANCE = 0.5

# Modules below this many statements are not floored: their percentage jumps by
# whole digits on a one-line change, which is noise rather than signal.
MIN_STATEMENTS = 40

README = ("Per-module floors for the UNIT suite only, produced by "
          "utils/gate_coverage.py --update. A drop of more than "
          f"{TOLERANCE} points fails the gate. Raising a floor needs no "
          "explanation; lowering one does, and it belongs in the commit "
          "message.")


def _measured(report):
    data = json.loads(Path(report).read_text(encoding="utf-8"))
    out = {}
    for path, entry in data["files"].items():
        summary = entry["summary"]
        if summary["num_statements"] < MIN_STATEMENTS:
            continue
        out[path] = round(summary["percent_covered"], 1)
    return out


def _floors():
    if not FLOORS.exists():
        return {}
    stored = json.loads(FLOORS.read_text(encoding="utf-8"))
    return {k: v for k, v in stored.items() if not k.startswith("_")}


def update(report):
    measured = _measured(report)
    floors = _floors()
    raised, added = [], []
    for path, value in sorted(measured.items()):
        if path not in floors:
            added.append((path, value))
        elif value > floors[path]:
            raised.append((path, floors[path], value))
    merged = dict(floors)
    merged.update({p: max(v, floors.get(p, 0)) for p, v in measured.items()})
    payload = {"_readme": README}
    payload.update({k: merged[k] for k in sorted(merged)})
    FLOORS.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    for path, value in added:
        print(f"  nuevo   {value:5.1f}%  {path}")
    for path, old, new in raised:
        print(f"  sube    {old:5.1f}% -> {new:5.1f}%  {path}")
    print(f"{len(merged)} suelos escritos en {FLOORS.name} "
          f"({len(added)} nuevos, {len(raised)} subidos)")
    return 0


def check(report):
    measured = _measured(report)
    floors = _floors()
    if not floors:
        print("No hay suelos todavia: corre --update una vez.", file=sys.stderr)
        return 2
    broken = []
    for path, floor in sorted(floors.items()):
        if path not in measured:
            continue                      # deleted or renamed: not this gate's job
        if measured[path] < floor - TOLERANCE:
            broken.append((path, floor, measured[path]))
    unfloored = [p for p in measured if p not in floors]
    for path in sorted(unfloored):
        print(f"  sin suelo  {measured[path]:5.1f}%  {path}  "
              f"(corre --update para fijarlo)")
    if not broken:
        print(f"Cobertura: {len(floors)} modulos, ninguno por debajo de su suelo "
              f"(tolerancia {TOLERANCE} puntos).")
        return 0
    print("\nCOBERTURA POR DEBAJO DEL SUELO:", file=sys.stderr)
    for path, floor, value in broken:
        print(f"  {path}: {value:.1f}% < {floor:.1f}%  "
              f"(-{floor - value:.1f} puntos)", file=sys.stderr)
    print("\nEl codigo nuevo entra sin vigilancia, que es exactamente lo que "
          "este gate existe para impedir.", file=sys.stderr)
    return 1


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("report", nargs="?", default="coverage.json",
                        help="el JSON de pytest-cov")
    parser.add_argument("--update", action="store_true",
                        help="sube los suelos a la medida de ahora")
    parser.add_argument("--check", action="store_true",
                        help="falla si algun modulo baja de su suelo (por defecto)")
    args = parser.parse_args(argv)
    if not Path(args.report).exists():
        print(f"No existe {args.report}. Genera el informe primero:\n"
              f"  python -m pytest -q --cov=main --cov=ptcg "
              f"--cov-report=json:{args.report}", file=sys.stderr)
        return 2
    if args.update:
        return update(args.report)
    return check(args.report)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
